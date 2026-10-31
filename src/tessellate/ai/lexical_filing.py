"""Filing by the notebook's own words, with no model at all (INBOX 434).

The owner: notes must file "amazing even when the ai isn't available or
accessible and then even better with it". Before this, with no chat model
and no embedding model loaded, every new note went to Uncategorised: the
log line said "the keyword fallback", and there was no keyword fallback.

This is that fallback, and it is a real one. It learns from what the person
has already done:

* every filed note is a labelled example of its category (its words and its
  tags, a tag counting as three words because it is a deliberate label);
* a note the person filed or moved by hand counts twice, because that is the
  strongest statement anyone made about where a note belongs;
* a category's own name, said in the note, is evidence for it ("gym: 5x5
  squats" belongs in Gym whatever else it says).

It is nearest neighbours by shared rare words (TF-IDF cosine): the closest
notes vote for their categories by how close they are, the classical answer
for short text with few examples. No training step, exact to recompute, a
thousand-note notebook in milliseconds. It abstains rather than guesses: a
category needs two notes to be chosen, and the winner must hold most of the
vote with two notes (or its own name) behind it, or the note stays in
Uncategorised with nothing pretending to have decided. A wrong category is
worse than none, because a note filed wrongly is a note the person cannot
find. Measured on a hand-written 100-note, ten-category notebook
(`scratchpad/filing_eval.py`, leave one out): right 80% of the times it
files, filing 15% of notes that share little vocabulary on purpose; a real
notebook repeats its own words more than that one does.

Not used when a model answered: the chain in `janitor.categorise` is the model
first (when there is one), then filing by meaning, then this.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import plain_words
from tessellate.core.database import Category, Entry
from tessellate.entry.manager import UNCATEGORISED

#: Words with no say in where a note belongs (`ai/plain_words.py`, shared with
#: the statistics): anything frequent across *every* category already cancels
#: out in the likelihoods, so the list only has to catch the words that would
#: otherwise dominate a short note.
_STOP = plain_words.PLAIN

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")

#: A tag is a label the person chose, so it says more than a word in passing.
TAG_WEIGHT = 3
#: A note filed or moved by hand: the strongest evidence there is.
USER_FILED_WEIGHT = 2
#: A category needs this many notes before it can be chosen.
MIN_EXAMPLES = 2
#: How many nearest notes vote.
NEIGHBOURS = 7
#: The category's own name in the note, as a vote.
NAME_VOTE = 0.6
#: To file, the winner needs this much summed similarity, this share of
#: all the votes, and this many notes (or its name) behind it. Tuned on
#: `scratchpad/filing_eval.py` for precision first: a wrong category is a
#: note lost, an Uncategorised one is a note waiting.
MIN_VOTE = 0.35
MIN_SHARE = 0.7
MIN_SUPPORT = 2
#: Or a clear lead: the winner has at least this many times the runner-up's
#: vote. A note with one stray word shared with another category ("oil",
#: "hot") split the share under MIN_SHARE while its own category won by far.
MIN_LEAD = 2.0
#: How many notes it reads, newest first; enough for any real notebook's
#: vocabulary and bounded so a huge one stays fast.
MAX_EXAMPLES = 4000


def tokens(text: str) -> list[str]:
    """Lower-case words, stop words out, a light plural fold ("squats" and
    "squat" are one word), digits kept ("5x5" is a gym word)."""
    out = []
    for word in _WORD.findall((text or "").lower()):
        word = word.replace("'", "")
        if len(word) < 2 or word in _STOP:
            continue
        if len(word) > 4 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        out.append(word)
    return out


#: The lines an OCR pass or a shop's printer adds to every capture: a page
#: count, a scanner's name, a receipt's thanks and tax number.
_BOILERPLATE = re.compile(
    r"page \d+ of \d+|scanned with \w+|thank you for shopping[^.\n]*|\babn[\d ]+|\bcaptured\b",
    re.IGNORECASE,
)
#: The bracket and paren runs exclude their own openers, so a run of "[" or
#: "(" cannot make each start rescan the line (linear, not polynomial).
_IMAGE = re.compile(r"!\[[^\[\]\n]*\]\([^()\n]*\)")
_LINK = re.compile(r"\[([^\[\]\n]*)\]\([^()\n]*\)")
_QUOTED = re.compile(r"\"[^\"\n]*\"|“[^“”\n]*”")
_BLOCKQUOTE = re.compile(r"^\s*>.*$", re.MULTILINE)


#: A fenced code block (``` or ~~~): its identifiers and language name say
#: nothing about the subject ("python" and "print" under a biology note made
#: it #software).
_FENCED = re.compile(r"^[ \t>]*(```|~~~)[^\n]*\n.*?(?:^[ \t>]*\1[^\n]*$|\Z)", re.MULTILINE | re.DOTALL)


def clean(content: str) -> str:
    """The note's own words: no image address, no link target, no OCR
    footer, no fenced code, and nothing in quotation marks or a blockquote
    (somebody else's words) unless the quotation is most of the note: a
    pasted message, "From the coach's email: ...", is what the note is about.
    Code is dropped unless it is most of the note, which is then about code."""
    out = _IMAGE.sub(" ", content or "")
    prose = _FENCED.sub(" ", out)
    if len(tokens(prose)) >= len(tokens(out)) - len(tokens(prose)):
        out = prose
    out = _LINK.sub(r"\1", out)
    out = _BOILERPLATE.sub(" ", out)
    unquoted = _BLOCKQUOTE.sub(" ", _QUOTED.sub(" ", out))
    quoted = len(tokens(out)) - len(tokens(unquoted))
    return unquoted if quoted and len(tokens(unquoted)) >= quoted else out


@dataclass
class LexicalMatch:
    name: str
    confidence: int
    margin: float
    #: One line a person can read: the words shared, the notes it joins, the
    #: measure that decided (WORLD_CLASS 23, decision 3).
    why: str = ""


def _tags(raw: str | None) -> list[str]:
    try:
        tags = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(tag) for tag in tags if tag] if isinstance(tags, list) else []


def lexical_category(
    session: Session, content: str, exclude_entry_id: int | None = None
) -> LexicalMatch | None:
    """The category the notebook's own words point to, or None to abstain
    (including a sensitive note held back for the person, `decide`)."""
    decision = decide(session, content, exclude_entry_id)
    if decision.filed is None:
        return None
    return LexicalMatch(
        name=decision.filed.name, confidence=decision.confidence,
        margin=decision.margin, why=decision.filed.why,
    )


def category_support(
    session: Session, content: str, category: str, exclude_entry_id: int | None = None
) -> tuple[float | None, int]:
    """How the notebook's own words see `category` for `content`: (its share
    of the vote, how many notes it holds).

    The share is None when the words have no real opinion (nothing in common
    with a filed note, or the best vote under `MIN_VOTE`), because "the words
    know nothing" must not read as "the words disagree". Names compare
    without case, since a model answers "work" for "Work". Read by
    `filing_certainty`, which lowers a model's number when this disagrees."""
    wanted = (category or "").strip().lower()
    held = session.scalar(
        select(func.count(Entry.id))
        .join(Category, Entry.category_id == Category.id)
        .where(
            func.lower(Category.name) == wanted,
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_board == False,  # noqa: E712
            Entry.id != (exclude_entry_id or 0),
        )
    )
    tally = _tally(session, content, exclude_entry_id)
    share: float | None = None
    if tally is not None:
        votes, _supporters = tally
        total = sum(votes.values())
        if votes and total > 0 and max(votes.values()) >= MIN_VOTE:
            share = sum(v for name, v in votes.items() if name.lower() == wanted) / total
    return share, int(held or 0)


