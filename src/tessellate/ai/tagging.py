"""Tag suggestions with no model: one engine for every path (INBOX 440, 781).

The owner: "I want the deterministic engine to be better for when suggesting
tags, both for popup suggestions, when using the 'tag and file with atlas',
and also when making a note". The three paths are the note card's kept
suggestions (`routes_entries._keep_suggestions`), Tag and file with Atlas
(`/entries/{id}/reevaluate`, and the batch act `starter_acts._tag_untagged`)
and Capture while typing (`/entries/suggest-tags`); each asks `suggest`.

What votes for a tag, all from the notebook (WORLD_CLASS 23, decisions 5 and 7):

* **the person's own vocabulary first**: only tags they already use are
  offered while they have any, each in its most used spelling;
* **its words in the note**, folded for plurals, endings and the common
  abbreviations ("stats" is #statistics, "running" is #run), counting more in
  the title and first line, where a note says what it is;
* **the nearest notes' tags** by shared rare words (TF-IDF), and the tags of
  the notes it links to;
* **less for a tag turned down often** across notes (`turned_down`), until
  the person offers it again from the tag manager.

Nothing is read from a quotation, an image's address or an OCR footer
(`clean`), and a tag is offered only where the note has a word for it
(`grounds`): the nearest notes alone gave every note near a lecture "study"
and "university" (the Study bug). Measured on `tests/fixtures/tagging/`
(`tests/test_tag_suggestions.py`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from tessellate.ai import lexical_filing
from tessellate.ai.lexical_filing import clean, tokens

#: At most this many tags offered on a note (decision 5).
TAG_LIMIT = 3
#: How many nearest notes vote, and the least vote that offers a tag.
TAG_NEIGHBOURS = 6
TAG_MIN_VOTE = 0.25
#: A tag the note names outright; more when the title or first line does.
TAG_NAME_VOTE = 0.5
TAG_LEAD_VOTE = 0.8
#: Its words only as another form ("run" for #running, "stats" for
#: #statistics), or only the pack's phrases for what it names ("dear diary"
#: for #journal): too loose to offer alone, enough beside a neighbour's vote.
TAG_FOLDED_VOTE = 0.2
TAG_PHRASE_VOTE = 0.2
#: A tag the notebook has never used is offered only for a subject the note
#: names in this many different phrases ("gym" and "squat" are Fitness; "eggs"
#: alone is not Cooking).
NEW_TOPIC_PHRASES = 2
#: Topics too broad to be a tag beside a specific one.
GENERIC_TOPICS = frozenset({"Education", "Learning", "Study"})
#: The title and first line's words count this many times in the note.
LEAD_WEIGHT = 2.0
#: A tag on a note this one links to, or that links to it.
LINK_VOTE = 0.3
#: Turned down on this many notes, a tag's vote is multiplied by `DAMPED`.
TURNED_DOWN_OFTEN = 3
DAMPED = 0.3
#: Where "Offer again" keeps the count a tag was forgiven at.
PREF_OFFERED_AGAIN = "tags_offered_again"

#: The abbreviations a student's notes use for a subject, folded as `tokens`
#: folds them ("stats" is "stat"). A spelling map, not a classifier: it only
#: lets a tag the person already uses be found under its short name.
ABBREVIATIONS = {
    "stat": "statistic",
    "uni": "university",
    "bio": "biology",
    "chem": "chemistry",
    "math": "mathematic",
    "psych": "psychology",
    "econ": "economic",
    "phys": "physic",
}

def lead(content: str) -> str:
    """The title and first line of a cleaned note: where it says what it is."""
    lines = [line.strip().lstrip("#").strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return ""
    if (content.lstrip().startswith("#") or len(lines[0]) < 60) and len(lines) > 1:
        return f"{lines[0]} {lines[1]}"
    return lines[0]


def stem(word: str) -> str:
    """A word's matching key: `tokens`' plural fold, then a light ending fold
    ("running" and "run", "gaming" and "game"), then the abbreviations."""
    word = ABBREVIATIONS.get(word, word)
    for ending in ("ing", "ed"):
        if len(word) > len(ending) + 2 and word.endswith(ending):
            word = word[: -len(ending)]
            if len(word) > 2 and word[-1] == word[-2] and word[-1] not in "aeiouls":
                word = word[:-1]
            break
    return word[:-1] if len(word) > 3 and word.endswith("e") else word


def stems(words: list[str]) -> set[str]:
    return {stem(word) for word in words}


def tag_words(tag: str) -> list[str]:
    return tokens(tag.replace("/", " ").replace("-", " "))


def tag_stems(tag: str) -> set[str]:
    return stems(tag_words(tag))


def _said(own: str, tag: str) -> list[str]:
    """The note's own spellings of the tag's words ("stats" for #statistics)."""
    wanted = tag_stems(tag)
    said = [word for word in re.findall(r"[a-z0-9]+", own.lower()) if (folded := tokens(word)) and stem(folded[0]) in wanted]
    return list(dict.fromkeys(said))[:2]


def _purpose_grounds(tag: str, content: str) -> list[str]:
    """A tag named for what a note is for ("journal") is backed by the pack's
    phrases for that purpose ("dear diary", "grateful for")."""
    from tessellate.ai import taxonomy

    named = {name for name in taxonomy.functional_categories() if stems(tokens(name)) == tag_stems(tag)}
    if not named:
        return []
    return list(dict.fromkeys(phrase for topic in named for phrase in taxonomy.purpose_hits(content).get(topic, ())))


def grounds(
    tag: str, content: str, hits: dict[str, list[str]] | None = None, note_stems: set[str] | None = None,
    own: str | None = None,
) -> list[str]:
    """What in `content` backs `tag`, or [] when nothing does (decision 5: a
    tag is never proposed on a note that contains none of its words). Every
    word of the tag, folded (`stem`); else the pack phrases of a topic or a
    purpose the tag names ("exam" for #study, Education). Never a word only
    its neighbours share: that vote was the Study bug."""
    from tessellate.ai import taxonomy

    #: `own`: the cleaned text, once per note when many tags are weighed.
    own = clean(content) if own is None else own
    words = tag_words(tag)
    note_stems = stems(tokens(own)) if note_stems is None else note_stems
    if words and all(stem(word) in note_stems for word in words):
        return _said(own, tag) or words
    named = taxonomy.name_topics(tag)
    if not named:
        return _purpose_grounds(tag, own)
    hits = taxonomy.topic_hits(own) if hits is None else hits
    return list(dict.fromkeys(phrase for topic in named for phrase in hits.get(topic, ())))


def reason(tag: str, content: str, hits: dict[str, list[str]] | None = None) -> str:
    """One line for a suggested tag's chip; "" when nothing grounds it."""
    found = grounds(tag, content, hits)
    if not found:
        return ""
    quoted = lexical_filing._quote_list(found[:2])
    if stems(tokens(" ".join(found))) <= tag_stems(tag):
        return f"It says {quoted}."
    return f"It mentions {quoted}."


def grounded(content: str, tags: list[str], limit: int = TAG_LIMIT) -> list[str]:
    """`tags` (a model's or the notebook's) kept only where the note has a
    word for them, in order, at most `limit`."""
    from tessellate.ai import taxonomy

    if not tags:
        return []
    own = clean(content)
    hits = taxonomy.topic_hits(own)
    note_stems = stems(tokens(own))
    return [tag for tag in tags if grounds(tag, content, hits, note_stems, own)][:limit]


@dataclass
class _Ask:
    """One note's words, read once for every vote."""

    words: list[str]
    lead_stems: set[str]
    note_stems: set[str]
    content: str
    #: The pack's topics the note names ("squats" is Fitness).
    hits: dict[str, list[str]]


def _read(content: str) -> _Ask:
    own = clean(content)
    words = tokens(own)
    from tessellate.ai import taxonomy

    return _Ask(
        words=words, lead_stems=stems(tokens(lead(own))), note_stems=stems(words), content=own,
        hits=taxonomy.topic_hits(own),
    )


def _query_bag(ask: _Ask) -> dict[str, float]:
    bag: dict[str, float] = {}
    for word in ask.words:
        bag[word] = bag.get(word, 0.0) + (LEAD_WEIGHT if stem(word) in ask.lead_stems else 1.0)
    return bag


def _key(tag: str) -> str:
    """One tag's folded key: "Assignment" and "assignments" are one tag."""
    return " ".join(sorted(tag_stems(tag))) or tag.casefold()


@dataclass
class _Vocab:
    """The person's tags: each by its key in its most used spelling, how many
    notes carry it, which tags it is used with, and the pack topics it names."""

    spelled: dict[str, str]
    uses: dict[str, int]
    together: dict[str, dict[str, int]]
    topics: dict[str, set[str]]

    def alternatives(self, one: str, other: str) -> bool:
        """Two tags for one topic that a note seldom carries together
        (#exam and #lecture), not a pair used as one (#gym and #legs)."""
        both = self.together.get(one, {}).get(other, 0)
        return one != other and both * 2 < min(self.uses.get(one, 0), self.uses.get(other, 0))


def _vocabulary(docs: list) -> _Vocab:
    from tessellate.ai import taxonomy

    spellings: dict[str, dict[str, int]] = {}
    together: dict[str, dict[str, int]] = {}
    for _id, doc in docs:
        keys = {_key(tag) for tag in doc.tags}
        for tag in doc.tags:
            spelled = spellings.setdefault(_key(tag), {})
            spelled[tag] = spelled.get(tag, 0) + 1
        for key in keys:
            pairs = together.setdefault(key, {})
            for other in keys - {key}:
                pairs[other] = pairs.get(other, 0) + 1
    spelled = {key: max(names, key=lambda tag: (names[tag], tag.islower())) for key, names in spellings.items()}
    return _Vocab(
        spelled=spelled,
        uses={key: sum(names.values()) for key, names in spellings.items()},
        together=together,
        topics={key: set(taxonomy.name_topics(tag)) for key, tag in spelled.items()},
    )


def _neighbour_votes(corpus, ask: _Ask, docs: list) -> dict[str, float]:  # noqa: ANN001
    votes: dict[str, float] = {}
    for similarity, doc in corpus.nearest(_query_bag(ask), "words", docs)[:TAG_NEIGHBOURS]:
        for tag in doc.tags:
            votes[_key(tag)] = votes.get(_key(tag), 0.0) + similarity
    return votes


def _said_outright(ask: _Ask, tag: str) -> bool:
    wanted = tag_stems(tag)
    return bool(wanted) and wanted <= ask.note_stems


def _owns_topic(vocab: _Vocab, key: str, topic: str) -> bool:
    """No alternative of `key` names `topic`: a phrase of it ("seminar") can
    say this tag rather than another (#exam, #lecture and #assignment all
    name Education, so it backs none of them)."""
    return not any(topic in vocab.topics[other] and vocab.alternatives(key, other) for other in vocab.topics)


def _name_vote(ask: _Ask, vocab: _Vocab, key: str) -> float:
    tag = vocab.spelled[key]
    words = tag_words(tag)
    if not words:
        return 0.0
    if _said_outright(ask, tag):
        if not set(words) <= set(ask.words):
            return TAG_FOLDED_VOTE
        return TAG_LEAD_VOTE if stems(words) <= ask.lead_stems else TAG_NAME_VOTE
    named = vocab.topics[key]
    if any(ask.hits.get(topic) and _owns_topic(vocab, key, topic) for topic in named):
        return TAG_PHRASE_VOTE
    return TAG_PHRASE_VOTE if not named and _purpose_grounds(tag, ask.content) else 0.0


def _name_votes(ask: _Ask, vocab: _Vocab, votes: dict[str, float]) -> set[str]:
    """Add each tag's own vote; the keys that have one."""
    own: set[str] = set()
    for key in vocab.spelled:
        if vote := _name_vote(ask, vocab, key):
            votes[key] = votes.get(key, 0.0) + vote
            own.add(key)
    return own


def _rides_a_sibling(ask: _Ask, vocab: _Vocab, key: str, said: list[str]) -> bool:
    """A tag the note does not say, for a topic a tag it does say already
    holds, and the two seldom go together: "lecture" said, #exam and
    #assignment are not offered on its strength (the Study bug's sibling
    shape); "legs" said, #gym still is, the two being used as one."""
    return any(
        vocab.topics.get(key, set()) & vocab.topics.get(other, set()) and vocab.alternatives(key, other)
        for other in said
    )


def _link_votes(session: Session, corpus, entry_id: int | None, votes: dict[str, float]) -> None:  # noqa: ANN001
    if entry_id is None:
        return
    from tessellate.core.database import EntryLink

    rows = session.execute(
        select(EntryLink.source_entry_id, EntryLink.target_entry_id).where(
            or_(EntryLink.source_entry_id == entry_id, EntryLink.target_entry_id == entry_id)
        )
    ).all()
    for source, target in rows:
        doc = corpus.docs.get(target if source == entry_id else source)
        for tag in doc.tags if doc else ():
            votes[_key(tag)] = votes.get(_key(tag), 0.0) + LINK_VOTE


def turned_down(session: Session) -> dict[str, tuple[str, int]]:
    """Each tag turned down on notes, by its folded key: its spelling and on
    how many notes, less the count it had when the person offered it again."""
    counts: dict[str, tuple[str, int]] = {}
    rows = session.execute(
        text("SELECT discarded_tags FROM entries WHERE is_deleted = 0 AND discarded_tags NOT IN ('', '[]')")
    ).scalars()
    for raw in rows:
        try:
            tags = json.loads(raw or "[]")
        except (TypeError, ValueError):
            continue
        for tag in {str(tag) for tag in tags if tag} if isinstance(tags, list) else ():
            spelled, seen = counts.get(_key(tag), (tag, 0))
            counts[_key(tag)] = (spelled, seen + 1)
    forgiven = _offered_again()
    return {key: (tag, n - int(forgiven.get(key, 0))) for key, (tag, n) in counts.items() if n > int(forgiven.get(key, 0))}


def _offered_again() -> dict:
    try:
        from tessellate.core import deps

        value = deps.get_config().get_preference(PREF_OFFERED_AGAIN, {})
    except Exception:  # noqa: BLE001 - no config (a script, a test without app state): none forgiven
        return {}
    return value if isinstance(value, dict) else {}


def offer_again(session: Session, tag: str) -> None:
    """Undo the learning for `tag`: its turn-downs so far stop counting."""
    from tessellate.core import deps

    key = _key(tag)
    forgiven = dict(_offered_again())
    forgiven[key] = int(forgiven.get(key, 0)) + turned_down(session).get(key, (tag, 0))[1]
    deps.get_config().set_preference(PREF_OFFERED_AGAIN, forgiven)


def _damp(session: Session, votes: dict[str, float]) -> None:
    for key, (_tag, notes) in turned_down(session).items():
        if key in votes and notes >= TURNED_DOWN_OFTEN:
            votes[key] *= DAMPED


def _subsumed(key: str, taken: list[str], have_keys: set[str]) -> bool:
    """A tag already on the note in another spelling, or one whose words are
    all inside a tag taken or held ("ideas" beside "app idea")."""
    words = set(key.split())
    return key in have_keys or any(words <= set(other.split()) for other in [*taken, *have_keys])


def suggest(
    session: Session,
    content: str,
    have: list[str],
    exclude_entry_id: int | None = None,
    limit: int = TAG_LIMIT,
) -> list[str]:
    """Tags this note probably wants, from the notebook's own, best first,
    each one the note has a word for; [] when nothing is close enough."""
    ask = _read(content)
    if not ask.words:
        return []
    with lexical_filing._corpus_lock:
        corpus = lexical_filing._corpus_for(session)
        scope = lexical_filing._scope(session)
        docs = [(i, doc) for i, doc in corpus.docs.items() if doc.tags and i != exclude_entry_id and scope(doc)]
        if not docs:
            return []
        votes = _neighbour_votes(corpus, ask, docs)
        vocab = _vocabulary(docs)
        _link_votes(session, corpus, exclude_entry_id, votes)
    own = _name_votes(ask, vocab, votes)
    _damp(session, votes)
    ranked = sorted((key for key in votes if key in vocab.spelled and votes[key] >= TAG_MIN_VOTE), key=votes.get, reverse=True)
    return [vocab.spelled[key] for key in _choose(ask, vocab, ranked, own, have)[:limit]]


def _choose(ask: _Ask, vocab: _Vocab, ranked: list[str], own: set[str], have: list[str]) -> list[str]:
    """The ranked keys worth offering, in order. Not said outright, a tag
    needs a vote of its own (a folded word, a phrase only it names), not just
    its neighbours', and no sibling the note does say."""
    have_keys = {_key(tag) for tag in have}
    said = [key for key in [*ranked, *have_keys] if key in vocab.spelled and _said_outright(ask, vocab.spelled[key])]
    taken: list[str] = []
    for key in grounded_keys(ask.content, ranked, vocab.spelled):
        if not _said_outright(ask, vocab.spelled[key]) and (key not in own or _rides_a_sibling(ask, vocab, key, said)):
            continue
        if not _subsumed(key, taken, have_keys):
            taken.append(key)
    return taken


def grounded_keys(content: str, keys: list[str], vocabulary: dict[str, str]) -> list[str]:
    kept = set(grounded(content, [vocabulary[key] for key in keys], limit=len(keys)))
    return [key for key in keys if vocabulary[key] in kept]


def filled(session: Session, content: str, tags: list[str], have: list[str], limit: int = TAG_LIMIT) -> list[str]:
    """`tags` (the notebook's own, a model's) with any room left filled by
    subjects the notebook has never tagged (B80)."""
    room = limit - len(tags)
    return [*tags, *new_topics(session, content, [*have, *tags])[:room]] if room > 0 else tags


def _named_topics(content: str) -> dict[str, int]:
    """The pack's topics `content` names in enough different phrases, with
    their phrase counts; a sensitive subject is left out, and so is a generic
    one (Education) when the note names a subject of its own."""
    from tessellate.ai import taxonomy

    sensitive = taxonomy.sensitive_topics()
    named = {
        topic: len(set(phrases)) for topic, phrases in _read(content).hits.items()
        if topic not in sensitive and not re.search(r"[&/]", topic) and len(set(phrases)) >= NEW_TOPIC_PHRASES
    }
    #: Every note in a student's notebook is "education": it is offered only
    #: when the note names no subject of its own (Mathematics, Biology).
    if any(topic not in GENERIC_TOPICS for topic in named):
        named = {topic: n for topic, n in named.items() if topic not in GENERIC_TOPICS}
    return named


def new_topics(session: Session, content: str, taken: list[str]) -> list[str]:
    """Tags for the subjects `content` names (the pack's topics, in at least
    `NEW_TOPIC_PHRASES` different phrases, most phrases first) that the
    notebook has not used and `taken` does not hold: the new-tag suggestions
    with no model to coin one. A sensitive subject (an illness, a debt) is
    never offered as a tag the person did not choose."""
    named = _named_topics(content)
    if not named:
        return []
    with lexical_filing._corpus_lock:
        scope = lexical_filing._scope(session)
        used = {_key(tag) for doc in lexical_filing._corpus_for(session).docs.values() if scope(doc) for tag in doc.tags}
    skip = used | {_key(tag) for tag in taken}
    tags = [topic.casefold().replace(" ", "-") for topic in sorted(named, key=named.get, reverse=True)]
    return [tag for tag in tags if _key(tag) not in skip]


def merged(first: list[str], then: list[str], have: list[str], limit: int = TAG_LIMIT) -> list[str]:
    """A model's grounded tags, then the engine's, one spelling each, none
    the note has."""
    out: list[str] = []
    seen = {_key(tag) for tag in have}
    for tag in [*first, *then]:
        if _key(tag) not in seen:
            seen.add(_key(tag))
            out.append(tag)
    return out[:limit]


