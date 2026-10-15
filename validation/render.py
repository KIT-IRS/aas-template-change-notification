"""Views of a chain and of its application to a submodel, for reading the validation.

Presentation only: a chain view reads the chain document; an application view runs resolution and
guarded application as the validation does (validation.application.run) and sets what it observes
beside the expectations derived by hand. Neither decides whether a case passes; the tests do.

    uv run python -m validation.render chains/technicaldata_1.2_to_2.0.yaml
    uv run python -m validation.render fixtures/expected/technicaldata_1.2_to_2.0.yaml
    uv run python -m validation.render <chain or expectation> -o view.html
"""

from __future__ import annotations

import argparse
import html
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from tcn import chainfile
from tcn.chainfile import Section
from tcn.core.addressing import Item

ORIGINS = ("hand", "rule", "generated")
NOTE_KINDS = ("manual", "removed", "transferred", "expanded", "inserted", "elided")


# --- chain view ---------------------------------------------------------------------------


@dataclass
class SectionView:
    number: int
    first: int  # 1-based index of the first item in the chain, as Note.index counts
    section: Section

    @property
    def group(self) -> str:
        head, sep, _ = self.section.title.partition(":")
        return head if sep and " " not in head else ""

    @property
    def heading(self) -> str:
        return self.section.title.partition(": ")[2] if self.group else self.section.title

    @property
    def indices(self) -> range:
        return range(self.first, self.first + len(self.section.items))

    def operations(self) -> Counter:
        return Counter(i.operation for i in self.section.items)


@dataclass
class ChainView:
    path: str
    header: dict
    sections: list[SectionView]

    @property
    def name(self) -> str:
        return Path(self.path).stem

    @property
    def size(self) -> int:
        return sum(len(s.section.items) for s in self.sections)

    def operations(self) -> list[str]:
        return sorted({op for s in self.sections for op in s.operations()})

    def by_origin(self) -> dict[str, Counter]:
        totals = {o: Counter() for o in ORIGINS}
        for s in self.sections:
            totals.setdefault(s.section.origin, Counter()).update(s.operations())
        return totals

    def section_of(self, index: int) -> SectionView | None:
        return next((s for s in self.sections if index in s.indices), None)


def chain_view(path: str) -> ChainView:
    chain = chainfile.load(path)
    sections, first = [], 1
    for n, s in enumerate(chain.sections, 1):
        sections.append(SectionView(n, first, s))
        first += len(s.items)
    return ChainView(str(path), chain.header, sections)


def arguments(item: Item) -> str:
    d = chainfile.item_to_dict(item)
    d.pop("ChangeOperation")
    d.pop("ElementPath", None)
    if "TransferFunction" in d:
        d["TransferFunction"] = d["TransferFunction"]["Kind"]
    return ", ".join(f"{k}={v}" for k, v in d.items())


# --- application view ---------------------------------------------------------------------


@dataclass
class Row:
    """A comparison of one expected entry with what was observed."""
    subject: str
    expected: object
    observed: object
    ok: bool


@dataclass
class ApplicationView:
    path: str
    chains: list[str]
    instance: str
    error: str | None = None
    notes: list = field(default_factory=list)
    retained: list[Row] = field(default_factory=list)
    control: list[Row] = field(default_factory=list)
    manual: list[Row] = field(default_factory=list)
    removed: list[Row] = field(default_factory=list)
    violations: list[Row] = field(default_factory=list)
    findings: list = field(default_factory=list)
    conforms: tuple[bool, bool] | None = None  # (expected, observed)

    @property
    def name(self) -> str:
        return Path(self.path).stem

    def counts(self) -> Counter:
        return Counter(n.kind for n in self.notes)

    def by_section(self, chain: ChainView) -> list[tuple[SectionView, Counter]]:
        """Notes per section of the chain. Only for one chain: Note.index counts within its chain."""
        rows = {s.number: Counter() for s in chain.sections}
        for n in self.notes:
            s = chain.section_of(n.index)
            if s is not None:
                rows[s.number][n.kind] += 1
        return [(s, rows[s.number]) for s in chain.sections]

    def rows(self) -> list[Row]:
        return self.retained + self.control + self.manual + self.removed + self.violations