def suggest_categories(
    session: Session, content: str, exclude_entry_id: int | None = None, limit: int = 3
) -> list[str]:
    """Up to `limit` categories to offer as one-tap choices when nothing was
    sure enough to file the note (INBOX 434): the decision's ranking, best
    first, then the ones used most recently. A guess shown as a choice costs
    a glance; a guess filed is a note lost."""
    return [name for name, _why in suggest_categories_explained(session, content, exclude_entry_id, limit)]


def suggest_categories_explained(
    session: Session, content: str, exclude_entry_id: int | None = None, limit: int = 3
) -> list[tuple[str, str]]:
    """`suggest_categories` with each one's why ("" for a recent one)."""
    decision = decide(session, content, exclude_entry_id)
    out: list[tuple[str, str]] = [(c.name, c.why) for c in decision.ranked if c.score > 0]
    if len(out) < limit:
        recent = session.execute(
            select(Category.name)
            .join(Entry, Entry.category_id == Category.id)
            .where(Entry.is_deleted == False, Category.name != UNCATEGORISED)  # noqa: E712
            .order_by(Entry.id.desc())
            .limit(200)
        ).scalars()
        taken = {name for name, _ in out}
        for name in recent:
            if name not in taken:
                out.append((name, ""))
                taken.add(name)
            if len(out) >= limit:
                break
    return out[:limit]


#: A category the notebook already has, named by a topic of the taxonomy
#: pack (`ai/taxonomy.py`: "squat" is Fitness, "simmer" Cooking), votes this
#: much. The pack replaced the Gemini map (WORLD_CLASS 23, step 2): 120-note
#: fixture top-1 0.175 to 0.192, wrong filings 8 throughout.
#: Measured leave-one-out on `tests/fixtures/filing/notes.json` (40 notes,
#: 8 categories): top-1 0.05 with no vote, 0.15 at 0.5, 1.0 and 2.0 alike,
#: wrong filings 2 throughout; the smallest weight that gains is taken. The
#: Gemini branch voted 2.0 for the map's own names whether the notebook had
#: them or not: 0.225 right but 14 notes filed into categories nobody made.
#: Tags are `ai/tagging.py`'s.
TAXONOMY_CATEGORY_VOTE = 0.5


def _tally(
    session: Session, content: str, exclude_entry_id: int | None
) -> tuple[dict[str, float], dict[str, int]] | None:
    """Each category's vote for `content` and how many notes (or its name)
    stand behind it; None when there is nothing to count."""
    wanted = tokens(content)
    if not wanted:
        return None
    names = dict(session.execute(select(Category.id, Category.name)).all())
    with _corpus_lock:
        corpus = _corpus_for(session)
        scope = _scope(session)
        docs = [
            (entry_id, doc)
            for entry_id, doc in corpus.docs.items()
            if entry_id != exclude_entry_id
            and not doc.board
            and doc.tagged
            and names.get(doc.category_id, UNCATEGORISED) != UNCATEGORISED
            and scope(doc)
        ]
        if not docs:
            return None

        #: **Nearest notes by shared rare words** (TF-IDF cosine), each voting
        #: for its category by how close it is. Naive Bayes was tried first
        #: and measured on a 100-note, ten-category notebook (scratchpad/
        #: filing_eval.py): 46% right when it filed. On notes this short, the
        #: words two notes share are the whole signal, and a rare shared word
        #: ("squats", "lentils") says far more than a common one.
        query_bag: dict[str, float] = {}
        for word in wanted:
            query_bag[word] = query_bag.get(word, 0.0) + 1.0
        notes_in: dict[str, int] = {}
        for _id, doc in docs:
            name = names[doc.category_id]
            notes_in[name] = notes_in.get(name, 0) + 1
        scored = [
            (similarity, names[doc.category_id], USER_FILED_WEIGHT if doc.by_hand else 1)
            for similarity, doc in corpus.nearest(query_bag, "tagged", docs)
        ]
    scored.sort(reverse=True)
    votes: dict[str, float] = {}
    supporters: dict[str, int] = {}
    for similarity, name, weight in scored[:NEIGHBOURS]:
        if notes_in.get(name, 0) < MIN_EXAMPLES:
            continue
        votes[name] = votes.get(name, 0.0) + similarity * weight
        supporters[name] = supporters.get(name, 0) + 1
    if TAXONOMY_CATEGORY_VOTE:
        from tessellate.ai.taxonomy import extract_categories

        held = {name.casefold(): name for name in notes_in if notes_in[name] >= MIN_EXAMPLES}
        for domain in set(extract_categories(content)):
            name = held.get(domain.casefold())
            if name:
                votes[name] = votes.get(name, 0.0) + TAXONOMY_CATEGORY_VOTE
                supporters[name] = supporters.get(name, 0) + 1

    #: Naming the category is a vote of its own ("gym: new shoes").
    for name in notes_in:
        name_words = _name_words(name)
        if notes_in[name] >= MIN_EXAMPLES and name_words and all(word in wanted for word in name_words):
            votes[name] = votes.get(name, 0.0) + NAME_VOTE
            supporters[name] = supporters.get(name, 0) + MIN_SUPPORT

    return votes, supporters


