"""The taxonomy pack: everyday words to the topics they belong to, as seed
data for filing (WORLD_CLASS_PLAN 23, decision 1).

The data is the owner's consolidated pack (5.0.0: 527 categories, 512 topics
and 15 note purposes, 6,478 phrase assignments; 1,109 roles; 44 institutions;
facets and 30 context rules kept as specification) under `data/taxonomy/`,
read on first use rather than at import (WORLD_CLASS 26, decision 56). It is
**candidate generation only**: it says which topics a note's words name and
by which phrases, and filing (`lexical_filing`) decides, the person's own
categories first. Nothing here files a note, names a category the person
does not have, or infers anything about the person (a role mentioned is not
a job held; a university named is not an enrolment).

The API is the pack's own (`analyze_note`, `extract_categories`,
`extract_occupations`, `extract_entities`, `reset_taxonomy_processors`,
`reload_taxonomy`), so its tests came with it (`tests/test_taxonomy_pack.py`).
It replaces the Gemini branch's 18-category map; that map's vocabulary is
inside the pack, preserved word for word (the pack's own test). Matching is
the vendored FlashText (`tessellate.vendor.flashtext`, MIT): whole words and
phrases, case folded, longest first, one pass over the text. The pack's
regex fallback for a missing FlashText is not carried, since the vendored copy
is always there.

Scoring, from the pack: distinct phrases count once; a weak (polysemous)
phrase scores 0.5, any other 2, split evenly among the topics that share it;
a topic needs 1.5 and either one strong phrase or two weak ones.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from tessellate.vendor.flashtext import KeywordProcessor

DATA_DIR = Path(__file__).with_name("data") / "taxonomy"
MATCHER_BACKEND = "vendored-flashtext"

#: The display prefix for a note purpose in `extract_dynamic_categories`.
PREFIX_LABELS = {
    "Projects": "Project", "Journal": "Journal", "Reference": "Reference",
    "Brainstorming": "Idea", "Meetings": "Meeting", "Research": "Research",
    "Decisions": "Decision", "Goals": "Goal",
}

#: Curly quotes and the dashes to plain ones, by code point so this file
#: carries none of them (`tests/test_no_em_dashes.py`).
_TRANSLATE = str.maketrans({
    **{chr(c): "'" for c in (0x2019, 0x2018)},
    **{chr(c): '"' for c in (0x201C, 0x201D)},
    **{chr(c): "-" for c in (0x2013, 0x2014, 0x2011, 0x2010, 0x2212)},
})


def _read(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


#: Pack phrases kept in code, not in `memorymap_taxonomy.json`, so the data
#: files hold no work-marker words (L-chat-243). `_data()` merges them back, so
#: the live map matches the same phrases to the same topics; the pack's phrase
#: set is the file plus these (`tests/test_relocated_phrases.py`).
RELOCATED_PHRASES: dict[str, tuple[str, ...]] = {
    "Projects": ("todo",),
    "Meetings": ("follow-up meeting",),
    "University Administration": ("deferred exam",),
    "Client & Customer Management": ("customer follow-up",),
    "Networking & Professional Contacts": ("contact follow-up",),
    "Questions & Problems": ("open question",),
    "Reminders & Follow-Ups": ("follow-up reminder", "follow-up task", "follow-up date"),
}

#: The facets file's `Check Back` action: the specification's own name for it
#: (the value's first item) and the phrases it gives it besides the file's.
_FACET_RENAMED = {"Check Back": ("Follow Up", ("follow up", "follow-up"))}


def facet_actions() -> dict[str, list[str]]:
    """The facets specification's actions with their phrases, as the pack
    gave them (nothing in the app matches on these yet)."""
    out: dict[str, list[str]] = {}
    for name, phrases in _read("memorymap_facets.json")["actions"].items():
        label, lead = _FACET_RENAMED.get(name, (name, ()))
        out[label] = [*lead, *phrases]
    return out


@lru_cache(maxsize=1)
def _data() -> dict:
    """The pack, with Tessellate's reviewed everyday vocabulary merged into its
    topics (`memorymap_everyday.json`: words the pack's formal phrases miss,
    INBOX 1297). The pack file itself is never edited."""
    pack = _read("memorymap_taxonomy.json")
    extra = _read("memorymap_everyday.json")
    pack["taxonomy"] = merge_taxonomy(merge_taxonomy(pack["taxonomy"], {k: list(v) for k, v in RELOCATED_PHRASES.items()}), extra["terms"])
    pack["weak_terms"] = list(dict.fromkeys([*pack["weak_terms"], *extra.get("weak", [])]))
    return pack


def taxonomy_map() -> dict[str, list[str]]:
    """Topic or purpose label to its phrases. Mutable on purpose, as the
    pack's `TAXONOMY_MAP` was: an edit takes effect after
    `reset_taxonomy_processors()`."""
    return _data()["taxonomy"]


def functional_priority() -> tuple[str, ...]:
    return tuple(_data()["functional_categories"])


def functional_categories() -> frozenset[str]:
    return _functional()


@lru_cache(maxsize=1)
def _functional() -> frozenset[str]:
    return frozenset(_data()["functional_categories"])


def weak_terms() -> frozenset[str]:
    return _weak_terms()


@lru_cache(maxsize=1)
def _weak_terms() -> frozenset[str]:
    return frozenset(_data()["weak_terms"])


def category_groups() -> dict[str, str]:
    return _data()["category_groups"]


#: The pack's groups that say where a topic came from or what a note is for,
#: not what it is about: "Original Coverage" holds Sports, Education, Finance
#: and 46 more, so as a parent it would make every topic a sibling of every
#: other (INBOX 1583, measured: 10 of 12 mixed notes right without it, 3 with).
_NOT_PARENTS = frozenset({"Original Coverage", "Note Purposes"})


def parent_of(topic: str) -> str | None:
    """The subject group a topic belongs to ("Sleep": Health & Wellbeing), or None."""
    group = category_groups().get(topic)
    return None if group in _NOT_PARENTS else group


@lru_cache(maxsize=1)
def _children() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for topic, group in category_groups().items():
        if group not in _NOT_PARENTS:
            out.setdefault(group.casefold(), []).append(topic)
    return {group: tuple(topics) for group, topics in out.items()}


def children_of(group: str) -> tuple[str, ...]:
    """The topics under a subject group named in any case ("leisure"), or ()."""
    return _children().get((group or "").strip().casefold(), ())


def __getattr__(name: str) -> Any:
    """The pack's module-level names, read lazily so importing this module
    reads no data (decision 56)."""
    lazy = {
        "TAXONOMY_MAP": taxonomy_map,
        "TAXONOMY_VERSION": lambda: _data()["version"],
        "CATEGORY_GROUPS": category_groups,
        "FUNCTIONAL_CATEGORIES": functional_categories,
        "FUNCTIONAL_PRIORITY": functional_priority,
        "WEAK_TERMS": weak_terms,
    }
    if name in lazy:
        return lazy[name]()
    raise AttributeError(name)


def normalize_text(text: str) -> str:
    """Unicode and whitespace normalised. Offsets refer to this text."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).translate(_TRANSLATE)).strip()


