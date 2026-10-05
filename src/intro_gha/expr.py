"""A mini evaluator for GitHub Actions expressions (the text inside ``${{ }}``).

It implements the rules observed from real runs (``fixtures/ctx_ch07_*.json``) and
documented by GitHub (verified 2026-10):

- Types: null, boolean, number, string, array, object. There is **no arithmetic**.
- Falsy values: ``false``, ``0``, ``-0``, ``''``, ``null`` (and NaN). Everything else is
  truthy, **including the strings ``'false'`` and ``'0'``**.
- ``==`` / ``!=`` / ``<`` ... coerce mismatched types to numbers (null -> 0, true -> 1,
  numeric string -> its number, other string -> NaN). Two strings compare
  case-insensitively (and ``<``/``>`` compare them lexicographically).
- ``&&`` returns the first falsy operand, else the last; ``||`` the first truthy, else
  the last; ``!`` returns a boolean.
- Functions: contains, startsWith, endsWith, format, join, toJSON, fromJSON, hashFiles.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

Value = Any
TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<str>'(?:[^']|'')*')|(?P<id>[A-Za-z_][\w-]*)"
    r"|(?P<op>==|!=|<=|>=|&&|\|\||[<>!().,\[\]*]))"
)


class ExprError(ValueError):
    """Raised for syntax errors, e.g. arithmetic, which GitHub expressions lack."""


def truthy(v: Value) -> bool:
    """GitHub truthiness: false, 0, -0, '', null and NaN are falsy; all else truthy."""
    if v is None or v is False or v == "":
        return False
    return not (isinstance(v, float) and (v == 0 or math.isnan(v)))


def to_number(v: Value) -> float:
    """Coerce for comparison: null 0, bool 0/1, numeric string its value, else NaN."""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        if v.strip() == "":
            return 0.0
        try:
            return float(v)
        except ValueError:
            return math.nan
    return math.nan


def _cmp_operands(a: Value, b: Value) -> tuple[Any, Any]:
    """Return comparable operands: two lowercase strings, or two numbers."""
    if isinstance(a, str) and isinstance(b, str):
        return a.lower(), b.lower()
    return to_number(a), to_number(b)


def loose_eq(a: Value, b: Value) -> bool:
    """Loose equality (case-insensitive strings, numeric coercion otherwise)."""
    x, y = _cmp_operands(a, b)
    return x == y


def stringify(v: Value) -> str:
    """Render a value the way ``${{ }}`` interpolates it into text."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return str(v)


def _contains(search: Value, item: Value) -> bool:
    """``contains``: case-insensitive substring, or loose membership for arrays."""
    if isinstance(search, list):
        return any(loose_eq(x, item) for x in search)
    return stringify(item).lower() in stringify(search).lower()


def _format(fmt: str, *args: Value) -> str:
    """``format``: replace ``{N}``; ``{{`` and ``}}`` are literal braces."""
    out = fmt.replace("{{", "\0").replace("}}", "\1")
    out = re.sub(r"\{(\d+)\}", lambda m: stringify(args[int(m[1])]), out)
    return out.replace("\0", "{").replace("\1", "}")


def _hash_files(*patterns: str, root: Path | None = None) -> str:
    """``hashFiles`` for the single-file case: sha256 of the file's sha256 digest."""
    base = root or Path.cwd()
    files = sorted(f for p in patterns for f in base.glob(p) if f.is_file())
    if not files:
        return ""
    outer = hashlib.sha256()
    for f in files:
        outer.update(hashlib.sha256(f.read_bytes()).digest())
    return outer.hexdigest()


FUNCS = {
    "contains": _contains,
    "startsWith": lambda s, p: stringify(s).lower().startswith(stringify(p).lower()),
    "endsWith": lambda s, p: stringify(s).lower().endswith(stringify(p).lower()),
    "format": _format,
    "join": lambda a, sep=",": stringify(sep).join(stringify(x) for x in a),
    "toJSON": lambda v: json.dumps(v, indent=2),
    "fromJSON": lambda s: _to_float(json.loads(s)),
    "hashFiles": _hash_files,
}