# --- the decision: the person's categories first (WORLD_CLASS 23, decision 2)
#
# Each category the notebook has is scored from four kinds of evidence, all
# from the notebook or the pack, none from a model:
#
# * **its nearest notes** (the TF-IDF neighbours above, `_tally`);
# * **its notes as one** (the cosine with the category's summed words, a
#   Rocchio centroid): steadier than seven neighbours when a category's notes
#   share few words with one another;
# * **its topics**: the pack topics its notes and its own name name ("Gym" is
#   Fitness), against the note's (`taxonomy.topic_weights`), so "squats" finds
#   Gym before any Gym note has said "squats";
# * **its name** said in the note, and the person's own aliases (step 4).
#
# The best files the note when it clears `FILE_SCORE` and leads the next by
# `FILE_LEAD`; otherwise the ranking is offered as one-tap choices, and a new
# category from the pack is proposed only when no existing one scored at all.
# Measured on the 120-note fixture (tests/test_filing_accuracy.py).

#: The weights of the four kinds of evidence.
W_NEIGHBOURS = 1.0
W_CENTROID = 1.0
W_TOPICS = 1.0
#: A topic is named in a category's why only when its profile holds at
#: least this share of its strongest topic's weight.
TOPIC_OWN_SHARE = 0.25
#: A category's own name counts this much towards its topic profile, against
#: one for each note's own topics.
NAME_TOPIC_WEIGHT = 3.0
#: To file: at least this score, and this many times the runner-up's.
FILE_SCORE = 0.3
FILE_LEAD = 1.3
#: A composite name ("Fitness & Health") only when the second topic is
#: within this share of the first and both are in the note (decision 2).
COMPOSITE_WITHIN = 0.9
#: A topic the person's own corrections send to a category counts this much
#: per correction (up to `LEXICON_MAX`) in that category's profile, and the
#: category gets `LEXICON_VOTE` outright, by the share of the note's topics it
#: was taught, where the note is really about the topic: one correction
#: decides "Work, not Software" (decision 7: weighed first). Measured by
#: `scratchpad/filing-tools/online.py` (notes arrive one at a time; a wrong
#: filing is moved by hand): 0.521 top-1 with no lexicon, 0.510 with it at
#: these weights, 0.448 at 10 and 1.0 when every weak topic of a corrected
#: note was taught. The fixture's categories name no pack topic that another
#: one holds, so it measures the cost, not the case the lexicon is for.
LEXICON_WEIGHT = 3.0
LEXICON_MAX = 3
LEXICON_VOTE = 1.5
#: The preference that lets a sensitive note file itself (decision 6).
PREF_AUTO_FILE_SENSITIVE = "auto_file_sensitive"


@dataclass
class Candidate:
    name: str
    score: float
    #: The note's words it shares with the category's notes, most telling first.
    words: list[str]
    #: Pack topics the note and the category share, with the note's phrases.
    topics: dict[str, list[str]]
    notes: int
    named: bool
    #: Note topics the person's own corrections send here (decision 7).
    lexicon: list[str] = field(default_factory=list)

    @property
    def why(self) -> str:
        return _why_line(self)


@dataclass
class Proposal:
    """A category the notebook does not have, from the pack (decision 2):
    shown with its reason and a one-tap accept, never made by itself."""

    name: str
    phrases: list[str]
    sensitive: bool

    @property
    def why(self) -> str:
        return f"Nothing you have fits; it mentions {_quote_list(self.phrases[:3])}, which the topic list files as {self.name}."


@dataclass
class Decision:
    ranked: list[Candidate]
    filed: Candidate | None
    confidence: int = 0
    margin: float = 0.0
    proposal: Proposal | None = None
    #: The sensitive topic the note reads as, when it does (decision 6).
    sensitive: str | None = None
    #: It would have filed, and was held back because it is sensitive.
    held: bool = False


_OPEN, _CLOSE = chr(0x201C), chr(0x201D)


def _quote_list(words: list[str]) -> str:
    quoted = [f"{_OPEN}{word}{_CLOSE}" for word in words]
    if len(quoted) <= 1:
        return "".join(quoted)
    return ", ".join(quoted[:-1]) + " and " + quoted[-1]


def _why_line(candidate: Candidate) -> str:
    """"It mentions “squat” and “deadlift” (Fitness), like the 9 notes in
    Gym." The words shared, the notes it joins, the measure that decided."""
    joins = f"the {candidate.notes} note{'s' if candidate.notes != 1 else ''} in {candidate.name}"
    if candidate.lexicon:
        topic = candidate.lexicon[0]
        said = candidate.topics.get(topic) or []
        mentions = f"It mentions {_quote_list(said[:2])} ({topic})" if said else f"It reads as {topic}"
        return f"{mentions}, which you file under {candidate.name}."
    phrases: list[str] = []
    topics: list[str] = []
    for topic, said in candidate.topics.items():
        topics.append(topic)
        phrases.extend(p for p in said if p not in phrases)
    if candidate.named and not phrases and not candidate.words:
        return f"It says {candidate.name}."
    if phrases:
        about = _quote_list(phrases[:3])
        #: A topic named by the very word quoted ("cooking (Cooking)") adds nothing, and
        #: read beside a category of another name it looked like a contradiction (audit 1031 N7).
        if {t.casefold() for t in topics[:2]} != {p.casefold() for p in phrases[:3]}:
            about += f" ({', '.join(topics[:2])})"
        return f"It mentions {about}, like {joins}."
    if candidate.words:
        return f"It shares {_quote_list(candidate.words[:3])} with {joins}."
    return f"It says {candidate.name}." if candidate.named else f"It reads like {joins}."


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(value * b.get(key, 0.0) for key, value in a.items())
    if not dot:
        return 0.0
    return dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


