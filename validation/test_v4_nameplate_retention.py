"""V4: Digital Nameplate IDTA 2.0 -> IDTA 3.0, end to end  (paper §5.3, §5.5, Table 4, Table 6).

Requirements R2, R4. Method: demonstration.
Pass criterion: as V3, without a change to the implementation compared to V3. The tests are those
of V3; only the expectations differ (fixtures/expected/nameplate_2.0_to_3.0.yaml).
"""

import pytest

from validation import application, endtoend

EXPECTED = "fixtures/expected/nameplate_2.0_to_3.0.yaml"


def test_chain_applies_and_retains_instance_data():
    application.check_chain_applies_and_retains_instance_data(EXPECTED)


def test_manual_steps_are_reported():
    application.check_manual_steps_are_reported(EXPECTED)


def test_result_is_serialisable_without_new_violations():
    application.check_result_is_serialisable_without_new_violations(EXPECTED)


def test_conformance_to_the_new_template():
    application.check_conformance_to_the_new_template(EXPECTED)


def test_no_value_is_lost_silently():
    application.check_no_value_is_lost_silently(EXPECTED)


@pytest.mark.infra
def test_end_to_end(gw):
    endtoend.check_end_to_end(gw, EXPECTED)
