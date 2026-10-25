"""The composition layer's word pools (`composer_compose.py` scores them).

Every entry is the app's own wording around facts the caller passes in; none
says anything about the world. A candidate is `c(text, voices, emotions,
keys)`: `voices` is letters (w warm, t terse, p playful, f formal; none means
any), `emotions` is letters (S stressed, R rushed, U upset, H upbeat; none
means any), `keys` are question-word prefixes that make it more apt.

The voices differ in rhythm and not only in their opener: terse frames are
fragments, formal ones full sentences with a subject, warm ones add a clause
of company, playful ones a light image. Sentence case, no exclamation marks,
no em-dashes (the tests hold it).
"""

from __future__ import annotations

from typing import NamedTuple

_V = {"w": "warm", "t": "terse", "p": "playful", "f": "formal"}
_E = {"S": "stressed", "R": "rushed", "U": "upset", "H": "upbeat"}


class Cand(NamedTuple):
    text: str
    voices: frozenset[str]
    emotions: frozenset[str]
    keys: tuple[str, ...]


def c(text: str, v: str = "", e: str = "", k: str = "") -> Cand:
    return Cand(text, frozenset(_V[x] for x in v), frozenset(_E[x] for x in e), tuple(k.split()))


OPENERS: tuple[Cand, ...] = (
    c("Sure.", "wt"), c("Of course.", "wf"), c("Happy to.", "w"), c("Right, here you go.", "w"), c("Let me see.", "w"),
    c("Okay.", "wt"), c("Gladly.", "wf"), c("Here you are.", "w"), c("Let me check.", "wf"),
    c("Okay, steady. Let us take this one step at a time.", "w", "S"), c("Take a breath, this is manageable.", "w", "S"),
    c("No rush. We will go through it together.", "w", "S"), c("Okay, steady.", "t", "S"), c("One thing at a time.", "t", "S"),
    c("Sorry about that.", "wt", "U"), c("That sounds frustrating, so let me help.", "w", "U"), c("Fair enough, let me put it right.", "w", "U"),
    c("Sorry.", "t", "U"),
    c("Glad you asked.", "w", "H"), c("Happy to help with that.", "w", "H"), c("Good one.", "wt", "H"), c("Nice, here goes.", "w", "H"),
    c("Certainly.", "f"), c("Understood.", "f"), c("As requested.", "f"), c("Very well.", "f"),
    c("I will keep this orderly, and take it in turn.", "f", "S"), c("Let us proceed in order.", "f", "S"),
    c("My apologies for the difficulty.", "f", "U"), c("I understand the frustration.", "f", "U"),
    c("Pleased to help.", "f", "H"), c("A pleasure.", "f", "H"),
    c("On it, notebook open.", "p"), c("Let me rummage through the notebook.", "p"), c("Consider it handled.", "p"),
    c("One moment, flipping pages.", "p"), c("Right, sleeves rolled up.", "p"), c("Notebook is open.", "p"),
    c("Deep breath, we have got this.", "p", "S"), c("Easy does it, one page at a time.", "p", "S"),
    c("Ugh, fair. Let me fix that.", "p", "U"), c("That is annoying. Let me try again.", "p", "U"),
    c("Love the energy.", "p", "H"), c("That is a fun one.", "p", "H"),
)

CLOSERS: tuple[Cand, ...] = (
    c("Say the word if you want more.", "w"), c("Ask if you want the details.", "w"), c("I am here if you need anything else.", "w"),
    c("Want me to dig further?", "w"), c("Tell me if I should look deeper.", "w"), c("That is the lot for now.", "w"),
    c("Anything else?", "t"), c("More on request.", "t"), c("Ask for detail.", "t"),
    c("Further detail is available on request.", "f"), c("Let me know if anything else is needed.", "f"),
    c("I can expand on any of these.", "f"), c("Please say if you would like more.", "f"),
    c("Poke me if you want the long version.", "p"), c("That is the whole pile, for now.", "p"), c("More where that came from, if you like.", "p"),
    c("Shout if you want the deep dive.", "p"),
    c("One thing at a time is enough. Pick one and I will stay on it.", "w", "S"), c("You do not have to do it all today.", "w", "S"),
    c("Start with the first and the rest can wait.", "wp", "S"), c("Start with the first.", "t", "S"),
    c("Let me know where to begin.", "f", "S"),
    c("Tell me what went wrong and I will try again.", "w", "U"), c("Ask it another way if this missed.", "wt", "U"),
    c("If this missed, say so and I will look again.", "f", "U"),
    c("Glad that helps. More whenever you like.", "w", "H"), c("Keep them coming.", "pt", "H"),
)