def _to_float(v: Value) -> Value:
    """GitHub numbers are doubles; keep booleans, convert ints."""
    if isinstance(v, bool) or not isinstance(v, int):
        return v
    return float(v)


class _Parser:
    """Recursive-descent evaluator. Precedence: ! > < > > == > && > ||."""

    def __init__(self, text: str, contexts: dict[str, Any]) -> None:
        """Tokenize ``text`` eagerly; raise ExprError on any unexpected character."""
        self.ctx = contexts
        self.toks: list[tuple[str, str]] = []
        pos = 0
        text = text.strip()
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m or m.end() == pos:
                raise ExprError(f"unexpected character {text[pos:pos + 1]!r}")
            kind = m.lastgroup or ""
            self.toks.append((kind, m.group(kind)))
            pos = m.end()
        self.i = 0

    def peek(self) -> str | None:
        """Next token's text, or None at the end."""
        return self.toks[self.i][1] if self.i < len(self.toks) else None

    def take(self) -> tuple[str, str]:
        """Consume and return the next token."""
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def parse(self) -> Value:
        """Evaluate the whole expression."""
        v = self.or_()
        if self.i != len(self.toks):
            raise ExprError(f"unexpected token {self.peek()!r}")
        return v

    def or_(self) -> Value:
        """``a || b || c``: first truthy operand, else the last."""
        v = self.and_()
        while self.peek() == "||":
            self.take()
            rhs = self.and_()
            v = v if truthy(v) else rhs
        return v

    def and_(self) -> Value:
        """``a && b && c``: first falsy operand, else the last."""
        v = self.eq()
        while self.peek() == "&&":
            self.take()
            rhs = self.eq()
            v = rhs if truthy(v) else v
        return v

    def eq(self) -> Value:
        """``==`` and ``!=``."""
        v = self.cmp()
        while self.peek() in ("==", "!="):
            op = self.take()[1]
            rhs = self.cmp()
            v = loose_eq(v, rhs) if op == "==" else not loose_eq(v, rhs)
        return v

    def cmp(self) -> Value:
        """``<``, ``<=``, ``>``, ``>=`` after type coercion."""
        v = self.unary()
        while self.peek() in ("<", "<=", ">", ">="):
            op = self.take()[1]
            x, y = _cmp_operands(v, self.unary())
            v = {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op]
        return v

    def unary(self) -> Value:
        """``!x`` returns a boolean."""
        if self.peek() == "!":
            self.take()
            return not truthy(self.unary())
        return self.primary()

    def primary(self) -> Value:
        """Literal, parenthesized expression, function call or context lookup."""
        kind, text = self.take()
        if kind == "num":
            return float(text)
        if kind == "str":
            return text[1:-1].replace("''", "'")
        if text == "(":
            v = self.or_()
            self.take()
            return v
        if kind != "id":
            raise ExprError(f"unexpected token {text!r}")
        if text in ("true", "false", "null"):
            return {"true": True, "false": False, "null": None}[text]
        if self.peek() == "(":
            return self.call(text)
        v: Value = self.ctx.get(text)
        while self.peek() in (".", "["):
            if self.take()[1] == ".":
                key = self.take()[1]
            else:
                key = stringify(self.or_())
                self.take()
            v = v.get(key) if isinstance(v, dict) else None
        return v

    def call(self, name: str) -> Value:
        """Parse arguments and call a built-in function."""
        if name not in FUNCS:
            raise ExprError(f"unknown function {name!r}")
        self.take()  # (
        args: list[Value] = []
        while self.peek() != ")":
            args.append(self.or_())
            if self.peek() == ",":
                self.take()
        self.take()  # )
        return FUNCS[name](*args)


def evaluate(expression: str, contexts: dict[str, Any]) -> Value:
    """Evaluate ``expression`` (without the ``${{ }}`` wrapper) against ``contexts``."""
    return _Parser(expression, contexts).parse()
