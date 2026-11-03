"""Resolution of a template chain against a conforming submodel instance  (paper §3.6).

A chain is written against the template, in which every repeatable element has exactly one
representative. Resolution rewrites it, before anything is applied, into a concrete chain for one
instance. It simulates the chain on the template and on a copy of the instance side by side and
keeps, for every template element t, its realisations R(t) in the instance.

Matching (start state): rules M1, M2 of tcn.core.matching.

Expansion
  E1  An item naming a template element yields one item per realisation, in document order.
  E2  An item whose element has no realisation is elided if the branch is optional in the template
      (cardinality ZeroToOne/ZeroToMany on the way up to a realised ancestor, as last stated before,
      during or after the change) or if the element is a
      placeholder (it names no concrete element); otherwise it is refused (SEMANTIC_MATCH_NONE).

Created elements
  C1  The origin of a created element is the lowest common ancestor, in the template before the
      change, of all elements the chain moves directly into it or whose values it synchronises
      into it (Sync). It is realised once per realisation of its origin, below the parent
      realisation that belongs together with it: the one whose own origin shares the deepest common
      ancestor with it in the instance before the change.
      (ProductClassifications[0] <- children of ProductClassificationItem: one entry per item.)
      If the origin has no realisation, the element is handled as in C2.
  C2  A created element without origin is realised once per parent realisation; it is elided if it
      is optional in the template after the change and no created descendant has an origin, and if
      it is a placeholder, whose realisations only the instance can define. A mandatory data element
      created this way has no value yet: the asset maintainer is asked to provide it.

Template-level constructs and instance data
  T1  Qualifiers are template constructs: every item on a qualifier, or a Sync over qualifier
      attributes, is elided.
  T2  Values are instance data: the attributes that hold the value of an element of its type
      (tcn.core.metamodel.instance_data, e.g. value and valueId, min and max, the contentType of a
      File, first and second of a relationship). UpdateAttr and RemoveAttr of them are elided, so
      template example values never overwrite instance values. Instance values are carried over
      by moving their element (UpdateParent) or by Sync.
  T3  The identity of the instance (root attributes id, kind and administration, which declares the
      template the instance conforms to) is not taken over from the template.
  T4  Attribute items are elided for placeholder realisations (instance-defined metadata).
  T5  UpdateIdShort applies to realisations named as in the template, and to realisations whose
      element occurs at most once after the change (its name is then fixed by the template, e.g.
      ProductImage01 -> ImageFile). Names chosen by the instance for repeatable elements (e.g.
      MainSection01, Width) are kept.

Containers with instance content
  H1  UpdateParent of a realisation that has children in the instance (content the template does
      not describe) follows the Hollow-Out pattern: a container of the same type, name and
      attributes is created at the target, the children are moved into it (recursively), and the
      emptied original is removed. Children, and thereby their values, keep their identity.
  H2  A chain may itself rebuild a container: create its counterpart (origin: the container), move
      the children the template describes, remove the container. Children the template does not
      describe are left in the realisation; before it is removed, they are moved into the
      counterpart created for it, as in H1. Without a counterpart, the removal is refused.

Values
  V1  Every instance value (T2) the chain removes without carrying it over automatically (by moving
      its element, or by an executable Sync) is reported as removed, at its path before the change.
  V2  Every instance value an executable Sync carries over is reported as transferred, with the
      value before and after.

Names
  N1  If moving a realisation would collide with a sibling's idShort, it is first renamed to
      <idShort>__<n>; once its template name is free again, it is renamed back. These renames are
      inserted by the resolution and reported as such.
  N2  An entry of a SubmodelElementList is addressed by its index. An entry the resolution creates
      in a list, or moves into one, carries no idShort, even where the template names it. An entry
      that leaves a list takes the name it is to carry before it moves (N1); without one, the chain
      is refused.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tcn.core import operators as ops
from tcn.core.addressing import Item, split_attribute_ref
from tcn.core.guarded import ACC, REJ, Unbound, apply_in_place
from tcn.core.matching import CARDINALITY_TYPES, match
from tcn.core.matching import card as _card
from tcn.core.matching import placeholder as _placeholder
from tcn.core.metamodel import instance_data
from tcn.core.model import LAMBDA, Id, Template

OPTIONAL = {"ZeroToOne", "ZeroToMany"}
DATA_ELEMENTS = {"Property", "MultiLanguageProperty", "Range", "File", "Blob", "ReferenceElement"}
ROOT_IDENTITY = {"id", "kind", "administration"}


class Refused(Exception):
    pass


@dataclass
class Note:
    index: int  # 1-based index of the template item
    kind: str  # expanded | elided | inserted | manual | transferred | removed | refused
    detail: str
    path: str | None = None  # manual: the element concerned, as a path of the template after the change


@dataclass
class Resolution:
    status: str
    items: list[Item] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    reason: str | None = None

    def count(self, kind: str) -> int:
        return sum(n.kind == kind for n in self.notes)


# --- template analysis --------------------------------------------------------------------


def _lca(T: Template, xs: set[Id]) -> Id:
    def chain(x):
        return [x] + (chain(T.E[x].parent) if T.E[x].parent is not None else [])
    common = set.intersection(*(set(chain(x)) for x in xs))
    return next(x for x in chain(next(iter(xs))) if x in common)


@dataclass
class _Analysis:
    origin: dict[Id, Id]  # created element -> origin (C1)
    carrying: dict[Id, set[Id]]  # created element -> created elements with an origin at or below it
    card: dict[Id, str]  # element -> cardinality as last stated before, during or after the change
    final: Template


def _analyse(items: list[Item], pre: Template) -> _Analysis:
    T, moved, created = pre.copy(), {}, {}  # created: element -> parent at creation
    card = {e: c for e in T.E if (c := _card(T, e))}
    for item in items:
        op = item.bind(T)
        if isinstance(op, ops.CreateSME):
            created[T.next_ids(1)[0]] = op.p
        received = []  # (element receiving content, element the content comes from)
        if isinstance(op, ops.UpdateParent):
            received = [(op.p, op.e)]
        if isinstance(op, ops.Sync):
            owners = lambda xs: [T.A[a].owner for a in xs if T.A[a].owner in T.E]  # noqa: E731
            received = [(t, s) for t in owners(op.tgt) for s in owners(op.src)]
        for target, source in received:
            while target is not None and target not in created:
                target = T.E[target].parent  # the nearest created element receives the content
            if target is not None:
                moved.setdefault(target, set()).add(source)
        outcome = apply_in_place(op, T)  # T is a working copy of pre
        assert outcome.status == ACC, f"chain is rejected on its own template: {item}"
        for _, x in op.mod(T) if isinstance(op, (ops.UpdateAttr, ops.Sync)) else ():
            if x in T.A and T.A[x].name == "value" and T.A[x].owner in T.Q \
                    and T.Q[T.A[x].owner].qtype in CARDINALITY_TYPES and isinstance(T.A[x].value, str):
                card[T.Q[T.A[x].owner].elem] = T.A[x].value

    origin: dict[Id, Id] = {}

    def resolve_origin(x: Id) -> Id:
        return x if x in pre.E else origin.get(x, x)

    for e in sorted(moved):  # creation order, so origins of created sources are known
        origin[e] = _lca(pre, {resolve_origin(x) for x in moved[e]})
    carrying: dict[Id, set[Id]] = {}
    for d in origin:
        e = d
        while e in created:  # the parent at creation, even if the chain removes the element later
            carrying.setdefault(e, set()).add(d)
            e = created[e]
    return _Analysis(origin, carrying, card, T)


# --- resolution ---------------------------------------------------------------------------


class _Resolver:
    def __init__(self, items: list[Item], pre: Template, instance: Template):
        a = _analyse(items, pre)
        self.origin, self.carrying, self.card, self.final = a.origin, a.carrying, a.card, a.final
        self.T, self.I, self.I0 = pre.copy(), instance.copy(), instance
        self.key: dict[Id, Id] = {}  # created realisation -> origin realisation (baseline id)
        m = match(self.T, self.I)  # M1, M2
        self.R, self.named, self.wild = m.R, m.named, m.wild  # named: T5; wild: placeholders, T4
        self.desired: dict[Id, str] = {}  # template name of a temporarily renamed realisation (N1)
        self.elided: set[Id] = set()  # created template elements not realised (C2), with descendants
        self.transferred: set[Id] = set()  # instance attributes whose values an executable Sync carried over
        self.out, self.notes, self.index = [], [], 0

    # --- helpers ---------------------------------------------------------------------------

    def note(self, kind: str, detail: str, path: str | None = None) -> None:
        self.notes.append(Note(self.index, kind, detail, path))

    def emit(self, operation: str, path: str, inserted: bool = False, **kw) -> None:
        item = Item(operation, path, **kw)
        try:
            op = item.bind(self.I)
        except Unbound as u:
            raise Refused(f"{u.code}: {item}")
        outcome = apply_in_place(op, self.I)  # self.I is a working copy of the instance
        if outcome.status == REJ:
            raise Refused(f"{outcome.reason}: {operation} {path}")
        self.out.append(item)
        if inserted:
            self.note("inserted", f"{operation} {path} {kw.get('new_id_short', '')}".strip())

    def realisations(self, t: Id, what: str) -> list[Id]:
        if t in self.elided:
            self.note("elided", f"{what} {self.T.path(t)}: element not created in the instance")
            return []
        rs = self.R.get(t, [])
        if not rs and t in self.T.E and not self._optional(t) and not _placeholder(self.T, t):
            raise Refused(f"SEMANTIC_MATCH_NONE: {what} {self.T.path(t)}")
        if not rs:
            self.note("elided", f"{what} {self.T.path(t)}: optional branch not realised")
        return rs

    def _optional(self, t: Id) -> bool:
        while t is not None and not self.R.get(t):
            if self.card.get(t) in OPTIONAL:
                return True
            t = self.T.E[t].parent
        return False

    def _ancestors0(self, x: Id) -> set[Id]:
        x = self.key.get(x, x)
        result = set()
        while x is not None and x in self.I0.E:
            result.add(x)
            x = self.I0.E[x].parent
        return result

    def pick(self, p: Id, anchor: Id) -> Id | None:
        """The realisation of p that belongs together with `anchor`: the one whose origin shares the
        deepest common ancestor with it in the instance before the change (unique, or None)."""
        rs = self.R.get(p, [])
        if len(rs) == 1:
            return rs[0]
        anc = self._ancestors0(anchor)
        depth = {r: len(self._ancestors0(self.key.get(r, r)) & anc) for r in rs}
        best = max(depth.values(), default=0)
        matches = [r for r in rs if depth[r] == best]
        return matches[0] if best and len(matches) == 1 else None

    def _free_name(self, parent: Id, name: str) -> str:
        taken = {self.I.E[c].id_short for c in self.I.children(parent)}
        n = 2
        while f"{name}__{n}" in taken:
            n += 1
        return name if name not in taken else f"{name}__{n}"

    # --- one template item -----------------------------------------------------------------

    def item(self, item: Item) -> None:
        op = item.bind(self.T)
        if item.qualifier_type or isinstance(op, (ops.CreateQual, ops.RemoveQual)) or (
                isinstance(op, ops.Sync) and any("@" in r for r in item.source_paths + item.target_paths)):
            self.note("elided", f"{item.operation}: qualifier (template construct)")
        else:
            getattr(self, "_" + type(op).__name__)(op, item)
        apply_in_place(op, self.T)  # self.T is a working copy of pre

    def _CreateSME(self, op: ops.CreateSME, item: Item) -> None:
        e = self.T.next_ids(1)[0]
        self.R[e] = []
        if op.p in self.elided:
            self.elided.add(e)
            self.note("elided", f"CreateSME {item.element_path}: parent not created in the instance")
            return
        sourced = e in self.origin and bool(self.R.get(self.origin[e]))
        if sourced:
            pairs = [(a, self.pick(op.p, a)) for a in self.R[self.origin[e]]]
        elif not any(self.R.get(self.origin[d]) for d in self.carrying.get(e, ())) and (
                self.card.get(e) in OPTIONAL or "arbitrary" in (op.s or "").lower()):
            self.elided.add(e)
            self.note("elided", f"CreateSME {item.element_path}: optional element, no content")
            return
        else:
            pairs = [(self.key.get(r, r), r) for r in self.R.get(op.p, [])]
        if not pairs:
            self.realisations(op.p, "CreateSME below")
        for anchor, parent in pairs:
            if parent is None:
                raise Refused(f"AMBIGUOUS_PARENT: {item.element_path}")
            if self.I.E[parent].type == "SubmodelElementList":
                path, name = f"{self.I.path(parent)}[{len(self.I.children(parent))}]", None
            else:
                name = self._free_name(parent, op.s)
                path = f"{self.I.path(parent)}.{name}".lstrip(".")
            self.emit("CreateSME", path, sme_type=op.t)
            r = self.I.children(parent)[-1]
            self.R[e].append(r)
            self.key[r] = anchor
            self.named.add(r)
            if name != op.s and name is not None:  # an entry of a list is addressed by its index (N2)
                self.desired[r] = op.s
        self.note("expanded", f"CreateSME {item.element_path}: {len(pairs)}")
        if pairs and not sourced and op.t in DATA_ELEMENTS:
            self.note("manual", "Mandatory: a value is to be provided.", self.final.path(e))

    def _attr_owner(self, a: Id) -> tuple[Id, str]:
        return self.T.A[a].owner, self.T.A[a].name

    def _attribute_item(self, owner: Id, name: str, item: Item, make) -> None:
        if name in instance_data(self.T.tau(owner)) and item.operation != "CreateAttr":
            self.note("elided", f"{item.operation} {item.element_path}#{name}: instance data")
            return
        if owner == self.T.root and name in ROOT_IDENTITY:
            self.note("elided", f"{item.operation} #{name}: identity of the instance")
            return
        for r in self.realisations(owner, item.operation):
            if r in self.wild:
                self.note("elided", f"{item.operation} {self.I.path(r)}#{name}: instance-defined")
                continue
            make(r)

    def _CreateAttr(self, op: ops.CreateAttr, item: Item) -> None:
        def make(r):
            if self.I.attr(r, op.n) is None:
                self.emit("CreateAttr", self.I.path(r), attribute_key=op.n)
        self._attribute_item(op.x, op.n, item, make)

    def _UpdateAttr(self, op: ops.UpdateAttr, item: Item) -> None:
        owner, name = self._attr_owner(op.a)

        def make(r):
            if self.I.attr(r, name) is None:
                self.emit("CreateAttr", self.I.path(r), inserted=True, attribute_key=name)
            self.emit("UpdateAttr", self.I.path(r), attribute_key=name, attribute_value=op.v)
        self._attribute_item(owner, name, item, make)

    def _RemoveAttr(self, op: ops.RemoveAttr, item: Item) -> None:
        owner, name = self._attr_owner(op.a)

        def make(r):
            if self.I.attr(r, name) is not None:
                self.emit("RemoveAttr", self.I.path(r), attribute_key=name)
        self._attribute_item(owner, name, item, make)

    def _UpdateIdShort(self, op: ops.UpdateIdShort, item: Item) -> None:
        if op.e == self.T.root:
            self.emit("UpdateIdShort", "", new_id_short=op.s)
            return
        single = (_card(self.final, op.e) or self.card.get(op.e)) in {"One", "ZeroToOne"}
        for r in self.realisations(op.e, "UpdateIdShort"):
            if r not in self.named and not single:
                self.note("elided", f"UpdateIdShort {self.I.path(r)}: name chosen by the instance")
                continue
            if op.s in {self.I.E[c].id_short for c in self.I.children(self.I.E[r].parent)}:
                self.desired[r] = op.s  # applied once the name is free (N1)
            else:
                self.emit("UpdateIdShort", self.I.path(r), new_id_short=op.s)

    def _restore_name(self, r: Id) -> None:
        """N1: rename back to the template name as soon as it is free."""
        want = self.desired.get(r)
        if want and self.I.E[r].id_short != want and \
                want not in {self.I.E[c].id_short for c in self.I.children(self.I.E[r].parent)}:
            self.emit("UpdateIdShort", self.I.path(r), inserted=True, new_id_short=want)
            del self.desired[r]

    def _UpdateParent(self, op: ops.UpdateParent, item: Item) -> None:
        rs = self.realisations(op.e, "UpdateParent")
        for r in rs:
            target = self.pick(op.p, r)
            if target is None:
                raise Refused(f"AMBIGUOUS_PARENT: {item.element_path} -> {item.new_parent_path}")
            self._move(r, target)
        self.note("expanded", f"UpdateParent {item.element_path}: {len(rs)}")

    def _move(self, r: Id, target: Id) -> Id:
        name = self.I.E[r].id_short
        in_list = self.I.E[target].type == "SubmodelElementList"
        if self.I.children(r):
            return self._hollow_out(r, target)
        if name is None and not in_list:  # an entry leaving a list takes its name first (N2)
            self._restore_name(r)
            name = self.I.E[r].id_short
            if name is None:
                raise Refused(f"IDSHORT_REQUIRED: {self.I.path(r)} leaves its list without a name")
        if name is not None and not in_list:
            free = self._free_name(target, name)
            if free != name:
                self.desired.setdefault(r, name)
                self.emit("UpdateIdShort", self.I.path(r), inserted=True, new_id_short=free)
        self.emit("UpdateParent", self.I.path(r), new_parent_path=self.I.path(target))
        self._restore_name(r)
        return r

    def _hollow_out(self, r: Id, target: Id) -> Id:
        """H1: move a container that has instance content."""
        el = self.I.E[r]
        if self.I.E[target].type == "SubmodelElementList":
            path = f"{self.I.path(target)}[{len(self.I.children(target))}]"
        else:
            path = f"{self.I.path(target)}.{self._free_name(target, el.id_short)}".lstrip(".")
        self.emit("CreateSME", path, inserted=True, sme_type=el.type)
        new = self.I.children(target)[-1]
        for a in self.I.attributes(r):
            name, value = self.I.A[a].name, self.I.A[a].value
            if self.I.attr(new, name) is None:
                self.emit("CreateAttr", self.I.path(new), inserted=True, attribute_key=name)
            self.emit("UpdateAttr", self.I.path(new), inserted=True, attribute_key=name, attribute_value=value)
        for c in self.I.children(r):
            self._move(c, new)
        self.emit("RemoveSME", self.I.path(r), inserted=True)
        # the copy takes the place of the original in all bookkeeping
        for rs in self.R.values():
            rs[:] = [new if x == r else x for x in rs]
        self.key[new] = self.key.get(r, r)
        for s in (self.named, self.wild):
            if r in s:
                s.add(new)
        if r in self.desired:
            self.desired[new] = self.desired.pop(r)
        if el.id_short != self.I.E[new].id_short and self.I.E[target].type != "SubmodelElementList":  # N2
            self.desired.setdefault(new, el.id_short)
        self._restore_name(new)
        return new

    def _counterpart(self, t: Id, r: Id) -> Id | None:
        """The realisation the chain created in place of realisation r of template element t: one of
        an element whose origin is t, created for r (H2)."""
        anchor = self.key.get(r, r)
        return next((n for e, rs in self.R.items() if self.origin.get(e) == t
                     for n in rs if n in self.I.E and self.key.get(n) == anchor), None)

    def _RemoveSME(self, op: ops.RemoveSME, item: Item) -> None:
        for r in reversed(self.realisations(op.e, "RemoveSME")):
            if self.I.children(r) and (new := self._counterpart(op.e, r)) is not None:  # H2
                for c in list(self.I.children(r)):
                    self.note("inserted", f"UpdateParent {self.I.path(c)}: content the template does not "
                                          f"describe moves with its container")
                    self._move(c, new)
            where = self.I0.path(r) if r in self.I0.E else self.I.path(r)
            for key in sorted(instance_data(self.I.E[r].type)):  # V1
                a = self.I.attr(r, key)
                if a is not None and self.I.A[a].value not in (LAMBDA, "", []) and a not in self.transferred:
                    value = self.I.A[a].value
                    self.note("removed", f"{value}" if key == "value" else f"{key}: {value}", where)
            self.emit("RemoveSME", self.I.path(r))

    def _Sync(self, op: ops.Sync, item: Item) -> None:
        refs = [split_attribute_ref(r) for r in item.source_paths + item.target_paths]
        owners = [self.T.A[a].owner for a in op.src + op.tgt]
        rs = [self.realisations(o, "Sync") for o in owners]
        if not all(rs[:len(op.src)]):
            self.note("elided", f"Sync {item.source_paths}: source not realised, nothing to transfer")
            return
        if len({len(x) for x in rs}) != 1:
            raise Refused(f"ARITY_MISMATCH: {item}")
        n = len(item.source_paths)
        for column in zip(*rs):
            paths = [f"{self.I.path(r)}#{key}" for r, (_, _, key) in zip(column, refs)]
            if any(self.I.attr(r, key) is None for r, (_, _, key) in zip(column, refs)):
                self.note("elided", f"Sync {paths}: attribute not present in the instance")
                continue
            if not op.f.executable:  # with the source values, so that the maintainer can carry them over
                values = [self.I.A[self.I.attr(r, key)].value for r, (_, _, key) in zip(column[:n], refs)]
                text = op.f.text.get("en") if op.f.text else f"{op.f.kind} {getattr(op.f, 'expression', '')}"
                self.note("manual", f"{text} Current value: {values[0] if len(values) == 1 else values}",
                          self.final.path(self.T.A[op.tgt[0]].owner))
            before = [self.I.A[self.I.attr(r, key)].value for r, (_, _, key) in zip(column[:n], refs)]
            self.emit("Sync", "", source_paths=paths[:n], target_paths=paths[n:], transfer=op.f)
            if op.f.executable:
                self.transferred |= {self.I.attr(r, key) for r, (_, _, key) in zip(column[:n], refs)}
                after = [self.I.A[self.I.attr(r, key)].value for r, (_, _, key) in zip(column[n:], refs[n:])]
                for r, value in zip(column[:n], before):
                    where = self.I0.path(r) if r in self.I0.E else self.I.path(r)
                    if value not in (LAMBDA, None, "", []) and value != after:
                        self.note("transferred", f"{value} -> {after[0] if len(after) == 1 else after}", where)

    def finish(self) -> None:
        for r in list(self.desired):
            if r in self.I.E:
                self._restore_name(r)
        for r, want in self.desired.items():
            if r in self.I.E:
                self.note("manual", f"{self.I.path(r)}: could not be renamed back to {want}")


def resolve(items: list[Item], pre: Template, instance: Template) -> Resolution:
    """Rewrite a chain written against the template `pre` into a concrete chain for `instance`.
    Nothing is applied: the instance passed in is not changed."""
    r = _Resolver(items, pre, instance)
    try:
        for r.index, item in enumerate(items, start=1):
            r.item(item)
        r.index = 0
        r.finish()
    except Refused as refusal:
        r.note("refused", str(refusal))
        return Resolution(REJ, r.out, r.notes, f"item {r.index}: {refusal}")
    return Resolution(ACC, r.out, r.notes)