@lru_cache(maxsize=1024)
def _name_words(name: str) -> tuple[str, ...]:
    """A category name's words, kept: a save reads every category's."""
    return tuple(tokens(name))


def holds_sensitive(content: str, category: str | None = None) -> str | None:
    """The sensitive topic that keeps `content` from filing itself, or None.

    Decision 6 on every path (INBOX 770): `decide` holds a note the words
    would file; this is the same test for a category another filer chose
    (the embedder's nearest notes, the chat model's answer), so a health or
    money note is suggested, never filed, until Settings says otherwise."""
    if _auto_file_sensitive():
        return None
    from tessellate.ai import taxonomy

    sensitive_set = taxonomy.sensitive_topics()
    hits = taxonomy.topic_hits(content)
    topic = next((t for t in taxonomy.strong_topics(content, hits) if t in sensitive_set), None)
    #: The category counts only when it is the sensitive topic itself
    #: ("Health", "Money"): a word of its name is not enough, or "Dad Jokes"
    #: would be held as Relationships (CI on e2f37a1eb, 11 tests).
    if topic is None and category in sensitive_set:
        topic = category
    return topic


def _auto_file_sensitive() -> bool:
    try:
        from tessellate.core import deps

        return bool(deps.get_config().get_preference(PREF_AUTO_FILE_SENSITIVE, False))
    except Exception:  # noqa: BLE001 - no config (a script, a test without app state): the safe default
        logging.getLogger("tessellate.lexical_filing").debug("no preference store; sensitive notes are held", exc_info=True)
        return False


@dataclass
class _NoteRead:
    """What `decide` knows about the note and the notebook, handed to the
    per-category scoring."""

    wanted: list
    hits: dict
    note_topics: dict
    strong: list
    knn_votes: dict
    query_vec: dict
    query_norm: float
    idf: dict
    sums: dict
    lengths: dict
    profiles: dict
    lexicon: dict


def _take_out_excluded(corpus, scope, names: dict, exclude_entry_id: int | None, held: dict, profiles: dict) -> None:  # noqa: ANN001
    excluded = corpus.docs.get(exclude_entry_id) if exclude_entry_id is not None else None
    if excluded is None or excluded.board or not scope(excluded):
        return
    #: The note being refiled is taken out of its category exactly.
    name = names.get(excluded.category_id, UNCATEGORISED)
    if name in held:
        held[name] -= 1
        if not held[name]:
            del held[name]
        for topic, weight in excluded.topics.items():
            profiles[name][topic] = profiles[name].get(topic, 0.0) - weight


def _category_sums(corpus, scope, names: dict, exclude_entry_id: int | None, query_bag: dict) -> dict:  # noqa: ANN001
    """The query's words summed per category through the inverted index: only
    the notes that share a word are read."""
    sums: dict[str, dict[str, float]] = {}
    postings = corpus.postings["tagged"]
    for word in query_bag:
        for holder in postings.get(word, ()):
            doc = corpus.docs.get(holder)
            if doc is None or holder == exclude_entry_id or doc.board or not scope(doc):
                continue
            name = names.get(doc.category_id, UNCATEGORISED)
            if name == UNCATEGORISED:
                continue
            bag = sums.setdefault(name, {})
            bag[word] = bag.get(word, 0.0) + doc.tagged[word]
    return sums


def _corpus_view(session: Session, names: dict, exclude_entry_id: int | None, query_bag: dict) -> tuple:
    """(category lengths, notes held per category, topic profiles, word sums,
    idf), read under the corpus lock."""
    with _corpus_lock:
        corpus = _corpus_for(session)
        scope = _scope(session)
        lengths, kept_profiles, kept_held = _category_aggregates(corpus, names, scope, _scope_key(session))
        held = dict(kept_held)
        profiles = {name: dict(profile) for name, profile in kept_profiles.items()}
        _take_out_excluded(corpus, scope, names, exclude_entry_id, held, profiles)
        sums = _category_sums(corpus, scope, names, exclude_entry_id, query_bag)
        idf = {word: corpus._idf("tagged", word) for word in query_bag}
    return lengths, held, profiles, sums, idf


def _taught_topics(name: str, profile: dict, read: _NoteRead) -> list:
    """Add the person's own words for topics to the category's profile; the
    topics that vote outright for it."""
    taught = []
    for topic, sent in read.lexicon.items():
        if sent.get(name):
            profile[topic] = profile.get(topic, 0.0) + LEXICON_WEIGHT * min(sent[name], LEXICON_MAX)
            #: The outright vote only where the person's word for this
            #: topic is this category more than any other, and the note
            #: is really about it (a topic the pack accepts for it).
            if topic in read.strong and sent[name] >= max(sent.values()):
                taught.append(topic)
    return taught


