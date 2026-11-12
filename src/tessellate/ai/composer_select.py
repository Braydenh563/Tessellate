"""Choosing what to quote: each sentence scored against the question
(`select`), sentences grouped by meaning (`_Meaning`), the one the others
lean towards (`centrality`) and two that may disagree.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.select` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import contextvars
import functools
import math
import re
from collections import Counter

from tessellate.ai import realise
from tessellate.ai.composer_ask import SYNONYM_WEIGHT, _alternatives, _holds, _stem, _words
from tessellate.ai.composer_read import NoteView, Sentence, _cue
from tessellate.core.lazyre import lazy_compile


#: At most this many quoted points in one answer. Six is about what reads as an
#: answer: past that it is a list of search results, and the Sources panel
#: under the answer already is one.
MAX_POINTS = 6


#: At most this many sentences from one note, so one long note cannot fill the
#: answer and push out a second note that says something different.
MAX_PER_NOTE = 3


#: A sentence scoring under this share of the best one is not in the same
#: league (the reasoning of `extractive.RELATIVE_FLOOR`: BM25 magnitudes move
#: with the pool, so only a ratio survives a different notebook).
RELATIVE_FLOOR = 0.3


#: What a question word found in a note's heading is worth, per word, and once
#: more when the heading holds every one of them: "Harbor launch plan" is the
#: note about the Harbor launch plan, whatever its sentences repeat.
TITLE_WEIGHT = 1.0


#: A note holding no more than this share of the question's words is about
#: something else that shares a word with it ("active" in a note about
#: reading, asked "how many beta testers are active"; the onboarding rewrite,
#: asked about the sync rewrite). Measured per note, over its words and its
#: heading, and only when the question has two words or more.
NOTE_COVERAGE = 0.5


#: A question word among a note's tags or its category, per word: half a
#: heading's worth, since a tag says what a note is about less precisely.
FILED_WEIGHT = 0.5


#: Two sentences sharing this share of their words say the same thing; the
#: second is dropped. Token Jaccard, because it needs no model.
NEAR_DUPLICATE = 0.6


#: Words that say what kind of note is asked for, not which one ("the gear
#: list"): beside a word that names the subject they count a quarter, so a
#: note that only has "list" in its text or title does not outrank the note
#: called Gear.
KIND_WORDS = frozenset({"list", "checklist"})


KIND_WORD_WEIGHT = 0.25


#: Words that say when a thing happens, not what it is: beside a subject they
#: count as little as a kind word, so "when are the designs coming" is
#: answered by the designs, not by the plumber who is coming Thursday, and
#: "when is the beta due" by the beta, not the car's service that is due
#: (2026-10-30 sweep).
TIMING_WORDS = frozenset(
    "due come coming comes arrive arrives arriving arrival start starts starting begin begins beginning".split()
)


@functools.cache
def _timing_stems() -> frozenset[str]:
    return frozenset(_stem(w) for w in TIMING_WORDS)


#: Everyday verbs say what was done, not to what: beside a noun they count
#: as little as a timing word ("how did we meet the plumber" is the plumber's
#: note, not "We meet on Thursdays"; CHAT_PLAN, placed 2026-10-30, item 2).
COMMON_VERBS = frozenset(
    "meet met go went get got make made know knew see saw come came take took think say said tell told find found give gave "
    "use work call try ask need feel leave left keep kept start begin began show hear heard play run move live bring brought "
    "happen write wrote sit stand lose lost pay paid speak spoke read spend spent".split()
)


@functools.lru_cache(maxsize=1)
def _verb_stems() -> frozenset[str]:
    return frozenset(_stem(w) for w in COMMON_VERBS)


def _term_weights(stems: list[str]) -> dict[str, float]:
    """What each term of the question counts for: a kind or timing word beside
    others counts `KIND_WORD_WEIGHT`, any other word, or one alone, 1."""
    light = KIND_WORDS | _timing_stems() | _verb_stems()
    named = [t for t in stems if t not in light]
    return {t: KIND_WORD_WEIGHT if named and t in light else 1.0 for t in stems}


def _heading_hits(view: NoteView, stems: list[str], term_weight: dict[str, float]) -> tuple[float, float]:
    """The weight of the question's terms in the note's title, and in its
    category and tags but not its title."""
    title = sum(term_weight[term] for term in stems if _holds(term, view.title_words))
    filed = sum(term_weight[term] for term in stems if _holds(term, view.filed_words) and not _holds(term, view.title_words))
    return title, filed


#: Words a note uses when it changes what an older one said: "Moved the
#: dentist appointment from 3 November to 4 November", "These replace the
#: dates from 6 October".
CORRECTS = lazy_compile(
    r"\b(?:moved|rescheduled|postponed|slips?|slipped|slipping|pushed\s+back|delayed|brought\s+forward|changed|revised|replaces?|replaced|instead\s+of|cancel+ed|no\s+longer|new\s+plan|dropped|is\s+now|are\s+now)\b",
    re.I,
)


def correcting(terms: list[str], views: list) -> list:
    """The dated views with a sentence that changes something about the
    subject ("Sam moved the launch to 27 November")."""
    return [
        v for v in views
        if v.written and any(CORRECTS.search(x.text) and any(_holds(t, set(_words(x.text))) for t in terms) for x in v.sentences)
    ]


def superseded(terms: list[str], views: list) -> set[int]:
    """The ids of the views on the subject that a newer correcting view
    outdates: the digest and the plain composer both rank them below it
    (stress run 2026-10-30: "when's the dentist now" quoted the first booking
    whenever the digest stood down)."""
    newest = max((v.written for v in correcting(terms, views)), default=None)
    if not newest:
        return set()
    return {id(v) for v in views if v.written and v.written < newest and any(_holds(_stem(t), v.words | v.title_words) for t in terms)}


def _score(shape: str, terms: list[str], views: list[NoteView], *, carrier: bool = False) -> list[Sentence]:
    """Every sentence scored: BM25 over the sentences of the notes found, plus
    the note's title, the question's shape and the note's retrieval rank.

    BM25 across sentences rather than within one note (`grounding.best_passage`
    asks the second question): here the question is "which of everything found
    answers this", so a word every candidate shares ("harbor" in nine Harbor
    notes) says little and a rare one says a lot.
    """
    pool = [s for view in views for s in view.sentences]
    if not pool:
        return []
    scorer = _Scorer(shape, terms, views, pool, carrier)
    for s in pool:
        s.score = scorer.score(s)
    return [s for s in pool if s.score > 0]


class _Scorer:
    """What scoring one question's sentences needs, worked out once: the
    stemmed terms and their weights, each term's words (itself and its
    synonyms), how many sentences hold each word, the notes' recency and the
    notes a newer one corrects. `score` is then one sentence's number."""

    def __init__(self, shape: str, terms: list[str], views: list[NoteView], pool: list[Sentence], carrier: bool = False) -> None:
        self.shape = shape
        #: The model's brief: a title's weight goes only to the sentences that carry its words (L500).
        self.carrier = carrier
        self.stems = [_stem(t) for t in terms]
        self.term_weight = _term_weights(self.stems)
        self.whole_title = sum(self.term_weight[term] for term in self.stems)
        self.forms = [((term, 1.0), *((alt, SYNONYM_WEIGHT) for alt in _alternatives(term))) for term in self.stems]
        self.frequency: Counter[str] = Counter()
        for s in pool:
            self.frequency.update(set(s.words))
        self.total = len(pool)
        self.average = sum(len(s.words) for s in pool) / self.total
        self.idf: dict[str, float] = {}
        self.by_id = {view.id: view for view in views}
        self.headings: dict[int, tuple[float, float]] = {}
        self.carriers: dict[int, bool] = {}
        self.outdated = _outdated(terms, views)
        dated = sorted((v for v in views if v.written), key=lambda v: v.written, reverse=True)
        self.recency = {v.id: 1.0 - i / max(1, len(dated)) for i, v in enumerate(dated)}

    def _idf(self, word: str) -> float:
        idf = self.idf.get(word)
        if idf is None:
            n = self.frequency[word]
            idf = self.idf[word] = math.log(1 + (self.total - n + 0.5) / (n + 0.5))
        return idf

    def bm25(self, s: Sentence) -> float:
        """Each term's best form (itself, or a synonym at `SYNONYM_WEIGHT`), summed by the term's weight."""
        counts = Counter(s.words)
        length = 0.25 + 0.75 * len(s.words) / self.average
        total = 0.0
        for term, forms in zip(self.stems, self.forms):
            best = 0.0
            for word, weight in forms:
                tf = counts.get(word, 0)
                if tf:
                    best = max(best, weight * self._idf(word) * tf * 2.2 / (tf + 1.2 * length))
            total += best * self.term_weight[term]
        return total

    def _carries(self, view: NoteView) -> bool:
        """Whether some sentence of the note holds a question word that is also in its title."""
        found = self.carriers.get(view.id)
        if found is None:
            found = self.carriers[view.id] = any(
                _holds(t, view.title_words) and _holds(t, set(x.words)) for x in view.sentences for t in self.stems
            )
        return found

    def relevance(self, s: Sentence, view: NoteView) -> float:
        """BM25 plus the note's headings. A sentence under a heading that
        names the subject is about it even when it does not repeat the words:
        "It was not the database." is the answer to "why did the list feel
        slow" because its note is called "Why the list felt slow"."""
        hits = self.headings.get(view.id)
        if hits is None:
            hits = self.headings[view.id] = _heading_hits(view, self.stems, self.term_weight)
        title_hits, filed_hits = hits
        whole = bool(self.stems) and title_hits == self.whole_title
        if self.carrier and title_hits and self._carries(view):
            #: The model's brief: only the sentence that says the title's words takes the weight, so a
            #: titled note's every sentence does not outrank an untitled note's best one (L500). A note
            #: no sentence of which says them keeps the weight on all, or the brief would drop it.
            own = set(s.words)
            title_hits = sum(self.term_weight[t] for t in self.stems if _holds(t, view.title_words) and _holds(t, own))
            whole = whole and title_hits == self.whole_title
        relevance = self.bm25(s) + TITLE_WEIGHT * title_hits + FILED_WEIGHT * filed_hits
        if whole:
            relevance += TITLE_WEIGHT
        return relevance

    def score(self, s: Sentence) -> float:
        view = self.by_id[s.note_id]
        relevance = self.relevance(s, view)
        if self.stems and relevance <= 0:
            return 0.0
        cue = _cue(self.shape, s.text)
        score = relevance + cue + 0.4 / (1 + s.rank)
        #: A sentence that only names the subject ("Store listing copy", a
        #: task on someone's checklist) says nothing about it: measured on
        #: the voice eval, it led "what did I decide about the store
        #: listing" over the note called "Store listing". Not one that has
        #: what the shape asks for ("Due in March." for a "when is it due",
        #: which the blind panel found left out).
        if not cue and len(self.stems) >= 2 and len([w for w in s.words if w not in self.stems]) <= 1:
            score *= 0.5
        if self.shape == "status":
            score += self.recency.get(s.note_id, 0.0)
        return score * _view_factor(view, self.outdated)