BRIDGES: tuple[Cand, ...] = (
    c("Also,", "w"), c("On top of that,", "w"), c("And", "w"), c("Plus,", "p"), c("Oh, and", "p"), c("Then there is this:", "p"),
    c("Also:", "t"), c("And:", "t"), c("Additionally,", "f"), c("Furthermore,", "f"), c("In addition,", "f"),
)

ABILITY_OPENERS: dict[str, tuple[Cand, ...]] = {
    "due": (c("Looking at the calendar.", "wf"), c("Checking what is dated.", "wt"), c("Calendar open.", "tp")),
    "plan": (c("Let us lay it out.", "w"), c("Here is a shape for it.", "wf"), c("Planning mode.", "tp")),
    "study": (c("Study time.", "tp"), c("Let us get you ready.", "w"), c("Right, to the books.", "p")),
}
ABILITY_OPENERS["act_done"] = (
    c("Done.", "wt"), c("Okay.", "wt"), c("Noted.", "wtf"), c("Certainly.", "f"), c("Right away.", "f"), c("Sorted.", "p"), c("Easy.", "p"),
    c("Got it.", "w"), c("Consider it done.", "p"), c("Of course.", "wf"),
)
ABILITY_OPENERS["act_ask"] = (c("Nearly there.", "wp"), c("One question.", "tw"), c("Before I do that.", "wf"))
ABILITY_CLOSERS: dict[str, tuple[Cand, ...]] = {
    "due": (c("Ask for the next week if you want to look further ahead.", "w", "", "week"), c("Next week is one question away.", "tp", "", "week")),
    "study": (c("Ask for a quiz when you are ready.", "w", "", "quiz cards study"), c("Quiz me later is one tap away.", "tp", "", "quiz cards")),
}