def _candidate_for(name: str, count: int, read: _NoteRead) -> Candidate | None:
    from tessellate.ai import taxonomy

    profile = dict(read.profiles.get(name, {}))
    for topic, weight in taxonomy.name_topics(name).items():
        profile[topic] = profile.get(topic, 0.0) + NAME_TOPIC_WEIGHT * weight
    taught = _taught_topics(name, profile, read)
    topic_score = _cosine(read.note_topics, profile)
    shared = read.sums.get(name, {})
    contributions = {word: read.query_vec[word] * shared[word] * read.idf[word] for word in shared if word in read.query_vec}
    centroid = sum(contributions.values()) / (read.query_norm * (read.lengths.get(name) or 1.0)) if contributions else 0.0
    name_words = _name_words(name)
    named = bool(name_words) and all(word in read.wanted for word in name_words)
    #: The name's own vote (`NAME_VOTE`) is already in the neighbours'.
    score = W_NEIGHBOURS * read.knn_votes.get(name, 0.0) + W_CENTROID * centroid + W_TOPICS * topic_score
    if taught:
        score += LEXICON_VOTE * sum(read.note_topics[t] for t in taught) / (sum(read.note_topics.values()) or 1.0)
    if score <= 0:
        return None
    return Candidate(
        name=name, score=score,
        words=sorted(contributions, key=contributions.__getitem__, reverse=True),
        #: Only the topics that are this category's own, not a stray
        #: phrase one of its notes once said ("smoke alarm" in Cooking).
        topics={
            topic: read.hits[topic]
            for topic in sorted(read.hits, key=lambda t: -profile.get(t, 0.0))
            if profile.get(topic, 0.0) >= TOPIC_OWN_SHARE * max(profile.values(), default=0.0) > 0
        },
        notes=count, named=named, lexicon=taught,
    )


def _file_if_clear(decision: Decision, sensitive_set: set) -> None:
    """File the note under the best category when it leads clearly enough, or
    hold it when its topic is a sensitive one."""
    ranked = decision.ranked
    best = ranked[0]
    runner_up = ranked[1].score if len(ranked) > 1 else 0.0
    decision.margin = best.score - runner_up
    if not (best.score >= FILE_SCORE and best.score >= FILE_LEAD * runner_up and (best.notes >= MIN_EXAMPLES or best.named)):
        return
    share = best.score / sum(c.score for c in ranked)
    #: Kept between 50 and 85, as before: this is word overlap.
    decision.confidence = max(50, min(85, round(40 + 50 * share)))
    sensitive_here = decision.sensitive or next((t for t in best.topics if t in sensitive_set), None)
    if sensitive_here and not _auto_file_sensitive():
        decision.sensitive = sensitive_here
        decision.held = True
    else:
        decision.filed = best


def _word_counts(wanted: list) -> dict:
    bag: dict[str, float] = {}
    for word in wanted:
        bag[word] = bag.get(word, 0.0) + 1.0
    return bag


def _note_read(session: Session, note: tuple, query_bag: dict, corpus_side: tuple) -> _NoteRead:
    wanted, hits, note_topics, strong, knn_votes = note
    idf, sums, lengths, profiles = corpus_side
    query_vec = {word: (1.0 + math.log(n)) * idf[word] for word, n in query_bag.items() if idf[word]}
    return _NoteRead(
        wanted, hits, note_topics, strong, knn_votes, query_vec, math.sqrt(sum(v * v for v in query_vec.values())) or 1.0,
        idf, sums, lengths, profiles, personal_lexicon(session),
    )


def decide(session: Session, content: str, exclude_entry_id: int | None = None) -> Decision:
    """Where the notebook's own words, and the pack's topics, put `content`.
    Never a category the notebook lacks; a new one only as a `proposal`."""
    from tessellate.ai import taxonomy

    #: The note's own words: a quotation, an image's address or an OCR
    #: footer says nothing about where it belongs (INBOX 781).
    content = clean(content)
    wanted = tokens(content)
    hits = taxonomy.topic_hits(content)
    note_topics = taxonomy.topic_weights(content, hits)
    sensitive_set = taxonomy.sensitive_topics()
    strong = taxonomy.strong_topics(content, hits)
    sensitive = next((topic for topic in strong if topic in sensitive_set), None)
    if not wanted and not hits:
        return Decision(ranked=[], filed=None, sensitive=sensitive)
    names = dict(session.execute(select(Category.id, Category.name)).all())
    tally = _tally(session, content, exclude_entry_id) if wanted else None
    knn_votes, _supporters = tally if tally is not None else ({}, {})
    query_bag = _word_counts(wanted)
    lengths, held, profiles, sums, idf = _corpus_view(session, names, exclude_entry_id, query_bag)
    if not held:
        return _with_proposal(Decision(ranked=[], filed=None, sensitive=sensitive), held, strong, hits, sensitive_set)
    read = _note_read(session, (wanted, hits, note_topics, strong, knn_votes), query_bag, (idf, sums, lengths, profiles))
    ranked = [c for c in (_candidate_for(name, count, read) for name, count in held.items()) if c is not None]
    ranked.sort(key=lambda c: c.score, reverse=True)
    decision = Decision(ranked=ranked, filed=None, sensitive=sensitive)
    if ranked:
        _file_if_clear(decision, sensitive_set)
    return _with_proposal(decision, held, strong, hits, sensitive_set)


def category_profiles(session: Session) -> dict[str, tuple[int, dict[str, float], dict[str, float]]]:
    """Each category's `(notes, topic profile, its notes' topics alone)`: the
    profile as the decision reads it (its notes, its name, the person's
    lexicon), and the part its notes said, for Tidy's merge and rename
    reviews (WORLD_CLASS 23, decision 4)."""
    from tessellate.ai import taxonomy

    names = dict(session.execute(select(Category.id, Category.name)).all())
    with _corpus_lock:
        corpus = _corpus_for(session)
        scope = _scope(session)
        _lengths, profiles, held = _category_aggregates(corpus, names, scope, _scope_key(session))
    lexicon = personal_lexicon(session)
    out: dict[str, tuple[int, dict[str, float], dict[str, float]]] = {}
    for name, count in held.items():
        own = {topic: weight for topic, weight in profiles.get(name, {}).items() if weight > 0}
        profile = dict(own)
        for topic, weight in taxonomy.name_topics(name).items():
            profile[topic] = profile.get(topic, 0.0) + NAME_TOPIC_WEIGHT * weight
        for topic, sent in lexicon.items():
            if sent.get(name):
                profile[topic] = profile.get(topic, 0.0) + LEXICON_WEIGHT * min(sent[name], LEXICON_MAX)
        out[name] = (count, profile, own)
    return out


def topic_overlap(a: dict[str, float], b: dict[str, float]) -> float:
    """How much two topic profiles say the same thing: their cosine."""
    return _cosine(a, b)


