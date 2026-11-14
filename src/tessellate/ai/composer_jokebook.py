"""C10 (CHAT_PLAN): when no note of the person's is a joke, "tell me a joke"
gets one from this table of short, clean jokes, always labelled as the app's
own so it is never mistaken for a note. The Plain answer style opts out."""

from __future__ import annotations

import hashlib

JOKES: tuple[str, ...] = (
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I told my computer I needed a break. It said it would go to sleep.",
    "Why don't skeletons fight each other? They don't have the guts.",
    "What do you call a fake noodle? An impasta.",
    "Why did the bicycle fall over? It was two tired.",
    "What do you call cheese that is not yours? Nacho cheese.",
    "Why can't you give Elsa a balloon? She will let it go.",
    "I used to hate facial hair, but then it grew on me.",
    "What did the ocean say to the beach? Nothing, it just waved.",
    "Why did the math book look sad? It had too many problems.",
    "What do you call a bear with no teeth? A gummy bear.",
    "Why did the coffee file a police report? It got mugged.",
    "How does a penguin build its house? Igloos it together.",
    "Why do bees have sticky hair? They use honeycombs.",
    "What did one wall say to the other? I will meet you at the corner.",
    "Why was the broom late? It over swept.",
    "What do you call a sleeping bull? A bulldozer.",
    "Why did the tomato turn red? It saw the salad dressing.",
    "What is a tree's favourite drink? Root beer.",
    "Why did the golfer bring two pairs of trousers? In case he got a hole in one.",
    "What do you call a boomerang that does not come back? A stick.",
    "Why do cows wear bells? Because their horns do not work.",
    "I would tell you a chemistry joke, but I know I would not get a reaction.",
    "What did the zero say to the eight? Nice belt.",
    "Why did the picture go to jail? It was framed.",
    "What do you call a dinosaur with an extensive vocabulary? A thesaurus.",
    "Why did the cookie go to the doctor? It felt crummy.",
    "What do you call a pile of kittens? A meowtain.",
    "Why can't a nose be twelve inches long? Then it would be a foot.",
    "What did the left eye say to the right eye? Between us, something smells.",
    "Why did the student eat his homework? The teacher said it was a piece of cake.",
    "What do you call a factory that makes okay products? A satisfactory.",
    "Why do fish live in salt water? Pepper makes them sneeze.",
    "What did the grape do when it got stepped on? It let out a little wine.",
    "Why was the belt arrested? It held up a pair of trousers.",
    "How do you organise a space party? You planet.",
    "What do you call a snowman in July? A puddle.",
    "Why did the clock get sent to the principal? It tocked too much.",
    "What is orange and sounds like a parrot? A carrot.",
    "Why did the orange stop? It ran out of juice.",
    "What do you call two birds in love? Tweethearts.",
    "Why did the invisible man turn down the job? He could not see himself doing it.",
    "What did the janitor say when he jumped out of the closet? Supplies.",
    "Why are ghosts bad liars? You can see right through them.",
    "What do you call a lazy kangaroo? A pouch potato.",
    "Why did the stadium get hot? All the fans left.",
    "What do you call an elephant that does not matter? Irrelephant.",
    "Why did the sun not go to university? It already had a million degrees.",
    "What kind of shoes do spies wear? Sneakers.",
    "Why did the pencil go to bed early? It was drawing a blank.",
    "What do you call a fish wearing a bowtie? Sofishticated.",
    "Why did the man put his money in the freezer? He wanted cold hard cash.",
    "What did the big flower say to the little flower? Hi, bud.",
    "Why do seagulls fly over the sea? If they flew over the bay, they would be bagels.",
    "What did the buffalo say to his son? Bison.",
    "Why was the computer cold? It left its Windows open.",
    "What do you call a sad strawberry? A blueberry.",
    "How do you make a tissue dance? Put a little boogie in it.",
    "Why did the teddy bear say no to dessert? She was already stuffed.",
    "What do you call a bee that cannot make up its mind? A maybe.",
    "Why did the chicken join a band? It had the drumsticks.",
    "What did the pirate say on his eightieth birthday? Aye matey.",
    "Why do birds fly south? It is too far to walk.",
    "What do you call a hippo in a lift? Stuck.",
    "Why did the dentist become a baker? He liked to make fillings.",
    "What do you call a pig that does karate? A pork chop.",
    "Why did the toilet paper roll down the hill? To get to the bottom.",
    "What did the pen say to the pencil? You are looking sharp.",
    "Why did the calendar feel nervous? Its days were numbered.",
    "How do you catch a squirrel? Climb a tree and act like a nut.",
    "What is a witch's favourite subject at school? Spelling.",
    "What do you call a train carrying bubblegum? A chew chew train.",
    "Why did the paper go to school? To get a little sharper.",
    "What do you call an alligator in a vest? An investigator.",
    "Why did the lightbulb fail its exam? It was not very bright.",
    "What do you call a cow with two legs? Lean beef.",
    "Why do ducks make good detectives? They always quack the case.",
    "What did the sock say to the shoe? Let us stick together.",
    "Why did the spider get a computer? To make a website.",
    "What do you call a monkey in a minefield? A baboom.",
    "Why was the music teacher locked out? Her keys were inside.",
    "How do trees get online? They log in.",
    "What do you call a bagel that can fly? A plane bagel.",
    "Why did the librarian slip? She was in the non-friction section.",
    "What do you call a sheep with no legs? A cloud.",
    "Why did the astronaut break up with the Moon? He needed space.",
    "What did the traffic light say to the car? Do not look, I am changing.",
    "Why did the bread go to therapy? It felt crumby.",
    "What is a cat's favourite colour? Purrple.",
    "Why was the cell phone wearing glasses? It lost its contacts.",
    "What do you call a magician who lost his magic? Ian.",
    "Why did the rabbit get a job? It wanted some lettuce.",
    "How do you fix a broken pumpkin? With a pumpkin patch.",
    "What do you call a fly without wings? A walk.",
    "Why do mathematicians like parks? Plenty of natural logs.",
    "What did the cloud wear under his raincoat? Thunderwear.",
    "Why did the tree go to the dentist? It needed a root canal.",
    "What do you call a note you never finished? A work in progress.",
    "Why did the notebook feel calm? Everything was in its place.",
    "What did the tag say to the note? I have got you covered.",
)


def pick(seed: str, recent: tuple[str, ...] | list[str] = ()) -> str:
    """One joke, the same for the same seed, never one in `recent`."""
    start = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(JOKES)
    for step in range(len(JOKES)):
        joke = JOKES[(start + step) % len(JOKES)]
        if joke not in recent:
            return joke
    return JOKES[start]


def said(seed: str, recent: tuple[str, ...] | list[str] = ()) -> str:
    """The reply: the joke, labelled as the app's own."""
    return f"Not from your notes, one of mine: {pick(seed, recent)}"