@lru_cache(maxsize=1)
def _keyword_index() -> dict[str, tuple[str, ...]]:
    result: dict[str, set[str]] = defaultdict(set)
    for category, keywords in taxonomy_map().items():
        for keyword in keywords:
            key = normalize_text(keyword).lower()
            if key:
                result[key].add(category)
    return {key: tuple(sorted(categories)) for key, categories in result.items()}


@lru_cache(maxsize=1)
def get_keyword_processor() -> KeywordProcessor:
    processor = KeywordProcessor(case_sensitive=False)
    for keyword in _keyword_index():
        processor.add_keyword(keyword, keyword)
    return processor


@lru_cache(maxsize=1)
def get_taxonomy_processor() -> KeywordProcessor:
    """Each match's payload is a JSON array of every category for the phrase."""
    processor = KeywordProcessor(case_sensitive=False)
    for keyword, categories in _keyword_index().items():
        processor.add_keyword(keyword, json.dumps(categories))
    return processor


def reset_taxonomy_processors() -> None:
    """Rebuild the matchers after an in-memory edit of `taxonomy_map()`."""
    _keyword_index.cache_clear()
    get_keyword_processor.cache_clear()
    get_taxonomy_processor.cache_clear()
    _weak_terms.cache_clear()
    _functional.cache_clear()
    _labels.cache_clear()
    _name_topics.cache_clear()