#: The lexicon last read, with the newest correction it saw: corrections
#: only ever grow, so the same newest id is the same lexicon.
_lexicon_seen: dict = {}


def personal_lexicon(session: Session) -> dict[str, dict[str, int]]:
    """The person's own words for topics (WORLD_CLASS 23, decision 7):
    `{topic: {category: how many times}}`, from the moves they made out of
    an automatic filing (a refile's note, read for its pack topics, and the
    category it went to: "Work, not Software") and the merges they applied in
    Tidy (`alias`). Stored where every correction is, in this notebook's log;
    nothing is learned from a filing nobody corrected."""
    from tessellate.ai import learning, taxonomy
    from tessellate.core.database import AuditLog

    newest = session.scalar(select(func.max(AuditLog.id)).where(AuditLog.action == "correction"))
    key = (str(session.get_bind().url), newest)
    if _lexicon_seen.get("key") == key:
        return _lexicon_seen["lexicon"]
    lexicon: dict[str, dict[str, int]] = {}
    if newest is not None:
        for correction in learning.corrections(session, kind="refile"):
            to = correction.to_value
            if not to or to == UNCATEGORISED or not correction.excerpt:
                continue
            #: Only the topics the pack itself accepts for that note: a stray
            #: weak word ("book" in a car note) taught the wrong rule.
            for topic in taxonomy.strong_topics(correction.excerpt):
                sent = lexicon.setdefault(topic, {})
                sent[to] = sent.get(to, 0) + 1
        for correction in learning.corrections(session, kind="alias"):
            topic = str(correction.subject.get("topic") or "")
            if topic and correction.to_value:
                sent = lexicon.setdefault(topic, {})
                sent[correction.to_value] = sent.get(correction.to_value, 0) + LEXICON_MAX
    _lexicon_seen.update(key=key, lexicon=lexicon)
    return lexicon


def _with_proposal(decision, held, strong, hits, sensitive_set):  # noqa: ANN001, ANN202
    """A new category from the pack, only when no existing one scored
    (decision 2): its strongest topic, or two as a composite when they tie
    within `COMPOSITE_WITHIN`. Never a note purpose, never a name the
    notebook already has, never a topic one of its categories already names."""
    if decision.filed is not None or decision.held or decision.ranked or not strong:
        return decision
    from tessellate.ai import taxonomy

    have = {name.casefold() for name in held}
    covered = {topic for name in held for topic in taxonomy.name_topics(name)}
    covered |= set(_lexicon_seen.get("lexicon") or {})
    topics = [topic for topic in strong if topic not in covered]
    if not topics:
        return decision
    first = topics[0]
    chosen = [first]
    if len(topics) > 1 and strong[topics[1]] >= COMPOSITE_WITHIN * strong[first]:
        chosen.append(topics[1])
    name = " & ".join(chosen)
    if name.casefold() in have:
        return decision
    phrases = [p for topic in chosen for p in hits.get(topic, [])]
    decision.proposal = Proposal(
        name=name, phrases=list(dict.fromkeys(phrases)),
        sensitive=any(topic in sensitive_set for topic in chosen),
    )
    return decision


def _category_aggregates(corpus, names, scope, scope_key):  # noqa: ANN001, ANN202
    """Per category, kept per corpus generation and scope so a save does not
    sum the notebook again for every note Tidy reads: its summed-words
    vector length (TF-IDF), its topic profile (its notes' pack topics) and
    how many notes it holds. The note being refiled is taken out by the
    caller; its words are left in the length, which moves it by one note in
    many."""
    key = (corpus.generation, corpus.epoch["tagged"], scope_key, tuple(sorted(names.items())))
    cached = corpus.lengths_cache.get("categories")
    if cached is not None and cached[0] == key:
        return cached[1]
    sums: dict[str, dict[str, float]] = {}
    profiles: dict[str, dict[str, float]] = {}
    held: dict[str, int] = {}
    for doc in corpus.docs.values():
        if doc.board or not scope(doc):
            continue
        name = names.get(doc.category_id, UNCATEGORISED)
        if name == UNCATEGORISED:
            continue
        held[name] = held.get(name, 0) + 1
        bag = sums.setdefault(name, {})
        for word, weight in doc.tagged.items():
            bag[word] = bag.get(word, 0.0) + weight
        profile = profiles.setdefault(name, {})
        for topic, weight in doc.topics.items():
            profile[topic] = profile.get(topic, 0.0) + weight
    lengths = {
        name: math.sqrt(sum((weight * corpus._idf("tagged", word)) ** 2 for word, weight in bag.items())) or 1.0
        for name, bag in sums.items()
    }
    found = (lengths, profiles, held)
    corpus.lengths_cache["categories"] = (key, found)
    return found

# --- the corpus, kept rather than rebuilt (audit 2026-10-05, ARCH-02) ---------
#
# **A save used to read the notebook.** Both passes above read up to
# `MAX_EXAMPLES` notes' full text and tokenised every one of them, on every
# save, to rebuild the same TF-IDF tables: 490 ms of a 1,415 ms save at 610
# notes, and the main reason seeding fell from 11 notes a second at 40 notes
# to 1 a second at 750. The tables are now kept per notebook and brought up
# to date by a diff: one query of small columns (id, when it changed, its
# tags, its category) finds what changed since the last call, and only those
# notes are read and tokenised again. Scoring then reads only the notes that
# share a word with the one being filed, through an inverted index.
#
# The stamp is what an edit moves: `updated_at` (`onupdate`, so every ORM
# write), and the tags and category themselves, because a notebook-wide tag
# or category rename is one UPDATE statement that does not.


@dataclass
class _Doc:
    stamp: tuple
    workspace: str
    category_id: int | None
    by_hand: bool
    board: bool
    tags: list[str]
    #: `1 + log(count)` per word of the text: the tag pass's bag.
    words: dict[str, float]
    #: The same over the text and the tags (a tag counting `TAG_WEIGHT`
    #: times): the filing pass's bag.
    tagged: dict[str, float]
    #: The pack topics its text and tags name, with the pack's weights
    #: (`taxonomy.topic_weights`): its category's topic profile is their sum.
    topics: dict[str, float] = field(default_factory=dict)
    #: `{kind: (epoch, length)}`: the bag's TF-IDF length, kept until the
    #: corpus has grown enough to move every word's rarity (`_Corpus.epoch`).
    lengths: dict[str, tuple[int, float]] = field(default_factory=dict)