def _outdated(terms: list[str], views: list[NoteView]) -> set[int]:
    return superseded(terms, views) if _ASKS_NOW.get() else set()


def _view_factor(view: NoteView, outdated: set[int]) -> float:
    """A connected note counts less than one found, and a note a newer one
    corrects less than the correction."""
    return (0.7 if view.note.get("connected") else 1.0) * (0.5 if id(view) in outdated else 1.0)


def _was_said(s: Sentence, said: str) -> bool:
    """Whether an earlier answer (`said`) quoted `s`, as written or said back
    shifted ("you went" for "I went", decision 33)."""
    if not said:
        return False
    flat = " ".join(said.split()).lower()
    if s.text.rstrip("…").lower() in flat or realise.shift_person(s.text).rstrip("…").lower() in flat:
        return True
    #: Said back reworded (the digest's "From your psych lecture note, 21
    #: September: memory is ...", B8): nearly every word of it is there.
    words = [w for w in re.findall(r"[a-z0-9']+", s.text.lower()) if len(w) >= 2]
    heard = set(re.findall(r"[a-z0-9']+", flat))
    return len(words) >= 4 and sum(w in heard for w in words) / len(words) >= 0.85


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def select(
    shape: str,
    terms: list[str],
    views: list[NoteView],
    limit: int = MAX_POINTS,
    *,
    meaning: "_Meaning | None" = None,
    per_note: int = MAX_PER_NOTE,
    said: str = "",
    carrier: bool = False,
) -> list[Sentence]:
    """The sentences worth quoting, best first: over the floor, no two saying
    the same thing, no more than `per_note` from one note.

    A sentence that says what a chosen one already says is not quoted again;
    it is kept on the chosen one as an echo, so the answer can say how many
    notes say it. `said` is an earlier answer's text ("tell me more"): a
    sentence it already quoted is left for something new."""
    stems = {_stem(t) for t in terms}
    if len(stems) >= 2:
        covering = [
            v for v in views
            if sum(1 for t in stems if _holds(t, v.words | v.title_words | v.filed_words)) / len(stems) > NOTE_COVERAGE
        ]
        #: None covering is a question the notes only half answer: every note
        #: stays in, and the closing line says which words none of them hold.
        views = covering or views
    scored = sorted(_score(shape, terms, views, carrier=carrier), key=lambda s: (-s.score, s.rank, s.order))
    if said:
        scored = [s for s in scored if not _was_said(s, said)]
    if not scored:
        return []
    meaning = meaning or _Meaning(scored[:MEANING_POOL], None)
    floor = scored[0].score * RELATIVE_FLOOR
    chosen: list[Sentence] = []
    counts: Counter[int] = Counter()
    for s in scored:
        if s.score < floor:
            break
        s.echoes = []
        #: Two that differ in a figure or a "not" are not one claim twice,
        #: however many words they share: that is a disagreement, said as one.
        twin = next((c for c in chosen if meaning.same(s, c) and not disagree(s, c)), None)
        if twin is not None:
            if s.note_id != twin.note_id and s.note_id not in {e.note_id for e in twin.echoes}:
                twin.echoes.append(s)
            continue
        if len(chosen) >= limit or counts[s.note_id] >= per_note:
            continue
        chosen.append(s)
        counts[s.note_id] += 1
    return chosen


