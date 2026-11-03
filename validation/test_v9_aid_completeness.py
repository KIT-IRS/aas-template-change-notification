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

# v1.1 corrects spelling errors in the values of Constraint and Comment qualifiers; v1.2 reintroduces
# them (and misspells AcknowledgeAlarm), i.e. it is not derived from v1.1 (it also carries the id of v1.0).
_INTEGER, _INTERGER = "Only applicable for number-/integer-based values", "Only applicable for number-/interger-based values"
_RECURSIVE, _RECUSIVE = "Recursive definition of last propertyName SMC", "Recusive definition of last propertyName SMC"
_PROPERTY = "InteractionMetadata.properties.property_name"
_MIN_MAX = [f"{_PROPERTY}.{p}min_max" for p in ("", "items.", "properties.property_name.", "properties.property_name.items.")]
_NESTED = f"{_PROPERTY}.properties.property_name.properties"


def _spelling(interfaces, min_max, comment):
    return {(f"InterfaceTemplateFor{i}.{p}@Constraint", "value", min_max) for i in interfaces for p in _MIN_MAX} | \
        {(f"InterfaceTemplateFor{i}.{_NESTED}@Comment", "value", comment) for i in interfaces}


_BACNET_URI = "InterfaceTemplateForBacnet.InteractionMetadata.properties.property_name.uriVariables.property_name"
GENERATED_OVERWRITES = {
    "aid_1.0_to_1.1": _spelling(("HTTP", "MODBUS", "MQTT"), _INTEGER, _RECURSIVE),
    "aid_1.1_to_1.2": _spelling(("HTTP", "MODBUS", "MQTT", "OPCUA", "Bacnet", "IOLINK_OVER_PROFINET_REST"),
                                _INTERGER, _RECUSIVE) | {
        (f"{_BACNET_URI}.min_max@Constraint", "value", _INTERGER),
        (f"{_BACNET_URI}.items.min_max@Constraint", "value", _INTERGER),
        (f"{_BACNET_URI}.properties@Comment", "value", _RECUSIVE),
        ("InterfaceTemplateForBacnet.InteractionMetadata.properties.property_name.forms.bacv_useService@Enumeration",
         "value", "ReadProperty, WriteProperty, SubscribeCOV, GetEventInfo, AcknowlegeAlarm, AddListElement,"
                  "RemoveListElement"),
    },
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
    analysis.check_undocumented_differences_are_enumerated(
        CHAINS[transition], UNDOCUMENTED[transition], GENERATED_OVERWRITES[transition])
