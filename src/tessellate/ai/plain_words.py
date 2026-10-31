"""Words that say nothing about what a note is about (notes audit 1031, N33).

The no-model filer cited "note", "one" and "two" as the telling words that
filed a note, and the statistics page counted the same words as the most
written-about. One list, so the filer, the statistics and anything else that
asks "is this word telling" agree.
"""

from __future__ import annotations

PLAIN: frozenset[str] = frozenset(
    """
    a about after again all also am an and any are as at be because been before being
    but by can cant could did didnt do does doing done dont eight five for four from get
    go got had has have having he her here him his how i if im in into is it its ive
    just like made make me more most my need nine no not note notes now of off ok okay
    on once one only or other our out over own really same seven she should six so some
    still such ten than that thats the their them then there these they thing things
    this those three through to today tomorrow too two up us very was we went were what
    when where which while who why will with wont would yes yesterday you your
    """.split()
)
