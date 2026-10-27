"""A map or an outline said as a hierarchy (composer work list 2).

A mind map arrives as an indented list: "Service models" with IaaS, PaaS and
SaaS under it. Read flat, the four come out as siblings ("lists four: service
models, IaaS, PaaS and SaaS"). Here the nesting the person drew is kept: the
parent leads and its children follow it, "Service models: IaaS, PaaS and
SaaS". Every part is a quote of one entry or a fixed phrase, as elsewhere in
the composer; nothing is added to what the entries say."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: A parent's children read as one phrase up to this many, each this short;
#: past that they are shown as sub-bullets.
KIDS_INLINE = 6
KID_WORDS = 10


@dataclass
class Node:
    head: object  # a composer.Sentence
    kids: list[Node] = field(default_factory=list)


def nested(items: list) -> bool:
    """Whether any entry sits under another."""
    return any(getattr(s, "depth", 0) for s in items)


def nest(items: list) -> list[Node]:
    """The entries as a forest, by their indent: an entry belongs to the
    nearest one before it that is less indented."""
    roots: list[Node] = []
    stack: list[tuple[int, Node]] = []
    for s in items:
        node = Node(s)
        depth = getattr(s, "depth", 0)
        while stack and stack[-1][0] >= depth:
            stack.pop()
        (stack[-1][1].kids if stack else roots).append(node)
        stack.append((depth, node))
    return roots


def _phrase(node: Node) -> bool:
    text = node.head.text
    return not node.kids and len(text.split()) <= KID_WORDS and not re.search(r"[.!?:;]\s*$|:\s", text)


def _inline(node: Node) -> bool:
    """A parent whose children are few short phrases."""
    return 1 <= len(node.kids) <= KIDS_INLINE and all(_phrase(k) for k in node.kids)


def _kids_sentence(out, node: Node, terms: list[str]) -> None:  # noqa: ANN001
    """"IaaS, PaaS and SaaS", the children as the person wrote them."""
    for i, kid in enumerate(node.kids):
        if i:
            out.t("and" if i == len(node.kids) - 1 else "comma")
        out.q(kid.head, terms)


def _inline_line(out, node: Node, terms: list[str]) -> None:  # noqa: ANN001
    """"Service models: IaaS, PaaS and SaaS", or the entry alone."""
    out.q(node.head, terms)
    if node.kids:
        out.t("colon")
        _kids_sentence(out, node, terms)


def _bullet(out, node: Node, terms: list[str], depth: int) -> None:  # noqa: ANN001
    for _ in range(depth):
        out.t("indent")
    out.t("bullet")
    if not node.kids or _inline(node):
        _inline_line(out, node, terms)
        return
    out.q(node.head, terms)
    out.t("colon")
    for kid in node.kids:
        out.t("line")
        _bullet(out, kid, terms, depth + 1)


def write(out, items: list, terms: list[str]) -> None:  # noqa: ANN001
    """The entries as a hierarchy, after the opener ("Your mind map **X**
    lists "): one parent with a few children is one sentence; anything more
    is a count and a bulleted tree."""
    roots = nest(items)
    if len(roots) == 1 and _inline(roots[0]):
        _inline_line(out, roots[0], terms)
        out.t("stop")
        return
    out.m(f"{out.count(len(roots))} {'topic' if len(roots) == 1 else 'topics'}")
    out.t("end_colon", "para")
    for i, root in enumerate(roots):
        if i:
            out.t("line")
        _bullet(out, root, terms, 0)
