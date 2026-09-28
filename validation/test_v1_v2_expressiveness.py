"""V1 (Technical Data v1.2 -> v2.0), V2 (Digital Nameplate v1.0 -> v2.0 -> v3.0) and V8 (the TCN
Submodel Template v0.3 -> v0.4 itself), method: analysis.

Pass criteria (Table 4):
  - the composed chain reproduces the target template at every position;
  - the result is accepted by aas-core and has exactly the metamodel violations of the published
    target template (the published templates are not free of violations themselves, paper §2.3);
  - relocations (UpdateParent) and value links (Sync) are stated by the owner, never generated;
  - differences the change log does not state are enumerated. They surface as generated items that
    overwrite an existing populated value of a constraint or an idShort. The expected sets below
    were derived by hand from the published templates and change logs.
"""

from collections import Counter

import pytest

from tcn import chainfile
from tcn.aas import bridge
from tcn.core.guarded import apply_chain, guarded
from tcn.core.model import LAMBDA
from tcn.roles import template_owner

UNDOCUMENTED = {
    "V1": set(),
    "V8": set(),
    "V2-1.0": {
        ("", "idShort", "DigitalNameplate"),  # reverted to "Nameplate" in v3.0
        ("ManufacturerProductFamily@Multiplicity", "value", "ZeroToOne"),
    },
    "V2": {
        ("", "idShort", "Nameplate"),
        ("OrderCodeOfManufacturer@SMT/Cardinality", "value", "One"),
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


@CASES
def test_undocumented_differences_are_enumerated(case):
    chain = chainfile.load(CHAINS[case])
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
    assert found == UNDOCUMENTED[case]
