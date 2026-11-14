"""Plain arithmetic for the composer: "what is 12 * (3 + 4)?".

Our own, in place of the vendored simpleeval the Gemini branch brought in
(2026-10-10 triage, decision 1): a question is untrusted text, so the grammar
is the smallest that answers it. Numbers, + - * / ** %, parentheses and a
leading minus; anything else (a name, a call, an attribute, a comparison) is
refused by the parser, never evaluated. Python's `ast` does the parsing, so
there is no hand-written tokeniser to get wrong; only the node types below
are walked.

Bounded as well as narrow: `2 ** 99999999` is valid arithmetic and would hold
the request thread for minutes, so an exponent over `MAX_EXPONENT` or an
answer over `MAX_MAGNITUDE` is refused rather than computed.
"""

from __future__ import annotations

import ast
import operator
import re
from tessellate.core.lazyre import lazy_compile

MAX_EXPONENT = 100
MAX_MAGNITUDE = 1e15
MAX_CHARS = 80

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

#: What a question may hold around the sum: "what is", "calculate", a "?".
#: "x" and "×" are read as times, "÷" as divided by, "^" as a power.
#: The trailing "?", "=" and "." come off in `sum_in`: a lazy `.+?` before
#: `\s*[?=.]*\s*$` was quadratic on a run of whitespace (CodeQL).
_ASK = lazy_compile(r"^\s*(?:what(?:'?s| is)|calculate|compute|work out)\s+(?P<expr>\S.*)$", re.I)
_ALLOWED = lazy_compile(r"^[\d\s.+\-*/%()^x×÷]+$")
#: "1,000" is a thousand: a comma between a digit and three more is grouping (L-chat-22).
_GROUPED = lazy_compile(r"(?<=\d),(?=\d{3}(?!\d))")


class NotArithmetic(ValueError):
    """The text is not a sum this module will work out."""


def _walk(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _walk(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _walk(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _walk(node.left), _walk(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise NotArithmetic("exponent too large")
        try:
            value = _BINARY[type(node.op)](left, right)
        except (ZeroDivisionError, OverflowError) as exc:
            raise NotArithmetic(str(exc)) from exc
        if isinstance(value, complex) or abs(value) > MAX_MAGNITUDE:
            raise NotArithmetic("answer out of range")
        return value
    raise NotArithmetic(f"{type(node).__name__} is not arithmetic")


def evaluate(expression: str) -> float:
    """The value of `expression`, or `NotArithmetic`."""
    text = _GROUPED.sub("", (expression or "").strip())
    if not text or len(text) > MAX_CHARS or not _ALLOWED.match(text):
        raise NotArithmetic("not a sum")
    text = text.replace("×", "*").replace("x", "*").replace("÷", "/").replace("^", "**")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise NotArithmetic("not a sum") from exc
    if not any(isinstance(node, ast.BinOp) for node in ast.walk(tree)):
        raise NotArithmetic("a number on its own is not a sum")
    return _walk(tree)


#: A sum typed bare ("5 + 5", INBOX 801: it got "None of my tools fits
#: that") needs an operator no date or code uses: `+ * x × ÷ ^ %`, or a minus
#: or a slash with a space on each side. "2024-10-11" and "10/11" are dates.
_BARE_OPERATOR = lazy_compile(r"[+*x×÷^%]|\s[-/]\s")


def sum_in(question: str) -> str | None:
    """The sum a question asks for ("what is 2 + 2?" gives "2 + 2", and "5 + 5"
    on its own gives "5 + 5"), or None when the question is not only a sum."""
    match = _ASK.match(question or "")
    if match:
        expr = match.group("expr")
    elif _BARE_OPERATOR.search(question or ""):
        expr = (question or "").strip()
    else:
        return None
    expr = expr.rstrip(" \t?=.")
    try:
        evaluate(expr)
    except NotArithmetic:
        return None
    return expr


def spoken(value: float) -> str:
    """12.0 as "12", 0.1 + 0.2 as "0.3", a long fraction to six places."""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{round(value, 6):,}".rstrip("0").rstrip(".")