FRAMES: dict[str, tuple[Cand, ...]] = {
    # ---- recent notes: "what did I write about X this week" ----
    "recent": (
        c("You wrote about {topic} in {count} {span}:", "w"), c("{topic} {span}: {count}, newest first:", "wp"),
        c("{span}, {topic} comes up in {count}:", "w"), c("Here is what you saved on {topic} {span}, {count} in all:", "w"),
        c("{topic}, {span}: {count}.", "t"), c("{topic}: {count} {span}.", "t"), c("{count} on {topic}, {span}.", "t"), c("Found {count} on {topic} {span}.", "t"),
        c("{topic} is recorded in {count} {span}. Here they are:", "f"), c("You recorded {topic} in {count} {span}:", "f"),
        c("The notes on {topic} {span} number {count}:", "f"), c("For {span}, {topic} appears in {count}:", "f"),
        c("{topic} turned up in {count} {span}, newest on top:", "p"), c("I dug up {count} on {topic} {span}:", "p"),
        c("{span}, {topic} cropped up in {count}:", "p"), c("The notebook has {count} on {topic} {span}:", "p"),
    ),
    "recent_any": (
        c("You wrote {count} {span}:", "w"), c("{count} {span}, newest first:", "w"), c("Here are your {count} {span}:", "w"),
        c("Your notebook grew by {count} {span}:", "w"),
        c("{span}: {count}.", "t"), c("{count} {span}.", "t"), c("Newest first, {count} {span}:", "t"), c("{count}, {span}:", "t"),
        c("You recorded {count} {span}:", "f"), c("{span} produced {count}, listed newest first:", "f"), c("The notebook holds {count} {span}:", "f"),
        c("For {span}, there are {count}:", "f"),
        c("{span} brought {count} to the pile:", "p"), c("Fresh off the press, {count} {span}:", "p"), c("The scribbling tally for {span} is {count}:", "p"),
        c("Look at you, {count} {span}:", "p"),
    ),
    "recent_none": (
        c("You did not write anything about {topic} {span}.", "w"), c("No note {span} mentions {topic}.", "wt"), c("Nothing {span} touches {topic}.", "wt"),
        c("I looked, and {topic} is not in anything you wrote {span}.", "w"),
        c("No notes on {topic} {span}.", "t"), c("{topic}, {span}: nothing.", "t"), c("Nothing on {topic} {span}.", "t"),
        c("No entry {span} refers to {topic}.", "f"), c("The notebook holds nothing on {topic} {span}.", "f"), c("There is no record of {topic} {span}.", "f"),
        c("{topic} has not made it into the notebook {span}.", "p"), c("Not a word on {topic} {span}. The pages are quiet.", "p"),
        c("I turned over every page {span} and {topic} is nowhere.", "p"),
    ),
    # ---- due and dated ----
    "due": (
        c("Coming up, {span}: {count}.", "w"), c("Here is what is due or dated for {span}, {count} in all:", "w"), c("{count} for {span}:", "w"),
        c("For {span} you have {count}:", "w"),
        c("{span}: {count}.", "t"), c("Due {span}: {count}.", "t"), c("{count}, {span}:", "t"), c("{count} dated, {span}.", "t"),
        c("You have {count} dated {span}:", "f"), c("The calendar for {span} lists {count}:", "f"), c("{span} holds {count}, set out below:", "f"),
        c("For {span}, {count} are due or dated:", "f"),
        c("{span} is carrying {count}:", "p"), c("The calendar says {count} for {span}:", "p"), c("{span} has {count} waiting in the wings:", "p"),
        c("On the horizon for {span}: {count}.", "p"),
    ),
    "due_overdue": (
        c("Nothing new is dated for {span}, but something is overdue.", "w"), c("{span} is clear of new dates, though something has slipped past.", "w"),
        c("Nothing new {span}. Something is overdue.", "t"), c("{span}: nothing new, one overdue.", "t"),
        c("No new dates fall in {span}; an earlier item is overdue.", "f"), c("{span} carries no new dates, but an item is overdue.", "f"),
        c("{span} is quiet, but an old date is waving at you.", "p"), c("No new dates {span}, yet something is past due.", "p"),
    ),
    "plan": (
        c("Your plan for {span}, from your reminders and notes.", "w"), c("Here is {span}, laid out from what you have saved.", "w"),
        c("{span}, as your notes and reminders have it.", "w"),
        c("Plan, {span}:", "t"), c("{span}, laid out:", "t"), c("{span}: your plan.", "t"),
        c("A plan for {span}, drawn from your reminders and notes:", "f"), c("{span} is arranged below from what you have recorded.", "f"),
        c("Here is a proposed order for {span}.", "f"),
        c("I sketched {span} from your reminders and notes:", "p"), c("{span}, drawn out like a treasure map:", "p"), c("Here is how {span} could go:", "p"),
    ),
    "left": (
        c("Here is what is still open: {r} and {t}.", "w"), c("Still to do, from your reminders and your checklists: {r} and {t}.", "w"),
        c("{r} and {t} are waiting.", "w"), c("What is left, as your notebook has it: {r} and {t}.", "w"),
        c("Open: {r}; {t}.", "t"), c("Left: {r}, {t}.", "t"), c("{r}. {t}.", "t"),
        c("Outstanding are {r} and {t}.", "f"), c("The notebook shows {r} and {t} still open.", "f"), c("You have {r} and {t} remaining.", "f"),
        c("Still hanging around: {r} and {t}.", "p"), c("The to-do pile holds {r} and {t}.", "p"), c("Not done yet: {r} and {t}.", "p"),
    ),
    "left_none": (
        c("Nothing is open: no reminder waiting and no unticked checklist item in your notes.", "w"),
        c("You are clear. No reminder is waiting and every checklist item is ticked.", "w"),
        c("All clear. Nothing waiting, nothing unticked.", "w"),
        c("Nothing open.", "t"), c("Clear: no reminders, no unticked items.", "t"), c("All done.", "t"),
        c("There is nothing outstanding: no reminder is pending and every checklist item is ticked.", "f"),
        c("No reminders or unticked items remain.", "f"),
        c("The to-do pile is empty. Enjoy the quiet.", "p"), c("Nothing left on the list, not even a stray tick box.", "p"),
    ),
    # ---- definitions and counts ----
    "define": (
        c("{term}: {meaning}", "wt"), c("In short, {term} is {meaning}", "w"), c("{term} means {meaning}", "w"),
        c("The short answer on {term}: {meaning}", "w"),
        c("{term}, defined: {meaning}", "f"), c("{term} is defined as follows: {meaning}", "f"), c("As a definition, {term}: {meaning}", "f"),
        c("{term}, the quick version: {meaning}", "p"), c("Here is the gist of {term}: {meaning}", "p"), c("{term} in a nutshell: {meaning}", "p"),
        c("{term}: {meaning}", "t"), c("{term}. {meaning}", "t"), c("Definition. {term}: {meaning}", "t"), c("{term}, briefly: {meaning}", "t"),
    ),
    "define_src": (
        c("None of your notes mention “{asked}”, so that is from the app's short study glossary, not from you. Write it in a note in your own words and I will quote that next time.", "w"),
        c("Your notes do not mention “{asked}”; this comes from the app's study glossary, not from you. Put it in a note in your own words and I will quote you next time.", "w"),
        c("Not in your notes: “{asked}” is from the app's glossary. Write it in your own words and I will quote that instead.", "t"),
        c("From the glossary, not your notes (no note mentions “{asked}”). Add your own wording and I will use it.", "t"),
        c("No note of yours mentions “{asked}”, so this definition comes from the app's study glossary. If you record it in your own words, I will quote that in future.", "f"),
        c("This is from the app's glossary and not from your notebook, which does not mention “{asked}”. A note in your own words would be quoted instead.", "f"),
        c("Your notebook is silent on “{asked}”, so I borrowed the app's glossary. Jot it down your way and I will quote you instead.", "p"),
        c("That one came from the app's glossary; none of your notes mention “{asked}”. Write it your way and it becomes yours.", "p"),
    ),
    "count_note": (
        c("{link} has {words}, {detail}.", "w"), c("{link} comes to {words} ({detail}).", "w"), c("Counting {link}: {words}, {detail}.", "w"),
        c("{link}: {words}, {detail}.", "t"), c("{link}, {words}. {detail}.", "t"),
        c("{link} contains {words}, with {detail}.", "f"), c("The count for {link} is {words}, with {detail}.", "f"),
        c("I counted {link}: {words}, plus {detail}.", "p"), c("{link} weighs in at {words}, {detail}.", "p"),
    ),
    "count_text": (
        c("That text has {words} and {chars}, about {read} to read.", "w"), c("It comes to {words} and {chars}, around {read} of reading.", "w"),
        c("{words}, {chars}, about {read}.", "t"), c("{words}; {chars}; {read} to read.", "t"),
        c("The text contains {words} and {chars}, and takes about {read} to read.", "f"), c("Count: {words} and {chars}; reading time is about {read}.", "f"),
        c("I tallied {words} and {chars}, roughly {read} of reading.", "p"), c("{words} and {chars} in all, about {read} of reading.", "p"),
    ),
    # ---- dates ----
    "until": (
        c("{when} is {words} away.", "w"), c("There are {words} until {when}.", "w"), c("{when} is {words} from today.", "wf"), c("{words} to go until {when}.", "w"),
        c("{when}: {words} away.", "t"), c("{words} until {when}.", "t"), c("{words} to {when}.", "t"),
        c("{when} falls {words} from now.", "f"), c("The interval to {when} is {words}.", "f"), c("{words} remain before {when}.", "f"),
        c("{when} is {words} down the road.", "p"), c("Only {words} until {when}.", "p"), c("{when} is {words} out, and counting.", "p"),
    ),
    "until_past": (
        c("{when} was {words} ago.", "w"), c("{when} has already passed, {words} ago.", "w"), c("That was {words} ago, on {when}.", "w"),
        c("{when}: {words} ago.", "t"), c("{words} ago, {when}.", "t"),
        c("{when} passed {words} ago.", "f"), c("The date, {when}, lies {words} in the past.", "f"),
        c("{when} is {words} behind us.", "p"), c("{when} slipped by {words} ago.", "p"),
    ),
    "today": (
        c("{when} is today.", "wt"), c("That is today, {when}.", "w"), c("It is today: {when}.", "t"),
        c("The date given, {when}, is today.", "f"), c("{when} is today, as it happens.", "p"), c("Today is {when}, no waiting needed.", "p"),
    ),
    "since": (
        c("It has been {words} since {when}.", "w"), c("{words} have passed since {when}.", "w"), c("{when} was {words} ago.", "w"),
        c("{words} since {when}.", "t"), c("{when}: {words} ago.", "t"),
        c("{words} have elapsed since {when}.", "f"), c("The time since {when} is {words}.", "f"),
        c("{when} was {words} back.", "p"), c("{words} and counting since {when}.", "p"),
    ),
    "since_future": (
        c("{when} has not happened yet: it is {words} away.", "w"), c("{when} is still ahead, {words} from today.", "w"),
        c("{when} is still ahead: {words}.", "t"), c("Not yet: {when} is {words} away.", "t"),
        c("{when} has not yet occurred; it is {words} away.", "f"), c("{when} lies {words} ahead.", "f"),
        c("{when} has not come round yet, {words} to go.", "p"), c("Still to come: {when}, {words} off.", "p"),
    ),
    # ---- study ----
    "study_nonotes": (
        c("There is no note to work from yet. Write a few lines of notes, then ask again.", "w"), c("Your notebook has nothing I can study from yet.", "w"),
        c("No notes to study from yet. Write a few lines and ask again.", "t"), c("Nothing to study from yet.", "t"),
        c("The notebook holds no material to study from yet; write a few lines and ask again.", "f"), c("There are no notes to draw on yet.", "f"),
        c("The notebook is a blank page, so there is nothing to quiz yet. Scribble something and ask again.", "p"), c("No notes, no quiz. Write a few lines first.", "p"),
    ),
    "study_which": (
        c("Which note should I {what}? Open one and ask again, or name it.", "w"), c("I need a note to {what}. Name one, or open it first.", "w"),
        c("Which note do you want to {what}? Open it, or say its name.", "w"),
        c("Which note to {what}? Name it or open it.", "t"), c("A note to {what}: name one.", "t"),
        c("Please name the note I should {what}, or open it first.", "f"), c("To {what}, I need a note; please name one or open it.", "f"),
        c("Pick a note and I will {what}. Name it or open it.", "p"), c("Point me at a note to {what}.", "p"),
    ),
    "study_nothing_named": (
        c("I did not find a note about “{topic}”.", "w"), c("Nothing in your notebook is about “{topic}”.", "w"),
        c("No note about “{topic}”.", "t"), c("“{topic}”: no match.", "t"),
        c("The notebook holds no note about “{topic}”.", "f"), c("I could not locate a note on “{topic}”.", "f"),
        c("No page of yours is about “{topic}”.", "p"), c("I turned the notebook over and “{topic}” is not in it.", "p"),
    ),
    "study_summary": (
        c("The short version of {link}:", "w"), c("Here is {link} in short:", "w"), c("{link}, boiled down:", "wp"),
        c("{link}, in brief:", "t"), c("Summary of {link}:", "t"),
        c("A summary of {link} follows.", "f"), c("{link}, summarised:", "f"),
        c("{link}, squeezed into a few lines:", "p"), c("{link} in a nutshell:", "p"),
    ),
    "study_terms": (
        c("Key terms in {link}:", "w"), c("The terms {link} leans on:", "w"), c("What {link} defines or stresses:", "w"),
        c("Terms, {link}:", "t"), c("{link}: key terms.", "t"),
        c("The key terms in {link} are listed below.", "f"), c("{link} defines or stresses these terms:", "f"),
        c("{link} keeps coming back to these:", "p"), c("The vocabulary of {link}:", "p"),
    ),
    # ---- greetings and welcome ----
    "hello": (
        c("Good {tod}.", "wf"), c("Good {tod}, and welcome back.", "w"), c("Hello, and good {tod}.", "w"), c("Hi there. Good {tod}.", "w"),
        c("Good {tod}.", "t"), c("Hi. Good {tod}.", "t"), c("Hello, {tod}.", "t"), c("Good {tod}. Back at it.", "t"),
        c("Good {tod}. Welcome back to the notebook.", "f"), c("Good {tod}; I trust it has been a good day so far.", "f"),
        c("Well, hello. Good {tod}.", "p"), c("Good {tod}, the notebook missed you.", "p"), c("Hey, good {tod}. The pages are ready.", "p"),
    ),
    "welcome_new": (
        c("Welcome. This notebook is empty, so the first note starts everything.", "w"), c("Welcome. Write your first note and I will start filing it.", "w"), c("Nothing in here yet. Your first note is the start.", "w"),
        c("Your notebook is new. Jot down anything and I will find it again later.", "w"),
        c("Welcome. Nothing here yet.", "t"), c("Empty notebook. Write a first note.", "t"), c("No notes yet. Start with one.", "t"), c("New notebook. First note?", "t"),
        c("Welcome. The notebook is empty; a first note is all it takes to begin.", "f"), c("Welcome. No notes are recorded yet.", "f"),
        c("A blank notebook, my favourite kind. Write the first note.", "p"), c("Clean pages, ready for you. Start with one line.", "p"),
    ),
    "w_due": (
        c("{due} due today.", "w"), c("You have {due} due today.", "w"), c("Today has {due} waiting.", "w"),
        c("Due today: {due}.", "t"), c("{due} today.", "t"),
        c("{due} fall due today.", "f"), c("Today you have {due} due.", "f"),
        c("{due} are on today's list.", "p"), c("Today's list holds {due}.", "p"),
    ),
    "w_last": (
        c("Your last note was {last}.", "w"), c("You last wrote {last}.", "w"), c("Last time you were in {last}.", "w"),
        c("Last note: {last}.", "t"), c("Latest: {last}.", "t"),
        c("The most recent entry is {last}.", "f"), c("Your latest note is {last}.", "f"),
        c("The last page you filled was {last}.", "p"), c("You left off at {last}.", "p"),
    ),
    "w_streak": (
        c("That makes {streak} in a row.", "w"), c("You have written {streak} running.", "w"),
        c("Streak: {streak}.", "t"), c("{streak} straight.", "t"),
        c("You have kept a streak of {streak}.", "f"), c("Notes have been written for {streak} consecutively.", "f"),
        c("{streak} running, nicely done.", "p"), c("The streak stands at {streak}.", "p"),
    ),
    "w_quiet": (
        c("Nothing is due today.", "w"), c("Nothing is waiting on you today.", "w"), c("Today is clear.", "wt"), c("No dates today.", "t"),
        c("No items fall due today.", "f"), c("Nothing is scheduled for today.", "f"),
        c("Today has no deadlines, which is a gift.", "p"), c("An empty day on the calendar.", "p"),
    ),
    # ---- tool confirmations (needle slots, the composer's prose) ----
    "act_done": (
        c("Done: {what}.", "wt"), c("Done. {what}.", "w"), c("I have {what}.", "w"), c("All set, {what}.", "w"),
        c("{what}. Done.", "t"), c("Done: {what}.", "t"),
        c("It is done: {what}.", "f"), c("I have completed this: {what}.", "f"),
        c("Consider it done: {what}.", "p"), c("Handled. {what}.", "p"),
    ),
    "act_ask": (
        c("I need a little more for that: {missing}.", "w"), c("Almost there. {missing}?", "w"), c("Before I do it, {missing}.", "w"),
        c("Need: {missing}.", "t"), c("{missing}?", "t"),
        c("To proceed I require {missing}.", "f"), c("Please provide {missing} so that I can proceed.", "f"),
        c("One gap left: {missing}.", "p"), c("I am missing one thing: {missing}.", "p"),
    ),
    "act_baddate": (
        c("I could not read “{said}” as a date or time. Try something like “tomorrow at 9” or “Friday 3pm”.", "w"),
        c("“{said}” did not read as a date to me. A day and a time, like “Friday at 3pm”, works best.", "w"),
        c("Could not read “{said}” as a date. Try “tomorrow 9am”.", "t"), c("Date unclear: “{said}”.", "t"),
        c("“{said}” could not be read as a date or time; please give a day and a time, for example “Friday at 3pm”.", "f"),
        c("I was unable to interpret “{said}” as a date. A day and a time will do.", "f"),
        c("“{said}” has me stumped as a date. Give me a day and a time and I will set it.", "p"),
        c("I cannot make a date out of “{said}”. Try “Friday at 3pm”.", "p"),
    ),
    "act_none": (
        c("That is not something I can do from here with no model. I can search, count, list and set reminders.", "w"),
        c("I cannot do that without a model, but I can search, count, list and set reminders.", "w"),
        c("Not without a model. I can search, count, list and set reminders.", "t"),
        c("Outside what I can do offline. Search, count, list, remind: yes.", "t"),
        c("That request needs a model. Without one I can search, count, list and set reminders.", "f"),
        c("That one needs a language model. Offline, I can search, count, list and set reminders.", "f"),
        c("That one is beyond me without a model. Search, count, list and remind, though, I can do.", "p"),
        c("No model, no magic. But searching, counting, listing and reminders are all mine.", "p"),
    ),
}
