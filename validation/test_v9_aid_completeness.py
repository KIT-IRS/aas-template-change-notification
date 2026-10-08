"""V9 for Asset Interfaces Description v1.0 -> v1.1 -> v1.2 (not part of the paper): completeness of
the change description.

Requirements R1, R2. Method: analysis; pass criterion as V9 (test_v9_idta_templates_completeness.py).
The templates are large, and the checks run for several minutes; they are marked slow and run only
with --run-slow.
"""

import pytest

from validation import analysis

pytestmark = pytest.mark.slow

CHAINS = {
    "aid_1.0_to_1.1": "chains/aid_1.0_to_1.1.yaml",
    "aid_1.1_to_1.2": "chains/aid_1.1_to_1.2.yaml",
}
UNDOCUMENTED = {
    "aid_1.0_to_1.1": [
        ("D1", None), ("D2", None), ("D4", None),  # named entries of lists
        ("generated", None),  # MODBUS keeps only nosec_sc; the semanticIds of base and support
    ],
    "aid_1.1_to_1.2": [
        # listed as new
        ("D3", ("InterfaceTemplateForIOLINK_OVER_PROFINET_REST.InteractionMetadata.properties.property_name.forms."
                "iolv_accessRigths", "idShort", "iolv_accessRights")),
        ("generated", None),  # the lists enum and the nested observable are removed
    ],
}
TRANSITIONS = pytest.mark.parametrize("transition", CHAINS)


@TRANSITIONS
def test_chain_reproduces_target_template(transition):
    analysis.check_chain_reproduces_target_template(CHAINS[transition])


@TRANSITIONS
def test_result_is_metamodel_conformant_as_published(transition):
    analysis.check_result_is_metamodel_conformant_as_published(CHAINS[transition])


@TRANSITIONS
def test_relocations_and_links_are_stated_by_hand(transition):
    analysis.check_relocations_and_links_are_stated_by_hand(CHAINS[transition])


@TRANSITIONS
def test_undocumented_differences_are_enumerated(transition):
    analysis.check_undocumented_differences_are_enumerated(CHAINS[transition], UNDOCUMENTED[transition], set())