#: Past this many postings, candidates come from the query's rarest words
#: only, and only the best `RESCORE` of them are scored in full. A shared
#: rare word is what puts a note among the nearest seven ("squats",
#: "lentils"); a word half the notebook uses moves the score a little and the
#: order of the top hardly at all, and reading its postings was most of the
#: cost on a notebook with a small vocabulary.
POSTINGS_BUDGET = 4_000
RESCORE = 64
#: How far the corpus may grow or shrink before every kept length is stale.
EPOCH_DRIFT = 0.1


class _Corpus:
    def __init__(self, key: str) -> None:
        self.key = key
        self.docs: dict[int, _Doc] = {}
        #: Per bag kind: how many docs hold each word, and which ones.
        self.frequency: dict[str, dict[str, int]] = {"words": {}, "tagged": {}}
        self.postings: dict[str, dict[str, set[int]]] = {"words": {}, "tagged": {}}
        self.totals: dict[str, int] = {"words": 0, "tagged": 0}
        #: Bumped when a kind's total has drifted `EPOCH_DRIFT` from the
        #: total its lengths were taken at; a length from an older epoch is
        #: taken again the next time its doc is scored.
        self.epoch: dict[str, int] = {"words": 0, "tagged": 0}
        self._epoch_total: dict[str, int] = {"words": 0, "tagged": 0}
        #: The newest `updated_at` read, and when the corpus was last read
        #: whole (`_corpus_for`).
        self.mark: str | None = None
        self.full_at = 0.0
        #: Bumped on every add and remove: what a kept per-category sum
        #: (`_category_lengths`) was taken at.
        self.generation = 0
        self.lengths_cache: dict[str, tuple] = {}

    def _bags(self, doc: _Doc) -> dict[str, dict[str, float]]:
        # The tag pass only ever reads tagged notes, so only they count
        # towards its word rarity, as when it read them from the table.
        return {"words": doc.words if doc.tags else {}, "tagged": doc.tagged}

    def remove(self, entry_id: int) -> None:
        doc = self.docs.pop(entry_id, None)
        if doc is None:
            return
        self.generation += 1
        for kind, bag in self._bags(doc).items():
            if not bag:
                continue
            self.totals[kind] -= 1
            frequency, postings = self.frequency[kind], self.postings[kind]
            for word in bag:
                frequency[word] -= 1
                if not frequency[word]:
                    del frequency[word]
                holders = postings.get(word)
                if holders is not None:
                    holders.discard(entry_id)
                    if not holders:
                        del postings[word]

    def add(self, entry_id: int, doc: _Doc) -> None:
        self.remove(entry_id)
        self.docs[entry_id] = doc
        self.generation += 1
        for kind, bag in self._bags(doc).items():
            if not bag:
                continue
            self.totals[kind] += 1
            frequency, postings = self.frequency[kind], self.postings[kind]
            for word in bag:
                frequency[word] = frequency.get(word, 0) + 1
                postings.setdefault(word, set()).add(entry_id)

    def _idf(self, kind: str, word: str) -> float:
        count = self.frequency[kind].get(word)
        return math.log((1 + self.totals[kind]) / (1 + count)) + 1.0 if count else 0.0

    def _length(self, kind: str, doc: _Doc) -> float:
        kept = doc.lengths.get(kind)
        if kept is not None and kept[0] == self.epoch[kind]:
            return kept[1]
        bag = doc.words if kind == "words" else doc.tagged
        frequency, total = self.frequency[kind], self.totals[kind]
        squares = 0.0
        for word, weight in bag.items():
            count = frequency.get(word)
            if count:
                value = weight * (math.log((1 + total) / (1 + count)) + 1.0)
                squares += value * value
        length = math.sqrt(squares) or 1.0
        doc.lengths[kind] = (self.epoch[kind], length)
        return length

    def nearest(
        self, query_bag: dict[str, float], kind: str, docs: list[tuple[int, _Doc]]
    ) -> list[tuple[float, _Doc]]:
        """`(cosine, doc)` for the docs in `docs` that share a word with the
        query, best first: TF-IDF, each word's rarity taken over the whole
        kept corpus of this kind. Bounded work per call (`POSTINGS_BUDGET`,
        `RESCORE`), whatever the notebook's size."""
        total = self.totals[kind]
        if abs(total - self._epoch_total[kind]) > EPOCH_DRIFT * max(self._epoch_total[kind], 1):
            self.epoch[kind] += 1
            self._epoch_total[kind] = total
        target = {word: (1.0 + math.log(n)) * self._idf(kind, word) for word, n in query_bag.items()}
        target = {word: value for word, value in target.items() if value}
        if not target:
            return []
        norm = math.sqrt(sum(v * v for v in target.values())) or 1.0
        #: Each query word's share of a dot product with a doc's `1 + log n`.
        share = {word: value / norm * self._idf(kind, word) for word, value in target.items()}
        allowed = dict(docs)
        postings = self.postings[kind]
        by_words = kind == "words"
        partial: dict[int, float] = {}
        read = 0
        for word in sorted(share, key=lambda w: len(postings.get(w, ()))):
            holders = postings.get(word, ())
            if read and read + len(holders) > POSTINGS_BUDGET:
                break
            read += len(holders)
            weight = share[word]
            for holder in holders:
                doc = allowed.get(holder)
                if doc is not None:
                    partial[holder] = partial.get(holder, 0.0) + weight * (doc.words if by_words else doc.tagged)[word]
        if not partial:
            return []
        ranked = sorted(partial, key=partial.__getitem__, reverse=True)[:RESCORE]
        scored: list[tuple[float, _Doc]] = []
        for holder in ranked:
            doc = allowed[holder]
            bag = doc.words if by_words else doc.tagged
            dot = sum(weight * bag.get(word, 0.0) for word, weight in share.items())
            similarity = dot / self._length(kind, doc)
            if similarity > 0:
                scored.append((similarity, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored


_corpus: _Corpus | None = None
#: Held while the corpus changes or is read. Never across a model call; the
#: only database work under it is the diff's own two small reads.
_corpus_lock = threading.RLock()


def _tag_words(tag: str) -> list[str]:
    return tokens(tag.replace("/", " "))


def _make_doc(stamp: tuple, content: str, tags: list[str], workspace, category_id, by_hand, board) -> _Doc:  # noqa: ANN001
    counts: dict[str, float] = {}
    for word in tokens(content):
        counts[word] = counts.get(word, 0.0) + 1.0
    tagged_counts = dict(counts)
    for tag in tags:
        for word in _tag_words(tag):
            tagged_counts[word] = tagged_counts.get(word, 0.0) + TAG_WEIGHT
    words = {word: 1.0 + math.log(n) for word, n in counts.items()}
    tagged = {word: 1.0 + math.log(n) for word, n in tagged_counts.items()}
    from tessellate.ai import taxonomy

    return _Doc(
        stamp=stamp,
        workspace=str(workspace or "default"),
        category_id=category_id,
        by_hand=bool(by_hand),
        board=bool(board),
        tags=tags,
        words=words,
        tagged=tagged,
        topics=taxonomy.topic_weights(" ".join([content, *tags])),
    )


#: How often the corpus is read whole rather than by what changed. Between
#: full reads only notes whose `updated_at` moved are read, which every ORM
#: write does; a statement that writes round the ORM (a space deleted, its
#: notes moved, which calls `forget_corpus`; a hard purge) is caught here.
FULL_REFRESH_SECONDS = 30.0

_STAMP_COLUMNS = "id, updated_at, tags, category_id, user_filed, is_board, workspace_id"


def _corpus_for(session: Session) -> _Corpus:
    """The kept corpus for this notebook, brought up to date. Call under
    `_corpus_lock`.

    Driver SQL, not an ORM select, on purpose: the corpus is every space's
    notes (the space hook would otherwise narrow it to whichever space the
    first caller had), and `_scope` narrows at read time instead.
    """
    global _corpus
    bind = session.get_bind()
    key = str(getattr(bind, "url", ""))
    if _corpus is None or _corpus.key != key:
        _corpus = _Corpus(key)
    corpus = _corpus
    connection = session.connection()
    now = time.monotonic()
    current: dict[int, tuple] = {}
    if corpus.mark is None or now - corpus.full_at > FULL_REFRESH_SECONDS:
        rows = connection.exec_driver_sql(
            f"SELECT {_STAMP_COLUMNS} FROM entries "  # noqa: S608  # constant columns
            "WHERE is_deleted = 0 AND is_private = 0 ORDER BY id DESC LIMIT ?",
            (MAX_EXAMPLES,),
        ).fetchall()
        current = {int(row[0]): tuple(row[1:]) for row in rows}
        for gone in [entry_id for entry_id in corpus.docs if entry_id not in current]:
            corpus.remove(gone)
        corpus.full_at = now
    else:
        # What moved since the last read, binned and made private included:
        # those leave the corpus. `>=`, so a write in the same instant as the
        # mark is read again rather than missed; its stamp then matches.
        for row in connection.exec_driver_sql(
            f"SELECT {_STAMP_COLUMNS}, is_deleted, is_private FROM entries "  # noqa: S608  # constant columns
            "WHERE updated_at >= ?",
            (corpus.mark,),
        ).fetchall():
            entry_id = int(row[0])
            if row[7] or row[8]:
                corpus.remove(entry_id)
            else:
                current[entry_id] = tuple(row[1:7])
    marks = [stamp[0] for stamp in current.values() if stamp[0] is not None]
    if marks:
        corpus.mark = max([*marks, corpus.mark] if corpus.mark is not None else marks)
    elif corpus.mark is None:
        corpus.mark = ""
    stale = [entry_id for entry_id, stamp in current.items() if (doc := corpus.docs.get(entry_id)) is None or doc.stamp != stamp]
    for start in range(0, len(stale), 500):
        batch = stale[start : start + 500]
        placeholders = ",".join("?" for _ in batch)
        for entry_id, content in connection.exec_driver_sql(
            f"SELECT id, content FROM entries WHERE id IN ({placeholders})", tuple(batch)  # noqa: S608  # placeholders only
        ).fetchall():
            stamp = current[int(entry_id)]
            _updated, raw_tags, category_id, by_hand, board, workspace = stamp
            corpus.add(
                int(entry_id),
                _make_doc(stamp, content or "", _tags(raw_tags), workspace, category_id, by_hand, board),
            )
    # The newest `MAX_EXAMPLES`, as the full read takes them.
    if len(corpus.docs) > MAX_EXAMPLES:
        for entry_id in sorted(corpus.docs)[: len(corpus.docs) - MAX_EXAMPLES]:
            corpus.remove(entry_id)
    return corpus


def _scope(session: Session):  # noqa: ANN202
    """Which kept notes this session may see: its space, or every space not
    hidden from "All spaces", as the space hook decides for an ORM read."""
    workspace = session.info.get("workspace_id")
    if workspace and workspace != "all":
        return lambda doc: doc.workspace == workspace
    hidden = set(session.info.get("hidden_workspaces") or ()) if workspace == "all" else set()
    if hidden:
        return lambda doc: doc.workspace not in hidden
    return lambda doc: True


def _scope_key(session: Session) -> tuple:
    """What `_scope` narrows by, as a key for a kept per-scope sum."""
    workspace = session.info.get("workspace_id")
    return (workspace, tuple(sorted(session.info.get("hidden_workspaces") or ())) if workspace == "all" else ())


def forget_corpus() -> None:
    """Drop the kept corpus (a restore replaced the notebook underneath it)."""
    global _corpus
    with _corpus_lock:
        _corpus = None
