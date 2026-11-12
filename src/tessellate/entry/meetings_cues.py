"""Decision and action cue words beyond English (L665): a small table per language
for the Latin-script languages the app already tells apart (`ai/note_language`:
French, Spanish, German, Italian, Portuguese, Dutch).

`meetings.py` reads a minute with English rules; the table here adds, per language,
the four things those rules are made of: the word that marks a line as an action,
the words that say a thing was decided, the words that say it was not, and the
modal that a named person takes a task on with. Decision and mark cues are phrases
that are rare outside a minute, so they apply to every note. A modal alone is
common ("wird", "va"), so a name taking a task on with it counts only when the name
is one of the meeting's attendees (or an @mention), never any capitalised word."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Cues:
    mark: str      # "Acción:", "À faire:" ... at the line start
    decided: str   # a sentence saying it was decided or agreed
    undecided: str  # a sentence saying it was not, or is open
    commit: str    # what a named person takes a task on with


CUES: dict[str, Cues] = {
    "spanish": Cues(
        r"acci[oó]n|tarea|pendiente|por hacer|siguiente paso|seguimiento",
        r"decidimos|decidido|se decidi[oó]|acordamos|acordado|se acord[oó]|aprobado|aprobamos|resolvimos|la decisi[oó]n es|el plan es|vamos a ir con",
        r"(?:no|nadie|a[uú]n no|todav[ií]a no)\s+(?:se\s+)?(?:ha\s+|hemos\s+)?(?:decidid[oa]|acordad[oa]|decidimos|acordamos|resuelt[oa])|sin decidir|pendiente de decidir",
        r"har[aá]|va a|debe|tiene que|se encargar[aá] de|se ocupar[aá] de|deber[aá]",
    ),
    "french": Cues(
        r"action|t[aâ]che|[aà] faire|prochaine [eé]tape|suivi",
        r"nous avons d[eé]cid[eé]|on a d[eé]cid[eé]|d[eé]cid[eé]|d[eé]cision|convenu|nous avons convenu|on a convenu|approuv[eé]|valid[eé]|le plan est|on part sur",
        r"(?:pas|jamais|personne n'a|rien n'a)\s+(?:\w+\s+){0,3}(?:d[eé]cid[eé]|convenu|valid[eé]|approuv[eé])|reste [aà] d[eé]cider|non d[eé]cid[eé]",
        r"va|doit|devra|s'occupe de|se charge de|fera|prendra en charge",
    ),
    "german": Cues(
        r"aktion|aufgabe|zu erledigen|offen|n[aä]chster schritt|nachfassen|todo",
        r"beschlossen|beschlie[sß]en|haben beschlossen|wurde beschlossen|entschieden|wir haben uns entschieden|vereinbart|einigten uns|genehmigt|der plan ist|wir machen",
        r"(?:nicht|noch nicht|nie|niemand hat)\s+(?:\w+\s+){0,3}(?:beschlossen|entschieden|vereinbart|genehmigt)|noch offen|unentschieden|ungekl[aä]rt",
        r"wird|muss|soll|[uü]bernimmt|k[uü]mmert sich um|sollte",
    ),
    "italian": Cues(
        r"azione|compito|da fare|prossimo passo|seguito",
        r"abbiamo deciso|deciso|si [eè] deciso|concordato|abbiamo concordato|approvato|risolto|la decisione [eè]|il piano [eè]|andiamo con",
        r"(?:non|mai|nessuno ha)\s+(?:\w+\s+){0,3}(?:deciso|concordato|approvato|risolto)|ancora da decidere|indeciso",
        r"far[aà]|deve|dovr[aà]|si occupa di|si occuper[aà] di|prender[aà] in carico",
    ),
    "portuguese": Cues(
        r"a[cç][aã]o|tarefa|a fazer|pr[oó]ximo passo|acompanhamento|pendente",
        r"decidimos|decidido|ficou decidido|acordamos|acordado|ficou acordado|aprovado|resolvemos|a decis[aã]o [eé]|o plano [eé]|vamos com",
        r"(?:n[aã]o|ningu[eé]m|ainda n[aã]o)\s+(?:foi\s+|ficou\s+)?(?:decidid[oa]|acordad[oa]|aprovad[oa]|resolvid[oa])|por decidir|em aberto",
        r"vai|deve|far[aá]|ficou de|fica respons[aá]vel por|precisa de",
    ),
    "dutch": Cues(
        r"actie|actiepunt|taak|te doen|volgende stap|opvolging",
        r"besloten|we hebben besloten|er is besloten|afgesproken|we hebben afgesproken|goedgekeurd|beslist|het plan is|we gaan voor",
        r"(?:niet|nog niet|nooit|niemand heeft)\s+(?:\w+\s+){0,3}(?:besloten|afgesproken|goedgekeurd|beslist)|nog open|onbeslist",
        r"gaat|moet|zal|neemt|pakt|regelt",
    ),
}


def _any(field: str) -> str:
    return "|".join(getattr(c, field) for c in CUES.values())


#: Compiled once: a minute may be in any of them, and these phrases are not
#: words an English minute uses.
MARK = re.compile(rf"^(?:{_any('mark')})[ \t]*[:\-][ \t]*", re.I)
DECIDED = re.compile(rf"\b(?:{_any('decided')})\b", re.I)
UNDECIDED = re.compile(rf"\b(?:{_any('undecided')})\b", re.I)
#: "Sam va a enviar", "Anna wird senden": a capitalised first word then the modal.
_COMMIT = rf"(?i:{_any('commit')})\b"
SUBJECT = re.compile(rf"^@?([A-ZÀ-Ý][a-zà-ÿ]+)(?:[ \t]+[A-ZÀ-Ý][a-zà-ÿ]+)?[ \t]+{_COMMIT}")