def _compare(expected: list, observed: list, distinct: bool) -> list[Row]:
    """Entries with how often each was expected and observed; `distinct`: compared as sets, as the
    test compares them, so that an entry observed more than once is still as expected."""
    exp, obs = Counter(expected), Counter(observed)
    return [Row(str(x), exp[x], obs[x], bool(exp[x]) == bool(obs[x]) if distinct else exp[x] == obs[x])
            for x in sorted(exp | obs, key=str)]


def application_view(path: str) -> ApplicationView:
    from tcn.core.conformance import VIOLATIONS, check, conforms
    from tcn.roles.template_owner import load_templates
    from validation import application

    exp = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    view = ApplicationView(str(path), exp.get("chains") or [exp["chain"]], exp["instance"])
    try:
        _, chain, instance, T, notes = application.run(path)
    except AssertionError as e:  # refused: the view shows the reason
        view.error = str(e) or "refused"
        return view

    def value(template, p):
        try:
            return application._attrs(template, p)
        except Exception:  # noqa: BLE001 - an element missing at the path is shown as missing
            return None

    view.notes = notes
    for p, want in exp.get("retained", {}).items():
        got = (value(T, p) or {}).get("value", "—")
        view.retained.append(Row(p, want, got, got == want))
    for old, new in exp.get("control", {}).items():
        before, after = value(instance, old), value(T, new)
        same = after is not None and after == before
        view.control.append(Row(f"{old} → {new}", "unchanged", "unchanged" if same else "changed", same))
    view.manual = _compare(exp.get("manual", []), [n.path for n in notes if n.kind == "manual"], distinct=True)
    view.removed = _compare(exp.get("removed", []), [n.path for n in notes if n.kind == "removed"], distinct=True)
    view.findings = check(load_templates(chain)[1], T)
    view.violations = _compare([tuple(v) for v in exp.get("violations", [])],
                               [(f.kind, f.path) for f in view.findings if f.kind in VIOLATIONS], distinct=False)
    if "conforms" in exp:
        view.conforms = (exp["conforms"], conforms(view.findings))
    return view


# --- text ---------------------------------------------------------------------------------


def chain_text(view: ChainView) -> str:
    h = view.header
    lines = [f"{view.path}", f"  {h.get('PreVersion')}", f"  → {h.get('PostVersion')}",
             f"  {view.size} items in {len(view.sections)} sections", "",
             f"  {'#':>3}  {'origin':9}  {'items':>5}  section"]
    for s in view.sections:
        ops = ", ".join(f"{op} {n}" for op, n in s.operations().most_common())
        lines.append(f"  {s.number:>3}  {s.section.origin:9}  {len(s.section.items):>5}  {s.section.title}")
        lines.append(f"  {'':>3}  {'':9}  {'':>5}    {ops}")
    return "\n".join(lines)


def application_text(view: ApplicationView) -> str:
    lines = [view.path, f"  instance {view.instance}", *(f"  chain    {c}" for c in view.chains)]
    if view.error:
        return "\n".join(lines + [f"  REFUSED  {view.error}"])
    lines.append("  notes    " + ", ".join(f"{k} {view.counts()[k]}" for k in NOTE_KINDS if view.counts()[k]))
    for title, rows in (("retained", view.retained), ("control set", view.control), ("manual", view.manual),
                        ("removed", view.removed), ("violations", view.violations)):
        if rows:
            lines.append(f"\n  {title}")
            lines += [f"    {'✓' if r.ok else '✗'} {r.subject}" + (
                (f" = {r.observed!r}" if rows is view.retained else "") if r.ok
                else f"   expected {r.expected!r}, observed {r.observed!r}") for r in rows]
    if view.conforms:
        lines.append(f"\n  conforms to the new template: {'yes' if view.conforms[1] else 'no'}"
                     f" (expected {'yes' if view.conforms[0] else 'no'})")
    return "\n".join(lines)


