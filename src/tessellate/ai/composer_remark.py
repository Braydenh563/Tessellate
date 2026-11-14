"""Social turns the composer answers like a person (INBOX 1749, the owner:
"composer has no conversational or social ability in soo many areas").

- **Register.** "heyy" is answered casually and briefly, "good morning" with
  the welcome (`register`, `casual_hello`).
- **Remarks.** "Its been really hot today", "ugh work", "I had pizza for
  dinner", "off to bed", "merry christmas": a short human reply, then at most
  one gentle link to a note that clearly bears on it (`reply`, `topic`).
  Never "not sure what you mean", never Sources, never stats chips.

Every reader works on the person's words alone and returns None for a
question or an order, so a turn that asks for something is never taken for
chat. The note link needs the notes, so the caller hands `link` a finder.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from tessellate.ai import phrasing, question_noise
from tessellate.core.lazyre import lazy_compile

#: Words that make a message a question or an order, never a remark.
_ASKING = frozenset(
    "what when where who whom whose why how which do does did is are was were am can could will would should shall have has may might "
    "show find search list tell give remind add make create open delete remove write note save set call send read help explain count "
    "summarise summarize compare plan draft translate convert calculate remember log record store jot put keep pin tag move rename archive mark schedule book buy text email message ring phone check cancel turn".split()
)
_TIMED = lazy_compile(r"\b(?:tomorrow|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday|at \d|\d{1,2}(?::\d\d)? ?(?:am|pm)|on the \d)\b")
_END = r"[\s?.!,]*$"


def _clean(text: str) -> str:
    plain = question_noise.strip_symbols(question_noise.destretch(str(text or ""))).replace("’", "'").lower()
    return " ".join(plain.replace("?", " ").replace("!", " ").replace(",", " ").split()).strip(" .")


#: A turn that names the notebook is about it, not a remark ("what's the weather note").
_NOTEBOOK = lazy_compile(r"\b(?:notes?|reminders?|notebook|tasks?)\b")


def _asks(said: str) -> bool:
    """Whether the first word opens a question or a command ("what's", "show")."""
    first = said.split()[0].split("'")[0] if said else ""
    return first in _ASKING or first in {"whats", "hows", "wheres", "whos"}


def _is_remark(said: str) -> bool:
    words = said.split()
    #: "what a day" is an exclamation, not a question.
    return 1 <= len(words) <= 10 and (not _asks(said) or said.startswith("what a ")) and (_WISH_NAMED.match(said) or not _TIMED.search(said)) and not _NOTEBOOK.search(said)


# --- the register of a hello -----------------------------------------------------------------

#: The hellos that are written out, not tapped: they get the welcome, with the day's facts.
_FORMAL = lazy_compile(r"^\W*(?:good (?:morning|afternoon|evening|day)|greetings|salutations|hello)\b(?!\s+there)", re.I)
_OPENERS = {"hi": "Hi", "hey": "Hey", "heya": "Heya", "hiya": "Hiya", "yo": "Yo", "sup": "Hey", "howdy": "Howdy", "gday": "G'day", "morning": "Morning", "hello": "Hello", "evening": "Evening", "afternoon": "Afternoon"}
_TAILS = {
    "natural": ("", "How is your day going?", "What are you up to?", "What is on your mind?", "Good to see you.", "Anything I can dig up for you?"),
    "professional": ("", "How can I help?", "What would you like to look up?"),
}


def register(message: str) -> str:
    """"casual" for a tapped hello ("heyy", "yo", "hi there", "hellooo") and
    "formal" for a written one ("good morning", "hello", "hello, I hope you
    are well"): the first is answered in a line, the second with the welcome."""
    raw = str(message or "").strip()
    if _FORMAL.match(raw) and not re.match(r"^\W*hello{2,}", raw, re.I):
        return "formal"
    return "casual"


#: What may follow the hello word in a message that is still only a hello ("hey there", "hi how are you doing today").
_HELLO_REST = frozenset(
    "there all everyone atlas mate buddy friend again you how are is it going things doing today u r ya whats what's hows up sup with the day "
    "been good morning afternoon evening".split()
)


def bare_hello(message: str) -> bool:
    """Whether the whole message is a hello, with at most a "how are you" after it. A hello in front of a request
    ("hey, what did I write about pasta", "yo open my last note") is the request: it is searched or done, not greeted."""
    words = _clean(message).split()
    if not words or len(words) > 8:
        return False
    rest = words[1:]
    return all(w in _HELLO_REST for w in rest) or (len(rest) == 1 and rest[0] not in _ASKING)


def casual_hello(message: str, voice: str = "natural", recent: list[str] | tuple = (), seed: str = "", asked_how: bool = False) -> str:
    """A hello in the person's own register: their word back ("Heyy.",
    "Hi."), then at most one short line. No time of day, no counts, no
    note: they only said hi. `asked_how` leaves the tail off, since the
    reply to "how are you" follows it."""
    first = re.match(r"^\W*([a-z']+)", question_noise.drop_filler(str(message or "")).lower())
    word = first.group(1) if first else "hey"
    stretched = re.match(r"^\W*([a-z]*?)([a-z])\2{1,}$", word)
    base = (stretched.group(1) + stretched.group(2)) if stretched else word
    opener = _OPENERS.get(base) or _OPENERS.get(word) or "Hey"
    if stretched and base in _OPENERS:
        opener = _OPENERS[base] + stretched.group(2) * 1
    said = "professional" if voice == "professional" else "natural"
    if said == "professional":
        opener = "Hello"
    tail = "" if asked_how else phrasing.choose(_TAILS[said], f"casual:{message}", list(recent), seed)
    return f"{opener}." + (f" {tail}" if tail else "")


# --- remarks ---------------------------------------------------------------------------------


def _pick(lines: tuple[str, ...], said: str, recent: list[str] | tuple, seed: str) -> str:
    return phrasing.choose(lines, said, list(recent), seed)


_WEATHER_WORDS = (
    r"hot|boiling|baking|roasting|warm|sweltering|humid|muggy|sunny|heatwave|cold|freezing|chilly|frosty|icy|snow|snowing|snowy|rain|raining|rainy|drizzling|"
    r"pouring|snowed|rained|hailed|thundered|windy|stormy|storm|foggy|cloudy|grey|gloomy|weather"
)
_WEATHER = lazy_compile(rf"\b(?P<w>{_WEATHER_WORDS})\b")
#: A weather word is a remark only in a statement ("it's so hot", "so cold outside", "raining again"), never inside a
#: search for a thing ("rainy day ideas", "hot sauce recipes today", "heat pump"): it leads with a subject or an
#: intensifier, or it is the word alone with only a where or when after it.
_WEATHER_SUBJECT = lazy_compile(
    rf"^(?:it|its|it's|it is|the weather|the day|today|this morning|tonight|outside|in here|so|really|very|wow|ugh|nice|lovely|horrible|awful)\b|"
    rf"^(?:{_WEATHER_WORDS})(?: (?:today|again|outside|out there|in here|now|tonight|this morning))*$"
)
_PAST = {"snowed": "snow", "rained": "rain", "hailed": "rain", "thundered": "storm"}
_HOT = frozenset("hot boiling baking roasting warm sweltering humid muggy sunny heatwave".split())
_COLD = frozenset("cold freezing chilly frosty icy snow snowing snowy snowed".split())
_WEATHER_LINES = {
    "hot": ("That sounds uncomfortable. Keep some water close and stay out of the sun if you can.", "Hot days are draining. Drink plenty and take it slowly.", "Rough with the heat. A cold drink and some shade will help."),
    "cold": ("Brr. Wrap up warm and keep something hot to drink nearby.", "That sounds bitter. I hope you can stay somewhere warm.", "Cold days call for a warm drink and a thick jumper."),
    "wet": ("A day for staying in, if you can. I hope you stay dry.", "Grey weather does that to a day. A warm drink helps.", "Hope you are somewhere dry."),
    "fair": ("It sounds like a good one. I hope you get outside for a bit.", "Nice. Worth getting some air if you can."),
}
_WEATHER_PRO = {
    "hot": ("The heat sounds uncomfortable. Please keep hydrated.",),
    "cold": ("That sounds cold. I hope you can stay warm.",),
    "wet": ("I hope you are able to stay dry.",),
    "fair": ("That sounds pleasant.",),
}
_FAIR = lazy_compile(r"\b(?:nice|lovely|beautiful|gorgeous|great|perfect|glorious|sunny)\b")


def _weather(said: str) -> tuple[str, str] | None:
    found = _WEATHER.search(said)
    if not found or not _WEATHER_SUBJECT.search(said):
        return None
    word = _PAST.get(found.group("w"), found.group("w"))
    if word == "weather":
        kind = "fair" if _FAIR.search(said) else "wet" if re.search(r"\b(?:awful|horrible|terrible|miserable|grim|rubbish|bad|dreadful)\b", said) else "fair"
    else:
        kind = "hot" if word in _HOT else "cold" if word in _COLD else "wet"
        if kind == "hot" and word == "sunny":
            kind = "fair"
    return kind, word


_SLEPT = lazy_compile(
    r"\b(?:couldn'?t sleep|can'?t sleep|cannot sleep|didn'?t sleep|no sleep|barely slept|hardly slept|slept (?:badly|terribly|poorly|awfully)|up all night|insomnia|"
    r"(?:bad|rough|terrible|awful|restless|sleepless) night|tossing and turning)\b"
)
_SLEPT_WELL = lazy_compile(r"\bslept (?:well|great|like a baby|really well|so well)\b|\b(?:good|great|lovely) (?:night'?s? sleep|sleep)\b")
_BEDTIME = lazy_compile(r"^(?:i'?m |i am |ok |okay |right |well ){0,6}(?:off to bed|going to bed|going to sleep|heading to bed|heading off to bed|time for bed|bedtime|time to sleep|turning in|calling it a night|hitting the hay|need to sleep)\b")
_SLEEP_LINES = ("That is rotten. A bad night makes everything harder, so go gently today.", "Sorry to hear that. Tired days are slow ones; be kind to yourself.", "That sounds like a long night. Try to rest when you can today.")
_SLEEP_WELL_LINES = ("Good. A proper night's sleep sets the day up.", "Lovely, that makes everything easier.")
_BEDTIME_LINES = ("Sleep well. Your notes will keep.", "Goodnight, then. Rest well.", "Sleep well. Everything you wrote is saved.")

_WORK_ENDS = (
    r"(?:rough|hard|tough|busy|crazy|mad|stressful|exhausting|boring|awful|terrible|long|slow|hectic|a nightmare|a lot|too much|killing me|a drag|draining|a grind|chaos|a mess)"
)
_WORK_NOUN = r"(?:work|my job|the job|the office|my boss|meetings?|my commute|the commute|uni|school|class|lectures?|the exam|exams|homework|college|the deadline|monday|mondays|traffic|emails?)"
_BAD_DAY = lazy_compile(
    rf"^(?:ugh|urgh|argh|oof|god|man|omg|wow|well|so|just)* ?(?:{_WORK_NOUN}(?: (?:is|was|has been|are|were|today|again))*(?: (?:so|really|very|just|too|a bit|pretty|quite))* {_WORK_ENDS}|"
    rf"(?:a |what a |such a |it was a |it'?s been a |today was a |today'?s been a |had a |what a )?(?:really |very |so |pretty )*(?:bad|rough|tough|long|hard|terrible|awful|stressful|busy|exhausting|crazy|mad|draining|hectic) (?:day|week|morning|afternoon|one))(?: (?:at work|today|again|so far))*{_END}"
)
_WHAT_A_DAY = lazy_compile(rf"^what a (?:day|week|morning|afternoon|night)(?: (?:it'?s been|it was|today|so far))*{_END}")
_WHAT_A_DAY_LINES = ("Sounds like quite a day. I hope it settles down.", "That sounds like a lot. Take a breath when you can.", "Quite a day, then. I hope the rest of it is kinder.")
_BAD_WORK_ONLY = lazy_compile(rf"^(?:ugh|urgh|argh|oof)+ {_WORK_NOUN}{_END}")
_GOOD_DAY = lazy_compile(
    r"^(?:(?:i )?(?:had|having|just had|'?ve had|have had) |(?:a |such a |what a ))(?:a |such a )?(?:really |very |so |pretty )*(?:great|good|lovely|nice|wonderful|fantastic|brilliant|amazing|productive|relaxing|fun) (?:day|week|morning|afternoon|weekend|time)"
    r"(?: (?:today|so far|at work|overall))*[\s.!]*$|^(?:today|it) (?:was|has been|'s been|is) (?:a )?(?:really |very |so |pretty )*(?:great|good|lovely|nice|wonderful|fantastic|brilliant|amazing|productive|relaxing|fun)"
    r"(?: (?:day|today|so far))*[\s.!]*$"
)
_BAD_DAY_LINES = ("That sounds like a heavy one. I hope it eases off soon.", "Sorry, that sounds exhausting. You have earned a break.", "Rough. Be kind to yourself tonight.", "I am sorry it has been like that. It will pass.")
_BAD_DAY_PRO = ("I am sorry to hear it has been a difficult day.",)
_GOOD_DAY_LINES = ("Glad to hear it. Those days are worth holding on to.", "Lovely, I am glad it went well.", "That is good to hear.")
_GOOD_DAY_PRO = ("I am glad to hear it went well.",)

_HUNGRY = lazy_compile(r"^(?:i'?m |i am |getting |so |really |feeling ){0,6}(?:hungry|starving|famished|peckish|ravenous|hangry)\b")
_ATE = lazy_compile(
    r"^(?:i |we |just |i'?ve |i have ){0,6}(?:had|ate|eaten|having|eating|made|am making|cooked|am cooking|'?m cooking|'?m making|cooking|making|baking|baked|grabbed|am grabbing|'?m grabbing|got)"
    r" (?:some |a |an |the |my |another |leftover |leftovers of )?(?P<what>[a-z][a-z ]{1,24}?)(?: for (?:breakfast|brunch|lunch|dinner|tea|supper|dessert|a snack))?(?: (?:today|tonight|again|earlier|just now))*[\s.!]*$"
)
_NEED = lazy_compile(r"^(?:i |we )?(?:really |just |badly )*(?:need|want|could do|could use|am craving|'?m craving) (?:a |an |some |another )?(?:coffee|tea|food|snack|drink|break|nap|rest|lie down|sleep)\b")
_NEED_LINES = ("Go and get it. Your notes will wait.", "Sounds like it is time. I will be here when you are back.", "Then take it. Nothing here needs you this minute.")
_MEAL_TIME = lazy_compile(r"^(?:it'?s |its |time for |time to eat|lunch ?time|dinner ?time|breakfast ?time|coffee ?time|tea ?time|snack ?time|(?:i'?m |i am |we'?re ){0,4}(?:cooking|baking|making (?:dinner|lunch|tea|breakfast|supper)|having (?:a )?(?:takeaway|takeout|bbq|barbecue)))\b")
_FOOD_NOUNS = lazy_compile(r"\b(?:breakfast|brunch|lunch|dinner|tea|supper|dessert|snack|coffee|food|meal|pizza|pasta|soup|curry|salad|toast|cake|pancakes?|sandwich|noodles|rice|burger|steak|eggs|bread|cookies|biscuits|cooking|baking|bbq|barbecue|takeaway|takeout|curry|stir fry)\b")
_FOOD_LINES = ("Sounds good. Enjoy it.", "Nice, I hope it is a good one.", "Hope it hits the spot.", "Enjoy your meal.")
_HUNGRY_LINES = ("Go and get something to eat. Your notes will wait.", "Sounds like it is time for a snack.", "Feed yourself first; I am not going anywhere.")
_FOOD_PRO = ("I hope you enjoy it.",)

_GOING = lazy_compile(
    r"^(?:i'?m |i am |we'?re |just |right |ok |okay |well |off |heading |going ){0,6}(?:going|headed|heading|off|popping|nipping|running|walking) (?:out )?(?:to|for|down to|over to|into) (?:the |a |my |some )?"
    r"(?P<what>gym|run|jog|walk|swim|shops?|shopping|store|supermarket|work|class|lecture|uni|school|park|beach|doctor|dentist|library|cinema|pub|bank|yoga|climbing|hike|bike ride|cycle|workout|training|practice)\b"
)
_BACK = lazy_compile(r"^(?:i'?m |i am |just ){0,4}(?:back|home|back home|back again|here again|just got home|got home|just got back|got back)\b[\s.!]*$")
_GOING_LINES = ("Have a good one. I will be here when you are back.", "Enjoy it. Your notes will keep.", "Sounds good. See you after.", "Have fun with that.")
_GOING_PRO = ("Have a good time. I will be here when you return.",)
_BACK_LINES = ("Welcome back. How did it go?", "Good to have you back.", "Welcome back. Anything to jot down?")

_WISH_NAMED = lazy_compile(r"^(?P<w>happy|merry) (?P<what>birthday|christmas|new year|easter|halloween|diwali|eid|hanukkah|thanksgiving|valentines?|anniversary|friday|monday|saturday|sunday|weekend|holidays?|mothers? day|fathers? day|year|day)")
_WELLWISH = lazy_compile(r"\bhope (?:you(?:'re| are| have|'ve)? (?:doing |been |having |feeling )*(?:well|good|ok|okay|great|fine|a (?:good|great|nice) (?:day|one))|all is well|everything is (?:well|good|ok)|things are (?:well|good|going well))")
_PRAISE = lazy_compile(r"^(?:i |we )?(?:really |just |absolutely )*(?:love|like|adore|enjoy|appreciate)(?: using)? (?:this|the|my) (?:app|assistant|tool|notebook|chat|bot)\b|^(?:this|the) (?:app|assistant|tool|notebook|chat|bot) (?:is|'?s) (?:so |really |very |pretty |quite )*(?:great|amazing|awesome|good|brilliant|useful|cool|helpful|nice|fantastic|handy|lovely)\b")
_PRAISE_LINES = ("That is good to hear. I am glad it helps.", "Thank you. That is kind of you to say.", "Glad it is useful. Tell me if anything could be better.")
_GRUMBLE = lazy_compile(r"^(?:i |we )?(?:really |just |absolutely )*(?:hate|dislike|can'?t stand) (?:this|the|my) (?:app|assistant|tool|notebook|chat|bot)\b|^(?:this|the) (?:app|assistant|tool|notebook|chat|bot) (?:is|'?s) (?:so |really |very |pretty |quite )*(?:bad|slow|useless|rubbish|annoying|broken|terrible|awful|confusing|frustrating|crap|rubbish)\b")
_GRUMBLE_LINES = ("Sorry about that. What is not working for you?", "That is fair to say if it is getting in your way. What went wrong?", "I am sorry. Tell me what is annoying you and I will try to do better.")
_MEET = lazy_compile(r"^(?:it'?s |its )?(?:nice|good|great|a pleasure|lovely|pleased|glad) to (?:meet|see|talk to|chat with|speak with|speak to) you\b")
_MEET_LINES = ("Nice to meet you too.", "Likewise. I am glad you are here.")

#: "can you read pdfs" and "would you read this aloud" are requests; only do, did and would ask about a taste.
_LIKE = lazy_compile(r"^(?:do|did|would) you (?:really |actually |even )?(?:like|love|enjoy|prefer|listen to|watch|play|eat|drink)(?: [a-z]+)? (?P<what>[a-z][a-z' ]{1,24}?)(?: at all| too| much)?$")
_WHATSUP = lazy_compile(r"^(?:hey |hi |so )*(?:what'?s|whats|what is|wassup|wazzup|whassup) (?:up|new with you|going on)(?: with you)?$")
_WHATSUP_LINES = ("Not much, just keeping your notes in order. What is up with you?", "All quiet here. What are you up to?", "Nothing much on my side. How about you?")
_LIKE_LINES = ("I am a program, so I do not have tastes, but I am curious about yours. Do you like {what}?", "Not the way you do, being a program. What about you, do you like {what}?")


def _is_question(said: str) -> bool:
    return _asks(said) if said else True


def _wish_back(said: str) -> tuple[str, str] | None:
    found = _WISH_NAMED.match(said)
    if not found:
        return None
    what = found.group("what")
    if what in {"birthday", "anniversary"}:
        return ("A happy one to whoever it is, then.", "")
    if what in {"friday", "monday", "saturday", "sunday", "weekend", "day", "year"}:
        return (f"{found.group('w').capitalize()} {what.capitalize()} to you too.", "")
    return (f"{found.group('w').capitalize()} {what.title()} to you too.", what.split()[0])


def _words(said: str, pick: Callable[..., str]) -> tuple[str, str] | None:
    """The remarks that are words said to Atlas: well wishes, praise, a grumble, a greeting wished back."""
    if _WELLWISH.search(said):
        greet = "Hello." if re.match(r"^(?:hello|hi|hey|good (?:morning|afternoon|evening))", said) else ""
        return " ".join(p for p in (greet, "I am well, thank you. How are you?") if p), ""
    if _PRAISE.match(said):
        return pick(_PRAISE_LINES), ""
    if _GRUMBLE.match(said):
        return pick(_GRUMBLE_LINES), ""
    if _MEET.match(said):
        return pick(_MEET_LINES), ""
    if (wish := _wish_back(said)) is not None:
        return wish
    return None


def _body(said: str, pick: Callable[..., str]) -> tuple[str, str] | None:
    """The remarks about sleep, the weather and how the day went."""
    if _BEDTIME.match(said):
        return pick(_BEDTIME_LINES), ""
    if _SLEPT.search(said):
        return pick(_SLEEP_LINES), "sleep"
    if _SLEPT_WELL.search(said):
        return pick(_SLEEP_WELL_LINES), ""
    if weather := _weather(said):
        kind, word = weather
        return pick(_WEATHER_LINES[kind], _WEATHER_PRO[kind]), word if kind != "fair" else ""
    if _WHAT_A_DAY.match(said):
        return pick(_WHAT_A_DAY_LINES), ""
    if _GOOD_DAY.match(said):
        return pick(_GOOD_DAY_LINES, _GOOD_DAY_PRO), ""
    if _BAD_DAY.match(said) or _BAD_WORK_ONLY.match(said):
        return pick(_BAD_DAY_LINES, _BAD_DAY_PRO), ""
    return None


def _life(said: str, pick: Callable[..., str]) -> tuple[str, str] | None:
    """The remarks about needs, food and going somewhere."""
    if _NEED.match(said):
        return pick(_NEED_LINES), ""
    if _HUNGRY.match(said):
        return pick(_HUNGRY_LINES), ""
    if (ate := _ATE.match(said)) and _FOOD_NOUNS.search(said):
        what = ate.group("what").strip()
        food = _FOOD_NOUNS.search(what)
        return pick(_FOOD_LINES, _FOOD_PRO), (food.group(0) if food and food.group(0) not in {"breakfast", "brunch", "lunch", "dinner", "tea", "supper", "dessert", "snack", "food", "meal"} else "")
    if _MEAL_TIME.match(said) and _FOOD_NOUNS.search(said):
        return pick(_FOOD_LINES, _FOOD_PRO), ""
    if going := _GOING.match(said):
        what = going.group("what")
        stem = {"jog": "run", "shops": "", "shop": "", "shopping": "", "work": "", "class": "", "lecture": "", "store": "", "supermarket": "", "park": "", "beach": "", "pub": "", "bank": "bank", "library": "", "training": "", "practice": "", "workout": "gym"}.get(what, what)
        return pick(_GOING_LINES, _GOING_PRO), stem
    if _BACK.match(said):
        return pick(_BACK_LINES), ""
    return None


def reply(question: str, history: list[dict] | None = None, seed: str = "", voice: str = "natural") -> tuple[str, str] | None:
    """`(the reply, a word a note may bear on it with)` for a remark, else None.
    The word is "" when no note could clearly bear on the turn ("what a day")."""
    said = _clean(question)
    recent = [str(t.get("answer") or "") for t in (history or [])][-phrasing.RECENT :]
    pro = voice == "professional"
    #: A remark is a few words; a long message never reaches the patterns below.
    if not said or len(said.split()) > 10:
        return None
    if (liked := _LIKE.match(said)) and not re.search(r"\b(?:note|notes|app|me|my)\b", said):
        return _pick(_LIKE_LINES, said, recent, seed).format(what=liked.group("what")), ""
    if _WHATSUP.match(said):
        return _pick(_WHATSUP_LINES, said, recent, seed), ""
    if not said or not _is_remark(said):
        return None

    def pick(lines: tuple[str, ...], pro_lines: tuple[str, ...] = ()) -> str:
        return _pick(pro_lines if pro and pro_lines else lines, said, recent, seed)

    for part in (_words, _body, _life):
        if (found := part(said, pick)) is not None:
            return found
    return None


def is_remark(question: str) -> bool:
    """Whether the whole message is a remark (a turn to talk back to, never to search for)."""
    return reply(question) is not None


# --- the gentle link ---------------------------------------------------------------------------

_LINKED = ("You have a note on this: {link}.", "A note of yours bears on it: {link}.", "There is a note on this: {link}.")
_LINKED_PRO = ("A related note: {link}.",)


#: The words a topic goes by in a note, so "hot" never finds "Hotel" and "sleep" finds "slept".
_FORMS = {
    "hot": "hot|heat|heatwave|heated", "heat": "heat|heatwave|hot", "warm": "warm|warmth", "cold": "cold|colder|coldest", "freezing": "freezing|frozen|cold",
    "chilly": "chilly|cold", "snow": "snow|snowing|snowed|snowy", "snowing": "snow|snowing|snowed", "rain": "rain|rains|rained|raining|rainy", "raining": "rain|rained|raining|rainy",
    "rainy": "rain|rained|raining|rainy", "windy": "wind|windy", "stormy": "storm|storms|stormy", "sleep": "sleep|slept|sleeping|asleep|insomnia",
    "run": "run|runs|running|ran|runner", "walk": "walk|walks|walked|walking", "swim": "swim|swims|swimming|swam", "gym": "gym|gyms", "hike": "hike|hikes|hiked|hiking",
    "cycle": "cycle|cycling|cycled|bike|biking", "pizza": "pizza|pizzas", "pasta": "pasta", "christmas": "christmas|xmas", "dentist": "dentist|dentists",
}


def topic_pattern(topic: str) -> str:
    """The regex (whole words) a note must hold for `topic` to bear on it; "" for none."""
    word = re.sub(r"[^a-z ]", "", str(topic or "").lower()).strip()
    return rf"\b(?:{_FORMS[word]})\b" if word in _FORMS else (rf"\b{re.escape(word)}s?\b" if word else "")


def with_link(line: str, topic: str, finder: Callable[[str], tuple[int, str] | None], seed: str = "", voice: str = "natural") -> str:
    """`line`, then at most one link to the newest note that mentions `topic`
    (`finder(word)` gives `(id, title)` or None); nothing when none does."""
    if not topic:
        return line
    found = finder(topic)
    if not found:
        return line
    note_id, title = found
    link = f"[{title.replace('[', '(').replace(']', ')')}](#/notes/{note_id})"
    options = _LINKED_PRO if voice == "professional" else _LINKED
    return f"{line} {phrasing.choose(options, topic, [], seed).format(link=link)}"


def facts(question: str, finder: Callable[[str], tuple[int, str] | None]) -> str:
    """What a model is told about a remark so it answers as the composer does
    (parity, decision 75): that it is a remark, and the one note that bears on it."""
    got = reply(question)
    if got is None:
        return ""
    line = "The person made a remark, not a request. Reply in a line or two as a friendly person would, with no question about their notes."
    topic = got[1]
    found = finder(topic) if topic else None
    if found:
        line += f" A note that bears on it, which you may link once: [{found[1]}](#/notes/{found[0]})."
    return line

