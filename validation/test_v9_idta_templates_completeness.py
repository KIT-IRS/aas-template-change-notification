"""V9: further IDTA Submodel Templates (not part of the paper): completeness of the change description.

Requirements R1, R2. Method: analysis, as V1 and V2 (paper §5.2, Table 4); the checks are described
in validation/analysis.py.
Pass criterion: as V1, for every transition: the chain, applied to v_i, reproduces every fact of
v_i+1 and no further fact and introduces no metamodel violation, and the differences between the
templates that the change log does not state are enumerated.

The transitions are the published revisions of a major or minor version of every IDTA Submodel
Template of admin-shell-io/submodel-templates other than those of the paper (Technical Data v1.2 ->
v2.0, Digital Nameplate, TCN Submodel Template), together with ZVEI Technical Data v1.1 -> IDTA v1.2.
The transitions of Asset Interfaces Description run for several minutes and are checked separately
in test_v9_aid_completeness.py (only with --run-slow).
Where a version has bug-fix releases, the latest one is taken. The bug-fix releases (v2.1 of AIMC,
v1.1 of Energy Flexibility, Plant Planning, Plastic Waste, OPC UA Server Datasheet, Product Change
Notifications, Production Calendar, Quality Control, v1.2 of Simulation Models) name as their change
log a list of issues, which concern attribute values only (language strings, blanks in references,
the kind of qualifiers): that the entries of lists no longer carry an idShort (F1) is not stated in
it. Transitions without a published change log list no undocumented differences.
"""

import pytest

from validation import analysis