# --- meaning ----------------------------------------------------------------------

#: How many of the best sentences are compared by meaning: the ones an answer
#: can quote, with room for the echoes beside them. One batch to the embedder.
MEANING_POOL = 24


#: Two sentences this alike say the same thing (cosine over the embedder's
#: vectors). Above the paraphrase line of the small sentence models, below
#: the near-identical: "The launch is on the 14th" and "We launch on the
#: 14th" are one claim, said twice.
SAME_COSINE = 0.9


#: ...and share at least this much of their words (token Jaccard over stems):
#: "The launch is on the 14th" and "We launch on the 14th" share 0.67.
SAME_WORDS = 0.34


#: Two sentences this alike are about the same thing, the line between
#: "also" and "separately" (cosine, then token Jaccard over the words that are
#: not the question's own, which every candidate shares).
TOPIC_COSINE = 0.55


TOPIC_JACCARD = 0.12


class _Meaning:
    """How alike two sentences are: cosine over the embedder's vectors when it
    gave them (`compose(embed=...)`), token Jaccard when it did not.

    The embedder is optional by decision (INBOX 725): an answer composed with
    no model running at all still has to read well, so every use of meaning
    here has a lexical twin, measured on the showcase eval with no vectors.
    """

    def __init__(self, sentences: list[Sentence], embed, subject: set[str] | None = None) -> None:  # noqa: ANN001
        self.vectors: dict[tuple, list[float]] = {}
        self.subject = subject or set()
        if embed is not None and sentences:
            try:
                vectors = list(embed([s.text for s in sentences]))
            except Exception:  # noqa: BLE001  # no vectors is a state, not an error
                vectors = []
            if len(vectors) == len(sentences):
                for s, vector in zip(sentences, vectors):
                    if vector is None:
                        continue
                    values = [float(x) for x in vector]
                    norm = math.sqrt(sum(x * x for x in values))
                    if norm:
                        self.vectors[s.key] = [x / norm for x in values]

    def cosine(self, a: Sentence, b: Sentence) -> float | None:
        va, vb = self.vectors.get(a.key), self.vectors.get(b.key)
        if va is None or vb is None:
            return None
        return sum(x * y for x, y in zip(va, vb))

    def same(self, a: Sentence, b: Sentence) -> bool:
        """One claim said twice. A cosine alone is not enough: an embedder
        that rates two unrelated short lines alike (a degenerate or stand-in
        one rates everything alike) had "Bib and pins the night before",
        written in one note, said four times (engine probe P4). Two sentences
        that say one thing share words too."""
        cosine = self.cosine(a, b)
        if cosine is not None:
            return cosine >= SAME_COSINE and _jaccard(a.words, b.words) >= SAME_WORDS
        return _jaccard(a.words, b.words) >= NEAR_DUPLICATE

    def alike(self, a: Sentence, b: Sentence) -> float:
        """Topic likeness: 1.0 for one claim, 0.0 for nothing shared."""
        cosine = self.cosine(a, b)
        if cosine is not None:
            return cosine
        return _jaccard([w for w in a.words if w not in self.subject], [w for w in b.words if w not in self.subject])

    def same_topic(self, a: Sentence, b: Sentence) -> bool:
        cosine = self.cosine(a, b)
        if cosine is not None:
            return cosine >= TOPIC_COSINE
        return self.alike(a, b) >= TOPIC_JACCARD


