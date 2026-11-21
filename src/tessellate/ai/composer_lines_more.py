"""More wording for the abilities that had fewer than 20 distinct surfaces (L-chat-229): `(text, voices,
emotions)` rows, turned into candidates by `composer_lines` (this file imports nothing, so the two never
loop). Same rules as there: terse is fragments, formal full sentences, warm adds company, playful an image;
sentence case, no exclamation marks, no em-dashes."""

from __future__ import annotations

MORE: dict[str, tuple[tuple[str, str, str], ...]] = {
    "hello": (
        ("Good {tod}. What shall we look at?", "w", ""), ("Good {tod}, good to have you here.", "w", ""), ("Good {tod}. I am all ears.", "w", ""),
        ("Good {tod}. Notes ready.", "t", ""), ("Hi. Good {tod}.", "t", ""), ("Morning, or whatever it is. Good {tod}.", "t", ""),
        ("Good {tod}. I hope the day treats you well.", "f", ""), ("Good {tod}. How may I be of use?", "f", ""),
        ("Good {tod}, and the kettle is metaphorically on.", "p", ""), ("Good {tod}. The notebook has been practising its welcome.", "p", ""),
        ("Good {tod}. Take your time settling in.", "w", "S"), ("Good {tod}. Let us make this easy.", "w", "SU"),
    ),
    "welcome_new": (
        ("Welcome. This notebook is new, and what you write stays on this machine.", "w", ""), ("Welcome. Nothing here yet, so add a note and ask me about it later.", "w", ""),
        ("Welcome. No notes yet, so start anywhere, a line is enough.", "w", ""), ("This notebook is new, so there is plenty of room.", "w", ""),
        ("Empty. Add a note.", "t", ""), ("Nothing yet. Write one line.", "t", ""),
        ("No notes. Start now.", "t", ""),
        ("Welcome. The notebook holds no entries; the first will begin its record.", "f", ""), ("Welcome. Please add a first note whenever you are ready.", "f", ""),
        ("Welcome. A notebook with no notes yet, and every page ahead of us.", "p", ""), ("Fresh binding, blank pages. Write the first line.", "p", ""),
    ),
    "w_due": (
        ("{due} are due today.", "w", ""), ("There are {due} due today.", "w", ""), ("{due} due today, so you know.", "w", ""), ("Heads up, {due} due today.", "w", ""),
        ("{due}, today.", "t", ""), ("Today: {due}.", "t", ""), ("Due: {due}.", "t", ""),
        ("There are {due} falling due today.", "f", ""), ("Today you have {due} to attend to.", "f", ""), ("{due} require attention today.", "f", ""),
        ("Today's page lists {due}.", "p", ""), ("{due} have their eye on today.", "p", ""),
    ),
    "w_last": (
        ("The last thing you wrote was {last}.", "w", ""), ("You wrote {last} most recently.", "w", ""), ("Latest note on the shelf: {last}.", "w", ""), ("Your newest note is {last}.", "w", ""),
        ("Last: {last}.", "t", ""), ("Newest: {last}.", "t", ""), ("Last written: {last}.", "t", ""),
        ("Your most recent note is {last}.", "f", ""), ("The note most recently written is {last}.", "f", ""), ("The latest addition is {last}.", "f", ""),
        ("The newest page in the notebook is {last}.", "p", ""), ("Fresh ink: {last}.", "p", ""),
    ),
    "w_streak": (
        ("Your writing streak is at {streak} running.", "w", ""), ("Notes on {streak} running now.", "w", ""), ("Notes on {streak} running, keep it up.", "w", ""), ("{streak} running so far.", "w", ""),
        ("Run: {streak}.", "t", ""), ("{streak} and counting.", "t", ""), ("Written {streak} running.", "t", ""),
        ("You have written notes on {streak} in succession.", "f", ""), ("Your streak currently stands at {streak}.", "f", ""), ("A streak of {streak} is on record.", "f", ""),
        ("{streak} without a gap, the notebook is impressed.", "p", ""), ("The pen has not rested for {streak}.", "p", ""),
    ),
    "w_quiet": (
        ("Nothing is due today.", "t", ""), ("No reminders are set for today.", "w", ""), ("There is nothing due today, which is a good sign.", "w", ""), ("No reminders fall today.", "w", ""),
        ("Clear today.", "t", ""), ("Nothing due.", "t", ""), ("No reminders.", "t", ""),
        ("No reminder is due today.", "f", ""), ("There are no reminders falling due today.", "f", ""), ("Today's schedule holds no reminders.", "f", ""),
        ("Today's page is blank of deadlines.", "p", ""), ("No reminders today, and that is allowed.", "w", ""), ("No due dates today.", "t", ""), ("Nothing is scheduled for today.", "f", ""), ("Not a single reminder is due today, so enjoy it.", "p", ""),
    ),
    "quiz_right": (
        ("Yes, you have it.", "w", ""), ("That is the one.", "w", ""), ("You got it.", "w", ""), ("Right on.", "w", ""),
        ("Correct.", "t", "R"), ("Yep.", "t", ""), ("Got it.", "t", ""),
        ("That is the correct answer.", "f", ""), ("Your answer is correct.", "f", ""),
        ("Bullseye.", "p", ""), ("Ding, that is right.", "p", ""), ("Right again, the notebook approves.", "p", ""),
    ),
    "quiz_close": (
        ("Close, and I will count it. The note says: {a}", "w", ""), ("Almost, and that is good enough. Your note says: {a}", "w", ""),
        ("Nearly right, credited. The note has: {a}", "w", ""), ("Pretty close, so it counts. The note reads: {a}", "w", ""),
        ("Close. Counted. {a}", "t", ""), ("Near enough. Note: {a}", "t", ""), ("Almost. It says: {a}", "t", ""),
        ("Near enough to be credited. The note reads: {a}", "f", ""), ("Largely correct; I will accept it. The note states: {a}", "f", ""),
        ("Warm enough to count. The note says: {a}", "p", ""), ("A near hit, counted. The note says: {a}", "p", ""),
    ),
    "quiz_wrong": (
        ("Not that one. The note says: {a}", "w", ""), ("Not quite right. Your note has it as: {a}", "w", ""), ("Close, but no. The note says: {a}", "w", ""),
        ("Not right. It says: {a}", "t", ""), ("No. The note: {a}", "t", ""), ("Wrong. It is: {a}", "t", ""),
        ("That answer is not correct. The note says: {a}", "f", ""), ("Unfortunately not. The note gives: {a}", "f", ""),
        ("Off the mark. The note says: {a}", "p", ""), ("Not this round. The note says: {a}", "p", ""), ("A miss, but a useful one. The note says: {a}", "p", ""),
    ),
    "quiz_skip": (
        ("Skipping it. The answer is: {a}", "w", ""), ("That is fine. The answer was: {a}", "w", ""), ("No worries, here it is: {a}", "w", ""), ("Skipped, here is the answer: {a}", "w", ""),
        ("Skipped. It was: {a}", "t", ""), ("Pass. Answer: {a}", "t", ""), ("Next. The answer was: {a}", "t", ""), ("Skip. It is: {a}", "t", ""),
        ("Skipped. The correct answer is: {a}", "f", ""), ("Understood. The answer is as follows: {a}", "f", ""), ("Passed over. The note reads: {a}", "f", ""),
        ("Skipping is allowed. The note says: {a}", "p", ""), ("Dodged it. The answer: {a}", "p", ""), ("A graceful pass. The answer was: {a}", "p", ""), ("Saved for later. The answer: {a}", "p", ""),
    ),
    "social_how": (
        ("Doing well, thanks. How about you?", "w", ""), ("All fine here. What shall we look at?", "w", ""), ("Good, thank you. Shall we pick up where you left off?", "w", ""),
        ("Fine. Next?", "t", ""), ("Good. You?", "t", ""),
        ("Very well, thank you. How can I help today?", "f", ""),
        ("Ticking along nicely. What are you after?", "p", ""),
    ),
    "social_sorry": (
        ("No harm done. What would you like next?", "w", ""), ("It is all right. Shall we carry on?", "w", ""),
        ("Fine. Go on.", "t", ""), ("No problem.", "t", ""),
        ("Please do not mention it. How may I help?", "f", ""),
        ("Nothing to forgive. Where to next?", "p", ""),
    ),
    "social_laugh": (
        ("Good, I am glad. What next?", "w", ""), ("Nice. Anything else on your mind?", "w", ""), ("Happy to hear it. What can I look up?", "w", ""),
        ("Ha. Carry on.", "t", ""), ("Good one. Next?", "t", ""),
        ("Glad that landed. How may I help further?", "f", ""), ("Most pleasing. What would you like next?", "f", ""),
        ("Ha, the notebook chuckles too. What next?", "p", ""), ("Comedy gold, filed under miscellaneous. What now?", "p", ""),
    ),
    "social_reaction": (
        ("I hear you. Want me to look anything up?", "w", ""), ("Understandable. What shall I check in your notes?", "w", ""),
        ("Yes. Go on.", "t", ""), ("Fair.", "t", ""),
        ("That is understandable. How may I assist?", "f", ""), ("Quite so. Shall I search your notes?", "f", ""),
        ("Ha, fair. Where shall we dig?", "p", ""), ("That tracks. Shall I check the notebook?", "p", ""),
    ),
    "social_confused": (
        ("Sorry, let me say that another way.", "w", ""), ("That may have been unclear, so ask me again and I will try.", "w", ""),
        ("Unclear, sorry. Again?", "t", ""), ("My miss. Try me again.", "t", ""),
        ("My apologies. Please rephrase and I will try again.", "f", ""), ("I regret the confusion. Shall I try once more?", "f", ""),
        ("Well, that came out muddled. One more go?", "p", ""), ("My wires crossed there. Ask again?", "p", ""),
    ),
    "social_ack": (
        ("Good. Just say if you need anything.", "w", ""), ("Okay. I am here whenever.", "w", ""),
        ("Fine.", "t", ""), ("Right. Next?", "t", ""),
        ("Very well. Do let me know if there is more.", "f", ""),
        ("Noted and filed. What now?", "p", ""),
    ),
    "social_compliment": (
        ("Thank you, that is lovely to hear.", "w", ""), ("That is kind. What shall we do next?", "w", ""), ("Thanks, that cheers me. What can I find?", "w", ""),
        ("Thanks.", "t", ""), ("Cheers. Next?", "t", ""),
        ("Thank you, I appreciate it. What would you like next?", "f", ""), ("That is generous of you. How may I assist?", "f", ""),
        ("Careful, the notebook will get a big head. What next?", "p", ""), ("Blushing in the margins. What are we after?", "p", ""),
    ),
    "close_next": (
        ("Want me to go through “{t}”, your newest note?", "w", ""), ("Your newest note is “{t}”. Shall I open it?", "w", ""),
        ("“{t}”. Open it?", "t", ""), ("Newest: “{t}”. Dates?", "t", ""),
        ("Shall I summarise “{t}”, your most recent note?", "f", ""), ("Your newest note, “{t}”, can be summarised if you wish.", "f", ""),
        ("“{t}” is hot off the press. Want a look?", "p", ""), ("Want the highlights of “{t}”, your newest page?", "p", ""),
    ),
    "close_cited": (
        ("Want a summary of “{t}”?", "w", ""), ("I can open “{t}” for you.", "w", ""), ("Shall I pull out what is open in “{t}”?", "w", ""), ("Ask me “when is {t} due” if that helps.", "w", ""),
        ("“{t}”: open it?", "t", ""), ("“{t}”. Dates?", "t", ""), ("Tasks in “{t}”?", "t", ""),
        ("I can summarise “{t}” if you wish.", "f", ""), ("Its dates in “{t}” can be listed on request.", "f", ""),
        ("There is more in “{t}”. Shall I dig?", "p", ""), ("“{t}” may be worth a second look.", "p", ""),
    ),
    "act_card": (
        ("Okay, I will {what}.", "w", ""), ("Right, I will {what}.", "w", ""), ("Will do, I will {what}.", "w", ""),
        ("Will {what}.", "t", ""), ("Okay: {what}.", "t", ""),
        ("Certainly. I will {what}.", "f", ""), ("Very well, I will {what}.", "f", ""),
        ("Leave it with me, I will {what}.", "p", ""), ("On it, I will {what}.", "p", ""),
    ),
    "next_due": (
        ("Next up is {what}, on {when}.", "w", ""), ("Your next one is {what}, due {when}.", "w", ""),
        ("Next: {what}, {when}.", "t", ""), ("{what}, {when}.", "t", ""),
        ("The next item is {what}, on {when}.", "f", ""), ("The next reminder falls on {when}: {what}.", "f", ""),
        ("Coming up: {what}, on {when}.", "p", ""), ("{what} is next in line, on {when}.", "p", ""),
    ),
    "act_baddate": (
        ("I could not make a date of “{said}”. Try “Friday at 3pm”.", "w", ""), ("“{said}” is not a date I can read. A day and a time will do.", "w", ""),
        ("I did not catch a date in “{said}”. Try “tomorrow at 9”.", "w", ""), ("Could you give me a day and a time instead of “{said}”?", "w", ""),
        ("Not a date: “{said}”. Try “Friday 3pm”.", "t", ""), ("No date in “{said}”.", "t", ""), ("“{said}”: no date read.", "t", ""),
        ("I could not interpret “{said}” as a date. Please give a day and a time.", "f", ""), ("“{said}” is not a date I can read; for example, “Friday at 3pm” is.", "f", ""),
        ("“{said}” sounds lovely but is not a date. Try “Friday at 3pm”.", "p", ""), ("No calendar knows “{said}”. Try a day and a time.", "p", ""), ("I cannot pin a date on “{said}”. Give me a day and a time.", "p", ""),
    ),
    "act_none": (
        ("I cannot do that without a model. I can search, count, list and set reminders.", "w", ""), ("That needs a model. What I can do offline is search, count, list and remind.", "w", ""),
        ("A model is needed for that. Offline: search, count, list, remind.", "t", ""), ("Not with no model. I can search, count, list and remind.", "t", ""), ("No model, so search, count, list, remind only.", "t", ""),
        ("That request requires a model. Offline I can search, count, list and set reminders.", "f", ""), ("This is beyond what I can do with no model, which is searching, counting, listing and reminders.", "f", ""),
        ("Beyond me without a model. Searching, counting, listing and reminders are not.", "p", ""), ("That takes a model, and I am flying solo. Search, count, list and remind, though.", "p", ""),
        ("Not possible with no model; searching, counting, listing and reminders are.", "t", ""), ("I would need a model for that, so I will stick to searching, counting, listing and reminders.", "f", ""),
        ("I cannot do that here with no model. Searching, counting, listing and reminders I can.", "w", ""), ("A model would be needed. Without one I can search, count, list and set reminders.", "w", ""),
        ("That one needs a model. I can still search, count, list and set reminders.", "", ""), ("Without a model that is out of reach, but searching, counting, listing and reminders are not.", "", ""),
    ),
}
