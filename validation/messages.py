"""Failure messages of the validation checks: what differs, not only that something differs."""

from collections import Counter
from collections.abc import Iterable

LIMIT = 10


def listing(label: str, entries: Iterable, limit: int = LIMIT) -> str:
    entries = sorted(entries, key=str)
    if not entries:
        return ""
    shown = "".join(f"\n    {e}" for e in entries[:limit])
    more = f"\n    … {len(entries) - limit} more" if len(entries) > limit else ""
    return f"\n  {label} ({len(entries)}):{shown}{more}"


def difference(what: str, observed: Iterable, expected: Iterable) -> str:
    """Observed and expected collections of `what`, as the entries only one of them has."""
    observed, expected = Counter(observed), Counter(expected)
    return (what + listing("observed, not expected", (observed - expected).elements())
            + listing("expected, not observed", (expected - observed).elements()))