def centrality(sentences: list[Sentence], meaning: _Meaning, rounds: int = 30) -> dict[tuple, float]:
    """TextRank over the sentences' likeness graph, its teleport weighted by
    each sentence's score: the sentence most of the others lean towards, among
    the ones that answer the question. Deterministic (a fixed number of
    rounds from a fixed start)."""
    n = len(sentences)
    if n == 0:
        return {}
    weights = [[0.0 if i == j else max(0.0, meaning.alike(a, b)) for j, b in enumerate(sentences)] for i, a in enumerate(sentences)]
    totals = [sum(row) for row in weights]
    prior_total = sum(max(s.score, 0.0) for s in sentences) or 1.0
    prior = [max(s.score, 0.0) / prior_total for s in sentences]
    rank = list(prior)
    for _ in range(rounds):
        rank = [
            0.15 * prior[i] + 0.85 * sum(rank[j] * weights[j][i] / totals[j] for j in range(n) if totals[j])
            for i in range(n)
        ]
    return {s.key: rank[i] for i, s in enumerate(sentences)}


# --- disagreement -----------------------------------------------------------------

_NEGATION = lazy_compile(
    r"\b(not|no|never|none|nobody|cannot|can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|"
    r"cancel(?:led|ed)?|dropped)\b",
    re.I,
)


_FIGURE = lazy_compile(r"\d+(?:[.,]\d+)?")


def disagree(a: Sentence, b: Sentence) -> bool:
    """Two sentences from different notes about the same thing, one denying
    what the other says, or giving a different figure for it.

    A measure, worded as a possibility ("may disagree"): sharing most of their
    words and differing in a negation or a number is what a contradiction
    looks like on the page, and the reader decides.
    """
    if a.note_id == b.note_id:
        return False
    if len(set(a.words) & set(b.words)) < 2 or _jaccard(a.words, b.words) < 0.3:
        return False
    if bool(_NEGATION.search(a.text)) != bool(_NEGATION.search(b.text)):
        return True
    fa, fb = set(_FIGURE.findall(a.text)), set(_FIGURE.findall(b.text))
    return bool(fa and fb and not (fa & fb))


#: Whether the question asks for the value as it stands ("when's the dentist
#: now"): only then does a newer correction outrank the note it corrects;
#: otherwise both are said, older first, "but" the newer (`but_newer`).
_ASKS_NOW: contextvars.ContextVar[bool] = contextvars.ContextVar("composer_asks_now", default=False)
