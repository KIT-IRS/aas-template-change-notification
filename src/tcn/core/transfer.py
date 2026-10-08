"""Transfer functions f of Sync(X_src, X_tgt, f)  (paper §3.3, §3.5, §4.2).

Pairing is positional: the i-th source value is mapped to the i-th target attribute.
Identity and ValueMap are executed. An Expression is executed if its language is on the allowlist
of the receiver, otherwise it is handed to the asset maintainer like an Instruction, which is never
executed and writes nothing.

Expressions are data, never code: they are evaluated by an interpreter for a side-effect-free
expression language. CEL (Common Expression Language) terminates on every input and has no access
to anything but the values it is given; cel-python is used with its interpreting runner, which
does not generate Python code. The expression sees the source values as the list `src` and yields
the target value (one target) or the list of target values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import celpy

from tcn.core.model import LAMBDA

CEL = "https://github.com/google/cel-spec"
ALLOWLIST = {CEL}  # expression languages this receiver evaluates
MAX_EXPRESSION_LENGTH = 2000


@dataclass(frozen=True)
class Identity:
    kind = "Identity"
    executable = True

    def defined(self, values: list[Any]) -> bool:
        return True

    def __call__(self, values: list[Any]) -> list[Any]:
        return list(values)


@dataclass(frozen=True)
class ValueMap:
    pairs: dict[str, str]
    kind = "ValueMap"
    executable = True

    def defined(self, values: list[Any]) -> bool:
        # f must be total on value[X_src]; an unpopulated source maps to an unpopulated target.
        return all(v is LAMBDA or (isinstance(v, str) and v in self.pairs) for v in values)

    def __call__(self, values: list[Any]) -> list[Any]:
        return [v if v is LAMBDA else self.pairs[v] for v in values]


@dataclass(frozen=True)
class Expression:
    language: str
    expression: str
    text: dict[str, str] = field(default_factory=dict)  # instruction for receivers without the language
    kind = "Expression"

    @property
    def executable(self) -> bool:
        return self.language in ALLOWLIST and len(self.expression) <= MAX_EXPRESSION_LENGTH

    def _evaluate(self, values: list[Any]) -> Any:
        env = celpy.Environment(runner_class=celpy.InterpretedRunner)
        result = env.program(env.compile(self.expression)).evaluate(
            {"src": celpy.json_to_cel([None if v is LAMBDA else v for v in values])})
        if isinstance(result, celpy.CELEvalError):
            raise result
        return _to_json(result)

    def defined(self, values: list[Any]) -> bool:
        try:
            self._evaluate(values)
            return True
        except Exception:  # any failure to compile or evaluate: f is not defined on these values
            return False

    def __call__(self, values: list[Any]) -> list[Any]:
        result = self._evaluate(values)
        return result if isinstance(result, list) else [result]


def _to_json(value: Any) -> Any:
    """CEL values (subclasses of the Python types) as plain JSON values."""
    if isinstance(value, dict):
        return {str(k): _to_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json(v) for v in value]
    if isinstance(value, celpy.celtypes.BoolType):  # a subclass of int in cel-python
        return bool(value)
    for t in (bool, int, float, str):
        if isinstance(value, t):
            return t(value)
    return value


@dataclass(frozen=True)
class Instruction:
    text: dict[str, str] = field(default_factory=dict)  # language -> text
    kind = "Instruction"
    executable = False


TransferFunction = Identity | ValueMap | Expression | Instruction
