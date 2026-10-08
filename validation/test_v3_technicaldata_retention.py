"""V3: Technical Data v1.2 -> v2.0, end to end  (paper §5.3, Table 4, Table 6).

Requirements R2, R4. Method: demonstration.
Pass criterion: instance values designated for retention keep their values, the control set remains
unchanged, and every deviation of the result from v2.0 and every removed value is reported before
consent. The expectations are in fixtures/expected/technicaldata_1.2_to_2.0.yaml.

The offline tests run resolution and guarded application directly (validation/application.py); the
end-to-end test runs the same record over BaSyx and MQTT (validation/endtoend.py, -m infra).
"""

import pytest

from validation import application, endtoend

EXPECTED = "fixtures/expected/technicaldata_1.2_to_2.0.yaml"


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


def test_baseline_is_not_changed():
    application.check_baseline_is_not_changed(EXPECTED)


@pytest.mark.infra
def test_end_to_end(gw):
    endtoend.check_end_to_end(gw, EXPECTED)
