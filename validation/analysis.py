"""Analysis of a chain against the published templates  (paper §5.2, Table 5): V1, V2, V8.

Pass criteria (Table 4):
  - the composed chain reproduces the target template at every position;
  - the result is accepted by aas-core and has exactly the metamodel violations of the published
    target template (the published templates are not free of violations themselves, paper §2.2, §5.2);
  - relocations (UpdateParent) and value links (Sync) are stated by the owner, never generated;
  - differences between the published versions that the change log does not state are enumerated
    (UNDOCUMENTED, as in Table 5 of the paper, derived by hand from the published templates and the
    change log), and the chain states each of them.

GENERATED_OVERWRITES is a separate, mechanical check: the generated items that overwrite an existing
populated value of a constraint or an idShort. It is narrower than UNDOCUMENTED and not equivalent
to it: an undocumented difference the owner states by hand (V1: ManufacturerLogo -> CompanyLogo) is
not a generated item, a documented one may still surface as an overwrite (V2: OrderCodeOfManufacturer,
whose cardinality the owner links by Sync and the completion then corrects), and a difference that
creates or removes an element instead of overwriting a value does not surface at all.

UNDOCUMENTED entries: (section of the chain that states the difference, identified by its group
"G1", or "generated"; the difference as a single change, where it is one). A change is
(element path[@qualifier type], "idShort" or attribute key, new value), with the paths of the item.
"""

from collections import Counter

from tcn import chainfile
from tcn.aas import bridge
from tcn.core.guarded import apply_chain, guarded
from tcn.core.model import LAMBDA
from tcn.roles import template_owner

Change = tuple[str, str, str]


def causes(submodel) -> Counter:
    # Sibling order is not a position of T, so violations are compared by cause, not by index path.
    return Counter(v.split(": ", 1)[1] for v in bridge.verify(submodel))


def check_chain_reproduces_target_template(chain_path: str) -> None:
    v = template_owner.verify(chainfile.load(chain_path))
    assert v.result.status == "ACC", v.result.reason
    assert not v.missing and not v.surplus


def check_result_is_metamodel_conformant_as_published(chain_path: str) -> None:
    chain = chainfile.load(chain_path)
    result = template_owner.verify(chain).result.template
    published = bridge.load_submodel(chain.header["PostTemplate"])
    assert causes(bridge.to_jsonable(result)) == causes(published)


def check_relocations_and_links_are_stated_by_hand(chain_path: str) -> None:
    chain = chainfile.load(chain_path)
    generated = [i for s in chain.sections if s.origin == "generated" for i in s.items]
    assert not any(i.operation in ("UpdateParent", "Sync") for i in generated)


def _change(item):
    if item.operation == "UpdateIdShort":
        return (item.element_path, "idShort", item.new_id_short)
    if item.operation == "UpdateAttr" and isinstance(item.attribute_value, str):
        path = f"{item.element_path}@{item.qualifier_type}" if item.qualifier_type else item.element_path
        return (path, item.attribute_key, item.attribute_value)
    return None


def check_undocumented_differences_are_enumerated(
        chain_path: str, undocumented: list[tuple[str, Change | None]], generated_overwrites: set[Change]) -> None:
    chain = chainfile.load(chain_path)

    # every difference not stated in the change log is stated in the chain
    for group, change in undocumented:
        if group == "generated":
            stating = [s for s in chain.sections if s.origin == "generated"]
        else:
            stating = [s for s in chain.sections if s.title.startswith(f"{group}:")]
        assert stating, group
        if change is not None:
            assert change in {_change(i) for s in stating for i in s.items}, change

    # mechanical cross-check: generated items that overwrite a populated value
    pre, _ = template_owner.load_templates(chain)
    stated = [i for s in chain.sections if s.origin != "generated" for i in s.items]
    T = apply_chain(stated, pre).template
    found = set()
    for item in (i for s in chain.sections if s.origin == "generated" for i in s.items):
        op = item.bind(T)
        if item.operation == "UpdateIdShort" and T.E[op.e].id_short != op.s:
            found.add((item.element_path, "idShort", op.s))
        if item.operation == "UpdateAttr" and T.A[op.a].owner in T.Q and T.A[op.a].value is not LAMBDA:
            found.add((f"{item.element_path}@{item.qualifier_type}", item.attribute_key, op.v))
        T, _ = guarded(op, T)
    assert found == generated_overwrites
