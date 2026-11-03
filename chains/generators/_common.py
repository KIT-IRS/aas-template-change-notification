"""Writing intent files: the record header of an IDTA template, and items in the flow style of the
hand-written intent files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tcn import dropins
from tcn.aas import bridge
from tcn.core.model import Template

ROOT = Path(__file__).resolve().parents[2]
ID = {"Kind": "Identity"}
IDTA_ADDRESS = {"Company": "Industrial Digital Twin Association e.V.", "Street": "Lyoner Straße 18",
                "Zipcode": "60528", "CityTown": "Frankfurt am Main", "NationalCode": "DE"}


def load(path: str) -> Template:
    """A template file (relative to the repository) as effective template."""
    return bridge.from_jsonable(dropins.load(ROOT / path))


def header(family: str, pre: str, post: str, change_uri: str) -> dict[str, Any]:
    """The record header of an IDTA template; the versions are the ids of the two templates."""
    A, B = load(pre), load(post)
    return {"Family": family, "PreVersion": A.A[A.attr(A.root, "id")].value,
            "PostVersion": B.A[B.attr(B.root, "id")].value, "PreTemplate": pre, "PostTemplate": post,
            "TemplateOwner": "Industrial Digital Twin Association (IDTA)", "TemplateOwnerAddress": IDTA_ADDRESS,
            "ChangeURI": change_uri}


def item(operation: str, path: str | None = None, **arguments: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"ChangeOperation": operation}
    if path is not None:
        d["ElementPath"] = path
    return d | arguments


def flow(d: dict[str, Any]) -> str:
    return yaml.safe_dump(d, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10**6).strip()


def write(path: str, comment: str, head: dict[str, Any], sections: list[tuple[str, str, Any]]) -> None:
    """Write an intent file. A section is (title, "hand", items) or (title, "rule", {rule: argument})."""
    lines = [comment.rstrip("\n"), "", yaml.safe_dump({"header": head}, sort_keys=False, allow_unicode=True,
                                                       width=120).rstrip("\n"), "", "sections:"]
    for title, origin, body in sections:
        lines += [f'  - title: "{title}"', f"    origin: {origin}"]
        if origin == "hand":
            lines += ["    items:"] + [f"      - {flow(i)}" for i in body]
        else:
            lines.append("    rule:")
            for rule, argument in body.items():
                lines.append(f"      {rule}:")
                lines += [f'        "{k}": {"null" if v is None else v}' for k, v in argument.items()]
    (ROOT / path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(len(b) for _, o, b in sections if o == "hand")
    print(f"{path}: {n} hand items, {sum(o == 'rule' for _, o, _ in sections)} rule sections")
