"""The decomposition is lossless: SMT -> T -> SMT reproduces every template unchanged."""

from pathlib import Path

import pytest

from tcn.aas import bridge

TEMPLATES = sorted(Path("ressources/Templates").glob("*.json"))


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.name)
def test_round_trip(path):
    submodel = bridge.load_submodel(path)
    t = bridge.from_jsonable(submodel)
    assert bridge.to_jsonable(t) == submodel

