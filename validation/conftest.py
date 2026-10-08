import pytest
import requests

from tcn import environment
from tcn.infra.gateway import Gateway


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