def extract_keywords(text: str) -> list[str]:
    """Matched phrases in order of occurrence, repetitions kept."""
    return get_keyword_processor().extract_keywords(normalize_text(text))


def extract_categories(text: str) -> list[str]:
    """Raw category evidence in order of occurrence, repetitions kept; a
    shared phrase emits each of its categories. No score filtering."""
    result: list[str] = []
    for payload in get_taxonomy_processor().extract_keywords(normalize_text(text)):
        result.extend(json.loads(payload))
    return result


def _analyze_topics(
    text: str, *, min_score: float = 1.5, max_topics: int | None = 5,
    title: str = "", title_boost: float = 1.25,
) -> dict:
    """Explainable heuristic suggestions, not a semantic classification. No
    negation, scope or intent; not for diagnosis or profiling."""
    if min_score < 0 or title_boost < 1:
        raise ValueError("min_score >= 0 and title_boost >= 1 required")
    if max_topics is not None and max_topics < 0:
        raise ValueError("max_topics must be nonnegative or None")
    index = _keyword_index()
    weak_set = _weak_terms()
    functions_set = functional_categories()
    priority = functional_priority()
    processor = get_keyword_processor()
    body_hits = processor.extract_keywords(normalize_text(text), span_info=True)
    title_hits = processor.extract_keywords(normalize_text(title), span_info=True)
    keywords = list(dict.fromkeys([k for k, _, _ in title_hits + body_hits]))
    in_title = {k for k, _, _ in title_hits}
    scores: dict[str, float] = defaultdict(float)
    evidence: dict[str, list[dict]] = defaultdict(list)
    for keyword in keywords:
        categories = index[keyword]
        weak = keyword in weak_set
        weight = (0.5 if weak else 2.0) / len(categories)
        if keyword in in_title:
            weight *= title_boost
        for category in categories:
            scores[category] += weight
            evidence[category].append({
                "keyword": keyword, "weight": round(weight, 4), "weak": weak, "in_title": keyword in in_title,
            })
    ranked = sorted(scores, key=lambda c: (-scores[c], c.casefold()))
    accepted = [
        c for c in ranked
        if scores[c] >= min_score and (any(not item["weak"] for item in evidence[c]) or len(evidence[c]) >= 2)
    ]
    topics = [c for c in accepted if c not in functions_set]
    functions = [c for c in accepted if c in functions_set]
    functions.sort(key=lambda c: (-scores[c], priority.index(c)))
    if max_topics is not None:
        topics = topics[:max_topics]
    return {
        "taxonomy_version": _data()["version"], "backend": MATCHER_BACKEND,
        "topics": topics, "functions": functions,
        "scores": {c: round(scores[c], 4) for c in ranked},
        "evidence": {c: evidence[c] for c in ranked},
        "keywords": keywords,
        "matches": [
            {"keyword": k, "start": start, "end": end, "field": field}
            for field, hits in (("title", title_hits), ("body", body_hits))
            for k, start, end in hits
        ],
        "offset_space": "normalized_text", "abstained": not accepted,
    }


