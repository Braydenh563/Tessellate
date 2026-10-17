"""The taxonomy pack's own tests (WORLD_CLASS_PLAN 23, decision 1: "its
tests come with it"), carried from the pack's `test_memorymap_taxonomy.py`
(5.0.0, 64 methods) with only the imports and the data paths changed: the
pack's JSON is under `src/tessellate/ai/data/taxonomy/`, its provenance copy
of the original vocabulary under `tests/fixtures/taxonomy/`. The names the
pack exposes as module constants are read through the module's lazy
attributes, so importing it reads no data.
"""

import json
import unittest
from pathlib import Path

from tessellate.ai import taxonomy
from tessellate.ai.taxonomy import (
    DATA_DIR, analyze_note, audit_taxonomy, build_alias_index, extract_categories,
    extract_dynamic_categories, extract_entities, extract_keywords, extract_occupations,
    merge_reviewed_topic_terms, merge_taxonomy, normalize_text, reload_taxonomy,
    reset_taxonomy_processors,
)

FIXTURES = Path(__file__).parent / "fixtures" / "taxonomy"
TAXONOMY_MAP = taxonomy.taxonomy_map()
FUNCTIONAL_CATEGORIES = taxonomy.functional_categories()


class TaxonomyTests(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(audit_taxonomy()["category_count"], 528)
        #: The pack's own file: the live map also carries Tessellate's everyday
        #: vocabulary (`memorymap_everyday.json`, INBOX 1297), which has its own tests.
        pack = json.loads((DATA_DIR / "memorymap_taxonomy.json").read_text(encoding="utf-8"))["taxonomy"]
        self.assertEqual(len({normalize_text(k).lower() for words in pack.values() for k in words}), 6441)
    def test_no_duplicates(self):
        self.assertEqual(audit_taxonomy()["duplicates_within_categories"], {})
    def test_functions_are_defined(self):
        self.assertLessEqual(FUNCTIONAL_CATEGORIES, TAXONOMY_MAP.keys())
    def test_legacy_names(self):
        original = {"Projects", "Journal", "Reference", "Fitness", "Health", "Software",
                    "Tech", "AI", "Finance", "Investing", "Brainstorming", "Travel",
                    "Cooking", "Entertainment", "Literature", "Errands", "Relationships",
                    "Education", "Business"}
        self.assertLessEqual(original, TAXONOMY_MAP.keys())
    def test_empty(self):
        self.assertTrue(analyze_note("")["abstained"])
    def test_no_match(self):
        self.assertEqual(extract_dynamic_categories("Maybe imagine another concept."), [])
    def test_single_weak(self):
        self.assertEqual(analyze_note("bank")["topics"], [])
    def test_repeated_weak(self):
        self.assertEqual(analyze_note("bank bank bank")["topics"], [])
    def test_distinct_evidence(self):
        self.assertEqual(analyze_note("bank debt budget")["topics"], ["Finance"])
    def test_software(self):
        self.assertIn("Software", analyze_note("Python source code and pytest unit tests")["topics"])
    def test_local_ai(self):
        self.assertIn("Local AI", analyze_note("GGUF and llama.cpp local inference")["topics"])
    def test_project_prefix(self):
        self.assertEqual(extract_dynamic_categories("Project plan: GGUF with llama.cpp"),
                         ["Local AI", "Project: Local AI"])
    def test_design_accessibility(self):
        self.assertEqual(extract_dynamic_categories("Reference guide: Figma design tokens and keyboard navigation"),
                         ["Accessibility & Design", "Reference: Accessibility & Design"])
    def test_journal(self):
        a = analyze_note("Dear diary, today I practised guided meditation")
        self.assertIn("Journal", a["functions"])
        self.assertIn("Mindfulness", a["topics"])
    def test_agents(self):
        self.assertIn("AI Agents", analyze_note("MCP server tool calling agentic workflow")["topics"])
    def test_australian_tax(self):
        self.assertIn("Tax & Administration", analyze_note("ATO tax return HECS-HELP")["topics"])
    def test_gaming(self):
        self.assertIn("Gaming", analyze_note("Steam Deck co-op video games")["topics"])
    def test_shared_evidence(self):
        categories = extract_categories("mental health")
        self.assertIn("Health", categories)
        self.assertIn("Mental Health", categories)
    def test_shared_threshold(self):
        self.assertEqual(analyze_note("mental health")["topics"], [])
        self.assertEqual(set(analyze_note("mental health", min_score=1)["topics"]),
                         {"Health", "Mental Health"})
    def test_longest_match(self):
        self.assertEqual(extract_keywords("machine learning"), ["machine learning"])
    def test_case(self):
        self.assertIn("gguf", extract_keywords("GGUF"))
    def test_word_boundaries(self):
        self.assertEqual(extract_keywords("chair fairytale concatenate"), [])
    def test_punctuation_languages(self):
        self.assertIn("c++", extract_keywords("C++ source code"))
        self.assertIn("c#", extract_keywords("C# programming"))
    def test_whitespace(self):
        self.assertIn("source code", extract_keywords("source\n   code"))
    def test_unicode_punctuation(self):
        self.assertIn("fine-tuning", extract_keywords("fine‑tuning"))
    def test_deduplicate_scores(self):
        self.assertEqual(analyze_note("gguf")["scores"], analyze_note("gguf gguf gguf")["scores"])
    def test_title_boost(self):
        a=analyze_note("gguf", title="GGUF")
        self.assertEqual(a["scores"]["Local AI"], 2.5)
        self.assertEqual(len(a["evidence"]["Local AI"]), 1)
    def test_normalized_spans(self):
        a = analyze_note("  GGUF\n  model")
        normalized = normalize_text("  GGUF\n  model")
        for match in a["matches"]:
            self.assertEqual(normalized[match["start"]:match["end"]].lower(), match["keyword"])
    def test_deterministic(self):
        text="Figma wireframes and GGUF llama.cpp"
        self.assertEqual(analyze_note(text), analyze_note(text))
    def test_limit(self):
        self.assertLessEqual(len(analyze_note("Figma wireframes GGUF llama.cpp", max_topics=1)["topics"]), 1)
    def test_invalid_input(self):
        with self.assertRaises(TypeError):
            analyze_note(None)
        with self.assertRaises(ValueError):
            analyze_note("", min_score=-1)
    def test_reset(self):
        reset_taxonomy_processors()
        self.assertIn("gguf", extract_keywords("gguf"))


class ExpansionTests(unittest.TestCase):
    def test_preserve_original_vocabulary(self):
        original=json.loads(FIXTURES.joinpath("original_taxonomy.json").read_text(encoding="utf-8"))["taxonomy"]
        for category,terms in original.items():
            with self.subTest(category=category):
                self.assertLessEqual(set(terms), set(TAXONOMY_MAP[category]))
    def test_general_designer(self):
        self.assertIn("Designer",[h["label"] for h in extract_occupations("Designer")])
    def test_design_specialists(self):
        for title in ["Graphic Designer","UX Designer","Service Designer","Industrial Designer","Costume Designer","Game Designer","Content Designer","Landscape Designer"]:
            with self.subTest(title=title):
                self.assertIn(title,[h["label"] for h in extract_occupations(title)])
    def test_every_occupation_label(self):
        roles=json.loads(DATA_DIR.joinpath("memorymap_occupations.json").read_text(encoding="utf-8"))["roles"]
        for role_id,role in roles.items():
            with self.subTest(role=role["label"]):
                self.assertIn(role_id,[h["role_id"] for h in extract_occupations(role["label"])])
    def test_nurse_generic(self):
        self.assertIn("Nurse",[h["label"] for h in extract_occupations("nurse")])
    def test_title_alias(self):
        self.assertIn("UX Designer",[h["label"] for h in extract_occupations("user experience designer")])
    def test_longest_role(self):
        labels=[h["label"] for h in extract_occupations("Graphic Designer")]
        self.assertIn("Graphic Designer",labels)
        self.assertNotIn("Designer",labels)
    def test_occupation_gate(self):
        self.assertEqual(extract_occupations("designer",require_job_context=True),[])
        self.assertTrue(extract_occupations("designer job",require_job_context=True))
    def test_no_job_inference(self):
        hits=extract_occupations("My friend was a graphic designer")
        self.assertTrue(hits)
        self.assertTrue(all(not h["personal_occupation_inferred"] for h in hits))
    def test_sharehouse(self):
        self.assertIn("Share Houses",analyze_note("Housemates and roommate agreement with shared bills")["topics"])
    def test_aged_care(self):
        self.assertIn("Aged Care",analyze_note("Aged care assessment and residential aged care")["topics"])
    def test_school_admin(self):
        self.assertIn("School Attendance & Absences",analyze_note("School attendance and absence note")["topics"])
    def test_trade(self):
        self.assertIn("Construction & Building Trades",analyze_note("White card and construction site")["topics"])
    def test_international_admin(self):
        self.assertIn("Cross-Border Administration",analyze_note("Apostille and consular service")["topics"])
    def test_occupation_in_unified_result(self):
        a=analyze_note("Graphic Designer job interview")
        self.assertIn("Graphic Designer",[h["label"] for h in a["occupations"]])
        self.assertFalse(a["personal_attributes_inferred"])
        self.assertFalse(a["context_engine_implemented"])
    def test_optional_facets(self):
        a=analyze_note("Graphic Designer",include_occupations=False,include_entities=False)
        self.assertEqual(a["occupations"],[])
        self.assertEqual(a["entities"],[])
    def test_university_acronym_gate(self):
        self.assertEqual(extract_entities("UQ UNE VU"),[])
        self.assertTrue(extract_entities("QUT lecture notes"))
    def test_all_university_names(self):
        entities=json.loads(DATA_DIR.joinpath("memorymap_entities.json").read_text(encoding="utf-8"))["entities"]
        for entity_id,entry in entities.items():
            with self.subTest(name=entry["label"]):
                self.assertIn(entity_id,[h["entity_id"] for h in extract_entities(entry["label"])])
    def test_historical_name(self):
        h=extract_entities("University of Adelaide")[0]
        self.assertEqual(h["entity_status"],"historical_name")
        self.assertEqual(h["label"],"University of Adelaide")
    def test_user_entity_alias(self):
        entries=[{"entity_id":"user:school:1","label":"Meridian Academy","type":"school","aliases":["Meridian"],"reviewed":True,"status":"accepted","requires_context":True}]
        hits=extract_entities("Meridian meeting",user_entities=entries)
        self.assertEqual(hits[0]["label"],"Meridian Academy")
        self.assertEqual(hits[0]["resolution"],"candidate_requires_context")
        self.assertFalse(hits[0]["affiliation_inferred"])
    def test_alias_collision(self):
        entries=[{"entity_id":str(i),"label":"Meridian "+str(i),"aliases":["Meridian"],"reviewed":True,"status":"accepted"} for i in [1,2]]
        self.assertEqual(build_alias_index(entries),{"meridian":["1","2"]})
        self.assertEqual(len(extract_entities("Meridian",user_entities=entries)),2)
    def test_unreviewed_not_learned(self):
        self.assertEqual(build_alias_index([{"status":"candidate","entity_id":"x","aliases":["test"]}]),{})
    def test_context_term_not_flattened(self):
        entries=[{"status":"accepted","reviewed":True,"term":"cedar","categories":["Software"],"requires_context":True}]
        self.assertEqual(merge_reviewed_topic_terms({"Software":[]},entries),{"Software":[]})
    def test_reviewed_unconditional_term(self):
        entries=[{"status":"accepted","reviewed":True,"term":"MY FRAMEWORK","categories":["Software"],"requires_context":False}]
        self.assertEqual(merge_reviewed_topic_terms({"Software":[]},entries),{"Software":["my framework"]})
    def test_unknown_category_rejected(self):
        with self.assertRaises(ValueError):
            merge_reviewed_topic_terms({},[{"status":"accepted","reviewed":True,"term":"x","categories":["Unknown"],"requires_context":False}])
    def test_merge_does_not_mutate(self):
        old={"A":["one"]}
        new=merge_taxonomy(old,{"A":["two"],"B":["three"]})
        self.assertEqual(old,{"A":["one"]})
        self.assertEqual(new["A"],["one","two"])
    def test_real_new_keyword(self):
        self.assertIn("rainfall",extract_keywords("rainfall"))
    def test_reload(self):
        reload_taxonomy()
        self.assertIn("gguf",extract_keywords("gguf"))
    def test_empty_extended(self):
        a=analyze_note("")
        self.assertEqual(a["occupations"],[])
        self.assertEqual(a["entities"],[])
    def test_occupation_offsets(self):
        text="  UX\n designer"
        normalized=normalize_text(text)
        for h in extract_occupations(text):
            self.assertEqual(normalized[h["start"]:h["end"]],h["surface"])
    def test_entity_collision_rejected(self):
        with self.assertRaises(ValueError):
            extract_entities("test",user_entities=[{"entity_id":"university:queensland_university_of_technology","label":"Fake","aliases":["fake"],"status":"accepted","reviewed":True}])
    def test_declared_context_limit(self):
        rules=json.loads(DATA_DIR.joinpath("memorymap_context_rules.json").read_text(encoding="utf-8"))
        self.assertFalse(rules["execution_implemented"])
        self.assertTrue(all(r["candidate_topic"] in TAXONOMY_MAP for r in rules["rules"]))

