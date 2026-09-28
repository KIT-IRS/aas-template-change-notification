"""Role of the template owner  (paper §4.1, Fig. 4 left).

    complete  hand-written intent chain  ->  full chain from v_i to v_i+1
    verify    the chain transforms v_i into v_i+1 at every position (validation case V1/V2)
    publish   the verified chain as a TCN record on the topic of the template family

Completion only adds what the owner did not state: rules the owner declared are expanded, and
the remaining attribute-level differences are closed mechanically. Every emitted item is applied
by guarded application at once, so the completion can only emit admissible items.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from tcn import dropins
from tcn.aas import bridge, tcn_submodel
from tcn.chainfile import Chain, Section
from tcn.core.addressing import Item, element
from tcn.core.guarded import ACC, ChainResult, apply_chain, guarded
from tcn.core.model import LAMBDA, Id, Template, canonical
from tcn.core.transfer import Identity
from tcn.infra import broker


def load_templates(chain: Chain) -> tuple[Template, Template]:
    """The effective templates before and after the change, with the content of their drop-ins."""
    return (bridge.from_jsonable(dropins.load(chain.header["PreTemplate"])),
            bridge.from_jsonable(dropins.load(chain.header["PostTemplate"])))


# --- verify -------------------------------------------------------------------------------


@dataclass
class Verification:
    result: ChainResult
    missing: set[str]  # facts of v_i+1 the chain does not produce
    surplus: set[str]  # facts the chain produces that v_i+1 does not have

    @property
    def ok(self) -> bool:
        return self.result.status == ACC and not self.missing and not self.surplus


def verify(chain: Chain) -> Verification:
    pre, post = load_templates(chain)
    result = apply_chain(chain.items, pre)
    got, want = canonical(result.template), canonical(post)
    return Verification(result, want - got, got - want)


# --- complete -----------------------------------------------------------------------------


class _Emitter:
    """Collects items and applies each one to the working state immediately."""

    def __init__(self, state: Template):
        self.state, self.items = state, []

    def __call__(self, operation: str, path: str = "", **kw) -> None:
        item = Item(operation, path, **kw)
        self.state, outcome = guarded(item.bind(self.state), self.state)
        assert outcome.status == ACC, f"completion emitted an inadmissible item {item}: {outcome.reason}"
        self.items.append(item)


def complete(intent: Chain) -> Chain:
    pre, post = load_templates(intent)
    state, sections = pre, []
    for section in intent.sections:
        if section.origin == "rule":
            emit = _Emitter(state)
            for name, argument in section.rule.items():
                RULES[name](emit, post, argument)
            section = Section(section.title, "rule", emit.items, section.rule)
        result = apply_chain(section.items, state)
        assert result.status == ACC, f"section '{section.title}' is rejected: {result.reason}"
        state = result.template
        sections.append(section)

    emit = _Emitter(state)
    for title, step in [("Completion: removed elements and qualifiers", _remove_surplus),
                        ("Completion: created elements and qualifiers", _create_missing),
                        ("Completion: attributes", _align_attributes)]:
        emit.items = []
        step(emit, post)
        sections.append(Section(title, "generated", emit.items))
    return Chain(intent.header, sections)


def _qualifier_key(T: Template, q: Id) -> tuple[str, str]:
    return T.path(T.Q[q].elem), T.Q[q].qtype


def _element_keys(T: Template) -> dict[tuple[str, str], Id]:
    return {(T.path(e), T.E[e].type): e for e in T.E}


# --- rules: declared by the owner, expanded mechanically in place -------------------------


def _rename_qualifier_types(emit: _Emitter, post: Template, renames: dict[str, str]) -> None:
    """For every element carrying qualifier type `old` that has a `new` counterpart in v_i+1:
    CreateQual + UpdateAttr(valueType) + CreateAttr(value) + Sync(Identity) + RemoveQual."""
    targets = {_qualifier_key(post, q) for q in post.Q}
    for old, new in renames.items():
        for q in [q for q in emit.state.Q if emit.state.Q[q].qtype == old]:
            path, _ = _qualifier_key(emit.state, q)
            if (path, new) not in targets:
                continue  # no counterpart: removed by the completion
            value_type = emit.state.A[emit.state.attr(q, "valueType")].value
            emit("CreateQual", path, qualifier_type=new)
            emit("UpdateAttr", path, qualifier_type=new, attribute_key="valueType", attribute_value=value_type)
            emit("CreateAttr", path, qualifier_type=new, attribute_key="value")
            emit("Sync", source_paths=[f"{path}@{old}#value"], target_paths=[f"{path}@{new}#value"],
                 transfer=Identity())
            emit("RemoveQual", path, qualifier_type=old)


def _remove(emit: _Emitter, elements: list[Id]) -> None:
    """RemoveQual for all qualifiers, then RemoveSME deepest first."""
    for q in [q for q in emit.state.Q if emit.state.Q[q].elem in elements]:
        path, qtype = _qualifier_key(emit.state, q)
        emit("RemoveQual", path, qualifier_type=qtype)
    # deepest first; the path is taken at emission time, so shifted list positions are respected
    for e in sorted(elements, key=lambda e: -len(emit.state.path(e))):
        emit("RemoveSME", emit.state.path(e))


def _remove_subtrees(emit: _Emitter, post: Template, paths: list[str]) -> None:
    for p in paths:
        e = element(emit.state, p)
        _remove(emit, [e, *emit.state.desc(e)])


def _remove_children(emit: _Emitter, post: Template, paths: list[str]) -> None:
    for p in paths:
        _remove(emit, list(emit.state.desc(element(emit.state, p))))


def _rename_containers(emit: _Emitter, post: Template, renames: dict[str, str]) -> None:
    """Rename elements. A container is renamed only without children, so a container with children
    is rebuilt under its new name (Hollow-Out): created beside the original with its attributes,
    its qualifiers relocated (value linked by Sync), its children moved into it, recursively for
    nested containers, which take their own new name if they are renamed too; then the emptied
    original is removed. Elements keep their identity; only containers are recreated."""
    names = {element(emit.state, p): n for p, n in renames.items()}

    def ancestors(e: Id) -> set[Id]:
        p = emit.state.E[e].parent
        return set() if p is None else {p} | ancestors(p)

    # an element below another renamed container is renamed while that container is rebuilt
    outermost = [e for e in names if not ancestors(e) & names.keys()]
    for e in outermost:
        name = names[e]
        if emit.state.children(e):
            _rebuild(emit, e, emit.state.E[e].parent, names)
        else:
            emit("UpdateIdShort", emit.state.path(e), new_id_short=name)


def _rebuild(emit: _Emitter, e: Id, parent: Id, names: dict[Id, str]) -> Id:
    T = emit.state
    el = T.E[e]
    name = names.get(e, el.id_short)
    if T.E[parent].type == "SubmodelElementList":
        path = f"{T.path(parent)}[{len(T.children(parent))}]"
    else:
        path = f"{T.path(parent)}.{name}".lstrip(".")
    emit("CreateSME", path, sme_type=el.type)
    new = emit.state.children(parent)[-1]
    for a in list(emit.state.attributes(e)):
        _copy_attribute(emit, emit.state.A[a].name, emit.state.A[a].value, new, None)
    for q in list(emit.state.qualifiers(e)):
        qtype, old = emit.state.Q[q].qtype, emit.state.path(e)
        emit("CreateQual", emit.state.path(new), qualifier_type=qtype)
        for a in list(emit.state.attributes(q)):
            if emit.state.A[a].name != "value":
                _copy_attribute(emit, emit.state.A[a].name, emit.state.A[a].value, new, qtype)
        if emit.state.attr(q, "value") is not None:
            emit("CreateAttr", emit.state.path(new), qualifier_type=qtype, attribute_key="value")
            emit("Sync", source_paths=[f"{old}@{qtype}#value"],
                 target_paths=[f"{emit.state.path(new)}@{qtype}#value"], transfer=Identity())
        emit("RemoveQual", old, qualifier_type=qtype)
    for c in list(emit.state.children(e)):
        if emit.state.children(c):
            _rebuild(emit, c, new, names)
        else:
            emit("UpdateParent", emit.state.path(c), new_parent_path=emit.state.path(new))
            if c in names:
                emit("UpdateIdShort", emit.state.path(c), new_id_short=names[c])
    emit("RemoveSME", emit.state.path(e))
    return new


def _copy_attribute(emit: _Emitter, name: str, value, element_: Id, qtype: str | None) -> None:
    """Copy an attribute value onto element_, or onto its qualifier of type qtype."""
    T = emit.state
    x = element_ if qtype is None else next(q for q in T.qualifiers(element_) if T.Q[q].qtype == qtype)
    if T.attr(x, name) is None:
        emit("CreateAttr", T.path(element_), qualifier_type=qtype, attribute_key=name)
    if value is not LAMBDA:
        emit("UpdateAttr", emit.state.path(element_), qualifier_type=qtype, attribute_key=name, attribute_value=value)


RULES = {
    "QualifierTypeRenames": _rename_qualifier_types,
    "RemoveSubtree": _remove_subtrees,
    "RemoveChildren": _remove_children,
    "RenameContainer": _rename_containers,
}


# --- completion ---------------------------------------------------------------------------


def _remove_surplus(emit: _Emitter, post: Template) -> None:
    T, want = emit.state, _element_keys(post)
    wanted_quals = {_qualifier_key(post, q) for q in post.Q}
    doomed = [e for k, e in _element_keys(T).items() if k not in want]
    for q in [q for q in T.Q if T.Q[q].elem not in doomed and _qualifier_key(T, q) not in wanted_quals]:
        path, qtype = _qualifier_key(emit.state, q)
        emit("RemoveQual", path, qualifier_type=qtype)
    _remove(emit, doomed)


def _create_missing(emit: _Emitter, post: Template) -> None:
    for e in post.E:  # document order: parents before children, list entries in order
        key = (post.path(e), post.E[e].type)
        have = _element_keys(emit.state)
        if key not in have:
            emit("CreateSME", key[0], sme_type=key[1])
        elif (s := post.E[e].id_short) is not None and emit.state.E[have[key]].id_short != s:
            emit("UpdateIdShort", key[0], new_id_short=s)  # the root: its idShort is not in its path
    have = {_qualifier_key(emit.state, q) for q in emit.state.Q}
    for q in post.Q:
        path, qtype = _qualifier_key(post, q)
        if (path, qtype) not in have:
            emit("CreateQual", path, qualifier_type=qtype)


def _align_attributes(emit: _Emitter, post: Template) -> None:
    def owners(T: Template) -> dict[tuple[str, str | None], Id]:
        o = {(T.path(e), None): e for e in T.E}
        return o | {_qualifier_key(T, q): q for q in T.Q}

    target_owners = owners(post)
    for (path, qtype), x in owners(emit.state).items():
        want = {post.A[a].name: post.A[a].value for a in post.attributes(target_owners[(path, qtype)])}
        have = {emit.state.A[a].name: emit.state.A[a].value for a in emit.state.attributes(x)}
        for name in sorted(have.keys() - want.keys()):
            emit("RemoveAttr", path, qualifier_type=qtype, attribute_key=name)
        for name, value in want.items():
            if name not in have:
                emit("CreateAttr", path, qualifier_type=qtype, attribute_key=name)
            if have.get(name, LAMBDA) != value:
                emit("UpdateAttr", path, qualifier_type=qtype, attribute_key=name, attribute_value=value)


# --- publish ------------------------------------------------------------------------------


def publish(chain: Chain) -> str:
    """Verify the chain, assemble it into a TCN record and publish it on the family topic."""
    v = verify(chain)
    if not v.ok:
        raise ValueError(f"chain does not transform v_i into v_i+1: {v.result.reason or 'positions differ'}")
    notification_id = f"urn:uuid:{uuid.uuid4()}"
    date = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    broker.publish(chain.header["Family"], {"Record": tcn_submodel.record(chain, notification_id, date)})
    return notification_id
