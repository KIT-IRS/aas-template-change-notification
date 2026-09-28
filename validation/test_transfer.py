"""Transfer functions of Sync (paper §3.2): execution of expressions without executing code."""

from tcn.core.model import LAMBDA
from tcn.core.transfer import CEL, MAX_EXPRESSION_LENGTH, Expression, Identity, ValueMap

MLP = [{"language": "de", "text": "Kompakt"}, {"language": "en", "text": "Compact"}]
EN_OR_FIRST = "src[0].exists(s, s.language == 'en') ? src[0].filter(s, s.language == 'en')[0].text : src[0][0].text"


def test_identity_and_value_map():
    assert Identity()(["a", LAMBDA]) == ["a", LAMBDA]
    f = ValueMap({"One": "ZeroToOne"})
    assert f.defined(["One", LAMBDA]) and f(["One"]) == ["ZeroToOne"]
    assert not f.defined(["ZeroToMany"])  # f must be total on the source values


def test_cel_transforms_values():
    assert Expression(CEL, EN_OR_FIRST)([MLP]) == ["Compact"]
    assert Expression(CEL, EN_OR_FIRST)([MLP[:1]]) == ["Kompakt"]
    assert Expression(CEL, "string(double(src[0]) / 1000.0)")(["62.4"]) == ["0.0624"]  # unit conversion
    assert Expression(CEL, "[src[0] + ' ' + src[1]]")(["24", "V"]) == ["24 V"]  # two sources, one target


def test_expression_undefined_on_values_is_not_defined():
    assert not Expression(CEL, "src[0].filter(s, s.language == 'fr')[0].text").defined([MLP])


def test_expression_cannot_execute_code(tmp_path):
    marker = tmp_path / "pwned"
    for attempt in [f"__import__('os').system('touch {marker}')",
                    f"open('{marker}', 'w')",
                    "src.__class__.__mro__"]:
        assert not Expression(CEL, attempt).defined(["x"])
    assert not marker.exists()


def test_only_allowlisted_languages_are_executable():
    assert Expression(CEL, "src[0]").executable
    assert not Expression("https://www.python.org", "src[0]").executable
    assert not Expression(CEL, "src[0]" + " " * MAX_EXPRESSION_LENGTH).executable