# --- HTML ---------------------------------------------------------------------------------

CSS = """
:root { --bg:#fbfbfa; --fg:#1d1d1f; --muted:#6b6b70; --line:#e2e2e0; --card:#ffffff; --code:#f2f2ef;
  --ok:#1a7f37; --ok-bg:#e6f4ea; --bad:#c62828; --bad-bg:#fdecea; --skip:#8a6d00; --skip-bg:#fff6d6;
  --hand:#2f5fb3; --rule:#7b4bb7; --generated:#6b6b70; --accent:#2f5fb3; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#141416; --fg:#ececee; --muted:#9a9aa2; --line:#2c2c31; --card:#1b1b1f; --code:#232328;
  --ok:#5cc777; --ok-bg:#16321f; --bad:#ff7b72; --bad-bg:#3a1a1a; --skip:#e3c25a; --skip-bg:#332b10;
  --hand:#7fa6ee; --rule:#b892ee; --generated:#9a9aa2; --accent:#7fa6ee; } }
:root[data-theme="dark"] { --bg:#141416; --fg:#ececee; --muted:#9a9aa2; --line:#2c2c31; --card:#1b1b1f;
  --code:#232328; --ok:#5cc777; --ok-bg:#16321f; --bad:#ff7b72; --bad-bg:#3a1a1a; --skip:#e3c25a;
  --skip-bg:#332b10; --hand:#7fa6ee; --rule:#b892ee; --generated:#9a9aa2; --accent:#7fa6ee; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width:1100px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:22px; margin:0 0 4px; } h2 { font-size:18px; margin:40px 0 8px; }
h3 { font-size:15px; margin:24px 0 6px; } h4 { font-size:13px; margin:16px 0 4px; color:var(--muted); }
p, .muted { color:var(--muted); margin:4px 0; }
a { color:var(--accent); }
code, .mono { font:12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }
code { background:var(--code); padding:1px 4px; border-radius:4px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; margin:12px 0; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; }
th, td { text-align:left; padding:5px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-weight:600; color:var(--muted); font-size:12px; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.badge { display:inline-block; padding:1px 8px; border-radius:999px; font-size:12px; font-weight:600;
  white-space:nowrap; }
.passed { color:var(--ok); background:var(--ok-bg); } .failed, .error { color:var(--bad); background:var(--bad-bg); }
.skipped, .not-run { color:var(--skip); background:var(--skip-bg); }
.o-hand { color:var(--hand); } .o-rule { color:var(--rule); } .o-generated { color:var(--generated); }
.ok { color:var(--ok); } .bad { color:var(--bad); }
.bar { display:flex; height:8px; border-radius:4px; overflow:hidden; background:var(--line); min-width:80px; }
.bar span { display:block; height:100%; }
.bar .b-hand { background:var(--hand); } .bar .b-rule { background:var(--rule); }
.bar .b-generated { background:var(--generated); }
.zero { color:var(--line); }
details > summary { cursor:pointer; color:var(--accent); margin:6px 0; }
pre { background:var(--code); padding:8px 10px; border-radius:6px; overflow-x:auto; white-space:pre-wrap;
  font:12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; margin:4px 0; }
.kv { display:grid; grid-template-columns:max-content 1fr; gap:2px 16px; }
.kv dt { color:var(--muted); } .kv dd { margin:0; overflow-wrap:anywhere; }
.legend span { margin-right:14px; }
.mark { color:var(--skip); font-weight:600; }
"""


def esc(x) -> str:
    return html.escape(str(x))


def badge(status: str) -> str:
    return f'<span class="badge {esc(status.replace(" ", "-"))}">{esc(status)}</span>'


