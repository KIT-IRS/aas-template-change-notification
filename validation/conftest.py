import pytest

# Failures inside the shared checks show the compared values, as in the test modules themselves.
pytest.register_assert_rewrite("validation.analysis", "validation.application", "validation.endtoend",
                               "validation.properties")

import requests  # noqa: E402

from tcn import environment  # noqa: E402
from tcn.infra.gateway import Gateway  # noqa: E402
from validation.report import pytest_addoption, pytest_configure  # noqa: E402,F401


@pytest.fixture
def gw():
    """The AAS environment with the AAS of the example device (end-to-end cases V3-V7)."""
    try:
        requests.get(Gateway().url + "/shells", timeout=2)
    except requests.ConnectionError:
        pytest.skip("AAS environment not running (docker compose up -d)")
    gateway = Gateway()
    environment.seed(gateway)
    yield gateway
    environment.reset(gateway)
