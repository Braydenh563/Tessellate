// avatars.js: the generated faces. `nameMood` reads a name for what the
// face should be (mood, creature, costume, hands, limbs, hair, style) and
// `nameMark` draws it as an SVG; the CSS motion is in 08-consistency.css.
//
// Split out of app.js on 2026-09-24, when the faces themselves took the
// gzipped app.js over tests/test_static_compression.py's bound (762,903
// bytes): a whole surface of its own, which is the answer that test's comment
// asks for rather than a raised number.
//
// Loaded straight after app.js (see index.html), before every other boot
// file, so anything that paints a face at boot finds it. Its top level only
// declares tables and functions; app.js, settings.js and the lazy bundles
// call `nameMark`/`nameMood` only from functions, never at parse time.

//: **What a name says about the face it gets** (the owner: "would it be funny
//: if ... the application detects the intent or mood from the name ... like
//: I have personas called 'overly dramatic narrator', and 'depressed
//: wizard'", then "most people wont do that ... if I put in the word
//: pandaSushi101, what would that generate"). `nameMood` reads a name in
//: four layers, most specific first, and `nameMark` draws what it found:
//:
//: 1. **Words.** A mood word ("depressed", "grumpy", "dramatic") or a noun
//:    that carries one ("coffee" is wired, "moon" is sleepy, "sushi" is
//:    hungry), an animal ("panda" draws a panda), and a costume ("wizard"
//:    is a hat, "academic" is glasses). camelCase, digits and underscores
//:    split a handle into words, so "pandaSushi101" is panda, sushi, 101;
//:    and a name typed as one lower-case run is scanned for the longer
//:    keywords (four letters and up) inside it, so "pandasushi" reads the
//:    same. A keyword of three letters only ever matches a whole word:
//:    "mad" is a mood and "Madison" is a name, "cat" is an animal and
//:    "education" is not a cat. A prefix (the `*`) only ever stands on four
//:    letters or more, for the same reason ("Sadie" is not sad).
//: 2. **Intensity.** "overly", "very", "extremely" and their friends turn the
//:    face up (a bigger gasp, steeper brows, a second tear).
//: 3. **How it is typed.** ALL CAPS shouts; "!" is excited, "?" confused,
//:    "..." sleepy; emoticons and emoji say what they say; a few numbers
//:    mean something to the people who type them (666, 007, 404, 1337).
//: 4. **Nothing at all.** A personality drawn from the name's own hash, so
//:    "Alice" is always the same Alice: a plain face a quarter of the time,
//:    otherwise a friendly one (happy, calm, a little excited, cute). Never
//:    a costume or an animal: those only come from a word, so a seeded face
//:    never claims something about a name that the name did not say.
//:
//: **The design rules** (the owner, 2026-09-24: "refine the avatar
//: generation as it is still a little messy and I'm not happy with what is
//: generated when I put in my name 'Brayden' or 'Sushicraft563,
//: SushiLord'"). Each is enforced here or in `drawCharacter`, and pinned by
//: tests/test_name_mood.py:
//:
//: - **A plain first name is a character, not a costume.** One hairstyle,
//:   a friendly face, no animal, nothing held, and two traits from the
//:   hash (headwear, eyewear, a small accent, attitude, facial hair), each
//:   from its own family (the owner, after the first clean defaults: "they
//:   look a bit too mundane now ... more character, less stock").
//: - **Presentation is the person's choice.** Masculine, feminine or
//:   neutral comes from Profile, Your look for your own name and Settings,
//:   Appearance, Face looks for every other; never from the name, first
//:   name or any word in it. It picks the hair set, brow weight, jaw and
//:   cheeks, lashes and whether facial hair is on offer.
//: - **Words drive at most two visual cues**, chosen by salience: a species
//:   first, then what is worn and held in the order the name says it, then
//:   food. "Sushicraft563" holds a pickaxe with sushi in its hair;
//:   "SushiLord" wears a crown and holds sushi. Numbers only nudge the
//:   seeded variety (they are in the hash); the few that mean something
//:   (666, 404) lean the mood and add nothing to wear.
//: - **A hard budget**: one head item, one face item, one held item, one
//:   body item. A second claim on a slot loses to the first; accessories
//:   only fill a slot the words left free. Nothing is drawn over the eyes
//:   but eyewear, and a flavour ("wink", "cooked") is drawn only when it
//:   does not fight the mood for the same features, one at most.
//: - **A curated palette** (`NM_CHAR_PAIRS`): each character's body, hair and
//:   clothes come from one of a few pairs chosen to sit together, each
//:   checked for contrast on the light and the dark page.
//: - **Readable at 28px**: the head-only mark at that size and under draws
//:   the face and at most one cue that breaks the outline.
//:
//: All local, all instant, nothing stored: the reading is a pure function of
//: the name, pinned by tests/test_name_mood.py.
const NAME_MOOD_LEXICON = {
  moods: {
    happy: "happy happily cheer* jolly joy joyful glad merry upbeat optimis* bubbly friendly kind sweet delight* sunny sunshine smile* smiley smiling cheery chipper jovial rainbow* sun hopeful wholesome",
    excited: "excit* exita* hyper* eager* enthus* thrill* energ* zeal* manic stoked ecstatic giddy pumped wired peppy coffee* espresso* caffein* rocket* sparkl* glitter* party partying hype hyped yay woo woohoo wahoo yeet",
    sad: "sad sadly sadness depress* gloom* melanch* mope mopey sorrow* weep* crying cries miser* lonely forlorn glum morose pessim* emo heartbr* tragic* despair* dejected rain rainy raincloud* cloudy drizzl* blues oof rip sob sobbing",
    angry: "angry anger angrily grump* cranky furious rage raging irate mad grouch* hostile bitter annoy* irritab* livid fuming salty cantankerous storm* thunder* fire fiery flame* blaze* volcan* spicy",
    dramatic: "dramat* theatric* melodram* overact* flamboy* diva extra histrion* operatic shakespear* bard",
    surprised: "surpris* shock* astonish* amaz* startl* stunned gobsmack* flabbergast* awestruck ghost* spook* boo",
    sleepy: "sleep* tired drowsy lazy yawn* bored boring weary exhaust* sluggish nap napping snooz* lethargic moon* night* midnight* dream* insomnia* pillow* sloth*",
    nervous: "nervous anxious anxiet* worri* worry panic* paranoi* jitter* shy timid awkward neurotic scared fright* coward* skittish frazzled",
    sly: "sly sneak* mischiev* cunning sarcas* snark* smug cheeky devious trickster rogue sassy cynic* scheming shady ninja* spy spies agent hacker* shadow* gremlin* goblin* raccoon* thief",
    evil: "evil villain* sinister menac* maniac* muaha* mwaha* bwaha* mwuaha* cackl* diabolic* wicked malic* overlord* mastermind* nefarious dastard* supervillain*",
    sick: "sick sickly ill nause* queasy flu covid sneez* feverish fever germ* poorly",
    dead: "dead ded deceased skull* zombie* undead corpse* ghoul* lich skeleton*",
    starstruck: "starstruck star stars superstar* famous celeb* fangirl* fanboy* fan fans idol*",
    cute: "cute cutie smol tiny baby babies bby lil kawaii precious chibi bean",
    drunk: "drunk tipsy wasted hungover boozy sloshed",
    greedy: "rich money cash* greed* banker* billion* million* capitalist* crypto* stonks bitcoin* hustl* moneybag* loaded",
    calm: "calm* wise zen serene stoic* sage patient gentle mellow relax* peace* tranquil tea monk* yoga",
    serious: "serious stern strict formal pedant* logical deadpan dry grave solemn business* lawyer* accountant* judge* doom* void abyss",
    confused: "confus* baffl* bewild* puzzl* clueless perplex* muddled ditzy lost hm hmm um umm uh uhh erm huh",
    laughing: "lol lolol lols lmao* lmfao rofl haha* hehe* hihi* jaja* kek xd funny funnie* joke* joking jester* clown* comed* silly goof* giggl* laugh* chuckl* prank*",
    unimpressed: "meh ugh bleh bruh whatever unimpress* sceptic* skeptic* jaded blase fine okay ok",
    dizzy: "dizzy woozy spinning chaos* chaotic random* glitch* scrambl*",
    hungry: "hungry hunger* starv* sushi* pizza* taco* burger* cake* cookie* donut* doughnut* noodle* ramen* pasta* cheese* bacon* snack* candy candies choco* waffle* pancake* muffin* cupcake* fries dumpling* boba mochi* sandwich* burrito* nacho* bagel* pie toast* peach* mango* banana* berry cherry* foodie* yum yummy nom nomnom",
    cool: "cool coolest chill* rad dude swag boss suave slick shades",
    love: "love* lovely romantic* crush* heart* cupid* valentin* adorable darling sweetheart",
    uwu: "uwu owo nya nyaa",
  },
  animals: {
    panda: "panda*",
    bear: "bear bears teddy grizzl*",
    koala: "koala*",
    mouse: "mouse mice",
    monkey: "monkey* chimp* ape",
    cat: "cat cats kitty kitten* kitteh meow* catto neko",
    fox: "fox foxy foxes",
    wolf: "wolf wolves",
    tiger: "tiger*",
    lion: "lion lions",
    bunny: "bunny bunnies rabbit* hare",
    dog: "dog dogs doggo* puppy puppies pup pupper* woof* corgi*",
    frog: "frog* toad*",
    pig: "pig pigs piggy piglet* oink",
    owl: "owl owls",
    chick: "chick chicks chicken*",
    duck: "duck ducks duckling* quack*",
    bird: "bird birds birb* parrot* robin* sparrow* crow* raven* tweet*",
    hamster: "hamster* gerbil*",
    sheep: "sheep lamb lambs ewe wool* baa",
    cow: "cow cows moo cattle bull bulls",
    deer: "deer reindeer* stag doe fawn* moose elk",
    unicorn: "unicorn*",
    dragon: "dragon* wyvern*",
    dino: "dino* trex raptor* dinosaur*",
    shark: "shark* jaws",
    snake: "snake* serpent* python* viper* cobra* sssnake",
    axolotl: "axolotl*",
    crab: "crab crabs crabby lobster*",
    raccoon: "raccoon* trashpanda*",
    hedgehog: "hedgehog* hedgie spiky",
    sloth: "sloth*",
    capybara: "capybara* capy",
    bee: "bee bees bumble* honeybee*",
    mermaid: "mermaid* siren* merfolk",
    elf: "elf elves elven elvish",
    goblin: "goblin* gremlin*",
    troll: "troll trolls trolling ogre* shrek",
    gnome: "gnome* garden gnome",
    genie: "genie* djinn* jinn",
    mummy: "mummy mummies pharaoh*",
    zombie: "zombie* undead walker",
    minotaur: "minotaur*",
    medusa: "medusa* gorgon*",
    cyclops: "cyclops cyclopes",
    phoenix: "phoenix*",
    yeti: "yeti* bigfoot* sasquatch* abominable",
    penguin: "penguin* pingu",
    ghost: "ghost* spook* boo",
    alien: "alien* ufo martian*",
    octopus: "octopus* octo octopi squid* kraken* cthulhu*",
    bat: "bat bats",
  },
  //: Not every character has hands (the owner: "some can have feet or
  //: tentacles or wings some none at all"). None is the default.
  limbs: {
    tentacles: "octopus* octo octopi squid* kraken* cthulhu* tentacle* jellyfish* eldritch",
    feet: "walker* runner* hiker* dancer* jogger* feet foot* toes sneaker* stomp*",
  },
  props: {
    hat: "wizard* witch* mage magi magician* sorcer* warlock* druid* necroman* enchant* merlin gandalf",
    chefhat: "chef chefs cook cooks baker* cooking",
    glasses: "academic* professor* prof scholar* librarian* teacher* tutor* researcher* historian* editor* critic* analyst* philosoph* linguist* mathemat* boffin* smart",
    squareglasses: "nerd* geek* coder* programmer* developer* dev hipster* techie*",
    monocle: "monocle* posh aristocrat* sophisticat* distinguished",
    goggles: "scientist* chemist* physicist* pilot* aviator* steampunk* welder* inventor* engineer* lab",
    threed: "3d cinema* movie* movies film* retro",
    starglasses: "rockstar* popstar* glam* fabulous",
    heartglasses: "heartbreaker* flirt* casanova",
    visor: "cyber* vr futur* hacker* neon synthwave",
    eyepatch: "pirate* buccaneer* arr arrr",
    crown: "king kings queen* prince princes royal* emperor* empress* monarch* regal duke duchess lord lords",
    tiara: "princess* tiara* pageant*",
    tricorn: "pirate* buccaneer* captain* corsair*",
    cap: "cap caps baseball* skater* skate* sporty jock* athlete* coach* trucker*",
    beanie: "beanie* cozy cosy winter* snowy chilly toque",
    flowercrown: "cottagecore boho* flowerchild* springtime maypole",
    headband: "karate* dojo* sensei* kungfu judo* taekwondo* blackbelt martial* rocky",
    bandana: "bandana* biker* rebel* rambo outlaw* bandit*",
    bow: "bow bows ribbon* coquette",
    beard: "beard* bearded lumberjack* santa hagrid dwarf* grizzled",
    halo: "angel angels angelic saint* guardian* cherub* holy",
    horns: "devil* demon* imp fiend* satan*",
    antenna: "robot* bot bots android* cyborg* droid* machine* automaton* ai",
    moustache: "butler* gentleman gentlemen baron* mustach* moustach* walrus* sir",
    headphones: "headphone* headset* dj music* gamer* gaming podcast* audio* beats",
    fangs: "vampire* vamp dracula* nosferatu",
    rednose: "clown* rudolph reindeer*",
    cowboy: "cowboy* cowgirl* sheriff* yeehaw rodeo* ranch* wrangler*",
    partyhat: "party partying birthday* bday celebrat* fiesta*",
    ninjamask: "ninja*",
    helmet: "astronaut* cosmonaut* spaceman* rocketman",
  },
  //: What the hand does or holds. One hand, one thing: the first named.
  hands: {
    thumbsup: "nice thumbs* thumbsup gg approve* approved goodjob kudos noice",
    peace: "peace* peaceout hippie* namaste",
    wave: "hi hii hey heya hiya hello* howdy greetings welcome* sup yo bye goodbye",
    beer: "beer* brew* ale lager booze* cheers pint* drinks",
    wine: "wine* vino merlot sommelier* classy fancy champagne* prosecco",
    mug: "coffee* espresso* latte* mug cappucc* barista* tea",
    sword: "knight* warrior* samurai* sword* paladin* viking* gladiator* slayer*",
    magnifier: "detective* sherlock* investigat* sleuth* inspector*",
    mic: "karaoke* singer* rapper* mic vocal* diva",
    book: "book* reader* novel* poet* writer* author* bookworm* storyteller*",
    phone: "influencer* selfie* tiktok* texting doomscroll* insta* phone*",
    flower: "flower* garden* bloom* blossom* florist* daisy* sunflower* petal*",
    pizza: "pizza*",
    donut: "donut* doughnut*",
    sushi: "sushi* nigiri* sashimi* onigiri* maki",
    balloon: "balloon*",
    tableflip: "tableflip* flip flipping ragequit",
    controller: "gamer* gaming xbox* playstation* ps5 nintendo* switch controller* joystick* gamepad* esports",
    pickaxe: "craft* miner* mining minecraft* pickaxe* digger*",
    axe: "axe axes lumberjack* woodcutter*",
    hammer: "hammer* thor builder* carpenter* blacksmith* smith mjolnir",
    blaster: "blaster* sniper* gunner* gunslinger* shooter* fps pewpew gun guns trigger* laser*",
    bow: "archer* archery hunter* legolas robinhood katniss arrow*",
    wand: "wand* wizard* spellcaster* sorcer* harrypotter hogwarts",
    fishingrod: "fisher* fishing angler* fisherman",
    paintbrush: "artist* painter* paint* picasso bobross",
    spear: "spear* spartan* lancer* pike pikeman javelin* hoplite*",
    trident: "trident* poseidon neptune merman mermaid* aquaman",
  },
  //: What the shoulders wear (the owner: "regular girls or guys, office,
  //: street attire"). A word picks it; otherwise the style below does.
  outfits: {
    suit: "office* corporate* business* ceo cfo cto boss manager* lawyer* banker* accountant* consultant* intern* clerk* executive* suit suits",
    hoodie: "street* hoodie* hypebeast* drip urban* skater* rapper* gamer* hacker* coder*",
    dress: "dress* gown* prom ball elegant fancy",
  },
  //: Which wings, when a name has them: seven kinds, each drawn its own way.
  wings: {
    angel: "angel angels angelic cherub* seraph* dove* pegasus* holy",
    bird: "bird birds birb* feather* parrot* robin*",
    phoenix: "phoenix*",
    dragon: "dragon* wyvern*",
    bat: "bat bats demon* gargoyle*",
    fairy: "fairy fairies faerie* pixie* sprite*",
    bee: "bee bees bumble* wasp* honeybee*",
    butterfly: "butterfl* moth moths",
  },
  //: Flavours stack on whatever mood the name set: "wink" winks, "ahhhh"
  //: screams, "cooked" sweats. A name that says five things gets all five.
  flavours: {
    wink: "wink winks winking winky",
    scream: "ah aah ahh scream* yell* shriek* help",
    doomed: "cooked doomed cursed rip finished panick* yikes",
    blush: "blush* flustered shy",
  },
  intensifiers: "overly very extremely super ultra really totally too so mega incredibly absurdly wildly insanely ridiculously deeply utterly perpetually chronically hella terribly awfully massively most",
};

//: **Your own face, your way** (the owner: "what if i dont like how the
//: avatar it looks on my name??"). The profile saves a `variant` (which take
//: on the name; each Shuffle moves it on) and per-part overrides. They apply
//: to the person's own name only (`userMarkSeed`, app.js), so renaming keeps
//: the choices and every other name keeps its own reading.
//: `null` means "what is saved" (`prefsCache.avatar_style`); the profile's
//: controls set a draft while the form is unsaved.
let nameMarkOwn = null;
const NAME_MARK_HAT_KINDS = ["hat", "chefhat", "cowboy", "partyhat", "crown", "tiara", "tricorn", "cap", "beanie", "flowercrown", "bandana", "headband"];
const NAME_MARK_EYEWEAR_KINDS = ["glasses", "squareglasses", "monocle", "goggles", "threed", "starglasses", "heartglasses", "visor", "shades"];

//: The slots a character has room for, one thing each (see the budget in
//: `nameMood`): what sits on the head, what sits on the face, what the
//: hand holds, and what the body wears.
const NAME_MARK_HEAD_KINDS = [...NAME_MARK_HAT_KINDS, "halo", "horns", "antenna", "headphones", "helmet", "bow", "sushiclip", "flowerclip", "hood"];
const NAME_MARK_FACE_KINDS = [...NAME_MARK_EYEWEAR_KINDS, "eyepatch", "ninjamask", "rednose", "moustache", "beard", "fangs", "stubble", "earrings", "lipstick", "shortbeard"];
const NAME_MARK_FOODS = ["sushi", "pizza", "donut"];
//: The hair styles, skins and hair colours by name (drawn from
//: `NM_HAIR_STYLES`, `NM_CHAR_SKINS` and `NM_CHAR_HAIR_TONES` below), and
//: the first styles' names, which a saved Profile choice may still carry.
const NAME_MARK_HAIR_KINDS = ["crop", "sweep", "quiff", "curtains", "messy", "curls", "wavy", "long", "waves", "bob", "bun", "ponytail", "locs", "undercut", "spiky", "mohawk", "fringe", "slick", "longcurls", "buzzline"];
const NAME_MARK_HAIR_ALIASES = { short: "crop", curly: "curls", buns: "bun", buzz: "buzzline", pigtails: "ponytail" };
const NAME_MARK_SKIN_KINDS = ["porcelain", "fair", "peach", "tan", "olive", "brown", "deep"];
const NAME_MARK_HAIR_TONE_KINDS = ["black", "espresso", "brown", "chestnut", "auburn", "copper", "honey", "blond", "platinum"];

function nameMarkSlot(kind, key) {
  if (kind === "animal") return "species";
  if (kind === "hand") return "held";
  if (kind === "prop" || kind === "accessory") return NAME_MARK_FACE_KINDS.includes(key) ? "face" : "head";
  return "body";
}

function setOwnNameMarkStyle(style) {
  nameMarkOwn = style && typeof style === "object" ? { ...style } : {};
}

//: **A saved style as it may be drawn now** (INBOX 426 w, 73.png and
//: 90.png): each part only if it is one of the part's options today (or
//: "none", or an old hair name the drawing still reads), so a part since
//: taken out (the rude gesture) is left to the name instead of leaving its
//: picker empty. The server drops retired parts too (`_clean_avatar_style`
//: in routes_settings.py); this is the same for anything kept on this
//: computer, and for a list that changes before the server's does.
function nameMarkStyleClean(style) {
  const out = {};
  if (!style || typeof style !== "object") return out;
  const variant = Number(style.variant);
  if (Number.isFinite(variant) && variant > 0) out.variant = Math.floor(variant) % 10000;
  let parts;
  try {
    parts = PROFILE_LOOK_PARTS;
  } catch (e) {
    //: Read before the part lists are defined (a face drawn while this
    //: file is still loading): as it was saved.
    return { ...style };
  }
  for (const [key, , options] of parts) {
    const value = style[key];
    if (typeof value !== "string" || !value) continue;
    const allowed = (value === "none" && key !== "skin" && key !== "hairtone") || options().includes(value) || (key === "hair" && NAME_MARK_HAIR_ALIASES[value]);
    if (allowed) out[key] = value;
  }
  return out;
}

function ownNameMarkStyle() {
  return nameMarkStyleClean(nameMarkOwn ?? ((typeof prefsCache !== "undefined" && prefsCache?.avatar_style) || {}));
}

function nameMarkOwnFor(name) {
  const lower = String(name || "").trim().toLowerCase();
  if (typeof userMarkSeed === "function") {
    const own = String(userMarkSeed() || "").trim().toLowerCase();
    if (own && lower === own) return ownNameMarkStyle();
  }
  //: Your own companion's name wears the parts you chose for it, and only
  //: while it is your companion (`nameMarkBuddyCustom`).
  if (lower && typeof appearancePref === "function" && appearancePref("avatar-buddy", "off") === "custom") {
    const custom = nameMarkBuddyCustom();
    if (lower === custom.name.toLowerCase()) return { ...custom.style };
  }
  return null;
}

//: **A companion of your own** (INBOX 426 e, the owner: "add the ability to
//: make a custom companion that isnt based off your name"). Any name, and
//: the same parts as Your look (look, mood, hair, skin, clothes, headwear,
//: eyewear, what it holds), each "From its name" until you choose; kept on
//: this computer (`avatar-buddy-custom`), like the rest of Appearance.
let nameMarkBuddyCustomCache = null;
function nameMarkBuddyCustom() {
  if (nameMarkBuddyCustomCache) return nameMarkBuddyCustomCache;
  let saved = {};
  try {
    saved = prefs.json("avatar-buddy-custom", {}) || {};
  } catch (e) {
    saved = {};
  }
  const name = String(saved.name || "").trim().slice(0, 40) || "Buddy";
  nameMarkBuddyCustomCache = { name, style: nameMarkStyleClean(saved.style) };
  return nameMarkBuddyCustomCache;
}

function nameMarkBuddyKeepCustom(custom) {
  nameMarkBuddyCustomCache = null;
  try {
    prefs.set("avatar-buddy-custom", JSON.stringify({ name: custom.name, style: custom.style }));
  } catch (e) {
    // Kept for this visit only.
  }
  const buddy = document.getElementById("nm-buddy");
  if (buddy) {
    delete buddy.dataset.seed;
    syncNameMarkBuddy();
  }
}

//: The look a generated face takes when its name gives no cue: null for
//: Neutral (stored as "mixed"), or one of the two.
function nameMarkLookLean() {
  const lean = typeof appearancePref === "function" ? appearancePref("face-look", "mixed") : "mixed";
  return lean === "feminine" || lean === "masculine" ? lean : null;
}

//: Every generated face on the page drawn again (a change of Face looks):
//: every size read first, then every face replaced, so it costs one layout.
function nameMarkRepaintAll() {
  const faces = [...document.querySelectorAll(".name-mark[data-nm-seed]:not(.nm-atlas)")].filter((el) => !el.closest("#nm-buddy"));
  const sizes = faces.map((el) => Math.round(el.getBoundingClientRect().width) || 20);
  faces.forEach((el, i) => el.replaceWith(nameMark(el.dataset.nmSeed, sizes[i])));
  repaintOwnFace();
}

function nameMood(name) {
  const raw = String(name || "").trim();
  const own = nameMarkOwnFor(raw);
  const variant = Number(own?.variant) || 0;
  const result = {
    mood: null, intense: false, animal: null, props: [], flavours: [], hand: null, limbs: null, mutant: null,
    wing: null, look: null, cues: [],
    style: { smile: "smile", eyes: "dot", features: [], nose: null, hair: null, hairColour: 0, hairTone: null, skin: null, accessories: [], outfit: null, outfitColour: 0 },
    source: "seed",
  };
  if (!raw) return result;
  //: One parsed table per page, not per mark: the lexicon is fixed.
  if (!nameMood.table) {
    const parse = (text) =>
      text.split(/\s+/).filter(Boolean).map((entry) => {
        const stem = entry.replace(/\*$/, "");
        //: A prefix needs four letters under it; a shorter one is exact.
        return { stem, prefix: entry.endsWith("*") && stem.length >= 4 };
      });
    const group = (table) =>
      Object.entries(table).map(([key, text]) => ({ key, entries: parse(text) }));
    nameMood.table = {
      moods: group(NAME_MOOD_LEXICON.moods),
      animals: group(NAME_MOOD_LEXICON.animals),
      props: group(NAME_MOOD_LEXICON.props),
      flavours: group(NAME_MOOD_LEXICON.flavours),
      hands: group(NAME_MOOD_LEXICON.hands),
      limbs: group(NAME_MOOD_LEXICON.limbs),
      wings: group(NAME_MOOD_LEXICON.wings),
      outfits: group(NAME_MOOD_LEXICON.outfits),
      intensifiers: new Set(NAME_MOOD_LEXICON.intensifiers.split(/\s+/)),
    };
  }
  const table = nameMood.table;
  const words = raw
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/([A-Za-z])(\d)/g, "$1 $2")
    .replace(/(\d)([A-Za-z])/g, "$1 $2")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
  //: A stretched word is still the word: "happyyyy" is happy, "sooo" is so,
  //: "hmmmm" is hm. Only a run of three or more is squeezed, so "cool" and
  //: "happy" keep their own double letters.
  const forms = words.map((word) => {
    const squeezed = word.replace(/(.)\1{2,}/g, "$1");
    return squeezed === word ? [word] : [word, squeezed];
  });
  const letters = raw.toLowerCase().replace(/[^a-z]/g, "");
  //: Where a group's keywords first hit the name. `at` ranks a whole-word
  //: match ahead of every glued one (the mood and the hand take the
  //: earliest); `order` is the plain place in the name, word by word and
  //: letter by letter, which is what ranks the visual cues below.
  //:
  //: The glued-name scan looks inside one word at a time: a prefix stem
  //: anywhere in it, an exact stem only where the word ends, so
  //: "sushilord" is a lord and "cooked" is not a cook (the owner's "ur
  //: cooked buddy" wore a chef's hat until this). Only stems of four
  //: letters and up, and only three letters or more into the word, which
  //: is where a second word glued on would start: "Janice" is not "nice"
  //: and "Clover" is not in love.
  const hitAt = (entries) => {
    let best = null;
    const take = (at, order) => {
      if (!best || at < best.at) best = { at, order };
    };
    for (const { stem, prefix } of entries) {
      forms.forEach((variants, index) => {
        for (const word of variants) {
          if (prefix ? word.startsWith(stem) : word === stem) take(index * 1000, index * 1000);
          else if (stem.length >= 4 && word.length > stem.length) {
            const off = prefix ? word.indexOf(stem) : word.endsWith(stem) ? word.length - stem.length : -1;
            if (off >= 3) take(500000 + index * 1000 + off, index * 1000 + off);
          }
        }
      });
      //: A keyword typed as two words is still the keyword: "rage quit",
      //: "good job", "screw you".
      if (stem.length >= 4 && forms.length > 1 && letters === stem) take(500000, 0);
    }
    return best;
  };
  //: The earliest match wins, by where it sits in the name: "sad happy cat"
  //: is sad, the way a reader takes the first adjective as the character.
  const find = (groups) => {
    let best = null;
    for (const { key, entries } of groups) {
      const hit = hitAt(entries);
      if (hit && (!best || hit.at < best.at)) best = { key, ...hit };
    }
    return best;
  };
  //: Every group that hits, in the order the name says them.
  const findAll = (groups) =>
    groups
      .map(({ key, entries }) => ({ key, ...hitAt(entries) }))
      .filter((hit) => hit.at !== undefined)
      .sort((a, b) => a.order - b.order || a.at - b.at);
  const moodHit = find(table.moods);
  result.mood = moodHit?.key || null;
  //: Every thing the words ask to be seen, with where they said it; the
  //: budget below keeps at most two (`result.cues`).
  const heard = [];
  const hear = (kind, key, order) => {
    if (key && !heard.some((h) => h.kind === kind && h.key === key)) heard.push({ kind, key, order });
  };
  for (const hit of findAll(table.hands)) hear("hand", hit.key, hit.order);
  const limbsHit = find(table.limbs);
  const wingHit = find(table.wings);
  //: **Presentation is your choice, never read from a name** (the owner:
  //: "for my own name 'Brayden' the face reads as feminine, which I don't
  //: want"; before that, "Queen" and "Dude" set it). Your own face takes
  //: Profile, Your look (masculine, feminine or neutral); every other face
  //: takes Settings, Appearance, Face looks; Neutral until either is set.
  //: It picks the hair set, the brows' weight, the jaw and cheeks, lashes,
  //: and whether facial hair is on offer.
  if (own && ["feminine", "masculine"].includes(own.look)) result.look = own.look;
  else if (!(own && own.look === "neutral")) result.look = nameMarkLookLean();
  const animalHit = find(table.animals);
  if (animalHit) hear("animal", animalHit.key, animalHit.order);
  if (wingHit) hear("wing", wingHit.key, wingHit.order);
  if (limbsHit) hear("limbs", limbsHit.key, limbsHit.order);
  for (const hit of findAll(table.props)) hear("prop", hit.key, hit.order);
  const outfitHit = find(table.outfits);
  if (outfitHit) hear("outfit", outfitHit.key, outfitHit.order);
  //: Flavours stack on the mood only where they do not fight it for the
  //: same features, and only one of them is drawn (the owner, on "Uwu wink
  //: wink ahhhhhh ur cooked buddy": "still a little messy"): a wink needs
  //: an open eye to close, a scream takes over the eyes and mouth so it
  //: only draws when no word set the mood, and a sweat drop or a blush
  //: sits beside anything. The first named that fits wins.
  const flavoursHeard = findAll(table.flavours).map((hit) => hit.key);
  if (/;-?\)/.test(raw) && !flavoursHeard.includes("wink")) flavoursHeard.push("wink");
  const shutEyes = ["happy", "sleepy", "calm", "hungry", "laughing", "uwu", "love", "dead", "dizzy", "starstruck", "greedy", "cool"];
  const fits = {
    wink: () => !shutEyes.includes(result.mood),
    scream: () => !moodHit,
    doomed: () => true,
    blush: () => true,
  };
  result.flavours = flavoursHeard.filter((flavour) => fits[flavour]?.()).slice(0, 1);
  //: (╯°□°)╯︵ ┻━┻ has no letters at all, and needs none.
  const flipped = /┻━+┻|╯°□°/.test(raw);
  if (flipped) hear("hand", "tableflip", -2);
  const emojiHands = [
    [/\u{1F44D}/u, "thumbsup"], [/✌/u, "peace"], [/\u{1F44B}/u, "wave"],
    [/[\u{1F37A}\u{1F37B}]/u, "beer"], [/[\u{1F377}\u{1F942}]/u, "wine"], [/☕/u, "mug"],
    [/[⚔\u{1F5E1}]/u, "sword"], [/[\u{1F50D}\u{1F50E}]/u, "magnifier"], [/\u{1F3A4}/u, "mic"],
    [/[\u{1F4DA}\u{1F4D6}]/u, "book"], [/\u{1F4F1}/u, "phone"], [/[\u{1F338}\u{1F339}\u{1F337}\u{1F33B}]/u, "flower"],
    [/\u{1F355}/u, "pizza"], [/\u{1F369}/u, "donut"], [/\u{1F388}/u, "balloon"], [/\u{1F363}/u, "sushi"],
    [/\u{1F3AE}/u, "controller"], [/⛏/u, "pickaxe"], [/\u{1FA93}/u, "axe"], [/\u{1F528}/u, "hammer"],
    [/\u{1F52B}/u, "blaster"], [/\u{1F3F9}/u, "bow"], [/\u{1FA84}/u, "wand"], [/\u{1F3A3}/u, "fishingrod"],
    [/[\u{1F58C}\u{1F3A8}]/u, "paintbrush"],
  ];
  if (!heard.some((h) => h.kind === "hand")) {
    for (const [pattern, hand] of emojiHands) {
      if (pattern.test(raw)) {
        hear("hand", hand, 900000);
        break;
      }
    }
  }
  //: Nobody flips a table calmly.
  if (heard.some((h) => h.key === "tableflip")) {
    result.mood = "angry";
    result.intense = true;
  }
  result.intense = result.intense || forms.some((variants) => variants.some((word) => table.intensifiers.has(word)));
  if (result.mood || heard.length) result.source = "words";

  //: Layer three, how it is typed. Read even when the words spoke, for the
  //: intensity ("Happy!!!"), and for the mood only when they did not.
  let hinted = null;
  const hint = (mood) => {
    if (!hinted) hinted = mood;
  };
  const emoji = [
    [/[\u{1F634}\u{1F4A4}\u{1F971}]/u, "sleepy"],
    [/[\u{1F60D}\u{1F970}\u{1F618}\u{2764}\u{1F495}\u{1F496}]/u, "love"],
    [/[\u{1F622}\u{1F62D}\u{1F61E}\u{1F614}\u{2639}\u{1F641}]/u, "sad"],
    [/[\u{1F620}\u{1F621}\u{1F92C}\u{1F4A2}]/u, "angry"],
    [/[\u{1F62E}\u{1F632}\u{1F631}\u{1F92F}]/u, "surprised"],
    [/\u{1F60E}/u, "cool"],
    [/\u{1F608}/u, "evil"],
    [/[\u{1F480}\u{2620}]/u, "dead"],
    [/[\u{1F922}\u{1F92E}\u{1F912}\u{1F927}]/u, "sick"],
    [/[\u{1F602}\u{1F923}\u{1F921}]/u, "laughing"],
    [/[\u{1F31F}\u{2B50}]/u, "starstruck"],
    [/\u{1F97A}/u, "cute"],
    [/\u{1F60F}/u, "sly"],
    [/[\u{1F911}\u{1F4B0}\u{1F4B8}]|\$\$/u, "greedy"],
    [/[\u{1F60B}\u{1F924}\u{1F363}\u{1F355}\u{1F354}\u{1F369}\u{1F370}]/u, "hungry"],
    [/[\u{1F914}\u{1F615}\u{2753}]/u, "confused"],
    [/\u{1F929}/u, "starstruck"],
    [/[\u{1F389}\u{2728}\u{26A1}\u{1F973}]/u, "excited"],
    [/[\u{1F600}\u{1F603}\u{1F604}\u{1F601}\u{1F642}\u{1F60A}\u{263A}]/u, "happy"],
  ];
  for (const [pattern, mood] of emoji) if (pattern.test(raw)) hint(mood);
  const emojiCreatures = [
    [/\u{1F43C}/u, "panda"], [/\u{1F431}/u, "cat"], [/\u{1F436}/u, "dog"], [/\u{1F430}/u, "bunny"],
    [/\u{1F98A}/u, "fox"], [/\u{1F43B}/u, "bear"], [/\u{1F438}/u, "frog"], [/\u{1F437}/u, "pig"],
    [/\u{1F989}/u, "owl"], [/\u{1F47B}/u, "ghost"], [/\u{1F47D}/u, "alien"], [/\u{1F427}/u, "penguin"],
  ];
  if (!heard.some((h) => h.kind === "animal")) {
    for (const [pattern, animal] of emojiCreatures) {
      if (pattern.test(raw)) {
        hear("animal", animal, 900000);
        break;
      }
    }
  }
  const emojiProps = [
    [/\u{1F916}/u, "antenna"], [/\u{1F451}/u, "crown"], [/\u{1F9D9}/u, "hat"], [/\u{1F913}/u, "glasses"],
    [/\u{1F608}/u, "horns"], [/\u{1F921}/u, "rednose"], [/\u{1F9DB}/u, "fangs"], [/\u{1F920}/u, "cowboy"],
    [/\u{1F973}/u, "partyhat"], [/\u{1F977}/u, "ninjamask"], [/\u{1F97D}/u, "goggles"], [/\u{1F9D0}/u, "monocle"],
  ];
  emojiProps.forEach(([pattern, prop], i) => {
    if (pattern.test(raw)) hear("prop", prop, 900001 + i);
  });
  const emoticons = [
    [/>:\(|>:-\(/, "angry"],
    [/:-?\)|\(:|\^_?\^|=\)/, "happy"],
    [/:-?\(|T_T|;_;|=\(/, "sad"],
    [/:-?D|\bx-?D\b/i, "excited"],
    [/:-?[Pp]\b|:-?[Pp]$/, "hungry"],
    [/:-?[Oo]\b|:-?[Oo]$|\b[oO]_[oO]\b/, "surprised"],
    [/-_-|\bz{3,}\b/i, "sleepy"],
    [/;-?\)/, "sly"],
    [/<3/, "love"],
    [/\b[B8]-?\)/, "cool"],
    [/^x+X|X+x+$/, "sly"],
  ];
  for (const [pattern, mood] of emoticons) if (pattern.test(raw)) hint(mood);
  //: A number a handle carries only nudges the seeded variety (it is in
  //: the hash); the few that mean something lean the mood, and none of them
  //: adds a thing to wear (the owner: "Sushicraft563").
  const numbers = { 666: "sly", "007": "cool", 404: "confused", 1337: "sly", 9000: "excited", 420: "calm" };
  for (const word of words) {
    if (!numbers[word]) continue;
    hint(numbers[word]);
    if (word === "9000") result.intense = true;
  }
  if (/\.\.\.|…/.test(raw)) hint("sleepy");
  if (/\?\s*$/.test(raw)) hint("confused");
  const bangs = (raw.match(/!/g) || []).length;
  if (bangs) hint("excited");
  if (bangs >= 2) result.intense = true;
  const capitals = raw.replace(/[^A-Za-z]/g, "");
  //: Shouting is three capitals or more and no lower case at all; "AI" and
  //: "DJ" are initials, not raised voices.
  if (capitals.length >= 3 && capitals === capitals.toUpperCase()) {
    result.intense = true;
    hint("excited");
  }
  if (!result.mood && hinted) {
    result.mood = hinted;
    if (result.source === "seed") result.source = "hint";
  } else if (result.source === "seed" && (heard.length || result.intense)) {
    result.source = "hint";
  }

  //: **Names that make no sense** (the owner: "can you improve or expand it
  //: even more for names which just make no sence haha??"). When neither the
  //: words nor the typing said anything, the letters themselves still can:
  //: a held key is a scream ("aaaaaaa"), a run along one keyboard row is a
  //: dizzy mash ("asdfgh"), and a handle nobody could pronounce (no vowels,
  //: five consonants in a row, or letters and digits shuffled together) is
  //: a little mutant whose traits come from its characters. That last idea
  //: is helixlabs's (the owner's own MIT project, sketch.js): sum each
  //: character's code times its position, so order matters, and let that
  //: number decide the species. Here it decides how many eyes, whether they
  //: are googly or on stalks, how many spots, and whether there are fangs.
  if (!result.mood && !heard.some((h) => h.kind === "animal" || h.kind === "prop") && letters.length >= 3) {
    const compact = raw.toLowerCase().replace(/[^a-z0-9]/g, "");
    const digits = compact.replace(/[a-z]/g, "").length;
    const mash = /asdf|sdfg|dfgh|fghj|ghjk|hjkl|qwer|wert|erty|rtyu|tyui|yuio|uiop|zxcv|xcvb|cvbn|vbnm|jkjk|fjfj/;
    const unsayable =
      !/[aeiouy]/.test(letters) || /[^aeiouy]{5,}/.test(letters) || (digits >= 2 && compact.length <= 8 && /[a-z]\d[a-z]/.test(compact));
    if (/([a-z])\1{3,}/.test(letters) && new Set(letters).size <= 2) {
      result.mood = "surprised";
      result.intense = true;
      result.source = "nonsense";
    } else if (mash.test(letters)) {
      result.mood = "dizzy";
      result.source = "nonsense";
    } else if (unsayable) {
      let mix = 0;
      for (let i = 0; i < compact.length; i += 1) mix += compact.charCodeAt(i) * (i + 1);
      const pick = (n) => {
        mix = Math.imul(mix ^ (mix >>> 7), 2654435761) >>> 0;
        return mix % n;
      };
      result.mutant = {
        eyes: [1, 2, 3, 1, 3, 2][pick(6)],
        googly: pick(3) === 0,
        stalks: pick(4) === 0,
        spots: pick(5),
        spotAt: pick(6),
        fangs: pick(3) === 0,
      };
      //: And its own limbs, or none: a mutant is the one character the
      //: letters alone may give wings.
      result.limbs = [null, "feet", "tentacles", "wings-bug", "wings-bat", null][pick(6)];
      if (result.limbs === "wings-bug") result.wing = ["fairy", "bee", "butterfly"][pick(3)];
      if (result.limbs === "wings-bat") result.wing = ["bat", "dragon"][pick(2)];
      result.source = "nonsense";
    }
  }

  //: **The budget** (the owner: "refine the avatar generation as it is
  //: still a little messy ... 'Sushicraft563', 'SushiLord'"). What the
  //: words asked to be seen is ranked by salience (a species first, then
  //: the things worn and held in the order the name says them, then food)
  //: and at most two are kept, one per slot: one head item, one face
  //: item, one held item, one body item (an outfit a word names, wings,
  //: feet, tentacles). A second claim on a full slot is dropped, except
  //: sushi, which goes in the hair as a clip when the hand is already
  //: full. So "Sushicraft563" holds a pickaxe with sushi in its hair,
  //: "SushiLord" wears a crown and holds sushi, and a handle that names
  //: five costumes wears two of them. Wings or tentacles that the species'
  //: own word brought ("Busy bee", "Kraken") are the species, not a cue.
  const species = heard.find((h) => h.kind === "animal") || null;
  const implied = (h) => species && (h.kind === "wing" || h.kind === "limbs") && h.order === species.order;
  const ranked = heard
    .filter((h) => !implied(h))
    .map((h) => ({ ...h, slot: nameMarkSlot(h.kind, h.key), rank: h.kind === "animal" ? 0 : h.kind === "hand" && NAME_MARK_FOODS.includes(h.key) ? 2 : 1 }))
    .sort((a, b) => a.rank - b.rank || a.order - b.order);
  const taken = {};
  const kept = [];
  for (const cue of ranked) {
    if (kept.length >= 2) break;
    if (taken[cue.slot]) {
      if (cue.key === "sushi" && !taken.head) {
        taken.head = { ...cue, kind: "prop", key: "sushiclip", slot: "head" };
        kept.push(taken.head);
      }
      continue;
    }
    taken[cue.slot] = cue;
    kept.push(cue);
  }
  result.animal = taken.species?.key || null;
  result.props = kept.filter((c) => c.kind === "prop").map((c) => c.key);
  result.hand = taken.held?.key || null;
  result.cues = kept.map((c) => c.key);
  if (!result.mutant) {
    const worn = (kind) => kept.find((c) => c.kind === kind)?.key || heard.find((h) => h.kind === kind && implied(h))?.key || null;
    result.wing = worn("wing");
    result.limbs = worn("limbs");
    const wingLimbs = { angel: "wings-feather", bird: "wings-feather", dragon: "wings-bat", bat: "wings-bat", fairy: "wings-bug", bee: "wings-bug", butterfly: "wings-bug" };
    if (result.wing && !result.limbs) result.limbs = wingLimbs[result.wing];
  }
  const wornOutfit = kept.find((c) => c.kind === "outfit")?.key || null;

  //: Some creatures come with a temperament when the name gives none.
  const temperament = {
    sloth: "sleepy", capybara: "calm", shark: "sly", snake: "sly", hedgehog: "nervous",
    goblin: "sly", troll: "angry", zombie: "sick", mummy: "sleepy", medusa: "evil", genie: "happy", gnome: "happy",
  };
  if (!result.mood && temperament[result.animal]) result.mood = temperament[result.animal];

  //: Layer four: the name's own hash picks a personality. FNV-1a, the same
  //: family `nameMark` uses, seeded differently so the two draws are
  //: independent of each other. Only friendly ones (the owner, on his own
  //: name: a plain name gets "a clean, appealing default character"): plain,
  //: happy, calm, a little excited or cute. Never sly, sleepy, nervous,
  //: lovestruck or in sunglasses, which read as a claim about a person that
  //: their name never made.
  if (!result.mood) {
    let h = (2166136261 ^ 0x9e3779b9 ^ Math.imul(variant, 0x27d4eb2d)) >>> 0;
    for (const ch of raw.toLowerCase()) {
      h ^= ch.codePointAt(0);
      h = Math.imul(h, 16777619) >>> 0;
    }
    h ^= h >>> 15;
    h = Math.imul(h, 2246822507) >>> 0;
    h ^= h >>> 13;
    const pool = [null, null, "happy", "happy", "calm", "calm", "excited", "cute"];
    result.mood = pool[(h >>> 0) % pool.length];
  }
  //: **The face's own style**, for every name: which smile, which small
  //: features (the owner: "there can be variations of types of smiles and
  //: other features as well"). A third hash of the name, so it is stable
  //: and independent of both the colours and the personality.
  let sh = (2166136261 ^ 0x85ebca6b ^ Math.imul(variant, 0x165667b1)) >>> 0;
  for (const ch of raw.toLowerCase()) {
    sh ^= ch.codePointAt(0);
    sh = Math.imul(sh, 16777619) >>> 0;
  }
  const roll = (n) => {
    sh ^= sh >>> 13;
    sh = Math.imul(sh, 3266489917) >>> 0;
    sh = (sh ^ (sh >>> 16)) >>> 0;
    return sh % n;
  };
  const smiles = ["smile", "grin", "toothy", "lopsided", "bigD", "cat3", "smile", "grin"];
  result.style.smile = smiles[roll(smiles.length)];
  //: One small feature at most: a beauty mark or a blush.
  const feature = [null, null, "blush", "mole", null, "blush"][roll(6)];
  if (feature) result.style.features.push(feature);
  result.style.nose = [null, null, "dot", "button"][roll(4)];
  result.style.eyes = ["dot", "dot", "oval", "anime", "button", "starry", "dot", "sparkle"][roll(8)];
  //: Hair (the owner: "some feminine ones definitely (a lot more ones), and
  //: masculine ones as well", then "they look a bit too mundane now"),
  //: always one style, and the presentation picks the set: bold cuts
  //: (an undercut, spikes, a mohawk, slicked back, a buzz with a line) for
  //: masculine, long, waves, curls and a messy fringe for feminine, and
  //: for Neutral the ones that read as either.
  const feminineHair = ["long", "waves", "bob", "bun", "ponytail", "longcurls", "curtains", "fringe", "wavy", "locs"];
  const masculineHair = ["crop", "sweep", "quiff", "messy", "undercut", "spiky", "mohawk", "slick", "buzzline", "curls", "locs"];
  const anyHair = ["crop", "sweep", "curtains", "messy", "curls", "wavy", "locs", "undercut", "fringe", "spiky"];
  const pool = result.look === "feminine" ? feminineHair : result.look === "masculine" ? masculineHair : anyHair;
  result.style.hair = pool[roll(pool.length)];
  //: Which of the skin's hair colours (`NM_CHAR_SKINS`), by index.
  result.style.hairColour = roll(12);
  if (result.look === "feminine") result.style.features.push("lashes");
  //: **Character** (the owner: "more character, less stock ... no two
  //: sample names should read the same"). Beside the hair, a face gets
  //: traits from the name's hash, each from its own family and each only
  //: where the budget has room: something on the head (a beanie, a cap,
  //: headphones, a hood), eyewear (round glasses, shades), a small accent
  //: (freckles, a scar through one brow, one earring, a plaster on the
  //: nose), attitude (a smirk, a raised brow) and, for a masculine face,
  //: facial hair (stubble, a short beard, a moustache). A name the words
  //: said nothing about gets two; a name whose words already dressed it
  //: gets one more at most, and never one that takes a slot.
  const families = [
    ["head", 0.45, ["beanie", "cap", "headphones", "hood"]],
    ["face", 0.5, ["glasses", "shades"]],
    ["accent", 0.8, ["freckles", "scar", "earring", "plaster"]],
    ["attitude", 0.85, ["smirk", "raisedbrow"]],
    ["facial", result.look === "masculine" ? 0.7 : 0, ["stubble", "shortbeard", "moustache"]],
  ];
  const drawn = families
    .map(([family, weight, kinds]) => ({ family, score: weight * (roll(1000) + 1), kind: kinds[roll(kinds.length)] }))
    .filter((t) => t.score > 0)
    .sort((a, b) => b.score - a.score);
  const traitRoom = kept.length ? 1 : 2;
  result.style.traits = [];
  for (const trait of drawn) {
    if (result.style.traits.length >= traitRoom) break;
    const slot = trait.family === "head" ? "head" : trait.family === "face" || trait.family === "facial" ? "face" : null;
    if (slot && (kept.length || taken[slot] || result.animal || result.mutant)) continue;
    if (slot) taken[slot] = { kind: "trait", key: trait.kind };
    if (trait.family === "head" || trait.family === "face") result.props.push(trait.kind);
    else if (trait.family === "facial") result.style.accessories.push(trait.kind);
    else if (trait.kind === "freckles" && !result.style.features.includes("freckles")) result.style.features.push("freckles");
    else if (trait.family === "accent" || trait.family === "attitude") result.style.features.push(trait.kind);
    result.style.traits.push(trait.kind);
  }
  //: Everyday clothes for everyone a word does not dress: a T-shirt, a
  //: hoodie, a shirt and tie, a blazer, a jumper, a scoop neck with a
  //: necklace. The pool leans the way the hair does.
  const feminineWear = ["scoop", "scoop", "tee", "sweater", "blazer", "hoodie"];
  const masculineWear = ["tee", "hoodie", "collar", "blazer", "sweater", "suit"];
  const anyWear = ["tee", "hoodie", "scoop", "collar", "sweater", "blazer", "tee", "hoodie"];
  const wear = result.look === "feminine" ? feminineWear : result.look === "masculine" ? masculineWear : anyWear;
  result.style.outfit = wornOutfit || wear[roll(wear.length)];
  //: Which of the colour pair's two cloth tones.
  result.style.outfitColour = roll(2);
  //: The person's own overrides, last, so they win over every reading.
  //: A key the drawing code does not know is ignored rather than drawn.
  //: The budget's one-per-slot still holds: a chosen hat replaces whatever
  //: else sat on the head, chosen eyewear whatever sat on the face.
  if (own) {
    const pick = (value, known) => (value === "none" ? "none" : known.includes(value) ? value : "");
    const mood = pick(own.mood, Object.keys(NAME_MOOD_LEXICON.moods).concat(["dizzy", "uwu", "laughing", "unimpressed"]));
    if (mood) result.mood = mood === "none" ? null : mood;
    const hair = pick(own.hair, NAME_MARK_HAIR_KINDS.concat(Object.keys(NAME_MARK_HAIR_ALIASES)));
    if (hair) result.style.hair = hair === "none" ? null : NAME_MARK_HAIR_ALIASES[hair] || hair;
    const skin = pick(own.skin, NAME_MARK_SKIN_KINDS);
    if (skin && skin !== "none") result.style.skin = skin;
    const tone = pick(own.hairtone, NAME_MARK_HAIR_TONE_KINDS);
    if (tone && tone !== "none") result.style.hairTone = tone;
    const outfit = pick(own.outfit, ["tee", "hoodie", "scoop", "collar", "sweater", "blazer", "suit", "dress"]);
    if (outfit) result.style.outfit = outfit === "none" ? null : outfit;
    for (const [key, kinds, slot] of [["hat", NAME_MARK_HAT_KINDS, NAME_MARK_HEAD_KINDS], ["eyewear", NAME_MARK_EYEWEAR_KINDS, NAME_MARK_FACE_KINDS]]) {
      const chosen = pick(own[key], kinds);
      if (!chosen) continue;
      result.props = result.props.filter((prop) => !slot.includes(prop));
      result.style.accessories = result.style.accessories.filter((one) => !slot.includes(one));
      if (chosen !== "none") result.props.push(chosen);
    }
    const hand = pick(own.hand, Object.keys(NAME_MOOD_LEXICON.hands));
    if (hand) result.hand = hand === "none" ? null : hand;
  }
  return result;
}

//: How each mood draws: eyes, brows, mouth, and the small things around a
//: face that carry the joke (a tear, a sweat drop, a "zz", a vein). An
//: intense reading swaps in the louder mouth and adds the louder extras.
const NAME_MARK_FACES = {
  happy: { eyes: "happy", mouth: "smile", loud: "grin", extras: ["blush"] },
  excited: { eyes: "sparkle", brows: "raised", mouth: "grin", extras: ["blush"], louder: ["spark"] },
  sad: { eyes: "glossy", brows: "sad", mouth: "frown", extras: ["tear"], louder: ["tear2"] },
  angry: { eyes: "narrow", brows: "angry", mouth: "frown", loud: "teeth", louder: ["vein"] },
  dramatic: { eyes: "wide", brows: "dramatic", mouth: "gasp", louder: ["tear", "spark"] },
  surprised: { eyes: "wide", brows: "raised", mouth: "o", louder: ["sweat"] },
  sleepy: { eyes: "closed", mouth: "yawn", extras: ["zz"] },
  nervous: { eyes: "dot", brows: "sad", mouth: "wavy", extras: ["sweat"], louder: ["sweat2"] },
  sly: { eyes: "narrow", brows: "sly", mouth: "smirk" },
  calm: { eyes: "content", mouth: "smile" },
  serious: { eyes: "dot", brows: "flat", mouth: "flat" },
  confused: { eyes: "mismatch", brows: "confused", mouth: "wavy", extras: ["question"] },
  hungry: { eyes: "sparkle", mouth: "yum", extras: ["blush"], loud: "tongue", louder: ["drool"] },
  cool: { eyes: "shades", mouth: "smirk" },
  love: { eyes: "heart", mouth: "smile", extras: ["blush"], louder: ["heart"] },
  laughing: { eyes: "squeeze", mouth: "grin", extras: ["tear", "tear2"], louder: ["spark"] },
  unimpressed: { eyes: "halflid", brows: "flat", mouth: "flat" },
  dizzy: { eyes: "spiral", mouth: "wavy", extras: ["stars"] },
  uwu: { eyes: "closed", mouth: "cat", extras: ["blush"], louder: ["heart"] },
  evil: { eyes: "evil", brows: "angry", mouth: "evil", extras: ["glint"], louder: ["glint2"] },
  sick: { eyes: "halflid", brows: "sad", mouth: "wavy", extras: ["greenblush", "thermometer"] },
  dead: { eyes: "x", mouth: "tongue" },
  starstruck: { eyes: "star", brows: "raised", mouth: "grin", extras: ["spark"] },
  cute: { eyes: "sparkle", mouth: "cat", extras: ["blush"], louder: ["heart"] },
  drunk: { eyes: "halflid", mouth: "smirk", extras: ["blush", "bubble"] },
  greedy: { eyes: "dollar", mouth: "grin", extras: ["spark"] },
};

//: **Each character's own way of wearing a mood** (round 7, INBOX 430,
//: the owner: "generated faces vary expression slightly per character").
//: Every face in one mood drew the same eyes, brows and mouth, so a room of
//: happy characters smiled one smile. Now, per mood, a few near neighbours
//: of each part, and each character favours one of them for good (its
//: seed and the mood choose, `nameMarkLean`): one is happy with a cat's
//: mouth and content eyes, another with a grin and sparkling ones. The
//: first of each list is the table's own; `null` keeps the face's own.
//: Only the parts listed vary; the extras (a tear, a "zz") stay the mood's.
const NAME_MARK_FACE_LEANS = {
  happy: { eyes: ["happy", "content", "sparkle"], mouth: ["smile", "cat", "grin"], brows: [null, null, "raised"] },
  excited: { eyes: ["sparkle", "star", "wide"], mouth: ["grin", "toothy"] },
  sad: { eyes: ["glossy", "halflid"], mouth: ["frown", "wavy"] },
  angry: { eyes: ["narrow", "halflid"], mouth: ["frown", "teeth", "flat"] },
  surprised: { eyes: ["wide", "round"], mouth: ["o", "gasp"], brows: ["raised", "dramatic"] },
  sleepy: { eyes: ["closed", "halflid"], mouth: ["yawn", "o"] },
  nervous: { eyes: ["dot", "wide"], mouth: ["wavy", "flat"], brows: ["sad", "raised"] },
  sly: { eyes: ["narrow", "halflid"], mouth: ["smirk", "lopsided"], brows: ["sly", "flat"] },
  calm: { eyes: ["content", "round", "happy"], mouth: ["smile", "cat"] },
  serious: { eyes: ["dot", "narrow"], brows: ["flat", "angry"] },
  confused: { mouth: ["wavy", "o", "lopsided"] },
  love: { eyes: ["heart", "happy"], mouth: ["smile", "cat"] },
  laughing: { eyes: ["squeeze", "happy"], mouth: ["grin", "toothy"] },
  unimpressed: { eyes: ["halflid", "dot"], mouth: ["flat", "smirk"] },
  cute: { eyes: ["sparkle", "happy"], mouth: ["cat", "smile"] },
};
//: The face for `mood` as the character with hash `lean` wears it: the
//: mood's own, with each listed part swapped for the one this character
//: favours. The pick mixes the name's hash with the mood's and the part's
//: names (FNV-1a), so a character's choices for one mood say nothing of
//: its choices for another, and the colour rolls are untouched.
function nameMarkLean(face, mood, lean) {
  const options = NAME_MARK_FACE_LEANS[mood];
  if (!options || !face) return face;
  const out = { ...face };
  for (const [part, list] of Object.entries(options)) {
    let h = lean >>> 0;
    for (const ch of `${mood}:${part}`) h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0;
    h ^= h >>> 15;
    h = Math.imul(h, 0x2c1b3c6d) >>> 0;
    h ^= h >>> 12;
    const pick = list[h % list.length];
    if (pick) out[part] = pick;
  }
  return out;
}

//: The creatures a name can ask for. `head` fixes the head's colour where
//: the animal has one (a panda is white, a fox is orange); the others keep
//: the name's own colour pair, so two cats still differ.
const NAME_MARK_CREATURES = {
  panda: { head: "#f5f4ef", ears: "round", ear: "#2b2a28", patches: "#2b2a28" },
  bear: { head: "#9c755f", ears: "round", muzzle: "#d9b38c" },
  koala: { head: "#a9aaa4", ears: "round", earSize: 4.6, inner: "#f3c6cf", nose: true },
  mouse: { head: "#b9b9b3", ears: "round", earSize: 5, inner: "#ff9da7" },
  monkey: { head: "#9c755f", ears: "side", muzzle: "#e8c9a4" },
  cat: { ears: "pointy", mouth: "cat", whiskers: true },
  fox: { head: "#f28e2c", ears: "pointy", mouth: "cat", muzzle: "#f5f4ef" },
  wolf: { head: "#8e9aa6", ears: "pointy", mouth: "cat", muzzle: "#dfe3e8" },
  tiger: { head: "#f28e2c", ears: "round", stripes: true, mouth: "cat", whiskers: true },
  lion: { head: "#edc949", mane: "#b0703a", ears: "round", mouth: "cat" },
  bunny: { ears: "long", inner: "#ff9da7", mouth: "cat" },
  dog: { head: "#d9b38c", ears: "floppy", ear: "#9c755f", nose: true },
  frog: { head: "#59a14f", eyesUp: true },
  pig: { head: "#ff9da7", ears: "pointy", snout: "#f07a8e" },
  owl: { head: "#9c755f", ears: "tufts", rings: "#f5f4ef", beak: "#f28e2c" },
  chick: { head: "#edc949", beak: "#f28e2c", tuft: true, limbs: "feet", foot: "#f28e2c" },
  penguin: { head: "#2b2a28", mask: "#f5f4ef", beak: "#f28e2c", limbs: "feet", foot: "#f28e2c" },
  ghost: { head: "#f5f4ef", shape: "ghost" },
  alien: { head: "#8cd17d", eyes: "alien", antenna: true },
  octopus: { head: "#af7aa1", limbs: "tentacles" },
  bird: { beak: "#f28e2c", tuft: true, wing: "bird", limbs: "wings-feather" },
  duck: { head: "#f5f4ef", bill: "#f28e2c", limbs: "feet", foot: "#f28e2c", tuft: true },
  hamster: { head: "#e8b27a", ears: "round", earSize: 3, inner: "#ff9da7", cheeks: "#f7dcc2" },
  sheep: { head: "#4a4441", wool: "#f5f4ef", ears: "side", ear: "#4a4441" },
  cow: { head: "#f5f4ef", spots: "#2b2a28", snout: "#ffb3c1", ears: "side", ear: "#f5f4ef", smallHorns: "#e8dcc0" },
  deer: { head: "#b0703a", ears: "pointy", antlers: "#6b4a2f", muzzle: "#e8c9a4", nose: true },
  unicorn: { head: "#f5f4ef", ears: "pointy", unihorn: true, mane: "rainbow" },
  dragon: { head: "#59a14f", smallHorns: "#e8dcc0", wing: "dragon", limbs: "wings-bat", nostrils: true },
  dino: { head: "#8cd17d", spikes: "#59a14f", nostrils: true },
  shark: { head: "#7a8fa6", fin: true, muzzle: "#f5f4ef", mouth: "evil" },
  snake: { head: "#59a14f", tongue: true, scales: true },
  axolotl: { head: "#ff9da7", gills: "#e8364f" },
  crab: { head: "#e15759", stalks: true, claws: true },
  raccoon: { head: "#8e9aa6", ears: "pointy", bandit: "#2b2a28", muzzle: "#f5f4ef" },
  hedgehog: { head: "#d9b38c", quills: "#6b4a2f", nose: true },
  sloth: { head: "#9c755f", patches: "#5a4030", muzzle: "#d9b38c" },
  capybara: { head: "#a0714f", ears: "round", earSize: 2.4, muzzle: "#8a5f40", nose: true },
  bee: { head: "#edc949", beeStripes: true, antennae: true, wing: "bee", limbs: "wings-bug" },
  mermaid: { human: true, hairFixed: "waves", hairTone: "#3fb8a8", shell: true, limbs: "tail" },
  elf: { human: true, sideEars: 1 },
  goblin: { head: "#8cd17d", sideEars: 1.6, nose: true },
  troll: { head: "#7fa06a", tusks: true, bigNose: true, sideEars: 0.8 },
  gnome: { human: true, gnomeHat: true, beard: "#f5f4ef", bigNose: true },
  genie: { head: "#59a9e8", topknot: "#2b2a28", earrings: true },
  mummy: { head: "#d8d0bc", bandages: true },
  zombie: { head: "#9bb58a", stitches: true },
  minotaur: { head: "#8a5a2b", bullHorns: true, noseRing: true, muzzle: "#b0703a" },
  medusa: { head: "#8cd17d", snakeHair: "#3f7f3a" },
  cyclops: { head: "#b3a0d6", oneEye: true },
  phoenix: { head: "#f28e2c", beak: "#edc949", flameCrest: true, wing: "phoenix", limbs: "wings-feather" },
  yeti: { head: "#f5f4ef", wool: "#e8eef5", mask: "#9fb8d0" },
  bat: { head: "#6b5b73", ears: "pointy", limbs: "wings-bat", wing: "bat", inner: "#ff9da7" },
};

//: Which colour pairs (`NM_CHAR_PAIRS`) each mood leans to, when the name
//: said the mood out loud (a seeded mood keeps the name's own pair):
//: grumpy is coral, gloomy is sky, sick is mint.
const NAME_MARK_MOOD_GROUNDS = {
  happy: [4, 0, 5], excited: [4, 5, 0], sad: [1, 7, 3], angry: [5], dramatic: [3, 6, 5],
  surprised: [4, 1, 7], sleepy: [3, 1], nervous: [2, 7, 4], sly: [3, 2], calm: [2, 7, 1],
  serious: [1, 3], confused: [7, 3, 2], hungry: [0, 4, 5], cool: [1, 7], love: [6, 5],
  laughing: [4, 0], unimpressed: [1, 3], dizzy: [7, 3, 6], uwu: [6, 3], evil: [3, 5],
  sick: [2], dead: [3, 1], starstruck: [4, 6], cute: [6, 0, 3], drunk: [5, 6], greedy: [4, 2],
};

//: A sentence for the tooltip: what the mark was read as, so the joke can be
//: found by hovering ("Very dramatic face", "Hungry panda").
const NAME_MARK_MOOD_WORDS = {
  angry: "grumpy", love: "smitten", sly: "sly", cool: "cool", drunk: "tipsy", greedy: "money-eyed",
};
const NAME_MARK_PROP_WORDS = {
  hat: "a wizard hat", chefhat: "a chef's hat", glasses: "glasses", eyepatch: "an eyepatch",
  crown: "a crown", halo: "a halo", horns: "horns", antenna: "an antenna",
  moustache: "a moustache", headphones: "headphones", fangs: "fangs", rednose: "a clown nose",
  cowboy: "a cowboy hat", partyhat: "a party hat", ninjamask: "a ninja mask", helmet: "a space helmet",
  sushiclip: "sushi in its hair", tricorn: "a pirate hat", tiara: "a tiara", monocle: "a monocle",
  shades: "shades", hood: "a hood", beanie: "a beanie", cap: "a cap",
};

const NAME_MARK_HAND_WORDS = {
  thumbsup: "giving a thumbs up", peace: "throwing a peace sign",
  wave: "waving", beer: "with a beer", wine: "with a glass of wine", mug: "with a hot drink",
  sword: "with a sword", magnifier: "with a magnifying glass", mic: "with a microphone",
  book: "with a book", phone: "on their phone", flower: "with a flower", pizza: "with pizza",
  donut: "with a donut", balloon: "with a balloon", tableflip: "flipping a table",
  controller: "with a controller", pickaxe: "with a pickaxe", axe: "with an axe", hammer: "with a hammer",
  blaster: "with a blaster", bow: "with a bow and arrow", wand: "with a wand", fishingrod: "with a fishing rod",
  paintbrush: "with a paintbrush", spear: "with a spear", trident: "with a trident", sushi: "with sushi",
};

function nameMarkTitle(reading) {
  if (!reading.mood && !reading.animal && !reading.props.length && !reading.mutant && !reading.flavours?.length && !reading.hand) return "";
  const mood = reading.mood ? NAME_MARK_MOOD_WORDS[reading.mood] || reading.mood : "";
  const mutant = reading.mutant;
  const creatureWord = mutant
    ? mutant.eyes === 1 ? "cyclops" : mutant.eyes === 3 ? "three-eyed critter" : "critter"
    : "face";
  const words = [reading.intense && mood ? "very" : "", mood, reading.animal || creatureWord].filter(Boolean);
  const props = reading.props.map((prop) => NAME_MARK_PROP_WORDS[prop]).filter(Boolean);
  const tail = props.length ? ` with ${props.join(" and ")}` : "";
  const doing = { wink: "winking", scream: "screaming", doomed: "sweating", blush: "blushing" };
  const flavours = (reading.flavours || []).map((flavour) => doing[flavour]).filter(Boolean);
  const also = flavours.length
    ? `, ${flavours.length > 1 ? `${flavours.slice(0, -1).join(", ")} and ${flavours.at(-1)}` : flavours[0]}`
    : "";
  const hand = reading.hand ? `, ${NAME_MARK_HAND_WORDS[reading.hand]}` : "";
  const text = `${words.join(" ")}${tail}${also}${hand}`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

//: **A mark generated from a name** (INBOX 405, then 409, then the owner's
//: "make the avatars, their generation and use very impressive ... funny
//: ... cute ... can they be animated as a togglable option"). The same name
//: always draws the same mark, with nothing stored: a hash of the name seeds
//: the geometry, and `nameMood` reads the name for what the face should be.
//:
//: The base is the "beam" idea from boring-avatars (the idea, not its code):
//: a rounded head in one colour set at an angle over a ground in another,
//: moved by the seed. Measured by `scratchpad/ui-sweeps/namemarks.js` (23
//: everyday names at 40px): the closest pair differs in 19.1% of pixels and
//: the mean pair in 71.9% (the floor is 15%). On top of it
//: sit the reading's face (nineteen moods, each with its own eyes, brows,
//: mouth and extras), a creature when the name names one (nineteen, from
//: ears and patches to a ghost's hem), a costume when it names one (ten),
//: flavours stacked on top (a wink, a scream, a sweat), and for a name that
//: makes no sense, a mutant with one, two or three eyes.
//:
//: Motion is CSS only, keyed off classes set here: the eyes blink, the face
//: breathes, and each mood has its own move (the tear falls, the "zz"
//: drifts, the vein throbs, an excited face bounces). Settings > Appearance >
//: Avatar animation chooses off, on hover, or always; Reduce motion wins.
//: Each mark starts its loop at its own point (`--nm-delay`, from the seed),
//: so a list of faces does not blink in unison.
//:
//: Colours are one of `NM_CHAR_PAIRS` (body, hair and cloth chosen to sit
//: together), or a creature's fixed coat. The features are ink or white by the head's own luminance, so
//: a face never vanishes into a light head. Decorative (`aria-hidden`): the
//: name beside it is what a screen reader says; the `<title>` is for a
//: pointer's tooltip.
let nameMarkSerial = 0;

//: **Only faces on screen move.** In "Always" mode a long persona list or
//: chat would otherwise animate every face in it, seen or not (the owner:
//: "make sure all the avatar ... animations and rendering are very light
//: weight"). One shared observer marks the visible ones, and the CSS only
//: animates a marked face. Hover mode needs none of this: a hovered face is
//: on screen by definition.
let nameMarkObserver = null;
//: The same faces as `[data-nm-on]`, kept as a set so the pointer-follow
//: frame below reads them without a document-wide `querySelectorAll` per
//: frame (INBOX 424: that query was the largest cost of a graph drag).
const nameMarkOnScreen = new Set();
function watchNameMark(svg) {
  //: Faces under 28px (a chat bubble's corner mark, a picker's glyph) are
  //: never watched: no always-on loop, no pointer-follow. At that size the
  //: motion is noise and a long chat has hundreds of them (the owner: "i
  //: dont think the really small faces on the message bubble corners should
  //: move even if it is selected as that might be too heavy"). Hover still
  //: wakes one.
  if ((Number(svg.dataset.nmSize || svg.getAttribute("width")) || 0) < 28) return;
  if (typeof IntersectionObserver !== "function") {
    svg.dataset.nmOn = "";
    nameMarkOnScreen.add(svg);
    nameMarkKeyboard(svg);
    return;
  }
  if (!nameMarkObserver) {
    nameMarkObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) nameMarkOnScreen.add(entry.target);
        else nameMarkOnScreen.delete(entry.target);
        if (entry.isIntersecting) entry.target.dataset.nmOn = "";
        if (entry.isIntersecting) nameMarkKeyboard(entry.target);
        if (entry.isIntersecting && (Number(entry.target.dataset.nmSize || entry.target.getAttribute("width")) || 0) >= NM_IDLE_MIN) nameMarkIdleWake();
        else delete entry.target.dataset.nmOn;
        if (!entry.target.isConnected) nameMarkObserver.unobserve(entry.target);
      }
    });
  }
  nameMarkObserver.observe(svg);
}

//: **A face you can reach from the keyboard** (INBOX 425 h): one that is not
//: inside a control takes a tab stop and says what Enter does; one inside a
//: control (the Settings head button) stays the control's decoration.
function nameMarkKeyboard(face) {
  if (face.dataset.nmKb) return;
  face.dataset.nmKb = "1";
  if (!face.isConnected || face.closest("button, a, [role='button'], label, select, summary, #nm-buddy, .nm-viewer")) return;
  face.tabIndex = 0;
  face.setAttribute("role", "button");
  face.removeAttribute("aria-hidden");
  face.setAttribute("aria-label", `${face.dataset.nmSeed || "Atlas"}: open the large view`);
}

//: **Atlas's own face** lives in atlas.js, loaded straight after this file:
//: a character designed for it (`atlasDraw`), registered through
//: `registerCharacter` below, with its moods (`setAtlasMood`,
//: `atlasRestingMood`) beside it. This name stays for the callers that ask
//: for Atlas directly (the welcome, `nameMark`'s fallback).
function atlasMark(size = 20, mood) {
  return atlasDraw(size, mood);
}

// --- the character interface -----------------------------------------------------
//: **One way in to every face** (INBOX 425; so a renderer can be swapped
//: without touching a call site). `characterFor(seed)` answers a
//: *character*:
//:
//:   {
//:     kind:    "atlas" | "generated" | a registered renderer's own name,
//:     seed:    the name it was drawn for,
//:     mark(size):   an <svg class="name-mark"> head-only mark, for lists,
//:                   chat bubbles, pickers and heads (any size; under 40px
//:                   it is always head-only, and under 28px it never moves,
//:                   see `watchNameMark`),
//:     figure():     the full character for the companion and the large
//:                   view: an element laid out in a 64 by 92 px box (the
//:                   companion's own; the viewer scales it), whose parts
//:                   carry the classes below so the companion's behaviours
//:                   can act them out,
//:     poses:   the poses it can take (see below),
//:     moods:   the moods it can show (Atlas: calm, thinking, happy,
//:              surprised, sleepy; a generated face: its reading's mood),
//:   }
//:
//: **The parts a figure must carry**, all transform/opacity only:
//:   `.nm-buddy-head` (holding the head's `.name-mark`, whose `.nm-eyes`
//:   are moved by `--nm-lx`/`--nm-ly` and whose `.nm-blinks` close),
//:   `.nmb-torso`, `.nmb-arm-l`/`.nmb-arm-r` (resting arms, turning at the
//:   shoulder), `.nmb-hold` (both arms raised, for hanging, stretching and
//:   cheering; `.nmb-hold-l`/`.nmb-hold-r` each), `.nmb-leg-l`/`.nmb-leg-r`
//:   (turning at the hip). Geometry, in the 64 by 92 box: the head's top at
//:   0, the seat at 72 (`NMB_SEAT`), the soles at 90 (`NMB_FEET`), the
//:   raised hands at 5 once dropped by `NMB_DROP` (12) when hanging.
//:
//: **What the companion sets on its `#nm-buddy`**, for a figure's CSS:
//:   `data-pose`  stand | sit | hang | float | lean
//:   `data-legs`  "" | tuck (sitting where dangling legs would cover content)
//:   `data-turn`  "" | l | r (a three-quarter turn)
//:   classes      `nmb-act-<name>` for the behaviour running (blink, look,
//:                turn, glance, stretch, yawn, nap, hop, wave, scratch,
//:                dangle, kick, peek, swing, sloth, onehand, feet, emerge,
//:                cheer, startle, land), and the states `nmb-walking`,
//:                `nm-buddy-dragging`, `nmb-think`, `nmb-watch`,
//:                `nmb-sleep`, `nmb-duck`.
//:
//: **Prop slots**, each a group of class `nmp nmp-<name>` the figure draws
//: hidden (the CSS shows it while the class in brackets is on `#nm-buddy`):
//:   head-top  `nmp-headphones` (`nmb-music`), `nmp-nightcap` (`nmb-night`)
//:   face      `nmp-glasses` (`nmb-reading`), inside `.nm-buddy-head`
//:   hand-r    `nmp-note` (`nmb-act-carry`, a saved note),
//:             `nmp-bell` (`nmb-act-bell`), `nmp-lantern` (`nmb-act-lantern`,
//:             with an `nmp-lantern-glow`), inside `.nmb-arm-r`
//:   hand-l    `nmp-cable` (`nmb-offline`), inside `.nmb-arm-l`
//: Other states a figure can answer: `nmb-drowsy`, `nmb-nod` (with
//: `nmb-watch`), `nmb-act-wake`.
//:
//: A renderer registers with `registerCharacter({ name, matches(seed),
//: make(seed) })`; the latest registered that matches wins, and the built-in
//: two (Atlas, then the generated faces) answer everything else.
const CHARACTER_RENDERERS = [];

function registerCharacter(renderer) {
  if (renderer && typeof renderer.matches === "function" && typeof renderer.make === "function") {
    CHARACTER_RENDERERS.unshift(renderer);
  }
}

function characterRendererFor(seed) {
  for (const renderer of CHARACTER_RENDERERS) {
    try {
      if (renderer.matches(seed)) return renderer;
    } catch (e) {
      // A renderer that throws on a name gives it back to the built-in ones.
    }
  }
  return null;
}

function isAtlasSeed(seed) {
  const named = String(seed || "").trim().toLowerCase();
  const ai = typeof aiNameNow === "function" ? String(aiNameNow() || "").toLowerCase() : "atlas";
  return Boolean(named) && (named === ai || named === "atlas");
}

function characterFor(seed) {
  const own = characterRendererFor(seed);
  if (own) return own.make(seed);
  const atlas = isAtlasSeed(seed);
  return {
    kind: atlas ? "atlas" : "generated",
    seed,
    mark: (size) => nameMark(seed, size),
    figure: () => (atlas ? nameMarkFigure(seed) : nameCharacterFigure(seed)),
    poses: ["stand", "sit", "hang", "float", "lean"],
    moods: atlas ? ["calm", "thinking", "happy", "surprised", "sleepy"] : [nameMood(seed).mood || "plain"],
  };
}

// --- faces drawn once, moved on the compositor ------------------------------------
//: **Why every face is a few cached pictures, not a live SVG** (the owner:
//: "can caching be used to reduce the load of companion, bg, and other
//: animations??"). An SVG group that animates is restyled, laid out and
//: repainted on the main thread every frame: measured, the companion at
//: rest cost 106 layouts and 107 style recalcs a minute. So a face is drawn
//: once as SVG, cut into its moving parts, and each part (and each run of
//: still drawing between them, so the paint order holds) becomes a small
//: image in an HTML element that carries the part's own class. The CSS that
//: moved the SVG groups moves those elements instead, with transform and
//: opacity only, which the compositor runs without the main thread.
//:
//: - `nameMarkCompose(key, build, options)` keeps one cut-up template per
//:   key in `nameMarkFaceCache` (the least recently used goes past 160) and
//:   hands back a clone. The key names everything the drawing depends on
//:   (the name, your own style, the accent, Atlas's mood), so a new theme,
//:   accent or character simply asks for a new key; nothing runs on a timer.
//: - The pictures are vector (`data:` SVG), so one template serves every
//:   size; positions are percentages of the part they sit in.
//: - A part's pivot (`data-pivot="x y"` in drawing units, for a hip or a
//:   shoulder) becomes its `transform-origin`; every other part turns about
//:   its own middle, as `transform-box: fill-box` made it do in the SVG.
//: - An expression is part of the key, so a change of mood swaps pictures
//:   rather than attributes; a blink is a squash of the eyes' picture.
const NM_MARK_PARTS = [
  ".nm-body", ".nm-eyes", ".nm-blinks", ".nm-tear", ".nm-sweat", ".nm-z", ".nm-spark", ".nm-vein", ".nm-heart",
  ".nm-q", ".nm-bulb", ".nm-halo", ".nm-steam", ".nm-table", ".nm-balloon", ".nm-bow", ".nm-pompom", ".nm-gem",
  ".nm-wave", ".nm-wing", ".nm-tentacle", ".nm-foot", ".nm-flame", ".nm-tail", ".nm-tails", ".nm-starfield",
  ".nm-aura", ".nm-earring",
].join(", ");
const NM_FIGURE_PARTS = `${NM_MARK_PARTS}, .nmb-leg, .nmb-arm, .nmb-hold, .nm-buddy-head, .nmp, .nmp-lantern-glow, .nmc-shadow, .nmc-hair-crown, .nm-eyewear, .nmc-lids`;
//: Where a covering hat's brim meets the head, in drawing units: the hair
//: above it is under the hat (K25). The nightcap's is the line along its
//: band, a little under the band's middle so the band covers the seam.
const NM_HAT_BRIM = { beanie: 14, cap: 11, cowboy: 11, hat: 10, gnome: 11, chefhat: 8, tricorn: 7 };
const NM_NIGHTCAP_BRIM = "M-40 17 L8 17 L20 12 L32 10.5 L46 11 L58 15 L104 15";
const NM_FACE_CACHE_CAP = 160;
const nameMarkFaceCache = new Map();
let nameMarkMeasureHost = null;

function nameMarkCompose(key, build, { parts = "", pad = 0, size = 20, height = 0 } = {}) {
  let template = nameMarkFaceCache.get(key);
  if (template) {
    nameMarkFaceCache.delete(key);
  } else {
    template = nameMarkRasterise(build(), parts, pad);
    if (nameMarkFaceCache.size >= NM_FACE_CACHE_CAP) nameMarkFaceCache.delete(nameMarkFaceCache.keys().next().value);
  }
  nameMarkFaceCache.set(key, template);
  const face = template.cloneNode(true);
  face.style.width = `${size}px`;
  face.style.height = `${height || size}px`;
  face.dataset.nmSize = String(size);
  return face;
}

//: Cuts a drawn SVG into its parts (see above). The SVG is laid out once,
//: out of sight, to measure where each part is; everything after that is
//: string work.
function nameMarkRasterise(svg, parts, pad) {
  if (!nameMarkMeasureHost) {
    nameMarkMeasureHost = document.createElement("div");
    nameMarkMeasureHost.className = "nm-measure";
    nameMarkMeasureHost.setAttribute("aria-hidden", "true");
    document.body.appendChild(nameMarkMeasureHost);
  }
  nameMarkMeasureHost.appendChild(svg);
  const [vx, vy, vw, vh] = (svg.getAttribute("viewBox") || "0 0 36 36").split(/[\s,]+/).map(Number);
  const frame = svg.getBoundingClientRect();
  const unit = vw / (frame.width || vw);
  //: Document order, and where each element's subtree ends in it.
  const all = [];
  const end = [];
  const walk = (el) => {
    const at = all.length;
    all.push(el);
    end.push(at);
    for (const child of el.children) walk(child);
    end[at] = all.length - 1;
  };
  walk(svg);
  const order = new Map(all.map((el, i) => [el, i]));
  const isDef = (el) => Boolean(el.closest("defs, clipPath, linearGradient, radialGradient, mask, filter, pattern, symbol, title"));
  const drawable = (i) => all[i].children.length === 0 && !isDef(all[i]) && all[i] !== svg;
  const nodes = [{ el: svg, i: 0, parent: -1, box: { x: vx - pad, y: vy - pad, w: vw + pad * 2, h: vh + pad * 2 }, frame: { x: vx, y: vy, w: vw, h: vh } }];
  const nodeOf = new Map([[svg, 0]]);
  if (parts) {
    for (const el of svg.querySelectorAll(parts)) {
      const r = el.getBoundingClientRect();
      if (!r.width && !r.height) continue;
      let up = el.parentElement;
      while (up && !nodeOf.has(up)) up = up.parentElement;
      //: A box measured round a shape's geometry, not its outline: a limb is
      //: a path drawn with a stroke up to about 10 units wide, whose outer
      //: half lies outside it. Framed on the bare box, the arms came out cut
      //: flat along their outer sides (INBOX 426 k); 7 units takes the
      //: widest outline.
      const grow = 7;
      const box = { x: vx + (r.left - frame.left) * unit - grow, y: vy + (r.top - frame.top) * unit - grow, w: r.width * unit + grow * 2, h: r.height * unit + grow * 2 };
      nodeOf.set(el, nodes.length);
      nodes.push({ el, i: order.get(el), parent: nodeOf.get(up) ?? 0, box, frame: box });
    }
  }
  //: One picture of the ordinals [from, to] of the drawing, framed on `box`.
  const serializer = new XMLSerializer();
  const picture = (from, to, box) => {
    let any = false;
    for (let i = from; i <= to && !any; i += 1) any = drawable(i);
    if (!any) return "";
    const copy = svg.cloneNode(true);
    const copies = [];
    const collect = (el) => {
      copies.push(el);
      for (const child of el.children) collect(child);
    };
    collect(copy);
    for (let i = copies.length - 1; i > 0; i -= 1) {
      const el = copies[i];
      if (el.tagName === "title") {
        el.remove();
        continue;
      }
      if (isDef(all[i])) continue;
      if (end[i] < from || i > to) el.remove();
    }
    for (const name of ["class", "style", "width", "height", "aria-hidden", "focusable", "overflow"]) copy.removeAttribute(name);
    copy.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
    copy.setAttribute("preserveAspectRatio", "none");
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(serializer.serializeToString(copy))}`;
  };
  const pct = (v) => `${(v * 100).toFixed(3)}%`;
  const place = (el, box, within) => {
    el.style.left = pct((box.x - within.x) / within.w);
    el.style.top = pct((box.y - within.y) / within.h);
    el.style.width = pct(box.w / within.w);
    el.style.height = pct(box.h / within.h);
  };
  const image = (url, box, within) => {
    const img = document.createElement("img");
    img.alt = "";
    img.draggable = false;
    img.decoding = "sync";
    img.src = url;
    place(img, box, within);
    return img;
  };
  const elements = nodes.map((node, n) => {
    if (n === 0) {
      const top = document.createElement("span");
      top.className = `${svg.getAttribute("class") || ""} nm-cached`;
      top.setAttribute("aria-hidden", "true");
      const title = svg.querySelector("title")?.textContent;
      if (title) top.title = title;
      for (const [k, v] of Object.entries(svg.dataset)) top.dataset[k] = v;
      const delay = svg.style.getPropertyValue("--nm-delay");
      if (delay) top.style.setProperty("--nm-delay", delay);
      return top;
    }
    const span = document.createElement("span");
    span.className = `${node.el.getAttribute("class") || ""} nmk`;
    place(span, node.box, nodes[node.parent].frame);
    const pivot = (node.el.getAttribute("data-pivot") || "").split(/\s+/).map(Number);
    if (pivot.length === 2 && pivot.every(Number.isFinite)) {
      span.style.transformOrigin = `${pct((pivot[0] - node.box.x) / node.box.w)} ${pct((pivot[1] - node.box.y) / node.box.h)}`;
    }
    return span;
  });
  //: Each element: its own drawing in runs, with its parts between them in
  //: the order the SVG painted them.
  nodes.forEach((node, n) => {
    const kids = nodes.map((k, m) => [k, m]).filter(([k]) => k.parent === n && k !== node).sort((a, b) => a[0].i - b[0].i);
    //: From the part itself: a part may be one shape (a star, a drop).
    let from = node.i;
    const own = node.box;
    const within = node.frame;
    for (const [kid, m] of kids) {
      const url = picture(from, kid.i - 1, own);
      if (url) elements[n].appendChild(image(url, own, within));
      elements[n].appendChild(elements[m]);
      from = end[kid.i] + 1;
    }
    const url = picture(from, end[node.i], own);
    if (url) elements[n].appendChild(image(url, own, within));
  });
  svg.remove();
  return elements[0];
}

function nameMark(seed, size = 20) {
  //: A registered renderer (a character drawn by hand) answers first.
  const own = characterRendererFor(seed);
  if (own) return own.make(seed).mark(size);
  //: The assistant's own name draws Atlas, not a face made from the name.
  const named = String(seed || "").trim().toLowerCase();
  const ai = typeof aiNameNow === "function" ? String(aiNameNow() || "").toLowerCase() : "atlas";
  if (named && (named === ai || named === "atlas")) return atlasMark(size);
  //: Under 28px a face never moves, so it is one picture; above, its parts.
  const moving = size >= 28;
  //: 28px and under is the small mark: the face and one cue (drawCharacter).
  const mini = size <= 28;
  const style = JSON.stringify(nameMarkOwnFor(seed) || {});
  const face = nameMarkCompose(`gen|${moving ? "p" : "f"}${mini ? "m" : ""}|${seed}|${style}|${nameMarkLookLean() || ""}`, () => drawCharacter(seed, 100, mini ? "mini" : "mark"), { parts: moving ? NM_MARK_PARTS : "", size });
  watchNameMark(face);
  return face;
}

// --- the generated characters ------------------------------------------------------
//: **One character, not a disc with a body stuck under it** (INBOX 425; the
//: owner: "get rid of the whole avatar circle with a body attached look, it
//: looks off and ai feel like they could be designed and generated a lot
//: better and more naturally"). Every generated face is now one small
//: mascot drawn as one silhouette: a soft bean whose head (about 58% of its
//: height) flows through a slight neck into the body, stubby limbs that
//: grow out from behind it with rounded ends, one linear gradient for its
//: shading, one outline (the body colour at half its lightness, 1.6 units,
//: the same on every part) and a flat contact shadow. The features sit on
//: that shape: eyes with whites and catchlights (readable on any body
//: colour), a mouth for the mood, brows, blush. The reading from `nameMood`
//: maps onto it: its colour, a species' own silhouette cues (ears break
//: the outline, a muzzle, a beak, a tail, wings, tentacles, a ghost's hem),
//: hair and clothes for people, the props on the head and the thing in its
//: hand.
//:
//: Drawn in the companion's 64 by 92 box (`NMB_*` below), so the figure
//: and the head-only mark are the same drawing: `mode` "figure" draws
//: everything; "mark" leaves out the legs, arms, hand and shadow and crops
//: the view to the head, which is what every list, bubble and picker shows;
//: "mini" is that mark at 28px and under (see `mini` in `drawCharacter`).
//:
//: **Colour** (the owner: "no muddy or clashing combinations", then "I
//: want a better aesthetic"). Nothing is rolled one colour at a time:
//:
//: - A person has a natural skin tone (`NM_CHAR_SKINS`, seven, from
//:   porcelain to deep, picked by the name's hash like everything else and
//:   never read from the name) and a hair colour from a natural palette
//:   (`NM_CHAR_HAIR_TONES`) tuned to that skin: each skin lists only the
//:   tones that read against it (1.8:1 or more), so fair skin takes black,
//:   brown, chestnut, auburn, copper or honey, deep skin black, copper,
//:   blond or platinum.
//: - Clothes, hats and a creature's coat come from one of twelve pairs
//:   (`NM_CHAR_PAIRS`): a soft gel body, in the family of Atlas's, for a
//:   creature that has no coat of its own, and two cloth tones that sit
//:   with it.
//:
//: `tests/test_name_mood.py` checks them all: a coat or its outline at 3:1
//: on the light page and the dark one, a skin at 2:1 on both, every hair
//: tone against its skin, the cloth apart from the coat. The first way
//: (the app's ten category colours for a body, ten hair colours and ten
//: cloth colours, each rolled on its own) gave a blue face with orange hair
//: and a grey top.
const NM_CHAR_PAIRS = [
  { name: "peach", body: "#f6b89a", cloth: ["#2f8582", "#5569c0"] },
  { name: "sky", body: "#8fc9f2", cloth: ["#f2b547", "#e5705f"] },
  { name: "mint", body: "#96dbbb", cloth: ["#e8747c", "#7a64c8"] },
  { name: "lilac", body: "#c3aef0", cloth: ["#f39b73", "#8c6d1f"] },
  { name: "butter", body: "#f6d87e", cloth: ["#4f7fd9", "#b5532e"] },
  { name: "coral", body: "#f7a397", cloth: ["#3b6fb6", "#2f9e75"] },
  { name: "rose", body: "#f5afcc", cloth: ["#3fa37e", "#5569c0"] },
  { name: "aqua", body: "#86d6d2", cloth: ["#ef8a5b", "#e8747c"] },
  { name: "apricot", body: "#f9c38c", cloth: ["#3f6fb5", "#8a5cc2"] },
  { name: "periwinkle", body: "#a8b6f4", cloth: ["#f2b547", "#2f9e75"] },
  { name: "pistachio", body: "#bfe08f", cloth: ["#e5705f", "#5569c0"] },
  { name: "sand", body: "#e9c9a6", cloth: ["#6b7f2a", "#c9577a"] },
];
const NM_CHAR_SKINS = [
  { name: "porcelain", skin: "#fde4d4", hair: ["black", "espresso", "brown", "chestnut", "auburn", "copper", "honey"] },
  { name: "fair", skin: "#f8d0b4", hair: ["black", "espresso", "brown", "chestnut", "auburn", "copper", "honey"] },
  { name: "peach", skin: "#f1bf9a", hair: ["black", "espresso", "brown", "chestnut", "auburn", "copper"] },
  { name: "tan", skin: "#dca27a", hair: ["black", "espresso", "brown", "chestnut", "auburn"] },
  { name: "olive", skin: "#c28c62", hair: ["black", "espresso", "brown", "chestnut", "auburn"] },
  { name: "brown", skin: "#9c6645", hair: ["black", "espresso", "blond", "platinum"] },
  { name: "deep", skin: "#77482f", hair: ["black", "black", "copper", "blond", "platinum"] },
];
const NM_CHAR_HAIR_TONES = {
  black: "#26222b", espresso: "#3d2b25", brown: "#6a432e", chestnut: "#8d4e2b", auburn: "#a8472a",
  copper: "#c56d36", honey: "#c7963f", blond: "#dcb25e", platinum: "#ecdcb4",
};

//: **Hair** (the owner, 2026-09-24: "I still dont like my hair for
//: 'Brayden' and I want a better aesthetic"). Each style is drawn by hand
//: as its own shape, never a cap laid on the head: it stands a little off
//: the skull for volume, has a parting or a fringe that goes one way, a
//: hairline that frames the forehead and temples, sideburns where the style
//: has them, and a back layer behind the head for anything longer than a
//: crop. Coordinates are the character's own (the head's crown at 32,4,
//: its widest at y 29, the brows at 21.5, the eyes at 30 about x 22 and
//: 42), and no fringe comes below 21 between x 17 and 47.
//:
//: - `front`: the hair over the head. Its copy two units lower, in the
//:   skin's shade and clipped to the head, is the shadow the fringe casts.
//: - `back`: behind the head and body, in the tone's shade (the nape).
//: - `part`: the parting, a line in the shade.
//: - `strands`: a few strokes of texture in the shade (left out at 28px).
//: - `shine`: the one highlight sweep, in the tone lifted towards white.
//: - `curls`, `backCurls`, `locs`, `bun`, `tail`: the parts a style adds;
//:   `sides` is a shaved layer under the top (an undercut, a mohawk),
//:   `shaved` draws the whole style as close-cropped, `line` is a line
//:   clipped into it, and `tall` marks a style that rises off the crop.
//:
//: Every style must look right on its own; the name only picks among them.
const NM_HAIR_STYLES = {
  crop: {
    front: "M5 31 C3 24 3 17 6 12 C9 5 18 0 30 -1 C44 -2 56 4 59 13 C61 19 61 25 59 31 L56.5 31 C56 26 54.5 22 52 19.5 Q50 21 48 18 Q45 20.5 42 17.5 Q39 20 36 17 Q33 19.5 30 16.5 Q27 19 24 16.5 Q21 19 18 17 Q15 19.5 12.5 19.5 C9.5 22 8 26 7.5 31 Z",
    strands: ["M16 12 Q18 8 22 6", "M26 10 Q28 5 33 3", "M38 11 Q41 6 46 5", "M47 13 Q51 10 54 11"],
    shine: "M11 11 Q16 4 24 2",
  },
  sweep: {
    front: "M5 32 C2 22 4 11 12 5 C20 -1 34 -3 45 0 C55 3 61 12 60 22 C60 26 59.5 29 59 32 L56.5 32 C56 27 55 23 52.5 20.5 C47 20.5 40 19 33 16 C28 13.5 25 11.5 23 9 C21 13 17 16.5 12.5 19 C9.5 21.5 8 26 7.5 32 Z",
    part: "M23 9 C22 5 21 2 20 0",
    strands: ["M25 7 C33 11 42 15 51 18", "M28 3 C37 6 46 10 56 15", "M18 6 C15 9 12 13 9 17"],
    shine: "M31 4 C39 6 46 9 52 13",
  },
  quiff: {
    front: "M5 31 C3 24 3 16 7 11 C10 5 15 1 22 -1 C28 -6 40 -8 49 -4 C56 -1 60 6 59 13 C61 19 61 25 59 31 L56.5 31 C56 25 54.5 21 52 18.5 C50 15 47 12.5 43 12 C38 11.5 33 13 28 12 C23 11.5 18 13.5 14 17 C10.5 20 8.5 25 7.5 31 Z",
    strands: ["M16 10 C22 2 32 -3 44 -5", "M20 12 C27 6 36 3 48 1", "M27 12 C33 8 42 7 53 9"],
    shine: "M22 1 C28 -3 36 -5 44 -5",
  },
  curtains: {
    front: "M4 36 C1 24 3 12 11 5 C18 -1 26 -2 32 -2 C38 -2 46 -1 53 5 C61 12 63 24 60 36 L56.5 36 C56.5 29 55 24.5 51.5 21.5 C45 19 38 15 33 7 L31 7 C26 15 19 19 12.5 21.5 C9 24.5 7.5 29 7.5 36 Z",
    part: "M32 -1 L32 7",
    strands: ["M30 5 C26 12 19 17 11 22", "M34 5 C38 12 45 17 53 22", "M28 1 C22 5 16 10 10 16", "M36 1 C42 5 48 10 54 16"],
    shine: "M12 12 Q17 5 25 2",
  },
  messy: {
    front: "M5 31 C3 24 3 17 6 12 Q5 5 11 5 Q12 -2 19 1 Q22 -5 28 -1 Q33 -6 38 -1 Q44 -5 47 1 Q54 -1 54 6 Q60 9 59 16 C61 21 60 27 59 31 L56.5 31 C56 26 55 22 52 20 Q51 23 47.5 21 Q46 17.5 43 19 Q40 21.5 37 18.5 Q34 21 31 18 Q28 20.5 24.5 18.5 Q22 17 19 19.5 Q16 21.5 13 20.5 C9.5 22.5 8 26 7.5 31 Z",
    strands: ["M14 9 Q18 12 20 16", "M26 4 Q28 9 27 14", "M36 3 Q38 9 41 13", "M46 6 Q48 11 51 14"],
    shine: "M12 10 Q16 4 23 3",
  },
  curls: {
    front: "M5 30 C3 16 14 3 32 3 C50 3 61 16 59 30 L56.5 30 C55 24 52 20 48 19 L16 19 C12 20 9 24 7.5 30 Z",
    curls: [[8, 24, 4.6], [8.5, 15.5, 5.4], [14.5, 8, 6], [23, 3.5, 6], [32, 2, 6.2], [41, 3.5, 6], [49.5, 8, 6], [55.5, 15.5, 5.4], [56, 24, 4.6], [15, 15.5, 4.2], [23, 14, 4.2], [31.5, 13.5, 4.2], [40, 14, 4.2], [48, 15.5, 4.2]],
    shine: "M11 10 Q15 4 21 1",
  },
  wavy: {
    back: "M3 30 C1 13 14 0 32 0 C50 0 63 13 61 30 C60 35 63 39 61 44 C62 48 58 50 55 48 C53 50 49 49 49 46 L15 46 C15 49 11 50 9 48 C6 50 2 48 3 44 C1 39 4 35 3 30 Z",
    front: "M3 40 C0 24 4 10 13 4 C21 -1 34 -3 45 0 C55 3 62 13 61 24 C60.5 30 61.5 35 60 40 L56.5 40 C57.5 34 55.5 29 54 25 C52 22 50 20.5 47 20.5 C40 19.5 32 15.5 25 9 C22 14 17 18 12.5 21 C9 24 7 29 8 34 C8.5 36.5 7.5 38.5 7 40 Z",
    part: "M25 9 C24 5 23 2 22 0",
    strands: ["M26 6 C34 11 42 15 50 18", "M29 2 C38 6 47 11 56 17", "M9 22 C7 28 9 33 7 38", "M57 24 C59 29 57 34 59 38"],
    shine: "M31 4 C39 6 46 9 52 13",
  },
  long: {
    back: "M3 30 C2 10 16 -1 32 -1 C48 -1 62 10 61 30 L62 64 C57 66 53 65 51 62 L13 62 C11 65 7 66 2 64 Z",
    front: "M3 46 C0 26 3 11 12 4 C19 -1 27 -2 33 -2 C42 -2 52 2 57 9 C63 18 63 30 61 46 L57 46 L56.5 30 C55.5 25 53 21.5 49 19.5 C42 17.5 37 13 34 7 C30 13 23 17.5 16 19.5 C11 21 8.5 25 8 30 L7.5 46 Z",
    part: "M34 -1 L34 7",
    strands: ["M9 26 L8.5 44", "M56 26 L56.5 44", "M33 3 C29 10 22 15 14 18", "M35 3 C39 10 45 15 52 18"],
    shine: "M12 12 Q17 4 26 1",
  },
  waves: {
    back: "M3 30 C1 12 15 -1 32 -1 C49 -1 63 12 61 30 C64 36 60 42 63 48 C66 54 61 60 63 64 C58 67 54 65 52 62 L12 62 C10 65 6 67 1 64 C3 60 -2 54 1 48 C4 42 0 36 3 30 Z",
    front: "M3 46 C0 26 4 10 13 4 C21 -1 34 -3 45 0 C55 3 62 13 61 24 C60 30 63 36 60 42 C59.5 44 60 45 60.5 46 L57 46 C56 42 58 36 55 30 C53.5 25 51 21.5 47 20.5 C40 19.5 32 15.5 25 9 C22 14 17 18 12.5 21 C9 24 7 29 9 34 C10 38 6 42 7.5 46 Z",
    part: "M25 9 C24 5 23 2 22 0",
    strands: ["M26 6 C34 11 42 15 50 18", "M9 24 C7 30 11 35 8 42", "M57 26 C60 31 56 36 59 42"],
    shine: "M31 4 C39 6 46 9 52 13",
  },
  bob: {
    back: "M3 30 C1 10 16 -1 32 -1 C48 -1 63 10 61 30 L61.5 45 C58 48 54 47 52 44 L12 44 C10 47 6 48 2.5 45 Z",
    front: "M3 45 C1 24 5 9 14 3 C22 -2 38 -2 47 1 C57 5 62 16 61 30 L61 45 L56.5 45 L56.5 30 C56 25 53 21 49 20 C43 20 35 17.5 29 12 C26 16 20 19 14 20.5 C10 22 8 26 7.5 30 L7.5 45 Z",
    part: "M29 12 C28 7 27 3 26 0",
    strands: ["M31 8 C37 13 44 16 52 18", "M10 26 L10 42", "M54 26 L54 42"],
    shine: "M14 9 Q19 3 27 1",
  },
  bun: {
    front: "M5 30 C3 16 13 2 32 2 C51 2 61 16 59 30 L56.5 30 C56 23 52 17 46 14 C41 12 36 12.5 32 14 C28 12.5 23 12 18 14 C12 17 8 23 7.5 30 Z",
    bun: [32, -6, 8],
    strands: ["M32 3 L32 13", "M24 4 C20 8 16 12 12 18", "M40 4 C44 8 48 12 52 18"],
    shine: "M13 12 Q18 5 25 4",
  },
  ponytail: {
    front: "M5 30 C3 16 13 2 32 2 C51 2 61 16 59 30 L56.5 30 C56 23 52 17 46 14 C41 12 36 12.5 32 14 C28 12.5 23 12 18 14 C12 17 8 23 7.5 30 Z",
    tail: "M51 8 C64 9 71 25 67 43 C65 50 60 53 57 49 C62 38 61 24 52 15 Z",
    strands: ["M32 3 L32 13", "M24 4 C20 8 16 12 12 18", "M40 4 C44 8 48 12 52 18", "M60 16 C65 24 66 34 63 44"],
    shine: "M13 12 Q18 5 25 4",
  },
  locs: {
    front: "M4 32 C1 22 3 11 11 5 C18 -1 26 -2 32 -2 C38 -2 46 -1 53 5 C61 11 63 22 60 32 L56.5 32 C56 26 54 22 50.5 20 C45 18.5 38 14 33 7 L31 7 C26 14 19 18.5 13.5 20 C10 22 8 26 7.5 32 Z",
    part: "M32 -1 L32 7",
    locs: [[3.5, 16, 50], [8.5, 20, 54], [13.5, 26, 50], [50.5, 26, 50], [55.5, 20, 54], [60.5, 16, 50]],
    frontLocs: [[5.5, 24, 46], [58.5, 24, 46], [11, 17, 26], [53, 17, 26]],
    strands: ["M30 4 C26 10 20 14 13 18", "M34 4 C38 10 44 14 51 18", "M26 1 C21 5 15 9 10 14", "M38 1 C43 5 49 9 54 14"],
    shine: "M12 11 Q17 4 25 1",
  },
  undercut: {
    sides: "M5 31 C3 22 5 13 11 9 L53 9 C59 13 61 22 59 31 L56.5 31 C56 26 55 22 52.5 20 L11.5 20 C9.5 22 8 26 7.5 31 Z",
    front: "M9 17 C6 6 16 -4 32 -5 C47 -6 59 0 60 10 C61 16 57 20 50 19.5 C42 19.5 31 17 23 12 C19 15.5 13 18.5 9 17 Z",
    strands: ["M14 8 C22 2 34 0 46 1", "M24 11 C32 12 42 14 52 14", "M18 4 C28 -2 40 -3 52 1"],
    shine: "M18 1 C25 -3 34 -4 42 -3",
  },
  spiky: {
    front: "M5 31 C3 24 3 17 6 12 L3 5 L11 7 L10 -2 L18 3 L20 -7 L27 0 L32 -9 L37 0 L44 -7 L46 3 L54 -2 L53 7 L61 5 L58 12 C61 19 61 25 59 31 L56.5 31 C56 26 54.5 22 52 19.5 L49 16 L45 19 L41 15 L37 18.5 L32 15 L27 18.5 L23 15 L19 19 L15 16 L12.5 19.5 C9.5 22 8 26 7.5 31 Z",
    strands: ["M20 10 L19 2", "M32 9 L32 -3", "M44 10 L45 2"],
    shine: "M13 9 L19 3",
  },
  mohawk: {
    sides: "M5 31 C3 22 5 11 12 6 C20 1 44 1 52 6 C59 11 61 22 59 31 L56.5 31 C56 26 55 22 52.5 20 L11.5 20 C9.5 22 8 26 7.5 31 Z",
    front: "M24 17 C22 8 23 -2 27 -9 L30 -5 L32 -13 L35 -5 L38 -10 C42 -2 42 8 40 17 C37 18.5 27 18.5 24 17 Z",
    strands: ["M32 -8 L32 14", "M28 -2 L29 14", "M36 -2 L35 14"],
    shine: "M28 -4 C29 2 29 8 28 14",
    tall: true,
  },
  fringe: {
    front: "M4 36 C1 22 4 8 14 3 C22 -1 42 -1 50 3 C60 8 63 22 60 36 L56.5 36 C56 30 55 25 53 21 L50 18.5 L47 21 L43 18 L39 21 L35 18 L31 21 L27 18 L23 21 L19 18 L15 21 L11.5 21 C9 25 7.5 30 7.5 36 Z",
    strands: ["M19 8 L20 17", "M27 6 L27 17", "M35 6 L35 17", "M43 8 L43 17"],
    shine: "M13 10 Q18 4 26 2",
  },
  slick: {
    front: "M5 29 C3 17 12 3 32 2 C52 1 61 15 59 29 L56.5 29 C56 22 53 16 47 13 C40 10 24 10 17 13 C11 16 8 22 7.5 29 Z",
    strands: ["M18 11 C22 6 28 3 34 3", "M26 11 C30 6 36 4 42 4", "M36 11 C40 7 45 6 50 8"],
    shine: "M14 13 C18 6 26 3 36 3",
  },
  longcurls: {
    back: "M3 30 C1 10 16 -1 32 -1 C48 -1 63 10 61 30 L62 58 L2 58 Z",
    backCurls: [[4, 22, 6], [3, 32, 6.5], [4, 42, 6.5], [6, 52, 6], [11, 59, 5.5], [60, 22, 6], [61, 32, 6.5], [60, 42, 6.5], [58, 52, 6], [53, 59, 5.5], [20, 61, 5], [44, 61, 5], [32, 62, 5]],
    front: "M5 30 C3 16 14 3 32 3 C50 3 61 16 59 30 L56.5 30 C55 24 52 20 48 19 L16 19 C12 20 9 24 7.5 30 Z",
    curls: [[6.5, 40, 4.6], [6, 32, 4.8], [8, 24, 4.6], [8.5, 15.5, 5.4], [14.5, 8, 6], [23, 3.5, 6], [32, 2, 6.2], [41, 3.5, 6], [49.5, 8, 6], [55.5, 15.5, 5.4], [56, 24, 4.6], [58, 32, 4.8], [57.5, 40, 4.6], [15, 15.5, 4.2], [23, 14, 4.2], [31.5, 13.5, 4.2], [40, 14, 4.2], [48, 15.5, 4.2]],
    shine: "M11 10 Q15 4 21 1",
  },
  buzzline: {
    shaved: true,
    front: "M6 24 C6 10 18 2 32 2 C46 2 58 10 58 24 C55 19 51 16.5 46 16 C38 15 26 15 18 16 C13 16.5 9 19 6 24 Z",
    line: "M11 14 L19 10",
    shine: "M13 10 Q18 5 25 4",
  },
};
const NM_CHAR_INK = "#2a2330";
//: The body's outline, in one place: a figure reads as designed when every
//: part is drawn with the same line.
const NM_CHAR_LINE = 1.6;
//: The silhouette: head, neck and body in one path.
const NM_CHAR_BODY = "M32 4 C48 4 59 14 59 29 C59 40 55 46 50.5 50 C55 55 56.5 65 53 71.5 C48 76.5 16 76.5 11 71.5 C7.5 65 9 55 13.5 50 C9 46 5 40 5 29 C5 14 16 4 32 4 Z";
//: The jaw and cheeks by presentation: a squarer, wider jaw for masculine,
//: a softer, narrower chin for feminine; the same head above the cheeks.
const NM_CHAR_BODY_MASCULINE = "M32 4 C48 4 59 14 59 29 C59.5 39 58 45.5 51.5 50 C55 55 56.5 65 53 71.5 C48 76.5 16 76.5 11 71.5 C7.5 65 9 55 12.5 50 C6 45.5 4.5 39 5 29 C5 14 16 4 32 4 Z";
const NM_CHAR_BODY_FEMININE = "M32 4 C48 4 59 14 59 29 C59 39 55.5 45 50 49.5 C55 55 56.5 65 53 71.5 C48 76.5 16 76.5 11 71.5 C7.5 65 9 55 14 49.5 C8.5 45 5 39 5 29 C5 14 16 4 32 4 Z";
const NM_CHAR_GHOST = "M32 4 C48 4 59 14 59 29 C59 40 56 48 55 56 C56 66 58 76 56 84 C52 80 49 86 45 82 C41 88 37 82 32 86 C27 82 23 88 19 82 C15 86 12 80 8 84 C6 76 8 66 9 56 C8 48 5 40 5 29 C5 14 16 4 32 4 Z";

function nmHex(value) {
  return /^#[0-9a-f]{6}$/i.test(value || "") ? value : null;
}

function nmMix(hex, other, t) {
  const a = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const b = [1, 3, 5].map((i) => parseInt(other.slice(i, i + 2), 16));
  return `#${a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, "0")).join("")}`;
}

//: The one outline colour for a fill: half its lightness, except on a fill
//: that is nearly black already (dark hair, a pirate's hat, a suit), where a
//: darker line vanished into a dark page; there it is a lighter rim.
function nmLineFor(hex) {
  return nmLuma(hex) < 0.045 ? nmMix(hex, "#ffffff", 0.38) : nmMix(hex, "#000000", 0.5);
}

function nmLuma(hex) {
  const c = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

function drawCharacter(seed, size = 20, mode = "mark") {
  const full = mode === "figure";
  const ns = "http://www.w3.org/2000/svg";
  const make = (tag, attrs = {}, parent = null) => {
    const el = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value !== undefined && value !== null) el.setAttribute(key, String(value));
    }
    if (parent) parent.appendChild(el);
    return el;
  };
  //: The name's own hash, as `nameMark` always took it, turned by your own
  //: shuffle when it is your name.
  let h = 2166136261;
  for (const ch of String(seed || "?").trim().toLowerCase()) {
    h ^= ch.codePointAt(0);
    h = Math.imul(h, 16777619) >>> 0;
  }
  const own = nameMarkOwnFor(seed);
  if (own?.variant) h = (h ^ Math.imul(Number(own.variant), 0x2545f491)) >>> 0;
  //: A finaliser before the xorshift: FNV of a short name alone is weakly
  //: mixed, and measured over 26 everyday names it put 15 of them on two of
  //: the eight colour pairs.
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b) >>> 0;
  h ^= h >>> 13;
  h = Math.imul(h, 0xc2b2ae35) >>> 0;
  h = (h ^ (h >>> 16)) >>> 0 || 1;
  //: Taken before the rolls, so the face's leanings never move a colour.
  const lean = h;
  const rnd = () => {
    h ^= h << 13;
    h >>>= 0;
    h ^= h >>> 17;
    h ^= h << 5;
    h >>>= 0;
    return h / 4294967296;
  };
  for (let i = 0; i < 4; i += 1) rnd();
  const reading = nameMood(seed);
  const creature = reading.animal ? NAME_MARK_CREATURES[reading.animal] : null;
  const beast = creature && !creature.human ? creature : null;
  const style = reading.style || {};
  //: **The small mark** (28px and under, `nameMark`): the face and at most
  //: one cue that breaks the outline. A species' ears are its cue, so a
  //: creature's hat goes; the freckles, earrings, stubble and the floating
  //: extras (a "zz", a question mark, a heart) go too, since at that size
  //: they are specks; and the line is thicker so the shape still holds.
  const mini = mode === "mini";
  const LW = mini ? 2.4 : NM_CHAR_LINE;
  const worn = mini && beast ? reading.props.filter((p) => !NAME_MARK_HEAD_KINDS.includes(p)) : reading.props;
  const hatOn = Boolean(creature?.gnomeHat) || worn.some((p) => NAME_MARK_HAT_KINDS.includes(p) || p === "helmet" || p === "hood");
  //: Under a hat or a hood a style that rises off the head (a quiff, a
  //: mohawk, spikes) is pressed flat: drawn as the crop.
  let hairKey = beast ? null : NAME_MARK_HAIR_ALIASES[creature?.hairFixed || style.hair] || creature?.hairFixed || style.hair;
  if (hatOn && ["quiff", "mohawk", "spiky"].includes(hairKey)) hairKey = "crop";
  const hairStyle = (hairKey && NM_HAIR_STYLES[hairKey]) || null;
  //: The companion's passing expression (`nameMarkBuddyExpress`) is its
  //: face only: the colours stay the ones its name gave it.
  const expr = full && nameCharacterExpression && NAME_MARK_FACES[nameCharacterExpression] ? nameCharacterExpression : "";
  const faceMood = expr || reading.mood || "";
  const face = nameMarkLean(expr ? NAME_MARK_FACES[expr] : reading.mood ? NAME_MARK_FACES[reading.mood] || {} : {}, faceMood, lean);
  const bias = reading.source !== "seed" && reading.mood ? NAME_MARK_MOOD_GROUNDS[reading.mood] : null;
  const colourRoll = rnd();
  const pair = NM_CHAR_PAIRS[bias ? bias[Math.floor(colourRoll * bias.length)] : Math.floor(colourRoll * NM_CHAR_PAIRS.length)];
  //: A person (anyone who is not a creature or a mutant) has a skin tone;
  //: a creature with no coat of its own takes the pair's gel body.
  const person = !beast && !reading.mutant;
  const skinRoll = rnd();
  const skin = NM_CHAR_SKINS.find((one) => one.name === style.skin) || NM_CHAR_SKINS[Math.floor(skinRoll * NM_CHAR_SKINS.length)];
  const base = nmHex(beast ? creature.head : null) || (person ? skin.skin : pair.body);
  const light = nmMix(base, "#ffffff", 0.28);
  const shade = nmMix(base, "#000000", 0.16);
  const line = nmLineFor(base);
  const spread = 9 + rnd() * 2.2;
  const delay = rnd();
  const tailRoll = rnd();
  const serial = (nameMarkSerial += 1);
  const id = (part) => `nmc-${serial}-${part}`;

  //: A head-only mark is cropped to the head and what stands on it; a tall
  //: hat, long ears or a horn widen the crop rather than lose their tops.
  const tall = worn.some((p) => ["hat", "partyhat", "chefhat", "halo", "antenna", "crown"].includes(p)) || (hairStyle?.bun && !hatOn) || hairStyle?.tall
    || creature?.gnomeHat || creature?.unihorn || creature?.ears === "long" || creature?.antenna || creature?.flameCrest;
  const svg = make("svg", {
    class: `name-mark nm-char${expr || reading.mood ? ` nm-${expr || reading.mood}` : ""}`,
    viewBox: full ? "0 0 64 92" : tall ? (mini ? "-6 -18 76 76" : "-8 -21 80 80") : mini ? "-1 -5 66 66" : "-3 -9 70 70",
    width: size,
    height: full ? Math.round((size * 92) / 64) : size,
    "aria-hidden": "true",
    focusable: "false",
    overflow: full ? "visible" : null,
  });
  svg.dataset.nmSeed = String(seed || "");
  svg.style.setProperty("--nm-delay", `${(-delay * 5).toFixed(2)}s`);
  const title = nameMarkTitle(reading);
  if (title) make("title", {}, svg).textContent = title;
  const defs = make("defs", {}, svg);
  const grad = make("linearGradient", { id: id("g"), x1: 0.2, y1: 0, x2: 0.8, y2: 1 }, defs);
  make("stop", { offset: 0, "stop-color": light }, grad);
  make("stop", { offset: 0.55, "stop-color": base }, grad);
  make("stop", { offset: 1, "stop-color": shade }, grad);
  const bodyPath = creature?.shape === "ghost" ? NM_CHAR_GHOST : !person ? NM_CHAR_BODY : reading.look === "masculine" ? NM_CHAR_BODY_MASCULINE : reading.look === "feminine" ? NM_CHAR_BODY_FEMININE : NM_CHAR_BODY;
  make("path", { d: bodyPath }, make("clipPath", { id: id("c") }, defs));

  const outlined = (d, colour, width, parent, extra = {}) => {
    const g = make("g", extra, parent);
    make("path", { d, fill: "none", stroke: line, "stroke-width": width + LW * 2, "stroke-linecap": "round", "stroke-linejoin": "round" }, g);
    make("path", { d, fill: "none", stroke: colour, "stroke-width": width, "stroke-linecap": "round", "stroke-linejoin": "round" }, g);
    return g;
  };
  const shape = (tag, attrs, parent) => make(tag, { stroke: line, "stroke-width": LW, "stroke-linejoin": "round", ...attrs }, parent);

  if (full) make("ellipse", { class: "nmc-shadow", cx: 32, cy: 90.5, rx: 16, ry: 2.4, fill: "#000000", "fill-opacity": 0.16 }, svg);
  const body = make("g", { class: "nm-body" }, svg);
  const back = make("g", { class: "nmc-back" }, body);

  // --- behind the body: tail, wings, long hair, a mane, raised arms ---------
  const wing = reading.wing || creature?.wing || null;
  if (wing) {
    const wingColour = { angel: "#ffffff", bird: nmMix(base, "#ffffff", 0.35), phoenix: "#f28e2c", dragon: nmMix(base, "#000000", 0.25), bat: "#4a3f55", fairy: "#cfe8ff", bee: "#e8f4ff", butterfly: pair.cloth[0] }[wing] || "#ffffff";
    const soft = ["fairy", "bee"].includes(wing);
    for (const [side, sx] of [["l", -1], ["r", 1]]) {
      const w = make("g", { class: `nm-wing nm-wing-${side}` }, back);
      const x0 = 32 + sx * 14;
      const d = ["bat", "dragon"].includes(wing)
        ? `M${x0} 50 C${x0 + sx * 10} 38 ${x0 + sx * 24} 36 ${x0 + sx * 28} 42 C${x0 + sx * 24} 46 ${x0 + sx * 22} 50 ${x0 + sx * 24} 56 C${x0 + sx * 18} 54 ${x0 + sx * 14} 58 ${x0 + sx * 12} 62 C${x0 + sx * 8} 58 ${x0 + sx * 4} 58 ${x0} 60 Z`
        : `M${x0} 52 C${x0 + sx * 8} 36 ${x0 + sx * 24} 34 ${x0 + sx * 27} 44 C${x0 + sx * 22} 46 ${x0 + sx * 24} 52 ${x0 + sx * 19} 55 C${x0 + sx * 17} 60 ${x0 + sx * 8} 62 ${x0} 60 Z`;
      shape("path", { d, fill: wingColour, "fill-opacity": soft ? 0.7 : 1 }, w);
    }
  }
  const tails = {
    cat: "thin", tiger: "thin", lion: "tuft", wolf: "bushy", fox: "bushy", mouse: "thin", raccoon: "ringed", dog: "wag",
    bunny: "puff", sheep: "puff", pig: "curl", dino: "thick", dragon: "thick", monkey: "curly", bear: "puff", panda: "puff",
    hamster: "puff", deer: "puff", cow: "tuft", unicorn: "tuft", koala: "puff", shark: "thick", snake: "thick",
  };
  const tail = beast ? tails[reading.animal] : reading.mutant && tailRoll < 0.3 ? "thin" : null;
  if (tail && full) {
    const t = make("g", { class: "nm-tail" }, back);
    const tailColour = nmMix(base, "#000000", 0.08);
    if (tail === "puff") shape("circle", { cx: 50, cy: 70, r: 5, fill: nmMix(base, "#ffffff", 0.3) }, t);
    else if (tail === "curl") outlined("M50 66 C58 64 60 70 56 72 C52 74 52 68 57 67", tailColour, 2.2, t);
    else if (tail === "bushy" || tail === "ringed") {
      shape("path", { d: "M49 68 C58 70 64 60 62 50 C60 44 55 44 56 50 C57 58 54 62 48 62 Z", fill: tailColour }, t);
      if (reading.animal === "fox") shape("path", { d: "M62 50 C60 44 55 44 56 50 C57 52 60 53 62 50 Z", fill: "#f5f4ef" }, t);
      if (tail === "ringed") for (const y of [52, 57]) make("path", { d: `M55 ${y} L62 ${y - 1}`, stroke: "#2b2a28", "stroke-width": 2 }, t);
    } else if (tail === "thick") shape("path", { d: "M46 64 C56 66 62 72 66 80 C58 78 52 76 46 72 Z", fill: tailColour }, t);
    else if (tail === "wag") outlined("M50 66 C56 64 58 58 57 54", tailColour, 3.2, t);
    else if (tail === "curly") outlined("M50 68 C60 70 64 62 60 56 C57 52 53 56 56 59", tailColour, 2.4, t);
    else {
      outlined("M50 68 C58 70 62 64 60 56", tailColour, 2.4, t);
      if (tail === "tuft") shape("circle", { cx: 60, cy: 55, r: 2.8, fill: creature?.mane && creature.mane !== "rainbow" ? creature.mane : line }, t);
    }
  }
  const toneKey = NAME_MARK_HAIR_TONE_KINDS.includes(style.hairTone) ? style.hairTone : skin.hair[((style.hairColour || 0) + (style.hair || "").length) % skin.hair.length];
  const hairColour = creature?.hairTone || NM_CHAR_HAIR_TONES[toneKey];
  //: Hair's own outline: darker than the hair, except on near-black hair,
  //: where it is a faint lighter rim so the shape holds on a dark page.
  const hairLine = nmLuma(hairColour) < 0.045 ? nmMix(hairColour, "#ffffff", 0.22) : nmMix(hairColour, "#000000", 0.45);
  const hairShade = nmMix(hairColour, "#000000", 0.24);
  const hairLit = nmMix(hairColour, "#ffffff", nmLuma(hairColour) > 0.3 ? 0.5 : 0.32);
  const hairShape = (d, parent, fill = hairColour) => make("path", { d, fill, stroke: hairLine, "stroke-width": LW, "stroke-linejoin": "round" }, parent);
  const lock = (x, y0, y1, fill, parent) => {
    const g = make("g", {}, parent);
    make("path", { d: `M${x} ${y0} L${x} ${y1}`, stroke: hairLine, "stroke-width": 4 + LW * 2, "stroke-linecap": "round" }, g);
    make("path", { d: `M${x} ${y0} L${x} ${y1}`, stroke: fill, "stroke-width": 4, "stroke-linecap": "round" }, g);
    return g;
  };
  //: **Hair under a hat** (K25, the owner: "the hair is showing from
  //: behind the hat"): under a hat that covers the crown, nothing of the
  //: hair above its brim is drawn; under the nightcap, which comes and
  //: goes, the hair above its band is a piece of its own
  //: (`nmc-hair-crown`) that the CSS hides while the cap shows.
  const brimAt = creature?.gnomeHat ? NM_HAT_BRIM.gnome : NM_HAT_BRIM[worn.find((p) => NM_HAT_BRIM[p])];
  const capSlot = full && !hatOn;
  const brimLine = brimAt ? `M-40 ${brimAt} L104 ${brimAt}` : capSlot ? NM_NIGHTCAP_BRIM : "";
  if (brimLine) {
    make("path", { d: `${brimLine} L104 120 L-40 120 Z` }, make("clipPath", { id: id("hb") }, defs));
    if (!brimAt) make("path", { d: `${brimLine} L104 -40 L-40 -40 Z` }, make("clipPath", { id: id("hc") }, defs));
  }
  const hairUnder = (parent, draw) => {
    if (!brimLine) return draw(parent);
    draw(make("g", { "clip-path": `url(#${id("hb")})` }, parent));
    if (!brimAt) draw(make("g", { class: "nmc-hair-crown", "clip-path": `url(#${id("hc")})` }, parent));
  };
  //: Behind the head: the back layer in the shade, a ponytail, locs, a bun.
  const backHair = (parent) => {
    if (hairStyle?.back) hairShape(hairStyle.back, parent, hairShade);
    if (hairStyle?.tail) hairShape(hairStyle.tail, parent);
    if (hairStyle?.locs) for (const [x, y0, y1] of hairStyle.locs) lock(x, y0, y1, hairShade, parent);
    if (hairStyle?.backCurls) {
      for (const [cx, cy, r] of hairStyle.backCurls) make("circle", { cx, cy, r, fill: hairLine, stroke: hairLine, "stroke-width": LW * 2 }, parent);
      for (const [cx, cy, r] of hairStyle.backCurls) make("circle", { cx, cy, r, fill: hairShade }, parent);
    }
    if (hairStyle?.bun && !hatOn) {
      const [cx, cy, r] = hairStyle.bun;
      make("circle", { cx, cy, r, fill: hairColour, stroke: hairLine, "stroke-width": LW }, parent);
      make("path", { d: `M${cx - r * 0.55} ${cy + r * 0.1} C${cx - r * 0.4} ${cy - r * 0.6} ${cx + r * 0.5} ${cy - r * 0.6} ${cx + r * 0.55} ${cy}`, fill: "none", stroke: hairShade, "stroke-width": 0.9, "stroke-linecap": "round" }, parent);
      make("path", { d: `M${cx - r * 0.6} ${cy - r * 0.35} Q${cx - r * 0.2} ${cy - r * 0.85} ${cx + r * 0.3} ${cy - r * 0.8}`, fill: "none", stroke: hairLit, "stroke-width": 1.6, "stroke-linecap": "round", "stroke-opacity": 0.8 }, parent);
    }
  };
  hairUnder(back, backHair);
  if (creature?.mane) {
    const mane = creature.mane === "rainbow" ? null : creature.mane;
    if (mane) {
      for (let i = 0; i < 12; i += 1) {
        const a = (Math.PI * 2 * i) / 12;
        make("circle", { cx: 32 + Math.cos(a) * 27, cy: 28 + Math.sin(a) * 24, r: 8, fill: mane, stroke: nmMix(mane, "#000000", 0.45), "stroke-width": LW }, back);
      }
    } else {
      ["#e15759", "#f28e2c", "#edc949", "#59a14f", "#4e79a7"].forEach((c, i) => outlined(`M${40 + i * 3} ${2 + i * 2} C${54 + i * 2} ${8 + i * 3} ${60 + i} ${24 + i * 4} ${58 + i} ${40 + i * 3}`, c, 2.6, back));
    }
  }
  if (creature?.wool) {
    for (let i = 0; i < 9; i += 1) {
      const a = Math.PI + (Math.PI * i) / 8;
      make("circle", { cx: 32 + Math.cos(a) * 25, cy: 26 + Math.sin(a) * 21, r: 7.5, fill: creature.wool, stroke: nmMix(creature.wool, "#000000", 0.35), "stroke-width": LW }, back);
    }
  }
  if (creature?.quills) {
    for (let i = 0; i < 9; i += 1) {
      const a = Math.PI * 0.95 + (Math.PI * 1.1 * i) / 8;
      const x = 32 + Math.cos(a) * 26;
      const y = 32 + Math.sin(a) * 26;
      make("path", { d: `M${x - 5} ${y} L${32 + Math.cos(a) * 36} ${32 + Math.sin(a) * 36} L${x + 5} ${y + 2} Z`, fill: creature.quills, stroke: nmMix(creature.quills, "#000000", 0.4), "stroke-width": LW, "stroke-linejoin": "round" }, back);
    }
  }
  // Ears that stand above the head, behind it.
  const earInner = creature?.inner || nmMix(base, "#ff9da7", 0.45);
  const earColour = nmHex(creature?.ear) || base;
  const earScale = (creature?.earSize || 4) / 4;
  const ears = beast?.ears;
  if (ears === "pointy") {
    for (const sx of [-1, 1]) {
      shape("path", { d: `M${32 + sx * 13} 9 L${32 + sx * 25} -6 L${32 + sx * 26} 17 Z`, fill: earColour }, back);
      make("path", { d: `M${32 + sx * 16} 9 L${32 + sx * 23.5} 0 L${32 + sx * 24} 13 Z`, fill: earInner }, back);
    }
  } else if (ears === "round") {
    for (const sx of [-1, 1]) {
      shape("circle", { cx: 32 + sx * 20, cy: 8, r: 7.5 * earScale, fill: earColour }, back);
      make("circle", { cx: 32 + sx * 20, cy: 8.5, r: 4.2 * earScale, fill: earInner }, back);
    }
  } else if (ears === "long") {
    for (const sx of [-1, 1]) {
      shape("ellipse", { cx: 32 + sx * 11, cy: -6, rx: 5.5, ry: 14, transform: `rotate(${sx * 12} ${32 + sx * 11} 8)`, fill: earColour }, back);
      make("ellipse", { cx: 32 + sx * 11, cy: -5, rx: 2.8, ry: 10, transform: `rotate(${sx * 12} ${32 + sx * 11} 8)`, fill: earInner }, back);
    }
  } else if (ears === "tufts") {
    for (const sx of [-1, 1]) shape("path", { d: `M${32 + sx * 14} 8 L${32 + sx * 24} -3 L${32 + sx * 25} 14 Z`, fill: shade }, back);
  }
  if (creature?.eyesUp) for (const sx of [-1, 1]) shape("circle", { cx: 32 + sx * 11, cy: 8, r: 9, fill: base }, back);
  if (beast?.fin) shape("path", { d: "M26 6 C30 -6 38 -10 42 -8 C38 -2 38 2 40 6 Z", fill: shade }, back);
  if (beast?.spikes) for (const x of [18, 32, 46]) shape("path", { d: `M${x - 6} ${x === 32 ? 5 : 8} L${x} ${x === 32 ? -6 : -2} L${x + 6} ${x === 32 ? 5 : 8} Z`, fill: beast.spikes }, back);
  if (full) {
    for (const [side, d] of [["l", "M14 56 C-2 52 -6 18 6 -6"], ["r", "M50 56 C66 52 70 18 58 -6"]]) {
      outlined(d, base, 6, back, { class: `nmb-hold nmb-hold-${side}`, "data-pivot": side === "l" ? "14 56" : "50 56" });
    }
  }

  // --- legs, the body, and the arms in front ----------------------------------
  if (full) {
    const legColour = nmMix(base, "#000000", 0.1);
    const limbs = reading.limbs || creature?.limbs;
    const footColour = nmHex(beast?.foot) || legColour;
    if (creature?.shape === "ghost") {
      // A ghost has no legs to stand on; its hem is its feet.
    } else if (limbs === "tentacles") {
      for (const [side, x] of [["l", 22], ["l", 29], ["r", 35], ["r", 42]]) {
        outlined(`M${x} 66 C${x - 3} 76 ${x + 3} 82 ${x - 1} 89`, legColour, 5, body, { class: `nmb-leg nmb-leg-${side} nm-tentacle`, "data-pivot": `${x} 66` });
      }
    } else if (limbs === "tail") {
      const g = make("g", { class: "nmb-leg nmb-leg-l nmb-leg-r", "data-pivot": "32 66" }, body);
      shape("path", { d: "M20 66 C22 80 30 84 32 86 C34 84 42 80 44 66 Z", fill: hairColour === base ? "#3fb8a8" : "#3fb8a8" }, g);
      shape("path", { d: "M32 84 L22 91 L32 88 L42 91 Z", fill: "#3fb8a8" }, g);
    } else {
      for (const [side, x] of [["l", 25.5], ["r", 38.5]]) {
        const leg = make("g", { class: `nmb-leg nmb-leg-${side}`, "data-pivot": `${x} 68` }, body);
        outlined(`M${x} 68 L${x} 84`, legColour, 7, leg);
        shape("ellipse", { cx: x + (side === "l" ? -1.4 : 1.4), cy: 87, rx: 5.6, ry: 3.3, fill: footColour }, leg);
      }
    }
  }
  const torso = make("g", { class: "nmb-torso" }, body);
  shape("path", { d: bodyPath, fill: `url(#${id("g")})` }, torso);
  const clip = make("g", { "clip-path": `url(#${id("c")})` }, torso);
  //: People wear clothes on the lower half; creatures show a paler belly.
  const outfit = beast ? null : style.outfit;
  if (outfit) {
    // The garment joins the roll, so two names on one pair and one roll still differ.
    let cloth = pair.cloth[((style.outfitColour || 0) + (outfit.length & 1)) % pair.cloth.length];
    if (outfit === "suit") cloth = "#33323a";
    const clothLine = nmLineFor(cloth);
    make("path", { d: "M0 52 C12 56 52 56 64 52 L64 92 L0 92 Z", fill: cloth }, clip);
    make("path", { d: "M0 52 C12 56 52 56 64 52", fill: "none", stroke: clothLine, "stroke-width": LW }, clip);
    if (outfit === "collar" || outfit === "suit" || outfit === "blazer") {
      make("path", { d: "M24 54 L32 66 L40 54 Z", fill: "#ffffff", stroke: clothLine, "stroke-width": 1 }, clip);
      if (outfit !== "blazer") make("path", { d: "M32 57 L30 61 L32 70 L34 61 Z", fill: "#e2574c", stroke: "#8e2a24", "stroke-width": 0.8 }, clip);
    } else if (outfit === "hoodie") {
      make("path", { d: "M22 54 C26 60 38 60 42 54", fill: "none", stroke: clothLine, "stroke-width": 1.4 }, clip);
      for (const x of [28, 36]) make("path", { d: `M${x} 58 L${x} 65`, stroke: "#f5f4ef", "stroke-width": 1.2, "stroke-linecap": "round" }, clip);
    } else if (outfit === "scoop") {
      make("path", { d: "M22 53 C26 61 38 61 42 53", fill: base, stroke: clothLine, "stroke-width": 1 }, clip);
      for (const x of [27, 32, 37]) make("circle", { cx: x, cy: x === 32 ? 59.5 : 58, r: 1, fill: "#f5f4ef" }, clip);
    } else if (outfit === "sweater") {
      for (const y of [68, 71]) make("path", { d: `M8 ${y} L56 ${y}`, stroke: clothLine, "stroke-width": 0.9 }, clip);
    } else if (outfit === "dress") {
      make("path", { d: "M8 63 L56 63", stroke: "#f5f4ef", "stroke-width": 2 }, clip);
    } else {
      make("path", { d: "M26 54 C28 58 36 58 38 54", fill: "none", stroke: clothLine, "stroke-width": 1.2 }, clip);
    }
  } else {
    make("ellipse", { cx: 32, cy: 64, rx: 12, ry: 8.5, fill: beast?.mask && reading.animal === "penguin" ? "#f5f4ef" : "#ffffff", "fill-opacity": beast?.mask ? 0.9 : 0.28 }, clip);
  }
  if (beast?.beeStripes) for (const y of [58, 66]) make("rect", { x: 0, y, width: 64, height: 4, fill: "#2b2a28" }, clip);
  if (beast?.stripes) for (const [x, y] of [[8, 24], [56, 24], [10, 32], [54, 32]]) make("path", { d: `M${x} ${y} L${x < 32 ? x + 7 : x - 7} ${y + 1.5}`, stroke: "#2b2a28", "stroke-width": 2, "stroke-linecap": "round" }, clip);
  if (beast?.stripes) make("path", { d: "M28 6 L32 12 L36 6", fill: "none", stroke: "#2b2a28", "stroke-width": 2, "stroke-linecap": "round" }, clip);
  if (beast?.spots || reading.mutant?.spots) {
    const spotColour = beast?.spots || nmMix(base, "#000000", 0.25);
    const count = beast?.spots ? 4 : reading.mutant.spots;
    const at = [[14, 18, 5], [50, 14, 4], [48, 60, 5], [18, 62, 4], [40, 8, 3]];
    for (let i = 0; i < count; i += 1) make("circle", { cx: at[i % 5][0], cy: at[i % 5][1], r: at[i % 5][2], fill: spotColour }, clip);
  }
  if (beast?.mask && reading.animal !== "penguin") make("ellipse", { cx: 32, cy: 33, rx: 20, ry: 16, fill: beast.mask }, clip);
  if (reading.animal === "penguin") make("path", { d: "M12 36 C12 18 22 14 32 20 C42 14 52 18 52 36 C52 50 12 50 12 36 Z", fill: "#f5f4ef" }, clip);
  if (beast?.bandit) make("path", { d: "M6 26 C16 22 48 22 58 26 L58 34 C48 31 16 31 6 34 Z", fill: beast.bandit }, clip);
  if (beast?.bandages) for (const y of [14, 24, 44, 60]) make("path", { d: `M0 ${y} L64 ${y + 4}`, stroke: "#f5f1e6", "stroke-width": 3, "stroke-opacity": 0.9 }, clip);
  if (beast?.stitches) make("path", { d: "M14 16 L24 20 M16 14 L16 18 M20 16 L20 20", stroke: "#2b2a28", "stroke-width": 1 }, clip);
  // Ears on the sides of the head, in front of it.
  if (ears === "floppy") for (const sx of [-1, 1]) shape("ellipse", { cx: 32 + sx * 25, cy: 22, rx: 5.5, ry: 11, transform: `rotate(${sx * -18} ${32 + sx * 25} 22)`, fill: earColour }, torso);
  if (ears === "side") for (const sx of [-1, 1]) shape("ellipse", { cx: 32 + sx * 28, cy: 22, rx: 7, ry: 4, fill: earColour }, torso);
  if (creature?.sideEars) for (const sx of [-1, 1]) shape("path", { d: `M${32 + sx * 26} 26 L${32 + sx * (34 + creature.sideEars * 4)} 18 L${32 + sx * 26} 34 Z`, fill: base }, torso);
  if (beast?.gills) for (const sx of [-1, 1]) for (const dy of [-5, 0, 5]) outlined(`M${32 + sx * 26} ${30 + dy} L${32 + sx * 34} ${27 + dy * 1.6}`, beast.gills, 2.4, torso);
  // The front hair.
  const frontHair = (parent) => {
    if (hairStyle) {
      //: The fringe's shadow on the forehead: its own shape two units
      //: lower, in the skin's shade, clipped to the head.
      make("path", { d: hairStyle.sides || hairStyle.front, transform: "translate(0 2)", fill: nmMix(base, "#000000", 0.22), "fill-opacity": 0.45 }, make("g", { "clip-path": `url(#${id("c")})` }, parent));
      //: A shaved layer reads as the hair colour thinned over the skin.
      if (hairStyle.sides) make("path", { d: hairStyle.sides, fill: nmMix(hairColour, base, 0.35), stroke: hairLine, "stroke-width": LW * 0.6, "stroke-linejoin": "round" }, parent);
      hairShape(hairStyle.front, parent, hairStyle.shaved ? nmMix(hairColour, base, 0.3) : hairColour);
      const texture = (d, colour, width, opacity) => make("path", { d, fill: "none", stroke: colour, "stroke-width": width, "stroke-opacity": opacity, "stroke-linecap": "round", "stroke-linejoin": "round" }, parent);
      if (hairStyle.curls) {
        //: One cloud of curls with one outline round the outside: every
        //: curl's outline first, then every curl's fill over them, so the
        //: line only shows where the cloud meets the page or the face. A
        //: small arc in the shade on every other curl is the texture.
        for (const [cx, cy, r] of hairStyle.curls) make("circle", { cx, cy, r, fill: hairLine, stroke: hairLine, "stroke-width": LW * 2 }, parent);
        for (const [cx, cy, r] of hairStyle.curls) make("circle", { cx, cy, r, fill: hairColour }, parent);
        if (!mini) hairStyle.curls.forEach(([cx, cy, r], i) => {
          if (i % 2 === 0) texture(`M${cx - r * 0.5} ${cy + r * 0.1} Q${cx - r * 0.1} ${cy + r * 0.6} ${cx + r * 0.45} ${cy + r * 0.2}`, hairShade, 0.9, 0.75);
        });
      }
      if (hairStyle.frontLocs) {
        for (const [x, y0, y1] of hairStyle.frontLocs) {
          lock(x, y0, y1, hairColour, parent);
          if (!mini) for (let y = y0 + 5; y < y1; y += 6) texture(`M${x - 2} ${y} Q${x} ${y + 1.2} ${x + 2} ${y}`, hairShade, 0.8, 0.8);
        }
      }
      if (hairStyle.part) texture(hairStyle.part, hairShade, 1.1, 0.9);
      if (hairStyle.line) texture(hairStyle.line, base, 1.4, 1);
      if (!mini) for (const d of hairStyle.strands || []) texture(d, hairShade, 0.9, 0.7);
      if (hairStyle.bun && !hatOn) make("ellipse", { cx: 32, cy: 2.4, rx: 4.4, ry: 1.8, fill: pair.cloth[0], stroke: nmLineFor(pair.cloth[0]), "stroke-width": 0.8 }, parent);
      if (hairStyle.tail) make("ellipse", { cx: 52, cy: 10, rx: 2.2, ry: 3, transform: "rotate(-30 52 10)", fill: pair.cloth[0], stroke: nmLineFor(pair.cloth[0]), "stroke-width": 0.8 }, parent);
      if (hairStyle.shine) texture(hairStyle.shine, hairLit, 2.2, 0.85);
    }
  };
  hairUnder(torso, frontHair);
  if (creature?.snakeHair) for (const x of [14, 24, 34, 44, 52]) outlined(`M${x} 10 C${x - 4} 2 ${x + 4} -2 ${x} -8`, creature.snakeHair, 3, torso);
  if (creature?.topknot) shape("circle", { cx: 32, cy: 0, r: 6, fill: creature.topknot }, torso);
  //: A soft sheen on a bare crown, top left, the gloss Atlas's gel has
  //: (hair carries its own).
  if (!hairStyle && !creature?.wool && !creature?.mane) make("path", { class: "nmc-sheen", d: "M12 14 Q16 6 25 4", fill: "none", stroke: "#ffffff", "stroke-opacity": 0.55, "stroke-width": 2.2, "stroke-linecap": "round" }, torso);

  // --- the face ---------------------------------------------------------------------
  const head = make("g", { class: "nm-buddy-head" }, body);
  const eyeY = creature?.eyesUp ? 10 : 30;
  const eyes = [];
  if (creature?.oneEye || reading.mutant?.eyes === 1) eyes.push([32, eyeY - 1, 1.35]);
  else if (reading.mutant?.eyes === 3) eyes.push([32 - spread, eyeY, 1], [32 + spread, eyeY, 1], [32, eyeY - 10, 0.8]);
  else eyes.push([32 - spread, eyeY, 1], [32 + spread, eyeY, 1]);
  if (beast?.patches) for (const [x, y] of eyes) make("ellipse", { cx: x, cy: y + 1, rx: 7, ry: 8.5, transform: `rotate(${x < 32 ? 25 : -25} ${x} ${y})`, fill: beast.patches }, head);
  if (beast?.rings) for (const [x, y] of eyes) make("circle", { cx: x, cy: y, r: 8, fill: beast.rings }, head);
  if (beast?.muzzle) make("ellipse", { cx: 32, cy: 40, rx: 10.5, ry: 7.5, fill: beast.muzzle }, head);
  if (beast?.snout) {
    shape("ellipse", { cx: 32, cy: 39, rx: 6.5, ry: 4.8, fill: beast.snout }, head);
    for (const x of [30, 34]) make("ellipse", { cx: x, cy: 39, rx: 1, ry: 1.6, fill: nmMix(beast.snout, "#000000", 0.45) }, head);
  }
  //: Eyes: whites and a pupil with a catchlight read on any body colour;
  //: a light body can have the beady ones too.
  let eyeStyle = face.eyes || (beast && ["dot", "button"].includes(style.eyes) && nmLuma(base) > 0.3 ? "beady" : style.eyes === "anime" || style.eyes === "sparkle" || style.eyes === "starry" ? "sparkle" : "round");
  if (reading.flavours?.includes("scream")) eyeStyle = "wide";
  if (beast?.eyes === "alien") eyeStyle = "alien";
  if (reading.mutant?.googly) eyeStyle = "googly";
  const eyesG = make("g", { class: "nm-eyes" }, head);
  const blinks = make("g", { class: "nm-blinks" }, eyesG);
  const stroke = (d, parent, width = 1.8, colour = NM_CHAR_INK) =>
    make("path", { d, fill: "none", stroke: colour, "stroke-width": width, "stroke-linecap": "round", "stroke-linejoin": "round" }, parent);
  const heart = (x, y, r, colour, parent, cls) =>
    make("path", { class: cls, d: `M${x} ${y + r * 0.9} C${x - r * 1.6} ${y - r * 0.2} ${x - r * 0.9} ${y - r * 1.3} ${x} ${y - r * 0.4} C${x + r * 0.9} ${y - r * 1.3} ${x + r * 1.6} ${y - r * 0.2} ${x} ${y + r * 0.9} Z`, fill: colour }, parent);
  const star = (x, y, r, colour, parent, cls) => {
    const pts = [];
    for (let i = 0; i < 10; i += 1) {
      const a = -Math.PI / 2 + (Math.PI * i) / 5;
      const rr = i % 2 ? r * 0.45 : r;
      pts.push(`${(x + Math.cos(a) * rr).toFixed(2)},${(y + Math.sin(a) * rr).toFixed(2)}`);
    }
    return make("polygon", { class: cls, points: pts.join(" "), fill: colour, stroke: nmMix(colour, "#000000", 0.4), "stroke-width": 0.7, "stroke-linejoin": "round" }, parent);
  };
  const winkLeft = reading.flavours?.includes("wink");
  eyes.forEach(([x, y, k], index) => {
    const eye = make("g", {}, blinks);
    const s = winkLeft && index === 0 ? "happy" : eyeStyle;
    const white = (rx, ry) => make("ellipse", { cx: x, cy: y, rx: rx * k, ry: ry * k, fill: "#ffffff", stroke: line, "stroke-width": 0.9 }, eye);
    const pupil = (r, dx = 0, dy = 0.6) => {
      make("ellipse", { cx: x + dx, cy: y + dy, rx: r * k, ry: r * 1.15 * k, fill: NM_CHAR_INK }, eye);
      make("circle", { cx: x + dx + r * 0.4 * k, cy: y + dy - r * 0.45 * k, r: 0.9 * k, fill: "#ffffff" }, eye);
    };
    const out = index === 0 ? -1 : 1;
    //: On a dark patch (a panda, a sloth) a closed eye is drawn in white.
    const lidInk = beast?.patches ? "#ffffff" : NM_CHAR_INK;
    if (s === "squeeze") stroke(`M${x + out * 3} ${y - 3} L${x - out * 3} ${y} L${x + out * 3} ${y + 3}`, eye, 2, lidInk);
    else if (s === "happy" || s === "content") stroke(`M${x - 3.6} ${y + 1.2} Q${x} ${y - (s === "content" ? 2 : 3.6)} ${x + 3.6} ${y + 1.2}`, eye, 2, lidInk);
    else if (s === "closed") stroke(`M${x - 3.6} ${y - 0.6} Q${x} ${y + 3} ${x + 3.6} ${y - 0.6}`, eye, 2, lidInk);
    else if (s === "beady" && !beast?.patches) pupil(2.8, 0, 0);
    else if (s === "heart") heart(x, y, 4.2 * k, "#e8364f", eye);
    else if (s === "star") star(x, y, 5 * k, "#f5c518", eye);
    else if (s === "x") stroke(`M${x - 3} ${y - 3} L${x + 3} ${y + 3} M${x + 3} ${y - 3} L${x - 3} ${y + 3}`, eye, 2);
    else if (s === "spiral") stroke(`M${x} ${y} m-0.8 0 a0.8 0.8 0 1 1 1.6 0 a1.8 1.8 0 1 1 -3.6 0 a2.8 2.8 0 1 1 5.6 0 a3.6 3.6 0 1 1 -7.2 0`, eye, 1.2);
    else if (s === "dollar") {
      make("circle", { cx: x, cy: y, r: 4.4, fill: "#f5c518", stroke: "#8a6d00", "stroke-width": 0.9 }, eye);
      stroke(`M${x + 1.6} ${y - 1.8} C${x - 2.6} ${y - 3} ${x - 2.6} ${y} ${x} ${y} C${x + 2.6} ${y} ${x + 2.6} ${y + 3} ${x - 1.6} ${y + 1.8} M${x} ${y - 3.4} L${x} ${y + 3.4}`, eye, 0.9, "#6b5300");
    } else if (s === "alien") make("ellipse", { cx: x, cy: y, rx: 4.6, ry: 6, transform: `rotate(${x < 32 ? 25 : -25} ${x} ${y})`, fill: NM_CHAR_INK }, eye);
    else if (s === "shades") {
      // Drawn with the eyewear below.
    } else if (s === "googly") {
      white(5, 5);
      pupil(2, (index % 2 ? 1 : -1) * 1.4, 1.2);
      const googly = eye.lastChild.previousSibling;
      //: A googly pupil rolls round its own eye (the `nm-roll` loop).
      googly?.setAttribute("class", "nm-pupil");
      googly?.style.setProperty("transform-origin", x + "px " + y + "px");
    } else if (s === "wide") {
      white(4.6, 5.4);
      pupil(1.7, 0, 0.2);
    } else if (s === "narrow" || s === "evil") {
      white(4.6, 3.4);
      pupil(2.2, index === 0 ? 0.8 : -0.8, 0.4);
      make("path", { d: `M${x - 5.4} ${y - (index === 0 ? 3.6 : 1)} L${x + 5.4} ${y - (index === 0 ? 1 : 3.6)} L${x + 5.4} ${y - 6} L${x - 5.4} ${y - 6} Z`, fill: base }, eye);
      stroke(`M${x - 5} ${y - (index === 0 ? 3.4 : 1.2)} L${x + 5} ${y - (index === 0 ? 1.2 : 3.4)}`, eye, 1.4);
    } else if (s === "halflid") {
      white(4.4, 4.8);
      pupil(2.3, 0, 1.2);
      make("path", { d: `M${x - 5.4} ${y + 0.4} L${x + 5.4} ${y + 0.4} L${x + 5.4} ${y - 6} L${x - 5.4} ${y - 6} Z`, fill: base }, eye);
      stroke(`M${x - 4.8} ${y + 0.4} L${x + 4.8} ${y + 0.4}`, eye, 1.3);
    } else if (s === "mismatch") {
      white(index ? 3.4 : 5, index ? 3.8 : 5.6);
      pupil(index ? 1.6 : 2.4);
    } else if (beast?.patches || (beast && nmLuma(base) < 0.12)) {
      //: On a dark patch or a dark coat a dark iris would vanish: whites.
      const big = s === "sparkle" || s === "glossy";
      white(big ? 5 : 4.4, big ? 5.8 : 5.2);
      pupil(big ? 3 : 2.5);
      if (big) make("circle", { cx: x - 1.2 * k, cy: y + 2 * k, r: 0.7 * k, fill: "#ffffff" }, eye);
    } else {
      //: The default eye, in Atlas's family: a big dark iris, lighter at
      //: its foot, with a large catchlight and a small one. Whites around a
      //: small pupil read as startled at every size.
      const big = s === "sparkle" || s === "glossy";
      const rx = (big ? 3.7 : 3.2) * k;
      const ry = (big ? 4.5 : 4) * k;
      make("ellipse", { cx: x, cy: y + 0.4, rx, ry, fill: NM_CHAR_INK }, eye);
      make("ellipse", { cx: x, cy: y + 0.4 + ry * 0.5, rx: rx * 0.66, ry: ry * 0.34, fill: "#6d5a86", "fill-opacity": 0.9 }, eye);
      make("circle", { cx: x + rx * 0.32, cy: y - ry * 0.32, r: (big ? 1.6 : 1.3) * k, fill: "#ffffff" }, eye);
      make("circle", { cx: x - rx * 0.42, cy: y + ry * 0.42, r: 0.65 * k, fill: "#ffffff" }, eye);
    }
    if (style.features?.includes("lashes") && !["x", "spiral", "heart", "star", "dollar"].includes(s)) {
      stroke(`M${x + (index === 0 ? -4 : 4)} ${y - 3} L${x + (index === 0 ? -6 : 6)} ${y - 5}`, eye, 1.2);
    }
  });
  if (creature?.stalks || reading.mutant?.stalks) for (const [x] of eyes) stroke(`M${x} ${eyeY - 5} L${x} ${eyeY - 14}`, head, 2, line);
  // Brows.
  const browY = eyeY - 8.5;
  const browPaths = {
    raised: (x, i) => `M${x - 3.5} ${browY + 0.5} Q${x} ${browY - 2.5} ${x + 3.5} ${browY + 0.5}`,
    sad: (x, i) => (i === 0 ? `M${x - 3.5} ${browY + 1.2} L${x + 3.2} ${browY - 1.2}` : `M${x - 3.2} ${browY - 1.2} L${x + 3.5} ${browY + 1.2}`),
    angry: (x, i) => (i === 0 ? `M${x - 3.5} ${browY - 1} L${x + 3.5} ${browY + 2}` : `M${x - 3.5} ${browY + 2} L${x + 3.5} ${browY - 1}`),
    flat: (x) => `M${x - 3.5} ${browY + 1} L${x + 3.5} ${browY + 1}`,
    dramatic: (x) => `M${x - 4} ${browY} Q${x} ${browY - 4} ${x + 4} ${browY}`,
    sly: (x, i) => (i === 0 ? `M${x - 3.5} ${browY + 1} L${x + 3.5} ${browY + 1}` : `M${x - 3.5} ${browY} Q${x} ${browY - 3} ${x + 3.5} ${browY - 1}`),
    confused: (x, i) => (i === 0 ? `M${x - 3.5} ${browY - 1.5} Q${x} ${browY - 4} ${x + 3.5} ${browY - 1.5}` : `M${x - 3.5} ${browY + 1.5} L${x + 3.5} ${browY + 0.5}`),
  };
  //: A person always has brows, weighted by presentation (heavy and
  //: straight, fine and arched, or between), in the hair's own colour
  //: taken darker; a mood's brows keep their shape and take the weight.
  browPaths.soft = (x) => `M${x - 3.6} ${browY + 0.8} Q${x} ${browY - 1.2} ${x + 3.6} ${browY + 0.8}`;
  browPaths.straight = (x, i) => (i === 0 ? `M${x - 4} ${browY + 0.6} L${x + 3.6} ${browY - 0.3}` : `M${x - 3.6} ${browY - 0.3} L${x + 4} ${browY + 0.6}`);
  browPaths.arched = (x) => `M${x - 3.8} ${browY + 1.2} Q${x - 0.5} ${browY - 2.4} ${x + 3.8} ${browY + 0.2}`;
  const browKind = face.brows || (person ? { masculine: "straight", feminine: "arched" }[reading.look] || "soft" : null);
  const browWeight = !person ? 1.6 : reading.look === "masculine" ? 2.5 : reading.look === "feminine" ? 1.3 : 1.9;
  const browInk = person ? nmMix(hairColour, "#000000", nmLuma(hairColour) > 0.2 ? 0.45 : 0.2) : NM_CHAR_INK;
  if (browKind && browPaths[browKind] && eyes.length === 2) {
    eyes.forEach(([x], i) => {
      const brow = stroke(browPaths[browKind](x, i), head, browWeight, browInk);
      //: Attitude: one brow up.
      if (i === 1 && style.features?.includes("raisedbrow")) brow.setAttribute("transform", `translate(0 -2.4) rotate(-8 ${x} ${browY})`);
    });
    //: A scar through the right brow: a pale nick that breaks it.
    if (style.features?.includes("scar")) stroke(`M${eyes[1][0] + 1.2} ${browY - 3.2} L${eyes[1][0] + 3.2} ${browY + 2.6}`, head, 1.3, nmMix(base, "#ffffff", 0.5));
  }
  // Cheeks: always a little blush; more when the mood or the name says so.
  const flushed = face.extras?.includes("blush") || style.features?.includes("blush") || reading.flavours?.includes("blush");
  const cheek = face.extras?.includes("greenblush") ? "#7fbf6a" : "#ff6f91";
  const cheekSize = reading.look === "feminine" ? 4.4 : 3.8;
  const cheekLift = reading.look === "masculine" && !flushed ? 0.14 : flushed ? 0.55 : 0.28;
  for (const sx of [-1, 1]) make("ellipse", { cx: 32 + sx * 16, cy: eyeY + 7.5, rx: cheekSize, ry: cheekSize * 0.6, fill: cheek, "fill-opacity": cheekLift }, head);
  if (!mini && style.features?.includes("freckles")) for (const sx of [-1, 1]) for (const [dx, dy] of [[0, 0], [2.4, 1], [-2, 1.4]]) make("circle", { cx: 32 + sx * 16 + dx, cy: eyeY + 6 + dy, r: 0.55, fill: nmMix(base, "#000000", 0.4) }, head);
  if (!mini && style.features?.includes("mole")) make("circle", { cx: 41, cy: eyeY + 13, r: 0.8, fill: NM_CHAR_INK }, head);
  if (beast?.whiskers) for (const sx of [-1, 1]) for (const dy of [-1.5, 1.5]) stroke(`M${32 + sx * 12} ${40 + dy} L${32 + sx * 20} ${39 + dy * 2}`, head, 0.8, line);
  // Nose, beak or bill.
  if (beast?.beak) shape("path", { d: "M27.5 36 L32 33.5 L36.5 36 L32 41 Z", fill: beast.beak }, head);
  else if (beast?.bill) shape("path", { d: "M25 37 C25 34 39 34 39 37 C39 41 25 41 25 37 Z", fill: beast.bill }, head);
  else if (beast?.muzzle || beast?.nose || creature?.nose || creature?.bigNose) make("ellipse", { cx: 32, cy: 36.5, rx: creature?.bigNose ? 3.6 : 2.4, ry: creature?.bigNose ? 2.8 : 1.7, fill: creature?.bigNose ? nmMix(base, "#000000", 0.2) : NM_CHAR_INK }, head);
  else if (style.nose === "button") make("ellipse", { cx: 32, cy: 36.5, rx: 1.6, ry: 1.2, fill: nmMix(base, "#000000", 0.25) }, head);
  if (worn.includes("rednose")) shape("circle", { cx: 32, cy: 36.5, r: 3.4, fill: "#e8364f" }, head);
  // The mouth.
  const my = beast?.beak || beast?.bill ? 44 : eyeY + 11;
  let mouth = face.mouth || { smile: "smile", grin: "grin", toothy: "toothy", lopsided: "lopsided", bigD: "grin", buck: "buck", gap: "gap", cat3: "cat" }[style.smile] || "smile";
  if (face.loud && reading.intense) mouth = face.loud;
  if (reading.flavours?.includes("scream")) mouth = "gasp";
  if (beast?.mouth && !face.mouth) mouth = beast.mouth;
  //: Attitude: a smirk in place of a plain smile.
  if (style.features?.includes("smirk") && ["smile", "grin", "toothy", "lopsided", "cat"].includes(mouth)) mouth = "smirk";
  const inner = "#6b2238";
  const openMouth = (d) => {
    make("path", { d, fill: inner, stroke: NM_CHAR_INK, "stroke-width": 1.4, "stroke-linejoin": "round" }, head);
  };
  if (mouth === "smile") stroke(`M27 ${my - 1} Q32 ${my + 3.4} 37 ${my - 1}`, head);
  else if (mouth === "lopsided") stroke(`M27 ${my} Q33 ${my + 3} 37.5 ${my - 2}`, head);
  else if (mouth === "smirk") stroke(`M28 ${my + 0.5} Q33 ${my + 1.8} 37 ${my - 1.8}`, head);
  else if (mouth === "yum") {
    //: A smile licking its lip: the tip of a tongue at one corner.
    stroke(`M27 ${my - 1} Q32 ${my + 3.4} 37 ${my - 1}`, head);
    make("ellipse", { cx: 35.6, cy: my + 1.6, rx: 1.9, ry: 1.6, fill: "#ff7a95", stroke: NM_CHAR_INK, "stroke-width": 0.9 }, head);
  }
  else if (mouth === "frown") stroke(`M27.5 ${my + 1.6} Q32 ${my - 2} 36.5 ${my + 1.6}`, head);
  else if (mouth === "flat") stroke(`M28 ${my} L36 ${my}`, head);
  else if (mouth === "wavy") stroke(`M26.5 ${my} Q28.5 ${my - 1.8} 30.5 ${my} Q32.5 ${my + 1.8} 34.5 ${my} Q36.5 ${my - 1.8} 38 ${my}`, head, 1.5);
  else if (mouth === "cat") stroke(`M27 ${my - 1} Q29.5 ${my + 2} 32 ${my - 0.4} Q34.5 ${my + 2} 37 ${my - 1}`, head, 1.6);
  else if (mouth === "o") make("ellipse", { cx: 32, cy: my + 0.5, rx: 2.2, ry: 2.6, fill: inner, stroke: NM_CHAR_INK, "stroke-width": 1.3 }, head);
  else if (mouth === "gasp" || mouth === "yawn") make("ellipse", { cx: 32, cy: my + 1, rx: 3.4, ry: mouth === "yawn" ? 3.6 : 4.4, fill: inner, stroke: NM_CHAR_INK, "stroke-width": 1.4 }, head);
  else {
    // An open smile, with what the style or mood puts in it.
    openMouth(`M25.5 ${my - 1.5} Q32 ${my - 0.4} 38.5 ${my - 1.5} Q38 ${my + 6.5} 32 ${my + 6.5} Q26 ${my + 6.5} 25.5 ${my - 1.5} Z`);
    if (["grin", "tongue", "toothy", "gap", "buck", "evil", "teeth"].includes(mouth)) make("ellipse", { cx: 32, cy: my + 4.6, rx: 3.6, ry: 1.9, fill: "#ff7a95" }, head);
    if (mouth === "toothy" || mouth === "teeth") make("path", { d: `M26.6 ${my - 1.1} Q32 ${my - 0.2} 37.4 ${my - 1.1} L37 ${my + 1} Q32 ${my + 1.6} 27 ${my + 1} Z`, fill: "#ffffff" }, head);
    if (mouth === "buck") make("rect", { x: 29.8, y: my - 1, width: 4.4, height: 2.8, rx: 0.6, fill: "#ffffff", stroke: NM_CHAR_INK, "stroke-width": 0.6 }, head);
    if (mouth === "gap") for (const x of [28.4, 33.2]) make("rect", { x, y: my - 1, width: 2.4, height: 2.2, rx: 0.4, fill: "#ffffff" }, head);
    if (mouth === "evil" || worn.includes("fangs") || creature?.tusks) for (const x of [28.6, 35.4]) make("path", { d: `M${x - 1.3} ${my - 1} L${x} ${my + 2.4} L${x + 1.3} ${my - 1} Z`, fill: "#ffffff" }, head);
    if (mouth === "tongue") shape("ellipse", { cx: 33, cy: my + 6.6, rx: 2.6, ry: 2.6, fill: "#ff7a95", "stroke-width": 1 }, head);
  }
  if (style.accessories?.includes("lipstick")) make("path", { d: `M27 ${my - 1} Q32 ${my + 1.5} 37 ${my - 1}`, fill: "none", stroke: "#d6336c", "stroke-width": 1.2, "stroke-linecap": "round" }, head);
  if (!mini && style.accessories?.includes("stubble")) for (const [dx, dy] of [[-4, 4], [-1, 5], [2, 5], [5, 4], [-6, 2], [7, 2]]) make("circle", { cx: 32 + dx, cy: my + dy, r: 0.45, fill: nmMix(base, "#000000", 0.45) }, head);
  if (style.accessories?.includes("beard") || worn.includes("beard") || creature?.beard) {
    const beard = creature?.beard || hairColour;
    make("path", { d: `M12 ${my + 1.5} C13 ${my + 19} 51 ${my + 19} 52 ${my + 1.5} C45 ${my + 6} 38 ${my + 5} 32 ${my + 7} C26 ${my + 5} 19 ${my + 6} 12 ${my + 1.5} Z`, fill: beard, stroke: nmMix(beard, "#000000", 0.4), "stroke-width": LW, "stroke-linejoin": "round" }, head);
  }
  if (worn.includes("moustache") || style.accessories?.includes("moustache")) make("path", { d: `M32 ${my - 2.4} C29 ${my - 4.6} 24 ${my - 3.6} 23.5 ${my - 0.6} C26 ${my - 2} 29 ${my - 1} 32 ${my - 1.2} C35 ${my - 1} 38 ${my - 2} 40.5 ${my - 0.6} C40 ${my - 3.6} 35 ${my - 4.6} 32 ${my - 2.4} Z`, fill: hairColour === base ? "#2b2a33" : hairColour }, head);
  //: One earring, a small hoop low on the left.
  if (!mini && style.features?.includes("earring")) make("circle", { cx: 6.5, cy: 39, r: 1.9, fill: "none", stroke: "#e0b43a", "stroke-width": 1.2 }, head);
  //: A plaster across the bridge of the nose.
  if (style.features?.includes("plaster")) {
    const plaster = make("g", { transform: "rotate(-16 32 34.5)" }, head);
    make("rect", { x: 27.8, y: 33, width: 8.4, height: 3.2, rx: 1.3, fill: "#f3dcb8", stroke: "#b89a6c", "stroke-width": 0.6 }, plaster);
    for (const dx of [-1.2, 1.2]) make("circle", { cx: 32 + dx, cy: 34.6, r: 0.35, fill: "#b89a6c" }, plaster);
  }
  //: A short beard along the jaw, leaving the mouth clear.
  if (style.accessories?.includes("shortbeard")) make("path", { d: `M10.5 ${my - 7} C10 ${my + 6} 20 ${my + 11} 32 ${my + 11} C44 ${my + 11} 54 ${my + 6} 53.5 ${my - 7} C51 ${my + 1} 46 ${my + 5.5} 41 ${my + 7.5} C37 ${my + 9} 27 ${my + 9} 23 ${my + 7.5} C18 ${my + 5.5} 13 ${my + 1} 10.5 ${my - 7} Z`, fill: hairColour, stroke: hairLine, "stroke-width": LW * 0.7, "stroke-linejoin": "round" }, head);
  if (!mini && (style.accessories?.includes("earrings") || creature?.earrings)) for (const sx of [-1, 1]) make("circle", { cx: 32 + sx * 27, cy: 38, r: 1.6, fill: "#f5c518", stroke: "#8a6d00", "stroke-width": 0.6 }, head);

  // --- the extras a mood brings ----------------------------------------------------
  const extras = [...(face.extras || []), ...(reading.intense ? face.louder || [] : [])].filter((extra) => !mini || ["tear", "tear2", "blush"].includes(extra));
  if (!mini && reading.flavours?.includes("doomed")) extras.push("sweat");
  //: The extras that float above the head's right move down beside it
  //: when something sits on the head, so a "zz" never lands on a crown.
  const hatted = worn.some((p) => NAME_MARK_HEAD_KINDS.includes(p)) || style.accessories?.some((bit) => NAME_MARK_HEAD_KINDS.includes(bit)) || creature?.gnomeHat;
  const fx = hatted ? 6 : 0;
  const fy = hatted ? 14 : 0;
  const drop = (x, y, cls) => make("path", { class: cls, d: `M${x} ${y - 3.2} C${x + 2.4} ${y} ${x + 2.4} ${y + 2.4} ${x} ${y + 2.4} C${x - 2.4} ${y + 2.4} ${x - 2.4} ${y} ${x} ${y - 3.2} Z`, fill: "#7cc4f0", stroke: "#3d86b8", "stroke-width": 0.7 }, head);
  if (extras.includes("tear")) drop(32 - spread - 1, eyeY + 7, "nm-tear");
  if (extras.includes("tear2")) drop(32 + spread + 1, eyeY + 7, "nm-tear nm-tear-late");
  if (extras.includes("sweat")) drop(52, 16, "nm-sweat");
  if (extras.includes("sweat2")) drop(12, 18, "nm-sweat");
  if (extras.includes("zz")) {
    const z = make("g", { class: "nm-z" }, head);
    stroke(`M${50 + fx} ${4 + fy} L${55 + fx} ${4 + fy} L${50 + fx} ${9 + fy} L${55 + fx} ${9 + fy}`, z, 1.3);
  }
  if (extras.includes("heart")) heart(54 + fx, 6 + fy, 3.4, "#e8364f", head, "nm-heart");
  if (extras.includes("spark")) star(55 + fx, 7 + fy, 4, "#f5c518", head, "nm-spark");
  if (extras.includes("question")) {
    const q = make("g", { class: "nm-q" }, head);
    stroke(`M${52 + fx} ${3 + fy} C${52 + fx} ${-1 + fy} ${58 + fx} ${-1 + fy} ${58 + fx} ${3 + fy} C${58 + fx} ${6 + fy} ${55 + fx} ${6 + fy} ${55 + fx} ${9 + fy}`, q, 1.6);
    make("circle", { cx: 55 + fx, cy: 12 + fy, r: 0.9, fill: NM_CHAR_INK }, q);
  }
  if (extras.includes("vein")) stroke("M47 11 L50 14 M50 11 L47 14 M49 9 L49 11 M52 12 L50 12", make("g", { class: "nm-vein" }, head), 1.2, "#e8364f");
  if (extras.includes("glint") || extras.includes("glint2")) star(38, my + 1, 1.8, "#ffffff", head, "nm-spark");
  if (extras.includes("stars")) for (const [x, y] of [[14, 6], [32, 0], [50, 6]]) star(x, y, 2.6, "#f5c518", head, "nm-spark nm-spark-late");
  if (extras.includes("bubble")) make("circle", { class: "nm-heart", cx: 44, cy: my + 2, r: 2.4, fill: "#cfe8ff", stroke: "#7cc4f0", "stroke-width": 0.7 }, head);
  if (extras.includes("drool")) drop(36, my + 6, "nm-sweat");
  if (extras.includes("thermometer")) {
    make("rect", { x: 34, y: my - 1, width: 9, height: 2, rx: 1, fill: "#ffffff", stroke: line, "stroke-width": 0.6, transform: `rotate(-18 34 ${my})` }, head);
    make("circle", { cx: 34.5, cy: my, r: 1.3, fill: "#e8364f" }, head);
  }

  // --- what it wears on its head and face --------------------------------------------
  const top = make("g", { class: "nmc-top" }, body);
  const props = worn;
  const eyewear = props.find((p) => NAME_MARK_EYEWEAR_KINDS.includes(p)) || (eyeStyle === "shades" ? "shades" : null);
  if (eyewear && eyes.length === 2) {
    const [lx, ly] = eyes[0];
    const [rx2] = eyes[1];
    const rim = { glasses: "#2b2a33", squareglasses: "#2b2a33", monocle: "#b8860b", goggles: "#6b4a2f", threed: "#f5f4ef", starglasses: "#e36fa6", heartglasses: "#e8364f", visor: "#3fd0e0", shades: "#1c1b22" }[eyewear] || "#2b2a33";
    //: On the face, not the crown: it goes with the head's tilt and turn
    //: (K14, the owner: "the sunglasses ... dont move with the face"). A
    //: figure in shades has no eyes drawn under them, so it has closed lids
    //: of its own, shown only asleep, when the shades go up (K25b).
    if (full && eyeStyle === "shades") {
      const lids = make("g", { class: "nmc-lids" }, head);
      for (const [x, y] of eyes) stroke(`M${x - 3.6} ${y - 0.6} Q${x} ${y + 3} ${x + 3.6} ${y - 0.6}`, lids, 2);
    }
    const g = make("g", { class: "nm-eyewear" }, head);
    if (eyewear === "visor") make("rect", { x: 9, y: ly - 5, width: 46, height: 10, rx: 5, fill: "#3fd0e0", "fill-opacity": 0.75, stroke: "#1b7f8c", "stroke-width": 1.2 }, g);
    else if (eyewear === "shades") {
      for (const x of [lx, rx2]) make("path", { d: `M${x - 6} ${ly - 3.5} L${x + 6} ${ly - 3.5} L${x + 5} ${ly + 3} Q${x} ${ly + 5.5} ${x - 5} ${ly + 3} Z`, fill: rim }, g);
      stroke(`M${lx + 6} ${ly - 3} L${rx2 - 6} ${ly - 3}`, g, 1.4, rim);
      stroke(`M${lx - 3} ${ly - 1.5} L${lx - 1} ${ly - 2.5}`, g, 1, "#ffffff");
    } else if (eyewear === "monocle") {
      make("circle", { cx: rx2, cy: ly, r: 6, fill: "#ffffff", "fill-opacity": 0.15, stroke: rim, "stroke-width": 1.4 }, g);
      stroke(`M${rx2 + 4} ${ly + 5} Q${rx2 + 6} ${ly + 14} ${rx2 + 1} ${ly + 20}`, g, 0.8, rim);
    } else if (eyewear === "starglasses" || eyewear === "heartglasses") {
      for (const x of [lx, rx2]) (eyewear === "starglasses" ? star(x, ly, 7, rim, g) : heart(x, ly, 5.2, rim, g)).setAttribute("fill-opacity", "0.85");
      stroke(`M${lx + 5} ${ly - 1} L${rx2 - 5} ${ly - 1}`, g, 1.2, rim);
    } else {
      const square = eyewear === "squareglasses";
      const lens = eyewear === "threed" ? ["#e8364f", "#3b82f6"] : eyewear === "goggles" ? ["#9fd8ef", "#9fd8ef"] : ["#ffffff", "#ffffff"];
      if (eyewear === "goggles") stroke(`M4 ${ly} L60 ${ly}`, g, 3, "#6b4a2f");
      [lx, rx2].forEach((x, i) => {
        if (square) make("rect", { x: x - 6, y: ly - 5, width: 12, height: 10, rx: 2.5, fill: lens[i], "fill-opacity": 0.18, stroke: rim, "stroke-width": 1.5 }, g);
        else make("circle", { cx: x, cy: ly, r: 6.2, fill: lens[i], "fill-opacity": eyewear === "threed" ? 0.55 : 0.18, stroke: rim, "stroke-width": eyewear === "goggles" ? 2.4 : 1.5 }, g);
      });
      stroke(`M${lx + 6} ${ly - 0.5} Q32 ${ly - 3} ${rx2 - 6} ${ly - 0.5}`, g, 1.4, rim);
    }
  }
  //: A patch and a mask are on the face too, with the eyes and mouth they
  //: cover; hats stay on the crown, which does not turn (K14).
  if (props.includes("eyepatch") && eyes.length === 2) {
    const [x, y] = eyes[1];
    stroke(`M8 ${y - 9} L56 ${y + 2}`, head, 1.2, "#1c1b22");
    make("ellipse", { cx: x, cy: y, rx: 5.6, ry: 5, fill: "#1c1b22" }, head);
  }
  if (props.includes("ninjamask")) {
    make("path", { d: `M6 ${my - 5} C12 ${my - 7} 52 ${my - 7} 58 ${my - 5} L56 ${my + 12} C44 ${my + 18} 20 ${my + 18} 8 ${my + 12} Z`, fill: "#2b2a33", stroke: nmLineFor("#2b2a33"), "stroke-width": LW }, head);
    make("path", { d: "M6 14 C16 10 48 10 58 14 L58 19 C48 16 16 16 6 19 Z", fill: "#2b2a33" }, head);
  }
  const headwear = props.find((p) => NAME_MARK_HAT_KINDS.includes(p) || ["halo", "horns", "antenna", "headphones", "helmet"].includes(p));
  const gold = "#f5c518";
  const goldLine = "#9a7300";
  if (props.includes("halo")) make("ellipse", { cx: 32, cy: -6, rx: 14, ry: 3.6, fill: "none", stroke: gold, "stroke-width": 2.4 }, top);
  if (props.includes("horns")) for (const sx of [-1, 1]) make("path", { d: `M${32 + sx * 14} 8 C${32 + sx * 16} 0 ${32 + sx * 20} -3 ${32 + sx * 22} -5 C${32 + sx * 22} 2 ${32 + sx * 21} 6 ${32 + sx * 19} 10 Z`, fill: "#c0392b", stroke: "#6e1f17", "stroke-width": LW, "stroke-linejoin": "round" }, top);
  if (props.includes("antenna") || beast?.antenna) {
    stroke("M32 5 L32 -8", top, 1.6, line);
    make("circle", { cx: 32, cy: -9, r: 3, fill: "#e8364f", stroke: "#7d1426", "stroke-width": 1 }, top);
  }
  if (beast?.antennae) for (const sx of [-1, 1]) {
    stroke(`M${32 + sx * 6} 6 Q${32 + sx * 10} -4 ${32 + sx * 14} -6`, top, 1.4, "#2b2a28");
    make("circle", { cx: 32 + sx * 14, cy: -6, r: 2, fill: "#2b2a28" }, top);
  }
  if (beast?.smallHorns || beast?.unihorn || beast?.bullHorns || beast?.antlers) {
    if (beast.unihorn) make("path", { d: "M28 6 L32 -14 L36 6 Z", fill: gold, stroke: goldLine, "stroke-width": LW, "stroke-linejoin": "round" }, top);
    if (beast.smallHorns) for (const sx of [-1, 1]) make("path", { d: `M${32 + sx * 10} 7 L${32 + sx * 13} -2 L${32 + sx * 16} 8 Z`, fill: beast.smallHorns, stroke: nmMix(beast.smallHorns, "#000000", 0.4), "stroke-width": LW, "stroke-linejoin": "round" }, top);
    if (beast.bullHorns) for (const sx of [-1, 1]) make("path", { d: `M${32 + sx * 20} 12 C${32 + sx * 30} 10 ${32 + sx * 32} 0 ${32 + sx * 28} -6 C${32 + sx * 28} 2 ${32 + sx * 24} 6 ${32 + sx * 18} 7 Z`, fill: "#e8dcc0", stroke: "#7a6a48", "stroke-width": LW, "stroke-linejoin": "round" }, top);
    if (beast.antlers) for (const sx of [-1, 1]) stroke(`M${32 + sx * 10} 6 L${32 + sx * 14} -8 M${32 + sx * 12.5} -3 L${32 + sx * 19} -6 M${32 + sx * 13.6} -6 L${32 + sx * 10} -12`, top, 2.4, beast.antlers);
  }
  if (beast?.tuft) outlined("M30 5 C28 -2 34 -3 32 -7", base, 2.4, top);
  if (creature?.flameCrest) for (const [x, hgt, c] of [[26, -6, "#f28e2c"], [32, -12, "#edc949"], [38, -6, "#e15759"]]) make("path", { d: `M${x - 4} 6 C${x - 4} ${hgt + 6} ${x} ${hgt + 2} ${x} ${hgt} C${x + 2} ${hgt + 4} ${x + 4} ${hgt + 6} ${x + 4} 6 Z`, fill: c }, top);
  if (worn.includes("hood")) {
    //: A hood: its shell behind the head (drawn into the back layer, so it
    //: covers long hair), its rim in front over the hair's edge.
    const hood = pair.cloth[((style.outfitColour || 0) + 1) % pair.cloth.length];
    const hoodLine = nmLineFor(hood);
    back.appendChild(make("path", { d: "M-1 38 C-3 10 14 -5 32 -5 C50 -5 67 10 65 38 C64 47 58 53 52 55 L12 55 C6 53 0 47 -1 38 Z", fill: nmMix(hood, "#000000", 0.12), stroke: hoodLine, "stroke-width": LW, "stroke-linejoin": "round" }));
    make("path", { class: "nm-hat", d: "M3 46 C-1 14 14 -1 32 -1 C50 -1 65 14 61 46", fill: "none", stroke: hoodLine, "stroke-width": 5 + LW * 2, "stroke-linecap": "round" }, top);
    make("path", { d: "M3 46 C-1 14 14 -1 32 -1 C50 -1 65 14 61 46", fill: "none", stroke: hood, "stroke-width": 5, "stroke-linecap": "round" }, top);
  }
  if (creature?.gnomeHat || headwear) {
    const kind = creature?.gnomeHat ? "gnome" : headwear;
    const hat = make("g", { class: "nm-hat" }, top);
    const hatColour = pair.cloth[((style.outfitColour || 0) + 1) % pair.cloth.length];
    const hatLine = nmLineFor(hatColour);
    const fill = (d, colour = hatColour, lineColour = hatLine) => make("path", { d, fill: colour, stroke: lineColour, "stroke-width": LW, "stroke-linejoin": "round" }, hat);
    if (kind === "hat") {
      fill("M18 8 C24 -4 30 -18 40 -22 C36 -12 44 -2 48 8 Z", "#5b4bb5", "#2d2366");
      make("ellipse", { cx: 32, cy: 8, rx: 24, ry: 4.4, fill: "#5b4bb5", stroke: "#2d2366", "stroke-width": LW }, hat);
      star(31, -2, 2.4, gold, hat);
      star(38, -10, 1.6, gold, hat);
    } else if (kind === "gnome") {
      fill("M12 12 C18 0 28 -20 38 -24 C36 -12 46 0 52 12 Z", "#e2574c", "#7d231c");
    } else if (kind === "chefhat") {
      for (const [x, y] of [[20, -4], [32, -9], [44, -4]]) make("circle", { cx: x, cy: y, r: 8, fill: "#ffffff", stroke: "#9aa0a6", "stroke-width": LW }, hat);
      fill("M16 -2 L48 -2 L47 9 C38 7 26 7 17 9 Z", "#ffffff", "#9aa0a6");
    } else if (kind === "cowboy") {
      fill("M20 6 C20 -6 26 -8 32 -4 C38 -8 44 -6 44 6 Z", "#a0714f", "#4a3020");
      make("path", { d: "M2 8 C10 14 54 14 62 8 C58 4 50 7 32 7 C14 7 6 4 2 8 Z", fill: "#a0714f", stroke: "#4a3020", "stroke-width": LW, "stroke-linejoin": "round" }, hat);
      make("path", { d: "M20 4 L44 4", stroke: "#4a3020", "stroke-width": 2 }, hat);
    } else if (kind === "partyhat") {
      fill("M22 8 L33 -18 L44 8 Z", "#e36fa6", "#7a1f4f");
      stroke("M26 -1 L40 -1 M29 -8 L37 -8", hat, 1.6, "#f5c518");
      make("circle", { cx: 33, cy: -19, r: 3, fill: gold, stroke: goldLine, "stroke-width": 1 }, hat);
    } else if (kind === "crown") {
      fill("M16 9 L14 -6 L22 1 L32 -10 L42 1 L50 -6 L48 9 Z", gold, goldLine);
      for (const x of [22, 32, 42]) make("circle", { cx: x, cy: 5, r: 1.6, fill: "#e8364f" }, hat);
    } else if (kind === "tiara") {
      fill("M20 8 C22 2 28 -2 32 -6 C36 -2 42 2 44 8 C40 5 24 5 20 8 Z", "#dfe6ee", "#7a8796");
      make("circle", { cx: 32, cy: 0, r: 1.8, fill: "#e36fa6" }, hat);
    } else if (kind === "tricorn") {
      fill("M4 8 C14 -6 22 -8 32 -4 C42 -8 50 -6 60 8 C48 4 16 4 4 8 Z", "#2b2a33", nmLineFor("#2b2a33"));
      make("circle", { cx: 32, cy: 1, r: 2.4, fill: "#f5f4ef" }, hat);
    } else if (kind === "cap") {
      fill("M9 12 C9 -2 20 -6 32 -6 C44 -6 55 -2 55 12 Z");
      make("path", { d: "M40 10 C50 8 62 10 66 14 C58 16 46 14 40 12 Z", fill: hatColour, stroke: hatLine, "stroke-width": LW, "stroke-linejoin": "round" }, hat);
      make("circle", { cx: 32, cy: -6, r: 1.6, fill: hatLine }, hat);
    } else if (kind === "beanie") {
      fill("M8 13 C8 -4 20 -8 32 -8 C44 -8 56 -4 56 13 Z");
      make("rect", { x: 7, y: 8, width: 50, height: 7, rx: 3.5, fill: nmMix(hatColour, "#ffffff", 0.3), stroke: hatLine, "stroke-width": LW }, hat);
      make("circle", { cx: 32, cy: -10, r: 4, fill: "#f5f4ef", stroke: "#9aa0a6", "stroke-width": LW }, hat);
    } else if (kind === "flowercrown") {
      for (const [x, y, c] of [[12, 12, "#e36fa6"], [21, 5, "#f5c518"], [32, 3, "#ffffff"], [43, 5, "#e36fa6"], [52, 12, "#f5c518"]]) {
        for (let i = 0; i < 5; i += 1) {
          const a = (Math.PI * 2 * i) / 5;
          make("circle", { cx: x + Math.cos(a) * 2.2, cy: y + Math.sin(a) * 2.2, r: 1.9, fill: c, stroke: nmMix(c, "#000000", 0.3), "stroke-width": 0.5 }, hat);
        }
        make("circle", { cx: x, cy: y, r: 1.2, fill: "#f28e2c" }, hat);
      }
    } else if (kind === "bandana" || kind === "headband") {
      const band = kind === "bandana" ? "#e2574c" : "#e8364f";
      //: Across the forehead, clear of the brows (at 21.5) and the eyes.
      make("path", { d: "M5 16 C14 9 50 9 59 16 L59 21 C50 14 14 14 5 21 Z", fill: band, stroke: nmMix(band, "#000000", 0.4), "stroke-width": LW }, hat);
      make("path", { d: "M58 16 L66 12 L64 20 Z M58 19 L67 23 L60 25 Z", fill: band, stroke: nmMix(band, "#000000", 0.4), "stroke-width": 1 }, hat);
    } else if (kind === "headphones") {
      make("path", { d: "M8 30 C6 6 58 6 56 30", fill: "none", stroke: "#2b2a33", "stroke-width": 3 }, hat);
      for (const x of [4, 60]) make("rect", { x: x - 4, y: 24, width: 8, height: 13, rx: 4, fill: "#e2574c", stroke: "#2b2a33", "stroke-width": LW }, hat);
    } else if (kind === "helmet") {
      make("circle", { cx: 32, cy: 28, r: 32, fill: "#cfe8ff", "fill-opacity": 0.22, stroke: "#9aa0a6", "stroke-width": 2 }, hat);
      stroke("M12 12 Q18 6 24 5", hat, 1.6, "#ffffff");
    }
  }
  if (style.accessories?.includes("bow") || props.includes("bow")) {
    const g = make("g", { class: "nm-bow" }, top);
    make("path", { d: "M44 4 L38 0 L38 8 Z M44 4 L50 0 L50 8 Z", fill: "#e36fa6", stroke: "#7a1f4f", "stroke-width": 1, "stroke-linejoin": "round" }, g);
    make("circle", { cx: 44, cy: 4, r: 1.6, fill: "#e36fa6", stroke: "#7a1f4f", "stroke-width": 0.8 }, g);
  }
  if (props.includes("sushiclip")) {
    //: Sushi in the hair: the same nigiri, small, pinned at the crown's
    //: right, where a bow would sit.
    nameMarkSushi(make, shape, make("g", { class: "nm-clip", transform: "translate(47 7) rotate(-24) scale(0.66)" }, top));
  }
  if (style.accessories?.includes("flowerclip")) {
    for (let i = 0; i < 5; i += 1) make("circle", { cx: 14 + Math.cos(i * 1.26) * 2.2, cy: 12 + Math.sin(i * 1.26) * 2.2, r: 1.8, fill: "#ffffff", stroke: "#c9c3b8", "stroke-width": 0.5 }, top);
    make("circle", { cx: 14, cy: 12, r: 1.2, fill: "#f5c518" }, top);
  }

  // --- arms in front, and the thing in its hand (the figure only) ------------------
  if (full) {
    const armColour = base;
    const claw = beast?.claws;
    const arms = [["l", "M13.5 56 Q9 61 7.5 67"], ["r", "M50.5 56 Q55 61 56.5 67"]];
    for (const [side, d] of arms) {
      const arm = outlined(d, armColour, 6, body, { class: `nmb-arm nmb-arm-${side}`, "data-pivot": side === "l" ? "13.5 56" : "50.5 56" });
      if (claw) shape("path", { d: side === "l" ? "M7.5 67 L2 70 L6 72 L3 75 L10 72 Z" : "M56.5 67 L62 70 L58 72 L61 75 L54 72 Z", fill: nmMix(base, "#000000", 0.1) }, arm);
      if (side === "r" && reading.hand) nameCharacterHeld(reading.hand, arm, { make, shape, stroke, outlined, star, heart, base, line });
      //: The hand slots: a bell and a lantern held up in the right hand,
      //: the unplugged cable in the left.
      if (side === "r") {
        const note = make("g", { class: "nmp nmp-note" }, arm);
        make("rect", { x: 51, y: 60, width: 11, height: 13, rx: 1.5, fill: "#fffbe6", stroke: "#b8a55a", "stroke-width": LW, transform: "rotate(-10 56.5 66.5)" }, note);
        for (const ly of [64, 67, 70]) make("path", { d: `M53.5 ${ly} L59.5 ${ly - 1}`, stroke: "#c9b56a", "stroke-width": 0.8, "stroke-linecap": "round" }, note);
        const bell = make("g", { class: "nmp nmp-bell" }, arm);
        make("path", { d: "M51.5 73 C51.5 64 61.5 64 61.5 73 L63 75 L50 75 Z", fill: "#f5c518", stroke: "#8a6d00", "stroke-width": LW, "stroke-linejoin": "round" }, bell);
        make("circle", { cx: 56.5, cy: 77, r: 1.6, fill: "#8a6d00" }, bell);
        const lantern = make("g", { class: "nmp nmp-lantern" }, arm);
        make("circle", { class: "nmp-lantern-glow", cx: 56.5, cy: 74, r: 9, fill: "#ffd84a", "fill-opacity": 0.35 }, lantern);
        make("rect", { x: 52.5, y: 69, width: 8, height: 10, rx: 2, fill: "#ffe9a3", stroke: "#6b4a2f", "stroke-width": LW }, lantern);
        make("path", { d: "M54 69 C54 65 59 65 59 69", fill: "none", stroke: "#6b4a2f", "stroke-width": 1.2 }, lantern);
      } else {
        const cable = make("g", { class: "nmp nmp-cable" }, arm);
        make("path", { d: "M7 68 C4 76 12 82 6 90", fill: "none", stroke: "#33323a", "stroke-width": 1.6, "stroke-linecap": "round" }, cable);
        make("rect", { x: 3, y: 64, width: 8, height: 6, rx: 1.4, fill: "#6b7a8f", stroke: "#33323a", "stroke-width": 1 }, cable);
        for (const x of [5, 9]) make("path", { d: `M${x} 64 L${x} 61`, stroke: "#9aa0a6", "stroke-width": 1.2 }, cable);
      }
    }
    //: The head slots: headphones and a nightcap on top, reading glasses on
    //: the face (in the face group, so they follow the eyes).
    const phones = make("g", { class: "nmp nmp-headphones" }, top);
    make("path", { d: "M7 30 C5 3 59 3 57 30", fill: "none", stroke: "#2b2a33", "stroke-width": 3.2, "stroke-linecap": "round" }, phones);
    for (const x of [5, 59]) make("rect", { x: x - 4.5, y: 23, width: 9, height: 14, rx: 4.5, fill: "#e2574c", stroke: "#2b2a33", "stroke-width": LW }, phones);
    //: Not over a hat it wears already: two hats at once (K14).
    if (capSlot) {
      const cap = make("g", { class: "nmp nmp-nightcap" }, top);
      make("path", { d: "M9 15 C13 1 30 -5 42 -1 C52 3 59 11 63 24 L57 22 C51 12 41 9 31 11 C23 12 16 14 9 15 Z", fill: "#4f7fd9", stroke: "#23407a", "stroke-width": LW, "stroke-linejoin": "round" }, cap);
      make("path", { d: "M8 16 C18 9 46 7 58 14", fill: "none", stroke: "#f5f4ef", "stroke-width": 4, "stroke-linecap": "round" }, cap);
      make("circle", { cx: 63, cy: 24, r: 3.4, fill: "#f5f4ef", stroke: "#9aa0a6", "stroke-width": 1 }, cap);
    }
    //: Not over glasses it wears already: two pairs at once (K14).
    if (eyes.length === 2 && !eyewear) {
      const glasses = make("g", { class: "nmp nmp-glasses" }, head);
      for (const [x, y] of eyes) make("circle", { cx: x, cy: y, r: 5.4, fill: "#ffffff", "fill-opacity": 0.18, stroke: "#6b4a2f", "stroke-width": 1.3 }, glasses);
      stroke(`M${eyes[0][0] + 5.4} ${eyes[0][1]} Q32 ${eyes[0][1] - 2.4} ${eyes[1][0] - 5.4} ${eyes[1][1]}`, glasses, 1.2, "#6b4a2f");
    }
  }
  //: **What it holds shows in the head mark too** (INBOX 426 f, the owner:
  //: "they still look bland and are missing a lot of the flare they used to
  //: have"). The first faces drew the held thing in a hand raised at the
  //: disc's lower right (a wand, a pickaxe, a mug); the head-only mark had
  //: dropped it, so a name that asked for one showed nothing of it outside
  //: the companion. The same hand and the same drawing as the figure's,
  //: four-fifths size, rising from the mark's lower right edge. Not in the
  //: small mark, which keeps its one cue.
  if (!full && !mini && reading.hand) {
    const hand = make("g", { class: "nmc-mark-hand", transform: "translate(4 -6) scale(0.82)" }, svg);
    outlined("M61 82 Q59 74 56.5 67", base, 6, hand);
    nameCharacterHeld(reading.hand, hand, { make, shape, stroke, outlined, star, heart, base, line });
  }
  svg.dataset.nmChar = "1";
  //: What it holds, so a pose that needs both hands (hanging) can keep the
  //: holding hand down and the thing in it on show.
  if (reading.hand) svg.dataset.nmHeld = reading.hand;
  return svg;
}

//: A nigiri about (0, 0), about 18 units wide: held in a hand or, scaled
//: down, pinned in the hair.
function nameMarkSushi(make, shape, g) {
  shape("path", { d: "M-8 1.5 C-9 -3 9 -3 8 1.5 C7 4.5 -7 4.5 -8 1.5 Z", fill: "#fbf7ee" }, g);
  shape("path", { d: "M-9.5 -1 C-6 -8 6 -8.5 9.5 -1.5 C5 0.6 -5 0.6 -9.5 -1 Z", fill: "#f58a63" }, g);
  for (const x of [-4.5, -0.5, 4]) make("path", { d: `M${x} -5.6 L${x + 1.6} -1.2`, stroke: "#ffe1d2", "stroke-width": 0.9, "stroke-linecap": "round" }, g);
  make("rect", { x: -1.7, y: -6.4, width: 3.4, height: 10.6, rx: 0.8, fill: "#24352b" }, g);
}

//: The thing in its right hand, drawn about the hand at (56.5, 67). Every
//: kind the name can ask for has a shape; a gesture raises the arm.
function nameCharacterHeld(kind, arm, t) {
  const { make, shape, stroke, outlined, star, heart } = t;
  const hx = 57;
  const hy = 67;
  const g = make("g", { class: "nmc-held" }, arm);
  const wood = "#8a5a2b";
  const steel = "#c9d1d9";
  const pole = (x1, y1, x2, y2, colour = wood, width = 2) => outlined(`M${x1} ${y1} L${x2} ${y2}`, colour, width, g);
  switch (kind) {
    case "mug":
      shape("rect", { x: hx - 1, y: hy - 7, width: 8, height: 9, rx: 2, fill: "#f5f4ef" }, g);
      stroke(`M${hx + 7} ${hy - 5} C${hx + 11} ${hy - 5} ${hx + 11} ${hy} ${hx + 7} ${hy}`, g, 1.4, "#6b7a8f");
      make("path", { class: "nm-steam", d: `M${hx + 2} ${hy - 10} Q${hx + 4} ${hy - 13} ${hx + 2} ${hy - 16}`, fill: "none", stroke: "#9aa0a6", "stroke-width": 1, "stroke-linecap": "round" }, g);
      break;
    case "beer":
      shape("rect", { x: hx - 1, y: hy - 9, width: 8, height: 11, rx: 1.5, fill: "#f0b429" }, g);
      make("path", { d: `M${hx - 1.5} ${hy - 9} C${hx} ${hy - 13} ${hx + 7} ${hy - 13} ${hx + 7.5} ${hy - 9} Z`, fill: "#ffffff" }, g);
      break;
    case "wine":
      shape("path", { d: `M${hx - 2} ${hy - 12} L${hx + 6} ${hy - 12} C${hx + 6} ${hy - 6} ${hx - 2} ${hy - 6} ${hx - 2} ${hy - 12} Z`, fill: "#8e1b3a" }, g);
      stroke(`M${hx + 2} ${hy - 7} L${hx + 2} ${hy - 1} M${hx - 1} ${hy - 1} L${hx + 5} ${hy - 1}`, g, 1, "#9aa0a6");
      break;
    case "book":
      shape("rect", { x: hx - 2, y: hy - 8, width: 10, height: 12, rx: 1.2, fill: "#3b6fb6" }, g);
      stroke(`M${hx} ${hy - 6} L${hx + 6} ${hy - 6}`, g, 1, "#ffffff");
      break;
    case "phone":
      shape("rect", { x: hx - 1, y: hy - 10, width: 7, height: 12, rx: 1.6, fill: "#2b2a33" }, g);
      make("rect", { x: hx, y: hy - 9, width: 5, height: 9, rx: 0.8, fill: "#7cc4f0" }, g);
      break;
    case "flower":
      pole(hx, hy, hx + 2, hy - 12, "#59a14f", 1.2);
      for (let i = 0; i < 5; i += 1) make("circle", { cx: hx + 2 + Math.cos(i * 1.26) * 2.6, cy: hy - 14 + Math.sin(i * 1.26) * 2.6, r: 2.2, fill: "#e36fa6", stroke: "#7a1f4f", "stroke-width": 0.5 }, g);
      make("circle", { cx: hx + 2, cy: hy - 14, r: 1.5, fill: "#f5c518" }, g);
      break;
    case "balloon":
      stroke(`M${hx} ${hy} Q${hx + 4} ${hy - 12} ${hx + 2} ${hy - 22}`, g, 0.8, "#6b7a8f");
      shape("ellipse", { class: "nm-balloon", cx: hx + 2, cy: hy - 28, rx: 6, ry: 7.4, fill: "#e2574c" }, g);
      break;
    case "pizza":
      shape("path", { d: `M${hx - 3} ${hy - 4} L${hx + 11} ${hy - 8} L${hx + 4} ${hy + 5} Z`, fill: "#f5c542" }, g);
      for (const [dx, dy] of [[4, -4], [6, 0]]) make("circle", { cx: hx + dx, cy: hy + dy, r: 1.2, fill: "#c0392b" }, g);
      break;
    case "donut":
      shape("circle", { cx: hx + 3, cy: hy - 4, r: 6, fill: "#e8a0c0" }, g);
      make("circle", { cx: hx + 3, cy: hy - 4, r: 2, fill: "#c86a94", stroke: "#7a1f4f", "stroke-width": 1 }, g);
      break;
    case "sushi":
      //: A nigiri held up: a rice pillow, a salmon slice with its pale
      //: lines, a band of nori round the middle.
      nameMarkSushi(make, shape, make("g", { transform: `translate(${hx + 1.5} ${hy - 4}) rotate(-14)` }, g));
      break;
    case "sword":
      pole(hx, hy + 2, hx + 3, hy - 22, steel, 2.4);
      stroke(`M${hx - 3} ${hy - 2} L${hx + 5} ${hy - 1}`, g, 2, "#8a5a2b");
      break;
    case "spear":
    case "trident":
      pole(hx - 1, hy + 10, hx + 2, hy - 24);
      if (kind === "spear") shape("path", { d: `M${hx + 2} ${hy - 30} L${hx - 1} ${hy - 23} L${hx + 5} ${hy - 23} Z`, fill: steel }, g);
      else stroke(`M${hx - 3} ${hy - 30} L${hx - 3} ${hy - 24} L${hx + 7} ${hy - 24} L${hx + 7} ${hy - 30} M${hx + 2} ${hy - 32} L${hx + 2} ${hy - 24}`, g, 1.6, "#f5c518");
      break;
    case "wand":
      pole(hx - 1, hy + 2, hx + 6, hy - 12, "#2b2a33", 1.6);
      star(hx + 7, hy - 14, 3.4, "#f5c518", g, "nm-spark");
      break;
    case "magnifier":
      pole(hx, hy, hx + 4, hy - 6, "#2b2a33", 1.6);
      make("circle", { cx: hx + 7, cy: hy - 10, r: 4.6, fill: "#cfe8ff", "fill-opacity": 0.5, stroke: "#2b2a33", "stroke-width": 1.6 }, g);
      break;
    case "mic":
      pole(hx, hy, hx + 2, hy - 7, "#2b2a33", 2);
      shape("circle", { cx: hx + 2.5, cy: hy - 10, r: 3.4, fill: "#9aa0a6" }, g);
      break;
    case "controller":
      shape("path", { d: `M${hx - 5} ${hy - 6} C${hx - 7} ${hy + 2} ${hx - 2} ${hy + 3} ${hx} ${hy} L${hx + 6} ${hy} C${hx + 8} ${hy + 3} ${hx + 13} ${hy + 2} ${hx + 11} ${hy - 6} Z`, fill: "#33323a" }, g);
      make("circle", { cx: hx + 7, cy: hy - 3.5, r: 1, fill: "#e2574c" }, g);
      break;
    case "paintbrush":
      pole(hx, hy + 2, hx + 4, hy - 12);
      shape("path", { d: `M${hx + 3} ${hy - 12} L${hx + 6} ${hy - 12} L${hx + 5} ${hy - 18} Z`, fill: "#4e79a7" }, g);
      break;
    case "hammer":
    case "axe":
    case "pickaxe":
      pole(hx, hy + 4, hx + 2, hy - 16);
      if (kind === "hammer") shape("rect", { x: hx - 4, y: hy - 21, width: 12, height: 6, rx: 1.2, fill: "#6b7a8f" }, g);
      else if (kind === "axe") shape("path", { d: `M${hx + 2} ${hy - 16} C${hx + 10} ${hy - 20} ${hx + 12} ${hy - 10} ${hx + 2} ${hy - 10} Z`, fill: steel }, g);
      else shape("path", { d: `M${hx - 8} ${hy - 14} C${hx - 2} ${hy - 22} ${hx + 6} ${hy - 22} ${hx + 12} ${hy - 14} C${hx + 6} ${hy - 18} ${hx - 2} ${hy - 18} ${hx - 8} ${hy - 14} Z`, fill: "#4fd1c5" }, g);
      break;
    case "fishingrod":
      pole(hx, hy + 2, hx + 10, hy - 24, wood, 1.4);
      stroke(`M${hx + 10} ${hy - 24} L${hx + 12} ${hy - 6}`, g, 0.6, "#9aa0a6");
      break;
    case "bow":
      stroke(`M${hx + 2} ${hy - 16} C${hx + 12} ${hy - 8} ${hx + 12} ${hy + 4} ${hx + 2} ${hy + 10}`, g, 1.8, wood);
      stroke(`M${hx + 2} ${hy - 16} L${hx + 2} ${hy + 10}`, g, 0.6, "#dcdcdc");
      break;
    case "blaster":
      shape("path", { d: `M${hx - 3} ${hy - 6} L${hx + 11} ${hy - 6} L${hx + 11} ${hy - 2} L${hx + 3} ${hy - 2} L${hx + 1} ${hy + 3} L${hx - 2} ${hy + 3} Z`, fill: "#7b61c4" }, g);
      break;
    case "tableflip":
      shape("rect", { x: hx + 1, y: hy - 16, width: 12, height: 3, rx: 1, fill: wood, transform: `rotate(-35 ${hx + 7} ${hy - 14})` }, g);
      break;
    case "wave":
    case "thumbsup":
    case "peace":
      arm.classList.add("nmc-raised");
      if (kind === "thumbsup") shape("ellipse", { cx: hx + 1, cy: hy - 4, rx: 1.6, ry: 3, fill: t.base }, g);
      if (kind === "peace") shape("ellipse", { cx: hx + 1, cy: hy - 4, rx: 1.3, ry: 3, fill: t.base }, g);
      if (kind === "peace") shape("ellipse", { cx: hx - 2, cy: hy - 3.5, rx: 1.3, ry: 3, fill: t.base, transform: `rotate(-20 ${hx - 2} ${hy - 3.5})` }, g);
      break;
    default:
      heart(hx + 2, hy - 4, 2.6, "#e8364f", g);
  }
}


// --- what a face does when you meet it ------------------------------------
//: The owner: "maybe the eyes and heads can tilt slightly to follow the
//: user's mouse if toggled?? and they can do something if clicked?? can
//: there also be a way to expand them or have them sit in the corner of the
//: screen ... but it has to be movable or hidable ... so it doesnt get
//: annoying". Four pieces, each behind its own Appearance setting where it
//: could get in the way: a click reaction, a large viewer, eyes that follow
//: the pointer, and a companion in the corner (off until asked for).

//: What a face says when it is poked, by mood. No exclamation marks: the
//: app's copy rule holds for the faces too.
const NAME_MARK_LINES = {
  happy: ["Hi there.", "Good to see you."], excited: ["Let's go.", "Ooh, what are we doing?"],
  sad: ["It's fine. I'm fine.", "..."], angry: ["Hmph.", "What now?"], dramatic: ["Alas.", "The drama of it all."],
  surprised: ["Oh.", "You startled me."], sleepy: ["Five more minutes.", "zzz…"], nervous: ["Is it the deadline?", "Um. Hi."],
  sly: ["I know things.", "Heh."], calm: ["Breathe.", "All is well."], serious: ["Focus.", "Back to work."],
  confused: ["Wait, what?", "Which tab was I on?"], hungry: ["Is it lunch yet?", "Snack break?"], cool: ["Sup.", "Stay cool."],
  love: ["You're doing great.", "Proud of you."], laughing: ["Ha. Good one.", "Stop, I can't."], unimpressed: ["Meh.", "Sure."],
  dizzy: ["Everything is spinning.", "Whoa."], uwu: ["Hewwo.", "Hi hi."], evil: ["Muahaha.", "All according to plan."],
  sick: ["I need soup.", "Achoo."], dead: ["Tell my notes I loved them.", "x_x"], starstruck: ["Wow.", "Amazing."],
  cute: ["Hi.", "Boop."], drunk: ["Heyyy.", "Who moved the floor."], greedy: ["Time is money.", "Stonks."],
};

function nameMarkLine(seed) {
  const reading = nameMood(seed);
  const lines = NAME_MARK_LINES[reading.mood] || ["Hello.", "Need anything?", "Still here."];
  return lines[Math.floor(Math.random() * lines.length)];
}

//: A face drawn to always move (the viewer, the companion, the dashboard):
//: its wrapper is what the CSS reads, not the Avatar animation setting,
//: which is for the faces that sit in lists. Off and Reduce motion still win.
function nameMarkLive(seed, size) {
  const holder = document.createElement("span");
  holder.className = "nm-live";
  holder.appendChild(nameMark(seed, size));
  return holder;
}

//: A poke: a hop and a spin. The class comes off when the animation ends.
function nameMarkReact(svg) {
  if (!svg) return;
  svg.classList.remove("nm-react");
  void svg.getBoundingClientRect();
  svg.classList.add("nm-react");
  setTimeout(() => svg.classList.remove("nm-react"), 800);
}

//: A speech bubble beside a face, for a moment.
function nameMarkSay(anchor, text) {
  if (!anchor) return;
  anchor.querySelector(".nm-say")?.remove();
  const bubble = document.createElement("span");
  bubble.className = "nm-say";
  bubble.setAttribute("role", "status");
  bubble.textContent = text;
  anchor.appendChild(bubble);
  //: Kept inside the window: a face at the edge (the companion at the
  //: right) used to say half its line off screen.
  const box = bubble.getBoundingClientRect();
  const shift = Math.max(0, box.right - (innerWidth - 8)) || -Math.max(0, 8 - box.left);
  if (shift) bubble.style.left = `calc(50% - ${Math.ceil(shift)}px)`;
  setTimeout(() => bubble.remove(), 2600);
}

//: How long after it arrives in the view a pointer it landed under is not
//: yet a hover (the view's fit runs over its first two frames).
const NMB_VISIT_SETTLE_MS = 700;

//: **The larger faces have a life of their own too** (the owner: "my popup
//: character doesnt really have much expression, same with when it is a
//: profile avatar and only gets it if it is an active companion"). One
//: shared timer, every 5 to 10 seconds, picks one face that is on screen
//: and at least `NM_IDLE_MIN` px (the large view, the profile head, persona
//: cards, the preview; never a list's small marks) and plays one small act
//: on it: a glance, a double blink, a hop, a wave in the large view. The
//: timer stops when there is nothing to animate and is started again when
//: a large face comes into view or the large view opens. Each act is a
//: short Web Animation on a part the face already has (its eyes, its
//: blinks, its arm), so nothing restyles the page. Off with Avatar
//: animation off, Reduce motion, the companion's Reduce actions set to off,
//: or the matching switch in What it does.
const NM_IDLE_MIN = 48;
let nameMarkIdleTimer = 0;
function nameMarkIdleWake() {
  if (!nameMarkIdleTimer) nameMarkIdleTimer = setTimeout(nameMarkIdleTick, 3000 + Math.random() * 3000);
}
function nameMarkIdleQuiet() {
  const root = document.documentElement;
  return root.dataset.avatarMotion === "off" || root.dataset.motion === "reduced"
    || (typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches)
    || nameMarkBuddyActions() === "off";
}
function nameMarkIdleTick() {
  nameMarkIdleTimer = 0;
  if (nameMarkIdleQuiet()) return;
  if (document.hidden) {
    document.addEventListener("visibilitychange", nameMarkIdleWake, { once: true });
    return;
  }
  const viewer = document.querySelector(".nm-viewer .nm-viewer-figure");
  const big = viewer ? [viewer] : [...nameMarkOnScreen].filter((face) => face.isConnected && !face.closest("#nm-buddy, .nm-viewer")
    && (Number(face.dataset.nmSize || face.getAttribute("width")) || 0) >= NM_IDLE_MIN);
  if (!big.length) return;
  nameMarkIdleAct(big[Math.floor(Math.random() * big.length)]);
  //: The large view is watched: its beat is twice as quick.
  nameMarkIdleTimer = setTimeout(nameMarkIdleTick, viewer ? 2500 + Math.random() * 3000 : 5000 + Math.random() * 5000);
}
function nameMarkIdleAct(el, pick = "") {
  if (!el?.isConnected || typeof el.animate !== "function" || nameMarkIdleQuiet()) return;
  const inViewer = !!el.closest(".nm-viewer");
  const acts = ["glance", "glance", "blink"];
  if (!nameMarkBuddyActOff("hop")) acts.push("hop");
  if (inViewer && !nameMarkBuddyActOff("wave")) acts.push("wave");
  //: In the large view it also looks about and fidgets (INBOX 443).
  if (inViewer) acts.push("look", "shift");
  const act = pick || acts[Math.floor(Math.random() * acts.length)];
  const part = (sel) => el.querySelector(sel);
  if (act === "glance") {
    const side = nameMarkPointer ? Math.sign(nameMarkPointer[0] - (innerWidth / 2)) || 1 : Math.random() < 0.5 ? -1 : 1;
    part(".nm-eyes")?.animate([
      { translate: "0 0" }, { translate: `${side * 2.4}px 0`, offset: 0.2 }, { translate: `${side * 2.4}px 0`, offset: 0.55 },
      { translate: `${-side * 1.6}px 0`, offset: 0.7 }, { translate: "0 0" },
    ], { duration: 2600, easing: "ease-in-out" });
  } else if (act === "blink") {
    part(".nm-blinks")?.animate([
      { transform: "scaleY(1)" }, { transform: "scaleY(0.1)", offset: 0.12 }, { transform: "scaleY(1)", offset: 0.3 },
      { transform: "scaleY(0.1)", offset: 0.45 }, { transform: "scaleY(1)", offset: 0.62 }, { transform: "scaleY(1)" },
    ], { duration: 800, easing: "linear" });
  } else if (act === "look") {
    part(".nm-eyes")?.animate([
      { translate: "0 0" }, { translate: "-2.4px 0", offset: 0.22 }, { translate: "-2.4px 0", offset: 0.4 },
      { translate: "2.4px 0", offset: 0.58 }, { translate: "2.4px 0", offset: 0.78 }, { translate: "0 0" },
    ], { duration: 2800, easing: "ease-in-out" });
  } else if (act === "shift") {
    //: `rotate`, which composes with the figure's own `scale` and loop.
    (el.querySelector(".nm-figure") || el).animate([
      { rotate: "0deg" }, { rotate: "3deg", offset: 0.35 }, { rotate: "-2deg", offset: 0.7 }, { rotate: "0deg" },
    ], { duration: 1800, easing: "ease-in-out" });
  } else if (act === "hop") {
    nameMarkReact(el.matches(".name-mark") ? el : part(".name-mark"));
  } else if (act === "wave") {
    part(".nmb-arm-r")?.animate([
      { rotate: "0deg" }, { rotate: "-120deg", offset: 0.25 }, { rotate: "-100deg", offset: 0.4 },
      { rotate: "-125deg", offset: 0.55 }, { rotate: "-105deg", offset: 0.7 }, { rotate: "0deg" },
    ], { duration: 1600, easing: "ease-in-out" });
  }
}
//: The pointer onto a large face: it notices (a blink), at most once in
//: two seconds a face.
const nameMarkNoticed = new WeakMap();
document.addEventListener("pointerover", (event) => {
  const el = event.target.closest?.(".nm-viewer-figure, .name-mark");
  if (!el || el.closest("#nm-buddy") || (event.pointerType && event.pointerType !== "mouse")) return;
  const big = el.matches(".nm-viewer-figure") || (Number(el.dataset.nmSize || el.getAttribute("width")) || 0) >= NM_IDLE_MIN;
  const now = performance.now();
  if (!big || now - (nameMarkNoticed.get(el) || -1e9) < 2000) return;
  nameMarkNoticed.set(el, now);
  nameMarkIdleAct(el.closest(".nm-viewer-figure") || el, "blink");
}, { passive: true });

//: One delegated listener for every face in the app: a poke always, and the
//: large view when the face is not inside a control (a face in the Settings
//: head's profile button still opens the profile, and hops on the way).
document.addEventListener("click", (event) => {
  const svg = event.target.closest?.(".name-mark");
  if (!svg || svg.closest(".nm-viewer, #nm-buddy")) return;
  nameMarkReact(svg);
  if (svg.closest("button, a, [role='button'], label, select, summary")) return;
  openNameMarkViewer(svg.dataset.nmSeed || "");
});

//: **Your own picture, enlarged by a double-click** (INBOX 426 w, the
//: owner: the profile picture "cannot be enlarged like the companion"),
//: wherever it is drawn: the profile's head, and the Settings head's
//: button (whose single click still goes to your profile).
document.addEventListener("dblclick", (event) => {
  const holder = event.target.closest?.("[data-user-mark]");
  if (!holder) return;
  event.preventDefault();
  openNameMarkViewer(typeof userMarkSeed === "function" ? userMarkSeed() : "You");
});

//: **Eyes that follow the pointer**, when Appearance says so. One listener,
//: at most one update a frame, and only the faces on screen (the observer's
//: `data-nm-on`), each nudged by a pair of custom properties the CSS turns
//: into a small eye shift and head tilt. Nothing runs while it is off.
let nameMarkFollowFrame = 0;
let nameMarkPointer = null;
document.addEventListener("pointermove", (event) => {
  if (document.documentElement.dataset.avatarFollow !== "on") return;
  nameMarkPointer = [event.clientX, event.clientY];
  if (nameMarkFollowFrame) return;
  nameMarkFollowFrame = requestAnimationFrame(() => {
    nameMarkFollowFrame = 0;
    const [px, py] = nameMarkPointer;
    const faces = [];
    for (const face of nameMarkOnScreen) {
      if (!face.isConnected) nameMarkOnScreen.delete(face);
      //: Not the companion's: it has its own attention (`nameMarkBuddyNotice`)
      //: and does not follow every move.
      else if (faces.length < 40 && !face.closest("#nm-buddy")) faces.push(face);
    }
    //: Every box read first, then every property written: a write between
    //: two reads forces a style and layout pass per face.
    const boxes = faces.map((face) => face.getBoundingClientRect());
    faces.forEach((face, i) => {
      const box = boxes[i];
      const dx = px - (box.left + box.width / 2);
      const dy = py - (box.top + box.height / 2);
      const reach = Math.max(160, box.width * 3);
      face.style.setProperty("--nm-lx", Math.max(-1, Math.min(1, dx / reach)).toFixed(2));
      face.style.setProperty("--nm-ly", Math.max(-1, Math.min(1, dy / reach)).toFixed(2));
    });
  });
}, { passive: true });

//: **The corner companion.** Off by default; Appearance chooses you, the
//: chat's persona, or nobody. Draggable anywhere (its place is remembered),
//: hidden by its own close button, and it says something when poked.
function nameMarkBuddySeed() {
  const choice = typeof appearancePref === "function" ? appearancePref("avatar-buddy", "off") : "off";
  if (choice === "me") return typeof userMarkSeed === "function" ? userMarkSeed() : "You";
  //: The chat's persona, and Atlas when the chat speaks as the default
  //: voice (an empty picker value). Falling back to the person was the old
  //: rule from before Atlas had a face, and it put you in the corner when
  //: you had asked for the persona.
  if (choice === "persona") return document.getElementById("persona-select")?.value || "Atlas";
  //: Atlas itself, whichever persona the chat is using (the owner: "I want
  //: atlas to be a companion option regardless").
  if (choice === "atlas") return "Atlas";
  if (choice === "custom") return nameMarkBuddyCustom().name;
  return null;
}

//: The companion follows the chat's picker when it is showing the persona.
document.addEventListener("change", (event) => {
  if (event.target?.id === "persona-select") syncNameMarkBuddy();
});

//: The dashboard's mark, when Appearance swaps the logo for a face: yours,
//: or the persona the greeting speaks as (the chat's own when it matches
//: Chat). Null keeps the logo.
function dashboardMarkSeed() {
  const choice = typeof appearancePref === "function" ? appearancePref("dash-mark", "logo") : "logo";
  if (choice === "me") return typeof userMarkSeed === "function" ? userMarkSeed() : "You";
  //: Atlas by name, whoever the greeting speaks as (the owner: "the
  //: dashboard mark should have atlas as an option as well"). "Greeting
  //: persona" only shows Atlas while Atlas is that persona.
  if (choice === "atlas") return "Atlas";
  if (choice === "persona") {
    return (typeof prefsCache !== "undefined" && prefsCache?.dashboard_persona) || document.getElementById("persona-select")?.value || "Atlas";
  }
  return null;
}


// --- the profile's "Your look" controls ------------------------------------
//: Shuffle, back to the name's own, and the pickers (look, mood, hair,
//: hair colour, skin, clothes, headwear, eyewear, holding), each "From your
//: name" by default. Every
//: change redraws your face everywhere at once and marks the profile form
//: unsaved; Save preferences keeps it (`avatar_style`).
const PROFILE_LOOK_PARTS = [
  ["look", "Look", () => ["masculine", "feminine", "neutral"]],
  ["mood", "Mood", () => ["happy", "excited", "calm", "cool", "cute", "sly", "evil", "sleepy", "dramatic", "love", "laughing", "unimpressed", "surprised", "serious", "nervous", "confused", "hungry", "greedy", "sad", "angry", "starstruck", "uwu", "dizzy", "sick", "dead", "drunk"]],
  ["hair", "Hair", () => NAME_MARK_HAIR_KINDS],
  ["hairtone", "Hair colour", () => NAME_MARK_HAIR_TONE_KINDS],
  ["skin", "Skin", () => NAME_MARK_SKIN_KINDS],
  ["outfit", "Clothes", () => ["tee", "hoodie", "scoop", "collar", "sweater", "blazer", "suit", "dress"]],
  ["hat", "Headwear", () => NAME_MARK_HAT_KINDS],
  ["eyewear", "Eyewear", () => NAME_MARK_EYEWEAR_KINDS],
  ["hand", "Holding", () => Object.keys(NAME_MOOD_LEXICON.hands)],
];
const PROFILE_LOOK_WORDS = {
  hat: "wizard hat", chefhat: "chef's hat", partyhat: "party hat", flowercrown: "flower crown", tricorn: "pirate hat",
  squareglasses: "square glasses", threed: "3D glasses", starglasses: "star shades", heartglasses: "heart shades", visor: "cyber visor",
  thumbsup: "thumbs up", mug: "hot drink", fishingrod: "fishing rod", tableflip: "table flip",
  tee: "T-shirt", scoop: "scoop neck", collar: "shirt and tie", sweater: "jumper", uwu: "uwu",
  crop: "textured crop", sweep: "side-swept fringe", quiff: "soft quiff", messy: "tousled", curls: "short curls",
  wavy: "wavy, to the chin", long: "long and straight", waves: "long waves",
};

function repaintOwnFace() {
  if (typeof paintUserMarks === "function") paintUserMarks();
  const buddy = document.getElementById("nm-buddy");
  if (buddy) {
    delete buddy.dataset.seed;
    syncNameMarkBuddy();
  }
  if (typeof paintDashEmblem === "function") paintDashEmblem();
}

//: The part pickers, one select per part, for Your look and for your own
//: companion alike: `read` gives the style as it is, `write` keeps a
//: changed one.
function nameMarkLookPickers(host, prefix, autoLabel, read, write) {
  for (const [key, label, options] of PROFILE_LOOK_PARTS) {
    const row = document.createElement("label");
    row.className = "profile-look-part";
    const text = document.createElement("span");
    text.className = "muted";
    text.textContent = label;
    const select = document.createElement("select");
    select.className = "small-select";
    select.id = `${prefix}${key}`;
    select.dataset.part = key;
    const auto = new Option(autoLabel, "");
    const none = new Option("None", "none");
    //: A face always has a skin and its hair a colour: no "None" for those.
    select.append(auto);
    if (key !== "skin" && key !== "hairtone") select.append(none);
    for (const value of options()) {
      const word = PROFILE_LOOK_WORDS[value] || value.replace(/([a-z])([A-Z])/g, "$1 $2");
      select.append(new Option(word.charAt(0).toUpperCase() + word.slice(1), value));
    }
    if (key === "mood") none.textContent = "Plain";
    select.addEventListener("change", () => {
      const style = read();
      style[key] = select.value;
      write(style);
    });
    row.append(text, select);
    host.appendChild(row);
  }
}

//: Appearance's "Your own character" companion: shown only while it is
//: the choice, its pickers built once.
//: **Made, or read from a name?** (the owner: "I havent made a custom avatar
//: yet but it set one randomly ... on the companion when I clicked it. but
//: I as a user might not have even known how to make a custom avatar").
//: Your face counts as made once you picked any part in Profile; your own
//: character once it has a name or a part.
function nameMarkBuddyMade(kind) {
  if (kind === "me") return Object.values(ownNameMarkStyle()).some((v) => v !== "" && v !== undefined && v !== null && v !== 0);
  if (kind === "custom") {
    try {
      return !!prefs.get("avatar-buddy-custom", null);
    } catch (e) {
      return false;
    }
  }
  return true;
}
//: Where to make it: your face in Profile, your character here in
//: Appearance under the companion's own row.
function nameMarkBuddyMakeIt(kind) {
  if (typeof openSettingsModal !== "function") return;
  if (kind === "me") openSettingsModal("preferences", "profile-look");
  else openSettingsModal("appearance", "avatar-buddy-custom");
}
//: The line under the companion's select: shown only while the choice is a
//: face you have not made.
function nameMarkBuddyMakeHint() {
  const hint = document.getElementById("avatar-buddy-make");
  if (!hint) return;
  const kind = typeof appearancePref === "function" ? appearancePref("avatar-buddy", "off") : "off";
  const show = (kind === "me" || kind === "custom") && !nameMarkBuddyMade(kind);
  hint.classList.toggle("hidden", !show);
  if (!show) return;
  document.getElementById("avatar-buddy-make-text").textContent = kind === "me"
    ? "It wears a face read from your name until you make your own."
    : "It wears a face read from its name until you give it one below.";
  const go = document.getElementById("avatar-buddy-make-go");
  go.textContent = kind === "me" ? "Create your avatar" : "Make your character";
  go.onclick = () => nameMarkBuddyMakeIt(kind);
}

function mountBuddyCustom() {
  nameMarkBuddyMakeHint();
  const box = document.getElementById("avatar-buddy-custom");
  if (!box) return;
  const on = (typeof appearancePref === "function" ? appearancePref("avatar-buddy", "off") : "off") === "custom";
  box.classList.toggle("hidden", !on);
  const host = document.getElementById("avatar-buddy-parts");
  const input = document.getElementById("avatar-buddy-name");
  if (host && !host.childElementCount) {
    nameMarkLookPickers(host, "avatar-buddy-look-", "From its name", () => ({ ...nameMarkBuddyCustom().style }), (style) => {
      nameMarkBuddyKeepCustom({ name: nameMarkBuddyCustom().name, style });
    });
    let typing = 0;
    input?.addEventListener("input", () => {
      clearTimeout(typing);
      typing = setTimeout(() => nameMarkBuddyKeepCustom({ name: input.value, style: nameMarkBuddyCustom().style }), 300);
    });
    document.getElementById("avatar-buddy-shuffle")?.addEventListener("click", () => {
      const custom = nameMarkBuddyCustom();
      nameMarkBuddyKeepCustom({ name: custom.name, style: { ...custom.style, variant: ((Number(custom.style.variant) || 0) + 1) % 10000 } });
    });
  }
  const custom = nameMarkBuddyCustom();
  if (input && document.activeElement !== input) input.value = custom.name;
  for (const [key] of PROFILE_LOOK_PARTS) {
    const select = document.getElementById(`avatar-buddy-look-${key}`);
    if (select) select.value = custom.style[key] || "";
  }
}

function mountProfileLook() {
  const host = document.getElementById("profile-look-parts");
  if (!host) return;
  if (!host.childElementCount) {
    nameMarkLookPickers(host, "profile-look-", "From your name", ownNameMarkStyle, (style) => {
      setOwnNameMarkStyle(style);
      repaintOwnFace();
      markPrefsDirty();
    });
    document.getElementById("profile-look-shuffle")?.addEventListener("click", () => {
      const style = ownNameMarkStyle();
      style.variant = ((Number(style.variant) || 0) + 1) % 10000;
      setOwnNameMarkStyle(style);
      repaintOwnFace();
      markPrefsDirty();
    });
    document.getElementById("profile-look-reset")?.addEventListener("click", () => {
      setOwnNameMarkStyle({});
      syncProfileLook();
      repaintOwnFace();
      markPrefsDirty();
    });
  }
  syncProfileLook();
}

function syncProfileLook() {
  const style = ownNameMarkStyle();
  for (const [key] of PROFILE_LOOK_PARTS) {
    const select = document.getElementById(`profile-look-${key}`);
    if (select) select.value = style[key] || "";
  }
}


// --- the companion ----------------------------------------------------------
//: **A character, not a disc, with somewhere to be on every page** (INBOX
//: 425 b; the owner: "is there a way to make the corner companion more
//: lifelike and less a circle just chilling somewhere on the screen?? give
//: it life", and "set areas are assigned as possible areas for a companion
//: to sit or chill around while not being in the way on every interface and
//: page ... hang from a top bar, sit on a bottom bar, walk a top a feature
//: ... just so I dont move it to one area, and then it is annoying for it
//: to be there on another page").
//:
//: - **The body.** nameMark's face is the head, unchanged; under it a small
//:   body in the face's own two colours (`nameMarkBuddyBody`): a torso in
//:   the ground colour, hands in the head's, arms that hang, wave or hold
//:   on, and legs that stand, dangle or kick.
//: - **Perches.** Per tab, a short list of named places measured from the
//:   interface as it is now (`nameMarkBuddyPerches`): sitting on the bottom
//:   bar, hanging from the top bar's lower edge, standing on a dock or on a
//:   card's top edge. Each is checked against every control it must never
//:   cover (`NAME_MARK_BUDDY_NEVER_COVER`, measured with
//:   getBoundingClientRect), then scored against the text it would hide,
//:   and the tab's own order of preference breaks the tie. Its pose follows
//:   the perch.
//: - **Your spot, per tab.** Dragged somewhere on a tab, it stays there on
//:   that tab (`nm-buddy-spots`, per tab); the other tabs keep choosing.
//:   Dropped just above a surface it lands on it; dropped under the top bar
//:   it hangs from it.
//: - **Life, with one timer.** Between behaviours nothing runs: one
//:   `setTimeout` at a time picks the next (look around, blink, glance at
//:   the pointer, stretch, hop, kick its legs, swing, a yawn when you have
//:   been idle a while, sleep after three minutes), and each is a class the
//:   CSS acts out on transforms. The app's events cue the rest: typing near
//:   it makes it watch, a chat turn makes it think, a saved note makes it
//:   cheer. Nothing runs while the window is hidden or the app is locked,
//:   and Reduce motion or Avatar animation Off keeps it still: it simply
//:   appears at its perch.
const NMB_W = 64;
const NMB_H = 92;
const NMB_HEAD = 52;
//: Where the body meets a ledge, from the top of its box: sitting puts the
//: seat on the edge, standing the soles, hanging the middle of the hands.
const NMB_SEAT = 72;
const NMB_FEET = 90;
const NMB_GRIP = 5;
//: Hanging, the character drops this far below its box's top (the CSS's
//: `top: 12px` on `.nm-buddy-char`) so its arms show between the ledge and
//: its head; the hands are drawn this far above the drawing's top.
const NMB_DROP = 12;
const NMB_GUTTER = 12;
//: Away from the keyboard: drowsy at three minutes, asleep at eight.
const NMB_DROWSY_MS = 3 * 60 * 1000;
const NMB_SLEEP_MS = 8 * 60 * 1000;
const NMB_YAWN_MS = 45 * 1000;

//: What it must never stand in front of. Controls by role and by kind, the
//: chat's composer, the floating buttons that share its corners, toasts,
//: dialogs and open menus.
const NAME_MARK_BUDDY_NEVER_COVER = [
  "a[href]", "button", "input:not([type='hidden'])", "select", "textarea", "summary", "label",
  "[role='button']", "[role='tab']", "[role='link']", "[role='menuitem']", "[role='option']",
  "[role='switch']", "[role='slider']", "[role='checkbox']", "[contenteditable='true']",
  ".cm-editor", ".dock-fab", ".scroll-top.visible", ".chat-jump-latest:not(.hidden)",
  ".toast", ".modal-card", ".action-menu", "video", "iframe",
].join(", ");

//: The order each tab prefers its perches in. **The page's own panels
//: first, on every tab** (round 7, INBOX 430, the owner: "perch and ride
//: on UI elements on every tab and scroll with them, as it does on the
//: Dashboard"). Measured before (companiontabs.js, 1440 by 900, a fresh
//: visit): every tab put it on a window bar, hanging from the top one on
//: the dashboard, notes and chat, standing on the bottom one on the other
//: five, where it never moved with the page. A card, a dock or the
//: underside of a panel is something to ride; the window's bars are the
//: fallback when every panel is full of controls or words. The toolbar
//: (`dock`) leads where the page is one big canvas (the graph) or a list
//: under a toolbar (notes, the library, documents).
const NAME_MARK_BUDDY_ORDER = {
  dashboard: ["card", "dock", "under", "hang", "bar"],
  notes: ["dock", "card", "under", "hang", "bar"],
  chat: ["dock", "card", "under", "hang", "bar"],
  graph: ["dock", "card", "bar", "hang"],
  library: ["dock", "card", "under", "hang", "bar"],
  documents: ["dock", "card", "under", "bar", "hang"],
  timeline: ["card", "dock", "under", "bar", "hang"],
  reminders: ["card", "under", "dock", "hang", "bar"],
};

//: **Its behaviours, as a small game AI** (the owner: "more diverse
//: movement and actions, maybe they hang from the roof like a sloth or
//: with one hand or from their feet, maybe they are shy and hiding with
//: their eyes peeking behind some ui panels ... just like a game ai").
//: A weighted pick, one decision every 4 to 12 seconds from the one timer:
//: `ms` is how long a behaviour runs, `w` its base weight, `cool` how long
//: before it may run again, `poses` where it makes sense (`legs: "out"`
//: only with its legs over the edge, `edge: "top"` only on a panel's top
//: edge, which is what it hides behind to peek). `nameMarkBuddyDecide`
//: multiplies the weights by the moment: how long since you last did
//: anything, the hour, what the app just did, and the character's own mood
//: and species (`NAME_MARK_BUDDY_MOODS`, `NAME_MARK_BUDDY_KINDS`). A weight
//: of 0 is a behaviour only an event starts.
const NAME_MARK_BUDDY_ACTS = {
  blink: { ms: 700, w: 3, cool: 5000, poses: ["stand", "sit", "hang", "float", "lean"] },
  look: { ms: 2600, w: 3, cool: 12000, poses: ["stand", "sit", "hang", "float", "lean"] },
  turn: { ms: 3400, w: 2, cool: 14000, poses: ["stand", "sit", "float", "lean"] },
  glance: { ms: 1800, w: 2, cool: 8000, poses: ["stand", "sit", "hang", "float", "lean"] },
  stretch: { ms: 1600, w: 1, cool: 45000, poses: ["stand", "sit", "float"] },
  yawn: { ms: 2200, w: 0, cool: 40000, poses: ["stand", "sit", "hang", "float", "lean"] },
  nap: { ms: 30000, w: 0, cool: 150000, poses: ["stand", "sit", "hang", "float", "lean"] },
  hop: { ms: 800, w: 1, cool: 20000, poses: ["stand", "float"] },
  wave: { ms: 1500, w: 1, cool: 30000, poses: ["stand", "sit", "float", "lean"] },
  scratch: { ms: 2600, w: 1, cool: 30000, poses: ["stand", "sit", "hang", "lean"] },
  dangle: { ms: 6000, w: 5, cool: 5000, poses: ["sit"], legs: "out" },
  kick: { ms: 1600, w: 2, cool: 12000, poses: ["sit"], legs: "out" },
  peek: { ms: 14000, w: 2, cool: 70000, poses: ["sit", "stand"], edge: "top" },
  swing: { ms: 2600, w: 3, cool: 8000, poses: ["hang"] },
  sloth: { ms: 9000, w: 2, cool: 30000, poses: ["hang"] },
  onehand: { ms: 4200, w: 2, cool: 20000, poses: ["hang"] },
  feet: { ms: 7000, w: 1, cool: 45000, poses: ["hang"] },
  emerge: { ms: 800, w: 0, cool: 0, poses: ["sit", "stand"] },
  //: **Peeking down from under a bar** (the owner: "is there a peak half
  //: hidden animation for the companion like with the bottom bar for the top
  //: bar as well?"). The mirror of `peek`: hanging from the top bar (or a
  //: panel's underside), it pulls itself up out of sight behind the edge,
  //: turns over there, and lets its head down under the edge upside down,
  //: eyes first, and stays so; `peekback` takes it up and down again to hang.
  //: Everything above the edge is clipped (the CSS, `nmb-act-peekdown`), so
  //: what is hidden is behind the bar, not over it.
  peekdown: { ms: 9000, w: 1.5, cool: 60000, poses: ["hang"] },
  peekback: { ms: 1500, w: 0, cool: 0, poses: ["hang"] },
  //: **Settling in with a thing of its own** (the owner, 2026-09-27: "new
  //: companion states with simple props, for example lying down and
  //: sleeping, reading, sitting on a beanbag, pulling out a chair and
  //: sitting, face palming, and other gestures, each with smooth transitions
  //: in and out"). Each prop is drawn once, in the companion's own box, and
  //: shown by its act's class (`nameMarkBuddyScene`, the CSS's `.nms-*`):
  //: it eases in, the body eases into it after, and on the way out the body
  //: gets up first and the prop goes after (`nmb-unwind`). Only on a flat
  //: place (standing on a card or a bar) for the ones that need the floor.
  lie: { ms: 26000, w: 0.8, cool: 240000, poses: ["stand"] },
  read: { ms: 20000, w: 1, cool: 150000, poses: ["stand", "sit", "float"] },
  beanbag: { ms: 22000, w: 0.8, cool: 200000, poses: ["stand"] },
  chair: { ms: 20000, w: 0.8, cool: 200000, poses: ["stand"] },
  facepalm: { ms: 2600, w: 0.5, cool: 90000, poses: ["stand", "sit", "float", "lean"] },
  shrug: { ms: 1900, w: 0.8, cool: 60000, poses: ["stand", "sit", "float", "lean"] },
  tilt: { ms: 5000, w: 1.5, cool: 25000, poses: ["stand", "sit", "float"] },
  cheer: { ms: 1300, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
  startle: { ms: 700, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
  land: { ms: 450, w: 0, cool: 0, poses: ["stand", "sit", "float"] },
  shift: { ms: 1800, w: 2, cool: 9000, poses: ["stand", "sit", "lean"] },
  wake: { ms: 1400, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
  bell: { ms: 3000, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
  carry: { ms: 2400, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
  lantern: { ms: 3000, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
  hide: { ms: 2400, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
  wiggle: { ms: 1400, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
  //: Pleased with a piece of work the app finished (`nameMarkBuddyWork`).
  nod: { ms: 1200, w: 0, cool: 0, poses: ["stand", "sit", "hang", "float", "lean"] },
};

//: The sudden or large acts the calm budget holds back
//: (`nameMarkBuddyCalmAllows`), and the acts with no face of their own
//: (`nameMarkBuddyAct` eases a face back only after the others).
const NMB_LOUD_ACTS = ["hop", "wave", "cheer", "startle", "wiggle", "kick", "swing", "stretch", "facepalm", "shrug", "scratch", "peekdown", "onehand", "feet", "carry", "lantern"];
const NMB_LOUD_GAP_MS = 75000;
const NMB_FACELESS_ACTS = ["blink", "look", "glance", "turn", "land", "shift", "emerge"];

//: **At rest, a stance of its own** (INBOX 430, the owner: "more stances,
//: with Atlas's masculine and feminine looks each getting their own (e.g.
//: arms folded or a hand on the hip for masculine, a sway or clasped hands
//: for feminine), used at rest"). Long, quiet acts, only standing or
//: floating, only for Atlas and only in the look named: the arms ease into
//: them (the pose transition) and out again when the act ends, and the sway
//: is the figure's box on the compositor.
const NMB_STANCES = {
  fold: { ms: 16000, w: 1.4, cool: 40000, poses: ["stand", "float"], look: "masculine" },
  hip: { ms: 14000, w: 1.4, cool: 40000, poses: ["stand"], look: "masculine" },
  clasp: { ms: 16000, w: 1.4, cool: 40000, poses: ["stand", "float"], look: "feminine" },
  sway: { ms: 14000, w: 1.4, cool: 40000, poses: ["stand", "float"], look: "feminine" },
};
Object.assign(NAME_MARK_BUDDY_ACTS, NMB_STANCES);
//: **Atlas's own acts** (Brief 88, the owner: "more behaviours and
//: actions especially for atlas"). Three were drawn for it in round 3
//: (`nmb-act-juggle`, `-map`, `-meditate`: their arms, props and loops are
//: in the CSS, and the rig knows them as gestures) and never given a row
//: here, so nothing ever played them. Now it juggles three of its stars,
//: reads its star map, and floats cross-legged a while; only Atlas.
const NMB_ATLAS_ACTS = {
  juggle: { ms: 5400, w: 1.2, cool: 90000, poses: ["stand", "float"], atlas: true },
  map: { ms: 6000, w: 1, cool: 120000, poses: ["stand", "sit", "float"], atlas: true },
  meditate: { ms: 12000, w: 0.8, cool: 180000, poses: ["float"], atlas: true },
};
Object.assign(NAME_MARK_BUDDY_ACTS, NMB_ATLAS_ACTS);

//: **Reduce actions** (INBOX 430): Off keeps it to blinks, looks and its
//: stances, Fewer (the default) makes the unprompted gestures a third as
//: likely, Normal as they were. What you start (a poke, a cheer at a
//: streak, a reaction) is never reduced: those have no weight here.
const NMB_QUIET_ACTS = ["blink", "look", "glance", "turn", "yawn", "nap", "dangle", "shift", "tilt", ...Object.keys(NMB_STANCES)];
//: **Each of its doings can be turned off** (the owner, 2026-09-27: "Every
//: companion feature must be togglable in Settings"). Appearance >
//: Companion > What it does (`mountBuddyActivities`): one switch a row, kept
//: in this browser as the list of the ones turned off. A row may stand for a
//: few acts that are one idea (its hanging tricks). What is off is never
//: picked on its own; a cue that asks for it (a bell, a saved note) still
//: plays, since that is it answering you.
const NMB_ACTIVITIES = [
  ["wave", "Wave", ["wave"]],
  ["hop", "Hop and stretch", ["hop", "stretch"]],
  ["peek", "Peek from behind a panel", ["peek"]],
  ["peekdown", "Peek down from under the top bar", ["peekdown"]],
  ["legs", "Swing its legs over an edge", ["dangle", "kick"]],
  ["hang", "Hanging tricks", ["swing", "sloth", "onehand", "feet"]],
  ["stances", "Stances at rest", Object.keys(NMB_STANCES)],
  ["atlas", "Atlas juggles stars, reads its map and meditates", [...Object.keys(NMB_ATLAS_ACTS), "toss"]],
  ["think", "Stop to think, or sigh", ["ponder", "sigh"]],
  ["lie", "Lie down for a nap", ["lie"]],
  ["read", "Read a book", ["read"]],
  ["beanbag", "Sink into a beanbag", ["beanbag"]],
  ["chair", "Pull up a chair", ["chair"]],
  ["facepalm", "Face palm", ["facepalm"]],
  ["shrug", "Shrug", ["shrug"]],
  ["tilt", "Lean to one side now and then", ["tilt"]],
  ["emotes", "Little emotes (a question mark, a sparkle, a sweat drop)", ["emote"]],
  ["nightcap", "A night cap when it naps", ["nightcap"]],
  ["wander", "Wander off now and then, and come back", ["wander"]],
  ["rub", "Lean into a rub (the pointer back and forth over it)", ["rub"]],
  ["flip", "Turn upside down when shaken while carried", ["flip"]],
];
function nameMarkBuddyActivitiesOff() {
  try {
    return new Set((prefs.get("avatar-buddy-acts-off", null) || "").split(",").filter(Boolean));
  } catch (e) {
    return new Set();
  }
}
function nameMarkBuddyActOff(act, off = nameMarkBuddyActivitiesOff()) {
  return NMB_ACTIVITIES.some(([key, , acts]) => off.has(key) && acts.includes(act));
}
//: What the CSS needs to know of the switches (the night cap is a style).
function nameMarkBuddyToggles(buddy) {
  buddy.classList.toggle("nmb-cap-off", nameMarkBuddyActOff("nightcap"));
}
//: Plays one emote by its head: popped up, drifted and faded, the
//: compositor's. Not for Atlas (its own are its drawing's), not when still,
//: not when switched off.
function nameMarkBuddyEmote(kind) {
  const buddy = document.getElementById("nm-buddy");
  const el = buddy?.querySelector(`.nmb-emote-${kind}`);
  if (!el || typeof el.animate !== "function" || nameMarkBuddyStill() || nameMarkBuddyActOff("emote")) return;
  if (isAtlasSeed(buddy.dataset.seed || "") || (typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches)) return;
  el.animate([
    { opacity: 0, transform: "translate(0, 4px) scale(0.6)" },
    { opacity: 1, transform: "translate(0, 0) scale(1.1)", offset: 0.18 },
    { opacity: 1, transform: "translate(1px, -3px) scale(1)", offset: 0.4 },
    { opacity: 1, transform: "translate(2px, -7px) scale(1)", offset: 0.8 },
    { opacity: 0, transform: "translate(3px, -10px) scale(0.95)" },
  ], { duration: 1600, easing: "ease-out" });
}

function mountBuddyActivities() {
  const host = document.getElementById("avatar-buddy-activities");
  if (!host || host.childElementCount) return;
  const off = nameMarkBuddyActivitiesOff();
  for (const [key, label] of NMB_ACTIVITIES) {
    const row = document.createElement("label");
    row.className = "setting-check";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = !off.has(key);
    input.dataset.activity = key;
    const text = document.createElement("span");
    text.textContent = label;
    row.append(input, text);
    host.appendChild(row);
  }
  host.addEventListener("change", (event) => {
    const input = event.target.closest?.("input[data-activity]");
    if (!input) return;
    const now = nameMarkBuddyActivitiesOff();
    if (input.checked) now.delete(input.dataset.activity);
    else now.add(input.dataset.activity);
    try {
      prefs.set("avatar-buddy-acts-off", [...now].join(","));
    } catch (e) {
      // Kept for this visit only.
    }
    //: Turned off while it is doing it: it stops, the way it always does.
    if (nmb.act && nameMarkBuddyActOff(nmb.act, now)) nameMarkBuddyAct("");
    const buddy = document.getElementById("nm-buddy");
    if (buddy) nameMarkBuddyToggles(buddy);
  });
}

function nameMarkBuddyActions() {
  try {
    return prefs.get("avatar-buddy-actions", null) || "fewer";
  } catch (e) {
    return "fewer";
  }
}

//: How a character's mood leans its choices (multipliers on the weights).
const NAME_MARK_BUDDY_MOODS = {
  sleepy: { yawn: 3, nap: 3, sloth: 3, hop: 0.3 },
  sick: { yawn: 2, nap: 2, hop: 0.3, kick: 0.5 },
  drunk: { sloth: 2, swing: 2, hop: 0.5 },
  excited: { hop: 2.5, wave: 2, kick: 2 },
  happy: { hop: 1.5, wave: 1.5, dangle: 1.5 },
  laughing: { hop: 2, kick: 2 },
  cute: { wave: 2, peek: 1.5, peekdown: 1.5, dangle: 1.5 },
  uwu: { wave: 2, peek: 2 },
  love: { wave: 2, glance: 2 },
  nervous: { peek: 3, peekdown: 2.5, look: 2, hop: 0.5 },
  sad: { peek: 2, nap: 1.5, hop: 0.3 },
  confused: { look: 2, scratch: 3 },
  sly: { peek: 2.5, peekdown: 2, feet: 2, onehand: 2 },
  evil: { peek: 2, feet: 2.5 },
  cool: { onehand: 2.5, feet: 1.5, turn: 2 },
  dramatic: { stretch: 2.5, wave: 2 },
  starstruck: { hop: 2, glance: 2 },
  serious: { hop: 0.4, kick: 0.5 },
  unimpressed: { turn: 2, yawn: 2 },
  hungry: { scratch: 1.5, look: 1.5 },
};

//: And its species.
const NAME_MARK_BUDDY_KINDS = {
  sloth: { sloth: 5, nap: 2, hop: 0.2 },
  monkey: { onehand: 3, feet: 2, swing: 2 },
  bat: { feet: 6 },
  cat: { stretch: 3, nap: 2, peek: 2 },
  owl: { look: 3 },
  bunny: { hop: 3 },
  frog: { hop: 3 },
  koala: { sloth: 3, nap: 2 },
  hedgehog: { peek: 3 },
  mouse: { peek: 3 },
  ghost: { peek: 2 },
};

const nmb = {
  x: NaN, y: NaN, pose: "", legs: "", perch: "", tab: "", act: "", lastAct: "", timer: 0,
  lastInput: Date.now(), lastCheer: 0, lastPoke: 0, pointer: null, watchTimer: 0, watchAt: 0,
  cueTimer: 0, startledAt: 0, errandTimer: 0, readingErrand: false, shyAt: 0, shyTimer: 0, readTimer: 0, keyAt: 0, keyRun: 0,
  trail: 0, ex: 0, ey: 0, target: null, targetAt: 0, lastMove: null, headTimer: 0, releaseTimer: 0,
  leanSide: "", leanAt: 0, stirAt: 0, groggyUntil: 0, grumpyUntil: 0, pokes: [], unlockDrop: true, lastHow: "",
  mood: { energy: 0.7, curiosity: 0.6, sociability: 0.7 }, edgeType: "", edgeLine: 72, reading: null, cool: {},
  anim: null, hopAnim: null, glue: null, heldTimer: 0, placeTimer: 0, movedAt: 0, pinned: false, menu: null, settle: [], checkFrame: 0,
};

//: The companion's own reading of Reduce motion and Avatar animation Off:
//: no travel and no behaviours, it simply appears where it is going. The
//: system's own hint stops the travel too (a walk across the screen is the
//: one motion here that moves something large), and leaves the small
//: behaviours to the CSS, which calms them like every other face.
//: **How much it moves, and why** (the owner: "when the companion is
//: appearing from off screen, it still just appears there. is it because I
//: have the motion on auto"). It was held still by `data-motion="reduced"`,
//: which Performance mode's automatic setting also sets on a small machine
//: or when the system asks for less transparency: a cheap transform-only
//: walk was taken away with the costly glass. Now its own setting decides
//: (Appearance > Companion movement, `avatar-buddy-motion`):
//:   follow  (the default) less motion only when you asked for it, in the
//:           app's Motion setting or the system's; Performance mode alone
//:           leaves it moving;
//:   always  walks, hops and portals whatever else asks;
//:   fades   no travel: it fades out and in, and does nothing on its own.
//: Avatar animation off keeps it still. `mode` is "full", "fades" or
//: "still"; `reason` names why it is not full, for the setting's hint.
function nameMarkBuddyMotion() {
  const root = document.documentElement;
  let choice = "follow";
  try {
    choice = prefs.get("avatar-buddy-motion", null) || "follow";
  } catch (e) {
    // The default.
  }
  if (root.dataset.avatarMotion === "off") return { mode: "still", reason: "avatar" };
  if (choice === "fades") return { mode: "fades", reason: "setting" };
  const app = typeof appearancePref === "function" ? appearancePref("motion", "auto") : "auto";
  const os = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  //: Always: it moves, and the hint still says what it is overriding, so
  //: a person who forgot choosing it knows why it walks under Reduce.
  if (choice === "always") return { mode: "full", reason: app === "reduced" ? "app-ignored" : os ? "os-ignored" : root.dataset.perf === "on" ? "perf-ignored" : "" };
  if (app === "reduced") return { mode: "fades", reason: "app" };
  if (os) return { mode: "fades", reason: "os" };
  return { mode: "full", reason: root.dataset.perf === "on" ? "perf-ignored" : "" };
}
const NMB_MOTION_WHY = {
  avatar: "Avatar animation is off, so it stays still.",
  setting: "Fades only, as chosen here.",
  app: "Fades only: Motion is set to Reduce in Appearance.",
  os: "Fades only: your system asks for less motion.",
  "perf-ignored": "Performance mode is on, but the companion still moves: it costs very little.",
  "app-ignored": "Always animates, although Motion is set to Reduce in Appearance.",
  "os-ignored": "Always animates, although your system asks for less motion.",
  "": "",
};
//: The page's own motion switch (`data-motion`) also gates its CSS; when it
//: is on for Performance mode only, or you chose Always, the companion's
//: gates are lifted by `data-buddy-motion` on the root.
function nameMarkBuddyMotionApply() {
  const root = document.documentElement;
  const { mode, reason } = nameMarkBuddyMotion();
  if (mode === "full" && root.dataset.motion === "reduced") root.dataset.buddyMotion = "full";
  else delete root.dataset.buddyMotion;
  const why = document.getElementById("avatar-buddy-motion-why");
  if (why) why.textContent = NMB_MOTION_WHY[reason] || "";
  return mode;
}
function nameMarkBuddyStill() {
  return nameMarkBuddyMotion().mode !== "full";
}
function nameMarkBuddyNoTravel() {
  return nameMarkBuddyMotion().mode !== "full";
}

function nameMarkShade(hex, t) {
  const to = t > 0 ? 0 : 255;
  const k = Math.min(1, Math.abs(t));
  return `#${[1, 3, 5]
    .map((i) => Math.round(parseInt(hex.slice(i, i + 2), 16) * (1 - k) + to * k).toString(16).padStart(2, "0"))
    .join("")}`;
}

//: The body's two colours come from the face it is drawn under: the ground
//: for the clothes, the head for the hands. Atlas wears its accent.
function nameMarkBuddyColours(svg) {
  const hex = (value) => (/^#[0-9a-f]{6}$/i.test(value || "") ? value : null);
  if (svg?.classList.contains("nm-atlas")) {
    const accent = hex(typeof currentAccentHex === "function" ? currentAccentHex() : "") || "#6d5dfc";
    return { coat: nameMarkShade(accent, 0.15), skin: nameMarkShade(accent, -0.55) };
  }
  const coat = hex(svg?.querySelector(":scope > g > rect")?.getAttribute("fill")) || "#4e79a7";
  const skin = hex(svg?.querySelector(".nm-body > :is(rect, circle, ellipse, path)")?.getAttribute("fill")) || "#f1c9a5";
  return { coat, skin };
}

//: The body, drawn at 1:1 in the same 64 by 92 box as the whole character,
//: behind the head. The arms that hold on reach up either side of the head
//: and only their hands show above it, which is what hanging from an edge
//: looks like from the front.
function nameMarkBuddyBody(coat, skin) {
  const ns = "http://www.w3.org/2000/svg";
  const make = (tag, attrs, parent) => {
    const el = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
    if (parent) parent.appendChild(el);
    return el;
  };
  const deep = nameMarkShade(coat, 0.3);
  const svg = make("svg", {
    class: "nmb-body", viewBox: `0 0 ${NMB_W} ${NMB_H}`, width: NMB_W, height: NMB_H,
    "aria-hidden": "true", focusable: "false",
  });
  const limb = (d, colour, width, parent) =>
    make("path", { d, fill: "none", stroke: colour, "stroke-width": width, "stroke-linecap": "round" }, parent);
  for (const [side, hip, foot] of [["l", 27.5, 26], ["r", 36.5, 38]]) {
    const leg = make("g", { class: `nmb-leg nmb-leg-${side}`, "data-pivot": `${hip} 68` }, svg);
    limb(`M${hip} 68 L${foot} 84.5`, deep, 5.5, leg);
    make("ellipse", { cx: foot + (side === "l" ? -1.5 : 1.5), cy: 86.5, rx: 5.2, ry: 3.2, fill: deep }, leg);
  }
  for (const [side, d, hx] of [["l", "M22 54 C 0 52, -6 16, 6 -6", 6], ["r", "M42 54 C 64 52, 70 16, 58 -6", 58]]) {
    const hold = make("g", { class: `nmb-hold nmb-hold-${side}`, "data-pivot": side === "l" ? "22 54" : "42 54" }, svg);
    limb(d, coat, 5, hold);
    make("circle", { cx: hx, cy: NMB_GRIP - NMB_DROP, r: 4.4, fill: skin, stroke: deep, "stroke-width": 0.8 }, hold);
  }
  make("rect", { class: "nmb-torso", x: 19, y: 43, width: 26, height: 31, rx: 12, fill: coat, stroke: deep, "stroke-width": 1 }, svg);
  make("ellipse", { cx: 32, cy: 63, rx: 7.5, ry: 6.5, fill: "#ffffff", "fill-opacity": 0.22 }, svg);
  for (const [side, d, hx, hy] of [["l", "M21.5 54 Q 14.5 59.5 13.8 66.5", 13.8, 68.2], ["r", "M42.5 54 Q 49.5 59.5 50.2 66.5", 50.2, 68.2]]) {
    const arm = make("g", { class: `nmb-arm nmb-arm-${side}`, "data-pivot": side === "l" ? "21.5 54" : "42.5 54" }, svg);
    limb(d, coat, 5, arm);
    make("circle", { cx: hx, cy: hy, r: 3.9, fill: skin, stroke: deep, "stroke-width": 0.8 }, arm);
  }
  return svg;
}

//: The built-in figure (the character interface's `figure()`): the head
//: mark over a body in its own two colours, in the companion's 64 by 92
//: box.
let nameCharacterExpression = "";
function nameCharacterFigure(seed, expr = "") {
  const figure = document.createElement("span");
  figure.className = "nm-figure nm-live";
  const own = JSON.stringify(nameMarkOwnFor(seed) || {});
  const draw = () => {
    nameCharacterExpression = expr;
    try {
      return drawCharacter(seed, NMB_W, "figure");
    } finally {
      nameCharacterExpression = "";
    }
  };
  figure.appendChild(nameMarkCompose(`fig|${seed}|${own}|${nameMarkLookLean() || ""}|${expr}`, draw, { parts: NM_FIGURE_PARTS, pad: 24, size: NMB_W, height: NMB_H }));
  return figure;
}

function nameMarkFigure(seed) {
  const figure = document.createElement("span");
  figure.className = "nm-figure";
  const head = document.createElement("span");
  head.className = "nm-buddy-head";
  const live = nameMarkLive(seed, NMB_HEAD);
  head.appendChild(live);
  const { coat, skin } = nameMarkBuddyColours(live.querySelector(".name-mark"));
  const body = nameMarkCompose(`body|${coat}|${skin}`, () => nameMarkBuddyBody(coat, skin), { parts: ".nmb-leg, .nmb-arm, .nmb-hold", pad: 16, size: NMB_W, height: NMB_H });
  figure.append(body, head);
  return figure;
}

function nameMarkBuddyTab() {
  for (const name of typeof TABS !== "undefined" ? TABS : []) {
    const page = document.getElementById(`tab-${name}`);
    if (page && !page.classList.contains("hidden")) return name;
  }
  return "app";
}

function nameMarkBuddyShown(el) {
  if (!el) return null;
  const box = el.getBoundingClientRect();
  return box.width > 0 && box.height > 0 && box.bottom > 0 && box.top < innerHeight && box.right > 0 && box.left < innerWidth ? box : null;
}

//: **A perch that can still be seen** (INBOX 462, the owner: "the
//: companion perches dont handle collapsed sidebars at least in the chat
//: tab"). A folded sidebar keeps its rows laid out, faded to nothing and
//: clipped to a 48px rail, so their boxes stayed and it sat on in the air
//: over a row nobody could see (companioncollapse.js: still on Chat's
//: "New chat" at 227,726 with the rail 48px wide). Inside a folded sidebar
//: (even peeked open on hover: it closes again on its own) or faded out,
//: a perch is gone.
function nameMarkBuddyPerchShown(el) {
  const box = nameMarkBuddyShown(el);
  if (!box || el.closest(".sidebar-collapsed")) return null;
  return typeof el.checkVisibility !== "function" || el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) ? box : null;
}

//: The two ledges every page has: the top bar's lower edge and the bottom
//: bar's upper one (the phone's tab dock where it has one).
function nameMarkBuddyLedges() {
  return {
    top: nameMarkBuddyShown(document.getElementById("top-bar")),
    bottom: nameMarkBuddyShown(document.getElementById("phone-tab-dock")) || nameMarkBuddyShown(document.getElementById("status-bar")),
  };
}

//: Every box it must stay clear of, measured once per placement: the tab's
//: own controls, the chrome's, and whatever floats over the page.
function nameMarkBuddyObstacles(tab) {
  nameMarkBuddyTextCache = new WeakMap();
  const roots = [
    document.getElementById(`tab-${tab}`), document.getElementById("top-bar"), document.getElementById("status-bar"),
    document.getElementById("phone-tab-dock"), document.getElementById("toast-box"), document.querySelector(".pointer-menu-host"),
    ...document.querySelectorAll(".modal-overlay:not(.hidden), .dock-fab, #scroll-top, .chat-jump-latest"),
  ];
  //: A popup's whole box, not only the controls in it (INBOX 430: the
  //: notifications panel was blocked by it): it is where the reader is
  //: looking the moment it opens.
  const boxes = nameMarkBuddyPopups();
  for (const root of roots) {
    if (!root) continue;
    const found = root.matches(NAME_MARK_BUDDY_NEVER_COVER) ? [root] : [];
    for (const el of [...found, ...root.querySelectorAll(NAME_MARK_BUDDY_NEVER_COVER)]) {
      if (el.closest("#nm-buddy")) continue;
      const box = nameMarkBuddyShown(el);
      if (box) boxes.push(box);
    }
  }
  //: **The chat's latest message is never covered** (INBOX 443): it is
  //: what the reader is reading, an answer still being written included.
  //: The words check alone let its legs hang over the bubble's empty edge.
  if (tab === "chat") {
    const msgs = document.querySelectorAll("#chat-messages .msg");
    const last = msgs.length ? nameMarkBuddyShown(msgs[msgs.length - 1]) : null;
    if (last) boxes.push(last);
  }
  return boxes;
}

//: **Out of the way of a popup** (INBOX 430, the owner: "move out of the
//: way of popups (the notifications panel was blocked by it)"). Every
//: surface that opens over the page and can land where it sits: the
//: notifications panel, a menu, a select's list, a '?' popover. Its own
//: menu is not one: that opens at it on purpose. The guided tour's ring
//: and card are two more (INBOX 430, "Atlas spills out of its ring in the
//: tour"): the ring is a hole in the tour's dim, and a companion perched by
//: the control it rings showed through the hole and ran out under the dim
//: (tourspill.js: 86 to 90px past the ring on Library's "Make something
//: new" and the status bar's "Find").
//: A dock's "more" menu is a `<details>`, not an `.action-menu`, so it was
//: missed (the owner, 2026-10-11, over Notes' Reload / Manage tags menu:
//: "the companion still covers some parts of the ui and doesnt move out of
//: the way"); any open details menu and any shown menu or listbox counts.
const NMB_POPUPS = "#notif-panel:not(.hidden), .action-menu:not(.hidden), .select-menu:not(.hidden), .help-popover:not(.hidden), #tour-spot:not(.hidden), #tour-card:not(.hidden), details[open][class*=\"menu\"] > :not(summary), [role=\"menu\"]:not(.hidden), [role=\"listbox\"]:not(.hidden), #wb-format:not(.hidden), #wb-sidebar-panel:not(.hidden)";
function nameMarkBuddyPopups() {
  const boxes = [];
  for (const el of document.querySelectorAll(NMB_POPUPS)) {
    if (el === nmb.menu || el.closest("#nm-buddy, .nm-viewer")) continue;
    const box = nameMarkBuddyShown(el);
    if (box) boxes.push(box);
  }
  return boxes;
}
//: Checked a moment after any press or key (the way a popup opens), from
//: boxes only. Over one, it fades at once, so the popup is readable that
//: frame, and then steps aside on the check it already has; once nothing
//: is over it any more, it fades back.
function nameMarkBuddyDodge() {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nmb.visit) return;
  //: The drawn figure's box, not the face button's: the tail and the
  //: skirt hang below the button, and a tour ring under them was missed.
  const face = buddy.querySelector(".nm-figure") || buddy.querySelector(".nm-buddy-face") || buddy;
  const me = face.getBoundingClientRect();
  const over = nameMarkBuddyPopups().some((b) => b.left < me.right && b.right > me.left && b.top < me.bottom && b.bottom > me.top);
  buddy.classList.toggle("nmb-dodge", over);
  if (!over) return;
  if (!nmb.pinned) queueNameMarkBuddyCheck();
  //: Looked at again while it is faded, so it fades back as soon as it has
  //: stepped out from under (or the popup has gone), not at the next press.
  clearTimeout(nmbDodgeTimer);
  nmbDodgeTimer = setTimeout(nameMarkBuddyDodge, 500);
}
let nmbDodgeTimer = 0;
let nmbDodgeLate = 0;
for (const type of ["click", "keyup"]) {
  document.addEventListener(type, () => {
    if (!document.getElementById("nm-buddy")) return;
    clearTimeout(nmbDodgeTimer);
    clearTimeout(nmbDodgeLate);
    nmbDodgeTimer = setTimeout(nameMarkBuddyDodge, 80);
    //: And once the page has settled: a tour step that changes tab, or a
    //: panel that slides in, lands its box after the first look.
    nmbDodgeLate = setTimeout(nameMarkBuddyDodge, 700);
  }, { passive: true, capture: true });
}

//: The parts of the character that are actually drawn, as boxes: the head
//: and the body (down to its seat when its legs are tucked), and the hands
//: above the head when it hangs.
//: **Its size** (INBOX 426 x: "size options"): small, medium or large
//: from its menu or Appearance, or any size between 0.7 and 1.6 from the
//: handle at its corner, kept on this computer. The figure is scaled about
//: the point it touches its perch (its hands hanging, its seat sitting, its
//: soles standing), so every perch stays where it was; its shape and the
//: points sampled for what it covers are scaled the same way, so a large
//: companion is kept off controls as a medium one is.
const NMB_SIZES = { small: 0.8, medium: 1, large: 1.3 };
function nameMarkBuddyScaleSaved() {
  let v = 1;
  try {
    v = Number(prefs.get("avatar-buddy-size", null)) || 1;
  } catch (e) {
    // Medium.
  }
  return Math.min(1.6, Math.max(0.7, v));
}
function nameMarkBuddySetSize(scale, keep = true) {
  const size = Math.round(Math.min(1.6, Math.max(keep ? 0.7 : 0.4, Number(scale) || 1)) * 100) / 100;
  nmb.scale = size;
  document.getElementById("nm-buddy")?.style.setProperty("--nmb-scale", String(size));
  if (!keep) return;
  try {
    prefs.set("avatar-buddy-size", String(size));
  } catch (e) {
    // This session only.
  }
  nameMarkBuddySizeSelect();
  //: A new size is a new overhang (`nameMarkBuddyOverhang`): the band it
  //: rides in is measured again now, not at its next placement, or a
  //: companion made Large where it stands keeps the smaller band and loses
  //: its rings to it. Once per chosen size, not per frame of a handle drag.
  if (nmb.ride) nameMarkBuddyRideBox(nmb.x, nmb.y, true);
  queueNameMarkBuddyCheck();
}
//: Back to its own size (Medium) from the handle (INBOX 601: a double-click
//: or double tap on it), eased as a fitted size is, and kept.
function nameMarkBuddyResetSize(buddy = document.getElementById("nm-buddy")) {
  if (!buddy) return;
  buddy.classList.add("nmb-fitting");
  clearTimeout(nmb.fitTimer);
  nmb.fitTimer = setTimeout(() => buddy.classList.remove("nmb-fitting"), 900);
  nameMarkBuddySetSize(NMB_SIZES.medium, true);
}
//: Appearance's select: the three sizes, and "As you sized it" for a size
//: the handle gave it.
function nameMarkBuddySizeSelect() {
  const select = document.getElementById("avatar-buddy-size");
  if (!select) return;
  const size = nameMarkBuddyScaleSaved();
  let own = select.querySelector("option[data-own]");
  const preset = Object.values(NMB_SIZES).includes(size);
  if (!preset) {
    if (!own) {
      own = document.createElement("option");
      own.dataset.own = "1";
      select.appendChild(own);
    }
    own.value = String(size);
    own.textContent = `As you sized it (${Math.round(size * 100)}%)`;
  } else {
    own?.remove();
  }
  select.value = String(size);
  const off = (document.getElementById("avatar-buddy")?.value || "off") === "off";
  document.getElementById("avatar-buddy-size-row")?.classList.toggle("hidden", off);
}
function nameMarkBuddyOrigin(x, y, pose) {
  const line = pose === "hang" ? NMB_GRIP : pose === "float" ? NMB_H / 2 : pose === "sit" ? NMB_SEAT : NMB_FEET - 1;
  return [x + NMB_W / 2, y + line];
}
function nameMarkBuddyScaled(boxes, x, y, pose) {
  const size = nmb.scale || 1;
  if (size === 1) return boxes;
  const [ox, oy] = nameMarkBuddyOrigin(x, y, pose);
  return boxes.map((b) => ({ left: ox + (b.left - ox) * size, right: ox + (b.right - ox) * size, top: oy + (b.top - oy) * size, bottom: oy + (b.bottom - oy) * size }));
}

function nameMarkBuddyShape(x, y, pose, legs = "") {
  return nameMarkBuddyScaled(nameMarkBuddyShapeAt1(x, y, pose, legs), x, y, pose);
}
function nameMarkBuddyShapeAt1(x, y, pose, legs = "") {
  if (legs === "peek") return [{ left: x + 8, top: y + NMB_SEAT - 36, right: x + 56, bottom: y + NMB_SEAT }];
  const drop = pose === "hang" ? NMB_DROP : 0;
  let bottom = y + drop + NMB_FEET;
  //: Standing or sitting tucked, it touches the edge it is on and nothing
  //: under it: a control can be its floor (a tile, a toolbar), never
  //: something it covers.
  if (pose === "stand") bottom -= 8;
  if (pose === "sit" && legs === "tuck") bottom = y + NMB_SEAT - 5;
  const shape = [
    { left: x + 5, top: y + drop, right: x + 59, bottom: y + drop + NMB_HEAD },
    { left: x + 8, top: y + drop + 43, right: x + 56, bottom },
  ];
  //: The arms that hold on, from just under the ledge.
  if (pose === "hang") shape.push({ left: x - 4, top: y + NMB_GRIP + 1, right: x + 68, bottom: y + drop + 30 });
  //: Atlas's tail curls out past the box to the lower right, to x + 80
  //: sitting (atlasreach.js); with panels preferred on every tab (round 7)
  //: it sat on the chat's composer row with its tail over Send. **Tucked
  //: too** (INBOX 443): a tucked Atlas has no legs to fold, and its tail
  //: still hangs 22px below its seat, from x + 32 to x + 78
  //: (companionchat.js): sitting tucked on the chat's dock it covered the
  //: input by 13px, and reading along an answer it covered Stop by 29.
  //: Standing, it reaches 6px under its soles (companionchat.js), which
  //: still fits the chat's dock, whose controls start 13px under its top.
  if (document.querySelector("#nm-buddy .atl-figure-box")) shape.push({ left: x + 30, top: y + drop + 50, right: x + 82, bottom: y + drop + NMB_FEET + (pose === "stand" ? 6 : 4) });
  return shape;
}

function nameMarkBuddyHits(x, y, pose, obstacles, legs = "") {
  const gap = 4;
  //: Peeking over the bottom bar, the bar's own buttons are behind it, not
  //: covered (INBOX 521): counted, every peek "hit" and none was ever
  //: checked, so one stayed under a button floating over the bar.
  const bar = legs === "peek" ? y + NMB_SEAT - 2 : Infinity;
  for (const part of nameMarkBuddyShape(x, y, pose, legs)) {
    for (const box of obstacles) {
      if (box.top >= bar) continue;
      if (part.right > box.left - gap && part.left < box.right + gap && part.bottom > box.top - gap && part.top < box.bottom + gap) return true;
    }
  }
  return false;
}

//: The share of the character that would sit over words or pictures,
//: sampled at a dozen points of its shape: a perch over an empty stretch
//: of card beats one over a paragraph.
function nameMarkBuddyCovers(x, y, pose, legs = "") {
  const drop = pose === "hang" ? NMB_DROP : 0;
  const points = [];
  for (const fx of [10, 24, 40, 54]) for (const fy of [8, 22, 36, 48]) points.push([x + fx, y + drop + fy]);
  points.push([x + 32, y + drop + 58], [x + 24, y + drop + 72], [x + 40, y + drop + 72]);
  if (legs !== "tuck") points.push([x + 32, y + drop + 84]);
  //: Tucked behind the bar only its eyes show.
  if (legs === "peek") {
    points.length = 0;
    for (const fx of [10, 24, 40, 54]) for (const fy of [NMB_SEAT - 30, NMB_SEAT - 14]) points.push([x + fx, y + fy]);
  }
  let covered = 0;
  const size = nmb.scale || 1;
  const [ox, oy] = nameMarkBuddyOrigin(x, y, pose);
  for (const [qx, qy] of points) {
    const px = size === 1 ? qx : ox + (qx - ox) * size;
    const py = size === 1 ? qy : oy + (qy - oy) * size;
    if (px < 0 || py < 0 || px >= innerWidth || py >= innerHeight) continue;
    //: One hit test per point per choice: perches along an edge share
    //: most of their points (`nmbCoverCache`, emptied by each choice).
    const key = `${Math.round(px)},${Math.round(py)}`;
    const known = nmbCoverCache?.get(key);
    if (known !== undefined) {
      covered += known;
      continue;
    }
    const hit = nameMarkBuddyCoverPoint(px, py);
    nmbCoverCache?.set(key, hit);
    covered += hit;
  }
  return covered / points.length;
}
let nmbCoverCache = null;

//: Whether one point of the figure would be over something to read: 1 or 0.
function nameMarkBuddyCoverPoint(px, py) {
  const el = document.elementsFromPoint(px, py).find((node) => !node.closest("#nm-buddy"));
  if (!el || el === document.body || el === document.documentElement) return 0;
  //: A picture counts; a canvas or a drawing the size of a pane (the
  //: graph, a board) is a ground, not a picture, or every perch over it
  //: would lose to one over the chrome.
  if (el.matches("img, picture, video")) return 1;
  if (el.matches("svg, canvas")) {
    const box = el.getBoundingClientRect();
    return box.width < 200 && box.height < 200 ? 1 : 0;
  }
  //: Words, measured as the boxes their lines actually take: a heading is
  //: a block the width of its card, and only its first few hundred pixels
  //: have anything in them.
  return nameMarkBuddyTextBoxes(el).some((box) => px >= box.left - 3 && px <= box.right + 3 && py >= box.top - 3 && py <= box.bottom + 3) ? 1 : 0;
}

//: The line boxes of an element's own words, kept for one placement (the
//: map is dropped with each `nameMarkBuddyObstacles` call).
let nameMarkBuddyTextCache = new WeakMap();
function nameMarkBuddyTextBoxes(el) {
  let boxes = nameMarkBuddyTextCache.get(el);
  if (boxes) return boxes;
  boxes = [];
  const range = document.createRange();
  for (const node of el.childNodes) {
    if (node.nodeType !== 3 || !node.textContent.trim()) continue;
    range.selectNodeContents(node);
    boxes.push(...range.getClientRects());
  }
  nameMarkBuddyTextCache.set(el, boxes);
  return boxes;
}

//: **Surfaces and their edges** (the owner: "sit on panels and dangle their
//: legs", then "why can atlas only be on some panels or hang from some
//: areas and not on other areas of the page or other panels??"). Every
//: visible surface on the tab is a candidate: cards, panels, widgets, docks
//: and toolbars, sidebars, headers, groups of rows, rows of chips and tabs.
//: Each gives a top edge to sit or stand on, an underside to hang from and
//: two sides to lean on. The list is one pass of getBoundingClientRect over
//: a bounded set of selectors, kept until the tab changes, the window
//: resizes or scrolls, or the tab page changes size (a ResizeObserver).
const NAME_MARK_BUDDY_SURFACES = [
  ".card", ".dock", ".dash-hero", ".dash-widget", ".widget", ".panel", ".settings-group", "aside", "header", "nav",
  "section", "form", "[role='toolbar']", "[role='tablist']", ".toolbar", ".sidebar", ".chip-row", ".chips",
  ".entry-list", ".msg", ".chat-composer", ".library-card", ".note-card", ".empty-state",
  //: The chat's own (INBOX 443): its dock's top edge, the ledge under
  //: the conversation and over everything you are about to send.
  ".chat-dock",
].join(", ");
const NMB_SURFACE_CAP = 80;
let nameMarkBuddyIndex = null;
let nameMarkBuddyIndexObserver = null;

function nameMarkBuddyIndexReset() {
  nameMarkBuddyIndex = null;
}

//: The tab's surfaces, found by walking it rather than by naming them all:
//: every element on screen at least 96 by 24 that draws a surface of its
//: own (a background, a border or a shadow), is one of the named kinds
//: above, or is a wide control (a tile, a big button: it can be stood on,
//: never covered). Bounded: eight levels deep, 600 elements looked at.
function nameMarkBuddySurfaceWalk(page) {
  const found = [];
  if (!page) return found;
  let looked = 0;
  const minW = Math.round(NMB_W * Math.max(0.7, nmb.scale || 1));
  const walk = (el, depth) => {
    for (const child of el.children) {
      if (looked >= 600 || found.length >= NMB_SURFACE_CAP) return;
      looked += 1;
      //: Nor anything in a folded sidebar (`nameMarkBuddyPerchShown`).
      if (child.id === "nm-buddy" || child.classList.contains("sidebar-collapsed")) continue;
      const box = child.getBoundingClientRect();
      //: As wide as the companion is enough to stand on (a toolbar button,
      //: a chip row, a tile): it was 96px, which left most buttons out.
      //: A box with no size of its own is looked inside (INBOX 521): an open
      //: board's view is 0px tall round its absolutely placed toolbars, so a
      //: board or map offered no surface but the window's bars.
      if (box.width < minW || box.height < 24 || box.bottom < 0 || box.top > innerHeight || box.right < 0 || box.left > innerWidth) {
        if ((!box.width || !box.height) && depth < 8 && (typeof child.checkVisibility !== "function" || child.checkVisibility())) walk(child, depth + 1);
        continue;
      }
      //: A closed menu keeps its box while faded out (the timeline's
      //: Options list, `visibility: hidden` at opacity 0): with panels
      //: preferred on every tab (round 7) it was chosen, and the companion
      //: hung in mid-air over a row from a menu nobody could see.
      if (typeof child.checkVisibility === "function" && !child.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
      //: Nor a field you type into: sitting on a document's editor its
      //: tail hung over the first line of what you were writing.
      if (child.matches("textarea, input, select, [contenteditable='true'], .cm-editor")) continue;
      //: Never a thing inside a run of words (the owner: "atlas companion
      //: just perched in the middle of the weekly digest"): a highlighted
      //: phrase, a code span or a link inside a paragraph has a surface of
      //: its own but is text, and standing on it put the figure over the
      //: words around it.
      if (child.closest("p, blockquote, pre, h1, h2, h3, h4, h5, h6") && !child.matches("button, [role='button']")) continue;
      //: **Only what is drawn** (INBOX 521, the owner's screenshot: standing
      //: in empty space under a card). A named kind (a `section`, a `form`,
      //: a list) counted whether or not it drew anything, so its top edge
      //: was a line in the air; now all but a wide control must paint.
      let surface = child.matches("button, a[href], [role='button']") && box.width >= minW;
      if (!surface) {
        const cs = getComputedStyle(child);
        surface = (child.matches(NAME_MARK_BUDDY_SURFACES) || !cs.display.startsWith("inline")) && nameMarkBuddyPainted(cs);
      }
      if (surface) found.push([child, box]);
      //: Nor into what is drawn on a canvas (INBOX 521): a board's notes and
      //: a map's topics are the person's work, panned and redrawn under it;
      //: it sat on one and stayed in the air when the next board opened.
      if (depth < 8 && !child.matches("button, a[href], [role='button'], svg, canvas") && !nameMarkBuddyOverCanvas(child, true)) walk(child, depth + 1);
    }
  };
  walk(page, 0);
  return found;
}

//: Draws a surface: a fill, a shadow, or a top border that shows.
function nameMarkBuddyPainted(cs) {
  const seen = (c) => !!c && c !== "transparent" && !/^rgba\(.*,\s*0\)$/.test(c);
  return seen(cs.backgroundColor) || cs.backgroundImage !== "none" || cs.boxShadow !== "none"
    || (cs.borderTopStyle !== "none" && parseFloat(cs.borderTopWidth) > 0 && seen(cs.borderTopColor));
}

function nameMarkBuddyEdges(tab) {
  if (nameMarkBuddyIndex && nameMarkBuddyIndex.tab === tab) return nameMarkBuddyIndex.edges;
  const { top, bottom } = nameMarkBuddyLedges();
  const floor = top ? top.bottom : 0;
  const ceiling = bottom ? bottom.top : innerHeight;
  const edges = [];
  if (top) edges.push({ el: document.getElementById("top-bar"), type: "under", kind: "hang", y: top.bottom, left: top.left, right: top.right, top: top.top, bottom: top.bottom });
  if (bottom) {
    const dock = document.getElementById("phone-tab-dock");
    const el = nameMarkBuddyShown(dock) ? dock : document.getElementById("status-bar");
    edges.push({ el, type: "top", kind: "bar", y: bottom.top, left: bottom.left, right: bottom.right, top: bottom.top, bottom: bottom.bottom });
  }
  const page = document.getElementById(`tab-${tab}`);
  //: Two surfaces whose edges fall on the same line (a card and the list
  //: inside it) are one edge to stand on.
  const same = (type, y, left, right) => edges.some((e) => e.type === type && Math.abs(e.y - y) < 4 && Math.min(e.right, right) - Math.max(e.left, left) > (right - left) * 0.7);
  let count = 0;
  for (const [el, box] of nameMarkBuddySurfaceWalk(page)) {
    //: The chat's dock is its toolbar's kind (INBOX 443): as a card it came
    //: after the sidebar's eight saved chats and the head's controls, past
    //: the dozen of each kind looked at, and was never considered at all.
    const kind = el.matches(".dock, [role='toolbar'], [role='tablist'], .toolbar, nav, header, .dash-toolbar, .chat-dock, .wb-topbar") ? "dock" : "card";
    const span = { el, left: box.left, right: box.right, top: box.top, bottom: box.bottom };
    //: **Top edges only, and a card's own** (the owner, 2026-09-27, again:
    //: Atlas sat over the Weekly digest, "just under the title, over
    //: 'Academics and Tech...'"; wanted: "valid perches are top edges only,
    //: and never within a card's content box below its heading"). A surface
    //: inside a content card (one smaller than most of the window: a whole
    //: tab's panel is not one) whose top is below the card's own is a row
    //: of what the card says, not a ledge; and a panel's underside is gone
    //: as a place to hang (it hung over the lines under a card's heading).
    //: The top bar's underside stays (`hang`, above).
    if (nameMarkBuddyInsideCard(el, box)) continue;
    if (box.top > floor + 20 && box.top < ceiling - 20 && !same("top", box.top, box.left, box.right)) edges.push({ ...span, type: "top", kind, y: box.top });
    //: A toolbar over a canvas (a board's, a map's, the graph's) is the one
    //: panel it may hang from (INBOX 521): there is no room above it under
    //: the top bar, and under it is ground, not a card's lines.
    if (kind === "dock" && box.height < 80 && box.bottom < ceiling - NMB_H && nameMarkBuddyOverCanvas(el)) edges.push({ ...span, type: "under", kind: "dock", y: box.bottom });
    if (box.height >= 80) edges.push({ ...span, type: "side", kind: "side" });
    count += 1;
    if (count >= NMB_SURFACE_CAP) break;
  }
  nameMarkBuddyIndex = { tab, edges };
  if (page && typeof ResizeObserver === "function") {
    if (!nameMarkBuddyIndexObserver) nameMarkBuddyIndexObserver = new ResizeObserver(nameMarkBuddyIndexReset);
    nameMarkBuddyIndexObserver.disconnect();
    nameMarkBuddyIndexObserver.observe(page);
  }
  return edges;
}
window.addEventListener("resize", nameMarkBuddyIndexReset, { passive: true });
document.addEventListener("scroll", nameMarkBuddyIndexReset, { passive: true, capture: true });

//: A canvas or drawing as big as a pane beside `el` (or, `host`, in it).
function nameMarkBuddyOverCanvas(el, host = false) {
  const root = host ? el : el.parentElement;
  for (const c of root?.querySelectorAll(host ? ":scope > canvas, :scope > svg" : ":scope > canvas, :scope > svg, :scope > * > canvas, :scope > * > svg") || []) {
    const b = c.getBoundingClientRect();
    if (b.width >= 400 && b.height >= 300) return true;
  }
  return false;
}

//: Inside a content card, below its top: see `nameMarkBuddyEdges`.
const NMB_CARDS = ".card, .dash-widget, .widget, .note-card, .library-card, .msg, li, .empty-state";
function nameMarkBuddyInsideCard(el, box) {
  const card = el.parentElement?.closest(NMB_CARDS);
  if (!card || card.id?.startsWith("tab-")) return false;
  //: A panel with its own toolbar holds cards; it is not one (INBOX 521: a
  //: Library sub-tab with a few files, its panel short of 60% of the window,
  //: hid every card in it and left only the window's bars).
  //: Its own cards and toolbars only: a list's rows stay lines of what it
  //: says (perchwords.js: on the Notes list's rows, over their words).
  if (el.matches(".dock, [role='toolbar'], .card, .library-card, .note-card, article") && card.querySelector(":scope > .dock, :scope > [role='toolbar']")) return false;
  const cb = card.getBoundingClientRect();
  if (cb.height > innerHeight * 0.6) return false;
  return box.top > cb.top + 6;
}

//: **Words under it, measured, not sampled** (the owner: "every settle
//: validated against text rects"). The sampled share (`nameMarkBuddyCovers`)
//: looks at nineteen points and missed a heading's line between two rows of
//: them (measured, perchwords.js: 289 square px of "Start something" under
//: a perch it scored clean). This takes the blocks under the figure (from
//: five points of each part of its shape) and adds up where the line boxes
//: of their words, as far as their scroll box shows them, fall inside the
//: shape, in square px. At most 400 text nodes a call; only a perch about
//: to be chosen is measured.
function nameMarkBuddyWordsUnder(x, y, pose, legs = "") {
  const parts = nameMarkBuddyShape(x, y, pose, legs).map((p) => ({ left: p.left + 2, top: p.top + 2, right: p.right - 2, bottom: p.bottom - 2 }));
  const roots = new Set();
  for (const p of parts) {
    for (const [fx, fy] of [[0.2, 0.2], [0.8, 0.2], [0.5, 0.5], [0.2, 0.8], [0.8, 0.8]]) {
      const px = p.left + (p.right - p.left) * fx;
      const py = p.top + (p.bottom - p.top) * fy;
      if (px < 0 || py < 0 || px >= innerWidth || py >= innerHeight) continue;
      const el = document.elementsFromPoint(px, py).find((node) => !node.closest("#nm-buddy"));
      if (!el || el === document.body || el === document.documentElement || el.closest("#top-bar, #status-bar")) continue;
      const root = el.closest(NMB_CARDS) || el.parentElement || el;
      if (!root.id?.startsWith("tab-")) roots.add(root);
      else roots.add(el);
    }
  }
  let area = 0;
  let seen = 0;
  const range = document.createRange();
  for (const root of roots) {
    const scroller = nameMarkBuddyScroller(root);
    const clip = scroller ? scroller.getBoundingClientRect() : { left: 0, top: 0, right: innerWidth, bottom: innerHeight };
    //: **Only what is drawn counts toward the cap** (INBOX 812: Atlas over the
    //: Ask answer's "You asked:" line). The walk used to count every text node,
    //: and the Ask card holds hundreds that are not on screen (the closed
    //: history list, the idle suggestions) ahead of the answer's own, so the
    //: cap was spent before it got there and the words under the figure read
    //: as 0 (measured: 1986 square px with 51 hidden nodes, 0 with 501). A
    //: hidden subtree is skipped whole, and a node with no words is not one.
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => (node.nodeType === 1 && typeof node.checkVisibility === "function" && !node.checkVisibility() ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    for (let n = walker.nextNode(); n && seen < 400; n = walker.nextNode()) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      seen += 1;
      if (n.parentElement?.closest("#nm-buddy")) continue;
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) {
        const left = Math.max(r.left, clip.left);
        const right = Math.min(r.right, clip.right);
        const top = Math.max(r.top, clip.top);
        const bottom = Math.min(r.bottom, clip.bottom);
        if (right <= left || bottom <= top) continue;
        for (const p of parts) {
          const w = Math.min(right, p.right) - Math.max(left, p.left);
          const h = Math.min(bottom, p.bottom) - Math.max(top, p.top);
          if (w > 0 && h > 0) area += w * h;
        }
      }
    }
  }
  return area;
}
const NMB_WORDS_PX = 12;
const NMB_FIT_SCALE = 0.75;

//: What it can do at a place on an edge: on a top edge sit with its legs
//: over (the owner's "dangle their legs"), sit with them tucked where they
//: would cover something, or stand; under one, hang.
function nameMarkBuddyStances(edge, x) {
  if (edge.type === "under") return [{ pose: "hang", legs: "", x, y: edge.y - NMB_GRIP }];
  if (edge.type !== "top") return [];
  return [
    { pose: "sit", legs: "", x, y: edge.y - NMB_SEAT },
    { pose: "sit", legs: "tuck", x, y: edge.y - NMB_SEAT, alt: 0.2 },
    { pose: "stand", legs: "", x, y: edge.y - NMB_FEET + 1, alt: 0.4 },
    //: The last resort on the bottom bar, for a small window with nowhere
    //: free: tucked behind the bar with only its eyes over the edge
    //: (`legs: "peek"`), ducking when the pointer comes near.
    ...(edge.kind === "bar" ? [{ pose: "sit", legs: "peek", x, y: edge.y - NMB_SEAT, alt: 7 }] : []),
  ];
}

//: The tab's candidate perches, in its own order of preference: each edge
//: kind at a few places along it from the right-hand end, every stance.
//: `focus`, an x: the places along each edge nearest it instead of from its
//: right-hand end (a toss comes down somewhere in particular).
function nameMarkBuddyPerches(tab, focus = null) {
  const { top } = nameMarkBuddyLedges();
  const floor = top ? top.bottom : 0;
  const lo = NMB_GUTTER;
  const hi = innerWidth - NMB_GUTTER - NMB_W;
  const along = (from, to, step, limit) => {
    const xs = [];
    if (focus !== null) {
      const all = [];
      for (let x = to; x >= from; x -= step) all.push(Math.round(x));
      return all.sort((a, b) => Math.abs(a - focus) - Math.abs(b - focus)).slice(0, limit);
    }
    for (let x = to; x >= from && xs.length < limit; x -= step) xs.push(Math.round(x));
    return xs;
  };
  const edges = nameMarkBuddyEdges(tab);
  const order = NAME_MARK_BUDDY_ORDER[tab] || ["bar", "hang", "dock", "card", "under"];
  const out = [];
  order.forEach((kind, rank) => {
    let i = 0;
    let used = 0;
    //: Panels before the controls standing in them (INBOX 521: a Library
    //: panel's sub-tab buttons and filter chips took all twelve, and the
    //: cards under them were never looked at).
    const ctl = (e) => (e.el?.matches?.("button, a[href], [role='button'], [role='tab']") ? 1 : 0);
    for (const edge of edges.filter((e) => e.kind === kind).sort((a, b) => ctl(a) - ctl(b))) {
      //: The first dozen of each kind, top of the page first: enough to
      //: choose from, and a placement stays a few milliseconds.
      used += 1;
      if (used > 12) break;
      const wide = kind === "bar" || kind === "hang";
      //: Along the whole of a long edge, not its right-hand 240px: a dock
      //: the window's width is free only in its middle (INBOX 521).
      const xs = along(Math.max(lo, edge.left + (wide ? 0 : 8)), Math.min(hi, edge.right - (wide ? 0 : 8) - NMB_W), wide ? 40 : 48, wide ? 40 : kind === "dock" ? Math.min(30, Math.max(5, Math.ceil((edge.right - edge.left) / 48))) : 5);
      for (const x of xs) {
        for (const stance of nameMarkBuddyStances(edge, x)) {
          //: Nothing but the top bar's own underside may put it over the
          //: top bar.
          if (stance.y < floor + 2 && !(kind === "hang")) continue;
          out.push({ ...stance, kind, edge, anchor: kind === "bar" || kind === "hang" ? null : edge.el, rank, i });
          i += 1;
        }
      }
    }
  });
  return out;
}

//: The best free perch: never over a control, then the least text hidden,
//: then the tab's preference, then the right-hand end. The perch it is on
//: already wins a close call, so a page that shifts a little does not send
//: it pacing.
function nameMarkBuddyChoose(tab, obstacles, near = null, per = 12) {
  let best = null;
  let soiled = null;
  let scored = 0;
  nmbCoverCache = new Map();
  for (const perch of nameMarkBuddyPerches(tab, near && per < 12 ? near[0] : null)) {
    if (perch.x < 0 || perch.y < 0 || perch.y + NMB_H > innerHeight + 2) continue;
    const here = perch.kind === nmb.perch && perch.pose === nmb.pose && Math.abs(perch.x - nmb.x) < 24 && Math.abs(perch.y - nmb.y) < 24;
    //: Near (a panel scrolled away, a new tab): every 12px of the way costs
    //: a point, so a perch a screen away has to be much better to be chosen.
    //: A toss asks for 4: where it comes down matters three times as much
    //: as the tab's preferred kind of perch.
    const way = near ? Math.hypot(perch.x - near[0], perch.y - near[1]) / per : 0;
    const ceiling = 100 - perch.rank * 9 - perch.i * 0.2 - (perch.alt || 0) * 3 + (here ? 4 : 0) - way;
    //: Its best score is with nothing under it; when even that cannot beat
    //: the best so far, it is not sampled at all (INBOX 426 x: the sampling
    //: is a hit test a point, and a choice with `near` took 176ms).
    if (best && ceiling <= best.score) {
      scored += 1;
      if (scored >= (near ? 120 : 36)) break;
      continue;
    }
    if (nameMarkBuddyHits(perch.x, perch.y, perch.pose, obstacles, perch.legs)) continue;
    const covers = nameMarkBuddyCovers(perch.x, perch.y, perch.pose, perch.legs);
    //: Any words under it at all cost more than a step along the ledge:
    //: sampling is sparse, and one hit is usually a word half hidden. A
    //: perch over words is kept only as the last resort: any clean one wins.
    perch.score = ceiling - (covers ? 25 + covers * 120 : 0);
    if (covers) {
      if (!soiled || perch.score > soiled.score) soiled = perch;
      scored += 1;
      if (scored >= (near ? 120 : 36)) break;
      continue;
    }
    scored += 1;
    if (!best || perch.score > best.score) {
      //: Clean by the samples; measured before it may win.
      const words = nameMarkBuddyWordsUnder(perch.x, perch.y, perch.pose, perch.legs);
      if (words > NMB_WORDS_PX) {
        perch.score = ceiling - 25 - Math.min(120, words / 20);
        perch.words = words;
        if (!soiled || perch.score > soiled.score) soiled = perch;
        if (scored >= (near ? 120 : 36)) break;
        continue;
      }
      best = perch;
    }
    if ((!near && perch.rank === 0) || scored >= (near ? 120 : 36)) break;
  }
  nmbCoverCache = null;
  if (best) return best;
  //: **Smaller where space is small** (the owner, 2026-09-27: "size and
  //: proportion depend on the perch; it scales down where space is small
  //: and never overlaps text"). Nothing clean at its own size: the same
  //: search at `NMB_FIT_SCALE`, and a clean edge found so is taken with
  //: that size (`spot.fit`, applied by `nameMarkBuddyMoveTo`, eased).
  if (!nmb.fitting && (nmb.scale || 1) > NMB_FIT_SCALE + 0.05) {
    const saved = nmb.scale || 1;
    nmb.fitting = true;
    nmb.scale = NMB_FIT_SCALE;
    let small = null;
    try {
      nameMarkBuddyIndexReset();
      small = nameMarkBuddyChoose(tab, obstacles, near, per);
    } finally {
      nmb.scale = saved;
      nmb.fitting = false;
      nameMarkBuddyIndexReset();
    }
    if (small && !small.words && !["corner"].includes(small.kind) && small.legs !== "peek") return { ...small, fit: NMB_FIT_SCALE };
  }
  //: **Never over words when it can help it**: nothing clean on any edge
  //: (a small window, a page of text), it tucks behind the bottom bar with
  //: only its eyes over it, at the free end, or stands in the corner; a
  //: perch over words is the last of all, and the one with the fewest.
  const { bottom } = nameMarkBuddyLedges();
  const fallbacks = [];
  if (bottom) {
    for (let x = innerWidth - NMB_GUTTER - NMB_W; x >= NMB_GUTTER; x -= 96) fallbacks.push({ kind: "bar", pose: "sit", legs: "peek", x, y: bottom.top - NMB_SEAT, edge: { el: document.getElementById("status-bar"), type: "top", kind: "bar", y: bottom.top } });
  }
  const corner = { kind: "corner", pose: "stand", legs: "", x: innerWidth - NMB_GUTTER - NMB_W, y: (bottom ? bottom.top : innerHeight) - NMB_FEET - NMB_GUTTER };
  fallbacks.push(corner);
  //: A peek is checked too now (`nameMarkBuddyHits`): its eyes were over
  //: New note on the phone (INBOX 521, perchall.js).
  const over = bottom ? obstacles.filter((box) => box.top < bottom.top - 2) : obstacles;
  const clear = (spot) => !nameMarkBuddyHits(spot.x, spot.y, spot.pose, obstacles, spot.legs);
  for (const spot of fallbacks) {
    if (!clear(spot)) continue;
    if (nameMarkBuddyWordsUnder(spot.x, spot.y, spot.pose, spot.legs) <= NMB_WORDS_PX) return spot;
  }
  //: **Never the corner over a control** (INBOX 443): on the phone's Chat,
  //: with an answer filling the pane down to the dock, there was no clean
  //: edge and the corner was taken anyway, over Send by 32px
  //: (companionchat.js, 390). Tucked behind the bottom bar, only its eyes
  //: show, over words at worst and never over a control.
  if (soiled) return soiled;
  //: None clear: never under a button floating over the page (the list
  //: scrolls out from under it, New note does not), then the least share
  //: of any control hidden.
  const floating = [...document.querySelectorAll(".dock-fab, #scroll-top.visible, .chat-jump-latest:not(.hidden)")].map((el) => nameMarkBuddyShown(el)).filter(Boolean);
  const under = (spot, boxes) => nameMarkBuddyShape(spot.x, spot.y, spot.pose, spot.legs).reduce((sum, p) => sum + boxes.reduce((s, b) => s + Math.max(0, Math.min(p.right, b.right) - Math.max(p.left, b.left)) * Math.max(0, Math.min(p.bottom, b.bottom) - Math.max(p.top, b.top)) / Math.max(1, (b.right - b.left) * (b.bottom - b.top)), 0), 0);
  const harm = (spot) => (under(spot, floating) > 0 ? 100 : 0) + under(spot, over);
  const tucked = fallbacks.filter((spot) => spot.legs === "peek").sort((a, b) => harm(a) - harm(b))[0];
  return tucked && nameMarkBuddyHits(corner.x, corner.y, corner.pose, obstacles, corner.legs) ? tucked : corner;
}

function nameMarkBuddySpots() {
  try {
    const spots = prefs.json("nm-buddy-spots", {});
    return spots && typeof spots === "object" ? spots : {};
  } catch (e) {
    return {};
  }
}

function nameMarkBuddyKeepSpots(spots) {
  try {
    prefs.set("nm-buddy-spots", JSON.stringify(spots));
  } catch (e) {
    // Remembered for this visit only; the companion stays where it is.
  }
}

//: A path back to a panel from the nearest ancestor with an id, so a spot
//: kept on it finds the same panel after a reload.
function nameMarkBuddySelector(el) {
  if (!el) return "";
  const parts = [];
  for (let node = el; node && node !== document.body; node = node.parentElement) {
    if (node.id) {
      parts.unshift(`#${CSS.escape(node.id)}`);
      break;
    }
    let nth = 1;
    for (let sib = node.previousElementSibling; sib; sib = sib.previousElementSibling) {
      if (sib.tagName === node.tagName) nth += 1;
    }
    parts.unshift(`${node.tagName.toLowerCase()}:nth-of-type(${nth})`);
  }
  return parts.join(" > ");
}

//: **What is kept of a spot you chose: the surface, not the pixels.** The
//: panel's selector, which of its edges, and how far along it from the
//: nearer end, so it stays on that panel when the layout moves or the
//: window resizes; a spot in open air keeps its place held to the nearer
//: window edges.
function nameMarkBuddySpotFor(spot) {
  const edge = spot.edge;
  if (edge?.el && ["top", "under", "side"].includes(edge.type)) {
    const fromRight = spot.x + NMB_W / 2 > (edge.left + edge.right) / 2;
    return {
      sel: nameMarkBuddySelector(edge.el), type: edge.type, side: spot.side || "", pose: spot.pose, legs: spot.legs || "",
      fromRight, along: Math.round(fromRight ? edge.right - spot.x : spot.x - edge.left), dy: Math.round(spot.y - edge.top),
    };
  }
  return { x: Math.round(spot.x), y: Math.round(spot.y), pose: spot.pose, legs: spot.legs || "", w: innerWidth, h: innerHeight };
}

//: A kept spot, for the page as it is now; null when its panel is gone,
//: and the tab's own best perch is used instead.
const NMB_EDGE_NEAR = 160;
function nameMarkBuddyRestore(spot) {
  const clampX = (x) => Math.min(Math.max(0, x), innerWidth - NMB_W);
  const clampY = (y) => Math.min(Math.max(0, y), innerHeight - NMB_H);
  if (spot.sel) {
    let el = null;
    try {
      el = document.querySelector(spot.sel);
    } catch (e) {
      el = null;
    }
    const box = el && nameMarkBuddyPerchShown(el);
    if (!box) return null;
    const edge = { el, type: spot.type, left: box.left, right: box.right, top: box.top, bottom: box.bottom, y: spot.type === "under" ? box.bottom : box.top };
    let x = spot.fromRight ? box.right - Number(spot.along) : box.left + Number(spot.along);
    let y = box.top + Number(spot.dy);
    if (spot.type === "under") y = box.bottom - NMB_GRIP;
    else if (spot.type === "top") y = box.top - (spot.pose === "sit" ? NMB_SEAT : NMB_FEET - 1);
    else x = spot.side === "left" ? box.left - NMB_W + 6 : box.right - 6;
    return { kind: "yours", pose: spot.pose, legs: spot.legs || "", side: spot.side || "", x: clampX(x), y: clampY(y), edge, anchor: el };
  }
  //: **A place on the window stays where it is** (INBOX 426 l, the owner:
  //: "when I press the option to stay in the same spot across pages ... it
  //: still moves sometimes"). It used to keep its distance from whichever
  //: half of the window it was in, so one pinned near the middle jumped by
  //: the whole change in size whenever the window was resized or the app
  //: opened at another size (measured: 200px for a 900 to 700px window).
  //: Now it keeps its place, and only a place close to the right or bottom
  //: edge (on the bottom bar, in a corner, within 160px) keeps its distance
  //: from that edge, so it stays on the bar. Inside the window either way.
  const w = Number(spot.w) || innerWidth;
  const h = Number(spot.h) || innerHeight;
  const sx = Number(spot.x);
  const sy = Number(spot.y);
  const toRight = w - sx - NMB_W;
  const toBottom = h - sy - NMB_H;
  const x = toRight < NMB_EDGE_NEAR && toRight < sx ? innerWidth - (w - sx) : sx;
  const y = toBottom < NMB_EDGE_NEAR && toBottom < sy ? innerHeight - (h - sy) : sy;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  //: A place pinned on every page keeps its pose; a spot dropped in open
  //: air floats.
  return spot.keep
    ? { kind: "yours", pose: spot.pose || "float", legs: spot.legs || "", side: spot.side || "", x: clampX(x), y: clampY(y) }
    : { kind: "yours", pose: "float", legs: "", x: clampX(x), y: clampY(y) };
}

//: Your spot, unless something has come up under it since (the back-to-top
//: button, a toast): then the nearest free place along the same line, for
//: as long as it is there. The spot itself is kept.
function nameMarkBuddyStepAside(spot, obstacles, far = 320) {
  if (!nameMarkBuddyHits(spot.x, spot.y, spot.pose, obstacles, spot.legs)) return spot;
  //: Along its own edge, not off the end of it into the air (K25: Atlas
  //: stepped 96px aside off the board's dock and was then carried away).
  const along = spot.edge?.type === "top" || spot.edge?.type === "under" ? spot.edge : null;
  const lo = Math.max(0, along?.left ?? 0);
  const hi = Math.min(innerWidth, along?.right ?? innerWidth) - NMB_W;
  for (let d = 16; d <= far; d += 16) {
    for (const x of [spot.x - d, spot.x + d]) {
      if (x < lo || x > hi) continue;
      if (!nameMarkBuddyHits(x, spot.y, spot.pose, obstacles, spot.legs)) return { ...spot, x };
    }
  }
  return spot;
}

//: **Where it lands when you let go** (the owner: "the surfaces I can drag
//: atlas onto are either at the top or bottom and nowhere else"): the
//: nearest surface edge within 80px of where it was let go, in any
//: direction, that it can take without covering a control: sitting or
//: standing on a top edge, hanging from an underside, leaning on a side.
//: Measured from the part of it that would touch the edge (its seat, its
//: soles, its hands, its side). With nothing that close it falls to the
//: first top edge under it; with nothing under it at all it floats where it
//: was let go.
//: **Where you put it, it may rest** (the owner: "atlas or the companion
//: wont let me rest it on the start something buttons on the dashboard").
//: Measured (perchbuttons.js): let go above a Start something tile it fell
//: 172 to 238px to another edge, for two reasons: the dashboard's find
//: field runs the whole width 42px above the tiles, so no figure standing
//: on a tile could miss it, and Atlas's tail reaches 5px into the tile it
//: stands on. For a place you chose, what it stands on is its floor, not
//: something it covers, and a control much wider than it (a find field, a
//: long bar) is still usable round it, so neither stops it there; a control
//: its own size (a button, a chip) still does. The tile it sits on keeps its
//: click (measured at its middle and its top).
function nameMarkBuddyYoursObstacles(obstacles, spot) {
  //: Its floor only when nothing of it hangs over the front: sitting with
  //: its legs over the edge they would cover the button (measured on a 75px
  //: toolbar button: sat on, it took the button's click).
  const overFront = spot?.pose === "sit" && spot?.legs !== "tuck";
  const floor = overFront ? null : spot?.anchor?.isConnected ? spot.anchor.getBoundingClientRect() : spot?.edge ? spot.edge : null;
  const wide = NMB_W * Math.max(0.7, nmb.scale || 1) * 4;
  return obstacles.filter((b) => b.right - b.left < wide
    && !(floor && Math.abs(b.left - floor.left) < 2 && Math.abs(b.top - floor.top) < 2 && Math.abs(b.right - floor.right) < 2));
}
function nameMarkBuddyDrop(x, y, reach = 48) {
  //: Put somewhere by you: no wander to come back from.
  nmb.home = null;
  const tab = nameMarkBuddyTab();
  const obstacles = nameMarkBuddyObstacles(tab);
  const edges = nameMarkBuddyEdges(tab);
  const cx = x + NMB_W / 2;
  const fits = (spot) => spot.x >= 0 && spot.x <= innerWidth - NMB_W && spot.y >= 0 && spot.y <= innerHeight - NMB_H + 8
    && !nameMarkBuddyHits(spot.x, spot.y, spot.pose, nameMarkBuddyYoursObstacles(obstacles, spot), spot.legs);
  const touch = { sit: NMB_SEAT, stand: NMB_FEET, hang: NMB_GRIP };
  let best = null;
  const consider = (spot, d) => {
    if (d > 80 || (best && d >= best.d)) return;
    const free = fits(spot) ? spot : nameMarkBuddyStepAside({ ...spot }, nameMarkBuddyYoursObstacles(obstacles, spot), Math.max(320, reach));
    if (fits(free) && Math.abs(free.x - spot.x) <= reach) best = { ...free, d: d + Math.abs(free.x - spot.x) / 4 };
  };
  for (const edge of edges) {
    if (edge.type === "side") {
      const middle = y + 46;
      if (middle < edge.top || middle > edge.bottom) continue;
      const ly = Math.min(Math.max(y, edge.top), edge.bottom - NMB_H);
      consider({ kind: "yours", pose: "lean", side: "left", legs: "", x: edge.left - NMB_W + 6, y: ly, edge }, Math.abs(x + NMB_W - 6 - edge.left) + 12);
      consider({ kind: "yours", pose: "lean", side: "right", legs: "", x: edge.right - 6, y: ly, edge }, Math.abs(x + 6 - edge.right) + 12);
      continue;
    }
    //: Along the edge: where it is, held inside the edge's own length.
    const along = Math.min(Math.max(cx, edge.left + NMB_W / 2 - 8), edge.right - NMB_W / 2 + 8);
    const dx = Math.abs(along - cx);
    for (const stance of nameMarkBuddyStances(edge, along - NMB_W / 2)) {
      if (stance.legs === "peek") continue;
      const dy = Math.abs(y + touch[stance.pose] - edge.y);
      consider({ kind: "yours", ...stance, edge }, Math.hypot(dx, dy) + (stance.alt || 0) * 10);
    }
  }
  if (best) return best;
  let fall = null;
  for (const edge of edges) {
    if (edge.type !== "top" || cx < edge.left || cx > edge.right) continue;
    const sx = Math.min(Math.max(x, edge.left - 16), edge.right - NMB_W + 16);
    for (const stance of nameMarkBuddyStances(edge, sx)) {
      if (stance.y < y || stance.legs === "peek") continue;
      const d = stance.y - y + (stance.alt || 0) * 10;
      //: A little along the edge is still "below": the nearest free place
      //: within 96px of where it was let go.
      const spot = fits(stance) ? stance : nameMarkBuddyStepAside({ ...stance }, nameMarkBuddyYoursObstacles(obstacles, { ...stance, edge }));
      if (Math.abs(spot.x - sx) > 96 || !fits(spot)) continue;
      if (!fall || d < fall.d) fall = { kind: "yours", ...spot, edge, d, falls: true };
    }
  }
  if (fall) return fall;
  //: Nothing under it: it floats, stepped aside from a control; one it cannot
  //: clear (chat's mode switch) gets the nearest good perch instead.
  const open = nameMarkBuddyStepAside({ kind: "yours", pose: "float", legs: "", x, y }, obstacles);
  return nameMarkBuddyHits(open.x, open.y, "float", obstacles) ? nameMarkBuddyChoose(tab, obstacles, [x, y], 4) || open : open;
}

//: **Where it is drawn: one `transform` on the host.** Its `left` and
//: `top` stay 0, so following a panel every frame is a compositor change and
//: never a layout; a walk, a hop and a drag ride on top through `translate`,
//: which adds to it.
//: `x` and `y` are always where it is in the window, which is what every
//: choice here reasons in; riding a scroll area, it is drawn at that point
//: in the area's own content, which the browser then scrolls.
function nameMarkBuddyPut(buddy, x, y) {
  nmb.x = x;
  nmb.y = y;
  const r = nmb.ride;
  nmb.lx = r ? x - r.left : x;
  nmb.ly = r ? y - r.top + r.el.scrollTop : y;
  buddy.style.transform = `translate(${nmb.lx}px, ${nmb.ly}px)`;
  if (nmb.menuPlace && nameMarkBuddyMenuOpen()) nmb.menuPlace();
}

//: The lean of a carried or flying companion, against the pull: the body by
//: 0.4 deg a unit and each leg by 1 deg, 0 clearing it. Written to the
//: elements that wear it, not as a custom property on #nm-buddy: an inherited
//: property set every frame restyled the whole drawing, and a thrown Atlas ran
//: at 29 frames in 1.6 s against 92 without it (test_companion_motion.py).
function nameMarkBuddySway(buddy, sway) {
  const lean = Math.round(sway * 10) / 10;
  for (const el of buddy.querySelectorAll(".nm-figure:not(.nmb-fig-leaving), .nmb-leg")) {
    el.style.rotate = lean ? `${el.classList.contains("nmb-leg") ? lean : lean * 0.4}deg` : "";
  }
}

//: **Leaves with its panel, like the page does** (INBOX 426 x, the owner:
//: "if I scroll really fast the companion will just float in the corner
//: ... then it will disappear"). On a panel inside a scroll area it rides
//: that area's scroll: the rider is moved by a scroll-driven animation
//: (a `ScrollTimeline` on the area, one pixel of travel per pixel
//: scrolled), which the browser runs with the scroll itself, however fast,
//: with no script in the way. The band clips it to the area's visible
//: box, below the top bar and any bar that sticks, so it goes out of sight
//: with its panel and is still there when the panel comes back. It moves
//: to a new perch only on its own beat (`nameMarkBuddySeen`). Where there
//: is no `ScrollTimeline` (an older WebKit) it keeps being followed by
//: script, held at the edge (`nameMarkBuddyFollow`).
const NMB_RIDE_PX = 1e6;
function nameMarkBuddyRide(scroller, x = nmb.x, y = nmb.y) {
  const buddy = document.getElementById("nm-buddy");
  const band = document.getElementById("nm-buddy-band");
  const shutter = band?.firstElementChild;
  const rider = shutter?.firstElementChild;
  if (!buddy || !band || !rider || nmb.visit) return;
  const want = scroller && typeof ScrollTimeline === "function" && typeof rider.animate === "function" ? scroller : null;
  if ((nmb.ride?.el || null) !== want) {
    nmb.rideAnim?.cancel();
    nmb.shutterAnim?.cancel();
    nmb.rideAnim = nmb.shutterAnim = null;
    nmb.ride = want ? { el: want, s0: 0, up: 0, down: 0 } : null;
    band.classList.toggle("nmb-riding", !!want);
    if (want) {
      //: One timeline, two transforms on it: the shutter (below) and the
      //: rider inside it, so the compositor moves both in the scroll's own
      //: frame. Their keyframes are set from the perch by the band's
      //: measure just below (`nameMarkBuddyRideClip`).
      const timeline = new ScrollTimeline({ source: want, axis: "block" });
      const opts = { timeline, fill: "both", easing: "linear", rangeStart: "0px", rangeEnd: `${NMB_RIDE_PX}px` };
      const frames = nameMarkBuddyRideFrames(0, 0, 0);
      nmb.shutterAnim = shutter.animate(frames.shutter, opts);
      nmb.rideAnim = rider.animate(frames.rider, opts);
    } else {
      for (const k of ["left", "top", "width", "height"]) band.style[k] = "";
    }
  }
  if (nmb.ride) nameMarkBuddyRideBox(x, y, true);
  if (Number.isFinite(x) && Number.isFinite(y)) nameMarkBuddyPut(buddy, x, y);
}

//: **Behind the bar its perch goes under** (INBOX 431 (5), the owner: "if
//: it is perched on like a chat message bubble or a library card, when it
//: scrolls with them it should probably go behind the top bar like the
//: thing it is perched on not in front of it"). The band is widened at
//: placement to take in a head that reaches over the top bar (or a bar that
//: sticks in the area), so a perch at the very top of a panel is drawn
//: whole where it stands; and while it stayed widened, the scroll carried
//: the figure up over the bar its perch had gone under (measured,
//: companionstack.js: 62px past its perch's clip line on a chat message, a
//: library card and a note card; 41px over the top bar at the Large size).
//: A shutter inside the band, a clipping box the band's size, is moved by
//: the same scroll: from the scroll it was perched at (`s0`), every px the
//: panel scrolls up brings the shutter's top edge down a px, until it is at
//: the bar's edge (`up` px down) and the figure is cut there exactly as its
//: perch is; scrolled the other way, its bottom edge comes up to the bottom
//: bar's edge (`down` px) the same way. It is shut by the time the line it
//: touches its perch on reaches the bar (`upSpan`, `downSpan`: the scroll
//: that takes), so a head over the bar is gone when its perch is, and
//: never slower than the panel moves (a span is at most its gap). Back
//: where it was perched, it is drawn whole again. The rider inside takes
//: the shutter's move back out, so it still goes one px per px scrolled
//: wherever the shutter is. Both are piecewise linear in the scroll offset,
//: so they are keyframes on the one timeline, at offsets of scroll px over
//: `NMB_RIDE_PX`. On the top bar itself it rides nothing
//: (`nameMarkBuddyGlue`: the bars hold nothing), in a band over the bar,
//: so it stays in front of it.
function nameMarkBuddyRideFrames(s0, up, down, upSpan = up, downSpan = down) {
  const R = NMB_RIDE_PX;
  const at = Math.min(Math.max(0, s0), R / 2);
  const spanUp = Math.min(Math.max(1, upSpan), Math.max(1, up));
  const spanDown = Math.min(Math.max(1, downSpan), Math.max(1, down));
  const shut = (u) => (u < at ? -down * Math.min(1, (at - u) / spanDown) : up * Math.min(1, (u - at) / spanUp));
  const us = [...new Set([0, Math.max(0, at - spanDown), at, at + spanUp, R])].sort((a, b) => a - b);
  return {
    shutter: us.map((u) => ({ offset: u / R, transform: `translateY(${shut(u)}px)` })),
    rider: us.map((u) => ({ offset: u / R, transform: `translateY(${-(u + shut(u))}px)` })),
  };
}

function nameMarkBuddyRideClip(r) {
  const frames = nameMarkBuddyRideFrames(r.s0, r.up, r.down, r.upSpan, r.downSpan);
  nmb.shutterAnim?.effect?.setKeyframes(frames.shutter);
  nmb.rideAnim?.effect?.setKeyframes(frames.rider);
}

//: The band's box: the area's visible box, from under the top bar (or a
//: bar that sticks in it) to over the bottom one, widened to take in where
//: it was put, so a perch with its head a little over a sticking bar is
//: not clipped where it stands (the shutter above closes that widening as
//: the panel scrolls away). `fresh` measures the bars again (a placement);
//: otherwise the insets found then are kept and only the area's own box is
//: read.
function nameMarkBuddyRideBox(x = nmb.x, y = nmb.y, fresh = false) {
  const r = nmb.ride;
  const band = document.getElementById("nm-buddy-band");
  if (!r || !band) return;
  const box = r.el.getBoundingClientRect();
  let lines = null;
  if (fresh || r.insetTop === undefined) {
    const { lo, hi } = nameMarkBuddyBand(r.el, nmb.glue?.el);
    const over = nameMarkBuddyOverhang();
    r.insetTop = Math.min(lo, y - over.top) - box.top;
    r.insetBottom = box.bottom - Math.max(hi, y + NMB_H + over.bottom);
    r.insetLeft = Math.min(box.left + r.el.clientLeft, x - over.left) - box.left;
    r.insetRight = box.right - Math.max(box.left + r.el.clientLeft + r.el.clientWidth, x + NMB_W + over.right);
    lines = { lo, hi };
  }
  const left = Math.round(box.left + r.insetLeft);
  const top = Math.round(box.top + r.insetTop);
  const width = Math.max(0, Math.round(box.right - r.insetRight) - left);
  const height = Math.max(0, Math.round(box.bottom - r.insetBottom) - top);
  if (lines) {
    //: How far the band reaches over each bar, from the band as drawn
    //: (rounded) to the bar's own edge, never short of it; the scroll it
    //: was perched at; and how far the line it touches its perch on (its
    //: seat, its soles, its hands) is from each bar.
    const touch = { sit: NMB_SEAT, stand: NMB_FEET, hang: NMB_GRIP }[nmb.glue?.pose || nmb.pose] ?? 0;
    r.s0 = r.el.scrollTop;
    r.up = Math.max(0, Math.ceil(lines.lo) - top);
    r.down = Math.max(0, top + height - Math.floor(lines.hi));
    r.upSpan = y + touch - lines.lo;
    r.downSpan = lines.hi - (y + touch);
    nameMarkBuddyRideClip(r);
  }
  if (left !== r.left || top !== r.top || width !== r.width || height !== r.height) {
    Object.assign(r, { left, top, width, height });
    band.style.left = `${left}px`;
    band.style.top = `${top}px`;
    band.style.width = `${width}px`;
    band.style.height = `${height}px`;
  }
}

//: How far the drawing reaches past its 64 by 92 box, per side, in px.
//: The band above was widened to the box, but the box is not the drawing:
//: at the Large size the figure is scaled up about the point it touches its
//: perch, and Atlas's rings and tail reach past the box as drawn, so on a
//: perch at the very top of a panel the band cut its rings off (the owner,
//: with the README's companion shot: "the atlas avatar gets cut off at the
//: top"; measured, the figure's top at y=55 against the band's at 77).
//: Worked out from the size and the pose's pivot (the same origins as the
//: CSS in 08-consistency.css, `.nm-buddy-face`), not measured: a placement
//: often lands while the figure is mid-way through its appear, and a rect
//: read then is the small one. `ART_REACH` is the drawing's own reach past
//: its box at size 1, rings and glow included.
function nameMarkBuddyOverhang() {
  const buddy = document.getElementById("nm-buddy");
  const ART_REACH = 10;
  const s = Math.max(0.7, nmb.scale || 1);
  const pose = buddy?.dataset.pose;
  const edge = buddy ? parseFloat(getComputedStyle(buddy).getPropertyValue("--nmb-edge")) : NaN;
  const oy = pose === "hang" ? 5 : pose === "float" ? NMB_H / 2 : Number.isFinite(edge) ? edge : NMB_H - 20;
  const reach = ART_REACH * s;
  const grow = (n) => Math.ceil(Math.max(0, n) + reach);
  return { top: grow(oy * (s - 1)), bottom: grow((NMB_H - oy) * (s - 1)), left: grow((NMB_W / 2) * (s - 1)), right: grow((NMB_W / 2) * (s - 1)) };
}

//: Out of sight with its panel: it stays put, and once the page has been
//: still a moment it asks for a place on its own beat. Back in sight
//: before then, nothing happens at all. Its own timer: it shared the tab
//: follow's (`nmb.awayTimer`), and a tab switch hides the panel it rode,
//: so this cleared the timer that was to bring it onto the new tab and it
//: never came (measured: away for 5s and more after a switch from a
//: scrolled dashboard, until the next switch). Away with its tab, the
//: arrival places it; nothing to do here.
function nameMarkBuddySeen(seen) {
  nmb.outOfSight = !seen;
  clearTimeout(nmb.sightTimer);
  if (nmb.away) return;
  nmb.sightTimer = 0;
  if (seen || !nmb.ride) return;
  const wait = () => {
    nmb.sightTimer = 0;
    if (!nmb.outOfSight || !nmb.ride) return;
    const since = performance.now() - nmbFollow.scrollAt;
    if (since < 1500) {
      nmb.sightTimer = setTimeout(wait, 1600 - since);
      return;
    }
    nameMarkBuddyQueuePlace();
  };
  nmb.sightTimer = setTimeout(wait, 1600);
}

//: The box a panel scrolls in: its nearest ancestor that scrolls, or the
//: window.
function nameMarkBuddyScroller(el) {
  for (let node = el?.parentElement; node && node !== document.body && node !== document.documentElement; node = node.parentElement) {
    const cs = getComputedStyle(node);
    if (/(auto|scroll|overlay)/.test(cs.overflowY) && node.scrollHeight > node.clientHeight + 1) return node;
  }
  return null;
}

//: The band a perch can be seen in: between the top bar and the bottom
//: bar, inside the panel's own scroll box, and under any bar that sticks
//: at the top of it (the Notes sub-tabs, the chat's toolbar), measured
//: where that bar sticks. Only the panel's own ancestors' earlier siblings
//: are looked at, so this stays a few dozen reads, once per perch.
function nameMarkBuddyBand(scroller, el = null) {
  const { top, bottom } = nameMarkBuddyLedges();
  let lo = top ? top.bottom : 0;
  let hi = bottom ? bottom.top : innerHeight;
  const box = scroller?.getBoundingClientRect();
  if (box && box.height) {
    lo = Math.max(lo, box.top);
    hi = Math.min(hi, box.bottom);
  }
  const mine = el?.getBoundingClientRect();
  for (let node = el; mine && node && node !== scroller && node !== document.body; node = node.parentElement) {
    for (let sib = node.previousElementSibling, n = 0; sib && n < 12; sib = sib.previousElementSibling, n += 1) {
      const cs = getComputedStyle(sib);
      if (cs.position !== "sticky" || cs.top === "auto") continue;
      const r = sib.getBoundingClientRect();
      if (r.height > 160 || r.right <= mine.left || r.left >= mine.right) continue;
      lo = Math.max(lo, (box ? box.top : 0) + parseFloat(cs.top) + r.height);
    }
  }
  return { lo, hi };
}

//: **Held to its perch** (INBOX 426 g, m, n, o; the owner: "if it is
//: sitting on a pannel and I scroll or that panel moves it might fall or
//: move with the panel. it needs to be smooth, unintrusive"). A perch on a
//: panel (a card, a dock, a widget, your spot on one) keeps the companion's
//: offset from that panel's corner and the line it touches (its seat, its
//: soles, its hands), and `nameMarkBuddyFollow` puts it back at that offset
//: whenever the panel moves: in the same frame as a scroll, and every frame
//: while anything on the page is moving. The two bars and open air hold
//: nothing: they do not move.
function nameMarkBuddyGlue(spot, x, y) {
  //: A drop carries its edge rather than an anchor; the bars hold nothing.
  const el = spot.kind === "pinned" ? null : spot.anchor || (spot.edge && !["bar", "hang"].includes(spot.edge.kind) ? spot.edge.el : null);
  const box = el?.isConnected ? el.getBoundingClientRect() : null;
  if (!box || (!box.width && !box.height)) {
    nmb.glue = null;
    nameMarkBuddyRide(null, x, y);
    nameMarkBuddyWatch();
    return;
  }
  const scroller = nameMarkBuddyScroller(el);
  nmb.glue = {
    el, sel: nameMarkBuddySelector(el), w: box.width, cls: el.className, dx: x - box.left, dy: y - box.top,
    scroller, band: null, pose: spot.pose, legs: spot.legs || "", lost: false, held: false,
  };
  nameMarkBuddyGlueBand(nmb.glue, y);
  nameMarkBuddyRide(nameMarkBuddyScrollsWith(el, scroller) ? scroller : null, x, y);
  nameMarkBuddyWatch();
}

//: Whether a panel really moves with its area's scroll: not a bar that
//: sticks in it (the Notes sub-tabs, a chat toolbar) or anything inside
//: one, and nothing fixed. Riding one of those, the companion was carried
//: off by a scroll its panel ignored (measured: 120px off its sticking
//: panel for two frames).
function nameMarkBuddyScrollsWith(el, scroller) {
  if (!scroller) return false;
  for (let node = el; node && node !== scroller; node = node.parentElement) {
    const pos = getComputedStyle(node).position;
    if (pos === "sticky" || pos === "fixed") return false;
  }
  return true;
}

//: The band its whole figure may be carried through, widened to take in
//: where it was put: a perch chosen with its head a little over a sticking
//: bar is not "out of sight" the moment it is taken.
function nameMarkBuddyGlueBand(g, y) {
  const band = nameMarkBuddyBand(g.scroller, g.el);
  g.band = { lo: Math.min(band.lo, y), hi: Math.max(band.hi, y + NMB_H) };
  return g.band;
}

//: Puts it back on its panel. Its panel gone from the page (another tab, a
//: list drawn again without it): it floats where it is and looks for a new
//: perch on its own next beat, not at once. Its panel scrolled out of the
//: band it can be seen in: it is carried to the band's edge and held there,
//: and once the scrolling has stopped it walks to the nearest free perch.
//: It is never hidden, and it never jumps: a move this finds that nothing
//: was watching for (the page changed on its own) is eased over 300ms.
function nameMarkBuddyFollow(eased = false) {
  const buddy = document.getElementById("nm-buddy");
  const g = nmb.glue;
  if (!buddy || !g || nmb.visit || buddy.classList.contains("nm-buddy-dragging")) return;
  if (!g.el.isConnected && g.sel) {
    try {
      //: The same panel drawn again, not whatever is in its place now
      //: (INBOX 521: a board's note's path found a map's topic, and it sat
      //: in the air at the note's offset from it).
      const again = document.querySelector(g.sel);
      if (again && again.className === g.cls && Math.abs(again.getBoundingClientRect().width - g.w) <= 8) g.el = again;
    } catch (e) {
      // A selector the page no longer parses: the panel is simply gone.
    }
  }
  //: Folded away or faded out counts as gone (`nameMarkBuddyPerchShown`).
  const folded = g.el.isConnected && (g.el.closest(".sidebar-collapsed") || (g.el.checkVisibility && !g.el.checkVisibility({ opacityProperty: true, visibilityProperty: true })));
  const box = g.el.isConnected && !folded ? g.el.getBoundingClientRect() : null;
  if (!box || (!box.width && !box.height)) {
    //: Its area gone with its panel (another tab): it lets go of the
    //: scroll where it is in the window, so it does not vanish with the tab.
    if (nmb.ride) nameMarkBuddyRide(null);
    if (!g.lost) {
      g.lost = true;
      buddy.dataset.pose = nmb.pose = "float";
      buddy.dataset.legs = nmb.legs = "";
      //: **Its perch went: a new one at once** (the owner, 2026-09-27: "it
      //: was left floating mid-panel for seconds after its perch (a button
      //: on an empty chat) went away"). The queued beat waited 1.2 to 5s;
      //: now a quarter second, for the page to finish drawing what replaced
      //: it. Hidden with its tab, the arrival places it instead.
      if (!nmb.away) {
        clearTimeout(nmb.placeTimer);
        nmb.placeTimer = setTimeout(nameMarkBuddyBeat, 250);
      }
    }
    return;
  }
  if (g.lost) {
    g.lost = false;
    buddy.dataset.pose = nmb.pose = g.pose;
    buddy.dataset.legs = nmb.legs = g.legs;
    if (g.scroller && !nmb.ride) nameMarkBuddyRide(g.scroller, Math.round(box.left + g.dx), Math.round(box.top + g.dy));
  }
  //: Riding its area's scroll, a scroll needs nothing from here; this
  //: puts it back only when the panel moved inside the area (a transform,
  //: content above it growing), and never holds it at an edge: it goes
  //: where its panel goes, clipped with it.
  if (nmb.ride) {
    if (g.held) {
      g.held = false;
      buddy.dataset.pose = nmb.pose = g.pose;
      buddy.dataset.legs = nmb.legs = g.legs;
    }
    nameMarkBuddyRideBox();
    //: Where it is drawn now, with the band where it is now.
    nmb.x = nmb.ride.left + nmb.lx;
    nmb.y = nmb.ride.top + nmb.ly - nmb.ride.el.scrollTop;
    const rx = Math.round(box.left + g.dx);
    const ry = Math.round(box.top + g.dy);
    const ddx = nmb.x - rx;
    const ddy = nmb.y - ry;
    if (Math.abs(ddx) >= 0.5 || Math.abs(ddy) >= 0.5) {
      nameMarkBuddyPut(buddy, rx, ry);
      nameMarkBuddyCatchUp(buddy, ddx, ddy, eased, true);
    }
    return;
  }
  let y = box.top + g.dy;
  const band = g.band || nameMarkBuddyGlueBand(g, y);
  //: **Held at the edge, not carried under a bar.** Its panel slides on
  //: under the top bar (or a bar that sticks) or off the bottom; the
  //: companion stops where its head, or its feet, would meet the bar, lets
  //: go of the panel and floats there, and once the page has been still for
  //: 600ms walks to the nearest free perch.
  const held = y < band.lo - 0.5 || y + NMB_H > band.hi + 0.5;
  if (held !== g.held) {
    g.held = held;
    buddy.dataset.pose = nmb.pose = held ? "float" : g.pose;
    buddy.dataset.legs = nmb.legs = held ? "" : g.legs;
  }
  if (y < band.lo) y = band.lo;
  else if (y + NMB_H > band.hi) y = band.hi - NMB_H;
  const x = Math.round(Math.min(Math.max(0, box.left + g.dx), innerWidth - NMB_W));
  y = Math.round(Math.min(Math.max(0, y), innerHeight - NMB_H));
  const dx = nmb.x - x;
  const dy = nmb.y - y;
  if (dx || dy) {
    nameMarkBuddyPut(buddy, x, y);
    nameMarkBuddyCatchUp(buddy, dx, dy, eased, false);
  }
  //: 600ms after its panel last moved, not after the last frame looked.
  if (!g.held) {
    clearTimeout(nmb.heldTimer);
    nmb.heldTimer = 0;
  } else if (dx || dy || !nmb.heldTimer || g.el !== g.heldEl || box.top !== g.heldTop) {
    g.heldEl = g.el;
    g.heldTop = box.top;
    clearTimeout(nmb.heldTimer);
    nmb.heldTimer = setTimeout(nameMarkBuddyUnheld, 600);
  }
}

//: **A panel that jumped is followed on foot, not jumped with** (the owner,
//: 2026-09-27: "pretty suddenly slightly adjusted its position ... that is
//: unclean"). Content arriving above its panel, a list drawn again, a font
//: landing: the panel moves in one frame, and following it exactly moved the
//: companion in one frame too (measured at start: 142px, then 18px). Such a
//: move is travelled from where it was drawn. A scroll is still
//: followed exactly (riding, the browser does that; otherwise the move came
//: within 200ms of a scroll), and so is a panel carried by its own animation
//: (`nameMarkBuddyPanelMoving`): lagging those would leave it behind its
//: panel. Under `NMB_GLIDE_PX` a move is absorbed as it is. The glide is
//: added to whatever else is moving it (`composite: "add"`), so an entrance
//: or a walk under way keeps going rather than being cut, and a second jump
//: during the first adds its own glide rather than restarting it. `eased`
//: is the slow look's (`nameMarkBuddyWatch`): every move it finds is one
//: nothing announced.
const NMB_GLIDE_PX = 3;
function nameMarkBuddyCatchUp(buddy, dx, dy, eased, riding) {
  const d = Math.hypot(dx, dy);
  if (d <= NMB_GLIDE_PX || typeof buddy.animate !== "function" || nameMarkBuddyNoTravel()) return;
  if (!eased && ((!riding && performance.now() - nmbFollow.scrollAt < 200) || nameMarkBuddyPanelMoving(nmb.glue?.el))) return;
  //: Standing still, it goes there as it goes anywhere (`nameMarkBuddyGo`):
  //: a hop, a few steps, a float. Already on its way somewhere (an entrance,
  //: a walk), the shift is added to that way, eased, so neither is cut.
  if (!(nmb.anim && nmb.anim.playState === "running")) {
    nameMarkBuddyGo(buddy, dx, dy, nmb.spot || {}, false);
    return;
  }
  nmb.glideAnim = buddy.animate([{ translate: `${dx}px ${dy}px` }, { translate: "0px 0px" }], { duration: 300, easing: "cubic-bezier(0.4, 0, 0.2, 1)", composite: "add" });
}

//: Its panel stayed out of sight after the scroll stopped: the nearest free
//: perch, walked to.
function nameMarkBuddyUnheld() {
  nmb.heldTimer = 0;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || !nmb.glue?.held || nmb.pinned || buddy.classList.contains("nm-buddy-dragging")) return;
  if (nameMarkBuddyMenuOpen()) {
    nmb.heldTimer = setTimeout(nameMarkBuddyUnheld, 600);
    return;
  }
  nameMarkBuddyIndexReset();
  const tab = nameMarkBuddyTab();
  nameMarkBuddyMoveTo(buddy, nameMarkBuddyChoose(tab, nameMarkBuddyObstacles(tab), [nmb.x, nmb.y]));
}

//: **Following, only while something moves.** A frame loop runs for a
//: second and a half after anything that can move a panel (a scroll, a
//: resize, a click, a key, a transition or an animation starting, the tab
//: page changing size), and for as long as its panel is animating, and
//: stops when the page is still, so an idle page runs nothing. A slow look
//: (one box read every 700ms; it was two seconds, in the air all that time,
//: INBOX 521) catches only what changes with nothing announcing it
//: (content arriving above the panel), eased rather than jumped.
const nmbFollow = { frame: 0, until: 0, poll: 0, observer: null, scrollAt: 0, recheck: 0, support: 0 };
function nameMarkBuddyKeepUp(ms = 1500) {
  if (!nmb.glue) return;
  nmbFollow.until = Math.max(nmbFollow.until, performance.now() + ms);
  if (!nmbFollow.frame) nmbFollow.frame = requestAnimationFrame(nameMarkBuddyFollowFrame);
}
function nameMarkBuddyFollowFrame(now) {
  nmbFollow.frame = 0;
  nameMarkBuddyFollow();
  if (nmb.glue && (now < nmbFollow.until || nameMarkBuddyPanelMoving(nmb.glue.el))) nmbFollow.frame = requestAnimationFrame(nameMarkBuddyFollowFrame);
  //: Its panel came to rest somewhere new: a floating button may be over it
  //: now (INBOX 521: content grew above a Library card, and it rode the
  //: card under New document).
  else queueNameMarkBuddyCheck();
}

//: **Followed for as long as its panel is animating** (INBOX 426, round
//: 2). A panel moved by a transform (a card that slides in, a dock that
//: eases open, a widget lifted while dragged) moves with no scroll and no
//: resize to announce it, and a transition longer than the loop's second
//: and a half used to be finished by the two-second look, eased, a beat
//: late. So the loop runs on while anything that can move the panel is
//: still animating: a transition or an animation of a property that places
//: a box, on the panel or any of its ancestors, or a finite one that
//: changes layout anywhere on the page (a sidebar easing its width moves
//: every panel beside it). An endless one on an ancestor is followed while
//: it runs, since the panel really does move every frame; an endless one
//: elsewhere (a spinner, a shimmer) is not, so an idle page stays idle.
const NMB_PLACES = /^(transform|translate|scale|rotate|offset|inset|top|left|right|bottom|margin|padding|width|height|min-|max-|flex|grid|gap|border-width|font-size|all)/;
const NMB_LAYOUT = /^(inset|top|left|right|bottom|margin|padding|width|height|min-|max-|flex|grid|gap|border-width|font-size|all)/;
function nameMarkBuddyAnimProps(anim) {
  if (anim.transitionProperty) return [anim.transitionProperty];
  try {
    const keys = new Set();
    for (const frame of anim.effect?.getKeyframes?.() || []) {
      for (const k of Object.keys(frame)) {
        if (!["offset", "computedOffset", "easing", "composite"].includes(k)) keys.add(k.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`));
      }
    }
    return [...keys];
  } catch (e) {
    return ["all"];
  }
}
function nameMarkBuddyPanelMoving(el) {
  if (!el?.isConnected || typeof document.getAnimations !== "function") return false;
  const buddy = document.getElementById("nm-buddy");
  for (const anim of document.getAnimations()) {
    if (anim.playState !== "running") continue;
    const target = anim.effect?.target;
    if (!target || !target.isConnected || buddy?.contains(target)) continue;
    const props = nameMarkBuddyAnimProps(anim);
    if (target.contains(el)) {
      if (props.some((p) => NMB_PLACES.test(p))) return true;
    } else if (props.some((p) => NMB_LAYOUT.test(p)) && Number.isFinite(anim.effect.getComputedTiming?.().endTime)) {
      return true;
    }
  }
  return false;
}

//: **Its idle motion at a companion's pace** (INBOX 426 x, the owner: "the
//: companion showing makes everything noticeably slower", "heavy and
//: glitchy"). A figure drawn in SVG that breathes, sways and twinkles by CSS
//: animations inside the drawing (Atlas: twenty of them on a 455-node
//: drawing) cannot be moved by the compositor: every frame the page
//: restyles, lays out and repaints the whole drawing. Measured at 1440 with
//: the page's own frame loop running: 165ms a second of main thread, 2.7ms a
//: frame, for a 64 by 92 figure; paused, nothing. So while it is idle its
//: drawing's animations are held and stepped on by hand twenty times a
//: second, which a figure this small reads as the same motion, and held
//: still while the page scrolls (its motion then competes with the one the
//: reader is watching). A walk, a drag, or anything it is doing (a wave, a
//: stretch, a landing) runs at full rate. Animations on the page's own
//: boxes (the figure drawn in HTML, its host) are the compositor's and are
//: left alone.
const NMB_TEMPO_MS = 50;
//: When the hold's hands show (the CSS's `.nmb-hold { opacity: 1 }` rules).
const NMB_HOLD_SHOWN = '[data-pose="hang"], [data-travel="climb"], .nm-buddy-dragging, .nmb-act-stretch, .nmb-act-yawn, .nmb-act-cheer, .nmb-act-wake, .nmb-act-startle';
//: The long, still acts are rest, and paced as rest: a stance, a nap, a
//: book, a seat. Full rate is for the short ones, where it is moving.
const NMB_RESTING_ACTS = new Set(["lie", "read", "beanbag", "chair", "nap", "peek", "peekdown", "meditate", ...Object.keys(NMB_STANCES)]);
const nmbTempo = { timer: 0, anims: [], at: 0, seen: 0, clock: new WeakMap(), slow: new WeakSet(), ticks: 0 };
function nameMarkBuddyTempo() {
  nmbTempo.timer = 0;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || typeof buddy.getAnimations !== "function") {
    nmbTempo.anims = [];
    return;
  }
  const now = performance.now();
  if (now - nmbTempo.seen > 1000) {
    nmbTempo.seen = now;
    //: Atlas's layer roots (atlas.js, `atlasDrawFigure`) animate on the
    //: compositor; stepping them here would put them back on the main
    //: thread, so only what animates inside a drawing is paced.
    //: Nor a transition (round 7: a limb easing into a new pose, 420ms,
    //: which stepped at 10Hz juddered; it is over before it costs much),
    //: nor a move let go (`nameMarkBuddyBlend`, 480ms), for the same reason.
    //: Nor Atlas's blink (atlas.js, `atlasBlink`, 320ms): stepped at
    //: 10Hz its lid jumped in three steps.
    nmbTempo.anims = buddy.getAnimations({ subtree: true }).filter((a) => a.effect?.target instanceof SVGElement && !(a.effect.target instanceof SVGSVGElement) && !(typeof CSSTransition === "function" && a instanceof CSSTransition) && a.id !== "nmb-blend" && a.id !== "atl-blink" && a.playState !== "finished");
    //: **Nor the hands it holds on by, while they are not shown** (Brief 34
    //: decision 7). The hold's reach (`.nmb-hold`, shown only hanging,
    //: carried or in a stretch, a yawn or a cheer) was stepped twenty times
    //: a second on a figure sitting or standing: each step restyled the
    //: drawing, and reading the next beat's play states paid for it (a 15s
    //: profile of the corner Atlas at rest: 494ms in this function). Hidden
    //: hands are paused where they are, and taken up again within a second
    //: of showing.
    if (!buddy.matches(NMB_HOLD_SHOWN)) {
      nmbTempo.anims = nmbTempo.anims.filter((a) => {
        if (!a.effect.target.closest(".nmb-hold")) return true;
        if (a.playState === "running") a.pause();
        return false;
      });
    }
    //: **What animates inside one of Atlas's layers goes at half that**
    //: (libtl-0926, from the Atlas agent's report): a mood's small effects
    //: (sparkles, the thinking dots, a drop), each step of which is a
    //: layout and a repaint of its layer. Measured with one such effect
    //: (`atlasmoodfx.js`, INJECT=1): stepped at 20Hz, 40 paints and 20
    //: layouts a second; left to run free, 119 and 60, since a change
    //: inside an svg is the main thread's whatever layer it sits in. So they
    //: are stepped every other beat, 10Hz, which a sparkle this size reads
    //: as the same twinkle. (Since Atlas round 5 the moods draw their
    //: effects on layer roots, which are not paced at all; this is for
    //: whatever animates inside a layer next.)
    //: Not a limb's gesture in a move (`nameMarkBuddyLimbs`): 20Hz, not 10.
    nmbTempo.slow = new WeakSet(nmbTempo.anims.filter((a) => a.id !== "nmb-limb" && a.effect.target.closest("svg.atl-layer")));
  }
  nmbTempo.ticks += 1;
  const beat = nmbTempo.ticks % 2 === 0;
  //: A walk is paced too (round 5 review): its steps inside a drawing's
  //: svg (Atlas's legs) laid out and repainted the figure every frame, 60
  //: layouts and 120 paints a second, while the walk itself (the host's
  //: translate) is the compositor's. An act or a drag still runs at full
  //: rate: those are short and are the moment it is being looked at.
  //: And in the large view (INBOX 669, the owner: "atlas's arm movements
  //: are jerky and not smooth"): there it is drawn 2.2 times over and is
  //: the one thing on screen, so a head turn stepped at 10Hz jumped 6
  //: degrees a step (atlas669-clicks.js), and the rig followed each arm's
  //: stepped gesture in jerks.
  const busy = (!!nmb.act && !NMB_RESTING_ACTS.has(nmb.act)) || buddy.classList.contains("nm-buddy-dragging") || !!nmb.visit;
  //: Held, not stepped, while a scroll is under way and while a page or a
  //: popup is arriving (`uiSettlingUntil`, set by `switchTab` and
  //: `openSettingsModal`; INBOX 580, the owner: "the atlas companion and app
  //: in general is ever so slightly laggy"): each step inside a drawing is a
  //: layout and a repaint the arriving view's frames are waiting on.
  const still = now - nmbFollow.scrollAt < 300 || now < (window.uiSettlingUntil || 0);
  const step = Math.min(now - (nmbTempo.at || now), 250);
  //: Every read first, then every write: reading an animation's state
  //: after one has been stepped makes the page lay itself out again, once
  //: per animation (measured: 354 layouts a second, interleaved).
  const states = nmbTempo.anims.map((anim) => anim.playState);
  nmbTempo.anims.forEach((anim, i) => {
    //: **A move that has ended stays ended** (INBOX 669, the owner: "when I
    //: click atlas, it often starts tilting to the left then just snaps
    //: back"). The list is read once a second, so it held an act's
    //: animations after the act's class came off and the stylesheet had
    //: cancelled them; `pause()` on a cancelled animation starts it again
    //: from its first frame, and every beat after stepped it on. So each
    //: act's gesture (a wave's arm, a look's head) played a second time,
    //: stepped at 10Hz, after the act had handed back (atlas669-clicks.js:
    //: the wave's probe back at -100 degrees 400ms after the act ended).
    if (states[i] === "idle" || states[i] === "finished") {
      nmbTempo.clock.delete(anim);
      return;
    }
    if (busy) {
      if (states[i] === "paused") anim.play();
      nmbTempo.clock.delete(anim);
    } else if (states[i] !== "paused") {
      anim.pause();
      nmbTempo.clock.set(anim, anim.currentTime || 0);
    } else if (!still && step > 0) {
      //: At the animation's own rate (a stride's, a manner's).
      const t = (nmbTempo.clock.get(anim) ?? 0) + step * (anim.playbackRate || 1);
      nmbTempo.clock.set(anim, t);
      if (beat || !nmbTempo.slow.has(anim)) anim.currentTime = t;
    }
  });
  nmbTempo.at = now;
  if (!document.hidden) nmbTempo.timer = setTimeout(nameMarkBuddyTempo, nmbTempo.anims.length ? NMB_TEMPO_MS : 1000);
}
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && !nmbTempo.timer) nameMarkBuddyTempo();
});
function nameMarkBuddyWatch() {
  const g = nmb.glue;
  if (typeof ResizeObserver === "function") {
    //: One observer. Following a panel it keeps the follow loop up; on a bar,
    //: which holds nothing to follow, its going (hidden, emptied, folded away,
    //: with no scroll, resize or class change to say so) is a look at the
    //: perch now. A resize observer costs nothing while it rests.
    if (!nmbFollow.observer) nmbFollow.observer = new ResizeObserver(() => (nmb.glue ? nameMarkBuddyKeepUp() : queueNameMarkBuddyCheck()));
    nmbFollow.observer.disconnect();
    const bar = !g && ["bar", "hang"].includes(nmb.spot?.edge?.kind) ? nmb.spot.edge.el : null;
    if (bar) nmbFollow.observer.observe(bar);
    if (g) {
      nmbFollow.observer.observe(g.el);
      const page = g.el.closest(".tab-page") || document.getElementById(`tab-${nameMarkBuddyTab()}`);
      if (page) nmbFollow.observer.observe(page);
      //: And what holds it, up to the page: content growing above its panel
      //: grows one of them, and the page itself keeps its size (INBOX 521:
      //: 140px in the air until the slow look, perchall.js).
      for (let node = g.el.parentElement; node && node !== page && node !== document.body; node = node.parentElement) nmbFollow.observer.observe(node);
    }
  }
  clearInterval(nmbFollow.poll);
  nmbFollow.poll = g ? setInterval(() => {
    if (document.hidden || nmbFollow.frame) return;
    const was = `${nmb.x},${nmb.y}`;
    nameMarkBuddyFollow(true);
    //: Carried somewhere new by content moving its panel: under a bar or a
    //: control now, it looks again (INBOX 521: on the phone, a card pushed
    //: under the tab dock took it along, head showing over the tabs).
    if (`${nmb.x},${nmb.y}` !== was) queueNameMarkBuddyCheck();
  }, 700) : 0;
}
//: **An area that only began to scroll after the perch** (B29's neighbour,
//: INBOX 904 B35: "doesn't scroll with what it is perched on if the thing it
//: is perched on is scrollable sometimes on the dashboard"). The area is
//: chosen once, when the companion lands (`nameMarkBuddyGlue`), and the
//: dashboard fills in after first paint: a perch made while it had nothing
//: to scroll chose none, so the companion was carried by script, 71px off its
//: panel mid-scroll and 2037px off once settled (companion1017-dash3.js).
//: The first scroll of the area that is now the panel's nearest one adopts it
//: and rides from where the panel is this frame.
function nameMarkBuddyAdoptScroller(g, target) {
  if (!(target instanceof Element) || nmb.ride?.el === target || nmb.visit) return false;
  if (nameMarkBuddyScroller(g.el) !== target || !nameMarkBuddyScrollsWith(g.el, target)) return false;
  const box = g.el.getBoundingClientRect();
  const x = Math.round(box.left + g.dx);
  const y = Math.round(box.top + g.dy);
  g.scroller = target;
  nameMarkBuddyGlueBand(g, y);
  nameMarkBuddyRide(target, x, y);
  return Boolean(nmb.ride);
}
document.addEventListener("scroll", (event) => {
  //: Any scroll, glued or not: the checks and its idle motion wait for the
  //: page to be still (`nameMarkBuddyCheck`, `nameMarkBuddyTempo`).
  nmbFollow.scrollAt = performance.now();
  const g = nmb.glue;
  if (!g) return;
  const target = event.target;
  if (target !== document && !(target instanceof Node && target.contains(g.el))) return;
  //: Riding this very area: the browser has already moved it; only where
  //: it now is in the window is written down, with no read of any box.
  if (nmb.ride && target === nmb.ride.el) {
    nmb.x = nmb.ride.left + nmb.lx;
    nmb.y = nmb.ride.top + nmb.ly - target.scrollTop;
    return;
  }
  if (nameMarkBuddyAdoptScroller(g, target)) return;
  //: In the scroll's own frame, so it rides with the panel rather than a
  //: frame behind it.
  nmbFollow.scrollAt = performance.now();
  nameMarkBuddyFollow();
  nameMarkBuddyKeepUp(400);
}, { passive: true, capture: true });
//: `transitionrun` rather than `transitionstart`, so a transition with a
//: delay is caught when it is set going; `transitionend`,
//: `transitioncancel` and `animationend` put it at its panel's resting
//: place in that frame.
for (const type of ["pointerdown", "pointerup", "keydown", "transitionrun", "animationstart", "transitionend", "transitioncancel", "animationend"]) {
  document.addEventListener(type, (event) => {
    if (nmb.glue && !event.target?.closest?.("#nm-buddy")) nameMarkBuddyKeepUp();
  }, { passive: true, capture: true });
}

//: Moves it, walking when it has somewhere to go: the move is a
//: `translate` animated on the compositor from where it was, with a jump
//: arc on the character when it changes level, and legs that step. Reduce
//: motion and Avatar animation Off skip straight to the end.
//: **Over a board, in the board** (INBOX 1300 C19, C20, the owner: "if it
//: is perched on them then it should be on the same layer"; "its size
//: should be in proportion to the zoom"). Put over the canvas itself, not
//: on a panel or the chrome, it is drawn under the board's panels (the
//: band's `nmb-canvas`) and sized to the board's zoom, never above its own.
function nameMarkBuddyCanvasAt(spot, x, y) {
  const board = document.getElementById("whiteboard-container");
  if (spot.edge?.el && !board?.contains(spot.edge.el)) return null;
  const r = nameMarkBuddyShown(board);
  const cx = x + NMB_W / 2;
  const cy = y + NMB_H / 2;
  return r && board.checkVisibility?.() !== false && cx > r.left && cx < r.right && cy > r.top && cy < r.bottom ? board : null;
}
const NMB_BOARD_WANDER = 0.1;
function nameMarkBuddyOnBoard() {
  return !!document.getElementById("wb-canvas-view")?.checkVisibility?.();
}
function nameMarkBuddyCanvasScale(k) {
  return Math.min(1, Math.max(0.4, Number(k) || 1));
}
//: From the board's zoom (whiteboard.js, `wbZoomFrameWork`).
function nameMarkBuddyCanvasZoom(k) {
  if (nmb.canvas) nameMarkBuddySetSize(nameMarkBuddyScaleSaved() * nameMarkBuddyCanvasScale(k), false);
}

//: A peek tucks in on arrival, never on the way (INBOX 1300 C01).
function nameMarkBuddyLegsNow(spot, travels) {
  const legs = spot?.legs || "";
  return travels && legs === "peek" ? "" : legs;
}

function nameMarkBuddyMoveTo(buddy, spot, instant = false) {
  //: Visiting its large view (`nameMarkBuddyVisit`): it is where you are
  //: looking at it, and goes nowhere until it is sent home.
  if (nmb.visit) return;
  //: Any other move ends a flight where it is (`nameMarkBuddyThrow`).
  nmb.flight?.stop();
  const x = Math.round(Math.min(Math.max(0, spot.x), innerWidth - NMB_W));
  const y = Math.round(Math.min(Math.max(0, spot.y), innerHeight - NMB_H));
  //: **Never a teleport** (the owner: "let the companions appear smoothly
  //: not just appear suddenly in different locations"): a move that starts
  //: while another is under way starts from where it is drawn now, not from
  //: where the last one was going.
  let was = { x: nmb.x, y: nmb.y };
  const underway = (nmb.anim && nmb.anim.playState === "running") || (nmb.glideAnim && nmb.glideAnim.playState === "running");
  const char = buddy.querySelector(".nm-buddy-char");
  let lift = 0;
  if (underway) {
    const box = buddy.getBoundingClientRect();
    was = { x: box.left, y: box.top };
    lift = Number.parseFloat(String(char ? getComputedStyle(char).translate : "").split(" ")[1]) || 0;
  }
  //: And the lean it was in: a float leans into its way and a shuffle
  //: rocks, on the body's own turn, which went upright in the frame the
  //: move was cut short (jolts.js: the figure 3.7px). Read before and
  //: after the whole change of move, and what differs eased off with the
  //: lift below, whatever moved it.
  const leaning = char && nmb.hopAnim?.playState === "running" ? Number.parseFloat(getComputedStyle(char).rotate) || 0 : null;
  nmb.liftAnim?.cancel();
  nmb.glideAnim?.cancel();
  nmb.glideAnim = null;
  nameMarkBuddyPut(buddy, x, y);
  //: Its size for this perch: smaller where it had to fit, its own
  //: elsewhere, eased either way (`nmb-fitting`).
  const board = nameMarkBuddyCanvasAt(spot, x, y);
  nmb.canvas = !!board;
  document.getElementById("nm-buddy-band")?.classList.toggle("nmb-canvas", nmb.canvas);
  const size = board ? nameMarkBuddyScaleSaved() * nameMarkBuddyCanvasScale(board.__zoom?.k) : spot.fit || nameMarkBuddyScaleSaved();
  if (Math.abs(size - (nmb.scale || 1)) > 0.01) {
    buddy.classList.add("nmb-fitting");
    clearTimeout(nmb.fitTimer);
    nmb.fitTimer = setTimeout(() => buddy.classList.remove("nmb-fitting"), 900);
    nameMarkBuddySetSize(size, false);
  }
  //: A new place: nothing to be bored of yet (a wander sets its own).
  if (spot.kind !== nmb.perch || Math.abs(was.x - x) > 8 || Math.abs(was.y - y) > 8) {
    nmb.perchAt = Date.now();
    //: A new place, a new way to hold its arms (atlas.js's variants for
    //: each mood, `data-atlas-variant`), eased by the limbs' transition.
    if (nmb.act !== "lie" && nameMarkBuddyHasAtlas(buddy)) buddy.dataset.atlasVariant = String(nameMarkBuddyPickVariant(3, Number(buddy.dataset.atlasVariant ?? -1)));
  }
  nmb.perch = spot.kind || "";
  nmb.spot = spot;
  nmb.pinned = spot.kind === "pinned";
  if (!nmb.pinned) nmb.tucked = false;
  clearTimeout(nmb.heldTimer);
  nameMarkBuddyGlue(spot, x, y);
  nmb.edgeType = spot.edge?.type || "";
  //: Where its panel's top edge crosses it, for peeking from behind it.
  nmb.edgeLine = spot.pose === "sit" ? NMB_SEAT : NMB_FEET - 1;
  buddy.style.setProperty("--nmb-edge", `${nmb.edgeLine}px`);
  buddy.dataset.perch = nmb.perch;
  nameMarkBuddyGait(buddy);
  const poseChanged = buddy.dataset.pose !== spot.pose;
  buddy.dataset.pose = spot.pose;
  const dx = was.x - x;
  const dy = was.y - y;
  const travels = !instant && typeof buddy.animate === "function" && Number.isFinite(dx) && Number.isFinite(dy) && (Math.abs(dx) >= 1 || Math.abs(dy) >= 1);
  clearTimeout(nmb.legsTimer);
  buddy.dataset.legs = nameMarkBuddyLegsNow(spot, travels);
  buddy.dataset.side = spot.side || "";
  nmb.pose = spot.pose;
  nmb.legs = spot.legs || "";
  nameMarkBuddyKeepFrame(buddy);
  //: The band was sized by the glue above, before this spot's pose and
  //: pivot were set, so for the pose it had before (arriving hanging, it
  //: was measured with the hang's pivot and a standing figure lost its
  //: rings to it). Once more, now they are this spot's.
  if (nmb.ride && poseChanged) nameMarkBuddyRideBox(x, y, true);
  if (!Number.isFinite(dx) || !Number.isFinite(dy) || (Math.abs(dx) < 1 && Math.abs(dy) < 1)) return;
  nmb.anim?.cancel();
  nmb.hopAnim?.cancel();
  //: A move cut short leaves nothing of itself behind (its own end no
  //: longer takes these off: see `nameMarkBuddyPoof`), eased from where
  //: its stride had it (jolts.js: the body 5.1px in a frame).
  const stop = () => buddy.classList.remove("nmb-poofing", "nmb-walking");
  if (instant || typeof buddy.animate !== "function") {
    stop();
    return;
  }
  nameMarkBuddyBlend(buddy, stop);
  nameMarkBuddyGo(buddy, dx, dy, spot, poseChanged, was, underway);
  if (buddy.dataset.legs !== (spot.legs || "")) {
    const end = Number(nmb.anim?.effect?.getComputedTiming?.().endTime);
    nmb.legsTimer = setTimeout(() => {
      if (nmb.spot === spot) buddy.dataset.legs = spot.legs || "";
    }, Number.isFinite(end) && end > 0 ? end : 900);
  }
  //: Cut off in mid-air (a hop's arc, a float's lift), the figure comes
  //: down from where it was drawn, added to the new way, not snapped to it.
  const turn = leaning === null ? 0 : leaning - (Number.parseFloat(getComputedStyle(char).rotate) || 0);
  if ((lift || Math.abs(turn) > 0.2) && char && typeof char.animate === "function") nmb.liftAnim = char.animate([{ translate: `0px ${lift}px`, rotate: `${turn}deg` }, { translate: "0px 0px", rotate: "0deg" }], { duration: 240, easing: "ease-out", composite: "add" });
}

//: **How it gets there: by the way its body moves, never a slide** (the
//: owner, 2026-09-27: "instead the slight position displacements, the
//: companion instead walks or jumps, fly, to the new position ... if it is
//: close, if it is further away then it will teleport ... It is a
//: companion, not a fake soulless construct"). It is already at its new
//: place (`nameMarkBuddyPut`); this plays the way from `dx`, `dy` back to
//: it. Distances are in its own size (`NMB_W` times its scale), so a large
//: companion takes a longer step before it needs a walk:
//: Reduce motion is a crossfade; thrown or let go, the flight or the fall;
//: from out of sight or very far, a poof; otherwise the way the geometry
//: chooses (`nameMarkBuddyRoute`). Every one eases from rest to rest, or
//: from the speed it already had, so its speed never jumps.
const NMB_HOP_SIZES = 0.7;
const NMB_FAR_SIZES = 3;
//: A climb up an edge only within this many of itself; further is a path.
const NMB_FAR_POOF_SIZES = 5;
const NMB_FLYERS = ["bat", "bird", "owl", "ghost", "bee", "butterfly", "fairy", "angel", "dragon", "phoenix"];
//: **A way of moving by look** (the owner: "masculine and feminine ways to
//: stand and move the body"): Atlas's look (its drawing says which) or,
//: for a face drawn from a name, Appearance's Face look. Heavier is slower,
//: with a deeper bob and a wider step; lighter is quicker and softer, with
//: a sway. `data-gait` for the CSS; `NMB_GAIT_PACE` for the travel's time.
const NMB_GAIT_PACE = { masculine: 1.12, feminine: 0.94 };
function nameMarkBuddyGait(buddy) {
  const atlas = buddy.querySelector("svg.atl-layer")?.dataset.atlasLook || "";
  const face = typeof appearancePref === "function" ? appearancePref("face-look", "mixed") : "mixed";
  const gait = atlas || (face === "masculine" || face === "feminine" ? face : "");
  if ((buddy.dataset.gait || "") !== gait) {
    if (gait) buddy.dataset.gait = gait;
    else delete buddy.dataset.gait;
  }
  return gait;
}
function nameMarkBuddyFlies(buddy) {
  const seed = buddy.dataset.seed || "";
  return isAtlasSeed(seed) || NMB_FLYERS.includes(nmb.reading?.animal) || nmb.pose === "float";
}
//: **A crossfade, never a blink out and back** (INBOX 443, the owner: "I
//: also want companion transitions to be better even with reduced motion
//: on"). Without travel (Reduce motion, Companion movement's Fades) or
//: carried asleep, it used to fade out where it was, be gone for a moment,
//: then fade in where it went: at the middle there was no companion at all.
//: Now a still copy stays where it was and fades out while it fades in where
//: it is, over the same time, so at every moment the two make one. Only
//: opacity moves, on the compositor; the copy is the element's own drawing
//: at that moment, never sent a pointer or read by a screen reader, and is
//: gone when the fade ends or the next move starts. It keeps the id for one
//: reason: every rule that draws the companion is written on `#nm-buddy`,
//: and it is put after the companion, so `getElementById` and every
//: `querySelector` find the companion first.
function nameMarkBuddyCrossfade(buddy, dx, dy, ms) {
  nmb.ghost?.remove();
  nmb.ghost = null;
  const ease = { duration: ms, easing: "ease-in-out" };
  if (buddy.parentNode && Number.isFinite(nmb.lx) && Number.isFinite(nmb.ly)) {
    const ghost = buddy.cloneNode(true);
    ghost.setAttribute("aria-hidden", "true");
    ghost.inert = true;
    ghost.classList.add("nmb-ghost");
    ghost.style.transform = `translate(${nmb.lx + dx}px, ${nmb.ly + dy}px)`;
    buddy.after(ghost);
    nmb.ghost = ghost;
    const gone = () => {
      ghost.remove();
      if (nmb.ghost === ghost) nmb.ghost = null;
    };
    ghost.animate([{ opacity: 1 }, { opacity: 0 }], { ...ease, fill: "forwards" }).finished.then(gone, gone);
  }
  nmb.anim = buddy.animate([{ opacity: 0 }, { opacity: 1 }], ease);
}
//: **The way there, by the shape of the move** (INBOX 455 (2), the owner:
//: "more and better transitions between positions"). Pure, so a test runs
//: it: `dx`, `dy` from where it is going back to where it was, `size` its
//: width, `roll` a draw in [0, 1).
//:   a flyer          a hop or a float for a step, a leap or a float across
//:                    a change of level, a float, and the far ways when far
//:   a small step     a hop, a shuffle or a scoot, one in three each
//:   mostly up or down, within `NMB_FAR_POOF_SIZES`  climb: along its
//:                    ledge, then up the edge hand over hand (down it first,
//:                    then along, going down)
//:   a change of level within `NMB_FAR_SIZES`  leap: a crouch, an arc over
//:                    the gap with its arms out, a landing
//:   further          "far": `companionPathPlan` (companion-menu.js) draws a run,
//:                    an arc or a drop, paced by its length, never a vanish
//:   anything else    walk, along the ledge it is on
function nameMarkBuddyRoute(dx, dy, size, flies, poseChanged, roll) {
  const d = Math.hypot(dx, dy);
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  //: A flyer (Atlas among them) only ever floated, or glided when far (the
  //: owner, 2026-10-10: "the companion doesn't really have any variation in
  //: how it moves around at various distances"): now a little bob of a hop
  //: or a float for a step, a swooping leap across a change of level one
  //: time in two, and far, the far ways (a glide, a walk on the level, a poof).
  if (flies) {
    if (d > size * NMB_FAR_SIZES) return "far";
    if (d < size * NMB_HOP_SIZES && !poseChanged) return roll < 0.5 ? "hop" : "float";
    return ay > 36 && roll < 0.5 ? "leap" : "float";
  }
  if (d < size * NMB_HOP_SIZES && !poseChanged) return ["hop", "shuffle", "scoot"][Math.floor(roll * 3)];
  if (ay > 48 && ay > ax * 0.8 && d < size * NMB_FAR_POOF_SIZES) return "climb";
  if (ay > 36 && d < size * NMB_FAR_SIZES) return "leap";
  return d > size * NMB_FAR_SIZES ? "far" : "walk";
}

//: **Limbs in motion** (INBOX 469, the owner: "have the arms and legs be
//: used a bit for various position, action etc changes and transitions").
//: One gesture per way of going, paced to the move: a leap crouches with
//: its arms back, then holds them out for balance and reaches its legs for
//: the landing; a glide spreads them like wings; a float is a stroke of the
//: arms with the hem trailing; a new act starts with a small lift of the
//: arms. Frames are `[offset, degrees, scaleY]` for the left side; the right
//: is the mirror, and the hem (Atlas's lower layer) leans against the way
//: it goes. On `rotate` and `scale`, the individual properties, with no end
//: frames: each adds to the pose's own `transform` and comes back to it, and
//: a cancelled one leaves the pose as it was. The walk's arm swing and the
//: climb's reach are the CSS's (`.nmb-walking`, `data-travel`), looped.
const NMB_LIMB_MOVES = {
  leap: { arm: [[0.14, -16], [0.5, 52], [0.84, 16]], leg: [[0.14, 0, 0.84], [0.5, 16, 0.76], [0.86, -4, 1.05]], lower: [[0.2, -4], [0.55, 10], [0.86, -3]] },
  glide: { arm: [[0.22, 66], [0.76, 60]], leg: [[0.25, -5, 0.86], [0.75, -5, 0.86]], lower: [[0.25, 12], [0.75, 9]] },
  float: { arm: [[0.25, -12], [0.6, 30], [0.86, 8]], lower: [[0.3, 10], [0.72, 6], [0.9, -3]] },
  cue: { arm: [[0.4, 20]] },
};
function nameMarkBuddyLimbs(buddy, kind, ms = 0, delay = 0, way = 1) {
  for (const anim of nmb.limbAnims || []) anim.cancel();
  nmb.limbAnims = [];
  const move = NMB_LIMB_MOVES[kind];
  if (!move || !ms || typeof buddy.animate !== "function") return;
  const timing = { duration: ms, delay, easing: "ease-in-out", id: "nmb-limb" };
  const part = (sel, list, side) => {
    for (const el of list ? buddy.querySelectorAll(sel) : []) {
      const m = side(el);
      nmb.limbAnims.push(el.animate(list.map(([offset, deg, sy]) => (sy ? { offset, rotate: `${deg * m}deg`, scale: `1 ${sy}` } : { offset, rotate: `${deg * m}deg` })), timing));
    }
  };
  part(".nmb-arm", move.arm, (el) => (el.classList.contains("nmb-arm-r") ? -1 : 1));
  //: Atlas's legs are two `<svg>` roots (`nmb-leg atl-layer`), on which
  //: `rotate` and `scale` are never composited: its boxes (`.atl-lw-leg-*`,
  //: atlas.js) take the gesture and the roots are left to the pose.
  part(".nmb-leg:not(.atl-layer), .atl-lw-leg-l, .atl-lw-leg-r", move.leg, (el) => (el.matches(".nmb-leg-r, .atl-lw-leg-r") ? -1 : 1));
  part(".atl-lw-lower", move.lower, () => way);
  //: Atlas's arms follow a gesture through its rig (atlas.js, `atlasRig`),
  //: which reads it off each arm's probe: wake the rig for it.
  atlasRigWake(buddy);
  //: Atlas's arms are inside its body layer's drawing, where a moving part
  //: lays out and repaints the layer each frame (companionroutes.js: 80
  //: layouts over a float), so they are paced as the walk's steps are
  //: (`nameMarkBuddyTempo`), from now rather than its next look.
  if (buddy.querySelector("svg.atl-layer .nmb-arm")) {
    nmbTempo.seen = 0;
    clearTimeout(nmbTempo.timer);
    nmbTempo.timer = setTimeout(nameMarkBuddyTempo, 0);
  }
}

//: The way it is about to go, -1 or 1 (`--nmb-lean`): the walk's bob and
//: glide lean into it (`.nm-buddy-char`) and so does the skirt's trail (its
//: own root). The property does not inherit (the CSS says why: written on
//: the buddy it restyled all 528 descendants), so the buddy carries it for
//: the first and the skirt's root is written to directly.
function nameMarkBuddyWay(buddy, way) {
  buddy.style.setProperty("--nmb-lean", way);
  for (const el of buddy.querySelectorAll(".atl-layer-lower")) el.style.setProperty("--nmb-lean", way);
}

//: Which way of going its limbs are in (the CSS's `data-travel`), and for
//: a move in two parts (a climb: along, then up), the part after `at` ms.
function nameMarkBuddyTravel(buddy, kind, at = 0, then = "") {
  clearTimeout(nmb.travelTimer);
  const set = (k) => {
    if (k) buddy.dataset.travel = k;
    else delete buddy.dataset.travel;
  };
  set(kind);
  if (at) nmb.travelTimer = setTimeout(() => set(then), at);
}

function nameMarkBuddyGo(buddy, dx, dy, spot = {}, poseChanged = false, was = { x: nmb.x + dx, y: nmb.y + dy }, underway = false) {
  nmb.ghost?.remove();
  nmb.hopAnim?.cancel();
  nameMarkBuddyLimbs(buddy, "");
  nameMarkBuddyTravel(buddy, "");
  //: It leans the way it is about to go, and straightens as it arrives.
  if (Math.abs(dx) > 6 && !nameMarkBuddyNoTravel()) nameMarkBuddyTilt(dx > 0 ? -0.8 : 0.8, Math.min(900, 300 + Math.abs(dx) * 2));
  nmb.movedAt = Date.now();
  const distance = Math.hypot(dx, dy);
  const size = NMB_W * Math.max(0.7, nmb.scale || 1);
  //: **Carried asleep** (the owner, 2026-09-27: "the companion was sleeping
  //: but then when I clicked a different tab, for a split second I saw it
  //: shoot back up look alive suddenly and look surprised"). Asleep, it is
  //: not woken to walk: it fades out where it was and in where it is going,
  //: still asleep, lying down again if the act allows the new pose, dozing
  //: where it is if not.
  if (nameMarkBuddyAsleep(buddy)) {
    const lying = NAME_MARK_BUDDY_ACTS[nmb.act];
    if (nmb.act && lying && !lying.poses.includes(nmb.pose)) nameMarkBuddyAct("");
    nameMarkBuddyCrossfade(buddy, dx, dy, 900);
    return;
  }
  nameMarkBuddyAct("");
  const char = buddy.querySelector(".nm-buddy-char");
  //: **Always the way there, never a vanish** (INBOX 426 n). Reduce motion
  //: alone gets a short crossfade in place of the travel.
  if (nameMarkBuddyNoTravel()) {
    nameMarkBuddyCrossfade(buddy, dx, dy, 420);
    return;
  }
  //: **Interruptible, at speed** (apple-design: a gesture that takes over a
  //: moving thing keeps its momentum). A new place chosen while it is on its
  //: way starts from where it is drawn (`nameMarkBuddyMoveTo`) with no
  //: crouch and no wait, on a curve whose first slope carries on at about
  //: the speed it had (`nmb.moveSpeed`, the last move's mean, half again
  //: mid-way), then eases in. Measured (companionroutes.js, a leap taken
  //: over at 300ms): a 35px frame at the hand-over before, 15 after.
  const setOff = underway ? 0 : NMB_SET_OFF_MS;
  const carried = underway ? (nmb.moveSpeed || 0) * 1.4 : 0;
  nmb.moveSpeed = 0;
  const leave = (easing, ms) => {
    nmb.moveSpeed = distance / ms;
    if (!underway) return easing;
    const slope = Math.min(4.5, Math.max(0.6, (carried * ms) / Math.max(1, distance)));
    return `cubic-bezier(0.2, ${(0.2 * slope).toFixed(3)}, 0.3, 1)`;
  };
  const way = dx > 0 ? -1 : 1;
  const seenFrom = !nmb.outOfSight && was.x > -NMB_W && was.y > -NMB_H && was.x < innerWidth && was.y < innerHeight;
  const flies = nameMarkBuddyFlies(buddy);
  let route = spot.falls ? "fall" : nameMarkBuddyRoute(dx, dy, size, flies, poseChanged, Math.random());
  //: **A far move is a path, never a vanish** (INBOX 1305, the owner:
  //: "companion movement for both small and large distances needs a lot of
  //: improvement"): `companionPathPlan` (companion-menu.js, lazy) draws a run,
  //: an arc or a drop paced by its length with no frame over 40px; until it
  //: is here a far move walks. Only a start out of sight is a poof.
  const plan = route === "far" && typeof companionPathPlan === "function" ? companionPathPlan(dx, dy, size, flies) : null;
  if (route === "far") route = !plan ? "walk" : flies ? "glide" : plan.kind === "arc" ? "leap" : "walk";
  if (route !== "fall" && !seenFrom) {
    buddy.dataset.route = "poof";
    nameMarkBuddyPoof(buddy, dx, dy, seenFrom);
    return;
  }
  buddy.dataset.route = route;
  nameMarkBuddyWay(buddy, dx > 0 ? "-1" : "1");
  if (route === "glide") {
    //: A flyer's far way (the plan's run or arc), leaning into the way it
    //: goes, arms out.
    const duration = plan.ms;
    nmb.anim = buddy.animate(plan.frames, { duration, delay: setOff, fill: "backwards", easing: "linear" });
    const lean = way * 12;
    nmb.hopAnim = char?.animate([
      { rotate: "0deg", translate: "0px 0px" }, { rotate: `${lean}deg`, translate: "0px -3px", offset: 0.3 },
      { rotate: `${lean}deg`, translate: "0px -3px", offset: 0.7 }, { rotate: `${-lean * 0.3}deg`, translate: "0px 0px", offset: 0.9 }, { rotate: "0deg" },
    ], { duration, delay: setOff, fill: "backwards", easing: "ease-in-out" }) || null;
    nameMarkBuddySquash(char, duration + setOff, underway);
    nameMarkBuddyLimbs(buddy, "glide", duration, setOff, way);
    return;
  }
  //: Let go over open space, it falls: gravity's curve, straight down,
  //: and a squash where it lands.
  if (route === "fall") {
    const duration = Math.round(Math.min(700, 180 + Math.sqrt(Math.abs(dy)) * 30));
    nmb.anim = buddy.animate([{ translate: `${dx}px ${dy}px` }, { translate: "0px 0px" }], { duration, easing: "cubic-bezier(0.55, 0, 1, 0.45)" });
    nmb.anim.onfinish = () => nameMarkBuddyAct("land");
    nameMarkBuddyLimbs(buddy, "glide", duration);
    return;
  }
  //: A float: no steps, a lift and a drift on a shallow arc, leaning a
  //: little into the way it goes, and a settle as it arrives.
  if (route === "float") {
    //: Its look sets its float too: heavier, slower and lower; lighter,
    //: quicker, higher and leaning more into the way it goes.
    const gait = buddy.dataset.gait || "";
    //: A float has its stride too: a slower one drifts higher, a quicker
    //: one skims.
    const beat = nameMarkBuddyStride();
    const duration = Math.round((Math.min(1300, 560 + distance * 0.9) * (NMB_GAIT_PACE[gait] || 1)) / beat);
    nmb.anim = buddy.animate([{ translate: `${dx}px ${dy}px` }, { translate: "0px 0px" }], { duration, easing: leave("cubic-bezier(0.45, 0, 0.25, 1)", duration) });
    const lift = (Math.min(28, 8 + distance * 0.06) * (gait === "masculine" ? 0.8 : gait === "feminine" ? 1.15 : 1)) / beat;
    const lean = Math.max(-8, Math.min(8, -dx * 0.04)) * (gait === "feminine" ? 1.4 : 1);
    nmb.hopAnim = char?.animate([
      { translate: "0px 0px", rotate: "0deg", easing: "ease-in-out" },
      { translate: `0px ${-lift}px`, rotate: `${lean}deg`, offset: 0.45, easing: "ease-in-out" },
      { translate: "0px 2px", rotate: `${-lean * 0.3}deg`, offset: 0.88, easing: "ease-in-out" },
      { translate: "0px 0px", rotate: "0deg" },
    ], { duration: duration + 120 }) || null;
    nameMarkBuddyLimbs(buddy, "float", duration + 120, 0, way);
    return;
  }
  //: **Not always a hop** (the owner at release: "vary the small movement
  //: transition choices"): a small step is a hop, a shuffle (a rock from
  //: foot to foot) or a scoot (a lean into the way it goes and back).
  if (route === "shuffle" || route === "scoot") {
    const slide = Math.round((300 + distance * 2.5) * 1.25);
    nmb.anim = buddy.animate([{ translate: `${dx}px ${dy}px` }, { translate: "0px 0px" }], { duration: slide, delay: setOff, fill: "backwards", easing: leave("ease-in-out", slide) });
    nmb.hopAnim = char?.animate(route === "shuffle" ? [
      { rotate: "0deg", translate: "0px 0px" }, { rotate: "-5deg", translate: "0px -2px", offset: 0.25 },
      { rotate: "5deg", translate: "0px -2px", offset: 0.6 }, { rotate: "0deg", translate: "0px 0px" },
    ] : [
      { rotate: "0deg" }, { rotate: `${-way * 7}deg`, offset: 0.35 }, { rotate: `${way * 2}deg`, offset: 0.8 }, { rotate: "0deg" },
    ], { duration: slide, delay: setOff, fill: "backwards", easing: "ease-in-out" }) || null;
    nameMarkBuddyLimbs(buddy, "cue", slide, setOff);
    return;
  }
  //: A hop, or a leap between ledges: gathered, over an arc (higher the
  //: more it climbs, its top late when going up so it clears the ledge),
  //: arms out for balance, legs reaching for the landing, and a squash.
  if (route === "hop" || route === "leap") {
    const leap = route === "leap";
    const duration = plan ? plan.ms : Math.round(leap ? Math.min(1000, 420 + distance * 1.4) : 300 + distance * 2.5);
    nmb.anim = buddy.animate(plan ? plan.frames : [{ translate: `${dx}px ${dy}px` }, { translate: "0px 0px" }], { duration, delay: setOff, fill: "backwards", easing: plan ? "linear" : leave("cubic-bezier(0.45, 0, 0.2, 1)", duration) });
    //: The plan's own path is the arc; the body adds only its small bob.
    const arc = plan ? 4 : leap ? Math.min(90, 18 + Math.abs(dy) * 0.35 + Math.abs(dx) * 0.05) : Math.min(22, 8 + distance * 0.35);
    const top = leap && dy > 0 ? 0.55 : 0.45;
    nmb.hopAnim = char?.animate([
      { translate: "0px 0px", easing: "cubic-bezier(0.2, 0.8, 0.4, 1)" },
      { translate: `0px ${-arc}px`, offset: top, easing: "cubic-bezier(0.6, 0, 0.8, 0.6)" },
      { translate: "0px 0px" },
    ], { duration, delay: setOff, fill: "backwards" }) || null;
    nameMarkBuddySquash(char, duration + setOff, underway);
    nameMarkBuddyLimbs(buddy, "leap", duration + setOff, 0, way);
    return;
  }
  //: A walking pace, not a dash: 160px was 520ms (measured 17px a frame
  //: at its fastest), now 800ms, about 8. A climb walks along its ledge and
  //: goes up the edge at the end of it hand over hand, a little slower than
  //: it walks (or down the edge first, then along): one path with a corner,
  //: its speed easing to nothing at the corner as it takes hold.
  const pace = NMB_GAIT_PACE[buddy.dataset.gait] || 1;
  const climb = route === "climb";
  const along = Math.abs(dx) * 2.2;
  const up = Math.abs(dy) * 3.2;
  //: **And a stride of its own** (Brief 88 d): a stroll, its pace or a
  //: hurry, any of the three but the last, the travel and the legs' beat
  //: changed together so its feet keep up with the ground.
  const beat = plan ? plan.beat : nameMarkBuddyStride();
  const duration = plan ? plan.ms : Math.round(((climb ? Math.min(2200, 380 + along + up) : Math.min(1600, 450 + distance * 2.2)) * pace) / beat);
  buddy.dataset.turn = dx > 0 ? "l" : "r";
  nameMarkBuddyBlend(buddy, () => buddy.classList.add("nmb-walking"), NMB_BLEND_IN_MS);
  //: The walk's own animations are paced from its first step, not when
  //: the pacer next looks (a second later, longer than most walks).
  nmbTempo.seen = 0;
  clearTimeout(nmbTempo.timer);
  nmbTempo.timer = setTimeout(nameMarkBuddyTempo, 0);
  for (const anim of buddy.getAnimations({ subtree: true })) if (typeof CSSAnimation === "function" && anim instanceof CSSAnimation && NMB_STRIDE_LOOPS.test(anim.animationName)) anim.playbackRate = beat;
  //: **A body that sets off and arrives** (round 7, INBOX 430): it gathers
  //: itself first (a crouch, `NMB_SET_OFF_MS`, the travel held back that
  //: long), springs up out of it, and on arriving squashes into the landing
  //: and rebounds once: anticipation and follow-through, on the
  //: character's own `scale` about its feet, the compositor's.
  let frames = plan ? plan.frames : [{ translate: `${dx}px ${dy}px` }, { translate: "0px 0px" }];
  if (climb) {
    const goingUp = dy > 0;
    const corner = Math.abs(dx) < 8 ? (goingUp ? 0 : 1) : (goingUp ? along : up) / (along + up);
    const bend = "cubic-bezier(0.45, 0, 0.55, 1)";
    frames = [
      { translate: `${dx}px ${dy}px`, easing: bend },
      { translate: goingUp ? `0px ${dy}px` : `${dx}px 0px`, offset: corner, easing: bend },
      { translate: "0px 0px" },
    ];
    const at = Math.round(setOff + duration * corner);
    nmb.moveSpeed = (Math.abs(dx) + Math.abs(dy)) / duration;
    if (goingUp) nameMarkBuddyTravel(buddy, "", at, "climb");
    else nameMarkBuddyTravel(buddy, "climb", at, "");
  }
  nmb.anim = buddy.animate(frames, { duration, delay: setOff, fill: "backwards", easing: climb || plan ? "linear" : leave("cubic-bezier(0.45, 0, 0.2, 1)", duration) });
  nameMarkBuddySquash(char, duration + setOff, underway);
  //: This walk's own end only (see `nameMarkBuddyPoof`): a walk cut short
  //: by the next reports its `cancel` after the next has begun.
  const walk = nmb.anim;
  const done = () => {
    if (nmb.anim !== walk) return;
    nameMarkBuddyBlend(buddy, () => buddy.classList.remove("nmb-walking"));
    delete buddy.dataset.turn;
    nameMarkBuddyTravel(buddy, "");
  };
  walk.onfinish = done;
  walk.oncancel = done;
}

const NMB_SET_OFF_MS = 90;
const NMB_STRIDES = [0.88, 1, 1.14];
function nameMarkBuddyStride() {
  nmb.stride = nameMarkBuddyPickVariant(NMB_STRIDES.length, nmb.stride ?? -1);
  return NMB_STRIDES[nmb.stride];
}
//: The walk's own loops (the CSS's, under `.nmb-walking`).
const NMB_STRIDE_LOOPS = /^(nmb-bob|nmb-step|nmb-arm-swing|atl-glide|atl-lower-)/;
const NMB_SETTLE_MS = 260;

//: The crouch before a move and the landing after it, over `travel` ms of
//: setting off and going plus `NMB_SETTLE_MS` of settling. The easing is
//: each keyframe's own: given to the whole animation it eased the whole
//: second, and the crouch came 140ms late, after it had set off
//: (companionmotion.js). `underway`, taking over a move: no crouch, only
//: the landing.
function nameMarkBuddySquash(char, travel, underway = false) {
  //: A move cut short in its landing squash goes on from that squash, not
  //: from upright (jolts.js: the body 3.8px in the frame the next began).
  const was = nmb.squashAnim && char ? getComputedStyle(char).scale : "none";
  nmb.squashAnim?.cancel();
  nmb.squashAnim = null;
  if (!char || typeof char.animate !== "function") return;
  const total = travel + NMB_SETTLE_MS;
  const at = (ms) => Math.min(1, Math.max(0, ms / total));
  nmb.squashAnim = char.animate([
    { scale: was === "none" ? "1 1" : was },
    ...(underway ? [] : [{ scale: "1.06 0.92", offset: at(NMB_SET_OFF_MS) }, { scale: "0.97 1.04", offset: at(NMB_SET_OFF_MS + 140) }]),
    { scale: "1 1", offset: at(Math.max(underway ? 0 : NMB_SET_OFF_MS + 200, travel - 110)) },
    { scale: "1.07 0.91", offset: at(travel + 50) },
    { scale: "0.98 1.02", offset: at(travel + 160) },
    { scale: "1 1" },
  ].map((frame) => ({ ...frame, easing: "ease-in-out" })), { duration: total });
}
//: **Thrown** (INBOX 882, the owner: "I try throwing the companion across
//: the screen and it just goes back to the same side, the companion physics
//: just isnt there"). It used to slide on for a quarter of a second and then
//: take the tab's best perch near there, so a hard throw and a soft one
//: came down in much the same place, and a let-go a frame late was a drop.
//: Now it flies: let go at the pointer's speed over its last 80ms
//: (`nameMarkBuddyReleaseVelocity`), it carries on under gravity and air
//: drag, bounces off the top bar, the floor and the window's sides at
//: `bounce` of its speed (off a side never faster than `wall`: at 0.4 a hard
//: throw came back off the far side 600px, the very "goes back"), leans into the way it flies, comes down on the first ledge or the
//: floor under its path with a squash, slides to a stop, and then takes the
//: nearest place to where it stopped (`nameMarkBuddyThrowLand`). px and ms.
const NMB_TOSS_SPEED = 0.6;
//: `max` is the fastest it is ever drawn: 2.3 px/ms is 38px a 60 Hz frame, under the 40 that reads as a jump (INBOX 1305; it was 4.5, 75px).
const NMB_THROW = { max: 2.3, g: 0.0032, air: 0.0011, ground: 0.006, bounce: 0.4, wall: 0.12, stick: 0.35, tilt: 14, ms: 1200 };
const NMB_PET_MS = 1100;

//: **Never the same flight twice** (Brief 88 (b), the owner: "it just
//: bounces off a panel and back to the top, I want it to do that, but vary
//: how much it does that"). Each throw draws its own bounce, floor grip and
//: air from a range by `roll` (three draws in [0, 1)), and one thrown hard
//: (past 1.9 px/ms) tumbles head over heels instead of leaning, by its speed.
function nameMarkBuddyThrowFeel(roll, speed, k = NMB_THROW) {
  return {
    ...k,
    bounce: +(0.28 + roll[0] * 0.24).toFixed(3),
    ground: +(0.0045 + roll[1] * 0.0035).toFixed(5),
    air: +(0.0009 + roll[2] * 0.0004).toFixed(5),
    spin: speed > 1.9 ? 0.3 : 0,
  };
}

//: The speed it is let go at, px per ms, from `samples` ([x, y, ms], oldest
//: first): over the pointer's last 80ms only, so a slow start to a quick
//: flick does not slow the flick, and clamped to `k.max`. Null when the
//: pointer had stopped 100ms before `now`, or there is nothing to measure.
function nameMarkBuddyReleaseVelocity(samples, now, k = NMB_THROW) {
  const last = samples[samples.length - 1];
  if (!last || now - last[2] > 100) return null;
  let i = samples.length - 1;
  while (i > 0 && last[2] - samples[i - 1][2] <= 80) i -= 1;
  //: One move inside the window (a slow machine's input): the one before it.
  if (i === samples.length - 1 && i > 0 && last[2] - samples[i - 1][2] <= 160) i -= 1;
  const first = samples[i];
  const dt = last[2] - first[2];
  if (dt < 8) return null;
  const vx = (last[0] - first[0]) / dt;
  const vy = (last[1] - first[1]) / dt;
  const cut = Math.min(1, k.max / Math.max(1e-9, Math.hypot(vx, vy)));
  return [vx * cut, vy * cut];
}

//: One step of a flight, pure: `s` its corner (`x`, `y`), speed (`vx`,
//: `vy`), lean (`rot`, degrees), time flown (`t`), what it slides on (`on`:
//: a ledge, "floor" or null) and `rest`; `dt` ms; `world` the box its corner
//: stays in (`left`, `right`, `top`, `floor`) and the `ledges` it can come
//: down on ({left, right, y}, for its corner). `hit` is the speed of a
//: landing this step, for the squash.
function nameMarkBuddyFlightStep(s, dt, world, k = NMB_THROW) {
  const n = { ...s, t: s.t + dt, hit: 0 };
  if (n.rest) return n;
  const ease = Math.min(1, dt / 90);
  if (n.on) {
    n.vx *= Math.exp(-k.ground * dt);
    //: Down from a tumble: it rolls the short way up, never unwinds.
    n.rot = (((n.rot + 180) % 360) + 360) % 360 - 180;
    n.rot -= n.rot * ease;
  } else {
    n.vy += k.g * dt;
    const drag = Math.exp(-k.air * dt);
    n.vx *= drag;
    n.vy *= drag;
    const fast = Math.min(1, k.max / Math.hypot(n.vx, n.vy));
    n.vx *= fast;
    n.vy *= fast;
    if (k.spin) n.rot += n.vx * k.spin * dt;
    else n.rot += (Math.max(-40, Math.min(40, n.vx * k.tilt)) - n.rot) * ease;
  }
  const py = n.y;
  n.x += n.vx * dt;
  n.y += n.on ? 0 : n.vy * dt;
  if (n.x < world.left || n.x > world.right) {
    //: Off a side: back at `bounce` of its speed, but never faster than
    //: `wall` px per ms (a hard throw thuds against it and drops).
    const left = n.x < world.left;
    const back = Math.min(Math.abs(n.vx) * k.bounce, k.wall);
    n.x = left ? world.left : world.right;
    n.vx = left ? back : -back;
  }
  if (n.y < world.top) {
    n.y = world.top;
    n.vy = -n.vy * k.bounce;
  }
  //: Off the end of the ledge it slid along: it falls again.
  if (n.on && n.on !== "floor" && (n.x < n.on.left || n.x > n.on.right)) n.on = null;
  if (!n.on && n.vy > 0) {
    let land = null;
    for (const l of world.ledges || []) {
      if (py < l.y && n.y >= l.y && n.x >= l.left && n.x <= l.right && (!land || l.y < land.y)) land = l;
    }
    if (land || n.y >= world.floor) {
      n.y = land ? land.y : world.floor;
      n.hit = n.vy;
      if (n.vy > k.stick) {
        n.vy = -n.vy * k.bounce;
        n.vx *= 0.85;
      } else {
        n.vy = 0;
        n.on = land || "floor";
      }
    }
  }
  if ((n.on && Math.abs(n.vx) < 0.02 && Math.abs(n.rot) < 1) || n.t >= k.ms) n.rest = true;
  return n;
}

//: The room a throw flies in, for its corner: the window's sides, the top
//: bar's underside, the bottom bar (or the window's foot) as the floor, and
//: the top of every panel on the tab at least its width wide as a ledge.
function nameMarkBuddyWorld(tab) {
  const { top, bottom } = nameMarkBuddyLedges();
  const roof = top ? top.bottom : 0;
  const base = bottom ? bottom.top : innerHeight;
  const ledges = nameMarkBuddyEdges(tab)
    .filter((e) => e.type === "top" && e.kind !== "bar" && e.right - e.left >= NMB_W && e.y > roof + NMB_FEET && e.y < base)
    .map((e) => ({ left: e.left - NMB_W / 2, right: e.right - NMB_W / 2, y: e.y - NMB_FEET + 1 }));
  return { left: 0, right: innerWidth - NMB_W, top: roof, floor: base - NMB_FEET + 1, ledges };
}

//: The throw itself, and what can happen on the way: companion-throw.js
//: (lazy, fetched on the first carry; INBOX 1301 D6).
//: Come down at `s`: the nearest place to there, as if dropped there, kept
//: as your spot on `tab`, the tab it was thrown on. Never the tab's own
//: choice near there: on Notes with 24 notes, thrown right from x 44 and
//: left from x 1168, both came down on one dock perch at x 763 (throw.js).
function nameMarkBuddyThrowSpot(s) {
  nameMarkBuddyIndexReset();
  let spot = nameMarkBuddyDrop(s.x, s.y);
  //: Landed where it cannot stand: step along that surface, not up to the top bar (INBOX 1302).
  if (s.on && spot.y < s.y - 40) {
    for (const reach of [400, innerWidth]) {
      const along = nameMarkBuddyDrop(s.x, s.y, reach);
      if (Math.abs(along.y - s.y) <= 40) {
        spot = along;
        break;
      }
    }
  }
  if (spot.y >= s.y + 2) spot.falls = true;
  return spot;
}
function nameMarkBuddyThrowLand(buddy, s, tab, spot) {
  nmb.thrown = { ...nmb.thrown, to: [Math.round(s.x), Math.round(s.y)] };
  nmb.placedAt = Date.now();
  nmb.afterLand = true;
  nameMarkBuddyMoveTo(buddy, spot);
  if (!nmb.anim || nmb.anim.playState !== "running") nameMarkBuddyAct("land");
  const spots = nameMarkBuddySpots();
  delete spots["*"];
  spots[tab] = nameMarkBuddySpotFor(spot);
  nameMarkBuddyKeepSpots(spots);
}

//: The pointer on it (`dwellMs` how long): awake, a look, a small lean, a
//: blink and a brighter face at once; asleep, a stir, and a wake if you stay.
function nameMarkBuddyHover(dwellMs) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nameMarkBuddyStill() || document.hidden || buddy.classList.contains("nm-buddy-dragging")) return;
  const asleep = buddy.classList.contains("nmb-sleep") || nmb.act === "nap" || nmb.act === "lie";
  const how = nameMarkBuddyHoverReaction(asleep, dwellMs, nameMarkBuddyWarmthAt(nmb.feel, Date.now()), Date.now() < nmb.grumpyUntil);
  if (how === "stir") {
    buddy.classList.add("nmb-stir", "nmb-groggy");
    setTimeout(() => buddy.classList.remove("nmb-stir"), 700);
    setTimeout(() => buddy.classList.remove("nmb-groggy"), 2400);
  } else if (how === "wake") {
    if (nmb.act === "lie") nameMarkBuddyAct("");
    nameMarkBuddyWake(true);
  } else if (how === "brighten") {
    if (nmb.pointer) nameMarkBuddyAim(nmb.pointer, true);
    if (!nmb.act) nameMarkBuddyAct("blink");
    if (!nmb.expr || nmb.expr === "calm") nameMarkBuddyExpress("happy", 1800);
  }
}

function nameMarkBuddyPet() {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nameMarkBuddyStill() || document.hidden || nameMarkBuddyMenuOpen()) return;
  if (buddy.classList.contains("nmb-sleep") || buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-walking")) return;
  const now = Date.now();
  if (now - (nmb.pettedAt || 0) < 15000 || now < nmb.grumpyUntil) return;
  nmb.pettedAt = now;
  nameMarkBuddyFeel(0.15);
  nmb.mood.sociability = Math.min(1, nmb.mood.sociability + 0.05);
  nameMarkBuddyExpress("happy", 1800);
  //: A pat does not end what it is doing (INBOX 443 c: "keep doing that
  //: action unless poked"): it is pleased, and wiggles only when idle.
  if (!nmb.act || NMB_FACELESS_ACTS.includes(nmb.act)) nameMarkBuddyAct("wiggle");
}
//: How often the pointer turned back along `axis` (0 is x, 1 is y) in the
//: last `windowMs` of `samples` ([x, y, t]), a turn counted only after a
//: leg of `travel` px or more: a rub over it, or a shake while it is
//: carried (INBOX 743). A pass across it, or a hand's tremor, is none.
function nameMarkBuddyStrokes(samples, axis, travel, windowMs) {
  const last = samples[samples.length - 1];
  if (!last) return 0;
  let turns = 0;
  let dir = 0;
  let anchor = null;
  for (const sample of samples) {
    if (last[2] - sample[2] > windowMs) continue;
    if (anchor === null) {
      anchor = sample[axis];
      continue;
    }
    const leg = sample[axis] - anchor;
    if (Math.abs(leg) < travel) continue;
    if (dir && Math.sign(leg) !== dir) turns += 1;
    dir = Math.sign(leg);
    anchor = sample[axis];
  }
  return turns;
}
//: **Rubbed** (INBOX 743, the owner: "more mouse interaction with the
//: companion like rubbing its head"): the pointer back and forth over it,
//: not pressing. It leans into the hand; awake, a fond face (Atlas fond or
//: bashful) and now and then a word, and a sulk ends, since a rub is the
//: apology a poke is not; asleep, it nuzzles and sleeps on. One transform
//: on the face's box, at most once in six seconds.
const NMB_RUB_LINES = ["Mm, that's nice.", "Hehe, that tickles.", "Right there.", "Again?"];
function nameMarkBuddyRubbed(buddy) {
  if (!buddy || nameMarkBuddyStill() || document.hidden || nameMarkBuddyMenuOpen() || buddy.classList.contains("nm-buddy-dragging") || nameMarkBuddyActOff("rub")) return;
  const now = Date.now();
  if (now - (nmb.rubbedAt || 0) < 6000) return;
  nmb.rubbedAt = now;
  nmb.pettedAt = now;
  nameMarkBuddyFeel(0.2);
  nmb.mood.sociability = Math.min(1, nmb.mood.sociability + 0.1);
  const face = buddy.querySelector(":scope > .nm-buddy-face");
  if (face && typeof face.animate === "function") {
    face.animate([
      { transform: "rotate(0deg)" }, { transform: "rotate(-6deg)", offset: 0.25 }, { transform: "rotate(4deg)", offset: 0.55 },
      { transform: "rotate(-2deg)", offset: 0.8 }, { transform: "rotate(0deg)" },
    ].map((frame) => ({ ...frame, transformOrigin: "50% 100%" })), { duration: 1400, easing: "ease-in-out" });
  }
  if (nameMarkBuddyAsleep(buddy)) return;
  if (now < nmb.grumpyUntil) {
    nmb.grumpyUntil = 0;
    buddy.classList.remove("nmb-grumpy", "nmb-pout");
    if (!buddy.classList.contains("nmb-walking")) delete buddy.dataset.turn;
  }
  if (isAtlasSeed(buddy.dataset.seed || "")) {
    setAtlasMood(Math.random() < 0.6 ? "love" : "shy", 3200, { quiet: true, backEaseMs: 1200 });
  } else {
    nameMarkBuddyExpress("love", 3200);
  }
  if (Math.random() < 0.4) nameMarkSay(buddy, NMB_RUB_LINES[Math.floor(Math.random() * NMB_RUB_LINES.length)]);
}
//: **Flipped** (INBOX 743, the owner: "flipping it upside down??"): shaken
//: up and down while carried, it turns over and hangs upside down from your
//: hold, startled; let go, it turns the rest of the way round as it falls
//: and lands dizzy for a moment. A transform on the face's box (the
//: compositor's), nothing laid out; under Still motion it stays upright.
function nameMarkBuddyFlip(buddy, on) {
  const face = buddy?.querySelector(":scope > .nm-buddy-face");
  nmb.flipAnim?.cancel();
  nmb.flipAnim = null;
  if (!face || typeof face.animate !== "function" || nameMarkBuddyStill()) return;
  const frames = on
    ? [{ transform: "rotate(0deg)" }, { transform: "rotate(200deg)", offset: 0.7 }, { transform: "rotate(180deg)" }]
    : [{ transform: "rotate(180deg)" }, { transform: "rotate(372deg)", offset: 0.75 }, { transform: "rotate(360deg)" }];
  const anim = face.animate(frames.map((frame) => ({ ...frame, transformOrigin: "50% 50%" })), { duration: on ? 420 : 560, easing: "ease-out", fill: on ? "forwards" : "none" });
  const atlas = isAtlasSeed(buddy.dataset.seed || "");
  buddy.classList.toggle("nmb-flipped", on);
  if (on) {
    nmb.flipAnim = anim;
    if (atlas) setAtlasMood("surprised", 1500, { quiet: true });
    else nameMarkBuddyExpress("surprised", 8000);
    return;
  }
  nameMarkBuddyFeel(-0.05);
  if (atlas) setAtlasMood("confused", 2600, { quiet: true, backEaseMs: 1200 });
  else nameMarkBuddyExpress("dizzy", 2600);
  nameMarkSay(buddy, ["Whoa.", "Everything is spinning.", "The room is upside down."][Math.floor(Math.random() * 3)]);
}
const NMB_POOF_OUT_MS = 180;
const NMB_POOF_IN_MS = 300;
function nameMarkBuddyPoof(buddy, dx, dy, fromSeen) {
  const out = fromSeen ? NMB_POOF_OUT_MS : 0;
  const total = out + NMB_POOF_IN_MS;
  const at = out / total;
  buddy.classList.add("nmb-poofing");
  //: The shrink is the character's, not the host's: an individual `scale`
  //: on the host is applied before its `transform`, so it scaled the
  //: translate that places it and swept it across the page.
  //: **Out and in as two gestures** (the owner, 2026-09-27: "the
  //: disappearing and reappearing animation needs to be improved again,
  //: even if it is adjusting its position"). It was one ease over both,
  //: 150ms out and 220ms in, a shrink to 0.55 and back: read as a blink.
  //: Now the way out eases in (it gathers, lifts a little and is gone) and
  //: the way in eases out from a small drop, overshooting its size a touch
  //: before it settles, as the materialise does (`nameMarkBuddyEnter`).
  const soft = "cubic-bezier(0.2, 0.8, 0.2, 1)";
  const cut = Math.min(1, at + 0.001);
  nmb.anim = buddy.animate(fromSeen ? [
    { translate: `${dx}px ${dy}px`, opacity: 1, easing: "ease-in" },
    { translate: `${dx}px ${dy}px`, opacity: 0, offset: at },
    { translate: "0px 0px", opacity: 0, offset: cut, easing: soft },
    { translate: "0px 0px", opacity: 1 },
  ] : [
    { opacity: 0, easing: soft },
    { opacity: 1 },
  ], { duration: total });
  const char = buddy.querySelector(".nm-buddy-char");
  const arrive = (from) => [
    { scale: "0.6", translate: "0px -8px", offset: from, easing: "ease-out" },
    { scale: "1.04", translate: "0px 1px", offset: from + (1 - from) * 0.7, easing: "ease-in-out" },
    { scale: "1", translate: "0px 0px" },
  ];
  nmb.hopAnim = char?.animate(fromSeen ? [
    { scale: "1", translate: "0px 0px", easing: "ease-in" },
    { scale: "0.6", translate: "0px -6px", offset: at },
    ...arrive(cut),
  ] : arrive(0), { duration: total }) || null;
  //: Only this poof's own end takes the class off: a cancelled earlier
  //: move reports its `cancel` a moment later, after this one began.
  const anim = nmb.anim;
  const done = () => {
    if (nmb.anim === anim) buddy.classList.remove("nmb-poofing");
  };
  anim.onfinish = done;
  anim.oncancel = done;
  if (fromSeen) nameMarkBuddyBurst(buddy, dx, dy, 0);
  nameMarkBuddyBurst(buddy, 0, 0, out);
}

//: The stars: beside the figure in its rider, not inside it, so they are
//: not faded with it; eight of them flung out on transforms, gone with
//: their element 240ms after they start.
function nameMarkBuddyBurst(buddy, dx, dy, delay) {
  const host = buddy.parentElement;
  if (!host) return;
  const burst = document.createElement("span");
  burst.className = "nmb-burst";
  burst.setAttribute("aria-hidden", "true");
  burst.style.transform = `translate(${nmb.lx + dx}px, ${nmb.ly + dy}px)`;
  burst.style.setProperty("--nmb-burst-delay", `${delay}ms`);
  for (let i = 0; i < 8; i += 1) {
    const star = document.createElement("i");
    star.style.setProperty("--nmb-burst-a", `${i * 45 + Math.round(Math.random() * 20 - 10)}deg`);
    star.style.setProperty("--nmb-burst-r", `${26 + Math.round(Math.random() * 12)}px`);
    burst.appendChild(star);
  }
  host.appendChild(burst);
  setTimeout(() => burst.remove(), delay + 260);
}

//: Chooses where it belongs on this tab now and goes there: your spot on
//: this tab while its panel is there, the place you pinned it on every
//: page, else the tab's best perch (the nearest good one, with `near`).
function placeNameMarkBuddy(buddy = document.getElementById("nm-buddy"), instant = false, near = null) {
  if (!buddy || buddy.classList.contains("nm-buddy-dragging")) return;
  const tab = nameMarkBuddyTab();
  nmb.tab = tab;
  nameMarkBuddyMoveTo(buddy, nameMarkBuddyNextSpot(tab, near), instant);
}

//: **Something under it** (INBOX 582, the owner: "bro's just perched on
//: nothing in the mindmap. the companion keeps being left floating in
//: places on various pages and sub tabs and tabs"). Its perch was chosen
//: once and then only checked for controls coming up under it, so a perch
//: that went (a sub-tab's dock hidden with its view, a card re-drawn, a
//: board's content panned away) left it sitting on the air where the edge
//: had been: measured (`scratchpad/ui-sweeps/smooth1005-perch.js`) on the
//: Library's AI skills, seated on a dock its view had hidden. Asked of the
//: page itself, not of the perch it remembers: under the middle of its
//: seat, soles or hands, is there a visible element whose top edge (bottom,
//: hanging) is within 2px of that line? Floating, peeking over the bar,
//: leaning on a side or pinned where you put it is not a perch to check;
//: what is drawn on a board, a map or the graph is never one.
const NMB_CANVAS = "#whiteboard-container, #graph-canvas, #graph-svg, #graph-pane-canvas, canvas";
function nameMarkBuddySupported() {
  if (nmb.pinned) return true;
  //: Peeking over a bar or leaning on a side holds on to its edge, which
  //: can still go (a status bar emptied on a phone is `visibility: hidden`):
  //: then it is in the air, as any other perch lost.
  if (nmb.legs === "peek" || nmb.spot?.side) {
    const held = nmb.spot?.edge?.el;
    return !held || Boolean(held.isConnected && nameMarkBuddyPerchShown(held));
  }
  if (!["sit", "stand", "hang"].includes(nmb.pose)) return true;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return true;
  //: Where it is drawn: the host is not scaled (its face is, about this
  //: same line), and a ride or a translate is in its box.
  const at = buddy.getBoundingClientRect();
  const hang = nmb.pose === "hang";
  const line = at.top + (hang ? NMB_GRIP : nmb.pose === "sit" ? NMB_SEAT : NMB_FEET - 1);
  const mid = at.left + NMB_W / 2;
  //: The edge it chose, where it still is and still shows (a surface that
  //: takes no pointer is missed by a hit test).
  const el = nmb.spot?.edge?.el || nmb.spot?.anchor;
  const box = el?.isConnected && !el.closest(NMB_CANVAS) ? nameMarkBuddyPerchShown(el) : null;
  if (box && Math.abs((hang ? box.bottom : box.top) - line) <= 2 && box.left <= mid && box.right >= mid) return true;
  const band = document.getElementById("nm-buddy-band");
  for (const f of [0.3, 0.5, 0.7]) {
    const px = at.left + NMB_W * f;
    const py = hang ? line - 1 : line + 1;
    if (px < 0 || px >= innerWidth || py < 0 || py >= innerHeight) continue;
    for (const el of document.elementsFromPoint(px, py)) {
      if (band?.contains(el)) continue;
      if (el === document.documentElement || el === document.body || el.classList.contains("tab-page")) break;
      if (el.closest(NMB_CANVAS) && !el.matches("#whiteboard-container")) continue;
      const r = el.getBoundingClientRect();
      if (Math.abs((hang ? r.bottom : r.top) - line) <= 2 && !el.matches("#whiteboard-container")) return true;
    }
  }
  return false;
}

//: Asked again whenever the page under it may have changed without a
//: scroll: a pan or a zoom on a canvas (a wheel there scrolls nothing), a
//: press that let go, and every 1.5s while it rests in view (three hit
//: tests). Gone from under it, it chooses again, now: a walk, a glide or a
//: float to the nearest good perch, or the window's bar.
//: Its timer is `nmbFollow.support`, beside the follow loop's own.
function nameMarkBuddySupportSoon() {
  clearTimeout(nmbFollow.support);
  nmbFollow.support = setTimeout(queueNameMarkBuddyCheck, 400);
}
document.addEventListener("wheel", nameMarkBuddySupportSoon, { passive: true, capture: true });
document.addEventListener("pointerup", nameMarkBuddySupportSoon, { passive: true, capture: true });

//: **A scroll over the companion scrolls what is under it** (INBOX 674, the
//: owner: "when hovering over the companion, I cant two finger scroll on the
//: trackpad"). It is `position: fixed`, so the browser's scroll chain from it
//: ends at the document, which does not scroll in this app: the list under
//: it never heard the wheel. The element beneath gets the same wheel (a
//: board or map pans by its own handler), and when nothing there takes it,
//: the nearest scroller under the pointer moves by the same amount.
document.addEventListener("wheel", (event) => {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || event.ctrlKey || !buddy.contains(event.target)) return;
  const under = document.elementsFromPoint(event.clientX, event.clientY).find((el) => !buddy.contains(el));
  if (!under) return;
  const passed = new WheelEvent("wheel", event);
  under.dispatchEvent(passed);
  if (passed.defaultPrevented) return event.preventDefault();
  const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? window.innerHeight : 1;
  for (let el = under; el && el !== document.documentElement; el = el.parentElement) {
    const style = getComputedStyle(el);
    const y = event.deltaY && /auto|scroll/.test(style.overflowY) && el.scrollHeight > el.clientHeight;
    const x = event.deltaX && /auto|scroll/.test(style.overflowX) && el.scrollWidth > el.clientWidth;
    if (!x && !y) continue;
    event.preventDefault();
    el.scrollBy({ left: x ? event.deltaX * unit : 0, top: y ? event.deltaY * unit : 0 });
    return;
  }
}, { passive: false });
//: **Behind the lock it is not drawn at all**: the lock screen covers it,
//: but its face's loops (a blink, a bounce) restyled the page under it
//: 264 times a minute. Out of the layout while locked, its loops stop;
//: back as it was when the lock lifts.
function nameMarkBuddyLockSync() {
  const band = document.getElementById("nm-buddy-band");
  const lock = document.getElementById("lock-overlay");
  if (band) band.style.display = lock && !lock.classList.contains("hidden") && lock.dataset.mode !== "prompt" ? "none" : "";
}
//: `data-cover` (read by the CSS) moves it off a modal or the lock screen. A
//: document-wide `:has()` did this and cost 4.7 of each 16.7 ms drag frame.
const NMB_COVER_SEL = "dialog, .modal-overlay, .lock-overlay";
function nameMarkBuddyCoverCheck() {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  const lock = document.querySelector("#lock-overlay:not(.hidden)");
  const cover = lock ? "lock" : document.querySelector("dialog[open]:modal, .modal-overlay:not(.hidden), .lock-overlay:not(.hidden)") ? "modal" : "";
  if (cover) buddy.dataset.cover = cover;
  else delete buddy.dataset.cover;
}
function nameMarkBuddyCoverWatch(records) {
  const hit = (n) => n.nodeType === 1 && (n.matches(NMB_COVER_SEL) || n.querySelector(NMB_COVER_SEL));
  const touched = records.some((m) => (m.type === "attributes" ? m.target.matches(NMB_COVER_SEL) : [...m.addedNodes, ...m.removedNodes].some(hit)));
  //: Read on the perch check's own frame (`queueNameMarkBuddyCheck`).
  if (touched) {
    nmb.coverDirty = true;
    queueNameMarkBuddyCheck();
  }
}
//: `typeof MutationObserver`: tests/test_atlas_shape.py loads this file in a node vm with a bare `document`.
if (typeof MutationObserver === "function" && document.getElementById("lock-overlay")) {
  new MutationObserver(nameMarkBuddyLockSync).observe(document.getElementById("lock-overlay"), { attributes: true, attributeFilter: ["class", "data-mode"] });
}
//: **The perch check runs when something could have changed** (Brief 34
//: decision 7). It used to look every 1.5s whatever happened: each look
//: walks the tab's controls (`nameMarkBuddyObstacles`), so a page nobody
//: touched paid for forty of them a minute (companionperf.js IDLE=1: 737ms
//: of script a minute with the generated companion on, against 32 off,
//: most of it here), and it went on under the lock screen. Now it looks
//: within 1.5s of input, a resize or a toast, and otherwise once in 10s in
//: case the page changed by itself; never in a hidden window or under the
//: lock.
const NMB_CHECK_IDLE_MS = 10000;
//: Armed, not polled (battery, INBOX 1351): one timer that sleeps the full
//: idle span and shortens only for input or a toast; none in a hidden window.
const NMB_IDLE_MARK_MS = 120000;
const nmbClock = { timer: 0, inputAt: Date.now() };
function nmbTickArm(ms) {
  clearTimeout(nmbClock.timer);
  nmbClock.timer = document.hidden ? 0 : setTimeout(nmbTick, ms);
}
for (const type of ["pointerdown", "keydown", "wheel", "resize"]) {
  (type === "resize" ? window : document).addEventListener(type, () => {
    if (type !== "resize") {
      nmbClock.inputAt = Date.now();
      document.documentElement.classList.remove("is-idle");
    }
    if (!nmb.checkDue) nmbTickArm(1500);
    nmb.checkDue = true;
  }, { passive: true, capture: true });
}
document.addEventListener("visibilitychange", () => nmbTickArm(1500));
function nmbTick() {
  const now = Date.now();
  //: Two minutes without input: the marks hold still (CSS `.is-idle`).
  document.documentElement.classList.toggle("is-idle", now - nmbClock.inputAt > NMB_IDLE_MARK_MS);
  const toasting = !!document.querySelector("#toast-box > :not(.hidden)");
  if (!(nmb.away || !document.getElementById("nm-buddy") || nameMarkBuddyCurtained())
      && (nmb.checkDue || toasting || now - (nmb.checkedAt || 0) >= NMB_CHECK_IDLE_MS)) {
    nmb.checkDue = false;
    nmb.checkedAt = now;
    queueNameMarkBuddyCheck();
  }
  nmbTickArm(nmb.checkDue || toasting ? 1500 : NMB_CHECK_IDLE_MS);
}
nmbTickArm(1500);

//: Where it is now still does: on screen, not lost, not held off its
//: panel, not over a control, and on something.
function nameMarkBuddyStillGood(obstacles) {
  if (!Number.isFinite(nmb.x) || nmb.perch === "errand" || nmb.outOfSight) return false;
  if (nmb.glue && (nmb.glue.lost || nmb.glue.held)) return false;
  if (!nameMarkBuddySupported()) return false;
  if (nmb.x < 0 || nmb.y < 0 || nmb.x > innerWidth - NMB_W || nmb.y > innerHeight - NMB_H) return false;
  return !nameMarkBuddyHits(nmb.x, nmb.y, nmb.pose, nmb.perch === "yours" ? nameMarkBuddyYoursObstacles(obstacles, nmb.spot) : obstacles, nmb.legs);
}

//: The cheap check (a placement's worth of rects, no sampling unless it
//: has to move): a control has come up under it, and it steps aside along
//: the same edge. Nothing else moves it from here: a panel that moved is
//: followed (`nameMarkBuddyFollow`), and a new tab is looked at on its own
//: next beat (`nameMarkBuddyQueuePlace`).
function nameMarkBuddyCheck() {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nmb.pinned || nmb.away || nmb.visit || buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-walking")) return;
  if (nameMarkBuddyMenuOpen()) {
    clearTimeout(nmbFollow.recheck);
    nmbFollow.recheck = setTimeout(queueNameMarkBuddyCheck, 600);
    return;
  }
  const tab = nameMarkBuddyTab();
  if (tab !== nmb.tab) {
    nameMarkBuddyQueuePlace();
    return;
  }
  //: Held at the edge of the band, or floating with its panel gone, where
  //: it is is not a place yet: `nameMarkBuddyUnheld` or its next beat
  //: chooses one.
  if (nmb.glue && (nmb.glue.held || nmb.glue.lost)) return;
  //: Not while the page is moving under it: once it has been still a
  //: moment, looked at again. Whatever it is on: this was the glued case
  //: only, and hanging from the top bar every `scrollend` (one per wheel
  //: step) ran the whole obstacle sweep, 139ms over a 3s scroll.
  if (performance.now() - nmbFollow.scrollAt < 400) {
    clearTimeout(nmbFollow.recheck);
    nmbFollow.recheck = setTimeout(queueNameMarkBuddyCheck, 450);
    return;
  }
  //: Its perch gone from under it (INBOX 582): never left sitting on the
  //: air until its next beat. Not mid-move: where it is drawn then is on
  //: the way, not a perch.
  //: Once in three seconds at most, so a perch this cannot see from here is
  //: never a loop.
  const wait = 3000 - (Date.now() - (nmb.unheldAt || 0));
  if (![nmb.anim, nmb.hopAnim, nmb.glideAnim].some((a) => a?.playState === "running") && !nameMarkBuddySupported()) {
    //: Lost inside the three seconds: looked at again when they are up, not
    //: left in the air until the next idle look.
    if (wait > 0) {
      clearTimeout(nmbFollow.recheck);
      nmbFollow.recheck = setTimeout(queueNameMarkBuddyCheck, wait + 50);
      return;
    }
    nmb.unheldAt = Date.now();
    nmb.moves = (nmb.moves || 0) + 1;
    nmb.moveWhy = "its perch went";
    nameMarkBuddyIndexReset();
    placeNameMarkBuddy(buddy, false, [nmb.x, nmb.y]);
    return;
  }
  const all = nameMarkBuddyObstacles(tab);
  const obstacles = nmb.perch === "yours" ? nameMarkBuddyYoursObstacles(all, nmb.spot) : all;
  if (!nameMarkBuddyHits(nmb.x, nmb.y, nmb.pose, obstacles, nmb.legs)) return;
  const here = { ...(nmb.spot || {}), x: nmb.x, y: nmb.y, pose: nmb.pose, legs: nmb.legs };
  const aside = nameMarkBuddyStepAside(here, obstacles);
  nmb.moves = (nmb.moves || 0) + 1;
  nmb.moveWhy = "covering a control";
  if (aside.x !== here.x) nameMarkBuddyMoveTo(buddy, aside);
  else nameMarkBuddyQueuePlace();
}

function queueNameMarkBuddyCheck() {
  if (nmb.checkFrame || !document.getElementById("nm-buddy")) return;
  nmb.checkFrame = requestAnimationFrame(() => {
    nmb.checkFrame = 0;
    if (nmb.coverDirty) {
      nmb.coverDirty = false;
      nameMarkBuddyCoverCheck();
    }
    nameMarkBuddyCheck();
  });
}

//: **On its own time** (INBOX 426 m, the owner: "atlas needs to move and
//: work on its own time not based off how fast the user is switching tabs
//: or scrolling"). A tab switch, or its panel going away, only asks for a
//: look; the look comes on its own beat, one and a bit to two and a half
//: seconds after the first ask and never within five seconds of its last
//: move, and asks in between do not push it back. At the beat it stays
//: where it is if that still does, goes to your spot for the tab if you
//: gave it one, and otherwise walks to the nearest good perch. Pinned on
//: every page, it never moves on its own (INBOX 426 l).
function nameMarkBuddyQueuePlace() {
  if (nmb.placeTimer || nmb.pinned || nmb.visit || !document.getElementById("nm-buddy")) return;
  const since = Date.now() - (nmb.movedAt || 0);
  nmb.placeTimer = setTimeout(nameMarkBuddyBeat, Math.max(1200 + Math.random() * 1300, 5000 - since));
}

//: **Its menu holds it where it is** (INBOX 426 x, 84.png: the menu open
//: in one corner and the companion in another). The menu is placed at it
//: when it opens; nothing it does on its own (a behaviour, an errand,
//: stepping aside, leaving an edge, its beat) moves it until the menu
//: closes, so the menu is never left behind.
function nameMarkBuddyMenuOpen() {
  return !!(nmb.menu && nmb.menu.isConnected && !nmb.menu.classList.contains("hidden"));
}

function nameMarkBuddyBeat() {
  nmb.placeTimer = 0;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nmb.pinned || nmb.away || nmb.visit) return;
  const busy = buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-walking")
    || nameMarkBuddyMenuOpen();
  if (busy || document.hidden) {
    nameMarkBuddyQueuePlace();
    return;
  }
  const tab = nameMarkBuddyTab();
  const own = nameMarkBuddySpots()[tab];
  nameMarkBuddyIndexReset();
  //: A new view in the tab (`nameMarkBuddyViewChanged`): a window bar was
  //: the last resort of the view it left, so it looks again, and by the
  //: tab's own preference rather than the nearest (a bar 15px away beat a
  //: card 400px away by 20 points).
  const fresh = nmb.fresh;
  nmb.fresh = false;
  if (!own && !(fresh && ["bar", "hang", "corner"].includes(nmb.perch)) && nameMarkBuddyStillGood(nameMarkBuddyObstacles(tab))) {
    nmb.tab = tab;
    return;
  }
  placeNameMarkBuddy(buddy, false, fresh ? null : [nmb.x, nmb.y]);
}

//: **Another view in the same tab** (INBOX 521, the owner: "the companion
//: perching needs fixing for many of the library tabs as well as for the
//: whiteboard and mindmap"). A Library sub-tab, a board opened or closed:
//: the tab is the same, so nothing asked it to look again, and it stayed on
//: the window bar the last view left it on, over a control the new one put
//: under it (perchall.js). Now a view shown or hidden in the tab, or a
//: sub-tab pressed, is a look at once for controls and a new perch on its
//: next beat.
const NMB_VIEWS = ".library-view-section, [role='tabpanel'], #wb-canvas-view, #wb-boards-landing";
function nameMarkBuddyViewChanged() {
  if (!document.getElementById("nm-buddy") || nmb.pinned) return;
  nameMarkBuddyIndexReset();
  nmb.fresh = true;
  queueNameMarkBuddyCheck();
  nameMarkBuddyQueuePlace();
}
if (globalThis.MutationObserver) {
  const views = new MutationObserver((records) => {
    for (const r of records) {
      const el = r.target;
      if (el.classList.contains("tab-page") || !el.matches(NMB_VIEWS)) continue;
      if (/(^|\s)hidden(\s|$)/.test(r.oldValue || "") !== el.classList.contains("hidden")) return nameMarkBuddyViewChanged();
    }
  });
  const watch = () => {
    for (const page of document.querySelectorAll(".tab-page")) views.observe(page, { subtree: true, attributes: true, attributeFilter: ["class"], attributeOldValue: true });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch);
  else watch();
}
document.addEventListener("click", (event) => {
  if (event.target?.closest?.(".tab-page [role='tab']")) setTimeout(nameMarkBuddyViewChanged, 300);
}, { passive: true });

//: **It lives on a tab, and follows you only once you have stayed**
//: (INBOX 430, the owner: "the companion lingers on the old tab for a
//: second, then pops in elsewhere"; wanted: it "stays on the old tab (hidden
//: with it) and only follows once the person has stayed on the new tab about
//: 1.5 to 3s. Quick flicks back and forth never make it appear and
//: disappear"). A tab switch hides it with the tab it is on; coming back
//: before it has followed shows it again where it was, as the tab itself
//: comes back; staying on another tab for `NMB_DWELL_MS` (plus up to
//: `NMB_DWELL_JITTER_MS`, so it is not a clock) brings it in, by the way in
//: that suits where it is going (`nameMarkBuddyEnter`). Every switch
//: restarts the wait. Pinned on every page, it is on every tab, and stays.
const NMB_DWELL_MS = 1300;
const NMB_DWELL_JITTER_MS = 1200;
function nameMarkBuddyTabChanged() {
  nameMarkBuddyIndexReset();
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nmb.visit) return;
  for (const timer of nmb.settle) clearTimeout(timer);
  if (nmb.pinned) {
    nameMarkBuddyFollow();
    return;
  }
  clearTimeout(nmb.awayTimer);
  const tab = nameMarkBuddyTab();
  //: Not placed yet (built a moment ago, still settling): it comes in on
  //: the tab that is shown, once that has settled.
  if (!Number.isFinite(nmb.x)) {
    nmb.away = true;
    buddy.classList.add("nmb-away");
    nameMarkBuddyArrive(buddy);
    return;
  }
  if (!nmb.tab || tab === nmb.tab) {
    nmb.away = false;
    buddy.classList.remove("nmb-away");
    nameMarkBuddyFollow();
    if (!nmb.tab) nameMarkBuddyQueuePlace();
    return;
  }
  nmb.away = true;
  buddy.classList.add("nmb-away");
  nmb.cameFrom = nameMarkBuddyTabSide(nmb.tab, tab);
  nmb.awayTimer = setTimeout(() => nameMarkBuddyArrive(buddy), NMB_DWELL_MS + Math.random() * NMB_DWELL_JITTER_MS);
}

//: **In from the side of the tab it left** (INBOX 455 (2): "moving across
//: different ... tab(s)"): the tab bar is a row, so a tab to the right of
//: the one it was on is reached by coming in from the left, and back again
//: from the right. -1 the left, 1 the right, 0 when it cannot tell.
function nameMarkBuddyTabSide(from, to) {
  const order = [...document.querySelectorAll("#tab-bar button[data-tab]")].map((b) => b.dataset.tab);
  const at = (tab) => order.indexOf(tab === "documents" ? "library" : tab);
  const a = at(from);
  const b = at(to);
  return a < 0 || b < 0 || a === b ? 0 : a < b ? -1 : 1;
}

//: Where it goes on `tab`: your spot for it, the spot for every page, or
//: the best free perch. `placeNameMarkBuddy`'s choice, without the move.
function nameMarkBuddyNextSpot(tab, near = null) {
  const obstacles = nameMarkBuddyObstacles(tab);
  const spots = nameMarkBuddySpots();
  if (spots["*"] && !spots[tab]) {
    const pinned = nameMarkBuddyRestore(spots["*"]);
    if (pinned) return { ...pinned, kind: "pinned" };
  }
  const restored = spots[tab] ? nameMarkBuddyRestore(spots[tab]) : null;
  return restored ? nameMarkBuddyStepAside(restored, nameMarkBuddyYoursObstacles(obstacles, restored)) : nameMarkBuddyChoose(tab, obstacles, near);
}

//: The person has stayed: it takes its place on this tab out of sight and
//: then comes in.
//: **Not behind the curtain** (INBOX 577): while the boot splash, the lock
//: screen or the opening curtain (`revealShell`, app.js) is over the page,
//: the page under it is still filling in and nobody can see it come in.
//: It used to play its whole entrance there, under the lock screen, and
//: then simply be there, full size, the moment the lock lifted. It waits,
//: and comes in once the shell has risen, as one more beat of the same
//: sequence rather than a second one racing it.
function nameMarkBuddyCurtained() {
  if (document.getElementById("boot-splash")) return true;
  if (document.documentElement.classList.contains("shell-curtain")) return true;
  const lock = document.getElementById("lock-overlay");
  return Boolean(lock && !lock.classList.contains("hidden") && lock.dataset.mode !== "prompt");
}

function nameMarkBuddyArrive(buddy) {
  nmb.awayTimer = 0;
  if (!buddy.isConnected || !nmb.away) return;
  if (nameMarkBuddyCurtained()) {
    nmb.awayTimer = setTimeout(() => nameMarkBuddyArrive(buddy), 250);
    return;
  }
  if (document.hidden || nameMarkBuddyMenuOpen() || buddy.classList.contains("nm-buddy-dragging")) {
    nmb.awayTimer = setTimeout(() => nameMarkBuddyArrive(buddy), 800);
    return;
  }
  const tab = nameMarkBuddyTab();
  nameMarkBuddySettle(tab, (spot) => {
    if (!buddy.isConnected || !nmb.away || nameMarkBuddyTab() !== tab) return;
    nmb.tab = tab;
    nameMarkBuddyMoveTo(buddy, spot, true);
    nmb.away = false;
    buddy.classList.remove("nmb-away");
    nmb.enteredBy = nameMarkBuddyEnter(buddy, spot);
  });
}

//: **Its place, once the page has stopped moving under it.** A tab (or the
//: app, at start) is often still filling in when the companion is due:
//: cards arrive, a list is drawn, fonts load, and a perch chosen then is
//: carried away a frame later. So the perch is chosen, the box it stands on
//: (or the tab's page, for a bar or a pinned place) is read once a frame,
//: and only when it has not moved for `NMB_SETTLE_QUIET_MS` is `then` given
//: the perch, chosen again if anything moved. One rect a frame, for at most
//: `NMB_SETTLE_MAX_MS`; nothing runs once it has come in. A second call
//: (another tab) replaces the first.
const NMB_SETTLE_QUIET_MS = 300;
const NMB_SETTLE_MAX_MS = 2500;
function nameMarkBuddySettle(tab, then) {
  cancelAnimationFrame(nmb.settleFrame);
  const start = performance.now();
  let spot = null;
  let sig = "";
  let quiet = start;
  let moved = false;
  const read = (s) => {
    const el = s.kind === "pinned" ? null : s.anchor || s.edge?.el || document.getElementById(`tab-${tab}`);
    const box = el?.isConnected ? el.getBoundingClientRect() : null;
    return box ? `${Math.round(box.left)},${Math.round(box.top)},${Math.round(box.width)},${Math.round(box.height)}` : "";
  };
  const choose = () => {
    nameMarkBuddyIndexReset();
    spot = nameMarkBuddyNextSpot(tab);
    sig = read(spot);
    moved = false;
  };
  const look = (now) => {
    nmb.settleFrame = 0;
    if (nameMarkBuddyTab() !== tab) return;
    const again = read(spot);
    if (again !== sig) {
      sig = again;
      quiet = now;
      moved = true;
    }
    if (now - quiet >= NMB_SETTLE_QUIET_MS || now - start >= NMB_SETTLE_MAX_MS) {
      //: And in when the page has a moment to spare: an entrance started
      //: while the app was still booting ran through 56ms frames and
      //: stuttered (measured, a walk-in covering 32px in one sampled frame).
      const go = () => {
        if (nameMarkBuddyTab() !== tab) return;
        if (moved) choose();
        then(spot);
      };
      if (typeof requestIdleCallback === "function") requestIdleCallback(go, { timeout: 600 });
      else go();
      return;
    }
    nmb.settleFrame = requestAnimationFrame(look);
  };
  const begin = () => {
    if (nameMarkBuddyTab() !== tab) return;
    choose();
    quiet = performance.now();
    nmb.settleFrame = requestAnimationFrame(look);
  };
  //: The faces' letters are part of what it measures around.
  if (document.fonts?.status === "loading") document.fonts.ready.then(begin, begin);
  else begin();
}

//: **In by the way that suits where it is going, never a pop** (INBOX
//: 430: "walk on from the nearest screen edge, climb up from the bottom
//: bar, climb down from the top bar to hang, or a soft materialise (a
//: starlight shimmer resolving into it)"). Each is the host's `translate`
//: and the character's `opacity`, the compositor's. With Reduce motion it
//: fades in where it is.
//:
//: **It comes in at its own size** (INBOX 577, the owner: "when loading
//: into the app, the companion or atlas's head goes large then small then
//: large again then settles on the normal size"). That was the landing
//: squash (`nameMarkBuddySquash`: 1.06, 0.97, 1, 1.07, 0.98, 1 across)
//: played on every way in, and the materialise's growth from half size:
//: the first thing anyone saw of it was its size changing. An entrance
//: moves it and fades it; a squash belongs to a hop between two perches it
//: was already seen on. `scratchpad/ui-sweeps/smooth1005-boot.js`: the
//: head's box moved 46% after it first showed, now under 2%.
function nameMarkBuddyEnter(buddy, spot) {
  if (typeof buddy.animate !== "function") return "";
  nmb.anim?.cancel();
  nmb.hopAnim?.cancel();
  nmb.movedAt = Date.now();
  const char = buddy.querySelector(".nm-buddy-char");
  //: Asleep, it is carried in, not walked: a slow fade where it lies.
  if (nameMarkBuddyAsleep(buddy)) {
    nmb.anim = buddy.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 700, easing: "ease-in-out" });
    nmb.anim.onfinish = null;
    return "asleep";
  }
  if (nameMarkBuddyNoTravel()) {
    nmb.anim = buddy.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, easing: "ease-out" });
    nmb.anim.onfinish = null;
    return "fade";
  }
  const x = nmb.x;
  const y = nmb.y;
  const edge = 150;
  //: **The first entrance after an unlock is a drop** (INBOX 707, the owner:
  //: "when loading the app after login, the companion just appears with no
  //: animation"). Measured at 1440x900 after the lock lifted: the usual
  //: starlight entrance went from invisible to opaque in 250ms over a 14px
  //: drift, which read as appearing. This one is once per page load (the
  //: unlock is the page's), 640ms: down 56px onto its perch, faded up over
  //: the first 40%, a small give at the bottom and settled at rest, so it
  //: ends where it stands with no jump. A tab switch never plays it: the
  //: flag is spent; hanging and bar perches already come out of their bar.
  //: Under Avatar animation off and Reduce motion the fade above ran first.
  const hangs = spot.kind === "hang" || spot.pose === "hang" || spot.kind === "bar" || y + NMB_H > innerHeight - 110;
  if (nmb.unlockDrop && !hangs) {
    nmb.unlockDrop = false;
    nmb.lastEnter = "drop";
    buddy.dataset.route = "enter-drop";
    nmb.anim = buddy.animate(
      [{ translate: "0px -56px", opacity: 0 }, { opacity: 1, offset: 0.4 }, { translate: "0px 5px", opacity: 1, offset: 0.78 }, { translate: "0px 0px", opacity: 1 }],
      { duration: 640, easing: "cubic-bezier(0.3, 0.6, 0.3, 1)" },
    );
    nmb.hopAnim = null;
    nameMarkBuddyLimbs(buddy, "float", 640);
    return "drop";
  }
  const unlockFirst = nmb.unlockDrop;
  nmb.unlockDrop = false;
  //: The side it comes from: the tab it left (`nameMarkBuddyTabSide`), or
  //: the nearer edge. Near that side it walks on; further in, it glides in
  //: from it; nearer the other side than that, it materialises.
  const side = nmb.cameFrom || 0;
  nmb.cameFrom = 0;
  const fromLeft = side ? side < 0 : x < innerWidth / 2;
  const reach = fromLeft ? x : innerWidth - x - NMB_W;
  //: **Not the same way twice** (INBOX 501, the owner: "it just kinda
  //: appears and there is no smooth or creative animation for it to
  //: happen, or even differences on how it gets there"). The same perch
  //: chose the same entrance every time: on the dashboard, hanging from
  //: the top bar, the climb down five times in five (companionarrive.js).
  //: Each place now has the ways that suit it, and the one it used last is
  //: left out when there is another: hanging, down from the bar or
  //: gathering out of starlight; on the bottom bar, up over it or
  //: gathering; near a side, walking on, gliding in or gathering; further
  //: in, gliding in from the side it came from or gathering.
  //: **And two more ways in** (Brief 88, the owner: "screen entries"):
  //: dropping in from above the window onto its perch (Atlas drifts down
  //: instead, swaying, as it floats), and tumbling in from the nearer side
  //: in a roll and a bounce. Three ways or more wherever it stands; one
  //: hanging under a bar keeps its two, since nothing falls up under a bar.
  let ways;
  if (spot.kind === "hang" || spot.pose === "hang") ways = ["down", "materialise"];
  else if (spot.kind === "bar" || y + NMB_H > innerHeight - 110) ways = ["up", "materialise", "tumble"];
  else if (reach < edge) ways = ["walk", "glide", "materialise", "tumble"];
  else if (reach < innerWidth * 0.5) ways = ["glide", "materialise", "fall"];
  else ways = ["materialise", "fall"];
  const fresh = ways.filter((w) => w !== nmb.lastEnter);
  const pick = fresh.length ? fresh : ways;
  //: The first entrance of an unlock is never the bare fade: a hanging one climbs down, one on a bar climbs up.
  const how = unlockFirst ? ways[0] : pick[Math.floor(Math.random() * pick.length)];
  nmb.lastEnter = how;
  buddy.dataset.route = `enter-${how}`;
  if (how === "glide") {
    const dx = fromLeft ? -(x + NMB_W + 12) : innerWidth - x + 12;
    //: In at speed and slowing to its place, under 30px a frame as it
    //: shows (companionroutes.js: 46 on a steeper curve).
    const duration = Math.round(Math.min(1100, 480 + Math.abs(dx) * 0.7));
    const way = dx > 0 ? -1 : 1;
    nameMarkBuddyWay(buddy, String(way));
    nmb.anim = buddy.animate([{ translate: `${dx}px 0px`, opacity: 0 }, { opacity: 1, offset: 0.25 }, { translate: "0px 0px", opacity: 1 }], { duration, easing: "cubic-bezier(0.25, 0.5, 0.25, 1)" });
    nmb.hopAnim = char?.animate([
      { rotate: `${way * 10}deg`, translate: "0px -3px" }, { rotate: `${way * 10}deg`, translate: "0px -3px", offset: 0.6 },
      { rotate: `${-way * 3}deg`, translate: "0px 0px", offset: 0.88 }, { rotate: "0deg" },
    ], { duration, easing: "ease-in-out" }) || null;
    nameMarkBuddyLimbs(buddy, "glide", duration, 0, way);
    return how;
  }
  if (how === "walk") {
    const dx = fromLeft ? -(x + NMB_W + 12) : innerWidth - x + 12;
    const duration = Math.round(Math.min(1500, 520 + Math.abs(dx) * 1.1));
    nameMarkBuddyWay(buddy, dx > 0 ? "-1" : "1");
    buddy.dataset.turn = dx > 0 ? "l" : "r";
    nameMarkBuddyBlend(buddy, () => buddy.classList.add("nmb-walking"), NMB_BLEND_IN_MS);
    nmbTempo.seen = 0;
    clearTimeout(nmbTempo.timer);
    nmbTempo.timer = setTimeout(nameMarkBuddyTempo, 0);
    //: Faded up over its first third as it comes past the edge: shown by
    //: the class alone, it went from 0 to 0.95 in two frames.
    nmb.anim = buddy.animate([{ translate: `${dx}px 0px`, opacity: 0 }, { opacity: 1, offset: 0.35 }, { translate: "0px 0px", opacity: 1 }], { duration, easing: "cubic-bezier(0.3, 0, 0.25, 1)" });
    const walk = nmb.anim;
    const done = () => {
      if (nmb.anim !== walk) return;
      nameMarkBuddyBlend(buddy, () => buddy.classList.remove("nmb-walking"));
      delete buddy.dataset.turn;
    };
    walk.onfinish = done;
    walk.oncancel = done;
    return how;
  }
  if (how === "fall") {
    //: From just above the window, under gravity (an ease-in), a squash on
    //: landing and one small bounce; Atlas drifts down, slower, swaying.
    const atlas = nameMarkBuddyHasAtlas(buddy);
    const dy = -(y + NMB_H + 16);
    const duration = Math.round(Math.min(atlas ? 1500 : 1000, (atlas ? 700 : 420) + Math.abs(dy) * (atlas ? 1.1 : 0.6)));
    const hit = atlas ? 0.86 : 0.7;
    nmb.anim = buddy.animate(atlas ? [
      { translate: `0px ${dy}px`, easing: "cubic-bezier(0.3, 0.2, 0.4, 1)" },
      { translate: "0px 3px", offset: hit, easing: "ease-in-out" },
      { translate: "0px 0px" },
    ] : [
      { translate: `0px ${dy}px`, easing: "cubic-bezier(0.55, 0, 1, 0.45)" },
      { translate: "0px 0px", offset: hit, easing: "cubic-bezier(0, 0.55, 0.45, 1)" },
      { translate: "0px -9px", offset: 0.83, easing: "cubic-bezier(0.55, 0, 1, 0.45)" },
      { translate: "0px 0px" },
    ], { duration });
    const sway = Math.random() < 0.5 ? -1 : 1;
    nmb.hopAnim = atlas ? char?.animate([
      { rotate: `${sway * 8}deg` }, { rotate: `${-sway * 6}deg`, offset: 0.35 }, { rotate: `${sway * 4}deg`, offset: 0.65 }, { rotate: "0deg" },
    ], { duration, easing: "ease-in-out" }) || null : null;
    nameMarkBuddyLimbs(buddy, atlas ? "float" : "leap", duration, 0, sway);
    return how;
  }
  if (how === "tumble") {
    //: In from the nearer side in a roll, a bounce, and onto its feet.
    const dx = fromLeft ? -(x + NMB_W + 12) : innerWidth - x + 12;
    const way = dx > 0 ? -1 : 1;
    const duration = Math.round(Math.min(1200, 620 + Math.abs(dx) * 0.6));
    nameMarkBuddyWay(buddy, String(way));
    nmb.anim = buddy.animate([
      { translate: `${dx}px -46px`, easing: "cubic-bezier(0.3, 0, 0.7, 1)" },
      { translate: `${Math.round(dx * 0.35)}px 0px`, offset: 0.5, easing: "cubic-bezier(0.2, 0.6, 0.4, 1)" },
      { translate: `${Math.round(dx * 0.12)}px -14px`, offset: 0.72, easing: "cubic-bezier(0.6, 0, 0.8, 0.6)" },
      { translate: "0px 0px" },
    ], { duration });
    nmb.hopAnim = char?.animate([
      { rotate: `${-way * 360}deg`, easing: "cubic-bezier(0.3, 0, 0.5, 1)" }, { rotate: `${-way * 20}deg`, offset: 0.5 },
      { rotate: `${way * 6}deg`, offset: 0.85 }, { rotate: "0deg" },
    ], { duration, easing: "ease-out" }) || null;
    nameMarkBuddyLimbs(buddy, "leap", duration, 0, way);
    return how;
  }
  if (how === "down" || how === "up") {
    //: Down from the top bar, arms first, and a small give at the grip;
    //: up over the bottom bar, a heave and a settle.
    //: **Out from behind the edge, not drawn over it** (the owner,
    //: 2026-09-27, of it coming in "in front of the top bar"): the part of
    //: it still beyond the edge of its own place (above it coming down,
    //: below it coming up) is clipped, so it is seen coming out of the bar
    //: rather than sliding over it. The clip is worked out for each
    //: keyframe's own offset, so it holds still on screen while the figure
    //: moves through it, and ends past the drawing's reach
    //: (`nameMarkBuddyOverhang`), so nothing is cut when it lets go.
    const from = how === "down" ? -Math.round(NMB_H * 0.8) : Math.round(NMB_H * 0.7);
    const duration = 720;
    const over = nameMarkBuddyOverhang();
    const pad = Math.max(over.left, over.right) + 40;
    const clip = (t) => how === "down"
      ? `inset(${-over.top - t}px -${pad}px -${over.bottom + pad}px -${pad}px)`
      : `inset(-${over.top + pad}px -${pad}px ${t - over.bottom}px -${pad}px)`;
    const at = (t, frame) => ({ translate: `0px ${t}px`, clipPath: clip(t), ...frame });
    nmb.anim = buddy.animate([
      at(from, { opacity: 0 }),
      //: Faded up over its first half (INBOX 501): over a third, 216ms,
      //: it read as appearing rather than climbing out.
      at(Math.round(from * 0.35), { opacity: 1, offset: 0.5 }),
      at(how === "down" ? 4 : -5, { offset: 0.78 }),
      at(0, {}),
    ], { duration, easing: "ease-in-out" });
    //: Hand over hand (INBOX 469), until it is out and standing.
    nameMarkBuddyTravel(buddy, "climb", Math.round(duration * 0.78), "");
    return how;
  }
  //: Starlight gathering into it: the stars first, then the figure
  //: resolving out of them and drifting down the last few pixels onto its
  //: perch (the owner: it "came back with barely an entrance"; a fade in
  //: place read as a pop). At its own size throughout: it used to grow from
  //: half size past its own and back (0.5, 1.06, 1).
  nameMarkBuddyBurst(buddy, 0, 0, 0);
  nmb.anim = buddy.animate([{ opacity: 0, translate: "0px -14px" }, { opacity: 0, translate: "0px -14px", offset: 0.18 }, { opacity: 1, offset: 0.6 }, { opacity: 1, translate: "0px 0px" }], { duration: 820, easing: "ease-out" });
  nmb.hopAnim = null;
  nameMarkBuddyLimbs(buddy, "float", 820);
  return how;
}

//: **Out the same way, or dissolving** (INBOX 430): hidden from its menu or
//: by Ctrl+Shift+Y it dematerialises into starlight rather than vanishing.
function nameMarkBuddyLeave(buddy, then) {
  if (!buddy || typeof buddy.animate !== "function") {
    then();
    return;
  }
  //: Less motion is a fade, never a cut.
  if (nameMarkBuddyNoTravel()) {
    buddy.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 260, easing: "ease-in", fill: "forwards" });
    setTimeout(then, 280);
    return;
  }
  const char = buddy.querySelector(".nm-buddy-char");
  nmb.anim?.cancel();
  nameMarkBuddyBurst(buddy, 0, 0, 120);
  char?.animate([{ scale: "1", opacity: 1 }, { scale: "1.05", opacity: 1, offset: 0.25 }, { scale: "0.45", opacity: 0 }], { duration: 380, easing: "ease-in", fill: "forwards" });
  setTimeout(then, 400);
}

//: The window changed size: held panels are followed at once, a pinned
//: place is worked out again for the new size, a place on a bar keeps to
//: the bar, and anything left off screen is brought back inside at once.
//: Whether a better perch exists waits for its own beat.
function nameMarkBuddyRefit() {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || !Number.isFinite(nmb.x) || nmb.visit || buddy.classList.contains("nm-buddy-dragging")) return;
  nameMarkBuddyIndexReset();
  if (nmb.glue) {
    if (!nmb.glue.held) nmb.glue.band = null;
    nameMarkBuddyFollow();
    nameMarkBuddyRefitClear(buddy);
    return;
  }
  if (nmb.pinned) {
    placeNameMarkBuddy(buddy, true);
    return;
  }
  let y = nmb.y;
  const { top, bottom } = nameMarkBuddyLedges();
  if (nmb.perch === "bar" && bottom) y = bottom.top - (nmb.pose === "sit" ? NMB_SEAT : NMB_FEET - 1);
  if (nmb.perch === "hang" && top) y = top.bottom - NMB_GRIP;
  const x = Math.round(Math.min(Math.max(0, nmb.x), innerWidth - NMB_W));
  y = Math.round(Math.min(Math.max(0, y), innerHeight - NMB_H));
  if (x !== nmb.x || y !== nmb.y) {
    const dx = nmb.x - x;
    const dy = nmb.y - y;
    nameMarkBuddyPut(buddy, x, y);
    //: Kept to its bar or inside the window by the way it moves, not moved
    //: under itself (unless far: a poof, as anywhere).
    if (Math.hypot(dx, dy) > NMB_GLIDE_PX && typeof buddy.animate === "function" && !(nmb.anim && nmb.anim.playState === "running")) nameMarkBuddyGo(buddy, dx, dy, nmb.spot || {}, false);
  }
  if (!nameMarkBuddyRefitClear(buddy)) nameMarkBuddyQueuePlace();
}

//: **Reflowed over a control, it moves now** (INBOX 521, perchall.js: the
//: window made narrower, the Library's dock reflowed and it sat on over New
//: document for 1.5s, until its beat). A resize is not a reason to choose
//: again; a control under it is, and nothing along the same edge was free.
function nameMarkBuddyRefitClear(buddy) {
  if (nmb.perch === "yours" || (nmb.glue && (nmb.glue.held || nmb.glue.lost)) || nameMarkBuddyMenuOpen()) return false;
  if (!nameMarkBuddyHits(nmb.x, nmb.y, nmb.pose, nameMarkBuddyObstacles(nameMarkBuddyTab()), nmb.legs)) return false;
  placeNameMarkBuddy(buddy, false, [nmb.x, nmb.y]);
  return true;
}

//: **Called back** (INBOX 426 k, the owner: "the companion just went off
//: the screen and I cant get it back now ... there needs to be some way to
//: reset the position and recall the companion"). From its menu, from
//: Appearance and from the command palette: every place you gave it is
//: forgotten and it comes to the tab's best perch, walking there when it
//: can be seen, arriving there when it could not. With no companion on, it
//: opens the setting that turns one on.
function nameMarkBuddyCallBack() {
  nmb.home = null;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) {
    if (typeof revealFeature === "function") revealFeature("set-companion");
    return;
  }
  nameMarkBuddyKeepSpots({});
  nmb.pinned = false;
  nmb.anim?.cancel();
  nmb.hopAnim?.cancel();
  buddy.style.translate = "";
  buddy.classList.remove("nm-buddy-dragging", "nmb-poofing", "nmb-walking");
  const box = buddy.getBoundingClientRect();
  const seen = !nmb.outOfSight && box.right > 0 && box.left < innerWidth && box.bottom > 0 && box.top < innerHeight;
  nameMarkBuddyIndexReset();
  placeNameMarkBuddy(buddy, !seen);
  //: Out of sight, it comes in the way it would to a tab (`nameMarkBuddyEnter`).
  if (!seen && nmb.spot) nmb.enteredBy = nameMarkBuddyEnter(buddy, nmb.spot);
  nameMarkSay(buddy, "Here I am.");
}

// --- its behaviours -----------------------------------------------------------

const NMB_RECENT_ACTS = 5;
function nameMarkBuddyAct(act, ms) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  const was = nmb.act;
  //: **Back the way it came** (the owner, 2026-09-27: emotes and acts on
  //: a click "must ease back to the prior state, never cut back after a
  //: few seconds"): an act that put a face on (a cheer's grin, a yawn, a
  //: startle, a lie-down's closed eyes) lets it go over 1.8s
  //: (`nmb-easing`), not in the frame its class comes off. The small ones
  //: (a blink, a look) have no face of their own.
  if (was && was !== act && !NMB_FACELESS_ACTS.includes(was)) nameMarkBuddyEase(buddy, 1800);
  if (was) nameMarkBuddyBlend(buddy, () => buddy.classList.remove(`nmb-act-${was}`));
  if (was === "lie" && act !== "lie" && !buddy.classList.contains("nmb-sleep")) nameMarkBuddyGetUp(buddy);
  if (act !== "emerge") buddy.classList.remove("nmb-duck");
  if (was === "turn" || was === "glance") delete buddy.dataset.turn;
  nmb.act = "";
  clearTimeout(nmb.timer);
  clearTimeout(nmb.shyTimer);
  nmb.timer = 0;
  //: Out from behind the panel before anything else.
  if (was === "peek" && act !== "emerge" && !nameMarkBuddyStill()) act = act || "emerge";
  if (was === "peekdown" && act !== "peekback" && !nameMarkBuddyStill()) act = act || "peekback";
  if (NMB_SCENE_ACTS.includes(was)) {
    buddy.classList.add("nmb-unwind");
    clearTimeout(nmb.unwindTimer);
    nmb.unwindTimer = setTimeout(() => buddy.classList.remove("nmb-unwind"), NMB_UNWIND_MS);
  }
  if (!act) {
    nameMarkBuddySchedule();
    return;
  }
  //: **Asleep, lying down if there is room** (the owner: "when it sleeps
  //: can it lay down??"): a nap on a flat place wide enough to lie on is a
  //: lie-down (`lie`, with its pillow and its slow way down and up);
  //: anywhere else it dozes where it is.
  //: A lie-down asked for where there is no room for one is a doze.
  const lieSide = act === "lie" || (act === "nap" && !nameMarkBuddyActOff("lie")) ? nameMarkBuddyLieRoom() : "";
  if (act === "nap" || act === "lie") act = lieSide ? "lie" : "nap";
  const spec = NAME_MARK_BUDDY_ACTS[act];
  if (act === "glance") nameMarkBuddyAim(nmb.pointer);
  if (act === "look" || act === "nap") nameMarkBuddyRelease();
  if (act === "turn" || act === "glance") {
    const lx = act === "glance" && nmb.pointer ? nmb.pointer[0] - nameMarkBuddyHeadAt()[0] : Math.random() - 0.5;
    buddy.dataset.turn = lx < 0 ? "l" : "r";
  }
  //: A class removed and added in one frame does not restart its animation,
  //: so the same act twice in a row (a second cheer) forces one style pass;
  //: any other act does not, since each style pass here is measurable.
  if (act === was) void buddy.offsetWidth;
  if (NMB_SCENE_ACTS.includes(act)) nameMarkBuddyScene(buddy);
  if (act === "lie") nameMarkBuddyLieDown(buddy, lieSide);
  //: **Never the same twice running** (the owner: "also state variations,
  //: not the exact same animation or mood animation each time"). An act
  //: with variants plays one it did not play last time (`data-variant`, the
  //: CSS's), and every act's own animations run a little faster or slower
  //: this time (`nameMarkBuddyVary`, below).
  const variants = NMB_VARIANTS[act] || 0;
  if (variants) {
    const v = nameMarkBuddyPickVariant(variants, nmb.variant?.[act] ?? -1);
    nmb.variant = { ...(nmb.variant || {}), [act]: v };
    buddy.dataset.variant = String(v);
  } else delete buddy.dataset.variant;
  if (act === "tilt") nameMarkBuddyTilt(Math.random() < 0.5 ? -0.7 : 0.7, (ms || spec.ms) - 400);
  //: **Into an act eased, as out of one** (INBOX 619, the owner: "it still
  //: snaps between behaviours and no behaviours"). An act's class takes
  //: over parts whose idle loop was mid-swing, and its first frame put them
  //: at the act's start in one frame; `nameMarkBuddyBlend` hands each such
  //: part over from where it was, in `NMB_BLEND_IN_MS`.
  nameMarkBuddyBlend(buddy, () => buddy.classList.add(`nmb-act-${act}`), NMB_BLEND_IN_MS);
  //: A new act starts with its arms (INBOX 469): a small lift and back.
  if (act !== was && !NMB_FACELESS_ACTS.includes(act) && !NMB_RESTING_ACTS.has(act) && !nameMarkBuddyStill()) nameMarkBuddyLimbs(buddy, "cue", 420);
  nmb.mind?.start(buddy, act, ms || spec?.ms || 1200);
  nmb.act = act;
  nmb.lastAct = act;
  //: The idle pool's memory (Brief 34 step 5, ledger 678 and 679): the last
  //: five acts, so `nameMarkBuddyDecide` does not reach for one of them.
  nmb.recentActs = [act, ...(nmb.recentActs || []).filter((a) => a !== act)].slice(0, NMB_RECENT_ACTS);
  if (NMB_LOUD_ACTS.includes(act)) nameMarkBuddyLoud();
  if (!NMB_RESTING_ACTS.has(act)) nameMarkBuddyVary(buddy, act, ms || spec?.ms || 1200);
  const face = { lie: "sleepy", facepalm: "unimpressed" }[act];
  if (face) nameMarkBuddyExpress(face, spec?.ms || 2000);
  if (spec?.cool) nmb.cool[act] = Date.now() + spec.cool;
  nmb.timer = setTimeout(() => {
    const next = act === "land" && nmb.afterLand ? "look" : nmb.mind?.after(buddy, act) || "";
    if (act === "land") nmb.afterLand = false;
    nameMarkBuddyAct(next);
  }, (ms || spec?.ms || 1200) * (act === "land" ? 1 : 1 + Math.random() * 0.3));
}

//: Room to lie down: standing (not tucked, not peeking) on a flat place,
//: with nothing it must not cover where it would lie, over its lower half.
//: Lying, it reaches past its box on one side (`NMB_LIE_SPAN`, px from its
//: left at size 1, measured: the cap to the soles), and the whole of that
//: must be on its perch (K25, the owner: "it is hanging off the ui element
//: it is perched on"; it lay with only its legs on the board's dock). The
//: side that fits, or either but last time's when both do; "" for none.
//: One obstacle sweep, at the moment it would lie down.
const NMB_LIE_SPAN = { left: [-42, 70], right: [-6, 106] };
function nameMarkBuddyLieRoom() {
  if (nmb.pose !== "stand" || nmb.legs || nmb.visit || !Number.isFinite(nmb.x)) return "";
  const s = Math.max(0.7, nmb.scale || 1);
  const edge = nmb.spot?.edge;
  const lo = Math.max(0, edge?.left ?? 0);
  const hi = Math.min(innerWidth, edge?.right ?? innerWidth);
  const top = nmb.y + NMB_FEET - 36 * s;
  const bottom = nmb.y + NMB_FEET - 2;
  const obstacles = nameMarkBuddyObstacles(nameMarkBuddyTab());
  const sides = Object.keys(NMB_LIE_SPAN).filter((side) => {
    const [a, b] = NMB_LIE_SPAN[side];
    const left = nmb.x + 32 + (a - 32) * s;
    const right = nmb.x + 32 + (b - 32) * s;
    return left >= lo && right <= hi && !obstacles.some((o) => o.right > left && o.left < right && o.bottom > top && o.top < bottom);
  });
  return sides.find((side) => side !== nmb.lieSide) || sides[0] || "";
}

//: How many ways each act can go, and the pick: any but the last one.
const NMB_VARIANTS = { wave: 3, hop: 3, stretch: 2, nap: 3, lie: 2, shrug: 2, facepalm: 2, tilt: 2, read: 2, wiggle: 2, cheer: 2 };
function nameMarkBuddyPickVariant(n, last, roll = Math.random()) {
  if (n <= 1) return 0;
  let i = Math.floor(roll * (n - 1));
  if (last >= 0 && i >= last) i += 1;
  return Math.min(n - 1, i);
}
//: **Three ways to do anything, never the last** (Brief 88 d, the owner:
//: "more atlas variations for each gesture, movement, position, emotion").
//: Over an act's drawn variants (`NMB_VARIANTS`), each play has a manner,
//: any of three but the one this act had last (`data-manner`): brisk (a
//: touch quicker), easy (slower, its weight shifted onto one foot) or
//: full (its own pace, a give at the knees as it starts and a lift
//: after). The shift and the give are added over whatever the act moves
//: (`composite: "add"`) and run from nothing to nothing, so neither can
//: jolt. Both are a `translate`: a `rotate` animation cancels the body's
//: lean (`--nmb-tilt`, eased by a transition), which then went in one
//: frame (jolts.js: 3.2 degrees, the head 5px). Only standing in the
//: open, since a shift would slide a peek out from behind its panel or
//: a seat off its chair. One read of the act's animations as it starts
//: (a style pass, no layout), nothing after.
const NMB_MANNERS = [{ rate: [1.06, 1.16] }, { rate: [0.86, 0.94], shift: 2 }, { rate: [0.96, 1.04], give: 2 }];
function nameMarkBuddyVary(buddy, act = "", ms = 1200) {
  if (typeof buddy.getAnimations !== "function") return;
  const pick = nameMarkBuddyPickVariant(NMB_MANNERS.length, nmb.manner?.[act] ?? -1);
  nmb.manner = { ...(nmb.manner || {}), [act]: pick };
  buddy.dataset.manner = String(pick);
  const manner = NMB_MANNERS[pick];
  const rate = manner.rate[0] + Math.random() * (manner.rate[1] - manner.rate[0]);
  for (const anim of buddy.getAnimations({ subtree: true })) {
    if (typeof CSSAnimation === "function" && anim instanceof CSSAnimation && (anim.currentTime || 0) < 60) anim.playbackRate = rate;
  }
  const char = buddy.querySelector(".nm-buddy-char");
  if (!char || typeof char.animate !== "function" || nameMarkIdleQuiet() || nmb.pose !== "stand" || nmb.legs || NMB_MANNER_STILL.has(act)) return;
  const options = { duration: Math.max(600, ms / rate), easing: "ease-in-out", composite: "add", id: "nmb-manner" };
  if (manner.shift) {
    const x = (Math.random() < 0.5 ? -1 : 1) * manner.shift;
    char.animate([{ translate: "0px 0px" }, { translate: `${x}px 0.5px`, offset: 0.3 }, { translate: `${x}px 0.5px`, offset: 0.75 }, { translate: "0px 0px" }], options);
  }
  if (manner.give) char.animate([{ translate: "0px 0px" }, { translate: `0px ${manner.give}px`, offset: 0.12 }, { translate: "0px -1px", offset: 0.3 }, { translate: "0px 0px", offset: 0.5 }, { translate: "0px 0px" }], options);
}

//: The acts that bring something of their own, and how long getting up
//: out of one takes (the CSS's slow transition, plus the prop's delay).
const NMB_SCENE_ACTS = ["lie", "read", "beanbag", "chair", "facepalm", "shrug"];
//: Where a manner's lean or give would show wrong (see `nameMarkBuddyVary`).
const NMB_MANNER_STILL = new Set(["peek", "peekdown", "peekback", "emerge", "hide", "dangle", "onehand", "swing", "sloth", "meditate", ...NMB_SCENE_ACTS]);
const NMB_UNWIND_MS = 1300;
//: Its props: a still drawing behind it (the beanbag, the chair, the
//: pillow) and one in front (the book), in its 64 by 92 box and scaled
//: with it, made the first time one is needed and kept. Nothing on them
//: animates at rest: they are shown and hidden by opacity and moved in by
//: `translate`, the compositor's.
function nameMarkBuddyScene(buddy) {
  const face = buddy.querySelector(".nm-buddy-face");
  const char = buddy.querySelector(".nm-buddy-char");
  if (!face || !char || face.querySelector(".nmb-scene")) return;
  const ns = "http://www.w3.org/2000/svg";
  const make = (tag, attrs, parent) => {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
    parent?.appendChild(el);
    return el;
  };
  const layer = (where) => {
    const svg = make("svg", { class: `nmb-scene nmb-scene-${where}`, viewBox: "0 0 64 92", width: 64, height: 92, "aria-hidden": "true", focusable: "false" });
    return svg;
  };
  const back = layer("back");
  const bag = make("g", { class: "nms nms-beanbag" }, back);
  make("path", { d: "M6 90 C2 74 14 62 32 62 C50 62 62 74 58 90 Z", fill: "#6c7fb0" }, bag);
  make("path", { d: "M14 72 C20 66 30 65 38 66", fill: "none", stroke: "#8fa0cc", "stroke-width": 2, "stroke-linecap": "round" }, bag);
  const chair = make("g", { class: "nms nms-chair" }, back);
  for (const [x, y, w, h] of [[45, 34, 4, 38], [12, 66, 38, 5], [14, 71, 3, 19], [44, 71, 3, 19]]) {
    make("rect", { x, y, width: w, height: h, rx: 1.5, fill: "#9a6b43" }, chair);
  }
  const pillow = make("g", { class: "nms nms-pillow" }, back);
  make("ellipse", { cx: -8, cy: 86, rx: 18, ry: 5, fill: "#e6e0f2" }, pillow);
  const front = layer("front");
  const book = make("g", { class: "nms nms-book" }, front);
  //: At its hands, turned in to hold it (the CSS), in front of its belly,
  //: not under its chin (K14).
  make("path", { d: "M17 55 L32 58 L47 55 L47 67 L32 70 L17 67 Z", fill: "#b5473a" }, book);
  make("path", { d: "M19 56 L32 59 L45 56 L45 65 L32 68 L19 65 Z", fill: "#fbf6ea" }, book);
  make("path", { d: "M32 59 L32 68", stroke: "#c9bfa6", "stroke-width": 1 }, book);
  face.insertBefore(back, char);
  char.after(front);
}

//: **Looks at a place: a saccade, then the head.** The eyes jump there at
//: once; the head follows 150 to 300ms later on a spring curve, and only as
//: far as a head turns (a dead zone below 0.15, so a small jitter moves
//: nothing). Everything is three custom properties on `#nm-buddy`
//: (`--nmb-ex`, `--nmb-ey` for the eyes, `--nmb-hx` for the head), read by
//: the CSS while `nmb-attend` is on; no frame loop.
function nameMarkBuddyAim(point, near = false) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  let lx = 0;
  let ly = 0;
  if (point) {
    const [cx, cy, size] = nameMarkBuddyHeadAt();
    const dx = point[0] - cx;
    const dy = point[1] - cy;
    const reach = Math.max(160 * size, Math.hypot(dx, dy));
    lx = (dx / reach) * 1.6;
    ly = (dy / reach) * 1.6;
    //: Inside the unit circle, not the square (INBOX 497): clamped on each
    //: axis, a pointer up and to the right put the look at (1, -1), 1.41
    //: times as far as any single direction, and the pupils left the eyes.
    const len = Math.hypot(lx, ly);
    if (len > 1) {
      lx /= len;
      ly /= len;
    }
  }
  //: **Close by, it keeps its eyes on you** (the owner: "atlas doesnt
  //: follow my mouse pointer when it is close. should it??"). Near, the
  //: dead zone is a twentieth, not a sixth, so a pointer moving a little
  //: beside it is still followed, and the head goes with the eyes at once
  //: rather than after a pause: the head's wait restarted with every move,
  //: so while the pointer kept moving it never came. Each change is eased by
  //: the CSS's own transitions, so ten a second reads as one smooth look.
  const dead = near ? 0.05 : 0.15;
  if (Math.abs(lx - nmb.ex) < dead && Math.abs(ly - nmb.ey) < dead) return;
  nmb.ex = lx;
  nmb.ey = ly;
  buddy.style.setProperty("--nmb-ex", lx.toFixed(2));
  buddy.style.setProperty("--nmb-ey", ly.toFixed(2));
  buddy.classList.add("nmb-attend");
  clearTimeout(nmb.headTimer);
  if (near && Date.now() >= nmb.groggyUntil) {
    buddy.style.setProperty("--nmb-hx", (lx * 0.8).toFixed(2));
    return;
  }
  const groggy = Date.now() < nmb.groggyUntil;
  nmb.headTimer = setTimeout(() => {
    buddy.style.setProperty("--nmb-hx", (lx * 0.8).toFixed(2));
  }, (groggy ? 450 : 150) + Math.random() * 150);
}

//: Leans its body `side` (-1 left, 1 right, 0 upright), a few degrees about
//: its feet, for `ms` (0: until told otherwise). One custom property, eased
//: by the CSS; nothing runs between.
function nameMarkBuddyTilt(side, ms = 0) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  const value = Math.max(-1, Math.min(1, side));
  if (Math.abs(value - (nmb.tilt || 0)) < 0.1 && !ms) return;
  nmb.tilt = value;
  buddy.style.setProperty("--nmb-tilt", value.toFixed(2));
  clearTimeout(nmb.tiltTimer);
  if (ms) nmb.tiltTimer = setTimeout(() => nameMarkBuddyTilt(0), ms);
}

//: **Atlas lies down on its nebula and curls up in it** (atlas.js's pose
//: hooks, 08-consistency.css: `data-pose` lie-1, lie-2, lie, curl-1,
//: curl). Its own drawing has these as frames that ease into each other,
//: so a lie-down is played through them, 450ms apart, and getting up plays
//: them back to the pose it had (`nmb.pose`, which stays "stand" or "sit"
//: for every placement rule: only the drawing's attribute changes). Asleep
//: sitting with no room to lie, it curls up. Generated faces keep the
//: prop act's own lie-down (the rotated body and the pillow). With less
//: motion the last frame is set at once.
const NMB_POSE_FRAME_MS = 450;
function nameMarkBuddyHasAtlas(buddy) {
  return !!buddy?.querySelector(".atl-figure-box");
}
function nameMarkBuddyFrames(buddy, frames) {
  for (const t of nmb.poseSteps || []) clearTimeout(t);
  nmb.poseSteps = [];
  if (nameMarkBuddyNoTravel()) {
    buddy.dataset.pose = frames[frames.length - 1];
    return;
  }
  frames.forEach((pose, i) => {
    const set = () => {
      if (buddy.isConnected) buddy.dataset.pose = pose;
    };
    if (!i) set();
    else nmb.poseSteps.push(setTimeout(set, i * NMB_POSE_FRAME_MS));
  });
}
//: Head to the left or the right: the side its perch has room for
//: (`nameMarkBuddyLieRoom`). Atlas's variant 1 reaches left of its box,
//: 0 right; a drawn face lies head left, or head right with `data-lie`.
function nameMarkBuddyLieDown(buddy, side = "left") {
  nmb.lieSide = side;
  if (!nameMarkBuddyHasAtlas(buddy)) {
    if (side === "right") buddy.dataset.lie = "r";
    else delete buddy.dataset.lie;
    return;
  }
  buddy.dataset.atlasVariant = side === "left" ? "1" : "0";
  nameMarkBuddyFrames(buddy, ["lie-1", "lie-2", "lie"]);
}
function nameMarkBuddyCurlUp(buddy) {
  if (!nameMarkBuddyHasAtlas(buddy) || nmb.pose !== "sit" || nmb.legs === "peek") return;
  nameMarkBuddyFrames(buddy, ["curl-1", "curl"]);
}
function nameMarkBuddyGetUp(buddy) {
  const now = buddy.dataset.pose || "";
  if (!/^(lie|curl)/.test(now)) return;
  nameMarkBuddyFrames(buddy, now.startsWith("curl") ? ["curl-1", nmb.pose] : now === "lie-1" ? [nmb.pose] : ["lie-2", "lie-1", nmb.pose].slice(now === "lie-2" ? 1 : 0));
}
//: Its drawing's pose again after a placement set it to `nmb.pose`:
//: carried asleep, it arrives lying or curled, not sitting up.
function nameMarkBuddyKeepFrame(buddy) {
  for (const t of nmb.poseSteps || []) clearTimeout(t);
  nmb.poseSteps = [];
  if (!nameMarkBuddyHasAtlas(buddy)) return;
  if (nmb.act === "lie") buddy.dataset.pose = "lie";
  else if (buddy.classList.contains("nmb-sleep") && nmb.pose === "sit" && nmb.legs !== "peek") buddy.dataset.pose = "curl";
}

//: Stops whatever it is doing, at once and without a follow-on: grabbed.
function nameMarkBuddyHalt(buddy) {
  if (nmb.act) buddy.classList.remove(`nmb-act-${nmb.act}`);
  nmb.act = "";
  nmb.afterLand = false;
  clearTimeout(nmb.timer);
  clearTimeout(nmb.shyTimer);
  nmb.timer = nmb.shyTimer = 0;
  buddy.classList.remove("nmb-walking", "nmb-poofing", "nmb-sleep", "nmb-drowsy", "nmb-duck", "nmb-stir");
  //: Picked up lying or curled: upright at once in the hand.
  for (const t of nmb.poseSteps || []) clearTimeout(t);
  nmb.poseSteps = [];
  if (/^(lie|curl)/.test(buddy.dataset.pose || "")) buddy.dataset.pose = nmb.pose;
  delete buddy.dataset.turn;
  if (buddy.dataset.legs === "peek") buddy.dataset.legs = nmb.legs = "";
}

//: Lets its attention go: eyes and head drift back to rest.
function nameMarkBuddyRelease() {
  const buddy = document.getElementById("nm-buddy");
  clearTimeout(nmb.releaseTimer);
  nmb.releaseTimer = 0;
  nmb.target = null;
  nmb.ex = nmb.ey = 0;
  nmb.leanSide = "";
  if (!buddy) return;
  buddy.classList.remove("nmb-attend");
  buddy.style.setProperty("--nmb-ex", "0");
  buddy.style.setProperty("--nmb-ey", "0");
  buddy.style.setProperty("--nmb-hx", "0");
  nmb.leanState = 0;
  nmb.leanSmooth = 0;
  if (!nmb.act || nmb.act !== "tilt") nameMarkBuddyTilt(0);
  if (!buddy.classList.contains("nmb-walking") && nmb.act !== "turn") delete buddy.dataset.turn;
}

function nameMarkBuddySchedule() {
  clearTimeout(nmb.timer);
  nmb.timer = 0;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || document.hidden || nameMarkBuddyStill() || buddy.classList.contains("nmb-sleep")) return;
  //: Calm (the owner: "fewer, longer, calmer behaviours at rest"):
  //: something every 20 to 60 seconds; between them it breathes and blinks
  //: on the compositor and nothing runs here. **In its large view, every 2.5
  //: to 6 seconds** (INBOX 443, the owner: "needs more life and not just a
  //: statue"): it is being watched, and that is the place for it to play.
  //: Its mind (companion-menu.js, `NMB_MIND.nextIn`) places the wait in that range.
  nmb.timer = setTimeout(nameMarkBuddyTick, nmb.visit ? 2500 + Math.random() * 3500 : nmb.mind?.nextIn() || 20000 + Math.random() * 40000);
}

//: The weighted pick: every behaviour that suits where it is and is off
//: its cooldown, weighted by the moment. No layout is read here: the pose,
//: the perch and the times are all kept in `nmb`.
function nameMarkBuddyDecide(now = Date.now(), hour = new Date().getHours()) {
  const idle = now - nmb.lastInput;
  const night = hour >= 22 || hour < 6;
  const reading = nmb.reading || {};
  const byMood = NAME_MARK_BUDDY_MOODS[reading.mood] || {};
  const byKind = NAME_MARK_BUDDY_KINDS[reading.animal] || {};
  const actions = nameMarkBuddyActions();
  const off = nameMarkBuddyActivitiesOff();
  //: The calm budget (below): a sudden or large act at most once a minute
  //: or so, and none while you type or scroll.
  //: Watched in its large view, the calm budget and Fewer do not hold it
  //: back (Off still does, and every switch in What it does).
  const calm = !!nmb.visit || nameMarkBuddyCalmAllows(now, nmb.loudAt || 0, nmb.loudGap || NMB_LOUD_GAP_MS, nmb.keyAt || 0, nameMarkBuddyScrollAgo());
  //: Which Atlas it is, for its stances (none for any other companion).
  nmb.atlasLook = document.querySelector("#nm-buddy svg.atl-layer")?.dataset.atlasLook || "";
  //: What you are doing (`NMB_MIND.drive`, companion-menu.js), once loaded.
  const drive = nmb.mind?.drive(now, idle) || {};
  const pool = [];
  let total = 0;
  for (const [act, spec] of Object.entries(NAME_MARK_BUDDY_ACTS)) {
    if (!spec.poses.includes(nmb.pose)) continue;
    if (spec.legs === "out" && nmb.legs) continue;
    //: Tucked behind the bottom bar, only what its eyes can do.
    if (nmb.legs === "peek" && !["blink", "look", "glance", "yawn", "nap"].includes(act)) continue;
    if (spec.edge && (nmb.edgeType !== spec.edge || nmb.visit)) continue;
    //: In the large view there is no bar to peek down from.
    if (nmb.visit && act === "peekdown") continue;
    if ((nmb.cool[act] || 0) > now || act === nmb.lastAct) continue;
    if (nameMarkBuddyActOff(act, off)) continue;
    if (!calm && NMB_LOUD_ACTS.includes(act)) continue;
    let w = spec.w;
    if (act === "yawn") w = idle > NMB_YAWN_MS ? 4 : night ? 2 : 0;
    if (act === "nap") w = idle > 90 * 1000 ? 3 : night ? 1 : 0;
    if (act === "glance" && !nmb.pointer) w = 0;
    w *= (byMood[act] || 1) * (byKind[act] || 1);
    //: Its own slow mood: energy, curiosity and sociability (0 to 1).
    const { energy, curiosity, sociability } = nmb.mood;
    if (["hop", "kick", "dangle", "wave", "stretch", "swing", "onehand", "feet"].includes(act)) w *= 0.4 + energy;
    if (["yawn", "nap", "sloth", "lie", "beanbag"].includes(act)) w *= 1.6 - energy;
    //: A nap lying down wants you away a while, or the night.
    if (act === "lie" && idle < 60 * 1000 && !night) w = 0;
    if (["look", "glance", "peek", "peekdown", "scratch", "read"].includes(act)) w *= 0.5 + curiosity;
    if (["wave", "glance"].includes(act)) w *= 0.4 + sociability;
    if (["peek", "peekdown", "turn"].includes(act)) w *= 1.4 - sociability;
    if (now < nmb.grumpyUntil && ["wave", "glance", "hop", "cheer"].includes(act)) w = 0;
    const warm = nameMarkBuddyWarmthAt(nmb.feel, now);
    if (["wave", "hop", "tilt", "shrug", "read", "glance"].includes(act)) w *= Math.max(0.2, 1 + warm * 0.8);
    if (["peek", "peekdown"].includes(act)) w *= Math.max(0.2, 1 - warm * 0.5);
    //: Ignored for twenty minutes while you are busy: it tries for your
    //: attention with a wave.
    if (act === "wave" && now - nmb.lastPoke > 20 * 60 * 1000 && idle < 30000) w *= 4;
    if (night && ["hop", "wave", "kick"].includes(act)) w *= 0.5;
    if (act === "hop" && nmb.onBoard) w *= NMB_BOARD_WANDER / 0.35;
    if (now - nmb.lastCheer < 60000 && ["hop", "wave", "kick", "dangle"].includes(act)) w *= 2;
    if (now - nmb.lastPoke < 20000 && ["glance", "wave", "look"].includes(act)) w *= 2;
    //: A stance is Atlas's, in the look it was drawn for.
    const stance = NMB_STANCES[act];
    if (stance && (!nmb.atlasLook || nmb.atlasLook !== stance.look)) w = 0;
    if (spec.atlas && !nmb.atlasLook) w = 0;
    if (!NMB_QUIET_ACTS.includes(act)) w *= { off: 0, fewer: nmb.visit ? 1 : 0.33, normal: 1 }[actions] ?? 0.33;
    w *= drive[act] ?? 1;
    if (w > 0) {
      pool.push([act, w]);
      total += w;
    }
  }
  //: **Never one of the last five** while anything else suits the moment
  //: (the owner: "more varied"): a weighted pick alone repeated a heavy act
  //: two or three times a minute. Only when every suitable act is recent
  //: does the plain pick stand.
  const recent = nmb.recentActs || [];
  const fresh = pool.filter(([act]) => !recent.includes(act));
  if (fresh.length && fresh.length < pool.length) {
    pool.length = 0;
    pool.push(...fresh);
    total = fresh.reduce((sum, [, w]) => sum + w, 0);
  }
  let roll = Math.random() * total;
  for (const [act, w] of pool) {
    roll -= w;
    if (roll <= 0) return act;
  }
  return pool.length ? pool[pool.length - 1][0] : "blink";
}

//: The one timer: every few seconds, one decision, and a check that its
//: perch is still clear.
function nameMarkBuddyTick() {
  nmb.timer = 0;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || document.hidden || nameMarkBuddyStill()) return;
  //: Away with the tab it lives on: nothing to act out, nobody to see it.
  if (nmb.away) {
    nameMarkBuddySchedule();
    return;
  }
  const locked = document.getElementById("lock-overlay") && !document.getElementById("lock-overlay").classList.contains("hidden");
  if (locked || nameMarkBuddyMenuOpen() || buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-walking") || buddy.classList.contains("nmb-think")) {
    nameMarkBuddySchedule();
    return;
  }
  nameMarkBuddyCheck();
  const idle = Date.now() - nmb.lastInput;
  nameMarkBuddyContext(buddy);
  nmb.onBoard = nameMarkBuddyOnBoard();
  const awake = Date.now() < (nmb.awakeUntil || 0);
  if (idle > NMB_SLEEP_MS && !awake) {
    //: An act under way ends as it drops off (the owner, 2026-10-11, the
    //: large view: a wave played on under the Zs, a pose stuck half way).
    if (nmb.act && !NMB_RESTING_ACTS.has(nmb.act)) nameMarkBuddyAct("");
    //: Drifting off over seconds, not snapping shut.
    if (!buddy.classList.contains("nmb-sleep")) nameMarkBuddyEase(buddy, 3200);
    buddy.classList.remove("nmb-drowsy");
    if (!buddy.classList.contains("nmb-sleep") && nmb.act !== "lie" && !nameMarkBuddyActOff("lie") && nameMarkBuddyLieRoom()) nameMarkBuddyAct("lie", 20 * 60 * 1000);
    buddy.classList.add("nmb-sleep");
    if (nmb.act !== "lie") nameMarkBuddyCurlUp(buddy);
    nameMarkBuddyHold("sleepy");
    nameMarkBuddyRelease();
    return;
  }
  buddy.classList.toggle("nmb-drowsy", idle > NMB_DROWSY_MS && !awake);
  //: Bored of this perch: a few steps over, or a wander and back.
  if (nameMarkBuddyWander(Date.now())) {
    nameMarkBuddySchedule();
    return;
  }
  if (!buddy.classList.contains("nmb-think")) nameMarkBuddyHold(idle > NMB_DROWSY_MS ? "sleepy" : "");
  const hour = new Date().getHours();
  const night = hour >= 22 || hour < 6;
  //: The mood moves every tick, a yawn's included: it used to be worked out
  //: after the yawn's early return, so a tick that yawned skipped it and a
  //: night of yawns kept the day's energy (review, round 6).
  const energyTarget = (night ? 0.3 : 0.75) - Math.min(0.3, idle / (20 * 60 * 1000));
  const drift = (value, toward) => value + (toward - value) * 0.1;
  nmb.mood.energy = drift(nmb.mood.energy, energyTarget);
  nmb.mood.curiosity = drift(nmb.mood.curiosity, 0.6);
  nmb.mood.sociability = drift(nmb.mood.sociability, 0.7);
  //: At night it yawns now and then, whatever you are doing (once in half
  //: an hour at most, `NMB_REACTIONS.yawn`). The yawn is this tick's act and
  //: its face, so it takes the place of the drift and the pick, not the mood.
  if (night && nameMarkBuddyReact("yawn")) return;
  if (Math.random() < 0.35) nameMarkBuddyDrift();
  //: **Its arms do not hang the whole time it stays** (the owner,
  //: 2026-10-10: "atlas's arm movements on both versions ... are basically
  //: permanently in a downward arc except for when hanging"). Atlas's
  //: three ways to hold its arms per mood (`data-atlas-variant`) changed
  //: only with a new perch, so a settled Atlas held one for as long as it
  //: stayed. Now and then a tick takes another, and the rig eases the arms
  //: there with its springs.
  else if (!nmb.act && nameMarkBuddyHasAtlas(buddy) && !/^(lie|curl)/.test(buddy.dataset.pose || "") && Math.random() < 0.45) {
    buddy.dataset.atlasVariant = String(nameMarkBuddyPickVariant(3, Number(buddy.dataset.atlasVariant ?? -1)));
  }
  //: Its mind is fetched at the first tick; once here it may lead into a big act on a beat (`NMB_MIND.lead`).
  if (!nmb.mind) ensureModule("companionMenu");
  const act = nameMarkBuddyDecide();
  if (!nmb.mind?.lead(buddy, act)) nameMarkBuddyAct(act);
}

//: **Its face changes with what is happening** (INBOX 426 x, the owner:
//: "one expression only ... wants more behaviour and slight expression
//: changes"). A face drawn from a name has one mood; the companion's own
//: face now passes through others and comes back: glad when you say hello
//: (laughing on the third poke), put out when poked too often, excited at a
//: saved note or an answer, surprised by a bell or an error, intent while
//: an answer is being written, heavy-lidded when you have been away, and
//: now and then, at rest, a neighbouring look for a few seconds (a happy
//: face going calm and back). Each is a face picture swapped in whole (the
//: pictures are cached, `nameMarkCompose`), never an animation, so it costs
//: nothing between changes. Atlas has its own moods (atlas.js) and only
//: gets the drift, and only when it is calm. `nmb.exprHold` is the one it
//: comes back to (sleepy while you are away, intent while it thinks).
const NMB_EXPR_NEAR = {
  happy: ["calm", "love", "cute"], calm: ["happy", "sly", "cute"], excited: ["happy", "starstruck"],
  sad: ["calm", "nervous"], angry: ["unimpressed", "serious"], serious: ["calm", "unimpressed"],
  sly: ["calm", "evil", "cool"], cool: ["sly", "calm"], nervous: ["calm", "confused"], sleepy: ["calm"],
  love: ["happy", "cute"], laughing: ["happy", "excited"], unimpressed: ["serious", "sly"],
  confused: ["calm", "nervous"], cute: ["happy", "uwu"], uwu: ["cute", "happy"], starstruck: ["excited", "happy"],
  "": ["happy", "calm", "sly"],
};
const NMB_ATLAS_NEAR = ["curious", "happy", "proud", "shy"];
function nameMarkBuddyExpress(expr, ms = 0, { drift = false } = {}) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nameMarkBuddyStill()) return;
  const seed = buddy.dataset.seed || "";
  if (isAtlasSeed(seed)) {
    if (drift && typeof setAtlasMood === "function" && typeof atlasMoodNow !== "undefined" && atlasMoodNow === "calm") setAtlasMood(expr, ms, { quiet: true });
    return;
  }
  if (characterRendererFor(seed)) return;
  clearTimeout(nmb.exprTimer);
  const want = NAME_MARK_FACES[expr] ? expr : "";
  //: **Back down gradually** (the owner: it "will change expressions for a
  //: sec then instantly go back ... it needs to be more natural and
  //: gradual"): a big face comes down through a smaller one for a while
  //: before its own, and every change is a crossfade.
  const softer = NMB_EXPR_SOFTEN[want];
  nmb.exprTimer = ms
    ? setTimeout(() => (softer && softer !== (nmb.exprHold || "") ? nameMarkBuddyExpress(softer, 2400) : nameMarkBuddyExpress(nmb.exprHold || "")), ms)
    : 0;
  if ((nmb.expr || "") === want) return;
  const char = buddy.querySelector(".nm-buddy-char");
  const old = char?.querySelector(".nm-figure:not(.nmb-fig-leaving)");
  if (!char) return;
  nmb.expr = want;
  const next = nameCharacterFigure(seed, want);
  //: An emote with a face that has one (a lingering one, not a drift).
  const emote = ms && !drift ? NMB_EXPR_EMOTE[want] : "";
  if (emote) nameMarkBuddyEmote(emote);
  if (ms && !drift && ["happy", "excited", "laughing"].includes(want)) nameMarkBuddyJoy(buddy);
  if (old && typeof next.animate === "function" && !nameMarkBuddyNoTravel()) {
    //: The new face over the old, faded in; the old goes when it is covered.
    old.classList.add("nmb-fig-leaving");
    old.after(next);
    next.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 280, easing: "ease-in-out" }).finished.then(() => old.remove(), () => old.remove());
  } else if (old) old.replaceWith(next);
  else char.prepend(next);
  buddy.dataset.expr = want;
  //: The mood its arms take (the CSS's `data-feel`): this face, or its own.
  buddy.dataset.feel = want || nmb.reading?.mood || "";
  nmbTempo.seen = 0;
}
//: Its faces drawn ahead, one per idle moment: a face drawn the first time
//: is a 57ms task (drawn, cut up, turned into pictures), which would be a
//: stall at the very moment it reacts; drawn in idle time, a swap is a
//: cached picture (0.3ms).
//: **Glad, a different way each time**: a bounce, a sway or a little
//: spin, never the one it did last, a beat after the face changes (60 to
//: 220ms, so it reads as a reaction) and a touch bigger or smaller.
function nameMarkBuddyJoy(buddy) {
  const char = buddy.querySelector(".nm-buddy-char");
  if (!char || typeof char.animate !== "function" || nameMarkBuddyNoTravel() || nmb.act || buddy.classList.contains("nmb-walking")) return;
  if (!nameMarkBuddyCalmAllows(Date.now(), nmb.loudAt || 0, nmb.loudGap || NMB_LOUD_GAP_MS, nmb.keyAt || 0, nameMarkBuddyScrollAgo())) return;
  nameMarkBuddyLoud();
  const v = nameMarkBuddyPickVariant(3, nmb.variant?.joy ?? -1);
  nmb.variant = { ...(nmb.variant || {}), joy: v };
  const amp = 0.8 + Math.random() * 0.4;
  const delay = 60 + Math.random() * 160;
  const frames = [
    [{ translate: "0 0" }, { translate: `0 ${-8 * amp}px`, offset: 0.25 }, { translate: "0 0", offset: 0.5 }, { translate: `0 ${-5 * amp}px`, offset: 0.72 }, { translate: "0 0" }],
    [{ rotate: "0deg" }, { rotate: `${6 * amp}deg`, offset: 0.3 }, { rotate: `${-6 * amp}deg`, offset: 0.7 }, { rotate: "0deg" }],
    [{ transform: "rotateY(0deg)" }, { transform: "rotateY(180deg) translateY(-6px)", offset: 0.5 }, { transform: "rotateY(360deg)" }],
  ][v];
  char.animate(frames, { duration: Math.round((v === 2 ? 700 : 900) * (0.87 + Math.random() * 0.28)), delay, easing: "ease-in-out" });
}

//: The smaller face a big one eases down through, and the emote each
//: lingering face brings.
const NMB_EXPR_SOFTEN = { laughing: "happy", excited: "happy", starstruck: "happy", surprised: "calm", angry: "unimpressed" };
const NMB_EXPR_EMOTE = { confused: "q", happy: "spark", excited: "spark", laughing: "spark", love: "spark", starstruck: "spark", nervous: "sweat" };
const NMB_EXPR_EVENTS = ["happy", "laughing", "excited", "surprised", "serious", "sleepy", "unimpressed", "love", "dizzy"];
function nameMarkBuddyPrewarm(seed) {
  if (!seed || isAtlasSeed(seed) || characterRendererFor(seed)) return;
  const near = NMB_EXPR_NEAR[nameMood(seed).mood || ""] || NMB_EXPR_NEAR[""];
  const queue = [...new Set([...NMB_EXPR_EVENTS, ...near])];
  const idle = typeof requestIdleCallback === "function" ? (fn) => requestIdleCallback(fn, { timeout: 4000 }) : (fn) => setTimeout(fn, 200);
  const next = () => {
    if (!queue.length || document.getElementById("nm-buddy")?.dataset.seed !== seed) return;
    nameCharacterFigure(seed, queue.shift());
    idle(next);
  };
  idle(next);
}

function nameMarkBuddyHold(expr) {
  if ((nmb.exprHold || "") === expr) return;
  nmb.exprHold = expr;
  if (!nmb.exprTimer) nameMarkBuddyExpress(expr);
}
function nameMarkBuddyDrift() {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nmb.exprTimer || nmb.exprHold) return;
  const seed = buddy.dataset.seed || "";
  const ms = 5000 + Math.random() * 5000;
  if (isAtlasSeed(seed)) {
    nameMarkBuddyExpress(NMB_ATLAS_NEAR[Math.floor(Math.random() * NMB_ATLAS_NEAR.length)], ms, { drift: true });
    return;
  }
  const near = NMB_EXPR_NEAR[nmb.reading?.mood || ""] || NMB_EXPR_NEAR[""];
  nameMarkBuddyExpress(near[Math.floor(Math.random() * near.length)], ms);
}

//: **What it notices in the app** (round 5: "more contextual reactions that
//: tie into real app events", "subtle and never intrusive"). Each is a real
//: event, each has its own cooldown and none comes within 6s of another, and
//: none runs under Reduce motion, Avatar animation Off, a hidden page, while
//: it is carried, asleep or its menu is open:
//:   read     a long note opened (Show more, or the phone's note page): it
//:            puts its reading glasses on and follows along for a while;
//:   graph    the graph laid out again: it peeks over at it;
//:   streak   the capture streak grew (the dashboard's count): one cheer;
//:   yawn     at night, now and then: a yawn;
//:   private  a private note opened: it covers its eyes;
//:   toast    something new said in a toast: it looks towards it.
//: Called from the page's own events (`nameMarkBuddyNoticeApp` below) and
//: from one line in dashboard.js (`nameMarkBuddyStreak`).
const NMB_REACTIONS = {
  read: { cool: 3 * 60 * 1000, ms: 7000 },
  graph: { cool: 60 * 1000, ms: 2600 },
  streak: { cool: 20 * 60 * 60 * 1000, ms: 1300 },
  yawn: { cool: 30 * 60 * 1000, ms: 2200 },
  private: { cool: 45 * 1000, ms: 2400 },
  toast: { cool: 8000, ms: 2000 },
};
const NMB_REACT_GAP = 6000;
function nameMarkBuddyReact(kind, target = null) {
  const buddy = document.getElementById("nm-buddy");
  const spec = NMB_REACTIONS[kind];
  if (!buddy || !spec || nameMarkBuddyStill() || document.hidden || nameMarkBuddyMenuOpen()) return false;
  if (buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-sleep")) return false;
  const now = Date.now();
  nmb.reactCool = nmb.reactCool || {};
  if ((nmb.reactCool[kind] || 0) > now || now - (nmb.reactAt || 0) < NMB_REACT_GAP) return false;
  nmb.reactCool[kind] = now + spec.cool;
  nmb.reactAt = now;
  nmb.reacted = kind;
  const look = () => {
    const box = target?.isConnected ? target.getBoundingClientRect() : null;
    if (box && box.width) nameMarkBuddyAim([box.left + box.width / 2, box.top + Math.min(box.height / 2, 120)]);
  };
  if (kind === "toast") {
    look();
    clearTimeout(nmb.releaseTimer);
    nmb.releaseTimer = setTimeout(nameMarkBuddyRelease, spec.ms);
  } else if (kind === "read") {
    look();
    buddy.classList.add("nmb-reading");
    nameMarkBuddyExpress("serious", spec.ms);
    clearTimeout(nmb.readTimer);
    nmb.readTimer = setTimeout(() => {
      buddy.classList.remove("nmb-reading");
      nameMarkBuddyRelease();
    }, spec.ms);
  } else if (kind === "graph") {
    look();
    const side = target?.isConnected && target.getBoundingClientRect().left + target.getBoundingClientRect().width / 2 < nmb.x + NMB_W / 2 ? "l" : "r";
    buddy.dataset.turn = side;
    nameMarkBuddyExpress("surprised", 900);
    nameMarkBuddyAct(NAME_MARK_BUDDY_ACTS.peek.poses.includes(nmb.pose) && nmb.edgeType === "top" ? "look" : "glance", spec.ms);
  } else if (kind === "streak") {
    nameMarkBuddyExpress("excited", 2400);
    nameMarkBuddyAct("cheer");
  } else if (kind === "yawn") {
    nameMarkBuddyExpress("sleepy", spec.ms);
    nameMarkBuddyAct("yawn");
  } else if (kind === "private") {
    nameMarkBuddyAct("hide", spec.ms);
  }
  return true;
}

//: The capture streak, from the dashboard each time it counts: a cheer the
//: first time it is seen longer than before (kept on this computer), never
//: for the count the page merely loads with.
function nameMarkBuddyStreak(days) {
  if (!(days >= 2)) return;
  let seen = 0;
  try {
    seen = Number(prefs.get("nm-buddy-streak", null)) || 0;
    prefs.set("nm-buddy-streak", String(days));
  } catch (e) {
    return;
  }
  if (seen && days > seen) nameMarkBuddyReact("streak");
}

//: The page's own events, watched here rather than hooked into each
//: surface: a note opened (by its Show more, its row in the rows view, or
//: the phone's note page), the graph's layout changed.
function nameMarkBuddyNoteOpened(id) {
  const entry = typeof allEntries !== "undefined" ? allEntries.find((e) => String(e.id) === String(id)) : null;
  if (!entry) return;
  const row = document.querySelector(`.note-page-list li[data-id="${CSS.escape(String(id))}"], li[data-id="${CSS.escape(String(id))}"]`);
  if (entry.is_private) nameMarkBuddyReact("private", row);
  else if (String(entry.content || "").length > 1200) nameMarkBuddyReact("read", row);
}
function nameMarkBuddyNoteOpen(id) {
  const inSet = (set) => set && (set.has(id) || set.has(Number(id)) || set.has(String(id)));
  return (typeof expandedNotes !== "undefined" && inSet(expandedNotes)) || (typeof expandedRows !== "undefined" && inSet(expandedRows))
    || (typeof notePageOpenId !== "undefined" && String(notePageOpenId) === String(id));
}
document.addEventListener("click", (event) => {
  if (!document.getElementById("nm-buddy")) return;
  const li = event.target.closest?.("li[data-id]");
  if (!li || event.target.closest("#nm-buddy")) return;
  const id = li.dataset.id;
  const was = nameMarkBuddyNoteOpen(id);
  //: After the page's own handler has opened it (or not).
  setTimeout(() => {
    if (!was && nameMarkBuddyNoteOpen(id)) nameMarkBuddyNoteOpened(id);
  }, 0);
}, true);
document.addEventListener("change", (event) => {
  if (event.target?.closest?.("#graph-layout")) {
    setTimeout(() => nameMarkBuddyReact("graph", document.querySelector("#tab-graph svg, #tab-graph canvas")), 400);
  }
});

//: The app's own events, for the companion to react to: `think` while a
//: chat turn runs, `cheer` when a note is saved or an answer lands,
//: `startle` when one fails.
function nameMarkBuddyCue(cue, from = "") {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  buddy.classList.toggle("nmb-think", cue === "think");
  nameMarkBuddyHold(cue === "think" ? "serious" : buddy.classList.contains("nmb-drowsy") ? "sleepy" : "");
  //: A long answer: after a few seconds of thinking it puts on its reading
  //: glasses and follows along until the answer lands.
  clearTimeout(nmb.readTimer);
  if (cue === "think" && NMB_PROPS_DRAWN) {
    nmb.readTimer = setTimeout(() => {
      buddy.classList.add("nmb-reading");
      if (nameMarkBuddyChatErrand()) nmb.readingErrand = true;
    }, 4000);
  } else {
    buddy.classList.remove("nmb-reading");
    if (nmb.readingErrand) {
      nmb.readingErrand = false;
      clearTimeout(nmb.errandTimer);
      nmb.errandTimer = setTimeout(() => placeNameMarkBuddy(undefined, false, [nmb.x, nmb.y]), 4000);
    }
  }
  if (cue === "cheer" || cue === "carry") nmb.lastCheer = Date.now();
  if ((cue === "bell" || cue === "lantern") && !NMB_PROPS_DRAWN) return;
  if (cue === "think" || cue === "rest" || nameMarkBuddyStill() || document.hidden) return;
  //: **A start only for a real error, and rarely** (the owner: "atlas
  //: startles a lot and it's kinda distracting ... because I navigate
  //: through the notebook so fast"): only an error toast may startle it,
  //: and at most once in two minutes; Atlas's own surprised face does not.
  if (cue === "startle" && (from !== "error" || Date.now() - nmb.startledAt < 120000)) return;
  //: **Reactions wait a moment** and the latest wins: an event is acted on
  //: 1.5s after it, unless another has come since, so a burst of them
  //: (moving fast through the notebook) is one reaction or none.
  clearTimeout(nmb.cueTimer);
  nmb.cueTimer = setTimeout(() => {
    nmb.cueTimer = 0;
    if (!buddy.isConnected || nameMarkBuddyStill() || document.hidden || buddy.classList.contains("nm-buddy-dragging")) return;
    //: **Asleep, the app's news keeps** (the owner: "make sure that random
    //: sudden movements dont happen too frequently or randomly"): a saved
    //: note or an answer used to pull it upright mid-sleep. Only a
    //: reminder's bell wakes it, and gently.
    if (nameMarkBuddyAsleep(buddy)) {
      if (cue === "bell") nameMarkBuddyWake(true);
      return;
    }
    if (cue === "startle") nmb.startledAt = Date.now();
    buddy.classList.remove("nmb-drowsy");
    const face = { cheer: ["excited", 2400], carry: ["happy", 2400], startle: ["surprised", 1600], bell: ["surprised", 1200], wave: ["happy", 2000], nod: ["happy", 2000], shrug: ["confused", 2400] }[cue];
    if (face) nameMarkBuddyExpress(face[0], face[1]);
    if (cue === "bell" && nameMarkBuddyBellErrand()) return;
    const calm = cue === "bell" || nameMarkBuddyCalmAllows(Date.now(), nmb.loudAt || 0, nmb.loudGap || NMB_LOUD_GAP_MS, nmb.keyAt || 0, nameMarkBuddyScrollAgo());
    if (NAME_MARK_BUDDY_ACTS[cue] && (calm || !NMB_LOUD_ACTS.includes(cue))) nameMarkBuddyAct(cue);
  }, 1500);
}

// --- what the app's AI is doing -----------------------------------------------
//: **It does what Atlas is doing** (INBOX 443, the owner: "the companion
//: doesnt change action for related actions when things are happening like
//: for the tag and file with atlas note function running with atlas reading
//: the note"). A note card said "Atlas is reading…" while the companion
//: stood idle beside it.
//:
//: **One hook, not a call in every feature**: every model call the app
//: makes goes out through `fetch`, so this watches `fetch` once and knows
//: the work by its address (`NMB_WORK`). A new model feature joins by a row
//: here, not by a line in its own file. The request itself is untouched:
//: the same call, the same promise, the same response; for a streamed
//: answer the body is handed on chunk by chunk as it is read, so the end of
//: the stream (or its cancel, or its error) is seen without reading it twice.
//: A note being filed is seen on the save's own answer (`filing_state:
//: "pending"`) and on the filing poll's (`/entries/<id>/filing`), whose
//: last answer says how it went.
//:
//: While work runs it reads (glasses on, and its book out where it stands or
//: sits: re-evaluate, Tag with Atlas, the tag offer, OCR, filing) or thinks
//: (the dots: chat, Ask, Improve writing, a draft); a caption is a look. When
//: the last piece ends it nods, pleased, or holds up the note it filed; a
//: failure is a puzzled face and a shrug. Atlas wears the same mood on every
//: Atlas the app draws. Under Reduce motion, Avatar animation Off or a
//: hidden companion it does nothing (the cue and act gates below).
const NMB_WORK = [
  ["POST", /^\/entries\/[^/]+\/reevaluate$/, "read"],
  ["POST", /^\/entries\/suggest-tags$/, "read"],
  ["POST", /^\/entries\/improve$/, "think"],
  ["POST", /^\/(?:media|files)\/[^/]+\/(?:ocr|vision-ocr|ocr-range-read|ocr-page-read|region-read)$/, "read"],
  ["POST", /^\/(?:media|files)\/[^/]+\/(?:caption|page-caption)$/, "look"],
  ["POST", /^\/(?:chat|help\/ask|drafts\/compose)\/stream$/, "think", "stream"],
];
const nmbWork = new Map();
let nmbWorkSeq = 0;
function nameMarkBuddyWorkFor(method, path) {
  for (const [m, pattern, kind, how] of NMB_WORK) if (m === method && pattern.test(path)) return { kind, how: how || "" };
  return null;
}
function nameMarkBuddyWork(id, kind, phase) {
  if (phase === "start") nmbWork.set(id, kind);
  else if (!nmbWork.delete(id)) return;
  const buddy = document.getElementById("nm-buddy");
  const atlas = !!buddy && isAtlasSeed(buddy.dataset.seed || "");
  if (nmbWork.size) {
    const kinds = new Set(nmbWork.values());
    if (atlas && typeof setAtlasMood === "function") setAtlasMood("thinking", 0, { quiet: true });
    if (!buddy) return;
    if (kinds.has("think")) nameMarkBuddyCue("think");
    if (kinds.has("read") || kinds.has("file")) {
      buddy.classList.add("nmb-reading");
      nameMarkBuddyHold("serious");
      //: Its book out, for as long as the reading takes (ended below).
      if (!nmb.workAct && !nmb.act && !nmb.visit && !nameMarkBuddyStill() && !nameMarkBuddyAsleep(buddy)
        && NAME_MARK_BUDDY_ACTS.read.poses.includes(nmb.pose) && !nameMarkBuddyActOff("read")) {
        nameMarkBuddyAct("read", 10 * 60 * 1000);
        nmb.workAct = "read";
      }
    } else if (kinds.has("look") && !nmb.act) nameMarkBuddyAct("look");
    return;
  }
  //: The last piece of work ended: back from reading, then a reaction.
  if (atlas && typeof setAtlasMood === "function") setAtlasMood(phase === "done" ? "happy" : phase === "failed" ? "confused" : "calm", 4000, { quiet: true });
  if (!buddy) return;
  //: "rest" takes the thinking dots, the glasses and a reading errand off
  //: and gives its face back (`nameMarkBuddyCue`).
  nameMarkBuddyCue("rest");
  if (nmb.workAct && nmb.act === nmb.workAct) nameMarkBuddyAct("");
  nmb.workAct = "";
  if (phase === "done") nameMarkBuddyCue(kind === "file" ? "carry" : "nod");
  else if (phase === "failed") nameMarkBuddyCue("shrug");
}
if (typeof window.fetch === "function") {
  const send = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    let path = "";
    try {
      path = new URL(url, location.href).pathname;
    } catch (e) {
      return send(input, init);
    }
    const method = String(init?.method || input?.method || "GET").toUpperCase();
    const filing = method === "GET" && /^\/entries\/[^/]+\/filing$/.test(path);
    const saving = method === "POST" && path === "/entries";
    const work = filing || saving ? null : nameMarkBuddyWorkFor(method, path);
    if (!work && !filing && !saving) return send(input, init);
    const id = work ? `w${(nmbWorkSeq += 1)}` : "";
    if (work) nameMarkBuddyWork(id, work.kind, "start");
    return send(input, init).then((response) => {
      if (filing || saving) {
        //: The filing's state, from its own answer (a copy of it: the app
        //: reads the original).
        if (response.ok) {
          response.clone().json().then((data) => {
            const entryId = filing ? path.split("/")[2] : data?.id;
            const state = data?.filing_state;
            if (state === "pending") nameMarkBuddyWork(`f${entryId}`, "file", "start");
            else if (state) nameMarkBuddyWork(`f${entryId}`, "file", state === "failed" || data?.filed_by === "none" ? "failed" : "done");
          }, () => {});
        }
        return response;
      }
      if (!response.ok) {
        nameMarkBuddyWork(id, work.kind, "failed");
        return response;
      }
      if (work.how !== "stream" || !response.body || typeof ReadableStream !== "function") {
        nameMarkBuddyWork(id, work.kind, "done");
        return response;
      }
      //: The stream handed on as it is read: its end, error or cancel is
      //: the work's end. The app's own reader sees the same chunks.
      const reader = response.body.getReader();
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const { done, value } = await reader.read();
            if (done) {
              controller.close();
              nameMarkBuddyWork(id, work.kind, "done");
            } else controller.enqueue(value);
          } catch (error) {
            nameMarkBuddyWork(id, work.kind, error?.name === "AbortError" ? "stopped" : "failed");
            controller.error(error);
          }
        },
        cancel(reason) {
          nameMarkBuddyWork(id, work.kind, "stopped");
          return reader.cancel(reason);
        },
      });
      Object.defineProperty(response, "body", { value: body });
      return response;
    }, (error) => {
      if (work) nameMarkBuddyWork(id, work.kind, error?.name === "AbortError" ? "stopped" : "failed");
      throw error;
    });
  };
}

//: Input keeps the idle clock at zero; a click is also something it may
//: notice, if it is near.
for (const type of ["pointerdown", "keydown"]) {
  document.addEventListener(type, (event) => {
    nameMarkBuddyAwake();
    if (type === "pointerdown" && !event.target?.closest?.("#nm-buddy")) nameMarkBuddyNotice(event.clientX, event.clientY, Date.now(), "click");
  }, { passive: true, capture: true });
}

//: Any input starts the idle clock again and lifts drowsiness. It does not
//: wake a sleeper: only something close and sudden might
//: (`nameMarkBuddyStir`), or being picked up or poked.
function nameMarkBuddyAwake() {
  const now = Date.now();
  const away = now - nmb.lastInput;
  nmb.lastInput = now;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  buddy.classList.remove("nmb-drowsy");
  if (buddy.classList.contains("nmb-sleep")) return;
  if (nmb.exprHold === "sleepy") nameMarkBuddyHold("");
  //: **You are back** (INBOX 426 x: "wave at the user after a long idle"):
  //: after three minutes or more with nothing from you, awake, it waves.
  if (away > NMB_DROWSY_MS && !nameMarkBuddyStill() && !document.hidden && !nmb.act && nameMarkBuddyCalmAllows(now, nmb.loudAt || 0, nmb.loudGap || NMB_LOUD_GAP_MS, 0, nameMarkBuddyScrollAgo())) {
    nameMarkBuddyExpress("happy", 2200);
    nameMarkBuddyAct("wave");
  }
}

//: **How it takes what you do: onset, hold, decay** (the owner: "the on
//: hover move of atlas doesnt really do anything and if I click it, it will
//: change expressions for a sec then instantly go back to doing what it was
//: doing like sleeping, it needs to be more natural and gradual, unless it
//: is startled or smth. it has moods and needs organic interactions"). The
//: choices are these pure functions, so each transition is tested on its own
//: (tests/test_companion_motion.py); the doing is in the handlers, and every
//: face they put on comes down gradually (`nameMarkBuddyExpress`).
//:
//: Warmth (-1 to 1) is what you have been to it lately: a pet or a hello
//: raises it, being poked too often lowers it, and it relaxes towards 0 with
//: a half-life of four minutes, read when needed (no timer). A warm
//: companion picks friendlier acts; a cold one hides more.
const NMB_WARMTH_HALF_MS = 4 * 60 * 1000;
function nameMarkBuddyWarmthAt(feel, now) {
  if (!feel) return 0;
  return feel.v * Math.pow(0.5, Math.max(0, now - feel.at) / NMB_WARMTH_HALF_MS);
}
function nameMarkBuddyFeel(delta, now = Date.now()) {
  nmb.feel = { v: Math.max(-1, Math.min(1, nameMarkBuddyWarmthAt(nmb.feel, now) + delta)), at: now };
}
//: A click (the owner, 2026-09-27: "when atlas is sleeping and i click it,
//: it opens its eyes and mouth for a sec like it is startled but then
//: falls back asleep a second later making it feel like the sleep is fake
//: ... maybe a pout or getting a temporarily a little mad if it happens
//: multiple times consecutively"). Asleep, it always wakes slowly, never
//: with a start; poked again while still waking (`groggy`, the first 10s),
//: it pouts.
//:
//: **Awake, a poke is one of six answers, never the same twice running**
//: (INBOX 705, the owner: "they get annoyed every time I tap them multiple
//: times, can they alternate how they respond a little more"). It used to
//: climb: hello, play, play, then grumpy at the fourth poke in twenty
//: seconds, so anyone tapping a few times met the sulk every time. Now a
//: first poke picks among the gentle three; from the second, from all six
//: (pleased, playful, curious, a wave, a spin, a laugh); and annoyed is a
//: rare answer, only from the fifth poke inside twenty seconds, then one
//: time in four, and never straight after it. The poke count decays by
//: itself (`nmb.pokes` keeps twenty seconds), so after a pause it is a
//: hello again. `last` is the previous answer, `rand` the draw (a function,
//: so a test fixes it).
const NMB_POKE_GENTLE = ["pleased", "curious", "wave"];
const NMB_POKE_POOL = ["pleased", "playful", "curious", "wave", "spin", "laugh"];
function nameMarkBuddyClickReaction(asleep, pokes, sinceLast, groggy = false, last = "", rand = Math.random) {
  if (asleep) return "wake";
  if (groggy && pokes < 3) return "pout";
  if (pokes >= 5 && last !== "grumpy" && rand() < 0.25) return "grumpy";
  const pool = (pokes >= 2 ? NMB_POKE_POOL : NMB_POKE_GENTLE).filter((how) => how !== last);
  return pool[Math.min(pool.length - 1, Math.floor(rand() * pool.length))];
}

//: **The calm budget** (the owner: "make sure that random sudden movements
//: dont happen too frequently or randomly. it cant be distracting for the
//: user"). A sudden or large act (`NMB_LOUD_ACTS`) that you did not ask for
//: plays at most once in `gap` (60 to 90s, drawn each time), and never
//: within 4s of a key typed in a field or 2s of a scroll. Pure, for the
//: tests; `nameMarkBuddyLoud` stamps it.
function nameMarkBuddyCalmAllows(now, loudAt, gap, keyAt, scrollAgoMs) {
  if (now - loudAt < gap) return false;
  if (now - keyAt < 4000) return false;
  return !(scrollAgoMs < 2000);
}
function nameMarkBuddyLoud() {
  nmb.loudAt = Date.now();
  nmb.loudGap = 60000 + Math.random() * 30000;
}
function nameMarkBuddyScrollAgo() {
  return nmbFollow.scrollAt ? performance.now() - nmbFollow.scrollAt : Infinity;
}
//: Asleep: its own sleep, or a nap or a lie-down.
function nameMarkBuddyAsleep(buddy) {
  return !!buddy && (buddy.classList.contains("nmb-sleep") || nmb.act === "nap" || nmb.act === "lie");
}
//: Its face eased for `ms` (the CSS's `nmb-easing`: eyes, lids and mouth
//: cross over 1.8s), so a wake or a doze is seen happening.
//: **Let go of a move, never drop it** (INBOX 497, the owner: "make the
//: atlas behaviour more smooth and less sudden beginning and stopping of
//: actions"). An act's or a walk's motion is a CSS animation keyed on a
//: class; taking the class off mid-way put every part back at rest in one
//: frame (companionblend.js: 7 to 22px in a frame, against at most 4px a
//: frame while the act ran), and a CSS transition cannot ease it, because a
//: value an animation drove never starts one. So before `change` takes a
//: class off, the parts it moves are read where they are; afterwards each
//: animation that went is replaced by a short one from there back to rest
//: (an implicit end keyframe: the rest the CSS now gives), eased in and
//: out, so it neither lurches off nor stops dead. Only
//: when something was moving, and never under reduced motion, where the
//: change is made as it was.
//: `buddy` may be a list of roots, and `ms` a longer hand-over: Atlas's
//: mood loops (a giggle, a hop, a wag) going back to its idle use both
//: (atlas.js, `setAtlasMood`, INBOX 600: "it might sway or do something for
//: a couple seconds but will then snap still").
const NMB_BLEND_MS = 480;
//: Into an act: shorter, so a quick one (a hop, 800ms) still reads as itself.
const NMB_BLEND_IN_MS = 300;
const NMB_BLEND_PROPS = ["transform", "translate", "rotate", "scale", "opacity"];
const NMB_BLEND_PARTS = ".nm-buddy-char, .nm-buddy-head, .nm-figure, .nmb-leg-l, .nmb-leg-r, :is(.nmb-arm-l, .nmb-arm-r):not(.atl-rigged, .atl-arm-probe)";
function nameMarkBuddyBlend(buddy, change, ms = NMB_BLEND_MS) {
  const roots = (Array.isArray(buddy) ? buddy : [buddy]).filter((el) => el && typeof el.getAnimations === "function");
  if (!roots.length || nameMarkIdleQuiet()) {
    change();
    return;
  }
  const held = [];
  for (const anim of roots.flatMap((el) => el.getAnimations({ subtree: true }))) {
    //: Running, or held by the pacer (`nameMarkBuddyTempo` pauses what
    //: animates inside a drawing and steps it by hand).
    if (!(typeof CSSAnimation === "function" && anim instanceof CSSAnimation) || anim.playState === "finished" || anim.playState === "idle") continue;
    const el = anim.effect && anim.effect.target;
    if (!el) continue;
    const props = new Set();
    for (const frame of anim.effect.getKeyframes()) for (const key of Object.keys(frame)) if (NMB_BLEND_PROPS.includes(key)) props.add(key);
    if (!props.size) continue;
    const style = getComputedStyle(el);
    const from = {};
    for (const key of props) from[key] = style[key];
    //: And the point it turns about (INBOX 669): an act that turns the
    //: body about its own point (hanging by one hand turns 16 degrees about
    //: the hand, `nmb-act-onehand`) took that point away with its class,
    //: and the turn eased back about the new one, 44px off in the large
    //: view, in one frame (atlas669-clicks.js, a poke cutting it short).
    if (props.has("rotate") || props.has("transform")) from.transformOrigin = style.transformOrigin;
    held.push({ anim, el, from });
  }
  //: **And the body's held pose** (INBOX 669, the owner: "when I click
  //: atlas, it often starts tilting to the left then just snaps back").
  //: An act that leans the body by a plain rule (a facepalm tips it 3
  //: degrees, a read, a shrug, a seat) also stops its idle bob while it
  //: lasts; at its end the bob's animation came back and covered the rule's
  //: transition, so the lean went in one frame (atlas669-clicks.js: the
  //: head 9px in a frame). The body's box is read before and after; if it
  //: moved and nothing above eased it, it is eased from where it was.
  //: **And its limbs, as a move starts** (the owner, 2026-10-11: "make
  //: sure no jolts to start or stop various movemements"). A walk's own
  //: loops begin where their keyframes do, not where the body is: the
  //: back leg's step starts half a beat in, folded to 0.7 of its length,
  //: and the bob's lean turns the body 3 degrees, all in one frame
  //: (jolts.js: a leg 5.5px, the head 4.8px). Legs, the head, the figure
  //: and the drawn arms are read too; Atlas's rigged arms ease on their
  //: own springs and are left to them.
  const BODY = ["transform", "rotate", "translate", "transformOrigin"];
  const bodies = roots.flatMap((el) => (el.id === "nm-buddy" ? [...el.querySelectorAll(NMB_BLEND_PARTS)] : [])).map((el) => {
    const style = getComputedStyle(el);
    return { el, from: Object.fromEntries(BODY.map((key) => [key, style[key]])) };
  });
  change();
  for (const { anim, el, from } of held) {
    if (el.getAnimations().includes(anim)) continue;
    //: Only what moved (the body's note below says why).
    const style = getComputedStyle(el);
    const moved = Object.fromEntries(Object.keys(from).filter((key) => style[key] !== from[key]).map((key) => [key, from[key]]));
    if (!Object.keys(moved).length) continue;
    //: `offset: 0`: a lone keyframe with none is the end, not the start.
    el.animate([{ ...moved, offset: 0 }], { duration: ms, easing: "cubic-bezier(0.4, 0, 0.2, 1)", id: "nmb-blend" });
  }
  //: A part eased above is read again, not passed over: what that loop
  //: eased now reads as it was, and anything else it moved is eased here
  //: (jolts.js: a move out of a landing eased the landing's squash and
  //: left the walk's lean, 3.2 degrees, to go in a frame).
  for (const { el, from } of bodies) {
    const style = getComputedStyle(el);
    //: Only what moved: a key held at its old value that the next act
    //: animates from the same value (a hang's turn starting at 0) was
    //: pinned there for the whole blend and then jumped (atlas669-blendcheck.js).
    const moved = Object.fromEntries(BODY.filter((key) => style[key] !== from[key]).map((key) => [key, from[key]]));
    if (!Object.keys(moved).length) continue;
    el.animate([{ ...moved, offset: 0 }], { duration: ms, easing: "cubic-bezier(0.4, 0, 0.2, 1)", id: "nmb-blend" });
  }
}

function nameMarkBuddyEase(buddy, ms) {
  const until = Date.now() + ms;
  //: A longer ease already running (a wake's) is not cut short.
  if (until <= (nmb.easeUntil || 0) && buddy.classList.contains("nmb-easing")) return;
  nmb.easeUntil = until;
  buddy.classList.add("nmb-easing");
  clearTimeout(nmb.easeTimer);
  nmb.easeTimer = setTimeout(() => buddy.classList.remove("nmb-easing"), ms);
}
//: Sleepy-annoyed: a pout and a small huff for `ms`, then its face eases
//: back. Generated faces wear their own unimpressed face.
function nameMarkBuddyPout(buddy, ms) {
  nameMarkBuddyEase(buddy, ms + 2400);
  buddy.classList.add("nmb-pout");
  nameMarkBuddyExpress("unimpressed", ms);
  clearTimeout(nmb.poutTimer);
  nmb.poutTimer = setTimeout(() => buddy.classList.remove("nmb-pout"), ms);
}
//: The pointer resting on it, by how long: awake, it brightens at once
//: (unless it is sulking or you have been unkind); asleep, it stirs, and
//: after 1.8s of you staying it wakes.
function nameMarkBuddyHoverReaction(asleep, dwellMs, warmth, grumpy) {
  if (asleep) return dwellMs >= 1800 ? "wake" : "stir";
  if (grumpy || warmth < -0.3) return "none";
  return "brighten";
}
//: Bored of a perch: how long it has been on it, over four minutes, less
//: for a tired or unsociable companion and for a shy or sleepy face.
const NMB_BORED_MS = 4 * 60 * 1000;
function nameMarkBuddyBoredom(msOnPerch, energy, sociability, mood) {
  let b = (msOnPerch / NMB_BORED_MS) * (0.4 + energy) * (0.6 + sociability * 0.6);
  if (["nervous", "sad", "sleepy", "uwu"].includes(mood)) b *= 0.6;
  return b;
}

//: **Bored of one spot** (the owner: "maybe it might get bored of one
//: specific spot and move a little over or wander off then come back"). At
//: its tick, bored enough, and one time in three: a few steps along the
//: same edge, or off to a nearby perch for half a minute and back (on foot,
//: or by a poof if far: `nameMarkBuddyGo`). Never while you type or read
//: near it, never pinned, on an errand or with its menu open, never with
//: Reduce actions off, and never when switched off (What it does).
function nameMarkBuddyWander(now) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nmb.pinned || nmb.away || nmb.visit || nmb.perch === "errand" || nmb.act || nameMarkBuddyMenuOpen()) return false;
  if (nameMarkBuddyActions() === "off" || nameMarkBuddyActOff("wander")) return false;
  if (now - (nmb.keyAt || 0) < 20000 || nmb.readingErrand) return false;
  const near = nmb.pointer && Math.hypot(nmb.pointer[0] - (nmb.x + NMB_W / 2), nmb.pointer[1] - (nmb.y + NMB_H / 2)) < 260;
  if (near && now - nmb.lastInput < 20000) return false;
  //: Back from a wander after half a minute: home again, if still free.
  if (nmb.home && now - nmb.home.at > 30000) {
    const home = nmb.home;
    nmb.home = null;
    const tab = nameMarkBuddyTab();
    nameMarkBuddyIndexReset();
    if (home.tab === tab && !nameMarkBuddyHits(home.x, home.y, home.pose, nameMarkBuddyObstacles(tab), home.legs)) {
      nmb.moveWhy = "back from a wander";
      nameMarkBuddyMoveTo(buddy, home);
      return true;
    }
  }
  if (nmb.home) return false;
  //: Off somewhere is a large move: within the calm budget.
  if (!nameMarkBuddyCalmAllows(now, nmb.loudAt || 0, nmb.loudGap || NMB_LOUD_GAP_MS, nmb.keyAt || 0, nameMarkBuddyScrollAgo())) return false;
  const { energy, sociability } = nmb.mood;
  //: Rarer on an open board (INBOX 1300 C20, the owner: "the companion
  //: jumping around my whiteboard a lot was a little annoying").
  if (nameMarkBuddyBoredom(now - (nmb.perchAt || now), energy, sociability, nmb.reading?.mood || "") < 1 || Math.random() > (nmb.onBoard ? NMB_BOARD_WANDER : 0.35)) return false;
  const tab = nameMarkBuddyTab();
  nameMarkBuddyIndexReset();
  const obstacles = nameMarkBuddyObstacles(tab);
  const spot = nmb.spot || {};
  if (Math.random() < 0.65) {
    //: A few steps over, along the same edge, staying on what it stands on.
    const size = NMB_W * Math.max(0.7, nmb.scale || 1);
    const dx = (Math.random() < 0.5 ? -1 : 1) * Math.round(size * (0.4 + Math.random() * 0.5));
    const x = Math.round(nmb.x + dx);
    const on = spot.anchor?.isConnected ? spot.anchor.getBoundingClientRect() : null;
    const inside = x >= 0 && x <= innerWidth - NMB_W && (!on || (x + NMB_W / 2 > on.left && x + NMB_W / 2 < on.right));
    if (inside && !nameMarkBuddyHits(x, nmb.y, nmb.pose, obstacles, nmb.legs)) {
      nmb.moveWhy = "bored: a few steps over";
      nameMarkBuddyMoveTo(buddy, { ...spot, x, y: nmb.y, pose: nmb.pose, legs: nmb.legs });
      return true;
    }
  }
  //: Somewhere a few of its own widths off, towards the middle of the
  //: window: asked near where it is, its own perch won every time.
  const off = NMB_W * Math.max(0.7, nmb.scale || 1) * 4 * (nmb.x > innerWidth / 2 ? -1 : 1);
  const away = nameMarkBuddyChoose(tab, obstacles, [nmb.x + off, nmb.y], 4);
  if (!away || (Math.abs(away.x - nmb.x) < 24 && Math.abs(away.y - nmb.y) < 24)) return false;
  nmb.home = { ...spot, x: nmb.x, y: nmb.y, pose: nmb.pose, legs: nmb.legs, tab, at: now };
  nmb.moveWhy = "bored: wandering off";
  nameMarkBuddyMoveTo(buddy, away);
  return true;
}

//: Woken: slowly (a yawn, then a stretch, then a look at you) unless
//: startled, and awake for the next 45s at least: drowsiness comes back only
//: after that, never at once.
const NMB_AWAKE_MS = 45000;
function nameMarkBuddyWake(gently = false, startled = false) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  const slept = gently || buddy.classList.contains("nmb-sleep") || nmb.act === "nap";
  //: Awake now, so its next quiet spell starts from here.
  if (gently) nmb.lastInput = Date.now();
  nmb.awakeUntil = Date.now() + NMB_AWAKE_MS;
  //: Its eyes open over seconds (`nmb-easing`), not in a frame.
  if (slept) nameMarkBuddyEase(buddy, 7000);
  buddy.classList.remove("nmb-sleep", "nmb-drowsy");
  if (slept) nameMarkBuddyGetUp(buddy);
  //: Atlas's face is its own mood (atlas.js): woken here, it wakes there
  //: too, slowly. A click on the companion lands on its face's box, not
  //: on `.nm-atlas`, so atlas.js's own poke never saw it, and the
  //: companion stood up with its eyes still shut (atlassleepinput.js).
  if (slept && nameMarkBuddyHasAtlas(buddy) && typeof atlasWake === "function") atlasWake();
  if (!slept) return;
  //: Groggy for a few seconds: slower to look, heavier lids.
  nmb.groggyUntil = Date.now() + 5000;
  nmb.wokeAt = Date.now();
  nmb.exprHold = "";
  buddy.classList.add("nmb-groggy");
  setTimeout(() => buddy.classList.remove("nmb-groggy"), 5000);
  if (nameMarkBuddyStill() || document.hidden) return;
  if (startled) {
    nameMarkBuddyExpress("surprised", 1400);
    nameMarkBuddyAct("startle");
    return;
  }
  nameMarkBuddyExpress("sleepy", 4200);
  nameMarkBuddyAct("yawn", 1700);
  for (const t of nmb.wakeSteps || []) clearTimeout(t);
  nmb.wakeSteps = [
    setTimeout(() => nameMarkBuddyAct("wake"), 1800),
    setTimeout(() => nmb.pointer && nameMarkBuddyAim(nmb.pointer), 3300),
  ];
}

//: **Stirred in its sleep** by a fast flick or a click close by: most of the
//: time an ear twitch and a mumble, and back to sleep; sometimes it wakes.
function nameMarkBuddyStir() {
  const now = Date.now();
  if (now - nmb.stirAt < 4000) return;
  nmb.stirAt = now;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  //: Never woken by it (the owner: "whenever I click near the companion
  //: when it is sleeping, not even on it just near it, it startles for
  //: about a second then goes instantly back to sleep"): a twitch, its eyes
  //: staying shut. Only a click on it, a pet or a pointer kept close wakes
  //: it.
  buddy.classList.add("nmb-stir");
  setTimeout(() => buddy.classList.remove("nmb-stir"), 700);
}

//: **Attention, not pointer-follow** (the owner: "if the companion is
//: sleeping they dont move with every mouse movement ... so their body isnt
//: constantly twitching ... like realistic npcs"). Called at most ten times
//: a second from the pointer, and on a click. Asleep, it only notices
//: something fast or a click within 120px (and then may only stir). Drowsy,
//: only the sudden. Awake, it notices the pointer within 220px, or
//: anything fast or clicked within 300 to 400px; it picks a look target and
//: holds it, choosing again only when the pointer has gone 80px from it
//: (and not sooner than about 0.7s, slower when groggy) or something
//: louder happens. Out of range for a moment, it lets go. A target held
//: well to one side for 1.5s turns its body that way.
const NMB_EYES_NEAR = 160;
//: Where its head is drawn, and how big it is drawn: its perch on the page,
//: or the box it takes in its large view (`nameMarkBuddyVisit`), where the
//: perch's numbers are a page it is not on.
function nameMarkBuddyHeadAt() {
  if (nmb.visit) {
    const box = document.querySelector("#nm-buddy .nm-buddy-face")?.getBoundingClientRect();
    if (box?.width) {
      const k = box.height / NMB_H;
      return [box.left + box.width / 2, box.top + (NMB_HEAD / 2) * k, k];
    }
  }
  return [nmb.x + NMB_W / 2, nmb.y + NMB_HEAD / 2 + (nmb.pose === "hang" ? NMB_DROP : 0), Math.max(0.7, nmb.scale || 1)];
}
function nameMarkBuddyNotice(x, y, now, salient = "") {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nameMarkBuddyStill() || document.hidden || buddy.classList.contains("nm-buddy-dragging")) return;
  const [cx, cy, size] = nameMarkBuddyHeadAt();
  const dist = Math.hypot(x - cx, y - cy);
  const last = nmb.lastMove;
  const speed = last && now > last[2] ? (Math.hypot(x - last[0], y - last[1]) / (now - last[2])) * 1000 : 0;
  nmb.lastMove = [x, y, now];
  if (buddy.classList.contains("nmb-sleep") || nmb.act === "nap" || nmb.act === "lie") {
    if ((speed > 2500 && dist < 120) || (salient === "click" && dist < 120)) nameMarkBuddyStir();
    //: **Woken gently by you coming close** (the owner: a close pointer
    //: "wakes a dozing companion gently: a blink, a stretch, then it looks at
    //: you"): the pointer kept within 100px for 0.7s, it wakes (groggy, a
    //: stretch, `nameMarkBuddyWake`) and a moment later looks your way.
    if (dist < 100 && document.documentElement.dataset.avatarFollow !== "off") {
      if (!nmb.nearSince) nmb.nearSince = now;
      else if (now - nmb.nearSince > 700) {
        nmb.nearSince = 0;
        if (nmb.act === "lie") nameMarkBuddyAct("");
        nameMarkBuddyWake(true);
        setTimeout(() => nmb.pointer && nameMarkBuddyAim(nmb.pointer), 1400);
      }
    } else nmb.nearSince = 0;
    return;
  }
  nmb.nearSince = 0;
  const loud = (speed > 1800 && dist < 400) || (salient && dist < 300);
  if (buddy.classList.contains("nmb-drowsy") && !loud) return;
  //: **Its eyes on the pointer, as Appearance says** (round 5): with Faces
  //: follow the pointer off, a pointer merely passing is not followed (a
  //: click or something sudden still catches its eye). Near it (160px),
  //: its eyes stay on the pointer as it moves rather than holding a look.
  const follows = document.documentElement.dataset.avatarFollow !== "off";
  if (!follows && !loud) {
    if (buddy.classList.contains("nmb-attend") && !nmb.releaseTimer) nmb.releaseTimer = setTimeout(nameMarkBuddyRelease, 800);
    return;
  }
  //: Its reach grows with it: a Large companion notices you from further,
  //: and in its large view it watches the whole card.
  const reach = size;
  const near = follows && dist < NMB_EYES_NEAR * reach;
  if (dist > 220 * reach && !loud) {
    if (buddy.classList.contains("nmb-attend") && !nmb.releaseTimer) nmb.releaseTimer = setTimeout(nameMarkBuddyRelease, 1200 + Math.random() * 1200);
    return;
  }
  clearTimeout(nmb.releaseTimer);
  nmb.releaseTimer = 0;
  if (nmb.grumpyUntil > now) return;
  const t = nmb.target;
  const wait = (now < nmb.groggyUntil ? 1500 : 700) * (0.75 + Math.random() * 0.5);
  if (!loud && !near && t && (Math.hypot(x - t[0], y - t[1]) < 80 || now - nmb.targetAt < wait)) return;
  nmb.target = [x, y];
  nmb.targetAt = now;
  nameMarkBuddyAim([x, y], near);
  nameMarkBuddyLean(nmb.ex, now, speed);
}

//: **Leaning toward you, steadily** (the owner: "sometimes the companion
//: leans or tilts to the left and right a bit back and forth too fast
//: because of my mouse movement"). The gaze was the lean: every pass of
//: the pointer flipped it. Now the gaze is smoothed first (about 250ms),
//: the lean is a side it is on (in past 0.7, out only under 0.3, nothing in
//: between), it keeps a side at least 1.3s before it may change, a flick of
//: the pointer (over 1500px a second) moves nothing, and the lean itself
//: eases over 400ms (the CSS). Held 1.5s, the head turns that way too.
function nameMarkBuddyLeanSide(state, smooth, heldMs) {
  const want = smooth > 0.7 ? 1 : smooth < -0.7 ? -1 : Math.abs(smooth) < 0.3 ? 0 : state;
  if (want !== state && heldMs < 1300) return state;
  return want;
}
function nameMarkBuddyLean(ex, now, speed = 0) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  const dt = Math.min(1000, Math.max(0, now - (nmb.leanSmoothAt || now)));
  nmb.leanSmoothAt = now;
  nmb.leanSmooth = (nmb.leanSmooth || 0) + (ex - (nmb.leanSmooth || 0)) * (1 - Math.exp(-dt / 250));
  //: The pointer stops sending moves when it stops: looked at again a
  //: moment later until the smoothed gaze has caught up, so a pointer that
  //: flicked over and stayed is leaned to.
  clearTimeout(nmb.leanTimer);
  if (speed > 1500 || Math.abs(ex - nmb.leanSmooth) > 0.05) nmb.leanTimer = setTimeout(() => nameMarkBuddyLean(nmb.ex, Date.now(), 0), 150);
  if (speed > 1500) return;
  const was = nmb.leanState || 0;
  const side = nameMarkBuddyLeanSide(was, nmb.leanSmooth, now - (nmb.leanChangedAt || 0));
  if (side !== was) {
    nmb.leanState = side;
    nmb.leanChangedAt = now;
    //: Atlas leans with its own drawing (the CSS's `data-lean`: the body
    //: a few degrees about its feet, the face sliding that way, the tail
    //: and nebula lagging); anything else tips its whole figure.
    if (nameMarkBuddyHasAtlas(buddy)) {
      if (side) buddy.dataset.lean = side < 0 ? "l" : "r";
      else delete buddy.dataset.lean;
    } else if (nmb.act !== "tilt") nameMarkBuddyTilt(side * 0.6);
    if (!side && !buddy.classList.contains("nmb-walking") && nmb.act !== "turn") delete buddy.dataset.turn;
  } else if (side && now - nmb.leanChangedAt > 1500 && !buddy.classList.contains("nmb-walking")) {
    buddy.dataset.turn = side < 0 ? "l" : "r";
  }
}

//: A scroll counts as being here, at most once a second.
document.addEventListener("scroll", () => {
  if (Date.now() - nmb.lastInput > 1000) nameMarkBuddyAwake();
}, { passive: true, capture: true });

// --- errands ------------------------------------------------------------------------
//: **Things it does with a purpose** (the owner: "atlas and the companions
//: need better ai and behaviour and abilities"), each rare, calm and tied to
//: what the app is doing. A reminder falling due: it goes to the Reminders
//: tab's button (or the notifications bell), hangs by it, looks at it and
//: holds up its bell, then goes back. A chat answer being written while the
//: chat is open: it sits on the composer's edge and reads along, and goes
//: back when the answer has landed. A saved note: it holds up a tiny note.
//: Something new on screen (a toast): it looks at it. None of them moves a
//: companion you put somewhere in the last thirty seconds.
function nameMarkBuddyErrand(spot, act, forMs, look) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nmb.pinned || nmb.visit || nameMarkBuddyStill() || document.hidden || buddy.classList.contains("nm-buddy-dragging") || nameMarkBuddyMenuOpen()) return false;
  if (Date.now() - (nmb.placedAt || 0) < 30000) return false;
  const obstacles = nameMarkBuddyObstacles(nameMarkBuddyTab());
  const free = nameMarkBuddyHits(spot.x, spot.y, spot.pose, obstacles, spot.legs) ? nameMarkBuddyStepAside({ ...spot }, obstacles) : spot;
  if (nameMarkBuddyHits(free.x, free.y, free.pose, obstacles, free.legs)) return false;
  clearTimeout(nmb.errandTimer);
  nameMarkBuddyMoveTo(buddy, { kind: "errand", ...free });
  const arrive = nmb.anim && nmb.anim.playState === "running" ? nmb.anim.finished.catch(() => null) : Promise.resolve();
  arrive.then(() => {
    if (look) nameMarkBuddyAim(look);
    if (act) nameMarkBuddyAct(act);
  });
  if (forMs) nmb.errandTimer = setTimeout(() => placeNameMarkBuddy(undefined, false, [nmb.x, nmb.y]), forMs);
  return true;
}

function nameMarkBuddyBellErrand() {
  const target = document.querySelector("#tab-bar button[data-tab='reminders']") || document.getElementById("notif-btn");
  const box = target && nameMarkBuddyShown(target);
  const { top } = nameMarkBuddyLedges();
  if (!box || !top) return false;
  const cx = box.left + box.width / 2;
  const x = Math.min(Math.max(NMB_GUTTER, cx - NMB_W / 2 + 40), innerWidth - NMB_W - NMB_GUTTER);
  return nameMarkBuddyErrand({ pose: "hang", legs: "", x, y: top.bottom - NMB_GRIP }, "bell", 14000, [cx, box.top + box.height / 2]);
}

function nameMarkBuddyChatErrand() {
  if (nameMarkBuddyTab() !== "chat") return false;
  const input = document.getElementById("chat-input");
  const dock = input?.closest(".chat-dock") || input?.closest("form, .chat-composer, .card") || input;
  const box = dock && nameMarkBuddyShown(dock);
  if (!box) return false;
  //: **A clean place on the dock's top edge** (INBOX 443): it was a fixed
  //: x 72px in from the right, which put Atlas's tail over Stop (29px,
  //: companionchat.js). Now the edge is searched from its right-hand end,
  //: sitting tucked first and standing second, and the first place that
  //: covers no control (Stop, Send, the input, the jump-to-latest pill)
  //: and none of the latest message is taken; none, and it stays put.
  const obstacles = nameMarkBuddyObstacles("chat");
  const look = [box.left + box.width / 2, box.top + 20];
  for (const [pose, legs, y] of [["sit", "tuck", box.top - NMB_SEAT], ["stand", "", box.top - NMB_FEET + 1]]) {
    for (let x = box.right - NMB_W - 8; x >= box.left + 8; x -= 24) {
      if (nameMarkBuddyHits(x, y, pose, obstacles, legs)) continue;
      //: Held to the dock while it reads, like any perch on a panel.
      return nameMarkBuddyErrand({ pose, legs, x, y, anchor: dock, edge: { type: "top", y: box.top, left: box.left, right: box.right } }, "", 0, look);
    }
  }
  return false;
}


// --- what is going on around it ---------------------------------------------
//: **Context, from events only** (the owner: "go to sleep if the user goes
//: afk for too long, or putting on headphones if music or sound is playing
//: ... or other things like that"). Each is a class on `#nm-buddy` that
//: shows a prop the figure carries (`.nmp-*`, see the character interface)
//: or changes a pose; nothing here polls.
//:
//: Sound: a page can only hear itself. What is detected is sound this app
//: plays: an <audio> or <video> element (a recording, a voice note) through
//: its play and pause events, and read aloud (`speakText`). Other apps'
//: audio, the system mixer and the microphone are not reachable, and no
//: permission is asked for.
const nmbSounds = new Set();
//: The props these show are drawn by the figure (`drawCharacter`'s prop
//: slots); a renderer without them simply shows nothing for them.
const NMB_PROPS_DRAWN = true;
//: **A prop says what it is** (Brief 88 a, the owner: "what is this on
//: the atlas companion??"). Hovered, the companion's tooltip names what it
//: has on and why, read from the classes that show each one; with none,
//: no tooltip (its name and what a click does are its label already).
const NMB_PROP_WORDS = [
  ["nmb-music", "headphones on: something is playing"],
  ["nmb-reading", "reading glasses on: you are reading"],
  ["nmb-act-read", "reading a book"],
  ["nmb-act-bell", "ringing a bell: a reminder"],
  ["nmb-act-lantern", "holding up a star: it got dark"],
  ["nmb-act-carry", "carrying a note it just filed"],
  ["nmb-act-juggle", "juggling stars"],
  ["nmb-act-map", "reading its star map"],
  ["nmb-offline", "holding a broken link: you are offline"],
];
function nameMarkBuddyNameProps(buddy, face) {
  const words = NMB_PROP_WORDS.filter(([cls]) => buddy.classList.contains(cls)).map(([, said]) => said);
  const cap = buddy.querySelector(".nmp-nightcap");
  if (cap && Number(getComputedStyle(cap).opacity) > 0.5) words.push(nameMarkBuddyHasAtlas(buddy) ? "a moon on its ear: it is resting" : "a night cap: it is resting");
  if (words.length) face.title = `${buddy.dataset.seed || "Your companion"}: ${words.join("; ")}`;
  else face.removeAttribute("title");
}
function nameMarkBuddySound(source, playing) {
  if (playing) nmbSounds.add(source);
  else nmbSounds.delete(source);
  for (const media of [...nmbSounds]) {
    if (media instanceof HTMLMediaElement && (media.paused || media.muted || !media.isConnected)) nmbSounds.delete(media);
  }
  if (NMB_PROPS_DRAWN) document.getElementById("nm-buddy")?.classList.toggle("nmb-music", nmbSounds.size > 0);
}
for (const type of ["play", "playing"]) {
  document.addEventListener(type, (event) => {
    if (event.target instanceof HTMLMediaElement) nameMarkBuddySound(event.target, !event.target.muted);
  }, true);
}
for (const type of ["pause", "ended", "emptied"]) {
  document.addEventListener(type, (event) => {
    if (event.target instanceof HTMLMediaElement) nameMarkBuddySound(event.target, false);
  }, true);
}

//: The hour (a nightcap and heavier eyes from 23:00 to 05:00) and whether
//: the machine is online (unplugged, it holds its cable), checked on each
//: decision and when the network changes.
function nameMarkBuddyContext(buddy = document.getElementById("nm-buddy")) {
  if (!buddy || !NMB_PROPS_DRAWN) return;
  const hour = new Date().getHours();
  buddy.classList.toggle("nmb-night", hour >= 23 || hour < 5);
  buddy.classList.toggle("nmb-offline", navigator.onLine === false);
}
window.addEventListener("online", () => nameMarkBuddyContext());
window.addEventListener("offline", () => nameMarkBuddyContext());

//: Back to the window after five minutes away: a wave.
let nameMarkBuddyBlurAt = 0;
window.addEventListener("blur", () => {
  nameMarkBuddyBlurAt = Date.now();
});
window.addEventListener("focus", () => {
  if (nameMarkBuddyBlurAt && Date.now() - nameMarkBuddyBlurAt > 5 * 60 * 1000) nameMarkBuddyCue("wave");
  nameMarkBuddyBlurAt = 0;
});

//: The theme turned dark: it lights a little lantern for a moment.
if (typeof MutationObserver === "function") {
  let darkBefore = document.documentElement.dataset.theme === "dark";
  new MutationObserver(() => {
    const dark = document.documentElement.dataset.theme === "dark";
    if (dark && !darkBefore) nameMarkBuddyCue("lantern");
    darkBefore = dark;
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
}

//: The pointer's place is kept for a glance; while it peeks, at most ten
//: times a second, a pointer within reach sends it ducking behind its
//: panel, and a moment after the pointer leaves it peeks out again. No
//: layout is read: its own place is in `nmb`.
document.addEventListener("pointermove", (event) => {
  nmb.pointer = [event.clientX, event.clientY];
  const now = Date.now();
  if (now - nmb.lastInput > 1000) nameMarkBuddyAwake();
  if (!document.getElementById("nm-buddy")) return;
  //: At most ten a second, and the last move of a burst is never lost: a
  //: pointer that stops inside the burst is looked at a moment later.
  if (now - nmb.shyAt < 100) {
    if (!nmb.trail) {
      nmb.trail = setTimeout(() => {
        nmb.trail = 0;
        nameMarkBuddyPointer(Date.now());
      }, 100 - (now - nmb.shyAt));
    }
    return;
  }
  nameMarkBuddyPointer(now);
}, { passive: true });

function nameMarkBuddyPointer(now) {
  if (!nmb.pointer) return;
  const [px, py] = nmb.pointer;
  nmb.shyAt = now;
  nameMarkBuddyNotice(px, py, now);
  nameMarkBuddyShy(now);
}

//: **Shy, with hysteresis** (the owner: "the peeking companion flashes in
//: and out?? and disappears when I try to move my mouse to it??"). While it
//: peeks, a pointer that comes within 120px and keeps approaching for 300ms
//: makes it sink to its eyes (never out of sight); it only comes back up
//: once the pointer is past 200px for a second; it changes its mind at most
//: once every three seconds. A pointer that arrives and stays is someone
//: reaching for it: after a second and a half curiosity wins, and it comes
//: out, looks at the pointer and can be picked up. One timer re-checks while
//: the pointer is still.
function nameMarkBuddyShy(now) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || (nmb.act !== "peek" && nmb.legs !== "peek") || !nmb.pointer) return;
  const [px, py] = nmb.pointer;
  const dist = Math.hypot(px - (nmb.x + NMB_W / 2), py - (nmb.y + nmb.edgeLine - 16));
  const shy = buddy.classList.contains("nmb-duck");
  const settled = now - (nmb.shyChangedAt || 0) >= 3000;
  clearTimeout(nmb.shyTimer);
  nmb.shyTimer = 0;
  const again = (ms) => {
    nmb.shyTimer = setTimeout(() => {
      nmb.shyTimer = 0;
      nameMarkBuddyShy(Date.now());
    }, ms);
  };
  if (dist < 120) {
    nmb.farSince = 0;
    if (!nmb.nearSince) nmb.nearSince = now;
    const near = now - nmb.nearSince;
    if (near >= 1500 && nmb.act === "peek") {
      nmb.nearSince = 0;
      buddy.classList.remove("nmb-duck");
      nmb.shyChangedAt = now;
      nameMarkBuddyAct("emerge");
      nameMarkBuddyAim([px, py]);
      return;
    }
    if (!shy && near >= 300 && settled) {
      buddy.classList.add("nmb-duck");
      nmb.shyChangedAt = now;
    }
    again(near < 300 ? 300 - near : 1500 - near > 0 ? 1500 - near : 3000);
    return;
  }
  nmb.nearSince = 0;
  if (dist > 200 && shy) {
    if (!nmb.farSince) nmb.farSince = now;
    const far = now - nmb.farSince;
    const wait = Math.max(1000 - far, 3000 - (now - (nmb.shyChangedAt || 0)));
    if (wait <= 0) {
      buddy.classList.remove("nmb-duck");
      nmb.shyChangedAt = now;
      nmb.farSince = 0;
    } else {
      again(wait);
    }
  }
}

//: Typing near it: it watches the field, for as long as the typing goes on
//: and a moment after. At most one measurement every 400ms.
document.addEventListener("keydown", (event) => {
  const buddy = document.getElementById("nm-buddy");
  const field = event.target;
  if (!buddy || nameMarkBuddyStill() || !(field instanceof Element)) return;
  if (!field.matches("input, textarea, [contenteditable='true'], [contenteditable=''], .cm-content")) return;
  const now = Date.now();
  if (now - nmb.watchAt > 400) {
    nmb.watchAt = now;
    const box = field.getBoundingClientRect();
    const px = Math.min(Math.max(nmb.x + NMB_W / 2, box.left), box.right);
    const py = Math.min(Math.max(nmb.y + NMB_HEAD / 2, box.top), box.bottom);
    if (Math.hypot(px - (nmb.x + NMB_W / 2), py - (nmb.y + NMB_HEAD / 2)) > 420) return;
    nameMarkBuddyAim([px, py]);
  }
  //: Typing fast (keys under 180ms apart, five in a row), it nods along.
  nmb.keyRun = now - nmb.keyAt < 180 ? nmb.keyRun + 1 : 0;
  nmb.keyAt = now;
  buddy.classList.add("nmb-watch");
  buddy.classList.toggle("nmb-nod", nmb.keyRun >= 5);
  clearTimeout(nmb.watchTimer);
  nmb.watchTimer = setTimeout(() => buddy.classList.remove("nmb-watch", "nmb-nod"), 1800);
}, { passive: true, capture: true });

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearTimeout(nmb.timer);
    nmb.timer = 0;
  } else {
    //: Hiding cleared the timer that ends an act (`nmb.timer`), so an act
    //: caught by it would hold its pose until the next beat: it ends now.
    if (nmb.act && !NMB_RESTING_ACTS.has(nmb.act)) nameMarkBuddyAct("");
    //: Back after a long absence, it is found asleep, and the next input
    //: wakes it.
    if (Date.now() - nmb.lastInput > NMB_SLEEP_MS) document.getElementById("nm-buddy")?.classList.add("nmb-sleep");
    nameMarkBuddyContext();
    nameMarkBuddySchedule();
  }
});

// --- building it ----------------------------------------------------------------

//: Hidden from its menu: off in Appearance, gone from the page, and a toast
//: that says where it comes back from.
//: Off the page: every timer it had stops and nothing is followed.
function nameMarkBuddyGone() {
  clearTimeout(nmb.timer);
  clearTimeout(nmb.placeTimer);
  clearTimeout(nmb.awayTimer);
  clearTimeout(nmb.sightTimer);
  nmb.away = false;
  //: Hidden while it visits its large view: no visit to come home from.
  nmb.visit = null;
  nmb.ghost?.remove();
  nmb.ghost = null;
  clearTimeout(nmb.heldTimer);
  nmb.timer = nmb.placeTimer = nmb.heldTimer = 0;
  nmb.glue = null;
  nmb.pinned = false;
  nmb.rideAnim?.cancel();
  nmb.shutterAnim?.cancel();
  nmb.rideAnim = nmb.shutterAnim = nmb.ride = null;
  nmb.seenObserver?.disconnect();
  nmb.seenObserver = null;
  document.getElementById("nm-buddy-band")?.remove();
  nameMarkBuddyWatch();
  nmb.x = nmb.y = NaN;
  //: What it was in the middle of goes with it: a companion shown again
  //: (or another one chosen) is not born mid-nap, mid-pout or mid-frame.
  //: With `nmb.act` left at "lie", the new one counted as asleep
  //: (`nameMarkBuddyAsleep`) and was carried in by the sleeping fade.
  for (const t of nmb.poseSteps || []) clearTimeout(t);
  nmb.poseSteps = [];
  for (const t of nmb.wakeSteps || []) clearTimeout(t);
  nmb.wakeSteps = [];
  clearTimeout(nmb.easeTimer);
  clearTimeout(nmb.poutTimer);
  clearTimeout(nmb.fitTimer);
  clearTimeout(nmb.cueTimer);
  nmb.act = "";
  nmb.wokeAt = 0;
  nmb.easeUntil = 0;
}

function nameMarkBuddyHide(buddy) {
  let was = null;
  try {
    //: Which companion it was, so the hotkey brings the same one back.
    was = prefs.get("avatar-buddy", null);
    if (was && was !== "off") prefs.set("nm-buddy-last", was);
    prefs.set("avatar-buddy", "off");
  } catch (e) {
    // Hidden for this session at least.
  }
  const select = document.getElementById("avatar-buddy");
  if (select) select.value = "off";
  nameMarkBuddyLeave(buddy, () => {
    buddy?.remove();
    //: Every copy: a stray second mount left its glow and grip behind.
    for (const stray of document.querySelectorAll("#nm-buddy, .nmb-burst")) stray.remove();
    nameMarkBuddyGone();
  });
  //: The chord as it is bound now (it is rebindable), not as it shipped.
  const keys = typeof shortcuts === "object" ? shortcuts?.toggleCompanion?.keys : "";
  //: **The way back is a button, not a sentence** (INBOX 743, the owner:
  //: "the show companion notification button was poorly shown"). The toast
  //: named a chord and a Settings path in prose, with nothing to press; the
  //: toast-with-action recipe puts the one press beside its first line.
  const back = was && was !== "off" ? was : "me";
  toastAction(
    keys ? `Companion hidden. ${keys} brings it back too.` : "Companion hidden.",
    "Show it",
    () => {
      try {
        prefs.set("avatar-buddy", back);
      } catch (e) {
        // Back for this visit.
      }
      const choice = document.getElementById("avatar-buddy");
      if (choice) choice.value = back;
      syncNameMarkBuddy();
    },
    { record: false }
  );
}

//: Whether it is out: chosen in Appearance, or still on the page.
function nameMarkBuddyShowing() {
  let choice = "off";
  try {
    choice = prefs.get("avatar-buddy", null) || "off";
  } catch (e) {
    choice = "off";
  }
  return choice !== "off" || !!document.getElementById("nm-buddy");
}

//: **Show or hide it from anywhere** (INBOX 430, the owner: "a show/hide
//: companion hotkey, and palette action"): Ctrl+Shift+Y (`toggleCompanion`
//: in the shortcut registry), the command palette and Find anything, whose
//: row says which it will do (`nameMarkBuddyShowing`). Hidden, it comes back
//: as whichever companion it was (`nm-buddy-last`), or Atlas.
function nameMarkBuddyToggle() {
  if (nameMarkBuddyShowing()) {
    nameMarkBuddyHide(document.getElementById("nm-buddy"));
    return;
  }
  let back = "atlas";
  try {
    back = prefs.get("nm-buddy-last", null) || "atlas";
    prefs.set("avatar-buddy", back);
  } catch (e) {
    // Shown for this session at least.
  }
  //: Through the Appearance select's own change, so a custom companion is
  //: mounted and the size control follows, as when it is picked there.
  const select = document.getElementById("avatar-buddy");
  if (select) {
    select.value = back;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  } else {
    syncNameMarkBuddy();
  }
}

function nameMarkBuddyBuild() {
  const buddy = document.createElement("div");
  buddy.id = "nm-buddy";
  //: Hidden from its first style on: its size is measured below, which
  //: computes its style, and a class added after that faded it out from
  //: where it was built (the window's corner) rather than never drawing it.
  buddy.classList.add("nmb-away");
  const face = document.createElement("button");
  face.type = "button";
  face.className = "nm-buddy-face";
  face.setAttribute("aria-haspopup", "menu");
  const char = document.createElement("span");
  char.className = "nm-buddy-char";
  const think = document.createElement("span");
  think.className = "nm-buddy-think";
  think.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 3; i += 1) think.appendChild(document.createElement("i"));
  const sleep = document.createElement("span");
  sleep.className = "nm-buddy-z";
  sleep.setAttribute("aria-hidden", "true");
  //: Three z's that drift up one after another (the CSS delays each).
  for (let i = 0; i < 3; i += 1) {
    const z = document.createElement("i");
    z.textContent = "z";
    sleep.appendChild(z);
  }
  //: The figure itself (`characterFor(seed).figure()`) goes in first, when
  //: `syncNameMarkBuddy` knows whose it is.
  char.append(think, sleep);
  face.appendChild(char);
  //: **Its little emotes** (the owner: "should there be more emotes like
  //: zzzz coming off it for sleeping"): a question mark, a sparkle, a sweat
  //: drop by its head, each played once by `nameMarkBuddyEmote`.
  const emote = document.createElement("span");
  emote.className = "nmb-emote";
  emote.setAttribute("aria-hidden", "true");
  const q = document.createElement("b");
  q.className = "nmb-emote-q";
  q.textContent = "?";
  const svg = (cls, d, fill) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    el.setAttribute("class", cls);
    el.setAttribute("viewBox", "0 0 12 12");
    el.setAttribute("width", "12");
    el.setAttribute("height", "12");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", fill);
    el.appendChild(path);
    return el;
  };
  emote.append(
    q,
    svg("nmb-emote-spark", "M6 0 L7.3 4.7 L12 6 L7.3 7.3 L6 12 L4.7 7.3 L0 6 L4.7 4.7 Z", "#ffd84a"),
    svg("nmb-emote-sweat", "M6 0 C8 4 10 6 10 8 A4 4 0 0 1 2 8 C2 6 4 4 6 0 Z", "#7cc4ff"),
  );
  face.appendChild(emote);
  //: No x on it (the owner: "the x button being on the companion the whole
  //: time is kinda annoying. keep it in the right click or hold popup
  //: menu"): Hide is in its menu, which the keyboard reaches too.
  //: The size handle: at its corner, shown on hover, dragged away from or
  //: towards the point it stands on to make it bigger or smaller. A mouse
  //: thing; the menu and Appearance size it from the keyboard or a touch.
  const grip = document.createElement("span");
  grip.className = "nmb-size-grip";
  grip.setAttribute("aria-hidden", "true");
  grip.title = "Drag to resize, double-click to reset";
  face.appendChild(grip);
  grip.addEventListener("click", (event) => event.stopPropagation());
  //: **A double-click or a double tap puts it back to its own size** (INBOX
  //: 601, the owner: "I want to be able to double tab the drag to resize
  //: circle on the companion to reset it to default size"): Medium, kept
  //: as a size from the handle is (`nameMarkBuddySetSize`), eased there
  //: rather than jumped (`nmb-fitting`, the CSS's scale transition). The
  //: second press is read here, not from `dblclick`: the press's
  //: `preventDefault` (no text selected while sizing) and the pointer
  //: capture keep a touch's taps from ever making one, and a press that
  //: became a drag is not half of a double. Its own `dblclick` stops here
  //: too, so it never opens the large view.
  grip.addEventListener("dblclick", (event) => event.stopPropagation());
  let lastPress = null;
  grip.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    event.preventDefault();
    const at = performance.now();
    if (lastPress && at - lastPress.at < 400 && Math.hypot(event.clientX - lastPress.x, event.clientY - lastPress.y) < 12 && !lastPress.moved) {
      lastPress = null;
      nameMarkBuddyResetSize(buddy);
      return;
    }
    const press = { at, x: event.clientX, y: event.clientY, moved: false };
    lastPress = press;
    const [ox, oy] = nameMarkBuddyOrigin(nmb.x, nmb.y, nmb.pose);
    const from = Math.max(8, Math.hypot(event.clientX - ox, event.clientY - oy));
    const was = nmb.scale || 1;
    grip.setPointerCapture(event.pointerId);
    buddy.classList.add("nmb-sizing");
    const move = (e) => {
      if (!press.moved && Math.hypot(e.clientX - press.x, e.clientY - press.y) < 4) return;
      press.moved = true;
      nameMarkBuddySetSize(was * Math.hypot(e.clientX - ox, e.clientY - oy) / from, false);
    };
    const end = () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", end);
      grip.removeEventListener("pointercancel", end);
      buddy.classList.remove("nmb-sizing");
      //: A press that never pulled leaves the size as it was (it may be
      //: the first of a double).
      if (press.moved) nameMarkBuddySetSize(nmb.scale, true);
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", end);
    grip.addEventListener("pointercancel", end);
  });
  buddy.append(face);
  //: **A band and a rider** (INBOX 426 x, `nameMarkBuddyRide`): the band
  //: is the window, or the visible box of the panel's scroll area it rides
  //: in, and clips it there; the rider inside it is moved by the browser
  //: with that scroll. It stays in the body: the app's own scroll boxes
  //: (the dashboard's flex page, the notes list) are never given a child
  //: they did not make. Between them the shutter, which closes the band
  //: down to the bar its perch has gone under (`nameMarkBuddyRideFrames`).
  const band = document.createElement("div");
  band.id = "nm-buddy-band";
  const shutter = document.createElement("div");
  shutter.className = "nm-buddy-shutter";
  const rider = document.createElement("div");
  rider.className = "nm-buddy-rider";
  rider.appendChild(buddy);
  shutter.appendChild(rider);
  band.appendChild(shutter);
  document.body.appendChild(band);
  nameMarkBuddyLockSync();
  nameMarkBuddySetSize(nameMarkBuddyScaleSaved(), false);
  nameMarkBuddyToggles(buddy);
  if (typeof MutationObserver === "function") {
    nmb.coverObserver?.disconnect();
    //: The one watch of the page: the body's own class (the back-to-top button) asks for a
    //: perch check, and a dialog or overlay anywhere sets `data-cover`.
    nmb.coverObserver = new MutationObserver((records) => {
      if (records.some((r) => r.type === "attributes" && r.target === document.body)) queueNameMarkBuddyCheck();
      nameMarkBuddyCoverWatch(records);
    });
    nmb.coverObserver.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["class", "open"] });
  }
  nameMarkBuddyCoverCheck();
  if (typeof IntersectionObserver === "function") {
    nmb.seenObserver?.disconnect();
    nmb.seenObserver = new IntersectionObserver((entries) => nameMarkBuddySeen(entries[entries.length - 1].isIntersecting), { threshold: 0 });
    nmb.seenObserver.observe(buddy);
  }

  //: **A smooth drag** (the owner: "dragging the corner companion is jerky
  //: and kinda like a grid snap"): a `translate` applied once a frame from
  //: the latest pointer, held by its hands with its legs kicking, and the
  //: place written back once, on release, where it lands.
  let drag = null;
  let dragFrame = 0;
  const follow = () => {
    dragFrame = 0;
    if (!drag?.moved) return;
    const dx = Math.min(Math.max(-drag.box.left, drag.x - drag.sx), innerWidth - drag.box.right);
    const dy = Math.min(Math.max(-drag.box.top, drag.y - drag.sy), innerHeight - drag.box.bottom);
    buddy.style.translate = `${dx}px ${dy}px`;
    //: Carried, it swings with the pull: its legs and body lean against
    //: the way it is moved, by how fast, and settle when the pull stops.
    const vx = drag.x - (drag.lastX ?? drag.x);
    drag.lastX = drag.x;
    const sway = Math.max(-28, Math.min(28, -vx * 1.4));
    nameMarkBuddySway(buddy, sway);
    //: Only on a change: a same-value attribute write still dirties its style.
    const turn = vx < 0 ? "l" : "r";
    if (Math.abs(vx) > 1 && buddy.dataset.turn !== turn) buddy.dataset.turn = turn;
    clearTimeout(drag.settle);
    drag.settle = setTimeout(() => nameMarkBuddySway(buddy, 0), 120);
  };
  face.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || nmb.visit) return;
    //: **Movable at all times** (the owner: "it needs to be movable at all
    //: times"): mid-walk, mid-hop, peeking, hanging or asleep, it is taken
    //: from where it is drawn and everything it was doing stops, once the
    //: press becomes a pull (below). A press that is a click stops nothing:
    //: halting on the press woke it before its click could see it asleep,
    //: so a sleeping companion answered a click as if awake, at once
    //: (companionfeel.js: "wave" 200ms after clicking it asleep).
    drag = { box: null, sx: event.clientX, sy: event.clientY, x: event.clientX, y: event.clientY, moved: false };
    face.setPointerCapture(event.pointerId);
  });
  face.addEventListener("pointermove", (event) => {
    if (!drag) return;
    drag.x = event.clientX;
    drag.y = event.clientY;
    //: The pull's last moves, for the speed it is let go at.
    //: The input's own time, not when this ran: on a busy main thread the
    //: handler runs late, and a late stamp read the pull as having stopped
    //: (a throw let go at speed came down as a plain drop at 4x CPU).
    const t = event.timeStamp;
    (drag.samples ||= []).push([event.clientX, event.clientY, t]);
    while (drag.samples.length > 2 && t - drag.samples[0][2] > 160) drag.samples.shift();
    //: A click wobbles a pixel or two; only a real pull is a drag.
    if (!drag.moved && Math.hypot(drag.x - drag.sx, drag.y - drag.sy) < 4) return;
    if (!drag.moved) {
      drag.moved = true;
      ensureModule("companionThrow");
      nmb.flight?.stop();
      const box = buddy.getBoundingClientRect();
      nmb.anim?.cancel();
      nmb.hopAnim?.cancel();
      nmb.glideAnim?.cancel();
      nameMarkBuddyHalt(buddy);
      buddy.style.translate = "";
      nameMarkBuddyPut(buddy, Math.round(box.left), Math.round(box.top));
      drag.box = buddy.getBoundingClientRect();
      drag.sx = drag.x;
      drag.sy = drag.y;
      //: Carried in the window, not in a scroll area: where it lands
      //: decides what it rides next.
      nameMarkBuddyRide(null);
      nameMarkBuddyAct("");
      buddy.classList.remove("nmb-sleep", "nmb-drowsy");
      nameMarkBuddyRelease();
      nmb.mood.energy = Math.min(1, nmb.mood.energy + 0.15);
      nmb.mood.sociability = Math.max(0, nmb.mood.sociability - 0.05);
      buddy.classList.add("nm-buddy-dragging");
    }
    //: Shaken up and down while carried, it turns over (`nameMarkBuddyFlip`).
    (drag.shake ||= []).push([event.clientX, event.clientY, t]);
    while (drag.shake.length > 2 && t - drag.shake[0][2] > 900) drag.shake.shift();
    if (!drag.flipped && nameMarkBuddyStrokes(drag.shake, 1, 14, 900) >= 3 && !nameMarkBuddyActOff("flip")) {
      drag.flipped = true;
      nameMarkBuddyFlip(buddy, true);
    }
    if (!dragFrame) dragFrame = requestAnimationFrame(follow);
  });
  const release = (event) => {
    if (drag?.flipped) nameMarkBuddyFlip(buddy, false);
    if (drag?.moved) {
      cancelAnimationFrame(dragFrame);
      dragFrame = 0;
      follow();
      const box = buddy.getBoundingClientRect();
      //: Reads first, then writes: one restyle of the rig, not three (Atlas at 4x).
      const v = nameMarkBuddyReleaseVelocity(drag.samples || [], event?.timeStamp ?? performance.now());
      const thrown = !!v && Math.hypot(v[0], v[1]) > NMB_TOSS_SPEED && typeof nameMarkBuddyThrow === "function";
      if (thrown) nameMarkBuddyIndexReset();
      const world = thrown && nameMarkBuddyWorld(nameMarkBuddyTab());
      const landed = !thrown && nameMarkBuddyDrop(Math.round(box.left), Math.round(box.top));
      buddy.style.translate = "";
      buddy.classList.remove("nm-buddy-dragging");
      clearTimeout(drag.settle);
      nameMarkBuddySway(buddy, 0);
      delete buddy.dataset.turn;
      nameMarkBuddyPut(buddy, Math.round(box.left), Math.round(box.top));
      //: **Thrown** (INBOX 882): let go while still moving fast, it flies
      //: (`nameMarkBuddyThrow`).
      if (thrown) {
        nameMarkBuddyThrow(buddy, v[0], v[1], world);
        face.dataset.dragged = "1";
        drag = null;
        return;
      }
      //: **Settling** (the owner: "how it acts and settles down when I move
      //: it"): it drops onto the surface under gravity's curve, lands with
      //: a squash and a small overshoot, looks around once, and then stays:
      //: nothing re-perches it for thirty seconds unless a control comes up
      //: under it.
      if (landed.y >= nmb.y - 2) landed.falls = true;
      nmb.placedAt = Date.now();
      nmb.afterLand = true;
      nameMarkBuddyMoveTo(buddy, landed);
      if (!nmb.anim || nmb.anim.playState === "finished" || nmb.anim.playState === "idle") nameMarkBuddyAct("land");
      const spots = nameMarkBuddySpots();
      delete spots["*"];
      spots[nameMarkBuddyTab()] = nameMarkBuddySpotFor(landed);
      nameMarkBuddyKeepSpots(spots);
      face.dataset.dragged = "1";
    }
    drag = null;
  };
  face.addEventListener("pointerup", release);
  face.addEventListener("pointercancel", release);
  //: **A double-click is not two pokes** (INBOX 443 c, the owner: a
  //: double-click to enlarge it should find it "still doing that action").
  //: Its first click used to poke it there and then, and the poke ended
  //: whatever it was doing before the large view opened. So a click on the
  //: page waits 280ms for a second one: a second one cancels it, and the
  //: double-click opens the large view with nothing interrupted. In the
  //: large view a click is a poke at once.
  let pokeTimer = 0;
  face.addEventListener("click", (event) => {
    if (face.dataset.dragged) {
      delete face.dataset.dragged;
      return;
    }
    //: Tucked behind the bar (the menu's "Tuck behind the bar"): a click
    //: stands it up where it is, on the bar's top edge, by a small step
    //: rather than a trip elsewhere (the owner: "it shouldn't instantly
    //: appear somewhere else when untucked manually"). If it then covers a
    //: control, the usual check steps it aside; otherwise it stays, settled
    //: as after a drop. A drag also untucks (`nameMarkBuddyMoveTo` clears the pin).
    if (nmb.tucked) {
      const { bottom } = nameMarkBuddyLedges();
      nmb.tucked = false;
      nmb.pinned = false;
      nmb.placedAt = Date.now();
      if (bottom) {
        nameMarkBuddyMoveTo(buddy, { kind: "bar", pose: "stand", legs: "", x: nmb.x, y: bottom.top - NMB_FEET, edge: { el: document.getElementById("status-bar"), type: "top", kind: "bar", y: bottom.top } });
        setTimeout(queueNameMarkBuddyCheck, 1200);
      } else {
        placeNameMarkBuddy(buddy, false, [nmb.x, nmb.y]);
      }
      return;
    }
    clearTimeout(pokeTimer);
    pokeTimer = 0;
    if (!nmb.visit && event.detail >= 2) return;
    const poke = () => {
      pokeTimer = 0;
      const now = Date.now();
      const wasAsleep = buddy.classList.contains("nmb-sleep") || nmb.act === "nap" || nmb.act === "lie";
      const sinceLast = now - (nmb.lastPoke || 0);
      nmb.lastPoke = now;
      nmb.pokes = [...nmb.pokes.filter((at) => now - at < 20000), now];
      const groggy = now - (nmb.wokeAt || 0) < 10000;
      //: What it did last counts only inside the same run of taps.
      const lastHow = sinceLast < 20000 ? nmb.lastHow || "" : "";
      const how = nameMarkBuddyClickReaction(wasAsleep, wasAsleep ? 1 : nmb.pokes.length, sinceLast, groggy, lastHow);
      nmb.lastHow = how;
      const mark = face.querySelector(".name-mark");
      //: A spin is Atlas's own turn (atlas.js); another face's react is
      //: already a hop and a spin.
      if (how === "spin" && mark?.classList.contains("nm-atlas")) atlasPlay("spin", 900);
      else nameMarkReact(mark);
      if (how === "wake") {
        //: The poke that woke it starts the count of pokes that annoy it.
        nmb.pokes = [now];
        if (nmb.act === "lie") nameMarkBuddyAct("");
        nameMarkBuddyWake(true);
        return;
      }
      if (how === "pout") {
        nameMarkBuddyFeel(-0.15);
        nmb.groggyUntil = Math.max(nmb.groggyUntil || 0, now + 4000);
        nameMarkBuddyPout(buddy, 6000);
        return;
      }
      //: **Poked too often** (four times in twenty seconds): grumpy for half
      //: a minute. It turns away, says so, and will not look at you.
      if (how === "grumpy") {
        nameMarkBuddyFeel(-0.4);
        nmb.grumpyUntil = now + 30000;
        nmb.mood.sociability = Math.max(0, nmb.mood.sociability - 0.25);
        nameMarkBuddyRelease();
        buddy.classList.remove("nmb-pout");
        nameMarkBuddyEase(buddy, 2400);
        buddy.classList.add("nmb-grumpy");
        nameMarkBuddyExpress("unimpressed", 30000);
        buddy.dataset.turn = nmb.pointer && nmb.pointer[0] > nmb.x + NMB_W / 2 ? "l" : "r";
        setTimeout(() => {
          //: And it comes down through a pout, not straight back (unless it
          //: has gone meanwhile: the pout would land on its successor, or a
          //: rub has made up already).
          if (!buddy.isConnected || (nmb.rubbedAt || 0) > now) return;
          buddy.classList.remove("nmb-grumpy");
          nameMarkBuddyPout(buddy, 5000);
          if (buddy.dataset.turn && !buddy.classList.contains("nmb-walking")) delete buddy.dataset.turn;
        }, 30000);
        nameMarkSay(buddy, ["Hmph.", "Okay, that's enough.", "I'm not talking to you."][Math.floor(Math.random() * 3)]);
        return;
      }
      nmb.mood.sociability = Math.min(1, nmb.mood.sociability + 0.05);
      nmb.mood.curiosity = Math.min(1, nmb.mood.curiosity + 0.05);
      nameMarkBuddyFeel(how === "playful" || how === "laugh" ? 0.08 : 0.12);
      //: The face holds a few seconds and comes down through a smaller one
      //: (`NMB_EXPR_SOFTEN`), never straight back. Each answer has its own:
      //: curious looks round with wide eyes, a spin is bright, a laugh holds
      //: longest.
      const answerFace = { playful: "laughing", laugh: "laughing", curious: "surprised", spin: "excited" };
      nameMarkBuddyExpress(answerFace[how] || "happy", how === "laugh" ? 3800 : how === "curious" ? 2600 : 3200);
      //: The acts are the gentle ones (a look, a wave, a wiggle): none is a
      //: whole-body hop, so the large view keeps INBOX 669's limits.
      const move = { pleased: "wave", wave: "wave", playful: "wiggle", laugh: "wiggle", curious: "look", spin: "" }[how];
      if (!nameMarkBuddyStill() && move !== "") nameMarkBuddyAct(nmb.pose === "hang" ? "swing" : move);
      nameMarkSay(buddy, nameMarkLine(buddy.dataset.seed || ""));
    };
    if (nmb.visit) poke();
    else pokeTimer = setTimeout(poke, 280);
  });
  //: Enlarged, it is itself, still doing what it was doing (INBOX 443 c).
  face.addEventListener("dblclick", () => {
    clearTimeout(pokeTimer);
    pokeTimer = 0;
    openNameMarkViewer(buddy.dataset.seed || "", { visit: true });
  });
  //: **Petted** (round 5): the pointer resting on it for a second, not
  //: pressing, gets a happy wiggle; not more than once in fifteen seconds.
  let pet = 0;
  const unpet = () => {
    clearTimeout(pet);
    pet = 0;
  };
  face.addEventListener("pointerenter", (event) => {
    nameMarkBuddyNameProps(buddy, face);
    if (event.pointerType !== "mouse" || drag) return;
    //: Carried into its large view under a pointer that has not moved: the
    //: figure arrived, the pointer did not come to it, so it is not a pet
    //: and does not wake it (viewersleep.js: asleep, it yawned awake 1.8s
    //: after the view opened and its Zs went with it).
    if (nmb.visit && Date.now() - nmb.visit.at < NMB_VISIT_SETTLE_MS) return;
    unpet();
    nameMarkBuddyHover(0);
    pet = setTimeout(() => {
      pet = 0;
      if (!face.matches(":hover")) return;
      nameMarkBuddyPet();
      //: Still there: a dozing companion wakes for you.
      pet = setTimeout(() => {
        pet = 0;
        if (face.matches(":hover")) nameMarkBuddyHover(1800);
      }, 1800 - NMB_PET_MS);
    }, NMB_PET_MS);
  });
  face.addEventListener("pointerleave", unpet);
  face.addEventListener("pointerdown", unpet);
  //: **Rubbed**: the pointer back and forth over it, not pressing
  //: (`nameMarkBuddyRubbed`); in the large view too.
  let rub = [];
  face.addEventListener("pointermove", (event) => {
    if (drag || event.buttons || event.pointerType === "touch") return;
    const t = performance.now();
    rub.push([event.clientX, event.clientY, t]);
    while (rub.length > 2 && t - rub[0][2] > 1600) rub.shift();
    if (rub.length >= 6 && nameMarkBuddyStrokes(rub, 0, 5, 1600) >= 4) {
      rub = [];
      nameMarkBuddyRubbed(buddy);
    }
  });
  face.addEventListener("pointerleave", () => {
    rub = [];
  });
  //: **Its own menu**, on right-click, a long press, or from the keyboard
  //: (the Menu key or Shift+F10 while it has focus).
  //: Wherever it is opened from, it opens at the companion
  //: (`nameMarkBuddyMenu`).
  //: A right-click opens it at the pointer: only when a real pointer
  //: pressed the second button just now (a keyboard's context-menu event
  //: carries a made-up point), and then from that press's own place.
  let rightDown = null;
  face.addEventListener("pointerdown", (event) => {
    if (event.button === 2) rightDown = { x: event.clientX, y: event.clientY, at: performance.now() };
  });
  face.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    //: In the enlarged view too (the owner, 2026-10-10: "I cant right click
    //: to view the menu to change the companion in the expanded popup
    //: view"); there the menu keeps only who it is (`nameMarkBuddyMenu`).
    const fresh = rightDown && performance.now() - rightDown.at < 1500;
    nameMarkBuddyMenu(buddy, fresh ? [event.clientX || rightDown.x, event.clientY || rightDown.y] : null);
    rightDown = null;
  });
  face.addEventListener("keydown", (event) => {
    if (event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) {
      event.preventDefault();
      nameMarkBuddyMenu(buddy);
    }
  });
  let hold = 0;
  face.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse" || nmb.visit) return;
    clearTimeout(hold);
    const at = [event.clientX, event.clientY];
    hold = setTimeout(() => {
      drag = null;
      face.dataset.dragged = "1";
      nameMarkBuddyMenu(buddy, at);
    }, 550);
  });
  for (const type of ["pointerup", "pointercancel", "pointermove"]) {
    face.addEventListener(type, () => {
      if (type !== "pointermove" || (drag && drag.moved)) clearTimeout(hold);
    });
  }
  //: The one-place and four-corner choices this replaces: a place kept for
  //: every page is the annoyance the perches exist to end.
  try {
    prefs.remove("nm-buddy-pos");
    prefs.remove("nm-buddy-corner");
  } catch (e) {
    // Nothing to tidy.
  }
  return buddy;
}

function syncNameMarkBuddy() {
  const seed = nameMarkBuddySeed();
  let buddy = document.getElementById("nm-buddy");
  if (!seed) {
    buddy?.remove();
    nameMarkBuddyGone();
    return;
  }
  const fresh = !buddy;
  nameMarkBuddyMotionApply();
  if (fresh) buddy = nameMarkBuddyBuild();
  if (buddy.dataset.seed !== seed) {
    buddy.dataset.seed = seed;
    //: Its mood and species lean its choices (`nameMarkBuddyDecide`).
    nmb.reading = nameMood(seed);
    buddy.dataset.feel = nmb.reading?.mood || "";
    const char = buddy.querySelector(".nm-buddy-char");
    char.querySelector(".nm-figure")?.remove();
    char.prepend(characterFor(seed).figure());
    //: A new face starts from its own look.
    nmb.expr = "";
    nmb.exprHold = "";
    clearTimeout(nmb.exprTimer);
    nmb.exprTimer = 0;
    nameMarkBuddyPrewarm(seed);
    //: A new drawing has new animations: looked for again at once.
    nmbTempo.seen = 0;
    if (!nmbTempo.timer) nmbTempo.timer = setTimeout(nameMarkBuddyTempo, 0);
    buddy.querySelector(".nm-buddy-face").setAttribute(
      "aria-label",
      `${seed}, your companion. Click to say hello, double-click to enlarge, drag to move, Shift+F10 for its menu.`,
    );
  }
  //: **Never drawn before it has a place** (the owner, 2026-09-27: it
  //: "appeared for a split second at the top right ... then it smoothly
  //: appeared, but then ... pretty suddenly slightly adjusted its position
  //: to perch"). It was placed the moment it was built, while the page was
  //: still filling in: measured at 1093x614, drawn at a card's corner at
  //: y=202, then carried 142px and 18px more in two single-frame jumps as
  //: the dashboard's content arrived above that card. Now it is built hidden
  //: (`nmb-away`, which starts with no transition) and comes in as it does
  //: to a tab (`nameMarkBuddyArrive`): once the page has stopped moving
  //: under the perch it chose (`nameMarkBuddySettle`).
  if (fresh) {
    nmb.x = nmb.y = NaN;
    nmb.tab = "";
    nmb.away = true;
    buddy.classList.add("nmb-away");
    clearTimeout(nmb.awayTimer);
    nmb.awayTimer = 0;
    nameMarkBuddyArrive(buddy);
  }
  nameMarkBuddySchedule();
}

//: Re-checked when the body's classes change (the back-to-top button
//: toggles `scroll-top-visible`), when a toast comes or goes, when a scroll
//: settles (a card it stands on may have moved), and on resize, where it
//: chooses again.
if (typeof MutationObserver === "function") {
  const toasts = document.getElementById("toast-box");
  if (toasts) {
    new MutationObserver((records) => {
      queueNameMarkBuddyCheck();
      //: Something new on screen: it looks at it (rate-limited with the
      //: other things it notices, `nameMarkBuddyReact`).
      const added = records.flatMap((r) => [...r.addedNodes]).find((n) => n instanceof Element);
      if (added) requestAnimationFrame(() => nameMarkBuddyReact("toast", added));
    }).observe(toasts, { childList: true });
  }
}
document.addEventListener("scrollend", queueNameMarkBuddyCheck, { passive: true, capture: true });
document.addEventListener("transitionend", (event) => {
  if (event.target?.closest?.("#scroll-top, .chat-jump-latest")) queueNameMarkBuddyCheck();
});
let nameMarkBuddyResize = 0;
window.addEventListener("resize", () => {
  nameMarkBuddyKeepUp();
  clearTimeout(nameMarkBuddyResize);
  nameMarkBuddyResize = setTimeout(nameMarkBuddyRefit, 150);
}, { passive: true });

// --- being found ------------------------------------------------------------------
//: **A one-time nudge** (the owner: "the companion should be advertised or
//: made more learnable that it is a feature in some places"). Besides its
//: catalogue row, its Help line and its tour card: once, after three days
//: of use or the first time Appearance is opened, a toast asks whether you
//: want one, with Turn on; its own x is "not now". Either way it is never
//: shown again, and never while the companion is already on or the app is
//: locked.
const NMB_HINT_AFTER_MS = 3 * 24 * 60 * 60 * 1000;
function nameMarkBuddyHint(fromAppearance = false) {
  let since = 0;
  try {
    if (prefs.get("nm-buddy-hint", null) === "done") return;
    since = Number(prefs.get("nm-buddy-first-seen", null)) || 0;
    if (!since) {
      since = Date.now();
      prefs.set("nm-buddy-first-seen", String(since));
    }
  } catch (e) {
    return;
  }
  if (!fromAppearance && Date.now() - since < NMB_HINT_AFTER_MS) return;
  if (nameMarkBuddySeed() || typeof toastAction !== "function") return;
  const lock = document.getElementById("lock-overlay");
  if (lock && !lock.classList.contains("hidden")) return;
  //: Not during the welcome or the tour (first-run sweep, 2026-10-11): the
  //: tour's Appearance step opens that pane, and the offer drew over Settings
  //: and beside the tour's card, a second voice in the middle of the first.
  //: Left unmarked, so it is offered the next time instead.
  for (const id of ["tour-card", "onboarding-overlay"]) {
    const surface = document.getElementById(id);
    if (surface && !surface.classList.contains("hidden")) return;
  }
  try {
    prefs.set("nm-buddy-hint", "done");
  } catch (e) {
    // Shown this once at least.
  }
  //: Two lines beside its button, not three (measured 72px of message at
  //: 384px wide before; INBOX 743 "poorly shown").
  toastAction("Want a companion on screen? It reacts to what you do.", "Turn on", () => {
    try {
      prefs.set("avatar-buddy", "me");
    } catch (e) {
      // On for this visit.
    }
    const select = document.getElementById("avatar-buddy");
    if (select) select.value = "me";
    syncNameMarkBuddy();
  });
}
//: Checked once a little after start, and again a minute later in case the
//: app was still locked.
setTimeout(() => nameMarkBuddyHint(), 20000);
setTimeout(() => nameMarkBuddyHint(), 80000);