def table(head: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    th = "".join(f'<th class="num">{h}</th>' if i in numeric else f"<th>{h}</th>" for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="num">{c}</td>' if i in numeric else f"<td>{c}</td>"
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")


def _origin(o: str) -> str:
    return f'<span class="o-{esc(o)}">{esc(o)}</span>'


def _bar(counts: dict[str, int]) -> str:
    total = sum(counts.values()) or 1
    return '<div class="bar">' + "".join(
        f'<span class="b-{o}" style="width:{100 * counts.get(o, 0) / total:.1f}%" title="{o}: {counts.get(o, 0)}">'
        "</span>" for o in ORIGINS) + "</div>"


def _n(x: int) -> str:
    return str(x) if x else '<span class="zero">·</span>'


def chain_html(view: ChainView, marked: dict[str, list[str]] | None = None, anchor: str | None = None) -> str:
    """The chain: header, items by origin and operation, and its sections with their items.
    `marked`: section groups (or "generated") with notes to show at the section, e.g. undocumented
    differences."""
    marked = marked or {}
    h = view.header
    out = [f'<div class="card" id="{esc(anchor or "chain-" + view.name)}">',
           f"<h3>{esc(view.name)}</h3>",
           '<dl class="kv">'
           + "".join(f"<dt>{k}</dt><dd><code>{esc(h[k])}</code></dd>" for k in
                     ("Family", "PreVersion", "PostVersion", "PreTemplate", "PostTemplate", "ChangeURI") if k in h)
           + "</dl>"]

    totals = view.by_origin()
    sizes = {o: sum(c.values()) for o, c in totals.items()}
    out.append(f"<h4>{view.size} items: " + ", ".join(
        f'{_origin(o)} {sizes.get(o, 0)}' for o in ORIGINS) + "</h4>" + _bar(sizes))
    ops = view.operations()
    out.append(table(["origin", *ops, "total"],
                     [[_origin(o), *(_n(totals[o][op]) for op in ops), str(sizes[o])] for o in ORIGINS if sizes[o]],
                     numeric=set(range(1, len(ops) + 2))))

    out.append("<h4>Sections</h4>")
    rows = []
    for s in view.sections:
        notes = marked.get(s.group, []) + (marked.get("generated", []) if s.section.origin == "generated" else [])
        mark = "".join(f'<div class="mark">undocumented in the change log: {esc(n)}</div>' for n in notes)
        rows.append([str(s.number), esc(s.group), esc(s.heading) + mark, _origin(s.section.origin),
                     str(len(s.section.items)),
                     esc(", ".join(f"{op} {n}" for op, n in s.operations().most_common()))])
    out.append(table(["#", "group", "section", "origin", "items", "operations"], rows, numeric={0, 4}))

    out.append("<details><summary>All items</summary>")
    for s in view.sections:
        out.append(f"<h4>{s.number}. {esc(s.section.title)} ({_origin(s.section.origin)})</h4>")
        out.append(table(["#", "operation", "ElementPath", "arguments"],
                         [[str(i), esc(it.operation), f'<span class="mono">{esc(it.element_path)}</span>',
                           f'<span class="mono">{esc(arguments(it))}</span>']
                          for i, it in zip(s.indices, s.section.items)], numeric={0}))
    out.append("</details></div>")
    return "\n".join(out)


def _rows_html(rows: list[Row], show_values: bool) -> str:
    def cell(r: Row):
        mark = '<span class="ok">✓</span>' if r.ok else '<span class="bad">✗</span>'
        base = [mark, f'<span class="mono">{esc(r.subject)}</span>']
        return base + ([esc(r.expected), esc(r.observed)] if show_values else
                       [_presence(r.expected), _presence(r.observed)])
    return table(["", "", "expected", "observed"], [cell(r) for r in rows])


def _presence(n) -> str:
    return "yes" if n == 1 else ("—" if not n else f"{n}×")


def application_html(view: ApplicationView, chain: ChainView | None = None) -> str:
    out = [f'<div class="card" id="application-{esc(view.name)}">', f"<h3>{esc(view.name)}</h3>",
           '<dl class="kv"><dt>instance</dt><dd><code>' + esc(view.instance) + "</code></dd>"
           + "".join(f'<dt>chain</dt><dd><a href="#chain-{esc(Path(c).stem)}"><code>{esc(c)}</code></a></dd>'
                     for c in view.chains) + "</dl>"]
    if view.error:
        out.append(f'<p>{badge("failed")} resolution or application refused</p><pre>{esc(view.error)}</pre></div>')
        return "\n".join(out)

    counts = view.counts()
    out.append("<h4>Resolution notes</h4>" + table(
        [k for k in NOTE_KINDS], [[_n(counts[k]) for k in NOTE_KINDS]], numeric=set(range(len(NOTE_KINDS)))))
    if chain is not None and len(view.chains) == 1:
        rows = [[str(s.number), esc(s.section.title), _origin(s.section.origin), *(_n(c[k]) for k in NOTE_KINDS)]
                for s, c in view.by_section(chain) if sum(c.values())]
        out.append("<details><summary>Notes per section of the chain</summary>"
                   + table(["#", "section", "origin", *NOTE_KINDS], rows, numeric={0, *range(3, 3 + len(NOTE_KINDS))})
                   + "</details>")

    ok = sum(r.ok for r in view.rows())
    out.append(f"<h4>Expectations: {ok} of {len(view.rows())} entries as expected</h4>")
    for title, rows, values in (("Retained values", view.retained, True), ("Control set", view.control, True),
                                ("Manual steps reported before consent", view.manual, False),
                                ("Values removed", view.removed, False),
                                ("Violations of the new template", view.violations, False)):
        if rows:
            out.append(f"<h4>{title}</h4>" + _rows_html(rows, values))
    if view.conforms:
        exp, obs = view.conforms
        out.append(f"<p>Result conforms to the new template: <b>{'yes' if obs else 'no'}</b> "
                   f"(expected {'yes' if exp else 'no'})</p>")

    shown = [n for n in view.notes if n.kind in ("manual", "transferred", "removed")]
    if shown:
        out.append("<details><summary>Reported before consent: manual steps, transferred and removed values"
                   "</summary>" + table(["item", "kind", "path", "detail"],
                                        [[str(n.index), esc(n.kind), f'<span class="mono">{esc(n.path)}</span>',
                                          esc(n.detail)] for n in shown], numeric={0}) + "</details>")
    if view.findings:
        out.append("<details><summary>All findings of the conformance check</summary>" + table(
            ["kind", "path", "detail"], [[esc(f.kind), f'<span class="mono">{esc(f.path)}</span>', esc(f.detail)]
                                         for f in view.findings]) + "</details>")
    out.append("</div>")
    return "\n".join(out)


def legend() -> str:
    return ('<p class="legend">Origin of a section: '
            + "".join(f'<span>{_origin(o)}</span>' for o in ORIGINS)
            + " (see <code>src/tcn/chainfile.py</code>)</p>")


# --- command line -------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m validation.render", description=__doc__.split("\n\n")[0])
    p.add_argument("document", help="a chain (chains/*.yaml) or an expectation (fixtures/expected/*.yaml)")
    p.add_argument("-o", "--out", help="write an HTML view to this file instead of printing a summary")
    args = p.parse_args(argv)

    doc = yaml.safe_load(Path(args.document).read_text(encoding="utf-8"))
    if "sections" in doc:
        view = chain_view(args.document)
        text, body = chain_text(view), legend() + chain_html(view)
        title = f"Chain {view.name}"
    else:
        view = application_view(args.document)
        chains = [chain_view(c) for c in view.chains]
        text = application_text(view)
        body = application_html(view, chains[0]) + "<h2>Chains</h2>" + legend() + "".join(map(chain_html, chains))
        title = f"Application {view.name}"
    if args.out:
        Path(args.out).write_text(page(title, f"<h1>{esc(title)}</h1>" + body), encoding="utf-8")
        print(f"written to {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