def extract_dynamic_categories(text: str) -> list[str]:
    """The pack's legacy display labels ("Fitness & Health", "Project: ...").
    Display only: filing never makes a category from these (decision 2)."""
    analysis = analyze_note(text)
    topics, functions = analysis["topics"], analysis["functions"]
    if not topics:
        return functions
    display = " & ".join(sorted(topics[:2], key=str.casefold))
    result = [display]
    if functions:
        result.append(f"{PREFIX_LABELS[functions[0]]}: {display}")
    return result


def audit_taxonomy() -> dict:
    index = _keyword_index()
    duplicates = {}
    for category, keywords in taxonomy_map().items():
        counter = Counter(normalize_text(k).lower() for k in keywords)
        repeated = [k for k, count in counter.items() if count > 1]
        if repeated:
            duplicates[category] = repeated
    return {
        "category_count": len(taxonomy_map()),
        "category_keyword_assignments": sum(map(len, taxonomy_map().values())),
        "unique_keyword_count": len(index),
        "shared_keywords": {k: list(v) for k, v in index.items() if len(v) > 1},
        "duplicates_within_categories": duplicates,
    }


@lru_cache(maxsize=1)
def _occupation_data() -> dict:
    return _read("memorymap_occupations.json")["roles"]


@lru_cache(maxsize=1)
def _occupation_processor() -> KeywordProcessor:
    aliases: dict[str, set[str]] = defaultdict(set)
    for role_id, role in _occupation_data().items():
        for alias in role["aliases"]:
            aliases[normalize_text(alias).lower()].add(role_id)
    processor = KeywordProcessor(case_sensitive=False)
    for alias, ids in aliases.items():
        processor.add_keyword(alias, json.dumps(sorted(ids)))
    return processor


_JOB_CONTEXT = re.compile(
    r"\b(?:job|jobs|career|occupation|employed|employment|hiring|recruitment|"
    r"position|vacancy|salary|profession|professional|works?\s+as)\b",
    re.I,
)


def extract_occupations(text: str, *, require_job_context: bool = False) -> list[dict]:
    """Role titles mentioned, never a fact about who holds them. The job
    context gate is document-level, not word sense."""
    text = normalize_text(text)
    if require_job_context and not _JOB_CONTEXT.search(text):
        return []
    result = []
    for payload, start, end in _occupation_processor().extract_keywords(text, span_info=True):
        for role_id in json.loads(payload):
            role = _occupation_data()[role_id]
            result.append({
                "role_id": role_id, "label": role["label"], "family": role["family"],
                "surface": text[start:end], "start": start, "end": end,
                "offset_space": "normalized_text", "resolution": "lexical_mention",
                "personal_occupation_inferred": False,
            })
    return result


@lru_cache(maxsize=1)
def _bundled_entities() -> dict:
    return _read("memorymap_entities.json")["entities"]


_EDUCATION_CONTEXT = re.compile(
    r"\b(?:university|universities|campus|lecture|degree|student|"
    r"assignment|semester|scholarship|enrolment|enrollment)\b",
    re.I,
)


def extract_entities(text: str, *, user_entities: list[dict] | None = None) -> list[dict]:
    """Bundled institutions and the person's reviewed aliases mentioned in
    the text; no discovery. A short university acronym needs an education
    word nearby in the document; a user alias marked `requires_context` is
    an unresolved candidate, never a relationship."""
    text = normalize_text(text)
    entries = dict(_bundled_entities())
    for record in user_entities or []:
        if record.get("status") != "accepted" or not record.get("reviewed", False):
            continue
        entity_id = record.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ValueError("reviewed user entity requires entity_id")
        if entity_id in entries:
            raise ValueError("user entity id collides with bundled entity id")
        if not isinstance(record.get("label"), str) or not record["label"].strip():
            raise ValueError("reviewed user entity requires label")
        aliases = record.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
            raise TypeError("aliases must be a list of strings")
        entries[entity_id] = record
    by_alias: dict[str, set[str]] = defaultdict(set)
    for entity_id, record in entries.items():
        for alias in record["aliases"]:
            alias = normalize_text(alias).lower()
            if alias:
                by_alias[alias].add(entity_id)
    processor = KeywordProcessor(case_sensitive=False)
    for alias, ids in by_alias.items():
        processor.add_keyword(alias, json.dumps({"alias": alias, "ids": sorted(ids)}))
    context = bool(_EDUCATION_CONTEXT.search(text))
    result = []
    for payload, start, end in processor.extract_keywords(text, span_info=True):
        hit = json.loads(payload)
        for entity_id in hit["ids"]:
            record = entries[entity_id]
            alias = hit["alias"]
            if record.get("type") == "university" and " " not in alias and len(alias) <= 5 and not context:
                continue
            result.append({
                "entity_id": entity_id, "label": record["label"],
                "type": record.get("type", "organisation"), "alias": alias,
                "start": start, "end": end, "offset_space": "normalized_text",
                "resolution": "candidate_ambiguous_alias" if len(hit["ids"]) > 1
                else "candidate_requires_context" if record.get("requires_context", False)
                else "lexical_mention",
                "entity_status": record.get("status", "unknown"),
                "affiliation_inferred": False,
            })
    return result


