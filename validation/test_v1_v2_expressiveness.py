"""V1 (Technical Data v1.2 -> v2.0), V2 (Digital Nameplate v1.0 -> v2.0 -> v3.0) and V8 (the TCN
Submodel Template v0.3 -> v0.4 itself), method: analysis.

Pass criteria (Table 4):
  - the composed chain reproduces the target template at every position;
  - the result is accepted by aas-core and has exactly the metamodel violations of the published
    target template (the published templates are not free of violations themselves, paper §2.3);
  - relocations (UpdateParent) and value links (Sync) are stated by the owner, never generated;
  - differences between the published versions that the change log does not state are enumerated
    (UNDOCUMENTED, as in Table 5 of the paper, derived by hand from the published templates and the
    change log), and the chain states each of them. V2-1.0 and V8 have no change log and are not
    listed.

The opposite case, a change the change log lists but the template does not carry out, cannot show in
a chain and is not checked: Technical Data v2.0 lists a rename of ClassificationSystemVersion, which
keeps its idShort in the published template (paper §6).

GENERATED_OVERWRITES is a separate, mechanical check: the generated items that overwrite an existing
populated value of a constraint or an idShort. It is narrower than UNDOCUMENTED and not equivalent
to it: an undocumented difference the owner states by hand (V1: ManufacturerLogo -> CompanyLogo) is
not a generated item, a documented one may still surface as an overwrite (V2: OrderCodeOfManufacturer,
whose cardinality the owner links by Sync and the completion then corrects), and a difference that
creates or removes an element instead of overwriting a value does not surface at all.
"""

from collections import Counter

import pytest

from tcn import chainfile
from tcn.aas import bridge
from tcn.core.guarded import apply_chain, guarded
from tcn.core.model import LAMBDA
from tcn.roles import template_owner

# Each entry: (section of the chain that states the difference, identified by its group "G1", or
# "generated"; the difference as a single change, where it is one). A change is
# (element path[@qualifier type], "idShort" or attribute key, new value), with the paths of the item.
UNDOCUMENTED: dict[str, list[tuple[str, tuple[str, str, str] | None]]] = {
    "V1": [
        ("G1", ("GeneralInformation.ManufacturerLogo", "idShort", "CompanyLogo")),
        ("G8", None),  # qualifier type Cardinality -> SMT/Cardinality, listed only as part of the schema update
    ],
    "V2": [
        ("generated", ("", "idShort", "Nameplate")),
        ("B8", None),  # GuidelineSpecificProperties converted into a list
        ("generated", ("AssetSpecificProperties.ArbitraryProperty@SMT/Cardinality", "value", "ZeroToMany")),
        ("generated", ("AssetSpecificProperties.GuidelineSpecificProperties[0].ArbitraryProperty@SMT/Cardinality",
                       "value", "ZeroToMany")),
        ("B1", None),  # qualifier type Multiplicity -> SMT/Cardinality, listed only as part of the metamodel update
    ],
}
GENERATED_OVERWRITES = {
    "V1": set(),
    "V8": set(),
    "V2-1.0": {
        ("", "idShort", "DigitalNameplate"),  # reverted to "Nameplate" in v3.0
        ("ManufacturerProductFamily@Multiplicity", "value", "ZeroToOne"),
    },
    "V2": {
        ("", "idShort", "Nameplate"),
        ("OrderCodeOfManufacturer@SMT/Cardinality", "value", "One"),  # in the change log
        ("AssetSpecificProperties.ArbitraryProperty@SMT/Cardinality", "value", "ZeroToMany"),
        ("AssetSpecificProperties.GuidelineSpecificProperties[0].ArbitraryProperty@SMT/Cardinality", "value",
         "ZeroToMany"),
    },
}
CHAINS = {"V1": "chains/technicaldata_1.2_to_2.0.yaml", "V2-1.0": "chains/nameplate_1.0_to_2.0.yaml",
          "V2": "chains/nameplate_2.0_to_3.0.yaml", "V8": "chains/tcn_0.3_to_0.4.yaml"}
CASES = pytest.mark.parametrize("case", CHAINS)


def _causes(submodel) -> Counter:
    # Sibling order is not a position of T, so violations are compared by cause, not by index path.
    return Counter(v.split(": ", 1)[1] for v in bridge.verify(submodel))


@CASES
def test_chain_reproduces_target_template(case):
    v = template_owner.verify(chainfile.load(CHAINS[case]))
    assert v.result.status == "ACC", v.result.reason
    assert not v.missing and not v.surplus


@CASES
def test_result_is_metamodel_conformant_as_published(case):
    chain = chainfile.load(CHAINS[case])
    result = template_owner.verify(chain).result.template
    published = bridge.load_submodel(chain.header["PostTemplate"])
    assert _causes(bridge.to_jsonable(result)) == _causes(published)


@CASES
def test_relocations_and_links_are_stated_by_hand(case):
    chain = chainfile.load(CHAINS[case])
    generated = [i for s in chain.sections if s.origin == "generated" for i in s.items]
    assert not any(i.operation in ("UpdateParent", "Sync") for i in generated)


def _change(item):
    if item.operation == "UpdateIdShort":
        return (item.element_path, "idShort", item.new_id_short)
    if item.operation == "UpdateAttr" and isinstance(item.attribute_value, str):
        path = f"{item.element_path}@{item.qualifier_type}" if item.qualifier_type else item.element_path
        return (path, item.attribute_key, item.attribute_value)
    return None


@CASES
def test_undocumented_differences_are_enumerated(case):
    chain = chainfile.load(CHAINS[case])

    # every difference not stated in the change log is stated in the chain
    for group, change in UNDOCUMENTED.get(case, []):
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
    assert found == GENERATED_OVERWRITES[case]