CHAINS = {
    "aimc_1.0_to_2.0": "chains/aimc_1.0_to_2.0.yaml",
    "aimc_2.0_to_2.1": "chains/aimc_2.0_to_2.1.yaml",
    "carbonfootprint_0.9_to_1.0": "chains/carbonfootprint_0.9_to_1.0.yaml",
    "ccinstance_1.0_to_2.0": "chains/ccinstance_1.0_to_2.0.yaml",
    "cctype_1.0_to_2.0": "chains/cctype_1.0_to_2.0.yaml",
    "energyflexibility_1.0_to_1.1": "chains/energyflexibility_1.0_to_1.1.yaml",
    "handover_1.2_to_2.0": "chains/handover_1.2_to_2.0.yaml",
    "opcuaserver_1.0_to_1.1": "chains/opcuaserver_1.0_to_1.1.yaml",
    "pcn_1.0_to_1.1": "chains/pcn_1.0_to_1.1.yaml",
    "plantplanning_1.0_to_1.1": "chains/plantplanning_1.0_to_1.1.yaml",
    "plasticwaste_1.0_to_1.1": "chains/plasticwaste_1.0_to_1.1.yaml",
    "productioncalendar_1.0_to_1.1": "chains/productioncalendar_1.0_to_1.1.yaml",
    "qualitycontrol_1.0_to_1.1": "chains/qualitycontrol_1.0_to_1.1.yaml",
    "simulationmodels_1.0_to_1.1": "chains/simulationmodels_1.0_to_1.1.yaml",
    "simulationmodels_1.1_to_1.2": "chains/simulationmodels_1.1_to_1.2.yaml",
    "technicaldata_1.1_to_1.2": "chains/technicaldata_1.1_to_1.2.yaml",
}
F1 = [("F1", None)]  # the entries of lists no longer carry an idShort; not in the issues of the release
UNDOCUMENTED = {
    "aimc_1.0_to_2.0": [("A0", None)],  # the entries of MappingConfigurations, Sources and Sinks are named
    "aimc_2.0_to_2.1": F1,
    "carbonfootprint_0.9_to_1.0": [],  # no change log published
    "ccinstance_1.0_to_2.0": [("C6", ("Skills.Skill.Modes.Mode", "idShort", "Mode__00__")), ("C7", None)],
    "cctype_1.0_to_2.0": [("C6", ("Skills.Skill.Modes.Mode", "idShort", "Mode__00__")), ("C7", None)],
    "energyflexibility_1.0_to_1.1": F1,
    "handover_1.2_to_2.0": [
        ("generated", ("", "idShort", "HandoverDocumentation")),
        ("generated", None),  # numberOfDocuments is removed
        ("H4", ("Document__00__.DocumentId__00__.IsPrimary", "idShort", "DocumentIsPrimary")),
        ("H6", ("Document__00__.DocumentVersion__00__.SubTitle", "idShort", "Subtitle")),
        ("H6", ("Document__00__.DocumentVersion__00__.OrganizationName", "idShort", "OrganizationShortName")),
        ("H15", None),  # qualifier type Cardinality -> SMT/Cardinality
    ],
    "opcuaserver_1.0_to_1.1": F1,
    "pcn_1.0_to_1.1": F1,
    "plantplanning_1.0_to_1.1": F1,
    "plasticwaste_1.0_to_1.1": F1,
    "productioncalendar_1.0_to_1.1": [],
    "qualitycontrol_1.0_to_1.1": F1,
    # the corrected semanticIds of PortConDescription and SimToolName; the change log misstates the new
    # semanticId of the submodel
    "simulationmodels_1.0_to_1.1": [("generated", None)],
    "simulationmodels_1.1_to_1.2": [],
    "technicaldata_1.1_to_1.2": [],  # no change log published
}
GENERATED_OVERWRITES = {
    "aimc_1.0_to_2.0": {
        ("MappingConfigurations@SMT/Cardinality", "kind", "TemplateQualifier"),
        # the repeatability of a relation constrains its source and sink entries, as published
        ("MappingConfigurations[0].Sinks[0]@SMT/Cardinality", "value", "OneToMany"),
        ("MappingConfigurations[0].Sources[0]@SMT/Cardinality", "value", "OneToMany"),
    },
    "aimc_2.0_to_2.1": set(),
    "carbonfootprint_0.9_to_1.0": set(),
    "ccinstance_1.0_to_2.0": {
        ("Skills.Skill.Parameters.Parameter@PresetIdShort", "kind", "TemplateQualifier"),
        ("Skills.Skill@PresetIdShort", "kind", "TemplateQualifier"),
    },
    "cctype_1.0_to_2.0": {
        ("Skills.Skill.Parameters.Parameter@PresetIdShort", "kind", "TemplateQualifier"),
        ("Skills.Skill@PresetIdShort", "kind", "TemplateQualifier"),
    },
    "energyflexibility_1.0_to_1.1": set(),
    "handover_1.2_to_2.0": {
        ("", "idShort", "HandoverDocumentation"),
        ("Documents[0].DocumentIds[0].DocumentDomainId@ExampleValue", "value", "https://domain.com/..."),
        ("Documents[0].DocumentVersions[0].KeyWords@SMT/Cardinality", "value", "ZeroToOne"),
    },
    "opcuaserver_1.0_to_1.1": set(),
    "pcn_1.0_to_1.1": set(),
    "plantplanning_1.0_to_1.1": set(),
    "plasticwaste_1.0_to_1.1": set(),
    "productioncalendar_1.0_to_1.1": set(),
    "qualitycontrol_1.0_to_1.1": set(),
    "simulationmodels_1.0_to_1.1": set(),
    "simulationmodels_1.1_to_1.2": {  # the kind of the qualifiers (#159)
        (f"SimulationModel.Quality{p}@Multiplicity", "kind", "TemplateQualifier")
        for p in ("", ".Architecture", ".EvaluationPerspective", ".QualityMetricFile", ".Usability", ".Validation")
    },
    "technicaldata_1.1_to_1.2": {  # cardinalities, relocated unchanged by T6 and then set as published
        ("FurtherInformation@Cardinality", "value", "ZeroToOne"),
        ("GeneralInformation.ManufacturerArticleNumber@Cardinality", "value", "One"),
        ("GeneralInformation.ManufacturerOrderCode@Cardinality", "value", "One"),
        ("ProductClassifications@Cardinality", "value", "ZeroToOne"),
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
