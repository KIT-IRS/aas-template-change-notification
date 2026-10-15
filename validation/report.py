"""Results of a validation run by case (paper Table 4): a summary in the terminal, and a report.

    uv run pytest -m "not infra"                                      # summary by case at the end
    uv run pytest -m "not infra" --validation-report=report.html      # report with views of the cases
    uv run pytest -m "not infra" --validation-report=report.md
    uv run pytest --validation-report=validation-report.html --validation-report=validation-report.md

A case is a test module; subject, requirements, method and pass criterion are taken from its
docstring, the expectations from its module attributes (CHAIN, CHAINS, EXPECTED, UNDOCUMENTED,
GENERATED_OVERWRITES) and the expectation documents they name. The report adds the views of
validation.render; their application views run resolution and application once more.
Presentation only: the outcome of a case is the outcome of its tests.
"""

from __future__ import annotations

import datetime
import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from validation import render
from validation.render import badge, esc, table

OUTCOMES = ("passed", "failed", "error", "skipped", "not run")


@dataclass
class Check:
    name: str
    param: str
    outcome: str = "not run"
    duration: float = 0.0
    message: str = ""
    detail: str = ""
    infra: bool = False


@dataclass
class Case:
    path: str
    module: object
    key: str = ""
    subject: str = ""
    refs: str = ""
    requirements: str = ""
    method: str = ""
    criterion: str = ""
    checks: dict[str, Check] = field(default_factory=dict)

    @property
    def anchor(self) -> str:
        return self.key.lower() or Path(self.path).stem

    @property
    def title(self) -> str:
        return f"{self.key} {self.subject}" if self.key else Path(self.path).name

    def count(self, outcome: str) -> int:
        return sum(c.outcome == outcome for c in self.checks.values())

    @property
    def status(self) -> str:
        if self.count("failed") or self.count("error"):
            return "failed"
        if self.count("passed"):
            return "passed"
        return "skipped" if self.count("skipped") else "not run"

    def result(self) -> str:
        """The status, with what did not run."""
        if self.status == "not run":
            return "not run (infra)" if all(c.infra for c in self.checks.values()) else "not run"
        return f"{self.status} ({self.note()})" if self.note() else self.status

    def note(self) -> str:
        """What did not run, and why."""
        parts = []
        if n := self.count("skipped"):
            parts.append(f"{n} skipped")
        if n := self.count("not run"):
            infra = all(c.infra for c in self.checks.values() if c.outcome == "not run")
            parts.append(f"{n} not run" + (" (infra)" if infra else ""))
        return ", ".join(parts)

    def chains(self) -> list[str]:
        m = self.module
        chains = getattr(m, "CHAINS", None)
        found = list(chains.values()) if isinstance(chains, dict) else list(chains or [])
        if c := getattr(m, "CHAIN", None):
            found.append(c)
        if e := getattr(m, "EXPECTED", None):
            exp = _yaml(e)
            found += exp.get("chains") or [exp["chain"]]
        return list(dict.fromkeys(found))


def _yaml(path: str) -> dict:
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _case(path: str, module) -> Case:
    doc = (module.__doc__ or "").strip()
    first = doc.split("\n", 1)[0]
    case = Case(path, module)
    if m := re.match(r"(V\d+): (.*?)\s+\((.*)\)\.?$", first):
        case.key, case.subject, case.refs = m.groups()
    else:
        case.subject = first.rstrip(".")
    if m := re.search(r"Requirements? ([^.]+)\.\s*Method: ([^.]+)\.", doc):
        case.requirements, case.method = m.groups()
    if m := re.search(r"Pass criterion: (.*?)(?:\n\s*\n|$)", doc, re.S):
        case.criterion = " ".join(m.group(1).split())
    return case


def _sort_key(case: Case):
    m = re.match(r"V(\d+)", case.key)
    return (0, int(m.group(1))) if m else (1, case.path)


