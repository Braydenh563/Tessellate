"""L-chat-135 (A1): the utilities gate, 60 phrasings at 95%. Each is asked of
the real chat route with a notebook full of notes and no model, and must answer
with the computed number and say how it was read, never from a note. Clock
fixed at Monday 9 November 2026, 12:00. Measured 59 of 60 (98.3%): "days until Friday"
answers from the Python course note due that Friday, which is right but not computed."""

import tests._seed_r9_1109 as sd

#: (question, what the answer must say). "Read as" is checked on every one but the bare sums.
ROWS = [
    ("what is 12 times 12", "144"), ("what's 15% of 80", "12"), ("what is 2 to the power of 10", "1,024"),
    ("square root of 144", "12"), ("average of 3, 8, 10", "7"), ("median of 4, 9, 1, 7", "5.5"),
    ("sum of 4, 5, 6", "15"), ("what is 100 divided by 8", "12.5"), ("what is 15 mod 4", "3"),
    ("what is 9 squared", "81"), ("what is 7 factorial", "5,040"), ("is 17 prime", "prime number"),
    ("is 91 a prime number", "7 times 13"), ("round 3.14159 to 2 places", "3.14"), ("what is 1/3 as a decimal", "0.333333"),
    ("convert 5 km to miles", "3.11"), ("10 miles in km", "16.09"), ("how many ounces in a pound", "16"),
    ("72 fahrenheit in celsius", "22.22"), ("what is 30 celsius in fahrenheit", "86"), ("3 cups in ml", "709.76"),
    ("how many litres in a gallon", "3.79"), ("200 pounds in kg", "90.72"), ("how many seconds in a day", "86,400"),
    ("how many minutes in a week", "10,080"), ("convert 1 GB to MB", "1,000"), ("how many bytes in a kilobyte", "1,000"),
    ("what is 1000 meters in feet", "3,280.8"), ("what is 3 hours in minutes", "180"), ("convert 5 stone to kg", "31.75"),
    ("how many days until 25 December", "46 days"), ("what day is 3 weeks from now", "30 November 2026"),
    ("how many weeks between 1 March and 1 June", "13.1 weeks"), ("what week number is 3 March", "week 10"),
    ("how old is 3 March 1990", "36 years"), ("how many days since 1 January", "312 days"),
    ("what is the date next Tuesday", "17 November 2026"), ("is 2028 a leap year", "leap year"),
    ("what time is it in Western Australia", "20:00"), ("time in Tokyo", "21:00"), ("what time is it in New York", "07:00"),
    ("time in London", "12:00"), ("what is the time in Sydney", "23:00"),
    ("what is 20% tip on 45", "54"), ("tip on 60 at 15%", "69"), ("split 90 between 4", "22.5"),
    ("50 usd in eur", "EUR"), ("100 euros in pounds", "GBP"), ("reading time for 1200 words", "5 min"),
    ("roll a die", "rolled"), ("flip a coin", "Read as one coin toss"), ("pick a number between 1 and 10", "Read as a whole number"),
    ("what is 5% of 200", "10"), ("20% off 80", "64"),
    ("half of 90", "45"), ("double 45", "90"), ("how many hours in a week", "168"), ("convert 100 cm to inches", "39.37"),
    ("what is 18 celsius in fahrenheit", "64.4"), ("how many days until Friday", "4 days"),
]
BARE = {"what is 12 times 12", "what is 100 divided by 8"}


def test_there_are_sixty_phrasings():
    assert len(ROWS) == 60


def test_the_gate_is_ninety_five_percent(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    results = {q: sd.ask(client, q, notes_only=False)["text"] for q, _ in ROWS}
    wrong = [q for q, said in ROWS if said not in results[q] or ("Read as" not in results[q] and q not in BARE and "Read as" not in said)]
    assert len(ROWS) - len(wrong) >= 57, [(q, results[q][:80]) for q in wrong]
