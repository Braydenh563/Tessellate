"""A generated face reads a mood out of the name it is drawn for.

The owner: "would it be funny if for the generated avatar profile pictures,
the application detects the intent or mood from the name ... I have personas
called 'overly dramatic narrator', and 'depressed wizard', 'exitable
academic'", and then: "most people wont do that, so there needs to be some
other way as well ... like if I put in the word pandaSushi101, what would
that generate".

So `nameMood` (app.js) reads a name in four layers, most specific first:
mood words and the nouns that carry one; the way the name is typed (capitals,
punctuation, emoticons, emoji, a few numbers); and, when nothing says
anything, a personality drawn from the name's own hash, so every name still
gets a character and the same name always gets the same one. These tests run
the real function under node and pin what each layer decides.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _mood_source() -> str:
    start = APP.index("const NAME_MOOD_LEXICON")
    end = APP.index("\n}\n", APP.index("function nameMood(")) + 3
    return APP[start:end]


def _moods(names: list[str], tmp_path: Path) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path / "mood.js"
    script.write_text(
        _mood_source() + f"\nconsole.log(JSON.stringify({json.dumps(names)}.map(nameMood)));\n",
        encoding="utf-8",
    )
    out = subprocess.run([node, str(script)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_the_owners_personas_get_the_face_their_name_asks_for(tmp_path: Path) -> None:
    dramatic, wizard, academic = _moods(
        ["Overly dramatic narrator", "Depressed wizard", "Exitable academic"], tmp_path
    )
    assert dramatic["mood"] == "dramatic" and dramatic["intense"] is True
    assert wizard["mood"] == "sad" and "hat" in wizard["props"]
    # "exitable" is how it was typed; a face should not need the spelling right.
    assert academic["mood"] == "excited" and "glasses" in academic["props"]
    assert all(m["source"] == "words" for m in (dramatic, wizard, academic))


def test_a_handle_with_no_mood_word_still_says_something(tmp_path: Path) -> None:
    (panda,) = _moods(["pandaSushi101"], tmp_path)
    assert panda["animal"] == "panda"
    assert panda["mood"] == "hungry"
    # Glued together, lower case, the same reading.
    (glued,) = _moods(["pandasushi101"], tmp_path)
    assert glued["animal"] == "panda" and glued["mood"] == "hungry"


def test_the_way_a_name_is_typed_is_read_when_the_words_say_nothing(tmp_path: Path) -> None:
    shout, bang, dots, huh, smile, frown, emoji, beast = _moods(
        ["BRAYDEN", "Maya!", "Liam...", "Tom?", "Sam :)", "Sam :(", "Jo 😴", "Kai666"], tmp_path
    )
    assert shout["intense"] is True and shout["source"] == "hint"
    assert bang["mood"] == "excited"
    assert dots["mood"] == "sleepy"
    assert huh["mood"] == "confused"
    assert smile["mood"] == "happy"
    assert frown["mood"] == "sad"
    assert emoji["mood"] == "sleepy"
    # A number leans the mood and nothing more: "numbers only nudge the
    # seeded variety" (the owner, 2026-09-24), so 666 is sly without horns.
    assert beast["mood"] == "sly" and not beast["props"]


def test_short_words_match_whole_words_only(tmp_path: Path) -> None:
    # "mad" is a mood; "Madison" is a name. "cat" is an animal; "Education" is
    # not a cat. A three-letter keyword only ever matches a whole word.
    madison, education, mad_cat = _moods(["Madison", "Education bot", "mad cat"], tmp_path)
    assert madison["mood"] != "angry" or madison["source"] == "seed"
    assert education["animal"] is None and "antenna" in education["props"]
    assert mad_cat["mood"] == "angry" and mad_cat["animal"] == "cat"


def test_nothing_said_draws_a_stable_personality_from_the_name(tmp_path: Path) -> None:
    names = ["Alice", "Ben", "Chloe", "Daniel", "Emma", "Farah", "George", "Hana", "Isaac", "Jade"]
    first = _moods(names, tmp_path)
    again = _moods(names, tmp_path)
    assert first == again
    assert all(m["source"] == "seed" and m["intense"] is False for m in first)
    # A personality and a couple of traits, never a species or a costume a
    # word would ask for: the only things worn are the trait families' own.
    assert all(m["animal"] is None and m["cues"] == [] for m in first)
    assert all(set(m["props"]) <= _TRAIT_WORN for m in first)
    # Some plain faces and some characters, not ten of one.
    kinds = {m["mood"] for m in first}
    assert len(kinds) >= 4, kinds


def test_an_empty_name_is_quiet(tmp_path: Path) -> None:
    (empty,) = _moods([""], tmp_path)
    assert empty["mood"] is None and not empty["props"] and empty["animal"] is None


def test_names_that_make_no_sense_still_get_a_character(tmp_path: Path) -> None:
    # The owner: "can you improve or expand it even more for names which just
    # make no sence haha??"
    mash, scream, mutant, digits_mash = _moods(["asdfgh", "aaaaaaa", "xqzvbrrt", "k7x9q"], tmp_path)
    assert mash["mood"] == "dizzy" and mash["source"] == "nonsense"
    assert scream["mood"] == "surprised" and scream["intense"] is True
    assert mutant["mutant"] and mutant["source"] == "nonsense"
    assert digits_mash["mutant"]
    # A mutant's traits come from the letters, helixlabs style, so they are
    # stable and two different nonsense names are two different creatures.
    again = _moods(["xqzvbrrt", "zzkrrptt", "bcdfgh", "qwxz"], tmp_path)
    assert again[0]["mutant"] == mutant["mutant"]
    assert len({json.dumps(m["mutant"], sort_keys=True) for m in again}) >= 3


def test_the_internets_own_words_are_read(tmp_path: Path) -> None:
    lol, haha, meh, bruh, uwu, hmm, happy, sooo = _moods(
        ["lol", "hahahaha", "meh", "bruh", "uwu", "hmmmm", "happyyyy", "sooo sleepy"], tmp_path
    )
    assert lol["mood"] == "laughing" and haha["mood"] == "laughing"
    assert meh["mood"] == "unimpressed" and bruh["mood"] == "unimpressed"
    assert uwu["mood"] == "uwu"
    assert hmm["mood"] == "confused"
    # A stretched word is still the word, and a stretched "so" still turns it up.
    assert happy["mood"] == "happy"
    assert sooo["mood"] == "sleepy" and sooo["intense"] is True


def test_a_real_name_is_not_mistaken_for_nonsense(tmp_path: Path) -> None:
    real = _moods(["Alice", "Brayden", "Siobhan", "Nguyen", "Krzysztof", "Chris"], tmp_path)
    assert all(m["source"] == "seed" and not m["mutant"] for m in real[:4])


def test_a_name_that_says_several_things_draws_what_fits(tmp_path: Path) -> None:
    # The owner: 'what if a there was a name like "Uwu wink wink ahhhhhh ur
    # cooked buddy"', and then of what it drew: "still a little messy". The
    # first mood word sets the face; one flavour stacks on it, the first
    # named that does not fight it: uwu's eyes are already shut (no wink) and
    # a word set the mood (no scream over it), so it sweats, "cooked". And
    # "cooked" is not a cook: no chef's hat.
    (chaos,) = _moods(["Uwu wink wink ahhhhhh ur cooked buddy"], tmp_path)
    assert chaos["mood"] == "uwu"
    assert chaos["flavours"] == ["doomed"]
    assert chaos["props"] == [] and chaos["cues"] == []
    wink, scream = _moods(["Nervous wink", "ahhhh"], tmp_path)
    assert wink["flavours"] == ["wink"]
    assert scream["flavours"] == ["scream"]
    (plain,) = _moods(["Alice"], tmp_path)
    assert plain["flavours"] == []


def test_evil_smiles_and_the_rest_of_the_cast(tmp_path: Path) -> None:
    # The owner: "what about evil smiles and other things haha".
    cases = {
        "Evil overlord": ("evil", None),
        "muahahaha": ("evil", None),
        "Vampire": (None, "fangs"),
        "Sick of mondays": ("sick", None),
        "dead inside": ("dead", None),
        "\U0001F480": ("dead", None),
        "Clown": ("laughing", "rednose"),
        "Space cowboy": (None, "cowboy"),
        "birthday girl": (None, "partyhat"),
        "Ninja": ("sly", "ninjamask"),
        "Astronaut": (None, "helmet"),
        "smol bean": ("cute", None),
        "starstruck fan": ("starstruck", None),
        "tipsy": ("drunk", None),
    }
    got = _moods(list(cases), tmp_path)
    for (name, (mood, prop)), reading in zip(cases.items(), got):
        if mood:
            assert reading["mood"] == mood, (name, reading)
        if prop:
            assert prop in reading["props"], (name, reading)


def test_one_hat_per_head(tmp_path: Path) -> None:
    party, king = _moods(["Party wizard", "Wizard king"], tmp_path)
    assert "partyhat" in party["props"] and "hat" not in party["props"]
    assert "hat" in king["props"] and "crown" not in king["props"]


def test_hands_and_the_things_they_hold(tmp_path: Path) -> None:
    # The owner: "could we add some hand gestures like a thumbs up, drink
    # bottles, wine glasses, someone ripping a table in half".
    cases = {
        "Nice one": "thumbsup",
        "\U0001F44D": "thumbsup",
        "Peace out": "peace",
        "Hi there": "wave",
        "Beer o clock": "beer",
        "Wine mom": "wine",
        "Latte lover": "mug",
        "Sir Knight": "sword",
        "Detective Pikachu": "magnifier",
        "Karaoke queen": "mic",
        "Bookworm": "book",
        "Selfie queen": "phone",
        "Pizza rat": "pizza",
    }
    got = _moods(list(cases), tmp_path)
    for (name, held), reading in zip(cases.items(), got):
        assert reading["hand"] == held, (name, reading)
    # One hand, one thing in it: the first one named.
    (both,) = _moods(["Beer and wine"], tmp_path)
    assert both["hand"] == "beer"


def test_a_table_flip_is_a_table_flip(tmp_path: Path) -> None:
    flips = _moods(["(╯°□°)╯︵ ┻━┻", "tableflip", "rage quit"], tmp_path)
    assert all(m["hand"] == "tableflip" and m["mood"] == "angry" for m in flips), flips


def test_money_eyes(tmp_path: Path) -> None:
    rich, stonks = _moods(["Filthy rich", "stonks"], tmp_path)
    assert rich["mood"] == "greedy" and stonks["mood"] == "greedy"


def test_plain_faces_vary_their_smiles_and_features(tmp_path: Path) -> None:
    names = [f"Person {chr(65 + i)}{chr(97 + i)}" for i in range(26)]
    got = _moods(names, tmp_path)
    smiles = {m["style"]["smile"] for m in got}
    extras = {e for m in got for e in m["style"]["features"]}
    assert len(smiles) >= 5, smiles
    assert len(extras) >= 3, extras


def test_limbs_are_not_always_hands(tmp_path: Path) -> None:
    # The owner: "not all of them have to have hands btw, some can have feet
    # or tentacles or wings some none at all."
    cases = {
        "Angel": "wings-feather",
        "Dragon": "wings-bat",
        "Bat": "wings-bat",
        "Fairy": "wings-bug",
        "Busy bee": "wings-bug",
        "Kraken": "tentacles",
        "Tentacle monster": "tentacles",
        "Speed walker": "feet",
        "Alice": None,
    }
    got = _moods(list(cases), tmp_path)
    for (name, limbs), reading in zip(cases.items(), got):
        assert reading["limbs"] == limbs, (name, reading)
    octo, bat = _moods(["Octopus", "Bat"], tmp_path)
    assert octo["animal"] == "octopus" and bat["animal"] == "bat"
    # Mutants roll their own: across a handful, more than one kind, and some
    # with none at all.
    mutants = _moods(["xqzvbrrt", "zzkrrptt", "bcdfgh", "qwxz", "k7x9q", "brrrt", "pfft", "grrr", "hmph", "xkcd"], tmp_path)
    kinds = {m["limbs"] for m in mutants if m["mutant"]}
    assert len(kinds) >= 2, kinds


def test_the_wider_zoo(tmp_path: Path) -> None:
    names = ["Frog", "Bear", "Tweety bird", "Duck", "Hamster", "Sheep", "Cow", "Deer", "Unicorn", "Dragon", "Dino", "Shark", "Snake", "Axolotl", "Crab", "Raccoon", "Hedgehog", "Sloth", "Capybara", "Bee"]
    want = ["frog", "bear", "bird", "duck", "hamster", "sheep", "cow", "deer", "unicorn", "dragon", "dino", "shark", "snake", "axolotl", "crab", "raccoon", "hedgehog", "sloth", "capybara", "bee"]
    got = _moods(names, tmp_path)
    assert [m["animal"] for m in got] == want
    # A sloth is sleepy and a capybara calm when the name says nothing else.
    assert got[names.index("Sloth")]["mood"] == "sleepy"
    assert got[names.index("Capybara")]["mood"] == "calm"


def test_eyewear_one_pair_each(tmp_path: Path) -> None:
    cases = {
        "Code nerd": "squareglasses",
        "Posh Byron": "monocle",
        "Mad scientist": "goggles",
        "3D movie buff": "threed",
        "Rockstar": "starglasses",
        "Heartbreaker": "heartglasses",
        "Cyber punk": "visor",
        "Professor Plum": "glasses",
    }
    got = _moods(list(cases), tmp_path)
    for (name, wear), reading in zip(cases.items(), got):
        assert wear in reading["props"], (name, reading)
    (both,) = _moods(["Nerdy scientist"], tmp_path)
    eyewear = {"glasses", "squareglasses", "monocle", "goggles", "threed", "starglasses", "heartglasses", "visor"}
    assert len(eyewear & set(both["props"])) == 1, both


def test_the_look_is_never_read_from_a_name(tmp_path: Path) -> None:
    # The owner: presentation "is the user's choice, never guessed from the
    # name". Not from a first name, and not from a word in it either.
    names = ["Space girl", "Gym bro", "Alice", "James", "Queen Mary", "Dude"]
    assert {m["look"] for m in _moods(names, tmp_path)} == {None}
    assert {m["look"] for m in _leaning("masculine", {}, names, tmp_path)} == {"masculine"}


def test_costumes_pirates_karate_and_friends(tmp_path: Path) -> None:
    cases = {"Captain Hook": "tricorn", "Karate kid": "headband", "Princess": "tiara", "Skater boi": "cap", "Winter vibes": "beanie", "Cottagecore queen": "flowercrown", "Biker gang": "bandana", "Lumberjack": "beard"}
    got = _moods(list(cases), tmp_path)
    for (name, prop), reading in zip(cases.items(), got):
        assert prop in reading["props"], (name, reading)


def test_hair_varies_and_the_look_is_never_guessed(tmp_path: Path) -> None:
    # The owner, 2026-09-24, on his own name drawing pigtails and lipstick: a
    # plain name's "look (masculine/feminine) follows the Appearance 'Face
    # looks' setting or the Profile look, never guessed from the first name".
    # With neither (Mixed), every face has hair, from the styles that read as
    # either, and wears nothing that says one or the other.
    got = _moods([f"Friend {i}" for i in range(60)], tmp_path)
    hair = [m["style"]["hair"] for m in got]
    assert None not in hair
    assert len(set(hair)) >= 5, set(hair)
    assert set(hair) <= {"crop", "sweep", "curtains", "messy", "curls", "wavy", "locs", "undercut", "fringe", "spiky"}, set(hair)
    assert all(m["style"]["accessories"] == [] and "lashes" not in m["style"]["features"] for m in got)
    # The long, tied-up and curled styles are there for a feminine look, the
    # bold cuts for a masculine one.
    feminine = _leaning("feminine", {}, [f"Friend {i}" for i in range(60)], tmp_path)
    assert {"long", "waves", "bun", "longcurls"} <= {m["style"]["hair"] for m in feminine}
    masculine = _leaning("masculine", {}, [f"Friend {i}" for i in range(60)], tmp_path)
    assert {"undercut", "mohawk", "slick", "buzzline"} <= {m["style"]["hair"] for m in masculine}


def test_tools_and_toys(tmp_path: Path) -> None:
    # The owner: "are there also some tools and utilities like guns, bows,
    # swords, axes, hammers etc?? My xbox gamertag is Sushicraft563. and my
    # gaming is sometimes sushilord563 gaming".
    cases = {
        "Sushicraft563": "pickaxe",
        "sushilord563 gaming": "controller",
        "Xbox fiend": "controller",
        "Axe murderer": "axe",
        "Thor": "hammer",
        "Sniper elite": "blaster",
        "Archer": "bow",
        "Wizard": "wand",
        "Gone fishing": "fishingrod",
        "Artist": "paintbrush",
        "Spartan": "spear",
        "Poseidon": "trident",
        "\U0001F3AE": "controller",
    }
    got = _moods(list(cases), tmp_path)
    for (name, held), reading in zip(cases.items(), got):
        assert reading["hand"] == held, (name, reading)
    craft, lord = got[0], got[1]
    assert craft["mood"] == "hungry"
    # Two cues, by salience: a lord wears a crown, and the gaming is the
    # controller; the headphones "gaming" also asks for would be a second
    # thing on the head, and the sushi a third cue.
    assert lord["props"] == ["crown"] and lord["cues"] == ["crown", "controller"]


def test_mythical_creatures(tmp_path: Path) -> None:
    names = ["Mermaid", "Elf", "Goblin", "Troll", "Gnome", "Genie", "Mummy", "Zombie", "Minotaur", "Medusa", "Cyclops", "Phoenix", "Yeti"]
    got = _moods(names, tmp_path)
    assert [m["animal"] for m in got] == [n.lower() for n in names]


def test_everyday_clothes(tmp_path: Path) -> None:
    office, street, gala = _moods(["Office Karen", "Street Steve", "Prom queen"], tmp_path)
    assert office["style"]["outfit"] == "suit"
    assert street["style"]["outfit"] == "hoodie"
    assert gala["style"]["outfit"] == "dress"
    got = _moods([f"Pal {i}" for i in range(40)], tmp_path)
    kinds = {m["style"]["outfit"] for m in got}
    assert {"tee", "hoodie", "scoop"} <= kinds, kinds


def test_atlas_has_a_face_of_its_own() -> None:
    # The owner: "should we make a very very impressive avatar for Atlas
    # that embodies the core of the application ... maybe with the logo
    # mixed in". The assistant's name draws the hand-made character, never a
    # face generated from the letters "Atlas": atlas.js registers it through
    # the character interface, and `atlasMark` (the old name) delegates to it.
    body = APP[APP.index("function nameMark(seed") :][:600]
    assert "return atlasMark(size);" in body
    assert "return atlasDraw(size, mood);" in APP
    atlas = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
    assert "registerCharacter({" in atlas
    # And its moods follow the app: thinking while a turn runs, happy or
    # surprised when it ends, and the rest of the fifteen from events.
    app = app_js_text()
    assert 'setAtlasMood("thinking")' in app
    assert 'endState === "done" ? "happy"' in app
    moods = ("calm", "happy", "delighted", "laughing", "thinking", "curious", "surprised",
             "confused", "sleepy", "sad", "proud", "shy", "determined", "love", "worried")
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    for mood in moods:
        assert f"  {mood}: {{ words:" in atlas, mood
        if mood != "calm":
            assert f'[data-atlas-mood="{mood}"]' in css, mood
    assert "oklch(from var(--accent)" in css, "Atlas's colours follow the accent"
    assert "watchNameMark(svg)" in atlas


def _own(style: dict, names: list[str], tmp_path: Path) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = tmp_path / "own.js"
    script.write_text(
        'function userMarkSeed() { return "Brayden"; }\n'
        + _mood_source()
        + f"\nsetOwnNameMarkStyle({json.dumps(style)});\n"
        + f"console.log(JSON.stringify({json.dumps(names)}.map(nameMood)));\n",
        encoding="utf-8",
    )
    out = subprocess.run([node, str(script)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_your_own_face_can_be_shuffled_and_customised(tmp_path: Path) -> None:
    # The owner: "what if i dont like how the avatar it looks on my name??"
    (base,) = _own({}, ["Brayden"], tmp_path)
    shuffles = [_own({"variant": v}, ["Brayden"], tmp_path)[0] for v in (1, 2, 3, 4)]
    looks = {json.dumps([m["mood"], m["style"]], sort_keys=True) for m in [base, *shuffles]}
    assert len(looks) >= 4, "a shuffle is a different take on the name"
    mine, other = _own(
        {"mood": "evil", "hair": "none", "outfit": "suit", "hat": "cowboy", "eyewear": "monocle", "hand": "wand"},
        ["Brayden", "Alice"],
        tmp_path,
    )
    assert mine["mood"] == "evil" and mine["style"]["hair"] is None and mine["style"]["outfit"] == "suit"
    assert "cowboy" in mine["props"] and "monocle" in mine["props"] and mine["hand"] == "wand"
    # Only your own name: everyone else keeps theirs.
    assert other == _own({}, ["Alice"], tmp_path)[0]
    # "none" takes a part away; an unknown key is ignored, never drawn.
    (bare,) = _own({"hat": "none", "hand": "none", "mood": "nonsense"}, ["Cowboy Brayden"], tmp_path)
    assert bare["hand"] is None


def test_the_companion_and_dashboard_fall_back_to_atlas_not_to_you() -> None:
    # The owner: "i set the corner companion to be the chat persona and it set
    # it to me instead" and "the dashboard mark didnt change from the logo
    # when I selected the greeting persona". The default voice is Atlas, who
    # has a face of its own now.
    buddy = APP[APP.index("function nameMarkBuddySeed(") :][:900]
    assert 'document.getElementById("persona-select")?.value || "Atlas"' in buddy
    # dashboardMarkSeed moved to dashboard.js (S3): the dashboard asks it at
    # boot, before avatars.js is in. The rule it holds is unchanged.
    dashboard = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    dash = dashboard[dashboard.index("function dashboardMarkSeed(") :][:700]
    assert '|| "Atlas"' in dash


def test_atlas_style_is_a_choice_that_every_atlas_follows() -> None:
    # The owner: "i actually dont mind atlas with the circle avatar and
    # blurred out edges so maybe that can be a toggle??". Appearance chooses
    # the character (default) or the classic globe; the draw path, the
    # companion's figure and a mood change all branch on it, and a change of
    # style redraws what is on the page.
    atlas = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
    settings = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '"atlas-style": "character"' in settings
    assert "\"avatar-buddy\", \"avatar-buddy-size\", \"avatar-buddy-actions\", \"atlas-style\", \"assistant-avatar\", \"atlas-look\", \"face-look\", \"dash-mark\"" in settings, "Reset forgets the choice"
    assert 'id="atlas-style"' in index and '<option value="classic">Classic globe</option>' in index
    assert 'atlasStyle() === "classic") return atlasClassicMark(size, mood);' in atlas
    assert 'if (atlasStyle() === "classic") return atlasClassicFigure();' in atlas
    assert "function atlasRepaint()" in atlas and "atlasRepaint()" in settings


def test_atlas_look_says_when_it_follows_face_looks() -> None:
    # OPEN.md, "Left by the 0.3.3 agents": the select read "Masculine" while
    # nothing was stored, and Atlas then followed Face looks, so a person
    # with Face looks on Feminine saw a feminine Atlas under a select that
    # said otherwise. "Auto (matches your faces)" is the first option and the
    # default (renamed 2026-09-27, INBOX 429 (d): Auto follows your own face
    # too, not only Face looks, and the owner asked what it meant); picking it, or changing Face looks while it is picked, redraws
    # every Atlas on the page.
    atlas = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
    settings = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    select = index[index.index('<select id="atlas-look"') :]
    select = select[: select.index("</select>")]
    options = re.findall(r'<option value="(\w+)">([^<]+)</option>', select)
    assert options[0] == ("auto", "Auto (matches your faces)"), options
    assert {value for value, _ in options} == {"auto", "masculine", "feminine"}
    assert '"atlas-look": "auto"' in settings
    #: Round 5: the decision lives in `atlasLookReason`, which also says
    #: which of the four decided (the lab's review card shows it): Atlas
    #: look when set, else Face looks when it says a look, else the look
    #: chosen for the person's own face, else the main look.
    look = atlas[atlas.index("function atlasLookReason()") :]
    look = look[: look.index("\n}\n")]
    assert 'if (own === "feminine" || own === "masculine") return { look: own, reason: "chosen" };' in look
    assert 'appearancePref("face-look", "mixed")' in look
    assert 'if (faces === "feminine" || faces === "masculine") return { look: faces, reason: "face-looks" };' in look
    assert 'ownNameMarkStyle().look' in look
    assert 'return { look: "masculine", reason: "default" };' in look
    assert "return atlasLookReason().look;" in atlas[atlas.index("function atlasLook()") :][:120]
    face = settings[settings.index('$("face-look").addEventListener') :]
    face = face[: face.index("});")]
    assert "atlasRepaint()" in face, "a Face looks change leaves an Auto Atlas in the old look"


def test_atlas_hears_a_saved_note_and_a_streak() -> None:
    # A saved note makes Atlas proud while the companion holds up a tiny
    # note (its "carry" errand, which counts as a cheer), and the
    # dashboard's streak count reaches Atlas, which celebrates it at most
    # once a day.
    app = app_js_text()
    dashboard = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    atlas = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
    saved = app[app.index('if (path === "/entries" && options.method === "POST") {') :][:260]
    assert 'nameMarkBuddyCue("carry")' in saved and 'atlasOn("saved")' in saved
    assert "atlasStreak(streak)" in dashboard
    streak = atlas[atlas.index("function atlasStreak(") :][:400]
    assert "atlas-streak-seen" in streak and "toDateString()" in streak


def _leaning(lean: str, style: dict, names: list[str], tmp_path: Path) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = tmp_path / "lean.js"
    script.write_text(
        f'function appearancePref(key, fallback) {{ return key === "face-look" ? {json.dumps(lean)} : fallback; }}\n'
        'function userMarkSeed() { return "Brayden"; }\n'
        + _mood_source()
        + f"\nsetOwnNameMarkStyle({json.dumps(style)});\n"
        + f"console.log(JSON.stringify({json.dumps(names)}.map(nameMood)));\n",
        encoding="utf-8",
    )
    out = subprocess.run([node, str(script)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_faces_take_the_chosen_presentation(tmp_path: Path) -> None:
    # The owner: "the male and female choice avatars generation", then
    # "Presentation is the user's choice ... Default to Neutral until set".
    # Settings, Appearance, Face looks sets every face; your own face's
    # Profile look (masculine, feminine or neutral) wins for your name.
    names = [f"Pal {i}" for i in range(12)] + ["Dude Bob", "Queen Mary"]
    assert {m["look"] for m in _leaning("mixed", {}, names, tmp_path)} == {None}
    assert {m["look"] for m in _leaning("feminine", {}, names, tmp_path)} == {"feminine"}
    assert {m["look"] for m in _leaning("masculine", {}, names, tmp_path)} == {"masculine"}
    (mine,) = _leaning("masculine", {"look": "feminine"}, ["Brayden"], tmp_path)
    assert mine["look"] == "feminine"
    (neutral,) = _leaning("masculine", {"look": "neutral"}, ["Brayden"], tmp_path)
    assert neutral["look"] is None
    # Facial hair is on offer to a masculine face only.
    many = [f"Pal {i}" for i in range(80)]
    assert not any(set(m["style"]["accessories"]) & {"stubble", "shortbeard", "moustache"} for m in _leaning("feminine", {}, many, tmp_path))
    assert any(set(m["style"]["accessories"]) & {"stubble", "shortbeard", "moustache"} for m in _leaning("masculine", {}, many, tmp_path))


# --- the budget (the owner, 2026-09-24: "refine the avatar generation as it
# is still a little messy and I'm not happy with what is generated when I put
# in my name 'Brayden' or 'Sushicraft563, SushiLord' etc") -------------------

_HEAD = {
    "hat", "chefhat", "cowboy", "partyhat", "crown", "tiara", "tricorn", "cap", "beanie", "flowercrown",
    "bandana", "headband", "halo", "horns", "antenna", "headphones", "helmet", "bow", "sushiclip", "flowerclip", "hood",
}
_FACE = {
    "glasses", "squareglasses", "monocle", "goggles", "threed", "starglasses", "heartglasses", "visor",
    "eyepatch", "ninjamask", "rednose", "moustache", "beard", "fangs", "stubble", "earrings", "lipstick",
    "shades", "shortbeard",
}
_TRAIT_WORN = {"beanie", "cap", "headphones", "hood", "glasses", "shades"}
_FRIENDLY = {None, "happy", "calm", "excited", "cute"}
_PLAIN = ["Brayden", "Sarah", "Mohammed", "Li Wei", "Aroha", "Olivia", "Marcus", "Priya", "Jonah", "Elena", "a", "12345"]


def test_a_plain_name_is_a_character_not_a_costume(tmp_path: Path) -> None:
    # A plain name: one hairstyle, a friendly face, no animal, nothing held,
    # and two traits from the hash (the owner, after a round of clean
    # defaults: "they look a bit too mundane now ... more character, less
    # stock"), each from its own family and within the budget.
    for lean in ("mixed", "feminine", "masculine"):
        readings = _leaning(lean, {}, _PLAIN, tmp_path)
        for reading in readings:
            assert reading["animal"] is None and reading["hand"] is None and reading["cues"] == [], reading
            assert reading["mood"] in _FRIENDLY and reading["style"]["hair"], reading
            assert len(reading["style"]["traits"]) == 2, reading
            assert set(reading["props"]) <= _TRAIT_WORN, reading
            assert set(reading["style"]["accessories"]) <= {"stubble", "shortbeard", "moustache"}, reading
        # No two sample names read the same: hair, mood and traits differ.
        looks = {(m["style"]["hair"], m["mood"], tuple(sorted(m["style"]["traits"]))) for m in readings}
        assert len(looks) == len(readings), (lean, looks)
    # Your own Profile look wins for your own name.
    (mine,) = _leaning("feminine", {"look": "masculine"}, ["Brayden"], tmp_path)
    assert mine["look"] == "masculine" and mine["style"]["hair"] in {"crop", "sweep", "quiff", "messy", "undercut", "spiky", "mohawk", "slick", "buzzline", "curls", "locs"}


def test_the_owners_handles_wear_two_cues(tmp_path: Path) -> None:
    craft, lord, panda = _moods(["Sushicraft563", "SushiLord", "pandaSushi101"], tmp_path)
    # A pickaxe for the craft, and the sushi in its hair since the hand is full.
    assert craft["hand"] == "pickaxe" and craft["props"] == ["sushiclip"] and craft["animal"] is None
    # A crown for the lord and sushi in the hand, and nothing else.
    assert lord["props"] == ["crown"] and lord["hand"] == "sushi" and lord["animal"] is None
    assert lord["cues"] == ["crown", "sushi"] and lord["style"]["accessories"] == [] and lord["wing"] is None
    # A panda holding sushi.
    assert panda["animal"] == "panda" and panda["hand"] == "sushi" and panda["props"] == []
    # The digits only move the seeded variety: the same cues on another number.
    other_craft, other_lord = _moods(["Sushicraft7", "SushiLord2024"], tmp_path)
    assert other_craft["cues"] == craft["cues"] and other_lord["cues"] == lord["cues"]


def test_the_budget_holds_for_every_name(tmp_path: Path) -> None:
    # At most two cues from the words; one head item, one face item, one held
    # item at most, counting the accessories; a name naming five costumes
    # wears two of them.
    lexicon = APP[APP.index("const NAME_MOOD_LEXICON") : APP.index("//: **Your own face, your way**")]
    words = sorted(set(re.findall(r"\b([a-z]{3,})\*?(?=[ \"])", lexicon)))
    names = [" ".join(words[i : i + 5]) for i in range(0, len(words), 5)]
    names += ["Pirate wizard king with headphones and a sword", "Nerdy vampire clown astronaut", *_PLAIN]
    names += ["Angel knight", "Busy bee", "Kraken", "Lumberjack", "Captain Pixel", "xX_DarkSlayer_Xx", "Coffee Queen"]
    assert len(names) > 100
    for lean in ("mixed", "feminine", "masculine"):
        for reading in _leaning(lean, {}, names, tmp_path):
            worn = reading["props"] + reading["style"]["accessories"]
            assert len(reading["cues"]) <= 2, reading
            assert len([p for p in worn if p in _HEAD]) <= 1, reading
            assert len([p for p in worn if p in _FACE]) <= 1, reading
            assert set(reading["props"]) <= _HEAD | _FACE, reading
    (five,) = _moods(["Pirate wizard king with headphones and a sword"], tmp_path)
    assert sorted(five["cues"]) == ["eyepatch", "tricorn"], five


def _luma(hex_colour: str) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luma(a), _luma(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _half(hex_colour: str) -> str:
    # nmLineFor on a light fill: the colour halfway to black.
    return "#" + "".join(f"{round(int(hex_colour[i : i + 2], 16) * 0.5):02x}" for i in (1, 3, 5))


def test_the_colour_pairs_hold_on_both_pages() -> None:
    # "A curated palette ... that works on light and dark, with contrast
    # checked; no muddy or clashing combinations." Every coat: the body or
    # its outline at 3:1 on the light page and on the dark one, and the
    # cloth clearly apart from it. Every skin: at 2:1 or its outline at 3:1
    # on both pages, and each hair colour it lists at 1.8:1 against it (the
    # owner: "a hair colour picked from a natural, harmonious palette tuned
    # against the skin tone").
    block = APP[APP.index("const NM_CHAR_PAIRS = [") :]
    block = block[: block.index("];")]
    pairs = re.findall(r'body: "(#[0-9a-f]{6})", cloth: \[([^\]]+)\]', block)
    assert len(pairs) >= 6, pairs
    skins_block = APP[APP.index("const NM_CHAR_SKINS = [") :]
    skins_block = skins_block[: skins_block.index("];")]
    skins = re.findall(r'name: "([a-z]+)", skin: "(#[0-9a-f]{6})", hair: \[([^\]]+)\]', skins_block)
    tones_block = APP[APP.index("const NM_CHAR_HAIR_TONES = {") :]
    tones = dict(re.findall(r'([a-z]+): "(#[0-9a-f]{6})"', tones_block[: tones_block.index("};")]))
    assert len(skins) == 7 and len(tones) >= 8
    for name, skin, hair in skins:
        for page in ("#ffffff", "#1c1c1f"):
            assert max(_contrast(skin, page), _contrast(_half(skin), page)) >= 2, (name, page)
        for tone in re.findall(r'"([a-z]+)"', hair):
            assert _contrast(tones[tone], skin) >= 1.8, (name, tone)
    # The names the profile offers are the ones drawn.
    listed = lambda const: re.findall(r'"([a-z]+)"', APP[APP.index(const) :].split("\n", 1)[0])  # noqa: E731
    assert listed("const NAME_MARK_SKIN_KINDS") == [n for n, _, _ in skins]
    assert sorted(listed("const NAME_MARK_HAIR_TONE_KINDS")) == sorted(tones)
    styles = APP[APP.index("const NM_HAIR_STYLES = {") :]
    styles = styles[: styles.index("\n};")]
    assert sorted(listed("const NAME_MARK_HAIR_KINDS")) == sorted(re.findall(r"^  ([a-z]+): \{", styles, re.M))
    for body, cloth in pairs:
        for page in ("#ffffff", "#1c1c1f"):
            assert max(_contrast(body, page), _contrast(_half(body), page)) >= 3, (body, page)
        for tone in re.findall(r"#[0-9a-f]{6}", cloth):
            apart = sum(abs(int(tone[i : i + 2], 16) - int(body[i : i + 2], 16)) for i in (1, 3, 5))
            assert apart >= 120, (body, tone)
    # The body is never drawn from the app's category colours again.
    draw = APP[APP.index("function drawCharacter(") : APP.index("//: A nigiri about")]
    assert "CATEGORY_DOT_COLOURS" not in draw and "NM_CHAR_PAIRS[" in draw


def test_the_small_mark_keeps_one_cue() -> None:
    # 28px and under draws the "mini" mark: no hat on a creature (its ears
    # are the cue), no specks, a thicker line.
    mark = APP[APP.index("function nameMark(seed") :][:1200]
    assert 'mini ? "mini" : "mark"' in mark and "const mini = size <= 28;" in mark
    draw = APP[APP.index("function drawCharacter(") : APP.index("//: A nigiri about")]
    assert 'const worn = mini && beast ? reading.props.filter((p) => !NAME_MARK_HEAD_KINDS.includes(p))' in draw
    assert "const LW = mini ? 2.4 : NM_CHAR_LINE;" in draw


def test_a_glued_word_is_read_only_where_a_word_could_start(tmp_path: Path) -> None:
    # "sushilord" is sushi and a lord; "cooked" is not a cook, "Janice" is
    # not "nice", "Clover" is not in love and "Angela" is not an angel.
    glued, cooked, janice, clover, angela = _moods(["sushilord563", "cooked", "Janice", "Clover", "Angela"], tmp_path)
    assert glued["props"] == ["crown"] and glued["hand"] == "sushi"
    assert "chefhat" not in cooked["props"]
    for plain in (janice, clover, angela):
        assert plain["source"] == "seed" and plain["cues"] == [], plain
    # And a keyword typed as two words is still one.
    (rage,) = _moods(["rage quit"], tmp_path)
    assert rage["hand"] == "tableflip"


def test_no_rude_gesture_and_every_named_gesture_is_drawn() -> None:
    # INBOX 426 j, the owner: "it did say it was flipping me off at one point
    # but it wasnt visually doing that". The rude gesture is gone from the
    # lexicon, the words and the drawing; and every hand a tooltip can name
    # has a case of its own in `nameCharacterHeld`, so no line promises a
    # gesture or a thing held that is not drawn.
    assert "middlefinger" not in APP and "flipping you off" not in APP
    words = APP[APP.index("const NAME_MARK_HAND_WORDS = {") :]
    words = words[: words.index("};")]
    named = re.findall(r"(\w+): \"", words)
    held = APP[APP.index("function nameCharacterHeld(") :]
    held = held[: held.index("\n}\n")]
    drawn = set(re.findall(r'case "(\w+)":', held))
    missing = [k for k in named if k not in drawn]
    assert named and not missing, f"gestures named but not drawn: {missing}"
    lexicon = APP[APP.index("  hands: {") :]
    lexicon = lexicon[: lexicon.index("  },")]
    for key in re.findall(r"^\s+(\w+): \"", lexicon, re.M):
        assert key in drawn, f"{key} can be read from a name but has no drawing"


def test_each_character_wears_a_mood_its_own_way(tmp_path: Path) -> None:
    # Round 7 (INBOX 430): "generated faces vary expression slightly per
    # character". Per mood each character favours its own eyes, brows and
    # mouth from a few near neighbours; the same character always the same.
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    start = APP.index("const NAME_MARK_FACES = {")
    end = APP.index("\n}\n", APP.index("function nameMarkLean(")) + 3
    script = tmp_path / "lean.js"
    script.write_text(
        APP[start:end]
        + "\nconst out = {};"
        + "\nfor (const mood of ['happy', 'sad', 'calm', 'surprised']) {"
        + "\n  const seen = new Set();"
        + "\n  for (let h = 1; h < 4000000000; h += 97531357) seen.add(JSON.stringify(nameMarkLean(NAME_MARK_FACES[mood], mood, h)));"
        + "\n  out[mood] = { n: seen.size, same: JSON.stringify(nameMarkLean(NAME_MARK_FACES[mood], mood, 12345)) === JSON.stringify(nameMarkLean(NAME_MARK_FACES[mood], mood, 12345)) };"
        + "\n}"
        + "\nout.untouched = JSON.stringify(nameMarkLean(NAME_MARK_FACES.dead, 'dead', 7)) === JSON.stringify(NAME_MARK_FACES.dead);"
        + "\nconsole.log(JSON.stringify(out));\n",
        encoding="utf-8",
    )
    out = json.loads(subprocess.run([node, str(script)], capture_output=True, text=True, check=True).stdout)
    for mood in ("happy", "sad", "calm", "surprised"):
        assert out[mood]["n"] >= 3, (mood, out[mood])
        assert out[mood]["same"]
    # A mood with no leanings is drawn as the table has it.
    assert out["untouched"]
