"""V10 for Asset Interfaces Description v1.0 -> v1.1 -> v1.2 (not part of the paper): retention of
instance values.

Requirements R2, R4. Method: demonstration, offline; pass criterion as V10
(test_v10_idta_templates_retention.py), with the expectations in fixtures/expected/<transition>.yaml.
The templates are large, and the checks run for several minutes; they are marked slow and run only
with --run-slow.

v1.2 declares every protocol binding (MODBUS, OPC UA, BACnet, IO-Link, SNMP, CAN, ...) OneToMany, whereas
its specification declares one Interface{00} with 1..*. An instance without one of these interfaces
holds no realisation of an element that is mandatory as last stated (rule E2 of
tcn.core.resolution): the resolution refuses the chain (SEMANTIC_MATCH_NONE). The checks of
aid_1.1_to_1.2 are marked as expected failures (XFAIL).
"""

import pytest

from validation import application

pytestmark = pytest.mark.slow

MANDATORY_BINDINGS = ("the template declares every protocol binding mandatory: the resolution refuses an "
                      "instance without one of them (SEMANTIC_MATCH_NONE)")
TRANSITIONS = pytest.mark.parametrize("transition", [
    "aid_1.0_to_1.1",
    pytest.param("aid_1.1_to_1.2", marks=pytest.mark.xfail(reason=MANDATORY_BINDINGS, strict=True)),
])


def _expected(transition: str) -> str:
    return f"fixtures/expected/{transition}.yaml"


@TRANSITIONS
def test_chain_applies_and_retains_instance_data(transition):
    application.check_chain_applies_and_retains_instance_data(_expected(transition))


@TRANSITIONS
def test_manual_steps_are_reported(transition):
    application.check_manual_steps_are_reported(_expected(transition))


@TRANSITIONS
def test_result_is_serialisable_without_new_violations(transition):
    application.check_result_is_serialisable_without_new_violations(_expected(transition))


@TRANSITIONS
def test_conformance_to_the_new_template(transition):
    application.check_conformance_to_the_new_template(_expected(transition))


@TRANSITIONS
def test_no_value_is_lost_silently(transition):
    application.check_no_value_is_lost_silently(_expected(transition))
