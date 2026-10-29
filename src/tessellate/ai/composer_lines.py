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
        c("The notes on {topic} {span} number {count}:", "f"), c("{topic} appears in {count} {span}:", "f"),
        c("{topic} turned up in {count} {span}, newest on top:", "p"), c("I dug up {count} on {topic} {span}:", "p"),
        c("{span}, {topic} cropped up in {count}:", "p"), c("The notebook has {count} on {topic} {span}:", "p"),
    ),
    "recent_any": (
        c("You wrote {count} {span}:", "w"), c("{count} {span}, newest first:", "w"), c("Here are your {count} {span}:", "w"),
        c("Your notebook grew by {count} {span}:", "w"),
        c("{span}: {count}.", "t"), c("{count} {span}.", "t"), c("Newest first, {count} {span}:", "t"), c("{count}, {span}:", "t"),
        c("You recorded {count} {span}:", "f"), c("{count} {span}, listed newest first:", "f"), c("The notebook holds {count} {span}:", "f"),
        c("There are {count} {span}:", "f"),
        c("{count} joined the pile {span}:", "p"), c("Fresh off the press, {count} {span}:", "p"), c("The scribbling tally {span} is {count}:", "p"),
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
        c("{span}: {count}.", "t"), c("Due {span}: {count}.", "t"), c("{count}, {span}:", "t"), c("Dated {span}: {count}.", "t"),
        c("You have {count} for {span}:", "f"), c("The calendar for {span} lists {count}:", "f"), c("{span} holds {count}, set out below:", "f"),
        c("For {span}, {count} are due or dated:", "f"),
        c("{span} is carrying {count}:", "p"), c("The calendar says {count} for {span}:", "p"), c("{span} has {count} waiting in the wings:", "p"),
        c("On the horizon for {span}: {count}.", "p"),
    ),
    "due_overdue": (
        c("Nothing new is dated for {span}, but something is overdue.", "w"), c("{span} is clear of new dates, though something has slipped past.", "w"),
        c("Nothing new for {span}. Something is overdue.", "t"), c("{span}: nothing new, one overdue.", "t"),
        c("No new dates for {span}; an earlier item is overdue.", "f"), c("{span} carries no new dates, but an item is overdue.", "f"),
        c("{span} is quiet, but an old date is waving at you.", "p"), c("No new dates for {span}, yet something is past due.", "p"),
    ),
    "due_none": (
        c("Nothing is dated for {span}.", "w"), c("{span} is clear: no reminder and no dated note.", "w"), c("You have nothing dated for {span}.", "w"),
        c("Nothing for {span}.", "t"), c("{span}: clear.", "t"), c("No dates for {span}.", "t"),
        c("No reminder or dated note is set for {span}.", "f"), c("The calendar holds nothing for {span}.", "f"),
        c("{span} is wide open, not a date in sight.", "p"), c("Not a thing is dated for {span}. Enjoy the quiet.", "p"),
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
    # ---- quiz feedback (graded against the note; {a} is the note's own answer) ----
    "quiz_right": (
        c("Correct.", "wt"), c("Yes, that's it.", "w"), c("Right.", "t"), c("That's right.", "w"), c("Good, that matches your note.", "w"),
        c("Yes.", "t"), c("Spot on, that matches your note.", "w", "H"), c("Correct, and well put.", "w", "H"),
        c("That is correct.", "f"), c("Correct, in agreement with your note.", "f"), c("Exactly right.", "f"),
        c("Nailed it.", "p"), c("Bang on, that matches your note.", "p"), c("Right, and I did not even have to nudge.", "p"),
        c("Correct. One step at a time and you are getting there.", "w", "SU"),
    ),
    "quiz_close": (
        c("Close enough, that counts. Your note says: {a}", "w"), c("Nearly. Your note has it as: {a} I'll count it.", "w"),
        c("Part of it, and I'll count it. The note says: {a}", "w"), c("Close, counted. Note: {a}", "t"), c("Nearly. Counted. The note says: {a}", "t"),
        c("Close enough to count. The note gives it as: {a}", "f"), c("Substantially correct; credit given. The note reads: {a}", "f"),
        c("So close, I'll let it through. The note says: {a}", "p"), c("Almost there, counted anyway. The note says: {a}", "p"),
        c("Nearly, and that is good progress. Your note says: {a}", "w", "SU"),
    ),
    "quiz_wrong": (
        c("Not quite. Your note says: {a}", "w"), c("Not this time. The note says: {a}", "w"), c("Missed that one. It is: {a}", "w"),
        c("Not quite: {a}", "t"), c("Missed. It is: {a}", "t"),
        c("That is not correct. The note reads: {a}", "f"), c("Incorrect on this occasion. The note states: {a}", "f"),
        c("Not quite, but now you know. The note says: {a}", "p"), c("Swing and a miss. The note says: {a}", "p"),
        c("Not quite, and that is fine, this is how it sticks. Your note says: {a}", "w", "SU"),
    ),
    "quiz_skip": (
        c("Skipped. The answer: {a}", "wt"), c("No problem. The answer is: {a}", "w"), c("The answer was: {a}", "wt"),
        c("Skipped. For the record, the answer is: {a}", "f"), c("Moving on. The answer was: {a}", "f"),
        c("Skipped, and here is the answer: {a}", "p"), c("Passing is allowed. The answer: {a}", "p"),
    ),
    # ---- small talk (no facts; the kind and the mood pick) ----
    "social_how": (
        c("All good here, and your notes are in order. What can I find for you?", "w"), c("Doing well, thanks for asking. What would you like to know?", "w"),
        c("Fine, thank you. Anything you want to look up?", "w"), c("Steady and ready. How are you getting on?", "w"),
        c("Good, thanks. What are we working on?", "t"), c("Fine. You?", "t"), c("Ready. What do you need?", "t"), c("All well. Ask away.", "t"),
        c("I am well, thank you. How may I assist with your notes?", "f"), c("Quite well, thank you. What may I find for you?", "f"),
        c("In good order, thank you. What would you like to review?", "f"),
        c("Pages crisp, pencils sharp. What shall we dig up?", "p"), c("Living my best notebook life. What are you after?", "p"),
        c("Never better, and the shelves are tidy. What next?", "p"),
        c("Doing fine, and more to the point, how are you holding up? We can take your list one item at a time.", "w", "SU"),
        c("Fine, thanks. You sound busy, so let me take something off your plate.", "w", "S"), c("Glad to hear from you too. What are we looking up?", "w", "H"),
    ),
    "social_sorry": (
        c("No need to apologise. What would you like to try?", "w"), c("Not at all. Ask it another way and I will look again.", "w"),
        c("It's completely fine. What can I do for you?", "w"), c("Don't worry about it. Let's try again.", "w"), c("That's okay. What are you looking for?", "w"),
        c("It's fine. Go on.", "t"), c("No harm. Again?", "t"), c("All good.", "t"), c("Fine. What next?", "t"),
        c("There is nothing to apologise for. How may I help?", "f"), c("No apology is necessary. Please continue.", "f"), c("That is quite all right. What would you like next?", "f"),
        c("Pah, no harm done. Where were we?", "p"), c("Forgiven before you finished typing. What next?", "p"), c("Apology accepted, notebook still intact.", "p"),
        c("It really is fine, you are juggling a lot. Take your time.", "w", "S"), c("No worries, a rough moment is allowed. Let's get it sorted.", "w", "U"),
    ),
    "social_laugh": (
        c("Glad something made you smile. Anything else I can find?", "w"), c("Good to hear. Ask whenever you like.", "w"), c("Glad you found that funny. Ready for the next question?", "w"),
        c("Heh. Let me know if you need to search anything else.", "w"), c("Nice to hear a laugh. What next?", "w", "H"),
        c("Ha. What next?", "t"), c("Good. Next?", "t"), c("Heh. Go on.", "t"),
        c("I am pleased that amused you. How may I help next?", "f"), c("Delighted to be of amusement. What would you like next?", "f"),
        c("Ha, I will be here all week. What now?", "p"), c("Tell me I am funny again, then ask me something.", "p"), c("Comedy break over. Back to the pages?", "p"),
    ),
    "social_reaction": (
        c("I know. Anything you want to look up about it?", "w"), c("Fair reaction. Want me to find anything else?", "w"), c("Totally. Let me know what to look up.", "w"),
        c("Quite something. What next?", "w"), c("It does look that way. Shall we check your notes on it?", "w"),
        c("Right. Next?", "t"), c("Noted. Anything to look up?", "t"), c("Yes. More?", "t"),
        c("Indeed. Would you like me to search on it?", "f"), c("Understandably so. What would you like to review?", "f"), c("Quite. Shall I look into your notes on it?", "f"),
        c("Wild, right? Shall I go rummage?", "p"), c("Ha, I felt that too. What shall I dig up?", "p"), c("Big reaction energy. Want me to check the notebook?", "p"),
    ),
    "social_confused": (
        c("Sorry, that was not clear. Ask it another way, or say “tell me more” for the rest of what I found.", "w"),
        c("Let me try again: put it in other words, or name the note you mean.", "w"), c("My answer may have missed. Which part should I look at again?", "w"),
        c("Which bit lost you? I can say it more plainly.", "w"), c("Fair, that was clumsy. Tell me which part and I will redo it.", "w", "U"),
        c("Unclear. Which part?", "t"), c("Say what is unclear and I will redo it.", "t"), c("Which part? I will simplify.", "t"),
        c("I apologise for the confusion. Which part should I clarify?", "f"), c("Allow me to restate that. Which point was unclear?", "f"),
        c("Plot twist: I was confusing. Which bit shall I untangle?", "p"), c("My notes got tangled. Point at the knot and I will unpick it.", "p"),
        c("No stress, we will go slowly. Which part should I make plainer?", "w", "S"),
    ),
    "social_ack": (
        c("Good. Anything else?", "w"), c("All right. What next?", "w"), c("Noted. Ask whenever you like.", "w"), c("Okay. I am here when you need me.", "w"),
        c("Understood. Just say what you want to look up.", "w"), c("Glad that worked. What else?", "w", "H"),
        c("Okay.", "t"), c("Noted.", "t"), c("Next?", "t"), c("Ready when you are.", "t"),
        c("Understood. Please let me know what else you need.", "f"), c("Very good. I remain at your disposal.", "f"), c("Noted. How may I help next?", "f"),
        c("Roger that. Notebook stays open.", "p"), c("Cool cool. What are we hunting next?", "p"), c("Filed under done. What now?", "p"),
        c("Okay, one thing down. What is next on your list?", "w", "S"),
    ),
    "social_compliment": (
        c("I am glad to hear that. What can I find for you next?", "w"), c("That's kind of you. What else should we search for?", "w"),
        c("Much appreciated. Anything else in your notes to find?", "w"), c("Thank you, that means a lot. What next?", "w", "H"),
        c("Thanks. Next?", "t"), c("Appreciated. More?", "t"), c("Good to hear. Go on.", "t"),
        c("Thank you, that is kind. How may I assist further?", "f"), c("I appreciate that. What would you like to review next?", "f"),
        c("Stop, you will make the pages blush. What next?", "p"), c("Aw, shucks. Back to the notebook?", "p"), c("I will take that and frame it. What are we after?", "p"),
    ),
    # ---- tool confirmations (needle slots, the composer's prose) ----
    "act_done": (
        c("Done: {what}.", "wt"), c("Done. {what}.", "w"), c("I have {what}.", "w"), c("All set, {what}.", "w"),
        c("{what}. Done.", "t"), c("Done: {what}.", "t"),
        c("It is done: {what}.", "f"), c("I have completed this: {what}.", "f"),
        c("Consider it done: {what}.", "p"), c("Handled. {what}.", "p"),
    ),
    #: A card's own label said back ("remind you on Friday at 9: call the dentist").
    #: The line after an answer that points at the next step (`composer_tone.closing`).
    "close_next": (
        c("I can see you've been working on “{t}”. Ask me what is left on it, or when it is due.", "w"),
        c("Your latest note is “{t}”. Want a summary of it, or what is left to do?", "w"),
        c("Since you've been in “{t}” lately, I can list what is still open there.", "w"),
        c("Next, I can open “{t}” or pull out its dates.", "w"),
        c("If it helps, ask me who is involved in “{t}”, your newest note.", "w"),
        c("Most recently you wrote “{t}”. Say the word and I will go through it with you.", "w"),
        c("Next: “{t}”, your newest note. Summary, dates or what is left?", "t"), c("Latest note: “{t}”. Ask for what is open on it.", "t"),
        c("“{t}” is your newest. Dates or tasks?", "t"), c("Want “{t}” opened?", "t"),
        c("Your most recent note is “{t}”. I can summarise it, list its dates or show what remains open.", "f"),
        c("Should you wish to continue with “{t}”, your newest note, I can list what is outstanding.", "f"),
        c("The latest entry is “{t}”; I can retrieve its dates or its open items.", "f"),
        c("“{t}” is where you left off. Shall I dig out its open items or dates?", "p"), c("Fresh off your keyboard: “{t}”. Want the dates or what is left?", "p"),
        c("Your newest page, “{t}”, is still warm. Ask what is left on it.", "p"),
    ),
    #: The same next step for a note the answer cited that is not the newest
    #: one: no "latest" or "newest" (INBOX 1357, class K: "Your latest note is
    #: Hello" under a gym answer, Hello being the oldest note).
    "close_cited": (
        c("Want me to open “{t}”, or pull out its dates?", "w"), c("Next, I can open “{t}” or pull out its dates.", "w"),
        c("If it helps, ask me what is still open in “{t}”.", "w"), c("Say the word and I will go through “{t}” with you.", "w"),
        c("I can summarise “{t}” or list what is left in it.", "w"),
        c("Open “{t}”? Dates or tasks?", "t"), c("“{t}”: summary, dates or what is left?", "t"),
        c("I can retrieve the dates or the open items in “{t}”.", "f"), c("Should you wish, I can summarise “{t}”.", "f"),
        c("Fancy a closer look at “{t}”? I can dig out its dates.", "p"), c("“{t}” has more in it. Want the open items?", "p"),
    ),
    "act_card": (
        c("Done: {what}.", "t"), c("Set: {what}.", "t"), c("{what}. Done.", "t"),
        c("All set, I will {what}.", "w"), c("Done. I will {what}.", "w"), c("Sure, I will {what}.", "w"), c("Got it, I will {what}.", "w"),
        c("Understood. I shall {what}.", "f"), c("Done: I will {what}.", "f"), c("Noted, and I will {what}.", "f"),
        c("Consider it handled: I will {what}.", "p"), c("Sorted, I will {what}.", "p"), c("Locked in, I will {what}.", "p"),
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


def _heads(**by_voice: str) -> tuple[Cand, ...]:
    """`w="A|B", t="C"` as candidates tagged for that voice."""
    return tuple(c(text, v) for v, joined in by_voice.items() for text in joined.split("|"))


#: Small talk is built as a head and a tail (a pair is a sentence somebody
#: would say), over the whole sentences in FRAMES: a kind holds the frames
#: and every head with every tail of its voice. A kind with no tails of its
#: own uses "*".
SOCIAL_HEADS: dict[str, tuple[Cand, ...]] = {
    "how": _heads(w="All good here.|Doing well, thanks.|Fine, thank you.|Steady and ready.|Glad you asked.", t="Fine.|Good.|Ready.|All well.",
                  f="I am well, thank you.|Quite well, thank you.|In good order, thank you.|Very well.", p="Pages crisp, pencils sharp.|Living my best notebook life.|Never better.|Shelves tidy, ink full."),
    "sorry": _heads(w="No need to apologise.|Not at all.|It's completely fine.|Don't worry about it.|That's okay.", t="Fine.|No harm.|All good.|Forget it.",
                    f="There is nothing to apologise for.|No apology is necessary.|That is quite all right.|Please think nothing of it.",
                    p="Forgiven before you finished typing.|Pah, no harm done.|Apology accepted.|Already forgotten."),
    "laugh": _heads(w="Glad something made you smile.|Good to hear.|Glad you found that funny.|Heh.|Nice to hear a laugh.", t="Ha.|Heh.|Good.|Funny.",
                    f="I am pleased that amused you.|Delighted to be of amusement.|Most agreeable.|Quite so.", p="Ha, I will be here all week.|Comedy break over.|Tell me I am funny again.|Ba dum tss."),
    "reaction": _heads(w="I know.|Fair reaction.|Totally.|Quite something.|It does look that way.", t="Right.|Noted.|Yes.|Same.",
                       f="Indeed.|Understandably so.|Quite.|One can see why.", p="Wild, right?|Ha, I felt that too.|Big reaction energy.|I gasped too, silently."),
    "confused": _heads(w="Sorry, that was not clear.|Fair, that was clumsy.|My answer may have missed.|Let me try again.", t="Unclear.|Missed.|Again.|My miss.",
                       f="I apologise for the confusion.|Allow me to restate that.|That was imprecise of me.|Forgive the muddle.", p="Plot twist: I was confusing.|My notes got tangled.|That came out as soup.|Well, that went sideways."),
    "ack": _heads(w="Good.|All right.|Noted.|Okay.|Understood.", t="Okay.|Noted.|Right.|Fine.", f="Understood.|Very good.|Noted with thanks.|Certainly.", p="Roger that.|Cool cool.|Filed under done.|Consider it logged."),
    "compliment": _heads(w="I am glad to hear that.|That's kind of you.|Much appreciated.|Thank you.|That means a lot.", t="Thanks.|Appreciated.|Good to hear.|Noted, thanks.",
                         f="Thank you, that is kind.|I appreciate that.|Most kind of you.|Thank you very much.", p="Stop, you will make the pages blush.|Aw, shucks.|I will take that and frame it.|Careful, it will go to my head."),
}
SOCIAL_TAILS: dict[str, tuple[Cand, ...]] = {
    "*": (*_heads(w="What can I find for you?|Anything you want to look up?|Tell me what you need from your notes.|Ask whenever you like.|Your notes are ready when you are.|What shall we look at?",
                  t="Next?|What do you need?|Ask away.|Go on.|More?", f="How may I assist with your notes?|What would you like to review?|Please say what you need.|I remain at your disposal.",
                  p="What are we digging up?|Where shall the notebook take us?|Point me at a page.|What is the hunt?"),
          c("We can take it one thing at a time.", "w", "SU"), c("Tell me what is most pressing and we will start there.", "w", "S"), c("What can I take off your plate?", "w", "S"),
          c("One item first.", "t", "S"), c("Take it in order, and I will keep pace.", "f", "S")),
    "confused": _heads(w="Which part should I look at again?|Ask it another way and I will redo it.|Name the note you mean and I will start there.|Tell me which bit lost you.",
                       t="Which part?|Say it another way.|Name the note.|Try again.", f="Which point should I clarify?|Please rephrase and I will try again.|Please name the note you mean.|Which part was unclear?",
                       p="Point at the knot and I will unpick it.|Which bit shall I untangle?|Say it another way and I will have another go.|Name the page and I will start there."),
}


#: The rest of small talk, and the no-answer, in the same shape (composer8,
#: CHAT_PLAN 1353): each kind is a head and a tail per voice, so a joke, a
#: test, a who-are-you or a nothing-found reads as the chat's persona says it.
#: Identity kinds name Atlas's assistant (CHAT_PLAN decision 36).
SOCIAL_HEADS.update({
    "insult": _heads(w="Sorry about that.|My apologies.|Fair enough.|Point taken.|I'm sorry that missed.", t="Sorry.|My bad.|Fair.|Point taken.",
                     f="My apologies.|I regret the poor result.|Point taken.|I am sorry that was not helpful.", p="Ouch, fair.|Fair hit.|I deserved that one.|The notebook hangs its head."),
    "emotion": _heads(w="I'm sorry to hear that.|That sounds hard.|I hear you.|I understand.|That's totally fair.", t="Sorry to hear it.|Hard.|Understood.|I hear you.",
                      f="I am sorry to hear that.|That sounds difficult.|I understand.|Thank you for telling me.", p="Ugh, that sounds rough.|Big sigh, I hear you.|That is a lot for one day.|Noted, with sympathy."),
    "who": _heads(w="I'm Atlas's assistant.|This is Atlas's assistant speaking.|Atlas's assistant, at your service.|I'm the assistant that works for Atlas.", t="Atlas's assistant.|Atlas's assistant here.|The notebook's assistant, for Atlas.|Assistant to Atlas.",
                  f="I am Atlas's assistant.|This is Atlas's assistant.|I am the assistant to Atlas.|Atlas's assistant, at your service.", p="Atlas's assistant, reporting for duty.|Atlas's assistant, notebook division.|Assistant to Atlas, keeper of your pages.|Atlas's assistant, ink on my fingers."),
    "about_app": _heads(w="I'm Atlas's assistant.|Atlas's assistant here.|Short version: I'm Atlas's assistant.|I'm Atlas's assistant, and I read your notes for you.", t="Atlas's assistant.|Atlas's assistant here.|Short version: Atlas's assistant.|Atlas's assistant, notes only.",
                        f="I am Atlas's assistant.|This is Atlas's assistant.|In brief, I am Atlas's assistant.|Atlas's assistant is at your disposal.", p="Atlas's assistant, reporting for duty.|Atlas's assistant, notebook division.|I'm Atlas's assistant, keeper of your pages.|Atlas's assistant, ink on my fingers."),
    "joke": _heads(w="I have no jokes of my own.|Jokes are not something I make up.|Comedy isn't my strength.|I'm a better finder than a comedian.", t="No jokes.|Not a comedian.|Sorry, none.|Not funny, me.",
                   f="I am not a comedian, I am afraid.|Humour is not my strength.|I do not keep jokes.|Regrettably, no.", p="Alas, my act is empty.|My stand-up career ends here.|The comedy shelf is bare.|I do notes, not punchlines."),
    "unclear": _heads(w="I couldn't make that out.|That didn't come through as words.|Looks like the keyboard got there first.|I didn't catch that.|Hmm, that looks like a few stray keys.", t="Unclear.|Stray keys?|Not words.|Missed that.",
                      f="That message was not clear.|That appears to be a few stray keys.|I could not read that.|The message was not recognised.", p="The keys have spoken, in no language.|That looks like a cat walked the keyboard.|Gibberish detected.|My decoder gave up."),
    "test": _heads(w="Test received.|Loud and clear.|Got your test.|Test noted.|I'm here and this works.", t="Received.|Working.|Test ok.|Loud and clear.",
                   f="Test received.|The test was received.|Test acknowledged.|The notebook is responding.", p="Testing, testing, and it works.|Mic check passed.|Beep boop, received.|The notebook heard you."),
    "nothing": _heads(w="I couldn't find that in your notes.|Nothing I found answers that.|No luck in your notes for that one.|That doesn't seem to be in the notes I found.|I looked, but nothing answers that.",
                      t="Nothing found.|No match.|Not in your notes.|Found nothing.", f="No entry found answers that.|The notes found do not address that.|No matching entry was found.|That does not appear in the notes found.",
                      p="The notebook came up empty.|I turned every page and found nothing.|Not a trace in the notebook.|The shelves are bare on that one."),
})
SOCIAL_TAILS.update({
    "insult": _heads(w="Tell me what you were after, in any words.|Could you try asking another way?|Name the note and I will start there.|Let me have another go.", t="Again?|Say it another way.|What did you need?|Try me again.",
                     f="Please describe what you need and I will try again.|Shall we try another approach?|Please rephrase and I shall retry.|What would be most useful?", p="Give me another swing.|Say it differently and I will try harder.|Point at the page you wanted.|Round two?"),
    "emotion": (*_heads(w="Take whatever time you need.|I can list today's plans, or you could jot down what's on your mind.|I'm here when you want to look something up.|Tell me what would help.", t="Here when needed.|Plans for today?|Note it down?|Say what helps.",
                        f="Take whatever time you need.|I can list today's plans, or you may note down what is on your mind.|I am available whenever you are ready.|Please say what would be useful.",
                        p="I will keep the notebook warm.|Shall we do one small thing from your list?|Jot it down and I will hold the page.|Say the word and I will fetch today's plans."),
                c("We can take it one thing at a time.", "w", "SU"), c("Tell me what is most pressing and we will start there.", "w", "S")),
    "who": _heads(w="With no model running I answer from your notes in their own words.|I find things in your notes and say what they say.|Connect a model and you can talk to Atlas itself.|Ask me when something is, or what you decided.",
                  t="I answer from your notes.|Notes only, no model.|Ask away.|Connect a model for Atlas itself.", f="Without a model running, I answer from your notes in their own words.|I locate entries in your notes and report what they say.|To speak with Atlas itself, a model must be connected.|Questions about dates, decisions and lists are welcome.",
                  p="I read your notes so you do not have to.|No model running, just me and your pages.|Connect a model if you want Atlas itself.|Ask me about anything you wrote down."),
    "about_app": _heads(w="I answer from your notes: when something is, who said what, what the latest is on a project.|I also set reminders, tag, pin and move notes.|Try “what did I do last week” or “remind me to call the dentist on Friday”.|Connecting a model adds writing and tools.",
                        t="Answers from your notes.|Reminders, tags, pins, moves.|Dates, lists, decisions.|A model adds writing.", f="Answers come from your notes: dates, decisions and the status of a project.|Reminders, tags, pins and moves are done on request.|Connecting a model adds writing and tools.|Try “what is on today” to begin.",
                        p="I turn your notes into answers: dates, lists, decisions.|Reminders, tags, pins and moves are small jobs I enjoy.|Try “what did I do last week”.|Connect a model and I get a writing partner."),
    "joke": _heads(w="If you saved one, ask me for it.|If one of your notes has a good one, I can find it.|Want me to search your notes for a joke?|Finding your notes is what I do.", t="Search your notes for one?|I only report notes.|Saved one? Ask.|Ask about a note.",
                   f="A joke recorded in your notes can be found on request.|I report what your notes contain.|Shall I search your notes for one?|Locating your notes is what I do.", p="Saved a good one? I will fetch it.|Shall I rummage your notes for a joke?|Your notes may be funnier than I am.|Ask for a note instead."),
    "unclear": _heads(w="Try a word or two about what you need.|Ask about a note, a date or a list.|What did you mean to ask?|You could start with “what's on today”.", t="Try again.|A word or two?|Ask about a note.|What do you need?",
                      f="Please try again in a few words.|What would you like to find?|Please ask about a note, a date or a reminder.|You could begin with “what is on today”.", p="Say it again with words.|What did you mean to ask?|Ask about a note and I will cheer up.|Try “what's on today”."),
    "test": _heads(w="Ask me something real whenever you like.|Try “what's on today” or “remind me to call the dentist on Friday”.|Everything runs on this computer, and I can answer from your notes right now.|Say “what can you do” for the short tour.",
                   t="Ask something.|Next?|Notes ready.|Try “what's on today”.", f="Ask about a note, a date or a reminder to continue.|Please state what to find.|Answers are drawn from your notes, with the source shown.|Say “what can you do” for a summary of the available functions.",
                   p="Ask me something real.|Try “what's on today”.|Say “what can you do” for the tour.|What shall we dig up?"),
    "nothing": (*_heads(w="Could you put it another way?|Is there a word you might have used in the note?|Do you remember roughly when you wrote it?|Which note might it be in?|Want to try a different word?",
                        t="Another word?|Which note?|When did you write it?|Rephrase?", f="Could you rephrase the question?|Which entry might contain it?|Do you recall approximately when it was recorded?|Would a different wording help?",
                        p="Try another word and I will look again.|Do you remember roughly when you wrote it?|Which note might be hiding it?|Could it be under another name?"),
                c("No harm, we will find it. Which note might it be in?", "w", "SU")),
})
for _kind in ("insult", "emotion", "who", "about_app", "joke", "unclear", "test", "nothing"):
    FRAMES[f"social_{_kind}"] = ()

#: The words that lead a no-answer naming what no note holds ("None of your
#: notes mention <word>."), per voice; a tail from SOCIAL_TAILS["nothing"] follows.
NONE_FOUND_LEADS: tuple[Cand, ...] = _heads(
    w="None of your notes mention |I couldn't find anything on |Your notes don't mention |There's nothing in your notes about |I found no mention of ",
    t="Nothing on |No mention of |No note has |Found no mention of ", f="No note found mentions |No entry refers to |The notes contain no mention of |No record mentions ",
    p="The notebook has nothing on |Not a word in the notes about |Every page turned, no sign of |Zero pages mention ",
)

#: Whole sentences beside the head and tail pairs, so the shapes vary: one
#: short line, one long, openers unlike the pairs' (reply_variety measures it).
FRAMES["social_who"] = (
    c("Your notebook's helper, Atlas's assistant. Atlas is the model you connect.", "w"), c("Here to help as Atlas's assistant: I live in this notebook and know what's in it.", "w"),
    c("Reading your notes so you don't have to is my job, as Atlas's assistant.", "w"), c("Assistant here; Atlas is the model. Connect one in Settings, Models to talk to Atlas.", "w"),
    c("Assistant to Atlas. Notes only.", "t"), c("Your notebook's helper, for Atlas.", "t"), c("Atlas's assistant, and nothing more.", "t"),
    c("The assistant to Atlas, answering from your notes.", "f"), c("To speak with Atlas itself, a model must be connected; I am its assistant.", "f"),
    c("Running on this computer, I am Atlas's assistant and know only what you have recorded.", "f"),
    c("Notebook sidekick to Atlas, at your service.", "p"), c("Your pages are read by Atlas's assistant, which is me, and nobody else.", "p"),
)
FRAMES["social_about_app"] = (
    c("Plenty. I'm Atlas's assistant: I answer questions from your notes, set reminders, and tag, pin or move notes for you.", "w"),
    c("Ask me, Atlas's assistant, what's on today, what you decided about something, or where a setting lives.", "w"),
    c("Think of me as a search that answers, from Atlas's assistant: dates, lists, decisions and how things are going.", "w"),
    c("Mostly, Atlas's assistant reads your notes for you. Try “what did I do last week”.", "w"),
    c("Plenty: answers, reminders, tags, pins. Atlas's assistant.", "t"), c("Ask about dates, lists, decisions. Atlas's assistant answers.", "t"),
    c("In brief: Atlas's assistant searches your notes and answers from them.", "f"),
    c("Ask Atlas's assistant what is on today, what was decided about a matter, or where a setting is located.", "f"),
    c("Short version: a tidy brain for your notebook, courtesy of Atlas's assistant.", "p"), c("Atlas's assistant reads, files and reminds; you just ask.", "p"),
)
FRAMES["social_emotion"] = (
    c("That sounds hard.", "w"), c("Sorry you're feeling that way. If it helps, I can pull up today's plans, or you could jot down what's on your mind.", "w"),
    c("Hard. Here when needed.", "t"), c("I understand.", "f"), c("That sounds difficult. I can list today's plans, or you could note down what is on your mind.", "f"),
    c("Ugh. I will keep the notebook warm.", "p"),
)
FRAMES["social_insult"] = (
    c("Fair. I can do better.", "w"), c("Point taken. Tell me what you were after, in any words, and I'll have another go.", "w"),
    c("Fair. Again?", "t"), c("Sorry, that one's on me.", "t"),
    c("My apologies. Please describe what you need and I will try again.", "f"), c("Understood. I will try to do better.", "f"),
    c("Ouch. Give me another swing and I will do better.", "p"), c("Fair hit.", "p"),
)
FRAMES["social_joke"] = (
    c("Comedy isn't my strength. Finding your notes is.", "w"), c("I'm a better finder than a comedian. Saved any good ones?", "w"),
    c("No jokes. Search your notes for one?", "t"), c("Not funny, me. Notes only.", "t"),
    c("Humour is not my strength. Locating your notes is.", "f"), c("I do not keep jokes. Shall I search your notes for one?", "f"),
    c("My stand-up career ends here. Your notes may be funnier.", "p"), c("The comedy shelf is bare, but your notes might not be.", "p"),
)
FRAMES["social_unclear"] = (
    c("Not sure what that was. Ask me about a note, a date or a reminder.", "w"), c("Hmm, that looks like a stray key or two.", "w"),
    c("Not words. Try again?", "t"), c("Missed that.", "t"),
    c("The message was not recognised. You could begin with “what is on today”.", "f"), c("I did not understand that. Please ask about a note, a date or a reminder.", "f"),
    c("My decoder gave up. Say it again with words.", "p"), c("Gibberish detected.", "p"),
)
FRAMES["social_test"] = (
    c("Loud and clear. Try “what's on today” or “remind me to call the dentist on Friday”.", "w"), c("All good on my end. What would you like to find?", "w"),
    c("Received. Notes ready.", "t"), c("Working.", "t"),
    c("All systems are working. What should be located?", "f"), c("Working as expected. Please state what to find.", "f"),
    c("Mic check passed. Ask me something real.", "p"), c("Testing, testing, and it works.", "p"),
)
FRAMES["social_nothing"] = (
    c("Your notes don't seem to cover that. Did you mean something else?", "w"), c("Nothing found.", "t"),
    c("Nothing found answers the question. Would a different wording help?", "f"), c("The notebook came up empty. Try another word?", "p"),
)
FRAMES["social_emotion"] += (
    c("I hear you.", "w", "SU"), c("That sounds like a lot. What would help most right now?", "w", "SU"),
    c("Sorry to hear that, truly. Take whatever time you need. I'm here when you're ready to look something up.", "w", "SU"),
    c("That is hard to carry. We can take it one thing at a time.", "w", "SU"),
    c("I hear you.", "w"), c("That sounds like a lot. What would help most right now?", "w"),
    c("Sorry to hear that, truly. Take whatever time you need. I'm here when you're ready to look something up.", "w"),
)
#: The line after an empty window that names the next dated item (composer8;
#: it was the plain "Next up:" in every voice).
FRAMES["next_due"] = (
    c("Next up: {what} ({when}).", "w"), c("After that comes {what} ({when}).", "w"), c("The next one is {what} ({when}).", "w"), c("Coming up after that: {what} ({when}).", "w"),
    c("Next: {what} ({when}).", "t"), c("Then: {what} ({when}).", "t"), c("After: {what} ({when}).", "t"),
    c("The next dated item is {what} ({when}).", "f"), c("Thereafter: {what} ({when}).", "f"), c("The following entry is {what} ({when}).", "f"), c("Next in the notes is {what} ({when}).", "f"),
    c("Next on the horizon: {what} ({when}).", "p"), c("Further out: {what} ({when}).", "p"), c("Peeking ahead: {what} ({when}).", "p"), c("Spotted on the horizon: {what} ({when}).", "p"),
)