def analyze_note(
    text: str, *, min_score: float = 1.5, max_topics: int | None = 8,
    title: str = "", title_boost: float = 1.25,
    include_occupations: bool = True, include_entities: bool = True,
    user_entities: list[dict] | None = None,
) -> dict:
    """Topics, purposes, role and institution mentions for one note, each
    with its evidence. No context, sense or claim extraction."""
    result = _analyze_topics(text, min_score=min_score, max_topics=max_topics, title=title, title_boost=title_boost)
    result["occupations"] = []
    result["entities"] = []
    for field, value in (("title", title), ("body", text)):
        if include_occupations:
            result["occupations"].extend(dict(hit, field=field) for hit in extract_occupations(value))
        if include_entities:
            result["entities"].extend(
                dict(hit, field=field) for hit in extract_entities(value, user_entities=user_entities)
            )
    result["personal_attributes_inferred"] = False
    result["context_engine_implemented"] = False
    result["abstained_topics"] = result["abstained"]
    return result


def reload_taxonomy() -> None:
    """Read the JSON again after editing it; not while matching."""
    _data.cache_clear()
    _occupation_data.cache_clear()
    _occupation_processor.cache_clear()
    _bundled_entities.cache_clear()
    reset_taxonomy_processors()


def context_rules() -> dict:
    """The pack's 30 word-sense seed rules: specification for the phase after
    (decision 9), not executed here."""
    return _read("memorymap_context_rules.json")


# --- reviewed vocabulary (the pack's `memorymap_lexicon.py`) ----------------
# Explicitly reviewed vocabulary only; nothing is learned from raw notes.


