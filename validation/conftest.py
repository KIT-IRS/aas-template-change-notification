import pytest
import requests

from tcn import environment
from tcn.infra.gateway import Gateway


def pytest_addoption(parser):
    parser.addoption("--run-slow", action="store_true", help="also run the tests marked slow")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip = pytest.mark.skip(reason="runs for several minutes; use --run-slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


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
