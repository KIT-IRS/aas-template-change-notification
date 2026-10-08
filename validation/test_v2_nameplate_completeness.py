"""V2: Digital Nameplate ZVEI 1.0 -> IDTA 2.0 -> IDTA 3.0  (paper §5.2, Table 4, Table 5).

Requirements R1, R2. Method: analysis.
Pass criterion: as V1, for both transitions. The checks are described in validation/analysis.py.
The transition ZVEI 1.0 -> IDTA 2.0 has no published change log, so no undocumented differences are
listed for it.
"""

import pytest

from validation import analysis

CHAINS = {"1.0_to_2.0": "chains/nameplate_1.0_to_2.0.yaml", "2.0_to_3.0": "chains/nameplate_2.0_to_3.0.yaml"}
UNDOCUMENTED = {
    "1.0_to_2.0": [],
    "2.0_to_3.0": [
        ("generated", ("", "idShort", "Nameplate")),
        ("B8", None),  # GuidelineSpecificProperties converted into a list
        ("generated", ("AssetSpecificProperties.ArbitraryProperty@SMT/Cardinality", "value", "ZeroToMany")),
        ("generated", ("AssetSpecificProperties.GuidelineSpecificProperties[0].ArbitraryProperty@SMT/Cardinality",
                       "value", "ZeroToMany")),
        ("B1", None),  # qualifier type Multiplicity -> SMT/Cardinality, listed only as part of the metamodel update
    ],
}
GENERATED_OVERWRITES = {
    "1.0_to_2.0": {
        ("", "idShort", "DigitalNameplate"),  # reverted to "Nameplate" in v3.0
        ("ManufacturerProductFamily@Multiplicity", "value", "ZeroToOne"),
    },
    "2.0_to_3.0": {
        ("", "idShort", "Nameplate"),
        ("OrderCodeOfManufacturer@SMT/Cardinality", "value", "One"),  # in the change log
        ("AssetSpecificProperties.ArbitraryProperty@SMT/Cardinality", "value", "ZeroToMany"),
        ("AssetSpecificProperties.GuidelineSpecificProperties[0].ArbitraryProperty@SMT/Cardinality", "value",
         "ZeroToMany"),
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
