"""V10: further IDTA Submodel Templates (not part of the paper): retention of instance values.

Requirements R2, R4. Method: demonstration, offline, as V3 and V4 (paper §5.3, Table 4); the checks
are described in validation/application.py.
Pass criterion: as V3, for every transition of V9: instance values designated for retention keep
their values, the control set remains unchanged, and every deviation of the result from v_i+1 and
every removed value is reported before consent. The expectations, derived by hand from the change
logs and the published templates before the chains were run, are in fixtures/expected/<transition>.yaml.
The transitions of Asset Interfaces Description run for several minutes and are checked separately
in test_v10_aid_retention.py (only with --run-slow).

Unlike for V4 (paper §5.5), the further templates required changes to the implementation: template
siblings that share a semanticId are told apart by their supplementalSemanticIds or idShort
(tcn.core.matching, M1); content the template does not describe moves with a container the chain
rebuilds (tcn.core.resolution, H2), and a rebuilt container takes over the semanticId of the original
(tcn.roles.template_owner); entries of lists are addressed by their index (N2); instance data comprise
all attributes that hold the value of an element (T2, tcn.core.metamodel.instance_data); and Sync
requires a transfer function that is defined and yields admissible values (tcn.core.transfer,
tcn.core.operators). The cases of the paper are unchanged by them.

Two templates use a SubmodelElementList for entries that differ (several template entries of one type
and semanticId, distinguished by their example values or their children), which the metamodel does
not provide for: Production Calendar and Plant Planning. Their cases fail where the entries are matched
and are marked as expected failures (XFAIL).
"""

import pytest

from validation import application

TRANSITIONS = ["aimc_1.0_to_2.0", "aimc_2.0_to_2.1",
               "carbonfootprint_0.9_to_1.0", "ccinstance_1.0_to_2.0", "cctype_1.0_to_2.0",
               "energyflexibility_1.0_to_1.1", "handover_1.2_to_2.0", "opcuaserver_1.0_to_1.1", "pcn_1.0_to_1.1",
               "plantplanning_1.0_to_1.1", "plasticwaste_1.0_to_1.1", "productioncalendar_1.0_to_1.1",
               "qualitycontrol_1.0_to_1.1", "simulationmodels_1.0_to_1.1", "simulationmodels_1.1_to_1.2",
               "technicaldata_1.1_to_1.2"]

HETEROGENEOUS_LIST = ("the template distinguishes the entries of a list by their example values or children, "
                      "which the metamodel does not provide for: every entry realises the first template entry")
ALL = {"retains", "manual", "serialisable", "conformance", "lost"}
XFAIL = {
    "productioncalendar_1.0_to_1.1": {"conformance"},  # the instance with all three variables is not conformant
    "plantplanning_1.0_to_1.1": ALL,  # the resolution cannot assign the 21 entries
}


def _cases(check: str) -> list:
    return [pytest.param(t, marks=pytest.mark.xfail(reason=HETEROGENEOUS_LIST, strict=True))
            if check in XFAIL.get(t, ()) else t for t in TRANSITIONS]


def _expected(transition: str) -> str:
    return f"fixtures/expected/{transition}.yaml"


@pytest.mark.parametrize("transition", _cases("retains"))
def test_chain_applies_and_retains_instance_data(transition):
    application.check_chain_applies_and_retains_instance_data(_expected(transition))


@pytest.mark.parametrize("transition", _cases("manual"))
def test_manual_steps_are_reported(transition):
    application.check_manual_steps_are_reported(_expected(transition))


@pytest.mark.parametrize("transition", _cases("serialisable"))
def test_result_is_serialisable_without_new_violations(transition):
    application.check_result_is_serialisable_without_new_violations(_expected(transition))


@pytest.mark.parametrize("transition", _cases("conformance"))
def test_conformance_to_the_new_template(transition):
    application.check_conformance_to_the_new_template(_expected(transition))


@pytest.mark.parametrize("transition", _cases("lost"))
def test_no_value_is_lost_silently(transition):
    application.check_no_value_is_lost_silently(_expected(transition))