class Recorder:
    def __init__(self, config: pytest.Config):
        self.config = config
        self.cases: dict[str, Case] = {}
        self.applications: dict[str, render.ApplicationView] = {}

    def _application(self, path: str) -> render.ApplicationView:
        """The application view of an expectation, computed once for all report formats."""
        if path not in self.applications:
            self.applications[path] = render.application_view(path)
        return self.applications[path]

    def _check(self, item) -> Check | None:
        module = getattr(item, "module", None)
        if module is None:
            return None
        path = item.nodeid.split("::", 1)[0]
        case = self.cases.setdefault(path, _case(path, module))
        name = getattr(item, "originalname", item.name)
        param = item.name[len(name):].strip("[]")
        return case.checks.setdefault(item.nodeid, Check(
            name.removeprefix("test_").replace("_", " "), param, infra=item.get_closest_marker("infra") is not None))

    @pytest.hookimpl(tryfirst=True)  # before -m deselects, so that deselected checks show as not run
    def pytest_collection_modifyitems(self, items):
        for item in items:
            self._check(item)

    def pytest_runtest_logreport(self, report: pytest.TestReport):
        path = report.nodeid.split("::", 1)[0]
        check = self.cases.get(path, Case(path, None)).checks.get(report.nodeid)
        if check is None:
            return
        check.duration += report.duration
        if report.when == "call" or (report.when == "setup" and not report.passed):
            check.outcome = report.outcome if report.when == "call" or report.skipped else "error"
        elif report.when == "teardown" and report.failed:
            check.outcome = "error"
        if report.failed:
            crash = getattr(report.longrepr, "reprcrash", None)
            check.message = (crash.message if crash else str(report.longrepr)).strip()
            check.detail = str(report.longrepr)
        elif report.skipped and isinstance(report.longrepr, tuple):
            check.message = str(report.longrepr[2]).removeprefix("Skipped: ")

    def ordered(self) -> list[Case]:
        return sorted(self.cases.values(), key=_sort_key)

    # --- terminal -------------------------------------------------------------------------

    def pytest_terminal_summary(self, terminalreporter, exitstatus, config):
        tr = terminalreporter
        cases = self.ordered()
        if not cases:
            return
        tr.write_sep("=", "validation cases (paper Table 4)")
        colour = {"passed": {"green": True}, "failed": {"red": True, "bold": True},
                  "skipped": {"yellow": True}, "not run": {"yellow": True}}
        width = max(len(c.title) for c in cases)
        rw, mw = (max(len(getattr(c, a)) for c in cases) for a in ("requirements", "method"))
        for c in cases:
            if not c.key and c is next(x for x in cases if not x.key):
                tr.write_line("supporting tests")
            meta = f"{c.requirements:<{rw}}  {c.method:<{mw}}"
            tr.write(f"{c.title:<{width}}  {meta} {c.count('passed'):>3}/{len(c.checks):<3} ")
            tr.write(f"{c.status:<8}", **colour[c.status])
            tr.write_line(f"  {c.note()}" if c.note() and c.status != "not run" else (
                "  (infra)" if c.result() == "not run (infra)" else ""))
            for check in c.checks.values():
                if check.outcome in ("failed", "error"):
                    tr.write("    ✗ ", red=True)
                    tr.write_line(f"{check.name}" + (f" [{check.param}]" if check.param else ""))
                    lines = check.message.splitlines()  # the message of the check, without the introspection
                    cut = next((i for i, x in enumerate(lines) if i and x.startswith("assert ")), len(lines))
                    for line in lines[:min(cut, 12)]:
                        tr.write_line(f"        {line}")
        for path in config.getoption("validation_report") or []:
            self.write(Path(path))
            tr.write_line(f"validation report written to {path}")

    # --- report ---------------------------------------------------------------------------

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".md":
            path.write_text(self.markdown(), encoding="utf-8")
        else:
            path.write_text(self.html(), encoding="utf-8")

    def _context(self) -> list[tuple[str, str]]:
        try:
            rev = subprocess.run(["git", "describe", "--always", "--dirty"], capture_output=True, text=True,
                                 cwd=self.config.rootpath, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            rev = ""
        return [("run", datetime.datetime.now().isoformat(timespec="seconds")), ("revision", rev or "—"),
                ("python", platform.python_version()),
                ("selection", self.config.getoption("markexpr") or "all tests")]

    def html(self) -> str:
        cases = self.ordered()
        vcases = [c for c in cases if c.key]
        out = ["<h1>Validation report</h1>",
               '<dl class="kv">' + "".join(f"<dt>{k}</dt><dd>{esc(v)}</dd>" for k, v in self._context()) + "</dl>"]

        out.append("<h2>Validation cases</h2><p>Paper Table 4. A case passes if all of its checks that ran pass."
                   "</p>")
        out.append(table(["case", "subject", "requirements", "method", "checks", "result", ""],
                         [[f'<a href="#{c.anchor}">{esc(c.key)}</a>', esc(c.subject), esc(c.requirements),
                           esc(c.method), f"{c.count('passed')}/{len(c.checks)}", badge(c.status),
                           f'<span class="muted">{esc(c.note())}</span>'] for c in vcases], numeric={4}))
        out.append("<h3>Supporting tests</h3>")
        out.append(table(["tests", "subject", "checks", "result", ""],
                         [[f'<a href="#{c.anchor}"><code>{esc(Path(c.path).name)}</code></a>', esc(c.subject),
                           f"{c.count('passed')}/{len(c.checks)}", badge(c.status),
                           f'<span class="muted">{esc(c.note())}</span>'] for c in cases if not c.key],
                         numeric={2}))

        views: dict[str, render.ChainView] = {}
        for c in cases:
            for p in c.chains():
                views.setdefault(p, render.chain_view(p))

        for c in vcases:
            out.append(self._case_html(c, views))
        out.append("<h2>Supporting tests</h2>")
        for c in cases:
            if not c.key:
                out.append(f'<div class="card" id="{esc(c.anchor)}"><h3><code>{esc(Path(c.path).name)}</code> '
                           f'{badge(c.status)}</h3><p>{esc(c.subject)}</p>' + self._checks_html(c, collapsed=True)
                           + "</div>")

        out.append("<h2>Chains</h2>" + render.legend())
        undocumented = self._undocumented()
        out += [render.chain_html(v, undocumented.get(p)) for p, v in views.items()]
        return render.page("Validation report", "\n".join(out))

    def _undocumented(self) -> dict[str, dict[str, list[str]]]:
        """Per chain: section group (or "generated") -> the undocumented differences it states."""
        marks: dict[str, dict[str, list[str]]] = {}
        for c in self.ordered():
            und = getattr(c.module, "UNDOCUMENTED", None)
            if und is None:
                continue
            chains = getattr(c.module, "CHAINS", None) or {"": getattr(c.module, "CHAIN", None)}
            per = und if isinstance(und, dict) else {k: und for k in chains}
            for k, entries in per.items():
                for group, change in entries:
                    marks.setdefault(chains[k], {}).setdefault(group, []).append(
                        " ".join(map(str, change)) if change else "(see the comment in the test module)")
        return marks

    def _checks_html(self, c: Case, collapsed: bool = False) -> str:
        rows = []
        for check in c.checks.values():
            msg = f'<pre>{esc(check.message)}</pre>' if check.message else ""
            if check.detail:
                msg += f"<details><summary>traceback</summary><pre>{esc(check.detail)}</pre></details>"
            rows.append([esc(check.name), f"<code>{esc(check.param)}</code>" if check.param else "",
                         badge(check.outcome), f"{check.duration:.2f} s", msg])
        t = table(["check", "parameter", "result", "time", ""], rows, numeric={3})
        failing = c.count("failed") or c.count("error")
        if collapsed and not failing:
            return f"<details><summary>{len(rows)} checks</summary>{t}</details>"
        return t

    def _case_html(self, c: Case, views: dict[str, render.ChainView]) -> str:
        m = c.module
        out = [f'<h2 id="{esc(c.anchor)}">{esc(c.key)}: {esc(c.subject)} {badge(c.status)}</h2>',
               f'<p>{esc(c.refs)}</p>' if c.refs else "",
               '<dl class="kv">'
               + (f"<dt>requirements</dt><dd>{esc(c.requirements)}</dd>" if c.requirements else "")
               + (f"<dt>method</dt><dd>{esc(c.method)}</dd>" if c.method else "")
               + (f"<dt>pass criterion</dt><dd>{esc(c.criterion)}</dd>" if c.criterion else "")
               + "".join(f'<dt>chain</dt><dd><a href="#chain-{esc(Path(p).stem)}"><code>{esc(p)}</code></a></dd>'
                         for p in c.chains())
               + "</dl>", "<h3>Checks</h3>", self._checks_html(c)]

        und = getattr(m, "UNDOCUMENTED", None)
        over = getattr(m, "GENERATED_OVERWRITES", None)
        if und is not None or over is not None:
            per_und = und if isinstance(und, dict) else {"": und or []}
            per_over = over if isinstance(over, dict) else {"": over or set()}
            out.append("<h3>Differences the change log does not state</h3><p>Paper Table 5; enumerated by hand "
                       "in the test module, each stated by the named section of the chain.</p>")
            for k in dict.fromkeys([*per_und, *per_over]):
                if k:
                    out.append(f"<h4>{esc(k)}</h4>")
                rows = [[esc(g), f'<span class="mono">{esc(" · ".join(map(str, ch)) if ch else "—")}</span>']
                        for g, ch in per_und.get(k, [])]
                out.append(table(["stated by", "change (path, key, new value)"], rows) if rows
                           else '<p>none listed</p>')
                rows = [[f'<span class="mono">{esc(" · ".join(map(str, ch)))}</span>']
                        for ch in sorted(per_over.get(k, set()))]
                out.append("<p>Generated items that overwrite a populated value:</p>"
                           + (table(["change (path, key, new value)"], rows) if rows else "<p>none</p>"))

        if e := getattr(m, "EXPECTED", None):
            out.append("<h3>Application to the instance</h3><p>Paper Table 6; expectations from "
                       f"<code>{esc(e)}</code>, observed by an offline run.</p>")
            view = self._application(e)
            out.append(render.application_html(view, views.get(view.chains[0])))
        return "\n".join(out)

    def markdown(self) -> str:
        cases = self.ordered()
        out = ["# Validation report", "", *(f"- {k}: {v}" for k, v in self._context()), "",
               "## Validation cases", "", "| case | subject | requirements | method | checks | result |",
               "|---|---|---|---|---:|---|"]
        for c in cases:
            if c.key:
                out.append(f"| {c.key} | {c.subject} | {c.requirements} | {c.method} | "
                           f"{c.count('passed')}/{len(c.checks)} | {c.result()} |")
        out += ["", "## Supporting tests", "", "| tests | subject | checks | result |", "|---|---|---:|---|"]
        for c in cases:
            if not c.key:
                out.append(f"| `{Path(c.path).name}` | {c.subject} | {c.count('passed')}/{len(c.checks)} | "
                           f"{c.result()} |")
        for c in cases:
            if not c.key:
                continue
            out += ["", f"## {c.key}: {c.subject} — {c.result()}", ""]
            if c.criterion:
                out += [f"Requirements {c.requirements}. Method: {c.method}.", "", f"Pass criterion: {c.criterion}",
                        ""]
            out += ["| check | parameter | result | time |", "|---|---|---|---:|"]
            out += [f"| {k.name} | {k.param} | {k.outcome} | {k.duration:.2f} s |" for k in c.checks.values()]
            for k in c.checks.values():
                if k.outcome in ("failed", "error"):
                    out += ["", f"**{k.name}** {k.param}", "", "```", k.message, "```"]
            if e := getattr(c.module, "EXPECTED", None):
                view = self._application(e)
                out += ["", f"Application to the instance (`{e}`):", ""]
                if view.error:
                    out += ["```", view.error, "```"]
                else:
                    counts = view.counts()
                    out += ["Notes: " + ", ".join(f"{k} {counts[k]}" for k in render.NOTE_KINDS if counts[k]), "",
                            "| | expectation | expected | observed |", "|---|---|---|---|"]
                    for title, rows in (("retained", view.retained), ("control", view.control),
                                        ("manual", view.manual), ("removed", view.removed),
                                        ("violation", view.violations)):
                        out += [f"| {'✓' if r.ok else '✗'} | {title}: `{r.subject}` | {r.expected} | {r.observed} |"
                                for r in rows]
        out.append("")
        return "\n".join(out)


def pytest_addoption(parser):
    parser.addoption("--validation-report", dest="validation_report", metavar="PATH", action="append",
                     help="write a report of the validation run by case (.html, or .md for Markdown); "
                          "may be given more than once")


def pytest_configure(config):
    config.pluginmanager.register(Recorder(config), "validation-report")