def _normalize_term(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("term or alias must be a string")
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def merge_taxonomy(existing: dict, extra: dict) -> dict:
    result = deepcopy(existing)
    for category, terms in extra.items():
        if not isinstance(category, str) or not isinstance(terms, list):
            raise TypeError("taxonomy must map string labels to term lists")
        cleaned = [_normalize_term(t) for t in terms]
        result[category] = list(dict.fromkeys(result.get(category, []) + [t for t in cleaned if t]))
    return result


def build_alias_index(reviewed_entries: list[dict]) -> dict[str, list[str]]:
    """A collision-preserving alias index, not entity disambiguation."""
    result: dict[str, set[str]] = defaultdict(set)
    for entry in reviewed_entries:
        if entry.get("status") != "accepted" or not entry.get("reviewed", False):
            continue
        entity_id = entry.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ValueError("accepted entity needs entity_id")
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            raise TypeError("aliases must be a list")
        for alias in aliases:
            key = _normalize_term(alias)
            if key:
                result[key].add(entity_id)
    return {key: sorted(ids) for key, ids in result.items()}


def merge_reviewed_topic_terms(existing: dict, reviewed_entries: list[dict]) -> dict:
    """Add only accepted, unconditional aliases to known labels; a term that
    needs context stays out of the flat map."""
    result = deepcopy(existing)
    for entry in reviewed_entries:
        if entry.get("status") != "accepted" or not entry.get("reviewed", False):
            continue
        if entry.get("requires_context", True):
            continue
        term = _normalize_term(entry.get("term"))
        if not term:
            raise ValueError("term must not be empty")
        categories = entry.get("categories", [])
        if not isinstance(categories, list) or any(not isinstance(c, str) for c in categories):
            raise TypeError("categories must be a list of strings")
        for category in categories:
            if category not in result:
                raise ValueError(f"unknown topic: {category}")
        for category in categories:
            result[category] = list(dict.fromkeys(result[category] + [term]))
    return result


# --- what filing reads (WORLD_CLASS_PLAN 23, decisions 2, 5 and 6) ----------
# `memorymap_filing.json` is Tessellate's own, beside the pack: the topics
# that are sensitive, and everyday category names the pack's phrases miss.


@lru_cache(maxsize=1)
def _filing_data() -> dict:
    return _read("memorymap_filing.json")


def sensitive_topics() -> frozenset[str]:
    """Health, relationships, money, the law and identity (decision 6)."""
    return frozenset(_filing_data()["sensitive_topics"])


def topic_hits(text: str) -> dict[str, list[str]]:
    """Each subject topic the text's phrases name, with those phrases in
    order of first mention. Note purposes ("Projects", "Journal") are left
    out: they say how a note is used, not what it is about, so they are never
    a category's subject (the "Study" bug's other half)."""
    return _hits(text, purposes=False)


def purpose_hits(text: str) -> dict[str, list[str]]:
    """`topic_hits` for the purposes only ("Journal": "dear diary"): what a
    tag named for a note's use is backed by (`ai/tagging.grounds`)."""
    return _hits(text, purposes=True)


def _hits(text: str, purposes: bool) -> dict[str, list[str]]:
    index = _keyword_index()
    purpose_names = functional_categories()
    found: dict[str, list[str]] = {}
    normalized = normalize_text(text or "")
    processor = get_keyword_processor()
    #: The pack's phrases are mostly singular ("squat", "deadlift"), so the
    #: text is matched as written and once more with its plurals folded:
    #: "squats and deadlifts" named nothing before.
    matched = processor.extract_keywords(normalized) + processor.extract_keywords(_fold_plurals(normalized))
    seen: set[str] = set()
    for keyword in dict.fromkeys(matched):
        #: "unit tests" and its folded "unit test" are one phrase said once.
        folded = _fold_plurals(keyword)
        if folded in seen:
            continue
        seen.add(folded)
        for topic in index[keyword]:
            if (topic in purpose_names) == purposes:
                found.setdefault(topic, []).append(keyword)
    return found


@lru_cache(maxsize=1)
def _related() -> tuple[dict[str, tuple[str, ...]], float]:
    """Source topic to the topics a person's category is likelier to be named
    for, and the share of a hit that counts toward them (Q29, owner
    2026-11-11). Reviewed by hand in `memorymap_related.json`; the pack's
    groups cannot derive it (its core topics all sit in "Original Coverage")."""
    data = _read("memorymap_related.json")
    return {src: tuple(targets) for src, targets in data["related"].items()}, float(data["factor"])


def _with_related(weights: dict[str, float]) -> dict[str, float]:
    """`weights` with each hit topic also counting, at the table's share,
    toward its related topics (never lowering one the text named itself):
    a gardening note reads a little as Home, a therapy note as Health."""
    related, share = _related()
    out = dict(weights)
    for topic, weight in weights.items():
        for target in related.get(topic, ()):
            out[target] = max(out.get(target, 0.0), weight * share)
    return out


def topic_weights(text: str, hits: dict[str, list[str]] | None = None) -> dict[str, float]:
    """The pack's own score per subject topic, unthresholded: a phrase is
    worth 2 (0.5 when weak), split among the topics that share it. A hit on a
    related topic also counts half toward its target (`_with_related`)."""
    return _with_related(_pack_weights(text, hits))


def _pack_weights(text: str, hits: dict[str, list[str]] | None = None) -> dict[str, float]:
    index = _keyword_index()
    weak = _weak_terms()
    purposes = functional_categories()
    weights: dict[str, float] = {}
    for topic, phrases in (topic_hits(text) if hits is None else hits).items():
        for phrase in phrases:
            owners = [t for t in index[phrase] if t not in purposes] or [topic]
            weights[topic] = weights.get(topic, 0.0) + (0.5 if phrase in weak else 2.0) / len(owners)
    return weights


def strong_topics(text: str, hits: dict[str, list[str]] | None = None) -> dict[str, float]:
    """The subject topics the pack itself would accept for this text (score
    at least 1.5, and one strong phrase or two weak ones), best first."""
    hits = topic_hits(text) if hits is None else hits
    weights = _pack_weights(text, hits)
    weak = _weak_terms()
    accepted = {
        topic: score for topic, score in weights.items()
        if score >= 1.5 and (any(p not in weak for p in hits[topic]) or len(hits[topic]) >= 2)
    }
    accepted = _with_related(accepted)
    return dict(sorted(accepted.items(), key=lambda pair: (-pair[1], pair[0].casefold())))


_PLURAL = re.compile(r"\b([A-Za-z]{3,}?)(ies|s)\b")


def _fold_plurals(text: str) -> str:
    def fold(match: re.Match) -> str:
        stem, ending = match.group(1), match.group(2)
        if ending == "ies":
            return stem + "y" if len(stem) >= 2 else match.group(0)
        if stem[-1:].lower() in ("s", "u", "i"):
            return match.group(0)
        return stem

    return _PLURAL.sub(fold, text)


_NAME_SPLIT = re.compile(r"\s*(?:&|\+|/|,|\band\b)\s*", re.I)


def name_topics(name: str) -> dict[str, float]:
    """The topics a category's own name points to: its phrases ("Gym" is
    Fitness), a topic it names outright ("Home", "Fitness & health"), or an
    everyday name from `memorymap_filing.json` ("Car", "Uni", "Money").
    Each part of a composite name counts ("Films & TV"). A copy: the kept
    answer is shared."""
    return dict(_name_topics(name or "") or _parent_topics(name or ""))


@lru_cache(maxsize=1)
def _labels() -> dict[str, str]:
    purposes = functional_categories()
    return {label.casefold(): label for label in taxonomy_map() if label not in purposes}


@lru_cache(maxsize=512)
def _name_topics(name: str) -> dict[str, float]:
    labels = _labels()
    aliases = _filing_data()["name_aliases"]
    found: dict[str, float] = dict(topic_weights(name or ""))
    for part in [p for p in _NAME_SPLIT.split(name or "") if p.strip()]:
        key = part.strip().casefold()
        singular = key[:-1] if len(key) > 3 and key.endswith("s") and not key.endswith("ss") else key
        for candidate in (key, singular):
            if candidate in labels:
                found[labels[candidate]] = found.get(labels[candidate], 0.0) + 2.0
            for topic in aliases.get(candidate, ()):
                found[topic] = found.get(topic, 0.0) + 2.0
            for topic, weight in topic_weights(candidate).items():
                found[topic] = max(found.get(topic, 0.0), weight)
            if candidate in labels or candidate in aliases:
                break
    return found


def _parent_topics(name: str) -> dict[str, float]:
    """**A name that is only a parent of the pack** ("Leisure", "Practical
    Life") reaches each topic under it (INBOX 1583: the taxonomy's parents),
    a named topic's 2.0 shared among them as a phrase is shared among its
    topics. Only when nothing else did: "Work" is a parent too, and its 24
    job sectors beside its own Business and Career cost the 120-note fixture
    its Work note."""
    children = children_of(name)
    return {topic: 2.0 / len(children) for topic in children}
