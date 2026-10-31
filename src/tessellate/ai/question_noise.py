"""A question typed the way people type: slang, typos, run-together words.

Asked for by the owner (INBOX 741): "does it cover any and ALL typos, maybe
use similarity or meaning, cover all slang like pls, ty, lol, u, r, wym,
etc?". The composer reads a question's kind (when, why, how many, a
comparison) from its words, so a question typed "whenis teh dentist rn pls"
must reach it as "when is the dentist right now please". Three layers, each
tested, each leaving the person's subject words as they typed them:

1. **Slang and text-speak** (`SLANG`, `SOCIAL`): a table, one entry per
   word, spelled out; pleasantries and laughter ("ty", "lol") are small
   talk, answered as such rather than searched for.
2. **Typo repair** (`repair`): a weighted edit distance against the
   composer's own small vocabulary of asking words (`VOCABULARY`), with a
   neighbouring key, a doubled letter and a swap of two letters cheaper
   than any other edit, scaled to the word's length; words run together
   ("whenis") split and words split ("wh en") joined when the result is
   an asking word. A real word near an asking word ("then", "show") is
   never changed. The subject's own typos are put right against the
   notebook's words by the composer (`composer._fit_terms`), for scoring
   only.
3. **Meaning as the fallback** (`guess_kind`): a question no rule read is
   compared with example questions of each kind, by the embedder's cosine
   when one is loaded and by character trigrams when not, and given a kind
   only when one is clearly nearest.

What is still missed is said in `docs/roadmap/archive/agent-remaining/composer-voice-1006.md`
and measured by `tests/_composer_eval.py --noise`.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from tessellate.ai import act_registry, spelling
from tessellate.ai.spelling import distance  # noqa: F401 - re-exported: the speller owns it, so the two modules do not import each other

# --- 1. slang and text-speak ----------------------------------------------------

#: Every entry a word people type for a longer one. Only words that are never
#: anything else in a question: "4" and "2" (numbers in "4 weeks"), "ill",
#: "sat", "sun", "mar" and "may" are left out on purpose.
SLANG: dict[str, str] = {
    # Pronouns, verbs, small words.
    "u": "you", "ya": "you", "yu": "you", "ur": "your", "urs": "yours", "r": "are", "y": "why",
    "yall": "you all", "y'all": "you all", "da": "the", "teh": "the", "dat": "that", "dis": "this",
    "cn": "can", "hv": "have", "hav": "have", "shld": "should", "shud": "should", "cld": "could",
    "cud": "could", "wld": "would", "wud": "would", "mny": "many", "meny": "many", "mch": "much",
    "mor": "more", "lng": "long", "oftn": "often", "wy": "why", "btwn": "between", "betw": "between",
    "shw": "show", "kno": "know", "knw": "know", "ne": "any", "evry": "every", "abt": "about", "bout": "about", "abour": "about", "b4": "before", "w/": "with",
    "w/o": "without", "thru": "through", "tho": "though", "altho": "although", "bc": "because",
    "b/c": "because", "cuz": "because", "coz": "because", "cos": "because", "bcuz": "because",
    "becuz": "because", "v": "very", "rly": "really", "rlly": "really", "prolly": "probably",
    "prob": "probably", "def": "definitely", "deffo": "definitely", "obvs": "obviously",
    "obv": "obviously", "obvi": "obviously", "srsly": "seriously", "lil": "little", "ne1": "anyone",
    "any1": "anyone", "some1": "someone", "every1": "everyone", "no1": "no one", "sum1": "someone",
    # Question words.
    "wat's": "what's", "wat": "what", "wot": "what", "wut": "what", "wht": "what", "wha": "what", "whut": "what",
    "whn": "when", "wen": "when", "wn": "when", "hw": "how", "hu": "who", "wher": "where",
    "whr": "where", "wer": "where", "whats": "what is", "wats": "what is", "hows": "how is",
    "wheres": "where is", "whens": "when is", "whos": "who is", "whys": "why is",
    "wym": "what do you mean", "yk": "you know", "wdym": "what do you mean", "wbu": "what about you",
    "hbu": "how about you",
    # Contractions typed without the apostrophe.
    "im": "I am", "ive": "I have", "dont": "do not", "didnt": "did not", "doesnt": "does not",
    "cant": "cannot", "wont": "will not", "isnt": "is not", "wasnt": "was not", "arent": "are not",
    "werent": "were not", "havent": "have not", "hasnt": "has not", "hadnt": "had not",
    "shouldnt": "should not", "couldnt": "could not", "wouldnt": "would not", "youre": "you are",
    "theyre": "they are", "thats": "that is", "theres": "there is", "aint": "is not",
    # Spoken run-togethers.
    "gonna": "going to", "wanna": "want to", "gotta": "got to", "kinda": "kind of",
    "sorta": "sort of", "lemme": "let me", "gimme": "give me", "dunno": "do not know",
    "tryna": "trying to", "outta": "out of", "lotta": "lot of", "whatcha": "what are you",
    "gotcha": "got it", "wassup": "what is up",
    # Abbreviations of a phrase.
    "idk": "I do not know", "idc": "I do not care", "imo": "in my opinion", "imho": "in my opinion",
    "tbh": "to be honest", "tbf": "to be fair", "ngl": "not going to lie", "rn": "right now",
    "atm": "at the moment", "nvm": "never mind", "fyi": "for your information", "btw": "by the way",
    "asap": "as soon as possible", "jk": "just kidding", "irl": "in real life",
    "iirc": "if I remember correctly", "afaik": "as far as I know", "tldr": "in short",
    "tl;dr": "in short", "ofc": "of course", "eta": "expected time", "smth": "something",
    "sth": "something", "smthn": "something", "smthng": "something", "pls": "please",
    "plz": "please", "plss": "please", "pleez": "please", "plox": "please",
    # Time.
    "2day": "today", "2nite": "tonight", "tonite": "tonight", "2moro": "tomorrow",
    "2morrow": "tomorrow", "tmrw": "tomorrow", "tmr": "tomorrow", "tmw": "tomorrow",
    "tmrow": "tomorrow", "2mrw": "tomorrow", "yday": "yesterday", "ystd": "yesterday",
    "wk": "week", "wks": "weeks", "wkend": "weekend", "wknd": "weekend", "yr": "year",
    "yrs": "years", "hr": "hour", "hrs": "hours", "mins": "minutes", "secs": "seconds",
    "l8r": "later", "l8": "late", "nxt": "next", "lst": "last", "prev": "previous",
    "mon": "Monday", "tue": "Tuesday", "tues": "Tuesday", "weds": "Wednesday", "thu": "Thursday",
    "thur": "Thursday", "thurs": "Thursday", "fri": "Friday", "feb": "February", "apr": "April",
    "aug": "August", "sept": "September", "oct": "October", "nov": "November", "dec": "December",
    "xmas": "Christmas", "bday": "birthday", "b-day": "birthday", "til": "till",
    # Things.
    "msg": "message", "msgs": "messages", "txt": "text", "pic": "picture", "pics": "pictures",
    "vid": "video", "vids": "videos", "info": "information", "appt": "appointment",
    "appts": "appointments", "mtg": "meeting", "mtgs": "meetings", "mgr": "manager",
    "dept": "department", "govt": "government", "hmwk": "homework", "ppl": "people",
    "peeps": "people", "bf": "boyfriend", "gf": "girlfriend", "bff": "best friend",
    "fam": "family", "sis": "sister", "convo": "conversation", "fave": "favourite",
    "fav": "favourite", "uni": "university", "pwd": "password", "pw": "password",
    "addr": "address", "num": "number", "nums": "numbers", "qty": "quantity", "amt": "amount",
    "approx": "approximately", "est": "estimated", "avg": "average", "dr": "doctor",
    "docs": "documents", "ref": "reference",
    "luv": "love", "gud": "good", "gr8": "great", "h8": "hate", "m8": "mate", "ez": "easy",
    "kewl": "cool", "pressie": "present", "brekkie": "breakfast", "sarnie": "sandwich",
}

#: The second slang table (2026-10-06, the owner: "expand its vocabulary"): common
#: misspellings of everyday words, dropped-letter forms and text-speak for time,
#: money, work, study, health, travel, home, people, feelings, tasks and places.
#: Same rule as above: only forms that are never anything else in a question.
SLANG.update({
    #: "mu" is "my" one key over (the owner's "what have i writtne about mu uni classes").
    "mu": "my",
    "hte": "the", "adn": "and", "nad": "and", "taht": "that", "waht": "what", "wich": "which",
    "whihc": "which", "wihch": "which", "whcih": "which", "becasue": "because", "becuase": "because",
    "beacuse": "because", "bcoz": "because", "thier": "their", "yer": "your", "recieve": "receive",
    "definately": "definitely", "definatly": "definitely", "seperate": "separate", "occured": "occurred",
    "untill": "until", "wierd": "weird", "alot": "a lot", "alrite": "all right", "abit": "a bit",
    "atleast": "at least", "infront": "in front", "incase": "in case", "aswell": "as well", "aslo": "also",
    "thnk": "think", "thng": "thing", "thngs": "things", "evrything": "everything",
    "evrythng": "everything", "evryone": "everyone", "evryday": "every day", "anythng": "anything",
    "nothng": "nothing", "nthng": "nothing", "sumthin": "something", "somthing": "something",
    "somethin": "something", "anythin": "anything", "nuthin": "nothing", "nothin": "nothing",
    "doin": "doing", "goin": "going", "gettin": "getting", "lookin": "looking", "thinkin": "thinking",
    "wonderin": "wondering", "tryin": "trying", "askin": "asking", "talkin": "talking", "sayin": "saying",
    "meetin": "meeting", "bookin": "booking", "writin": "writing", "waitin": "waiting", "havin": "having",
    "makin": "making", "takin": "taking", "comin": "coming", "leavin": "leaving", "coulda": "could have",
    "shoulda": "should have", "woulda": "would have", "musta": "must have", "mighta": "might have",
    "hafta": "have to", "oughta": "ought to", "supposta": "supposed to", "useta": "used to",
    "finna": "going to", "boutta": "about to", "cuppa": "cup of", "whatchu": "what are you",
    "watcha": "what are you", "dontcha": "do not you", "betcha": "bet you", "letme": "let me",
    "gimmie": "give me", "wouldve": "would have", "couldve": "could have", "shouldve": "should have",
    "mustve": "must have", "mightve": "might have", "weve": "we have", "theyve": "they have",
    "youve": "you have", "youll": "you will", "theyll": "they will", "whatll": "what will",
    "itll": "it will", "thatll": "that will", "itd": "it would", "thatd": "that would",
    "mustnt": "must not", "neednt": "need not", "dosnt": "does not", "dosent": "does not",
    "dident": "did not", "wudnt": "would not", "cudnt": "could not", "shudnt": "should not",
    "havnt": "have not", "cnt": "cannot", "dnt": "do not", "whatre": "what are", "tdy": "today",
    "tday": "today", "tmmrw": "tomorrow", "tomorow": "tomorrow", "tommorow": "tomorrow",
    "thrity": "thirty", "thirtey": "thirty", "thirthy": "thirty", "fiften": "fifteen", "fithteen": "fifteen",
    "twnty": "twenty", "tomorro": "tomorrow", "tomoz": "tomorrow", "tmz": "tomorrow", "2mro": "tomorrow", "tonyt": "tonight",
    "tnite": "tonight", "tngt": "tonight", "yest": "yesterday", "yesterdy": "yesterday",
    "yestday": "yesterday", "morn": "morning", "mornin": "morning", "evng": "evening", "aftn": "afternoon",
    "arvo": "afternoon", "wkly": "weekly", "mthly": "monthly", "mth": "month", "mths": "months",
    "mnth": "month", "mnths": "months", "dly": "daily", "yrly": "yearly", "wknds": "weekends",
    "wkends": "weekends", "wkdy": "weekday", "wkdys": "weekdays", "qtr": "quarter", "qtrs": "quarters",
    "wensday": "Wednesday", "wendsday": "Wednesday", "wednsday": "Wednesday", "thursdy": "Thursday",
    "firday": "Friday", "fryday": "Friday", "saterday": "Saturday", "satday": "Saturday", "mondy": "Monday",
    "tuesdy": "Tuesday", "tusday": "Tuesday", "febuary": "February", "feburary": "February",
    "decemeber": "December", "novemeber": "November", "septmber": "September", "janurary": "January",
    "januray": "January", "midnite": "midnight", "sibs": "siblings", "hubby": "husband", "wifey": "wife",
    "collegue": "colleague", "cowrker": "coworker", "mngr": "manager", "mgmt": "management",
    "acct": "account", "accts": "accounts", "biz": "business", "bizness": "business", "tix": "tickets",
    "tkt": "ticket", "tkts": "tickets", "hotle": "hotel", "hotal": "hotel", "airprt": "airport",
    "arprt": "airport", "flt": "flight", "flite": "flight", "flts": "flights", "pssprt": "passport",
    "lugage": "luggage", "bagage": "baggage", "accomodation": "accommodation",
    "acommodation": "accommodation", "restaraunt": "restaurant", "restraunt": "restaurant",
    "resto": "restaurant", "bkfst": "breakfast", "brekky": "breakfast", "brekfast": "breakfast",
    "lnch": "lunch", "dinr": "dinner", "dinnr": "dinner", "grocs": "groceries", "veggies": "vegetables",
    "meds": "medication", "perscription": "prescription", "dentst": "dentist", "docter": "doctor",
    "doctr": "doctor", "docotr": "doctor", "hospitl": "hospital", "pharmcy": "pharmacy",
    "apmt": "appointment", "appoinment": "appointment", "apointment": "appointment",
    "appointmnt": "appointment", "mtng": "meeting", "mting": "meeting", "calender": "calendar",
    "calandar": "calendar", "sched": "schedule", "schedual": "schedule", "shedule": "schedule",
    "rmndr": "reminder", "rmnd": "remind", "remmber": "remember", "rember": "remember",
    "remeber": "remember", "rmbr": "remember", "forgt": "forgot", "frgt": "forgot", "frgot": "forgot",
    "frst": "first", "scnd": "second", "thrd": "third", "thse": "these", "thos": "those", "tht": "that",
    "wiht": "with", "wtih": "with", "wih": "with", "frm": "from", "fom": "from", "abotu": "about",
    "aobut": "about", "abuot": "about", "abou": "about", "aboot": "about", "aroud": "around",
    "arnd": "around", "btween": "between", "betwen": "between", "bewteen": "between",
    "diferrence": "difference", "diference": "difference", "differnce": "difference",
    "differnt": "different", "diffrent": "different", "diferent": "different", "compair": "compare",
    "compre": "compare", "comapre": "compare", "comparision": "comparison", "compairson": "comparison",
    "versis": "versus", "verus": "versus", "bttr": "better", "betr": "better", "btr": "better",
    "cheeper": "cheaper", "cheapr": "cheaper", "chepr": "cheaper", "fastr": "faster", "fster": "faster",
    "slwr": "slower", "bgr": "bigger", "smlr": "smaller", "lrgr": "larger", "lngr": "longer",
    "shrtr": "shorter", "advantges": "advantages", "disadvantges": "disadvantages", "expnsive": "expensive",
    "expesive": "expensive", "expensiv": "expensive", "mney": "money", "pmt": "payment", "pymt": "payment",
    "pymnt": "payment", "paymnt": "payment", "payed": "paid", "invce": "invoice", "invoce": "invoice",
    "recpt": "receipt", "reciept": "receipt", "recipt": "receipt", "subscrip": "subscription",
    "bdgt": "budget", "budjet": "budget", "bugdet": "budget", "budgt": "budget", "dposit": "deposit",
    "depost": "deposit", "deposite": "deposit", "refnd": "refund", "mortage": "mortgage",
    "morgage": "mortgage", "insurnce": "insurance", "insurence": "insurance", "salry": "salary",
    "salery": "salary", "savngs": "savings", "svngs": "savings", "bnk": "bank", "acount": "account",
    "accout": "account", "accnt": "account", "xfer": "transfer", "trnsfr": "transfer",
    "tranfer": "transfer", "txn": "transaction", "txns": "transactions", "prj": "project",
    "projet": "project", "pln": "plan", "plns": "plans", "tsk": "task", "tsks": "tasks",
    "dline": "deadline", "ddl": "deadline", "deadine": "deadline", "dedline": "deadline",
    "ddline": "deadline", "mstone": "milestone", "mlstn": "milestone", "docmnt": "document",
    "reqs": "requirements", "feedbck": "feedback", "fdbk": "feedback", "feeback": "feedback",
    "assgnmnt": "assignment", "assignmnt": "assignment", "assignement": "assignment", "assgn": "assignment",
    "hwk": "homework", "exm": "exam", "exms": "exams", "examn": "exam", "excersise": "exercise",
    "excercise": "exercise", "exersize": "exercise", "essy": "essay", "lectre": "lecture",
    "semestr": "semester", "tutorail": "tutorial", "tchr": "teacher", "teachr": "teacher",
    "teacer": "teacher", "stdnt": "student", "studnt": "student", "stdnts": "students", "colege": "college",
    "unvrsty": "university", "univeristy": "university", "degre": "degree", "grde": "grade",
    "grdes": "grades", "mrks": "marks", "stdy": "study", "studdy": "study", "studing": "studying",
    "stdying": "studying", "revisn": "revision", "revisin": "revision", "intrvw": "interview",
    "intervew": "interview", "interveiw": "interview", "recrtr": "recruiter", "resum": "resume",
    "reume": "resume", "promtn": "promotion", "wfh": "working from home", "ooo": "out of office",
    "pto": "paid time off", "eod": "end of day", "eow": "end of week", "eom": "end of month",
    "eoy": "end of year", "lgtm": "looks good to me", "nbd": "no big deal", "tba": "to be announced",
    "tbc": "to be confirmed", "tbd": "to be decided", "fwiw": "for what it is worth",
    "iow": "in other words", "afk": "away from keyboard", "omw": "on my way", "otw": "on the way",
    "hmu": "hit me up", "lmk": "let me know", "wdyt": "what do you think", "hbd": "happy birthday",
    "gtg": "got to go", "g2g": "got to go", "bbl": "be back later", "bbs": "be back soon",
    "idek": "I do not even know", "plis": "please", "pliz": "please", "mayb": "maybe", "mabye": "maybe",
    "mybe": "maybe", "perhps": "perhaps", "prhps": "perhaps", "probly": "probably", "probbly": "probably",
    "prbly": "probably", "prbbly": "probably", "possbl": "possible", "necessry": "necessary",
    "neccesary": "necessary", "necesary": "necessary", "importnt": "important", "imprtnt": "important",
    "impt": "important", "urgnt": "urgent", "absolutly": "absolutely", "totes": "totally",
    "defs": "definitely", "espec": "especially", "gnrl": "general", "genral": "general",
    "gnrly": "generally", "usualy": "usually", "usally": "usually", "normaly": "normally",
    "aprox": "approximately", "aproximately": "approximately", "hapy": "happy", "hppy": "happy",
    "angy": "angry", "stressd": "stressed", "stresed": "stressed", "tird": "tired", "tirde": "tired",
    "exhaustd": "exhausted", "excitd": "excited", "exicted": "excited", "worrid": "worried",
    "wrried": "worried", "wrry": "worry", "nervus": "nervous", "overwelmed": "overwhelmed",
    "ovrwhlmd": "overwhelmed", "thankfull": "thankful", "fustrated": "frustrated",
    "frustrted": "frustrated", "annoyd": "annoyed", "confusd": "confused", "confuzed": "confused",
    "hlth": "health", "helth": "health", "wrkout": "workout", "wrkt": "workout", "exercize": "exercise",
    "vaca": "vacation", "vacay": "vacation", "vacaton": "vacation", "holliday": "holiday",
    "holdiay": "holiday", "hoilday": "holiday", "trvl": "travel", "travle": "travel",
    "trvling": "travelling", "itin": "itinerary", "itinary": "itinerary", "itinerery": "itinerary",
    "abnb": "airbnb", "rntl": "rental", "rentl": "rental", "hse": "house", "hous": "house",
    "aprtmnt": "apartment", "apartmnt": "apartment", "apartement": "apartment", "appartment": "apartment",
    "aprtment": "apartment", "lndlrd": "landlord", "landlrd": "landlord", "lanlord": "landlord",
    "tenat": "tenant", "furnitue": "furniture", "furnature": "furniture", "furnitre": "furniture",
    "frnitr": "furniture", "kitchn": "kitchen", "kitchin": "kitchen", "bathrm": "bathroom",
    "bdrm": "bedroom", "bedrm": "bedroom", "bdrms": "bedrooms", "gardn": "garden", "gardan": "garden",
    "garge": "garage", "garag": "garage", "repiar": "repair", "repar": "repair", "plumbr": "plumber",
    "plumer": "plumber", "electrcian": "electrician", "electrican": "electrician",
    "contractr": "contractor", "utlities": "utilities", "internt": "internet", "frnd": "friend",
    "frnds": "friends", "freind": "friend", "freinds": "friends", "frend": "friend", "frens": "friends",
    "fren": "friend", "partnr": "partner", "huband": "husband", "husbnd": "husband", "mothr": "mother",
    "fathr": "father", "brothr": "brother", "sistr": "sister", "cousn": "cousin", "cusin": "cousin",
    "gparents": "grandparents", "granparents": "grandparents", "prnts": "parents", "parnts": "parents",
    "kidz": "kids", "chldrn": "children", "childen": "children", "neighbr": "neighbour",
    "nieghbour": "neighbour", "neibour": "neighbour", "colleage": "colleague", "colleagu": "colleague",
    "persn": "person", "peple": "people", "poeple": "people", "pepole": "people", "peopel": "people",
    "ppls": "people", "som1": "someone", "evry1": "everyone", "evrybody": "everybody",
    "evrybdy": "everybody", "sombody": "somebody", "sumbdy": "somebody", "anybdy": "anybody",
    "nobdy": "nobody", "nbdy": "nobody", "locn": "location", "lcation": "location", "locaton": "location",
    "adress": "address", "adresse": "address", "addres": "address", "ofice": "office", "offce": "office",
    "ofis": "office", "wrkplace": "workplace", "statn": "station", "mseum": "museum", "musuem": "museum",
    "musem": "museum", "libary": "library", "librry": "library", "lbrary": "library",
    "supermkt": "supermarket", "cty": "city", "citty": "city", "cntry": "country", "countery": "country",
    "contry": "country", "twn": "town", "nbrhd": "neighbourhood", "neighbourhod": "neighbourhood",
    "neighbrhood": "neighbourhood", "dwntwn": "downtown", "intl": "international",
    "destnation": "destination", "destinaton": "destination", "deliv": "delivery", "delivry": "delivery",
    "delivary": "delivery", "dlvry": "delivery", "shpmt": "shipment", "shiping": "shipping",
    "shpng": "shipping", "ordr": "order",
})

#: Words that are small talk on their own: a message made only of these is
#: answered as small talk (`composer.social`), never searched for. The value
#: is the kind of reply.
SOCIAL: dict[str, str] = {
    "ty": "thanks", "tysm": "thanks", "tyvm": "thanks", "thx": "thanks", "thnx": "thanks",
    "thnks": "thanks", "tx": "thanks", "thanx": "thanks", "ta": "thanks", "cheers": "thanks",
    "thanks": "thanks", "thank": "thanks", "you": "thanks", "so": "thanks", "much": "thanks",
    "lol": "laugh", "lmao": "laugh", "lmfao": "laugh", "rofl": "laugh", "haha": "laugh",
    "hahaha": "laugh", "hehe": "laugh", "xd": "laugh", "lolz": "laugh", "lolol": "laugh",
    "np": "ack", "nw": "ack", "yw": "ack", "gg": "ack", "k": "ack", "kk": "ack", "ok": "ack",
    "okk": "ack", "okie": "ack", "oki": "ack", "okay": "ack", "cool": "ack", "nice": "ack",
    "ikr": "ack", "omg": "reaction", "wow": "reaction", "yep": "ack", "yup": "ack", "yeah": "ack",
    "yea": "ack", "nah": "ack", "nope": "ack", "jk": "ack", "nvm": "ack", "fair": "ack",
    "gm": "morning", "gn": "bye", "gnight": "bye", "brb": "bye", "cya": "bye", "ttyl": "bye",
    "bye": "bye", "byee": "bye", "later": "bye", "hiya": "greeting", "hi": "greeting",
    "hii": "greeting", "hiii": "greeting", "hey": "greeting", "heyy": "greeting",
    "heyyy": "greeting", "yo": "greeting", "sup": "greeting", "hello": "greeting",
    "wassup": "how", "wbu": "how", "hbu": "how", "xoxo": "bye", "ily": "thanks",
    "sorry": "sorry", "soz": "sorry", "sry": "sorry",
}

#: Words that ride along with small talk without making it a question:
#: "ty for the help", "thanks a lot mate".
_SOCIAL_FILLER = frozenset(
    "for the a lot help helping that this it again man mate bro dude buddy friend all very really much so"
    #: "i'm tired" is tiredness and "you're useless" a complaint, not "ok"
    #: (measured 2026-10-11: both read as an acknowledgement).
    " i i'm im am feel feeling you're youre ur bot was today too tbh".split()
)

SLANG.update({
    #: Common English misspellings (the owner, 2026-10-07: "are common typos all accounted for??").
    "realy": "really",
    "ro": "or",
    "beleive": "believe",
    "belive": "believe",
    "acheive": "achieve",
    "accomodate": "accommodate",
    "acommodate": "accommodate",
    "agian": "again",
    "aginst": "against",
    "allready": "already",
    "anual": "annual",
    "apparantly": "apparently",
    "appearence": "appearance",
    "arguement": "argument",
    "basicly": "basically",
    "begining": "beginning",
    "beleif": "belief",
    "bizzare": "bizarre",
    "buisness": "business",
    "catagory": "category",
    "cemetary": "cemetery",
    "chnage": "change",
    "cheif": "chief",
    "comming": "coming",
    "commitee": "committee",
    "completly": "completely",
    "concious": "conscious",
    "curiousity": "curiosity",
    "decison": "decision",
    "dissapear": "disappear",
    "dissapoint": "disappoint",
    "embarass": "embarrass",
    "enviroment": "environment",
    "existance": "existence",
    "experiance": "experience",
    "familar": "familiar",
    "finaly": "finally",
    "foriegn": "foreign",
    "frist": "first",
    "goverment": "government",
    "gaurd": "guard",
    "happend": "happened",
    "harrass": "harass",
    "hieght": "height",
    "immediatly": "immediately",
    "independant": "independent",
    "interupt": "interrupt",
    "knowlege": "knowledge",
    "liason": "liaison",
    "lisence": "licence",
    "maintainance": "maintenance",
    "managment": "management",
    "millenium": "millennium",
    "mispell": "misspell",
    "neccessary": "necessary",
    "necessery": "necessary",
    "noticable": "noticeable",
    "occassion": "occasion",
    "occurence": "occurrence",
    "ommit": "omit",
    "oppurtunity": "opportunity",
    "orignal": "original",
    "peice": "piece",
    "persistant": "persistent",
    "posession": "possession",
    "prefered": "preferred",
    "presense": "presence",
    "probaly": "probably",
    "proffesional": "professional",
    "promiss": "promise",
    "publically": "publicly",
    "recomend": "recommend",
    "reccomend": "recommend",
    "refered": "referred",
    "relevent": "relevant",
    "religous": "religious",
    "resistence": "resistance",
    "responsability": "responsibility",
    "rythm": "rhythm",
    "sentance": "sentence",
    "similiar": "similar",
    "sincerly": "sincerely",
    "speach": "speech",
    "stoped": "stopped",
    "succesful": "successful",
    "suprise": "surprise",
    "tatoo": "tattoo",
    "tendancy": "tendency",
    "therefor": "therefore",
    "threshhold": "threshold",
    "tounge": "tongue",
    "truely": "truly",
    "twelth": "twelfth",
    "tyrany": "tyranny",
    "underate": "underrate",
    "unfortunatly": "unfortunately",
    "vaccum": "vacuum",
    "vegtable": "vegetable",
    "wether": "whether",
    "whereever": "wherever",
    "writting": "writing",
    "writen": "written",
    "youre": "you're",
    "thru": "through",
    "tho": "though",
    "infact": "in fact",
    "eachother": "each other",
    "nevermind": "never mind",
})

#: Laughter typed long ("hahahaha", "lmaooo", "lollll").
_LAUGH = re.compile(r"^(?:(?:ha|he|ah){2,}h?|lo+l+(?:o+l+)*|lmf?a+o+|xd+)$", re.I)
#: One range for the supplementary symbols block: a second range inside it
#: (U+1F900 to U+1F9FF) was redundant (CodeQL #551, overly large range).
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002300-\U000023FF\U0000FE0F\U0000200D]+"
)
#: Emoticons, read as small talk too.
_EMOTICON = re.compile(r"(?:^|\s)(?:[:;=8][-']?[)(DPp/\\|*]+|<3|\^_?\^)(?=\s|$)")


#: Keys hit by accident at a sentence's edge (INBOX 801, the owner: "it
#: doesnt account for accidental extra characters like a backslash"): a stray
#: `\\`, `|`, backtick, `~` or `^` against a word. One beside a colon or a
#: semicolon is an emoticon (":\\", ";|") and stays.
_STRAY_KEYS = "\\|`~^"
_BEFORE_STRAY = "?.!)\"'"
_STRAY_HEAD = re.compile(r"^\s*[\\|`~^]+(?=\w)")
_RUN_OF_SPACES = re.compile(r"[ \t]{2,}")


_ARCHIVED_WORD = re.compile(r"\barchived\b", re.I)


def asks_archived(question: str) -> bool:
    """Whether the question is about archived notes ("archived notes from last
    week"); any other list or count leaves them out."""
    return bool(_ARCHIVED_WORD.search(question or ""))


def _strip_stray_tail(text: str) -> str:
    """The trailing stray keys off a text, by a scan from the end rather than a
    regex: an anchored-at-the-end pattern rescans a long run of backslashes
    from every start (CodeQL, polynomial regex on user input). A run of stray
    keys goes when a word, a space or closing punctuation stands before it; a
    run of slashes only after a sentence's end ("why?/")."""
    body = text.rstrip()
    end = len(body)
    start = end
    while start > 0 and body[start - 1] in _STRAY_KEYS:
        start -= 1
    if start < end and start > 0 and (body[start - 1].isalnum() or body[start - 1] == "_" or body[start - 1].isspace() or body[start - 1] in _BEFORE_STRAY):
        return body[:start]
    start = end
    while start > 0 and body[start - 1] == "/":
        start -= 1
    if start < end and start > 0 and body[start - 1] in "?.!":
        return body[:start]
    return text


def strip_strays(text: str) -> str:
    """Stray keys off a text's edges and runs of spaces made one; nothing
    else changes (a tool's argument, INBOX 808)."""
    text = _STRAY_HEAD.sub("", _strip_stray_tail(str(text or "")))
    return _RUN_OF_SPACES.sub(" ", text).strip()


def tidy(text: str) -> str:
    """A question as it was meant before anything reads it (INBOX 801): stray
    keys off its edges, runs of spaces made one (line breaks kept, a pasted
    passage keeps its shape), and a sentence typed all in capitals
    ("NOTEBOOK STATS") put in lower case. One capitalised word ("NASA") is a
    name and stays. Words are never changed here: `repair` does that, for
    the readers that want it."""
    text = strip_strays(text)
    words = re.findall(r"[A-Za-z]{2,}", text)
    if len(words) >= 2 and len(text) <= 200 and not re.search(r"[a-z]", text):
        text = text.lower()
    return text


def strip_symbols(text: str) -> str:
    """Emoji and emoticons off, the rest kept."""
    text = _EMOJI.sub(" ", text or "")
    text = _EMOTICON.sub(" ", text)
    return " ".join(text.split())


#: The asking words before a topic ("what is there about", "search my notes
#: for"), taken off to leave the topic a search_notes call is given.
_ASKING_HEAD = re.compile(
    r"^(?:(?:can|could|would) you |please )?(?:what(?:'s| is)? (?:there |do i have |have i got |did i write )?(?:about|on)|"
    r"search (?:my |the )?(?:notes? )?(?:for|about)|search|find (?:my )?(?:notes? )?(?:about|on)?|look (?:for|up)|"
    r"(?:show|list) (?:me )?(?:my )?notes? (?:about|on)|notes? (?:about|on)|anything (?:about|on))(?:\s+|$)",
    re.I,
)


def topic_of(text: str) -> str:
    """The topic a request names, cleaned (`tidy`), with its
    asking words and trailing punctuation off: "what is there about dentist\\"
    gives "dentist". "" when nothing is left."""
    #: The agent's user message carries the notes first and the request
    #: last, after "My request: " (`agent.build_agent_messages`).
    text = str(text or "").rsplit("My request: ", 1)[-1]
    words = _ASKING_HEAD.sub("", tidy(text).strip(" ?.!,;:")).strip(" ?.!,;:")
    return re.sub(r"^(?:the|my|our|a|an)\s+", "", words, flags=re.I)


#: Conversational turns of more than one word, read whole (INBOX 741, the
#: owner: "k is also ok", "right ok", "alright. any and all conversational
#: messages"). Longest first, so "wait what" is confusion before "what" is
#: anything at all.
SOCIAL_PHRASES: dict[str, str] = {
    "got it": "ack", "makes sense": "ack", "that makes sense": "ack", "sounds good": "ack",
    "right ok": "ack", "ok right": "ack", "fair enough": "ack", "all good": "ack", "no worries": "ack",
    "never mind": "ack", "fair point": "ack", "good to know": "ack", "i see": "ack", "ah i see": "ack",
    "oh ok": "ack", "oh okay": "ack", "ok cool": "ack", "cool cool": "ack", "will do": "ack",
    "that works": "ack", "perfect thanks": "thanks", "thank you": "thanks", "thanks a lot": "thanks",
    "appreciate it": "thanks", "much appreciated": "thanks", "thanks so much": "thanks",
    "good morning": "morning", "morning all": "morning", "good afternoon": "greeting",
    "good evening": "greeting", "good night": "bye", "see you": "bye", "see ya": "bye",
    "talk later": "bye", "talk to you later": "bye", "catch you later": "bye", "im off": "bye",
    "how are you": "how", "how r u": "how", "how are u": "how", "how r you": "how", "hows it going": "how",
    "how is it going": "how", "how's it going": "how", "whats up": "how", "what's up": "how",
    "what is up": "how", "how you doing": "how", "how are things": "how", "you good": "how",
    "what are you doing": "how", "what you up to": "how", "what are you up to": "how",
    "my bad": "sorry", "my mistake": "sorry", "sorry about that": "sorry",
    "wait what": "confused", "come again": "confused", "say again": "confused", "sorry what": "confused",
    "i dont get it": "confused", "i don't get it": "confused", "i dont understand": "confused",
    "i don't understand": "confused", "what do you mean": "confused", "what does that mean": "confused",
    "not sure what you mean": "confused", "that doesnt make sense": "confused",
    "that doesn't make sense": "confused", "no idea what that means": "confused",
    "oh no": "reaction", "oh wow": "reaction", "no way": "reaction", "thats great": "reaction",
    "that's great": "reaction", "nice one": "thanks", "well done": "reaction", "oh dear": "reaction",
    "who are you": "who", "whats your name": "who", "what's your name": "who",
    #: A repair: the last reply missed (INBOX 1485). Owned and read again,
    #: never searched for ("not what I asked" found "not asked").
    "not what i asked": "repair", "thats not what i asked": "repair", "that's not what i asked": "repair",
    "that is not what i asked": "repair", "not what i meant": "repair", "thats not what i meant": "repair",
    "that's not what i meant": "repair", "not what i said": "repair", "thats wrong": "repair",
    "that's wrong": "repair", "that is wrong": "repair", "wrong answer": "repair", "no i meant": "repair",
    "you misunderstood": "repair", "you misunderstood me": "repair", "you got it wrong": "repair",
    "you got that wrong": "repair", "thats not right": "repair", "that's not right": "repair",
    "that is not right": "repair", "you misread": "repair", "you misread me": "repair",
    "i didnt ask that": "repair", "i didn't ask that": "repair", "i did not ask that": "repair",
    "not what i was asking": "repair", "thats not it": "repair", "that's not it": "repair",
}

#: One-word turns that are not in `SOCIAL` above: reactions and confusion.
SOCIAL.update({
    "okey": "ack", "alright": "ack", "aight": "ack", "ight": "ack", "right": "ack", "sure": "ack",
    "gotcha": "ack", "word": "ack", "bet": "ack", "noted": "ack", "understood": "ack", "great": "ack",
    "awesome": "ack", "perfect": "ack", "sweet": "ack", "lovely": "ack", "fine": "ack", "agreed": "ack",
    "true": "ack", "same": "ack", "yes": "ack", "no": "ack", "yeh": "ack", "ya": "ack", "mhm": "ack",
    "damn": "reaction", "oof": "reaction", "rip": "reaction", "yikes": "reaction", "whoa": "reaction",
    "woah": "reaction", "ugh": "frustrated", "wild": "reaction", "crazy": "reaction", "dang": "reaction",
    "huh": "confused", "wym": "confused", "wdym": "confused", "eh": "confused", "hm": "confused",
    "hmm": "confused", "hmmm": "confused", "what": "confused", "confused": "confused",
    "wyd": "how", "morning": "morning", "evening": "greeting", "night": "bye", "goodbye": "bye",
    "apologies": "sorry", "oops": "sorry", "appreciated": "thanks", "thankyou": "thanks",
})


#: More one-word turns (2026-10-06, the owner: "expand its vocabulary"): thanks in
#: other languages and spellings, laughter, agreement, reactions, goodbyes,
#: greetings and apologies. A word that is also a slang entry is left out: slang
#: is spelled out first.
SOCIAL.update({
    "thanku": "thanks", "thnku": "thanks", "thankss": "thanks", "tyty": "thanks", "tyy": "thanks",
    "thxx": "thanks", "thks": "thanks", "thankyouu": "thanks", "gracias": "thanks", "danke": "thanks",
    "merci": "thanks", "tku": "thanks", "tnx": "thanks", "cheerio": "bye", "thankful": "thanks",
    "kek": "laugh", "lel": "laugh", "lul": "laugh", "hehehe": "laugh", "bahaha": "laugh",
    "roflmao": "laugh", "lmaoo": "laugh", "hilarious": "laugh", "funny": "laugh",
    "yass": "ack", "yas": "ack", "yess": "ack", "yesss": "ack", "noo": "ack", "nooo": "ack",
    "uhuh": "ack", "righto": "ack", "roger": "ack", "brill": "ack", "brilliant": "ack", "fab": "ack",
    "dope": "ack", "solid": "ack", "nicee": "ack", "coolio": "ack", "yupp": "ack", "yepp": "ack",
    "ohk": "ack", "oky": "ack", "kay": "ack", "kayy": "ack", "indeed": "ack", "exactly": "ack",
    "totally": "ack", "absolutely": "ack", "definitely": "ack", "yessir": "ack", "aye": "ack",
    "okok": "ack", "okayy": "ack", "okies": "ack", "mkay": "ack", "mk": "ack", "mmk": "ack",
    "uhhuh": "ack", "yeahh": "ack", "affirmative": "ack", "negative": "ack", "excellent": "ack",
    "splendid": "ack", "wonderful": "ack", "fantastic": "ack", "terrific": "ack", "super": "ack",
    "jeez": "reaction", "geez": "reaction", "gosh": "reaction", "eek": "reaction", "ouch": "reaction",
    "omfg": "reaction", "omgg": "reaction", "omggg": "reaction", "wowza": "reaction", "woo": "reaction",
    "woohoo": "reaction", "yay": "reaction", "yayy": "reaction", "hooray": "reaction", "phew": "reaction",
    "sheesh": "reaction", "blimey": "reaction", "crikey": "reaction", "bummer": "reaction",
    "dammit": "frustrated", "damnit": "frustrated", "congrats": "reaction", "congratulations": "reaction",
    "laters": "bye", "ttfn": "bye", "peace": "bye", "adios": "bye", "ciao": "bye", "seeya": "bye",
    "gnite": "bye", "nini": "bye", "nite": "bye", "goodnight": "bye", "farewell": "bye",
    "hola": "greeting", "heya": "greeting", "hiyaa": "greeting", "howdy": "greeting",
    "greetings": "greeting", "helloo": "greeting", "hellooo": "greeting", "gday": "greeting",
    "ello": "greeting", "wotcha": "greeting", "salutations": "greeting",
    "gmorning": "morning", "goodmorning": "morning",
    "sowwy": "sorry", "sorryy": "sorry", "sorrry": "sorry", "mybad": "sorry", "pardon": "sorry",
    "hru": "how", "hry": "how",
})
SOCIAL_PHRASES.update({
    "sounds great": "ack", "sounds fine": "ack", "that is fine": "ack", "thats fine": "ack",
    "that's fine": "ack", "okay great": "ack", "ok great": "ack", "ok sure": "ack", "yeah ok": "ack",
    "yes please": "ack", "no thanks": "ack", "not now": "ack", "maybe later": "ack",
    "all right then": "ack", "alright then": "ack", "good stuff": "ack", "great stuff": "ack",
    "thats helpful": "thanks", "that's helpful": "thanks", "that helps": "thanks",
    "that is helpful": "thanks", "very helpful": "thanks", "helpful thanks": "thanks",
    "many thanks": "thanks", "thanks again": "thanks", "thank you so much": "thanks",
    "thanks very much": "thanks", "thanks mate": "thanks", "cheers for that": "thanks",
    "ta very much": "thanks", "big thanks": "thanks", "i appreciate it": "thanks",
    "really appreciate it": "thanks", "thanks for that": "thanks", "thanks for your help": "thanks",
    "thank you very much": "thanks", "thank you kindly": "thanks", "thanks a bunch": "thanks",
    "thanks a million": "thanks", "see you later": "bye", "see you tomorrow": "bye",
    "see you soon": "bye", "speak soon": "bye", "speak later": "bye", "have a good one": "bye",
    "have a nice day": "bye", "have a good day": "bye", "good bye": "bye", "take care": "bye",
    "until next time": "bye", "gotta go": "bye", "got to go": "bye", "i have to go": "bye",
    "i must go": "bye", "goodnight all": "bye", "night night": "bye", "sleep well": "bye",
    "how have you been": "how", "how are you doing": "how", "how is your day": "how",
    "how was your day": "how", "how's your day": "how", "hows your day": "how", "how do you do": "how",
    "you ok": "how", "are you ok": "how", "are you okay": "how", "you alright": "how",
    #: "are u" before ok, good, well or alright is a how-are-you; before
    #: anything else it is not ("are u an ai??" got "Good.", INBOX 1485).
    **{f"{are} {you} {how}": "how" for are in ("are", "r") for you in ("you", "u") for how in ("ok", "okay", "good", "well", "alright", "all right", "doing ok", "doing well", "doing good")},
    "hope you are well": "how", "hope youre well": "how", "hi there": "greeting",
    "hello there": "greeting", "hey there": "greeting", "hey you": "greeting", "good day": "greeting",
    "hi again": "greeting", "hello again": "greeting", "hey again": "greeting", "well hello": "greeting",
    "good morning all": "morning", "morning to you": "morning", "top of the morning": "morning",
    "so sorry": "sorry", "very sorry": "sorry", "sorry mate": "sorry", "apologies for that": "sorry",
    "i apologise": "sorry", "i apologize": "sorry", "pardon me": "sorry", "excuse me": "sorry",
    "forgive me": "sorry", "that is funny": "laugh", "thats funny": "laugh", "that's funny": "laugh",
    "so funny": "laugh", "too funny": "laugh", "made me laugh": "laugh", "ha ha": "laugh",
    "ha ha ha": "laugh", "hee hee": "laugh", "that is great": "reaction", "how nice": "reaction",
    "how lovely": "reaction", "so cool": "reaction", "very cool": "reaction", "that is cool": "reaction",
    "thats cool": "reaction", "that's cool": "reaction", "that is awesome": "reaction",
    "thats awesome": "reaction", "that's awesome": "reaction", "wow nice": "reaction",
    "oh nice": "reaction", "oh cool": "reaction", "oh great": "reaction", "oh good": "reaction",
    "oh well": "reaction", "too bad": "reaction", "that is sad": "reaction", "thats sad": "reaction",
    "that's sad": "reaction", "what a shame": "reaction", "good grief": "reaction",
    "oh my god": "reaction", "oh my gosh": "reaction", "oh my goodness": "reaction",
    "holy cow": "reaction", "holy moly": "reaction", "i dont follow": "confused",
    "i don't follow": "confused", "i am lost": "confused", "im lost": "confused", "i'm lost": "confused",
    "huh what": "confused", "i dont know what you mean": "confused", "what are you saying": "confused",
    "what are you talking about": "confused", "run that by me again": "confused",
    "can you repeat that": "confused", "repeat that": "confused", "can you rephrase": "confused",
    "who is this": "who", "who am i talking to": "who", "what should i call you": "who",
    "what is your name": "who", "tell me your name": "who",
})


#: Added 2026-10-10 from the Gemini branch: misspellings, keyboard slips and
#: text-speak (3973 entries). Filtered: a key that is itself a word in
#: `REAL_WORDS` or the shipped word list (frontend/vendor/wordlist/en.txt) is
#: left out, since repairing it would "correct" a correctly spelt word ("ill",
#: "id", "mid", "loosing", "weather"); so is a key with a space, which
#: `repair` never looks up (it reads one word at a time). The common
#: misspellings among these look to come from Wikipedia's "Lists of common
#: misspellings" (CC BY-SA): see docs/THIRD_PARTY.md.
SLANG.update({
    "broski": "brother", "brotato": "brother", "brotatochip": "brother", "nocap": "no lie",
    "lowkey": "secretly", "highkey": "obviously", "sus": "suspicious", "rizz": "charm",
    "bussin": "great", "yeet": "throw", "skibidi": "crazy", "gyatt": "wow",
    "looksmaxxing": "looking good", "ong": "on god", "smh": "shaking my head", "thx": "thanks",
    "tysm": "thank you so much", "yw": "you are welcome", "ily": "i love you",
    "ikr": "i know right", "brb": "be right back", "abandonned": "abandoned",
    "aberation": "aberration", "abilityes": "abilities", "abilties": "abilities",
    "abilty": "ability", "abondon": "abandon", "abbout": "about", "abscence": "absence",
    "abondoned": "abandoned", "abondoning": "abandoning", "abondons": "abandons",
    "aborigene": "aborigine", "accesories": "accessories", "accidant": "accident",
    "abortificant": "abortifacient", "abreviate": "abbreviate", "abreviated": "abbreviated",
    "abreviation": "abbreviation", "abritrary": "arbitrary", "absail": "abseil",
    "absailing": "abseiling", "absense": "absence", "absorbsion": "absorption",
    "absorbtion": "absorption", "abudance": "abundance", "abundacies": "abundances",
    "abundancies": "abundances", "abundunt": "abundant", "abutts": "abuts", "acadamy": "academy",
    "acadmic": "academic", "accademic": "academic", "accademy": "academy", "acccused": "accused",
    "accelleration": "acceleration", "acceptence": "acceptance", "acceptible": "acceptable",
    "accessable": "accessible", "acident": "accident", "accidentaly": "accidentally",
    "accidently": "accidentally", "acclimitization": "acclimatization", "accomadate": "accommodate",
    "accomadated": "accommodated", "accomadates": "accommodates", "accomadating": "accommodating",
    "accomadation": "accommodation", "accomadations": "accommodations", "accomdate": "accommodate",
    "accomodated": "accommodated", "accomodates": "accommodates", "accomodating": "accommodating",
    "accomodations": "accommodations", "accompanyed": "accompanied", "accordeon": "accordion",
    "accordian": "accordion", "accoring": "according", "accoustic": "acoustic",
    "accquainted": "acquainted", "accrediation": "accreditation", "accredidation": "accreditation",
    "accross": "across", "accussed": "accused", "acedemic": "academic", "acheived": "achieved",
    "acheivement": "achievement", "acheivements": "achievements", "acheives": "achieves",
    "acheiving": "achieving", "acheivment": "achievement", "acheivments": "achievements",
    "achievment": "achievement", "achievments": "achievements", "achivement": "achievement",
    "achivements": "achievements", "acknowldeged": "acknowledged",
    "acknowledgeing": "acknowledging", "acomplish": "accomplish", "acomplished": "accomplished",
    "acomplishment": "accomplishment", "acomplishments": "accomplishments", "acording": "according",
    "acordingly": "accordingly", "acquaintence": "acquaintance", "acquaintences": "acquaintances",
    "acquiantence": "acquaintance", "acquiantences": "acquaintances", "acquited": "acquitted",
    "activites": "activities", "activly": "actively", "actualy": "actually", "acuracy": "accuracy",
    "acused": "accused", "acustom": "accustom", "acustommed": "accustomed", "adavanced": "advanced",
    "adbandon": "abandon", "addional": "additional", "addionally": "additionally",
    "additinally": "additionally", "additionaly": "additionally", "additonal": "additional",
    "additonally": "additionally", "addmission": "admission", "addopt": "adopt",
    "addopted": "adopted", "addoptive": "adoptive", "addresable": "addressable",
    "addresed": "addressed", "addresing": "addressing", "addressess": "addresses",
    "addtion": "addition", "addtional": "additional", "adecuate": "adequate", "adequit": "adequate",
    "adhearing": "adhering", "adherance": "adherence", "admendment": "amendment",
    "admininistrative": "administrative", "adminstered": "administered",
    "adminstrate": "administrate", "adminstration": "administration",
    "adminstrative": "administrative", "adminstrator": "administrator",
    "admissability": "admissibility", "admissable": "admissible", "admited": "admitted",
    "admitedly": "admittedly", "adolecent": "adolescent", "adquire": "acquire",
    "adquired": "acquired", "adquires": "acquires", "adquiring": "acquiring", "adres": "address",
    "adresable": "addressable", "adresing": "addressing", "adressable": "addressable",
    "adressed": "addressed", "adventrous": "adventurous", "advertisment": "advertisement",
    "advertisments": "advertisements", "advesary": "adversary", "adviced": "advised",
    "aeriel": "aerial", "aeriels": "aerials", "afair": "affair", "afficianados": "aficionados",
    "afficionado": "aficionado", "afficionados": "aficionados", "affilate": "affiliate",
    "affilliate": "affiliate", "aforememtioned": "aforementioned", "againnst": "against",
    "agains": "against", "agaisnt": "against", "aganist": "against", "aggaravates": "aggravates",
    "aggreed": "agreed", "aggreement": "agreement", "aggregious": "egregious",
    "aggregrator": "aggregator", "aggresive": "aggressive", "agianst": "against", "agin": "again",
    "agravate": "aggravate", "agre": "agree", "agred": "agreed", "agreeement": "agreement",
    "agreemnt": "agreement", "agregate": "aggregate", "agregates": "aggregates",
    "agreing": "agreeing", "agression": "aggression", "agressive": "aggressive",
    "agressively": "aggressively", "agressor": "aggressor", "agricultue": "agriculture",
    "agriculure": "agriculture", "agricuture": "agriculture", "agrieved": "aggrieved",
    "ahev": "have", "ahppen": "happen", "ahve": "have", "aicraft": "aircraft", "aiport": "airport",
    "airbourne": "airborne", "aircaft": "aircraft", "aircrafts": "aircraft", "airporta": "airports",
    "airrcraft": "aircraft", "aisian": "asian", "albiet": "albeit", "alchohol": "alcohol",
    "alchoholic": "alcoholic", "alchol": "alcohol", "alcholic": "alcoholic", "alcohal": "alcohol",
    "alcoholical": "alcoholic", "aledge": "allege", "aledged": "alleged", "aledges": "alleges",
    "alege": "allege", "aleged": "alleged", "alegience": "allegiance", "algebraical": "algebraic",
    "algorhitms": "algorithms", "algoritm": "algorithm", "algoritms": "algorithms",
    "alientating": "alienating", "alledge": "allege", "alledged": "alleged",
    "alledgedly": "allegedly", "alledges": "alleges", "allegedely": "allegedly",
    "allegedy": "allegedly", "allegely": "allegedly", "allegence": "allegiance",
    "allegience": "allegiance", "allign": "align", "alligned": "aligned", "alliviate": "alleviate",
    "allopone": "allophone", "allopones": "allophones", "allthough": "although",
    "alltogether": "altogether", "almsot": "almost", "alochol": "alcohol", "alomst": "almost",
    "alos": "also", "alotted": "allotted", "alowed": "allowed", "alowing": "allowing",
    "alreayd": "already", "alse": "else", "alsot": "also", "alternitives": "alternatives",
    "althought": "although", "altough": "although", "alwasy": "always", "alwyas": "always",
    "amalgomated": "amalgamated", "amatuer": "amateur", "amendmant": "amendment",
    "amercia": "america", "amerliorate": "ameliorate", "amke": "make", "amking": "making",
    "ammend": "amend", "ammended": "amended", "ammendment": "amendment",
    "ammendments": "amendments", "ammount": "amount", "ammused": "amused", "amoung": "among",
    "amoungst": "amongst", "amung": "among", "amunition": "ammunition", "analagous": "analogous",
    "analitic": "analytic", "analogeous": "analogous", "anarchim": "anarchism",
    "anarchistm": "anarchism", "anbd": "and", "ancestory": "ancestry", "ancilliary": "ancillary",
    "andd": "and", "androgenous": "androgynous", "androgeny": "androgyny",
    "anihilation": "annihilation", "aniversary": "anniversary", "annoint": "anoint",
    "annointed": "anointed", "annointing": "anointing", "annoints": "anoints",
    "annouced": "announced", "annualy": "annually", "annuled": "annulled", "anohter": "another",
    "anomolies": "anomalies", "anomolous": "anomalous", "anomoly": "anomaly",
    "anonimity": "anonymity", "anounced": "announced", "anouncement": "announcement",
    "ansalisation": "nasalisation", "ansalization": "nasalization", "ansestors": "ancestors",
    "antartic": "antarctic", "anthromorphization": "anthropomorphization",
    "anthropolgist": "anthropologist", "anthropolgy": "anthropology", "anulled": "annulled",
    "anwsered": "answered", "anyhwere": "anywhere", "anytying": "anything", "aparent": "apparent",
    "aparment": "apartment", "aplication": "application", "aplied": "applied",
    "apolegetics": "apologetics", "apparant": "apparent", "appart": "apart",
    "appartments": "apartments", "appeareance": "appearance", "appearences": "appearances",
    "apperance": "appearance", "apperances": "appearances", "appereance": "appearance",
    "appereances": "appearances", "applicaiton": "application", "applicaitons": "applications",
    "appologies": "apologies", "appology": "apology", "apprearance": "appearance",
    "apprieciate": "appreciate", "approachs": "approaches", "appropiate": "appropriate",
    "appropraite": "appropriate", "appropropiate": "appropriate", "approproximate": "approximate",
    "approxamately": "approximately", "approxiately": "approximately",
    "approximitely": "approximately", "aprehensive": "apprehensive", "apropriate": "appropriate",
    "aproval": "approval", "aproximate": "approximate", "aquaduct": "aqueduct",
    "aquaintance": "acquaintance", "aquainted": "acquainted", "aquiantance": "acquaintance",
    "aquire": "acquire", "aquired": "acquired", "aquiring": "acquiring",
    "aquisition": "acquisition", "aquitted": "acquitted", "aranged": "arranged",
    "arangement": "arrangement", "arbitarily": "arbitrarily", "arbitary": "arbitrary",
    "archaelogical": "archaeological", "archaelogists": "archaeologists",
    "archaelogy": "archaeology", "archetect": "architect", "archetects": "architects",
    "archetectural": "architectural", "archetecturally": "architecturally",
    "archetecture": "architecture", "archiac": "archaic", "archictect": "architect",
    "archimedian": "archimedean", "architecht": "architect", "architechturally": "architecturally",
    "architechture": "architecture", "architechtures": "architectures",
    "architectual": "architectural", "archtype": "archetype", "archtypes": "archetypes",
    "aready": "already", "areodynamics": "aerodynamics", "argubly": "arguably",
    "arguements": "arguments", "arised": "arose", "arival": "arrival", "armamant": "armament",
    "armistace": "armistice", "arogant": "arrogant", "arogent": "arrogant",
    "arrangment": "arrangement", "arrangments": "arrangements", "arrengement": "arrangement",
    "arrengements": "arrangements", "arround": "around", "artcile": "article", "artical": "article",
    "artice": "article", "articel": "article", "artifical": "artificial",
    "artifically": "artificially", "artillary": "artillery", "arund": "around", "asetic": "ascetic",
    "asign": "assign", "asociated": "associated", "asorbed": "absorbed",
    "asphyxation": "asphyxiation", "assasin": "assassin", "assasinate": "assassinate",
    "assasinated": "assassinated", "assasinates": "assassinates", "assasination": "assassination",
    "assasinations": "assassinations", "assasined": "assassinated", "assasins": "assassins",
    "assassintation": "assassination", "assemple": "assemble", "assertation": "assertion",
    "asside": "aside", "assisnate": "assassinate", "assit": "assist", "assitant": "assistant",
    "assocation": "association", "assoicate": "associate", "assoicated": "associated",
    "assoicates": "associates", "assosication": "assassination", "asssassans": "assassins",
    "assualt": "assault", "assualted": "assaulted", "assymetric": "asymmetric",
    "assymetrical": "asymmetrical", "asteriod": "asteroid", "asthetic": "aesthetic",
    "asthetical": "aesthetical", "asthetically": "aesthetically", "asume": "assume",
    "atain": "attain", "atempting": "attempting", "atheistical": "atheistic",
    "athenean": "athenian", "atheneans": "athenians", "athiesm": "atheism", "athiest": "atheist",
    "atorney": "attorney", "atribute": "attribute", "atributed": "attributed",
    "atributes": "attributes", "attemp": "attempt", "attemped": "attempted", "attemt": "attempt",
    "attemted": "attempted", "attemting": "attempting", "attemts": "attempts",
    "attendence": "attendance", "attendent": "attendant", "attendents": "attendants",
    "attened": "attended", "attension": "attention", "attitide": "attitude",
    "attributred": "attributed", "attrocities": "atrocities", "audeince": "audience",
    "auromated": "automated", "austrailia": "australia", "austrailian": "australian",
    "auther": "author", "authobiographic": "autobiographic", "authobiography": "autobiography",
    "authorative": "authoritative", "authorites": "authorities", "authorithy": "authority",
    "authoritiers": "authorities", "authoritive": "authoritative", "authrorities": "authorities",
    "autochtonous": "autochthonous", "autoctonous": "autochthonous", "automaticly": "automatically",
    "automibile": "automobile", "automonomous": "autonomous", "autor": "author",
    "autority": "authority", "auxilary": "auxiliary", "auxillaries": "auxiliaries",
    "auxillary": "auxiliary", "auxilliaries": "auxiliaries", "auxilliary": "auxiliary",
    "availabe": "available", "availablity": "availability", "availaible": "available",
    "availble": "available", "availiable": "available", "availible": "available",
    "avalable": "available", "avalance": "avalanche", "avaliable": "available",
    "avation": "aviation", "averageed": "averaged", "avilable": "available", "awared": "awarded",
    "awya": "away", "bacame": "became", "baceause": "because", "backgorund": "background",
    "backrounds": "backgrounds", "bakc": "back", "banannas": "bananas", "bandwith": "bandwidth",
    "bankrupcy": "bankruptcy", "banruptcy": "bankruptcy", "basicaly": "basically", "bcak": "back",
    "beachead": "beachhead", "beastiality": "bestiality", "beatiful": "beautiful",
    "beaurocracy": "bureaucracy", "beaurocratic": "bureaucratic", "beautyfull": "beautiful",
    "becamae": "became", "beccause": "because", "becomeing": "becoming", "becomming": "becoming",
    "becouse": "because", "bedore": "before", "beeing": "being", "befoer": "before",
    "begginer": "beginner", "begginers": "beginners", "beggining": "beginning",
    "begginings": "beginnings", "beggins": "begins", "beginnig": "beginning",
    "beleagured": "beleaguered", "beleived": "believed", "beleives": "believes",
    "beleiving": "believing", "beligum": "belgium", "belligerant": "belligerent",
    "bellweather": "bellwether", "bemusemnt": "bemusement", "beneficary": "beneficiary",
    "beng": "being", "benificial": "beneficial", "benifit": "benefit", "benifits": "benefits",
    "bergamont": "bergamot", "bernouilli": "bernoulli", "beseige": "besiege",
    "beseiged": "besieged", "beseiging": "besieging", "beteen": "between", "beween": "between",
    "bigining": "beginning", "biginning": "beginning", "bilateraly": "bilaterally",
    "billingualism": "bilingualism", "binominal": "binomial", "blaim": "blame", "blaimed": "blamed",
    "blessure": "blessing", "blitzkreig": "blitzkrieg", "bodydbuilder": "bodybuilder",
    "bombardement": "bombardment", "bombarment": "bombardment", "bondary": "boundary",
    "bonnano": "bonanno", "boook": "book", "borke": "broke", "boundry": "boundary",
    "bouyancy": "buoyancy", "bouyant": "buoyant", "boyant": "buoyant", "bradcast": "broadcast",
    "brasillian": "brazilian", "breakthough": "breakthrough", "breakthroughts": "breakthroughs",
    "breif": "brief", "breifly": "briefly", "brethen": "brethren", "bretheren": "brethren",
    "briliant": "brilliant", "brillant": "brilliant", "brimestone": "brimstone",
    "britian": "britain", "brittish": "british", "broacasted": "broadcast",
    "broadacasting": "broadcasting", "broady": "broadly", "buddah": "buddha", "buddist": "buddhist",
    "buisnessman": "businessman", "buoancy": "buoyancy", "burried": "buried", "busines": "business",
    "busness": "business", "bussiness": "business", "caculater": "calculator",
    "cacuses": "caucuses", "cahracters": "characters", "calaber": "caliber",
    "calculater": "calculator", "calculs": "calculus", "calenders": "calendars",
    "caligraphy": "calligraphy", "caluclate": "calculate", "caluclated": "calculated",
    "caluculate": "calculate", "caluculated": "calculated", "calulate": "calculate",
    "calulated": "calculated", "calulater": "calculator", "cambrige": "cambridge",
    "camoflage": "camouflage", "campagin": "campaign", "campain": "campaign",
    "campains": "campaigns", "candadate": "candidate", "candiate": "candidate",
    "candidiate": "candidate", "cannister": "canister", "cannisters": "canisters",
    "cannnot": "cannot", "cannonical": "canonical", "cannotation": "connotation",
    "cannotations": "connotations", "caost": "coast", "caperbility": "capability",
    "capible": "capable", "captial": "capital", "captued": "captured", "capturd": "captured",
    "carachter": "character", "caracterized": "characterized", "carefull": "careful",
    "careing": "caring", "carismatic": "charismatic", "carmalite": "carmelite",
    "carnagie": "carnegie", "carnigie": "carnegie", "carreer": "career", "carrers": "careers",
    "carribbean": "caribbean", "carribean": "caribbean", "carryng": "carrying",
    "cartdridge": "cartridge", "carthagian": "carthaginian", "carthographer": "cartographer",
    "cartilege": "cartilage", "cartilidge": "cartilage", "cartrige": "cartridge",
    "casette": "cassette", "casion": "caisson", "cassawory": "cassowary", "cassowarry": "cassowary",
    "casue": "cause", "casued": "caused", "casues": "causes", "casuing": "causing",
    "casulaties": "casualties", "casulaty": "casualty", "catagories": "categories",
    "catagorized": "categorized", "catapillar": "caterpillar", "catapillars": "caterpillars",
    "catapiller": "caterpillar", "catapillers": "caterpillars", "catepillar": "caterpillar",
    "catepillars": "caterpillars", "catergorize": "categorize", "catergorized": "categorized",
    "caterpilar": "caterpillar", "caterpilars": "caterpillars", "caterpiller": "caterpillar",
    "caterpillers": "caterpillars", "cathlic": "catholic", "catholocism": "catholicism",
    "catterpilar": "caterpillar", "catterpilars": "caterpillars", "catterpillar": "caterpillar",
    "catterpillars": "caterpillars", "cattleship": "battleship", "ceasar": "caesar",
    "celcius": "celsius", "cellpading": "cellpadding", "cementary": "cemetery",
    "cemetarey": "cemetery", "cemetaries": "cemeteries", "cencus": "census",
    "cententenial": "centennial", "centruies": "centuries", "centruy": "century",
    "centuties": "centuries", "centuty": "century", "cerimonial": "ceremonial",
    "cerimonies": "ceremonies", "cerimonious": "ceremonious", "cerimony": "ceremony",
    "ceromony": "ceremony", "certaintly": "certainly", "certainity": "certainty",
    "certian": "certain", "chalenging": "challenging", "challange": "challenge",
    "challanged": "challenged", "challege": "challenge", "champange": "champagne",
    "changable": "changeable", "charachter": "character", "charachters": "characters",
    "charactersistic": "characteristic", "charactor": "character", "charactors": "characters",
    "charasmatic": "charismatic", "charaterized": "characterized", "chariman": "chairman",
    "charistics": "characteristics", "cheifs": "chiefs", "chemcial": "chemical",
    "chemcially": "chemically", "chemestry": "chemistry", "chemicaly": "chemically",
    "childbird": "childbirth", "choclate": "chocolate", "choosen": "chosen",
    "chracter": "character", "chuch": "church", "churchs": "churches", "cincinatti": "cincinnati",
    "cincinnatti": "cincinnati", "circulaton": "circulation", "circumsicion": "circumcision",
    "circut": "circuit", "ciricuit": "circuit", "ciriculum": "curriculum", "civillian": "civilian",
    "claer": "clear", "claerer": "clearer", "claerly": "clearly", "claimes": "claims",
    "clas": "class", "clasic": "classic", "clasical": "classical", "clasically": "classically",
    "cleareance": "clearance", "clincial": "clinical", "clinicaly": "clinically", "cmo": "com",
    "cmoputer": "computer", "coctail": "cocktail", "coform": "conform", "cognizent": "cognizant",
    "coincedentally": "coincidentally", "colaborations": "collaborations",
    "colateral": "collateral", "colelctive": "collective", "collaberative": "collaborative",
    "collecton": "collection", "collegues": "colleagues", "collonade": "colonnade",
    "collonies": "colonies", "collony": "colony", "collosal": "colossal",
    "colonizators": "colonizers", "comando": "commando", "comandos": "commandos",
    "comany": "company", "comapany": "company", "comback": "comeback",
    "combanations": "combinations", "combinatins": "combinations", "combusion": "combustion",
    "comdemnation": "condemnation", "comemmorates": "commemorates", "comemoretion": "commemoration",
    "comision": "commission", "comisioned": "commissioned", "comisioner": "commissioner",
    "comisioning": "commissioning", "comisions": "commissions", "comission": "commission",
    "comissioned": "commissioned", "comissioner": "commissioner", "comissioning": "commissioning",
    "comissions": "commissions", "comited": "committed", "comiting": "committing",
    "comitted": "committed", "comittee": "committee", "comitting": "committing",
    "commandoes": "commandos", "commedic": "comedic", "commemerative": "commemorative",
    "commemmorate": "commemorate", "commemmorating": "commemorating", "commerical": "commercial",
    "commerically": "commercially", "commericial": "commercial", "commericially": "commercially",
    "commerorative": "commemorative", "comminication": "communication", "commision": "commission",
    "commisioned": "commissioned", "commisioner": "commissioner", "commisioning": "commissioning",
    "commisions": "commissions", "commited": "committed", "commiting": "committing",
    "committe": "committee", "committment": "commitment", "committments": "commitments",
    "commmemorated": "commemorated", "commongly": "commonly", "commonweath": "commonwealth",
    "commuications": "communications", "commuinications": "communications",
    "communciation": "communication", "communiation": "communication", "communites": "communities",
    "compability": "compatibility", "comparisions": "comparisons", "comparitive": "comparative",
    "comparitively": "comparatively", "compatabilities": "compatibilities",
    "compatability": "compatibility", "compatable": "compatible",
    "compatablities": "compatibilities", "compatablity": "compatibility",
    "compatiable": "compatible", "compatiblities": "compatibilities",
    "compatiblity": "compatibility", "compeitions": "competitions", "compensantion": "compensation",
    "competance": "competence", "competant": "competent", "competative": "competitive",
    "competitiion": "competition", "competive": "competitive", "competiveness": "competitiveness",
    "comphrehensive": "comprehensive", "compitent": "competent", "completelyl": "completely",
    "completetion": "completion", "complier": "compiler", "componant": "component",
    "comprable": "comparable", "comprimise": "compromise", "compulsary": "compulsory",
    "compulsery": "compulsory", "computarized": "computerized", "concensus": "consensus",
    "concider": "consider", "concidered": "considered", "concidering": "considering",
    "conciders": "considers", "concieted": "conceited", "concieved": "conceived",
    "conciously": "consciously", "conciousness": "consciousness", "condamned": "condemned",
    "condemmed": "condemned", "condidtion": "condition", "condidtions": "conditions",
    "conected": "connected", "conection": "connection", "conesencus": "consensus",
    "confidental": "confidential", "confidentally": "confidentially", "confids": "confides",
    "configureable": "configurable", "confortable": "comfortable",
    "congradulations": "congratulations", "congresional": "congressional", "conived": "connived",
    "conjecutre": "conjecture", "conjuction": "conjunction", "conneticut": "connecticut",
    "conotations": "connotations", "conquerd": "conquered", "conquerer": "conqueror",
    "conquerers": "conquerors", "conqured": "conquered", "conscent": "consent",
    "consciouness": "consciousness", "consdider": "consider", "consdidered": "considered",
    "consdiered": "considered", "consectutive": "consecutive", "consenquently": "consequently",
    "consentrate": "concentrate", "consentrated": "concentrated", "consentrates": "concentrates",
    "consept": "concept", "consequentually": "consequently", "consequeseces": "consequences",
    "consern": "concern", "conserned": "concerned", "conserning": "concerning",
    "conservitive": "conservative", "consiciousness": "consciousness",
    "consicousness": "consciousness", "considerd": "considered", "consideres": "considered",
    "consious": "conscious", "consistant": "consistent", "consistantly": "consistently",
    "consituencies": "constituencies", "consituency": "constituency", "consituted": "constituted",
    "consitution": "constitution", "consitutional": "constitutional", "consolodate": "consolidate",
    "consolodated": "consolidated", "consonent": "consonant", "consonents": "consonants",
    "consorcium": "consortium", "conspiracys": "conspiracies", "conspiriator": "conspirator",
    "constaints": "constraints", "constanly": "constantly", "constarnation": "consternation",
    "constatn": "constant", "constinually": "continually", "constituant": "constituent",
    "constituants": "constituents", "constituion": "constitution",
    "constituional": "constitutional", "consttruction": "construction",
    "constuction": "construction", "contstruction": "construction", "consulant": "consultant",
    "consumate": "consummate", "consumated": "consummated", "contaiminate": "contaminate",
    "containes": "contains", "contamporaries": "contemporaries", "contamporary": "contemporary",
    "contempoary": "contemporary", "contemporaneus": "contemporaneous",
    "contempory": "contemporary", "contendor": "contender", "contian": "contain",
    "contians": "contains", "contibute": "contribute", "contibuted": "contributed",
    "contibutes": "contributes", "contigent": "contingent", "contined": "continued",
    "continential": "continental", "continous": "continuous", "continously": "continuously",
    "continueing": "continuing", "contravercial": "controversial", "contraversy": "controversy",
    "contributer": "contributor", "contributers": "contributors", "contritutions": "contributions",
    "controled": "controlled", "controling": "controlling", "controll": "control",
    "controlls": "controls", "controvercial": "controversial", "controvercy": "controversy",
    "controveries": "controversies", "controversal": "controversial", "controversey": "controversy",
    "controvertial": "controversial", "controvery": "controversy", "contruction": "construction",
    "conveinent": "convenient", "convenant": "covenant", "convential": "conventional",
    "convertables": "convertibles", "convertion": "conversion", "conviced": "convinced",
    "convienient": "convenient", "coordiantion": "coordination", "coorperations": "corporations",
    "copmetitors": "competitors", "coputer": "computer", "copywrite": "copyright",
    "coridal": "cordial", "cornmitted": "committed", "corosion": "corrosion",
    "corparate": "corporate", "corperations": "corporations", "correcters": "correctors",
    "correponding": "corresponding", "correposding": "corresponding",
    "correspondant": "correspondent", "correspondants": "correspondents", "corridoors": "corridors",
    "corrispond": "correspond", "corrispondant": "correspondent",
    "corrispondants": "correspondents", "corrisponded": "corresponded",
    "corrisponding": "corresponding", "corrisponds": "corresponds", "costitution": "constitution",
    "coucil": "council", "counries": "countries", "countains": "contains", "countires": "countries",
    "creaeted": "created", "creedence": "credence", "critereon": "criterion",
    "criterias": "criteria", "criticists": "critics", "critisising": "criticising",
    "critisism": "criticism", "critisisms": "criticisms", "critized": "criticized",
    "critizing": "criticizing", "crockodiles": "crocodiles", "crowm": "crown",
    "crtical": "critical", "crticised": "criticised", "crucifiction": "crucifixion",
    "crusies": "cruises", "crutial": "crucial", "crystalisation": "crystallisation",
    "culiminating": "culminating", "cumulatative": "cumulative", "curch": "church",
    "curcuit": "circuit", "currenly": "currently", "curriculem": "curriculum", "cxan": "cyan",
    "cyclinder": "cylinder", "dacquiri": "daiquiri", "daed": "dead", "dalmation": "dalmatian",
    "damenor": "demeanor", "dammage": "damage", "dardenelles": "dardanelles", "daugher": "daughter",
    "debateable": "debatable", "decendant": "descendant", "decendants": "descendants",
    "decendent": "descendant", "decendents": "descendants", "decideable": "decidable",
    "decidely": "decidedly", "decieved": "deceived", "decomissioned": "decommissioned",
    "decomposit": "decompose", "decomposited": "decomposed", "decompositing": "decomposing",
    "decomposits": "decomposes", "decress": "decrees", "decribe": "describe",
    "decribed": "described", "decribes": "describes", "decribing": "describing",
    "dectect": "detect", "defendent": "defendant", "defendents": "defendants",
    "deffensively": "defensively", "deffine": "define", "deffined": "defined",
    "definance": "defiance", "definate": "definite", "definetly": "definitely",
    "definining": "defining", "definit": "definite", "definitly": "definitely",
    "definiton": "definition", "defintion": "definition", "degrate": "degrade",
    "delagates": "delegates", "delapidated": "dilapidated", "delerious": "delirious",
    "delevopment": "development", "deliberatly": "deliberately", "delusionally": "delusively",
    "demenor": "demeanor", "demographical": "demographic", "demolision": "demolition",
    "demorcracy": "democracy", "demostration": "demonstration", "denegrating": "denigrating",
    "densly": "densely", "deparment": "department", "deparmental": "departmental",
    "deparments": "departments", "dependance": "dependence", "dependancy": "dependency",
    "deriviated": "derived", "derivitive": "derivative", "derogitory": "derogatory",
    "descendands": "descendants", "descibed": "described", "descision": "decision",
    "descisions": "decisions", "descriibes": "describes", "descripters": "descriptors",
    "descripton": "description", "desctruction": "destruction", "descuss": "discuss",
    "desgined": "designed", "deside": "decide", "desigining": "designing",
    "desinations": "destinations", "desintegrated": "disintegrated",
    "desintegration": "disintegration", "desireable": "desirable", "desitned": "destined",
    "desktiop": "desktop", "desorder": "disorder", "desoriented": "disoriented",
    "despict": "depict", "despiration": "desperation", "dessicated": "desiccated",
    "dessigned": "designed", "destablized": "destabilized", "destory": "destroy",
    "detailled": "detailed", "detatched": "detached", "deteoriated": "deteriorated",
    "deteriate": "deteriorate", "deterioriating": "deteriorating", "determinining": "determining",
    "detremental": "detrimental", "devasted": "devastated", "develope": "develop",
    "developement": "development", "developped": "developed", "develpment": "development",
    "devels": "delves", "devestated": "devastated", "devestating": "devastating",
    "devide": "divide", "devided": "divided", "devistating": "devastating",
    "devolopement": "development", "diablical": "diabolical", "diamons": "diamonds",
    "diaster": "disaster", "dichtomy": "dichotomy", "diconnects": "disconnects",
    "dicover": "discover", "dicovered": "discovered", "dicovering": "discovering",
    "dicovers": "discovers", "dicovery": "discovery", "dictionarys": "dictionaries",
    "dicussed": "discussed", "dieties": "deities", "diety": "deity", "diferrent": "different",
    "differentiatiations": "differentiations", "difficulity": "difficulty",
    "dificulties": "difficulties", "dificulty": "difficulty", "dimenions": "dimensions",
    "dimention": "dimension", "dimentional": "dimensional", "dimentions": "dimensions",
    "dimesnional": "dimensional", "diminuitive": "diminutive", "dimunitive": "diminutive",
    "diosese": "diocese", "diphtong": "diphthong", "diphtongs": "diphthongs",
    "diplomancy": "diplomacy", "dipthong": "diphthong", "dipthongs": "diphthongs",
    "directoty": "directory", "dirived": "derived", "disagreeed": "disagreed",
    "disapeared": "disappeared", "disapointing": "disappointing", "disappearred": "disappeared",
    "disaproval": "disapproval", "disasterous": "disastrous", "disatisfaction": "dissatisfaction",
    "disatisfied": "dissatisfied", "disatrous": "disastrous", "discribe": "describe",
    "discribed": "described", "discribes": "describes", "discribing": "describing",
    "disctinction": "distinction", "disctinctive": "distinctive", "disemination": "dissemination",
    "disenchanged": "disenchanted", "disiplined": "disciplined", "disobediance": "disobedience",
    "disobediant": "disobedient", "disolved": "dissolved", "disover": "discover",
    "dispair": "despair", "disparingly": "disparagingly", "dispence": "dispense",
    "dispenced": "dispensed", "dispencing": "dispensing", "dispicable": "despicable",
    "dispite": "despite", "dispostion": "disposition", "disproportiate": "disproportionate",
    "disputandem": "disputandum", "disricts": "districts", "dissagreement": "disagreement",
    "dissapearance": "disappearance", "dissapeared": "disappeared", "dissapearing": "disappearing",
    "dissapears": "disappears", "dissappear": "disappear", "dissappears": "disappears",
    "dissappointed": "disappointed", "dissarray": "disarray", "dissobediance": "disobedience",
    "dissobediant": "disobedient", "dissobedience": "disobedience", "dissobedient": "disobedient",
    "distiction": "distinction", "distingish": "distinguish", "distingished": "distinguished",
    "distingishes": "distinguishes", "distingishing": "distinguishing",
    "distingquished": "distinguished", "distrubution": "distribution", "distruction": "destruction",
    "distructive": "destructive", "ditributed": "distributed", "divice": "device",
    "divinition": "divination", "divison": "division", "divisons": "divisions", "dum": "dumb",
    "doccument": "document", "doccumented": "documented", "doccuments": "documents",
    "docrines": "doctrines", "doctines": "doctrines", "documenatry": "documentary", "doens": "does",
    "doign": "doing", "dominaton": "domination", "dominent": "dominant", "dominiant": "dominant",
    "donig": "doing", "doulbe": "double", "dowloads": "downloads", "dramtic": "dramatic",
    "draughtman": "draughtsman", "dravadian": "dravidian", "dreasm": "dreams",
    "driectly": "directly", "drnik": "drink", "druming": "drumming", "drummless": "drumless",
    "dupicate": "duplicate", "durig": "during", "durring": "during", "duting": "during",
    "dyas": "dryas", "eahc": "each", "ealier": "earlier", "earlies": "earliest", "earnt": "earned",
    "ecclectic": "eclectic", "eceonomy": "economy", "ecidious": "deciduous", "eclispe": "eclipse",
    "ecomonic": "economic", "econoımic": "economic", "econoimic": "economic", "ect": "etc",
    "eearly": "early", "efel": "evil", "effeciency": "efficiency", "effecient": "efficient",
    "effeciently": "efficiently", "efficency": "efficiency", "efficent": "efficient",
    "efficently": "efficiently", "effulence": "effluence", "eiter": "either", "elction": "election",
    "electrial": "electrical", "electricly": "electrically", "electricty": "electricity",
    "elementay": "elementary", "eleminated": "eliminated", "eleminating": "eliminating",
    "eles": "eels", "eletricity": "electricity", "elicided": "elicited", "eligable": "eligible",
    "elimentary": "elementary", "ellected": "elected", "elphant": "elephant",
    "embarassed": "embarrassed", "embarassing": "embarrassing", "embarassment": "embarrassment",
    "embargos": "embargoes", "embarras": "embarrass", "embarrased": "embarrassed",
    "embarrasing": "embarrassing", "embarrasment": "embarrassment", "embezelled": "embezzled",
    "emblamatic": "emblematic", "eminate": "emanate", "eminated": "emanated", "emision": "emission",
    "emited": "emitted", "emiting": "emitting", "emmediately": "immediately",
    "emminently": "eminently", "emmisaries": "emissaries", "emmisarries": "emissaries",
    "emmisarry": "emissary", "emmisary": "emissary", "emmision": "emission",
    "emmisions": "emissions", "emmited": "emitted", "emmiting": "emitting", "emmitted": "emitted",
    "emmitting": "emitting", "emnity": "enmity", "emperical": "empirical",
    "emphaised": "emphasised", "emphsis": "emphasis", "emphysyma": "emphysema",
    "emporer": "emperor", "emprisoned": "imprisoned", "enameld": "enameled",
    "enchancement": "enhancement", "encouraing": "encouraging", "encryptiion": "encryption",
    "encylopedia": "encyclopedia", "endevors": "endeavors", "endevour": "endeavour",
    "endig": "ending", "endolithes": "endoliths", "enduce": "induce", "ened": "need",
    "enforceing": "enforcing", "engagment": "engagement", "engeneer": "engineer",
    "engeneering": "engineering", "engieneer": "engineer", "engieneers": "engineers",
    "enlargment": "enlargement", "enlargments": "enlargements", "enourmous": "enormous",
    "enourmously": "enormously", "ensconsed": "ensconced", "entaglements": "entanglements",
    "enteratinment": "entertainment", "enthusiatic": "enthusiastic", "entitity": "entity",
    "entitlied": "entitled", "entrepeneur": "entrepreneur", "entrepeneurs": "entrepreneurs",
    "enviorment": "environment", "enviormental": "environmental",
    "enviormentally": "environmentally", "enviorments": "environments",
    "enviornment": "environment", "enviornmental": "environmental",
    "enviornmentalist": "environmentalist", "enviornmentally": "environmentally",
    "enviornments": "environments", "enviromental": "environmental",
    "enviromentalist": "environmentalist", "enviromentally": "environmentally",
    "enviroments": "environments", "envolutionary": "evolutionary", "envrionments": "environments",
    "enxt": "next", "epidsodes": "episodes", "epsiode": "episode", "equialent": "equivalent",
    "equalibrium": "equilibrium", "equelibrium": "equilibrium", "equilibium": "equilibrium",
    "equilibrum": "equilibrium", "equiped": "equipped", "equippment": "equipment",
    "equitorial": "equatorial", "equivelant": "equivalent", "equivelent": "equivalent",
    "equivilant": "equivalent", "equivilent": "equivalent", "equivlalent": "equivalent",
    "eratic": "erratic", "eratically": "erratically", "eraticly": "erratically",
    "errupted": "erupted", "esential": "essential", "esitmated": "estimated", "esle": "else",
    "especialy": "especially", "essencial": "essential", "essense": "essence",
    "essentail": "essential", "essentialy": "essentially", "essentual": "essential",
    "essesital": "essential", "estabishes": "establishes", "establising": "establishing",
    "ethnocentricm": "ethnocentrism", "europian": "european", "europians": "europeans",
    "eurpean": "european", "eurpoean": "european", "evenhtually": "eventually",
    "eventally": "eventually", "eventially": "eventually", "eventualy": "eventually",
    "everthing": "everything", "everyting": "everything", "eveyr": "every",
    "evidentally": "evidently", "exagerate": "exaggerate", "exagerated": "exaggerated",
    "exagerates": "exaggerates", "exagerating": "exaggerating", "exagerrate": "exaggerate",
    "exagerrated": "exaggerated", "exagerrates": "exaggerates", "exagerrating": "exaggerating",
    "examinated": "examined", "exampt": "exempt", "exapansion": "expansion", "excact": "exact",
    "excange": "exchange", "excecute": "execute", "excecuted": "executed", "excecutes": "executes",
    "excecuting": "executing", "excecution": "execution", "excedded": "exceeded",
    "excelent": "excellent", "excell": "excel", "excellance": "excellence",
    "excellant": "excellent", "excells": "excels", "exchanching": "exchanging",
    "excisted": "existed", "exculsivly": "exclusively", "execising": "exercising",
    "exection": "execution", "exectued": "executed", "exeedingly": "exceedingly",
    "exelent": "excellent", "exellent": "excellent", "exemple": "example", "exept": "except",
    "exeptional": "exceptional", "exerbate": "exacerbate", "exerbated": "exacerbated",
    "exerciese": "exercises", "exerpt": "excerpt", "exerpts": "excerpts", "exerternal": "external",
    "exhalted": "exalted", "exhibtion": "exhibition", "exibition": "exhibition",
    "exibitions": "exhibitions", "exicting": "exciting", "exinct": "extinct",
    "existant": "existent", "existince": "existence", "exliled": "exiled", "exludes": "excludes",
    "exmaple": "example", "exonorate": "exonerate", "exoskelaton": "exoskeleton",
    "expalin": "explain", "expatriot": "expatriate", "expeced": "expected",
    "expecially": "especially", "expeditonary": "expeditionary", "expeiments": "experiments",
    "expell": "expel", "expells": "expels", "experianced": "experienced",
    "expiditions": "expeditions", "expierence": "experience", "explaination": "explanation",
    "explaning": "explaining", "explictly": "explicitly", "exploititive": "exploitative",
    "explotation": "exploitation", "expropiated": "expropriated", "expropiation": "expropriation",
    "exressed": "expressed", "extemely": "extremely", "extention": "extension",
    "extentions": "extensions", "extered": "exerted", "extermist": "extremist",
    "extradiction": "extradition", "extraterrestial": "extraterrestrial",
    "extraterrestials": "extraterrestrials", "extravagent": "extravagant",
    "extrememly": "extremely", "extremeophile": "extremophile", "extremly": "extremely",
    "extrordinarily": "extraordinarily", "extrordinary": "extraordinary", "faciliate": "facilitate",
    "faciliated": "facilitated", "faciliates": "facilitates", "facilites": "facilities",
    "facillitate": "facilitate", "facinated": "fascinated", "facist": "fascist",
    "familes": "families", "familliar": "familiar", "famoust": "famous", "fanatism": "fanaticism",
    "farenheit": "fahrenheit", "fatc": "fact", "faught": "fought", "favoutrable": "favourable",
    "feasable": "feasible", "fedreally": "federally", "femminist": "feminist",
    "feromone": "pheromone", "fertily": "fertility", "fianite": "finite", "fianlly": "finally",
    "ficticious": "fictitious", "fictious": "fictitious", "fidn": "find", "fiercly": "fiercely",
    "fightings": "fighting", "filiament": "filament", "fimilies": "families",
    "finacial": "financial", "financialy": "financially", "firends": "friends",
    "fisionable": "fissionable", "flamable": "flammable", "flawess": "flawless",
    "flemmish": "flemish", "flourescent": "fluorescent", "flourine": "fluorine",
    "fluorish": "flourish", "flourishment": "flourishing", "follwoing": "following",
    "folowing": "following", "fomed": "formed", "fonetic": "phonetic", "fontrier": "fontier",
    "foootball": "football", "forbad": "forbade", "forbiden": "forbidden", "foreward": "foreword",
    "forfiet": "forfeit", "forhead": "forehead", "formalhaut": "fomalhaut",
    "formallize": "formalize", "formallized": "formalized", "formelly": "formerly",
    "formidible": "formidable", "formost": "foremost", "forsaw": "foresaw",
    "forseeable": "foreseeable", "fortelling": "foretelling", "forunner": "forerunner",
    "foucs": "focus", "foudn": "found", "fougth": "fought", "foundaries": "foundries",
    "foundary": "foundry", "foundland": "newfoundland", "fourties": "forties", "fourty": "forty",
    "fouth": "fourth", "foward": "forward", "fransiscan": "franciscan",
    "fransiscans": "franciscans", "freindly": "friendly", "frequentily": "frequently",
    "frome": "from", "fromed": "formed", "froniter": "frontier", "fucntion": "function",
    "fucntioning": "functioning", "fufill": "fulfill", "fufilled": "fulfilled",
    "fulfiled": "fulfilled", "fullfill": "fulfill", "fullfilled": "fulfilled",
    "fundametal": "fundamental", "fundametals": "fundamentals", "funguses": "fungi",
    "funtion": "function", "furuther": "further", "futher": "further", "futhermore": "furthermore",
    "galatic": "galactic", "galations": "galatians", "gallaxies": "galaxies",
    "galvinized": "galvanized", "ganerate": "generate", "ganes": "games", "ganster": "gangster",
    "garantee": "guarantee", "garanteed": "guaranteed", "garantees": "guarantees",
    "gardai": "gardaí", "garnison": "garrison", "gauarana": "guaraná", "gaurantee": "guarantee",
    "gauranteed": "guaranteed", "gaurantees": "guarantees", "gaurentee": "guarantee",
    "gaurenteed": "guaranteed", "gaurentees": "guarantees", "geneological": "genealogical",
    "geneologies": "genealogies", "geneology": "genealogy", "generaly": "generally",
    "generatting": "generating", "genialia": "genitalia", "geographicial": "geographical",
    "geometrician": "geometer", "geometricians": "geometers", "gerat": "great", "ghandi": "gandhi",
    "glamourous": "glamorous", "glight": "flight", "gnawwed": "gnawed", "godess": "goddess",
    "godesses": "goddesses", "godounov": "godunov", "goign": "going", "gonig": "going",
    "gothenberg": "gothenburg", "gottleib": "gottlieb", "gouvener": "governor",
    "govement": "government", "govenment": "government", "govenrment": "government",
    "goverance": "governance", "govermental": "governmental", "governer": "governor",
    "governmnet": "government", "govorment": "government", "govormental": "governmental",
    "govornment": "government", "gracefull": "graceful", "graet": "great", "grafitti": "graffiti",
    "gramatically": "grammatically", "grammaticaly": "grammatically", "grammer": "grammar",
    "grat": "great", "gratuitious": "gratuitous", "greatful": "grateful",
    "greatfully": "gratefully", "greif": "grief", "gridles": "griddles", "gropu": "group",
    "grwo": "grow", "guage": "gauge", "guarentee": "guarantee", "guarenteed": "guaranteed",
    "guarentees": "guarantees", "guatamala": "guatemala", "guatamalan": "guatemalan",
    "guerrila": "guerrilla", "guerrilas": "guerrillas", "guidence": "guidance", "guilia": "giulia",
    "guilio": "giulio", "guiness": "guinness", "guiseppe": "giuseppe", "gunanine": "guanine",
    "gurantee": "guarantee", "guranteed": "guaranteed", "gurantees": "guarantees",
    "guttaral": "guttural", "gutteral": "guttural", "gya": "gay", "habaeus": "habeas",
    "habeus": "habeas", "habsbourg": "habsburg", "haemorrage": "haemorrhage",
    "halarious": "hilarious", "halp": "help", "hapen": "happen", "hapened": "happened",
    "hapening": "happening", "happended": "happened", "happenned": "happened",
    "harased": "harassed", "harases": "harasses", "harasment": "harassment",
    "harasments": "harassments", "harassement": "harassment", "harras": "harass",
    "harrased": "harassed", "harrases": "harasses", "harrasing": "harassing",
    "harrasment": "harassment", "harrasments": "harassments", "harrassed": "harassed",
    "harrasses": "harassed", "harrassing": "harassing", "harrassment": "harassment",
    "harrassments": "harassments", "hatian": "haitian", "haviest": "heaviest",
    "headquarer": "headquarter", "headquater": "headquarter", "headquatered": "headquartered",
    "headquaters": "headquarters", "healthercare": "healthcare", "heared": "heard",
    "heathy": "healthy", "heidelburg": "heidelberg", "heigher": "higher", "heirarchy": "hierarchy",
    "heiroglyphics": "hieroglyphics", "helment": "helmet", "helpfull": "helpful",
    "helpped": "helped", "hemmorhage": "hemorrhage", "heridity": "heredity", "heroe": "hero",
    "heros": "heroes", "hertiage": "heritage", "hertzs": "hertz", "hesistant": "hesitant",
    "heterogenous": "heterogeneous", "hierachical": "hierarchical", "hierachies": "hierarchies",
    "hierachy": "hierarchy", "hierarcical": "hierarchical", "hierarcy": "hierarchy",
    "hieroglph": "hieroglyph", "hieroglphs": "hieroglyphs", "higer": "higher", "higest": "highest",
    "higway": "highway", "hillarious": "hilarious", "himselv": "himself", "hinderance": "hindrance",
    "hinderence": "hindrance", "hindrence": "hindrance", "hipopotamus": "hippopotamus",
    "hismelf": "himself", "histocompatability": "histocompatibility", "historicians": "historians",
    "holf": "hold", "homogeneize": "homogenize", "homogeneized": "homogenized",
    "honory": "honorary", "horrifing": "horrifying", "hosited": "hoisted",
    "hospitible": "hospitable", "hounour": "honour", "howver": "however",
    "hsitorians": "historians", "hstory": "history", "htey": "they", "htikn": "think",
    "hting": "thing", "htink": "think", "htis": "this", "huminoid": "humanoid",
    "humoural": "humoral", "humurous": "humorous", "husban": "husband", "hvae": "have",
    "hvaing": "having", "hwihc": "which", "hwile": "while", "hwole": "whole", "hydogen": "hydrogen",
    "hydropile": "hydrophile", "hydropilic": "hydrophilic", "hydropobe": "hydrophobe",
    "hydropobic": "hydrophobic", "hygeine": "hygiene", "hyjack": "hijack", "hyjacking": "hijacking",
    "hypocracy": "hypocrisy", "hypocrasy": "hypocrisy", "hypocricy": "hypocrisy",
    "hypocrit": "hypocrite", "hypocrits": "hypocrites", "iconclastic": "iconoclastic",
    "idaeidae": "idea", "idaes": "ideas", "idealogies": "ideologies", "idealogy": "ideology",
    "identicial": "identical", "identifers": "identifiers", "ideosyncratic": "idiosyncratic",
    "idiosyncracy": "idiosyncrasy", "ihaca": "ithaca", "illegimacy": "illegitimacy",
    "illegitmate": "illegitimate", "illess": "illness", "illiegal": "illegal",
    "illution": "illusion", "ilness": "illness", "ilogical": "illogical", "imagenary": "imaginary",
    "imagin": "imagine", "imcomplete": "incomplete", "imediately": "immediately",
    "imense": "immense", "immediatley": "immediately", "immidately": "immediately",
    "immidiately": "immediately", "immitate": "imitate", "immitated": "imitated",
    "immitating": "imitating", "immitator": "imitator", "immunosupressant": "immunosuppressant",
    "impecabbly": "impeccably", "impedence": "impedance", "implamenting": "implementing",
    "impliment": "implement", "implimented": "implemented", "imploys": "employs",
    "importamt": "important", "impressario": "impresario", "imprioned": "imprisoned",
    "imprisonned": "imprisoned", "improvision": "improvisation", "improvments": "improvements",
    "inablility": "inability", "inaccessable": "inaccessible", "inadiquate": "inadequate",
    "inadquate": "inadequate", "inadvertant": "inadvertent", "inadvertantly": "inadvertently",
    "inagurated": "inaugurated", "inaguration": "inauguration", "inappropiate": "inappropriate",
    "inaugures": "inaugurates", "inbalance": "imbalance", "inbalanced": "imbalanced",
    "inbetween": "between", "incarcirated": "incarcerated", "incidentially": "incidentally",
    "incidently": "incidentally", "inclreased": "increased", "includ": "include",
    "includng": "including", "incompatabilities": "incompatibilities",
    "incompatability": "incompatibility", "incompatable": "incompatible",
    "incompatablities": "incompatibilities", "incompatablity": "incompatibility",
    "incompatiblities": "incompatibilities", "incompatiblity": "incompatibility",
    "incompetance": "incompetence", "incompetant": "incompetent", "incomptable": "incompatible",
    "incomptetent": "incompetent", "inconsistant": "inconsistent", "incoroporated": "incorporated",
    "incorperation": "incorporation", "incorportaed": "incorporated", "incorprates": "incorporates",
    "incorruptable": "incorruptible", "incramentally": "incrementally", "increadible": "incredible",
    "incredable": "incredible", "inctroduce": "introduce", "inctroduced": "introduced",
    "incuding": "including", "incunabla": "incunabula", "indefinately": "indefinitely",
    "indefineable": "undefinable", "indefinitly": "indefinitely", "indentical": "identical",
    "indepedantly": "independently", "indepedence": "independence", "independance": "independence",
    "independantly": "independently", "independece": "independence", "independendet": "independent",
    "indespensable": "indispensable", "indespensible": "indispensable", "indictement": "indictment",
    "indigineous": "indigenous", "indipendence": "independence", "indipendent": "independent",
    "indipendently": "independently", "indispensible": "indispensable",
    "indisputible": "indisputable", "indisputibly": "indisputably", "individualy": "individually",
    "indpendent": "independent", "indpendently": "independently", "indulgue": "indulge",
    "indutrial": "industrial", "indviduals": "individuals", "inefficienty": "inefficiently",
    "inevatible": "inevitable", "inevitible": "inevitable", "inevititably": "inevitably",
    "infalability": "infallibility", "infallable": "infallible", "infectuous": "infectious",
    "infered": "inferred", "infilitrate": "infiltrate", "infilitrated": "infiltrated",
    "infilitration": "infiltration", "infinit": "infinite", "inflamation": "inflammation",
    "influencial": "influential", "influented": "influenced", "infomation": "information",
    "informtion": "information", "infrantryman": "infantryman", "infrigement": "infringement",
    "ingenius": "ingenious", "ingreediants": "ingredients", "inhabitans": "inhabitants",
    "inherantly": "inherently", "inheritence": "inheritance", "inital": "initial",
    "initally": "initially", "initation": "initiation", "initiaitive": "initiative",
    "inlcuding": "including", "inmigrant": "immigrant", "inmigrants": "immigrants",
    "innoculated": "inoculated", "inocence": "innocence", "inofficial": "unofficial",
    "inot": "into", "inpeach": "impeach", "inpending": "impending", "inpenetrable": "impenetrable",
    "inpolite": "impolite", "inprisonment": "imprisonment", "inproving": "improving",
    "insectiverous": "insectivorous", "insensative": "insensitive", "inseperable": "inseparable",
    "insistance": "insistence", "insitution": "institution", "insitutions": "institutions",
    "instade": "instead", "instatance": "instance", "institue": "institute",
    "instuction": "instruction", "instuments": "instruments",
    "instutionalized": "institutionalized", "intelectual": "intellectual",
    "inteligence": "intelligence", "inteligent": "intelligent", "intenational": "international",
    "intepretation": "interpretation", "intepretator": "interpretor",
    "interational": "international", "interchangable": "interchangeable",
    "interchangably": "interchangeably", "intercontinential": "intercontinental",
    "intercontinetal": "intercontinental", "interelated": "interrelated",
    "interferance": "interference", "interfereing": "interfering", "intergrated": "integrated",
    "intergration": "integration", "interm": "interim", "internation": "international",
    "interpet": "interpret", "interrim": "interim", "interrugum": "interregnum",
    "intertaining": "entertaining", "intervines": "intervenes", "intevene": "intervene",
    "intial": "initial", "intially": "initially", "intrduced": "introduced", "intrest": "interest",
    "introdued": "introduced", "intruduced": "introduced", "intrument": "instrument",
    "intrumental": "instrumental", "intruments": "instruments", "intrusted": "entrusted",
    "intutive": "intuitive", "intutively": "intuitively", "inudstry": "industry",
    "inventer": "inventor", "invertibrates": "invertebrates", "investingate": "investigate",
    "involvment": "involvement", "irelevent": "irrelevant", "iresistable": "irresistible",
    "iresistably": "irresistibly", "iresistible": "irresistible", "iresistibly": "irresistibly",
    "iritable": "irritable", "iritated": "irritated", "ironicly": "ironically",
    "irregardless": "regardless", "irrelevent": "irrelevant", "irreplacable": "irreplaceable",
    "irresistable": "irresistible", "irresistably": "irresistibly", "israelies": "israelis",
    "issueing": "issuing", "itnroduced": "introduced", "iunior": "junior", "iwll": "will",
    "iwth": "with", "japanes": "japanese", "jeapardy": "jeopardy", "jewllery": "jewellery",
    "johanine": "johannine", "jorunal": "journal", "jospeh": "joseph", "jouney": "journey",
    "journied": "journeyed", "journies": "journeys", "jstu": "just", "jsut": "just",
    "juadaism": "judaism", "juadism": "judaism", "judical": "judicial", "judisuary": "judiciary",
    "juducial": "judicial", "juristiction": "jurisdiction", "juristictions": "jurisdictions",
    "kindergarden": "kindergarten", "klenex": "kleenex", "knive": "knife",
    "knowlegeable": "knowledgeable", "knwo": "know", "knwos": "knows", "konw": "know",
    "konws": "knows", "kwno": "know", "labratory": "laboratory", "laguage": "language",
    "laguages": "languages", "laparascopic": "laparoscopic", "larg": "large", "largst": "largest",
    "larrry": "larry", "lastr": "last", "lattitude": "latitude", "launhed": "launched",
    "lavae": "larvae", "layed": "laid", "lazyness": "laziness", "leage": "league",
    "leathal": "lethal", "lebsian": "lesbian", "lefted": "left", "legitamate": "legitimate",
    "legitmate": "legitimate", "leibnitz": "leibniz", "lenght": "length", "leran": "learn",
    "lerans": "learns", "lesban": "lesbian", "lesbain": "lesbian", "lesbina": "lesbian",
    "leutenant": "lieutenant", "leval": "level", "levetate": "levitate", "levetated": "levitated",
    "levetates": "levitates", "levetating": "levitating", "levle": "level", "liad": "laid",
    "liasion": "liaison", "liasons": "liaisons", "libell": "libel", "libguistic": "linguistic",
    "libguistics": "linguistics", "libitarianisn": "libertarianism", "lieing": "lying",
    "liek": "like", "liekd": "liked", "liesure": "leisure", "lieuenant": "lieutenant",
    "lieved": "lived", "liftime": "lifetime", "likelyhood": "likelihood", "linnaena": "linnaean",
    "lippizaner": "lipizzaner", "listners": "listeners", "litature": "literature",
    "literaly": "literally", "literture": "literature", "littel": "little",
    "litterally": "literally", "liuke": "like", "livley": "lively", "lmits": "limits",
    "loev": "love", "lonelyness": "loneliness", "longitudonal": "longitudinal", "lonley": "lonely",
    "lotharingen": "lothringen", "lukid": "likud", "lveo": "love", "lvoe": "love", "lybia": "libya",
    "mackeral": "mackerel", "magasine": "magazine", "magizine": "magazine", "magisine": "magazine",
    "magincian": "magician", "magnificient": "magnificent", "magolia": "magnolia",
    "mailny": "mainly", "maintainence": "maintenance", "maintance": "maintenance",
    "maintenence": "maintenance", "maintinaing": "maintaining", "maintioned": "mentioned",
    "majoroty": "majority", "makse": "makes", "malcom": "malcolm", "maltesian": "maltese",
    "mamal": "mammal", "mamalian": "mammalian", "maneouvre": "manoeuvre",
    "maneouvred": "manoeuvred", "maneouvres": "manoeuvres", "maneouvring": "manoeuvring",
    "manisfestations": "manifestations", "manoeuverability": "maneuverability",
    "mantained": "maintained", "manufacturedd": "manufactured", "manufature": "manufacture",
    "manufatured": "manufactured", "manufaturing": "manufacturing", "manuver": "maneuver",
    "mariage": "marriage", "marjority": "majority", "markes": "marks", "marketting": "marketing",
    "marmelade": "marmalade", "marrage": "marriage", "marraige": "marriage",
    "marrtyred": "martyred", "marryied": "married", "massachussets": "massachusetts",
    "massachussetts": "massachusetts", "masterbation": "masturbation",
    "mataphysical": "metaphysical", "materalists": "materialist", "mathamatics": "mathematics",
    "mathematican": "mathematician", "mathematicas": "mathematics",
    "matheticians": "mathematicians", "mathmatically": "mathematically",
    "mathmatician": "mathematician", "mathmaticians": "mathematicians", "mccarthyst": "mccarthyist",
    "mchanics": "mechanics", "meaing": "meaning", "meaninng": "meaning",
    "mechandise": "merchandise", "medacine": "medicine", "medeival": "medieval",
    "medevial": "medieval", "mediciney": "mediciny", "medievel": "medieval",
    "mediterainnean": "mediterranean", "mediteranean": "mediterranean", "meerkrat": "meerkat",
    "melieux": "milieux", "membranaphone": "membranophone", "memeber": "member",
    "menally": "mentally", "mercentile": "mercantile", "messanger": "messenger",
    "messenging": "messaging", "metalic": "metallic", "metalurgic": "metallurgic",
    "metalurgical": "metallurgical", "metalurgy": "metallurgy", "metamorphysis": "metamorphosis",
    "metaphoricial": "metaphorical", "meterologist": "meteorologist", "meterology": "meteorology",
    "methaphor": "metaphor", "methaphors": "metaphors", "michagan": "michigan",
    "micoscopy": "microscopy", "mileau": "milieu", "milennia": "millennia",
    "milennium": "millennium", "mileu": "milieu", "miliary": "military", "miligram": "milligram",
    "milion": "million", "miliraty": "military", "millenia": "millennia", "millenial": "millennial",
    "millenialism": "millennialism", "millepede": "millipede", "millioniare": "millionaire",
    "millitant": "militant", "millitary": "military", "millon": "million", "miltary": "military",
    "minature": "miniature", "minerial": "mineral", "ministery": "ministry", "minsitry": "ministry",
    "minstries": "ministries", "minstry": "ministry", "minumum": "minimum", "mirrorred": "mirrored",
    "miscelaneous": "miscellaneous", "miscellanious": "miscellaneous",
    "miscellanous": "miscellaneous", "mischeivous": "mischievous", "mischevious": "mischievous",
    "mischievious": "mischievous", "misdameanor": "misdemeanor", "misdameanors": "misdemeanors",
    "misdemenor": "misdemeanor", "misdemenors": "misdemeanors", "misfourtunes": "misfortunes",
    "misile": "missile", "misouri": "missouri", "mispelled": "misspelled",
    "mispelling": "misspelling", "missen": "mizzen", "missisipi": "mississippi",
    "missisippi": "mississippi", "missle": "missile", "missonary": "missionary",
    "misterious": "mysterious", "mistery": "mystery", "misteryous": "mysterious", "mkae": "make",
    "mkaes": "makes", "mkaing": "making", "mkea": "make", "moderm": "modem", "modle": "model",
    "moent": "moment", "moeny": "money", "mohammedans": "muslims", "moleclues": "molecules",
    "momento": "memento", "monestaries": "monasteries", "monickers": "monikers",
    "monolite": "monolithic", "monserrat": "montserrat", "montains": "mountains",
    "montanous": "mountainous", "montnana": "montana", "monts": "months", "montypic": "monotypic",
    "morisette": "morissette", "morrisette": "morissette", "morroccan": "moroccan",
    "morrocco": "morocco", "morroco": "morocco", "mosture": "moisture", "motiviated": "motivated",
    "mounth": "month", "movei": "movie", "movment": "movement", "mroe": "more", "mucuous": "mucous",
    "muder": "murder", "mudering": "murdering", "multicultralism": "multiculturalism",
    "multipled": "multiplied", "multiplers": "multipliers", "munbers": "numbers",
    "muncipalities": "municipalities", "muncipality": "municipality",
    "munnicipality": "municipality", "muscial": "musical", "muscician": "musician",
    "muscicians": "musicians", "mutiliated": "mutilated", "myraid": "myriad", "mysef": "myself",
    "mysogynist": "misogynist", "mysogyny": "misogyny", "mysterous": "mysterious",
    "mythraic": "mithraic", "naieve": "naive", "naploeon": "napoleon", "napolean": "napoleon",
    "napoleonian": "napoleonic", "naturaly": "naturally", "naturely": "naturally",
    "naturual": "natural", "naturually": "naturally", "nazereth": "nazareth",
    "neccesarily": "necessarily", "neccessarily": "necessarily", "neccessities": "necessities",
    "necesarily": "necessarily", "necessiate": "necessitate", "neglible": "negligible",
    "negligable": "negligible", "negociate": "negotiate", "negociation": "negotiation",
    "negociations": "negotiations", "negotation": "negotiation", "neigborhood": "neighborhood",
    "neigbourhood": "neighbourhood", "neolitic": "neolithic", "nessasarily": "necessarily",
    "nessecary": "necessary", "nestin": "nesting", "neverthless": "nevertheless",
    "newletters": "newsletters", "nightime": "nighttime", "nineth": "ninth",
    "ninteenth": "nineteenth", "ninty": "ninety", "nkow": "know", "nkwo": "know", "nmae": "name",
    "noncombatents": "noncombatants", "nonsence": "nonsense", "nontheless": "nonetheless",
    "norhern": "northern", "northen": "northern", "northereastern": "northeastern",
    "notabley": "notably", "noteable": "notable", "noteably": "notably", "noteriety": "notoriety",
    "noth": "north", "nothern": "northern", "noticably": "noticeably", "noticeing": "noticing",
    "noticible": "noticeable", "notwhithstanding": "notwithstanding", "noveau": "nouveau",
    "novermber": "november", "nowdays": "nowadays", "nowe": "now", "nto": "not",
    "nucular": "nuclear", "nuculear": "nuclear", "nuisanse": "nuisance", "nullabour": "nullarbor",
    "numberous": "numerous", "nuremburg": "nuremberg", "nusance": "nuisance",
    "nutritent": "nutrient", "nutritents": "nutrients", "nuturing": "nurturing",
    "obediance": "obedience", "obediant": "obedient", "obession": "obsession",
    "obssessed": "obsessed", "obstacal": "obstacle", "obstancles": "obstacles",
    "obstruced": "obstructed", "ocasion": "occasion", "ocasional": "occasional",
    "ocasionally": "occasionally", "ocasionaly": "occasionally", "ocasioned": "occasioned",
    "ocasions": "occasions", "ocassion": "occasion", "ocassional": "occasional",
    "ocassionally": "occasionally", "ocassionaly": "occasionally", "ocassioned": "occasioned",
    "ocassions": "occasions", "occaison": "occasion", "occassional": "occasional",
    "occassionally": "occasionally", "occassionaly": "occasionally", "occassioned": "occasioned",
    "occassions": "occasions", "occationally": "occasionally", "occour": "occur",
    "occurance": "occurrence", "occurances": "occurrences", "occurences": "occurrences",
    "occuring": "occurring", "occurr": "occur", "occurrance": "occurrence",
    "occurrances": "occurrences", "octohedra": "octahedra", "octohedral": "octahedral",
    "octohedron": "octahedron", "ocuntries": "countries", "ocuntry": "country", "ocurr": "occur",
    "ocurrance": "occurrence", "ocurred": "occurred", "ocurrence": "occurrence",
    "offcers": "officers", "offcially": "officially", "offereings": "offerings",
    "offical": "official", "offically": "officially", "officals": "officials",
    "officaly": "officially", "officialy": "officially", "offred": "offered", "oftenly": "often",
    "olther": "other", "omision": "omission", "omited": "omitted", "omiting": "omitting",
    "omlette": "omelette", "ommision": "omission", "ommited": "omitted", "ommiting": "omitting",
    "ommitted": "omitted", "ommitting": "omitting", "omniverous": "omnivorous",
    "omniverously": "omnivorously", "omre": "more", "onyl": "only", "openess": "openness",
    "oponent": "opponent", "oportunity": "opportunity", "opose": "oppose", "oposite": "opposite",
    "oposition": "opposition", "oppenly": "openly", "oppinion": "opinion", "opponant": "opponent",
    "oppononent": "opponent", "oppositition": "opposition", "oppossed": "opposed",
    "opprotunity": "opportunity", "opression": "oppression", "opressive": "oppressive",
    "opthalmic": "ophthalmic", "opthalmologist": "ophthalmologist", "opthalmology": "ophthalmology",
    "opthamologist": "ophthalmologist", "optmizations": "optimizations", "optomism": "optimism",
    "orded": "ordered", "organim": "organism", "organistion": "organisation",
    "organiztion": "organization", "orginal": "original", "orginally": "originally",
    "orginize": "organise", "oridinarily": "ordinarily", "origanaly": "originally",
    "originaly": "originally", "originially": "originally", "originnally": "originally",
    "origional": "original", "orignally": "originally", "orignially": "originally",
    "otehr": "other", "otherwordly": "otherworldly", "oublisher": "publisher", "ouevre": "oeuvre",
    "oustanding": "outstanding", "overshaddowed": "overshadowed", "overwelming": "overwhelming",
    "overwheliming": "overwhelming", "owrk": "work", "owudl": "would", "oxigen": "oxygen",
    "oximoron": "oxymoron", "paide": "paid", "paitience": "patience", "paleolitic": "paleolithic",
    "paliamentarian": "parliamentarian", "palistian": "palestinian", "palistinian": "palestinian",
    "palistinians": "palestinians", "pallete": "palette", "pamflet": "pamphlet",
    "pamplet": "pamphlet", "pantomine": "pantomime", "papanicalou": "papanicolaou",
    "paralel": "parallel", "paralell": "parallel", "paralelly": "parallelly",
    "paralely": "parallelly", "parallely": "parallelly", "paranthesis": "parenthesis",
    "paraphenalia": "paraphernalia", "parellels": "parallels", "parisitic": "parasitic",
    "parituclar": "particular", "parliment": "parliament", "parrakeets": "parakeets",
    "parralel": "parallel", "parrallel": "parallel", "parrallell": "parallel",
    "parrallelly": "parallelly", "parrallely": "parallelly", "partialy": "partially",
    "particually": "particularly", "particualr": "particular", "particuarly": "particularly",
    "particularily": "particularly", "particulary": "particularly", "pary": "party",
    "pased": "passed", "pasengers": "passengers", "passerbys": "passersby", "pasttime": "pastime",
    "pastural": "pastoral", "paticular": "particular", "pattented": "patented",
    "pavillion": "pavilion", "pblisher": "publisher", "pbulisher": "publisher",
    "peageant": "pageant", "peaple": "people", "peaples": "peoples", "peculure": "peculiar",
    "pedestrain": "pedestrian", "peformed": "performed", "peloponnes": "peloponnesus",
    "penatly": "penalty", "penerator": "penetrator", "penisula": "peninsula",
    "penisular": "peninsular", "penninsula": "peninsula", "penninsular": "peninsular",
    "pennisula": "peninsula", "pennyslvania": "pennsylvania", "pensle": "pencil",
    "pensinula": "peninsula", "peom": "poem", "peoms": "poems", "peopels": "peoples",
    "peotry": "poetry", "perade": "parade", "percepted": "perceived", "percieve": "perceive",
    "percieved": "perceived", "pereguine": "peregrine", "perenially": "perennially",
    "peretrator": "perpetrator", "perfomance": "performance", "perfomers": "performers",
    "performence": "performance", "perhasp": "perhaps", "perheaps": "perhaps", "perhpas": "perhaps",
    "peripathetic": "peripatetic", "peristent": "persistent", "perjery": "perjury",
    "perjorative": "pejorative", "permanant": "permanent", "permenant": "permanent",
    "permenantly": "permanently", "permissable": "permissible", "perogative": "prerogative",
    "peronal": "personal", "perpertrated": "perpetrated", "perosnality": "personality",
    "perphas": "perhaps", "perpindicular": "perpendicular", "persan": "person",
    "perseverence": "perseverance", "persistance": "persistence", "personell": "personnel",
    "personnell": "personnel", "persuded": "persuaded", "persue": "pursue", "persued": "pursued",
    "persuing": "pursuing", "persuit": "pursuit", "persuits": "pursuits",
    "pertubation": "perturbation", "pertubations": "perturbations", "pessiary": "pessary",
    "petetion": "petition", "pharoah": "pharaoh", "phenomenom": "phenomenon",
    "phenomenonal": "phenomenal", "phenomenonly": "phenomenally", "phenomonenon": "phenomenon",
    "phenomonon": "phenomenon", "phenonmena": "phenomena", "philipines": "philippines",
    "philisopher": "philosopher", "philisophical": "philosophical", "philisophy": "philosophy",
    "phillipine": "philippine", "phillipines": "philippines", "phillippines": "philippines",
    "phillosophically": "philosophically", "philospher": "philosopher",
    "philosphies": "philosophies", "philosphy": "philosophy", "phonecian": "phoenecian",
    "phongraph": "phonograph", "phylosophical": "philosophical", "physicaly": "physically",
    "piblisher": "publisher", "pich": "pitch", "pilgrimmage": "pilgrimage",
    "pilgrimmages": "pilgrimages", "pinapple": "pineapple", "pinnaple": "pineapple",
    "pinoneered": "pioneered", "plagarism": "plagiarism", "planation": "plantation",
    "plantiff": "plaintiff", "plateu": "plateau", "plausable": "plausible",
    "playright": "playwright", "playwrite": "playwright", "playwrites": "playwrights",
    "pleasent": "pleasant", "plebicite": "plebiscite", "plesant": "pleasant", "poenis": "penis",
    "poeoples": "peoples", "poety": "poetry", "poisin": "poison", "polical": "political",
    "polinator": "pollinator", "polinators": "pollinators", "politican": "politician",
    "politicans": "politicians", "poltical": "political", "polute": "pollute",
    "poluted": "polluted", "polutes": "pollutes", "poluting": "polluting", "polution": "pollution",
    "polyphonyic": "polyphonic", "polysaccaride": "polysaccharide",
    "polysaccharid": "polysaccharide", "pomegranite": "pomegranate", "pomotion": "promotion",
    "poportional": "proportional", "popoulation": "population", "popularaty": "popularity",
    "populare": "popular", "populer": "popular", "porshan": "portion", "porshon": "portion",
    "portait": "portrait", "portayed": "portrayed", "portraing": "portraying",
    "portugese": "portuguese", "portuguease": "portuguese", "portugues": "portuguese",
    "posess": "possess", "posessed": "possessed", "posesses": "possesses",
    "posessing": "possessing", "posessions": "possessions", "posion": "poison",
    "possable": "possible", "possably": "possibly", "posseses": "possesses",
    "possesing": "possessing", "possesion": "possession", "possessess": "possesses",
    "possibile": "possible", "possibilty": "possibility", "possiblility": "possibility",
    "possiblilty": "possibility", "possiblities": "possibilities", "possiblity": "possibility",
    "possition": "position", "postdam": "potsdam", "posthomous": "posthumous",
    "postion": "position", "postive": "positive", "potatos": "potatoes", "potrait": "portrait",
    "potrayed": "portrayed", "poulations": "populations", "poverful": "powerful",
    "poweful": "powerful", "powerfull": "powerful", "ppublisher": "publisher",
    "practial": "practical", "practially": "practically", "practicaly": "practically",
    "practicioner": "practitioner", "practicioners": "practitioners", "practicly": "practically",
    "practioner": "practitioner", "practioners": "practitioners", "prairy": "prairie",
    "prarie": "prairie", "praries": "prairies", "pratice": "practice", "preample": "preamble",
    "precedessor": "predecessor", "preceed": "precede", "preceeded": "preceded",
    "preceeding": "preceding", "preceeds": "precedes", "precentage": "percentage",
    "precice": "precise", "precisly": "precisely", "precurser": "precursor",
    "predecesors": "predecessors", "predicatble": "predictable", "predicitons": "predictions",
    "predomiantly": "predominately", "prefering": "preferring", "preferrably": "preferably",
    "pregancies": "pregnancies", "preiod": "period", "preliferation": "proliferation",
    "premeire": "premiere", "premeired": "premiered", "premillenial": "premillennial",
    "preminence": "preeminence", "premission": "permission",
    "premonasterians": "premonstratensians", "preocupation": "preoccupation", "prepair": "prepare",
    "prepartion": "preparation", "prepatory": "preparatory", "preperation": "preparation",
    "preperations": "preparations", "preriod": "period", "presedential": "presidential",
    "presidenital": "presidential", "presidental": "presidential", "presitgious": "prestigious",
    "prespective": "perspective", "prestigeous": "prestigious", "prestigous": "prestigious",
    "presumabely": "presumably", "presumibly": "presumably", "pretection": "protection",
    "prevelant": "prevalent", "preverse": "perverse", "previvous": "previous",
    "pricipal": "principal", "priciple": "principle", "priestood": "priesthood",
    "primarly": "primarily", "primative": "primitive", "primatively": "primitively",
    "primatives": "primitives", "primordal": "primordial", "principlaity": "principality",
    "principaly": "principality", "principial": "principal", "principly": "principally",
    "prinicipal": "principal", "privalege": "privilege", "privaleges": "privileges",
    "priveledges": "privileges", "privelege": "privilege", "priveleged": "privileged",
    "priveleges": "privileges", "privelige": "privilege", "priveliged": "privileged",
    "priveliges": "privileges", "privelleges": "privileges", "privilage": "privilege",
    "priviledge": "privilege", "priviledges": "privileges", "privledge": "privilege",
    "privte": "private", "probabilaty": "probability", "probablistic": "probabilistic",
    "probablly": "probably", "probalibity": "probability", "probelm": "problem",
    "proccess": "process", "proccessing": "processing", "procedger": "procedure",
    "procedings": "proceedings", "proceedure": "procedure", "proces": "process",
    "processer": "processor", "proclaimation": "proclamation", "proclamed": "proclaimed",
    "proclaming": "proclaiming", "proclomation": "proclamation", "profesor": "professor",
    "professer": "professor", "proffesed": "professed", "proffesion": "profession",
    "proffesor": "professor", "proffession": "profession", "proffessional": "professional",
    "proffessor": "professor", "profilic": "prolific", "progessed": "progressed",
    "progidy": "prodigy", "programable": "programmable", "prohabition": "prohibition",
    "prologomena": "prolegomena", "prominance": "prominence", "prominant": "prominent",
    "prominantly": "prominently", "promiscous": "promiscuous", "promotted": "promoted",
    "pronomial": "pronominal", "pronouced": "pronounced", "pronounched": "pronounced",
    "pronounciation": "pronunciation", "proove": "prove", "prooved": "proved",
    "prophacy": "prophecy", "propietary": "proprietary", "propmted": "prompted",
    "propoganda": "propaganda", "propogate": "propagate", "propogates": "propagates",
    "propogation": "propagation", "propostion": "proposition", "propotions": "proportions",
    "propper": "proper", "propperly": "properly", "proprietory": "proprietary",
    "proseletyzing": "proselytizing", "protaganist": "protagonist", "protaganists": "protagonists",
    "protocal": "protocol", "protoganist": "protagonist", "protrayed": "portrayed",
    "protruberance": "protuberance", "protruberances": "protuberances",
    "prouncements": "pronouncements", "provacative": "provocative", "provded": "provided",
    "provicial": "provincial", "provinicial": "provincial", "provisiosn": "provision",
    "provisonal": "provisional", "proximty": "proximity", "pseudononymous": "pseudonymous",
    "pseudonyn": "pseudonym", "psuedo": "pseudo", "psycology": "psychology", "psyhic": "psychic",
    "pubilsher": "publisher", "pubisher": "publisher", "publiaher": "publisher",
    "publicaly": "publicly", "publicher": "publisher", "publihser": "publisher",
    "publisehr": "publisher", "publiser": "publisher", "publisger": "publisher",
    "publisheed": "published", "publisherr": "publisher", "publishher": "publisher",
    "publishor": "publisher", "publishre": "publisher", "publissher": "publisher",
    "publlisher": "publisher", "publsiher": "publisher", "publusher": "publisher",
    "puchasing": "purchasing", "pucini": "puccini", "pulisher": "publisher", "pumkin": "pumpkin",
    "puplisher": "publisher", "puritannical": "puritanical", "purposedly": "purposely",
    "purpotedly": "purportedly", "pursuade": "persuade", "pursuaded": "persuaded",
    "pursuades": "persuades", "pususading": "persuading", "puting": "putting", "pwoer": "power",
    "pyscic": "psychic", "quantaty": "quantity", "quantitiy": "quantity",
    "quarantaine": "quarantine", "queenland": "queensland", "questonable": "questionable",
    "quicklyu": "quickly", "quinessential": "quintessential", "quitted": "quit",
    "quizes": "quizzes", "rabinnical": "rabbinical", "racaus": "raucous",
    "radiactive": "radioactive", "radify": "ratify", "raelly": "really", "rarified": "rarefied",
    "reaccurring": "recurring", "reacing": "reaching", "reacll": "recall",
    "readmition": "readmission", "realitvely": "relatively", "realsitic": "realistic",
    "realtions": "relations", "realyl": "really", "reasearch": "research",
    "rebiulding": "rebuilding", "rebllions": "rebellions", "rebounce": "rebound",
    "reccomendations": "recommendations", "reccomended": "recommended",
    "reccomending": "recommending", "reccommend": "recommend", "reccommended": "recommended",
    "reccommending": "recommending", "reccuring": "recurring", "receeded": "receded",
    "receeding": "receding", "recepient": "recipient", "recepients": "recipients",
    "receving": "receiving", "rechargable": "rechargeable", "reched": "reached", "recide": "reside",
    "recided": "resided", "recident": "resident", "recidents": "residents", "reciding": "residing",
    "reciepents": "recipients", "recieved": "received", "reciever": "receiver",
    "recievers": "receivers", "recieves": "receives", "recieving": "receiving",
    "recipiant": "recipient", "recipiants": "recipients", "recived": "received",
    "recivership": "receivership", "recogise": "recognise", "recogize": "recognize",
    "recomended": "recommended", "recomending": "recommending", "recomends": "recommends",
    "recommedations": "recommendations", "recompence": "recompense",
    "reconaissance": "reconnaissance", "reconcilation": "reconciliation", "reconized": "recognized",
    "reconnaisance": "reconnaissance", "reconnaissence": "reconnaissance",
    "recontructed": "reconstructed", "recquired": "required", "recrational": "recreational",
    "recrod": "record", "recuiting": "recruiting", "recuring": "recurring",
    "recurrance": "recurrence", "rediculous": "ridiculous", "reedeming": "redeeming",
    "reenforced": "reinforced", "refect": "reflect", "refedendum": "referendum",
    "referal": "referral", "referece": "reference", "refereces": "references",
    "referemce": "reference", "referemces": "references", "referencs": "references",
    "referenece": "reference", "refereneced": "referenced", "refereneces": "references",
    "referiang": "referring", "refering": "referring", "refernces": "references",
    "referrence": "reference", "referrences": "references", "referrs": "refers",
    "reffered": "referred", "refference": "reference", "reffering": "referring",
    "refrence": "reference", "refrences": "references", "refrers": "refers",
    "refridgeration": "refrigeration", "refridgerator": "refrigerator", "refromist": "reformist",
    "refusla": "refusal", "regardes": "regards", "regluar": "regular", "reguarly": "regularly",
    "regulaion": "regulation", "regulaotrs": "regulators", "regularily": "regularly",
    "rehersal": "rehearsal", "reicarnation": "reincarnation", "reigining": "reigning",
    "reknown": "renown", "reknowned": "renowned", "rela": "real", "relaly": "really",
    "relatiopnship": "relationship", "relativly": "relatively", "relected": "reelected",
    "releive": "relieve", "releived": "relieved", "releiver": "reliever", "releses": "releases",
    "relevence": "relevance", "reliablity": "reliability", "relient": "reliant",
    "religeous": "religious", "religously": "religiously", "relinqushment": "relinquishment",
    "relitavely": "relatively", "relpacement": "replacement", "remaing": "remaining",
    "rememberable": "memorable", "rememberance": "remembrance", "remembrence": "remembrance",
    "remenant": "remnant", "remenicent": "reminiscent", "reminent": "remnant",
    "reminescent": "reminiscent", "reminscent": "reminiscent", "reminsicent": "reminiscent",
    "rendevous": "rendezvous", "rendezous": "rendezvous", "renedered": "rende", "renewl": "renewal",
    "rennovate": "renovate", "rennovated": "renovated", "rennovating": "renovating",
    "rennovation": "renovation", "rentors": "renters", "reoccurrence": "recurrence",
    "reorganision": "reorganisation", "repblic": "republic", "repblican": "republican",
    "repblicans": "republicans", "repblics": "republics", "repectively": "respectively",
    "repeition": "repetition", "repentence": "repentance", "repentent": "repentant",
    "repeteadly": "repeatedly", "repetion": "repetition", "repid": "rapid", "reponse": "response",
    "reponsible": "responsible", "reportadly": "reportedly", "represantative": "representative",
    "representive": "representative", "representives": "representatives",
    "reproducable": "reproducible", "reprtoire": "repertoire", "repsectively": "respectively",
    "reptition": "repetition", "repubic": "republic", "repubican": "republican",
    "repubicans": "republicans", "repubics": "republics", "republi": "republic",
    "republian": "republican", "republians": "republicans", "republis": "republics",
    "repulic": "republic", "repulican": "republican", "repulicans": "republicans",
    "repulics": "republics", "requirment": "requirement", "requred": "required",
    "resaurant": "restaurant", "resembelance": "resemblance", "resembes": "resembles",
    "resemblence": "resemblance", "resevoir": "reservoir", "residental": "residential",
    "resignement": "resignment", "resistable": "resistible", "resistent": "resistant",
    "respectivly": "respectively", "responce": "response", "responibilities": "responsibilities",
    "responisble": "responsible", "responnsibilty": "responsibility", "responsibile": "responsible",
    "responsibilites": "responsibilities", "responsiblities": "responsibilities",
    "responsiblity": "responsibility", "ressemblance": "resemblance", "ressemble": "resemble",
    "ressembled": "resembled", "ressemblence": "resemblance", "ressembling": "resembling",
    "resssurecting": "resurrecting", "ressurect": "resurrect", "ressurected": "resurrected",
    "ressurection": "resurrection", "ressurrection": "resurrection", "restarant": "restaurant",
    "restarants": "restaurants", "restaraunteur": "restaurateur", "restaraunteurs": "restaurateurs",
    "restaraunts": "restaurants", "restauranteurs": "restaurateurs", "restauration": "restoration",
    "restauraunt": "restaurant", "resteraunt": "restaurant", "resteraunts": "restaurants",
    "resticted": "restricted", "resturant": "restaurant", "resturants": "restaurants",
    "resturaunt": "restaurant", "resturaunts": "restaurants", "resurecting": "resurrecting",
    "retalitated": "retaliated", "retalitation": "retaliation", "retreive": "retrieve",
    "returnd": "returned", "revaluated": "reevaluated", "reveiw": "review", "reveral": "reversal",
    "reversable": "reversible", "revolutionar": "revolutionary", "rewitten": "rewritten",
    "rewriet": "rewrite", "rference": "reference", "rferences": "references", "rhymme": "rhyme",
    "rhythem": "rhythm", "rhythim": "rhythm", "rhytmic": "rhythmic", "rigourous": "rigorous",
    "rininging": "ringing", "rockerfeller": "rockefeller", "rococco": "rococo", "rocord": "record",
    "roomate": "roommate", "rougly": "roughly", "rucuperate": "recuperate",
    "rudimentatry": "rudimentary", "rulle": "rule", "runing": "running", "runnung": "running",
    "russina": "russian", "russion": "russian", "rwite": "write", "rythem": "rhythm",
    "rythim": "rhythm", "rythmic": "rhythmic", "rythyms": "rhythms", "sacrafice": "sacrifice",
    "sacreligious": "sacrilegious", "sacremento": "sacramento", "sacrifical": "sacrificial",
    "saftey": "safety", "safty": "safety", "sanctionning": "sanctioning", "sandwhich": "sandwich",
    "sanhedrim": "sanhedrin", "santioned": "sanctioned", "sargant": "sergeant",
    "sargeant": "sergeant", "satelite": "satellite", "satelites": "satellites",
    "saterdays": "saturdays", "satisfactority": "satisfactorily", "satric": "satiric",
    "satrical": "satirical", "satrically": "satirically", "sattelite": "satellite",
    "sattelites": "satellites", "saught": "sought", "saveing": "saving", "saxaphone": "saxophone",
    "scaleable": "scalable", "scandanavia": "scandinavia", "scaricity": "scarcity",
    "scavanged": "scavenged", "scholarhip": "scholarship", "scientfic": "scientific",
    "scientifc": "scientific", "scientis": "scientist", "scince": "science", "scinece": "science",
    "scirpt": "script", "scoll": "scroll", "screenwrighter": "screenwriter",
    "scrutinity": "scrutiny", "scuptures": "sculptures", "seach": "search", "seached": "searched", "serch": "search", "serach": "search", "saerch": "search", "wbe": "web",
    "seaches": "searches", "secratary": "secretary", "secretery": "secretary",
    "sedereal": "sidereal", "seeked": "sought", "segementation": "segmentation",
    "seguoys": "segues", "seige": "siege", "seing": "seeing", "seinor": "senior",
    "seldomly": "seldom", "senarios": "scenarios", "senstive": "sensitive", "sensure": "censure",
    "seperated": "separated", "seperately": "separately", "seperates": "separates",
    "seperating": "separating", "seperation": "separation", "seperatism": "separatism",
    "seperatist": "separatist", "sepina": "subpoena", "sergent": "sergeant",
    "sernedipity": "serendipity", "serendipiyt": "serendipity", "settelement": "settlement",
    "settlment": "settlement", "sevral": "several", "sevreal": "several", "severeal": "several",
    "severley": "severely", "severly": "severely", "sevice": "service", "sexaul": "sexual",
    "sexaully": "sexually", "shadasloo": "shadaloo", "shaddow": "shadow", "shadoloo": "shadaloo",
    "sheild": "shield", "sherif": "sheriff", "shineing": "shining", "shiped": "shipped",
    "shopkeeepers": "shopkeepers", "shorly": "shortly", "shoudl": "should", "shreak": "shriek",
    "shrinked": "shrunk", "sicne": "since", "sideral": "sidereal", "siezure": "seizure",
    "siezures": "seizures", "siginificant": "significant", "signficant": "significant",
    "signficiant": "significant", "signfies": "signifies", "signifantly": "significantly",
    "significently": "significantly", "signifigant": "significant",
    "signifigantly": "significantly", "signitories": "signatories", "signitory": "signatory",
    "similarily": "similarly", "similiarity": "similarity", "similiarly": "similarly",
    "simmilar": "similar", "simpley": "simply", "simplier": "simpler",
    "simultanous": "simultaneous", "simultanously": "simultaneously", "sincerley": "sincerely",
    "singsog": "singsong", "sionist": "zionist", "sionists": "zionists", "sixtin": "sistine",
    "skagerak": "skagerrak", "skateing": "skating", "slaugterhouses": "slaughterhouses",
    "slighly": "slightly", "slowy": "slowly", "smae": "same", "smealting": "smelting",
    "smoe": "some", "sneeks": "sneaks", "snese": "sneeze", "socalism": "socialism",
    "socities": "societies", "soem": "some", "sofware": "software", "sohw": "show",
    "soilders": "soldiers", "solatary": "solitary", "soley": "solely", "soliders": "soldiers",
    "soliliquy": "soliloquy", "soluable": "soluble", "somene": "someone", "somtimes": "sometimes",
    "somwhere": "somewhere", "sophicated": "sophisticated", "sophmore": "sophomore",
    "sorceror": "sorcerer", "sorrounding": "surrounding", "sotry": "story", "soudn": "sound",
    "soudns": "sounds", "sountrack": "soundtrack", "sourth": "south", "sourthern": "southern",
    "souvenier": "souvenir", "souveniers": "souvenirs", "soveits": "soviets",
    "sovereignity": "sovereignty", "soverign": "sovereign", "soverignity": "sovereignty",
    "soverignty": "sovereignty", "spainish": "spanish", "specfic": "specific",
    "specifiying": "specifying", "speciman": "specimen", "spectauclar": "spectacular",
    "spectaulars": "spectaculars", "spectum": "spectrum", "speices": "species",
    "spendour": "splendour", "spermatozoan": "spermatozoon", "spoace": "space",
    "sponser": "sponsor", "sponsered": "sponsored", "spontanous": "spontaneous",
    "sponzored": "sponsored", "spoonfulls": "spoonfuls", "sppeches": "speeches",
    "spreaded": "spread", "sprech": "speech", "spred": "spread", "spriritual": "spiritual",
    "spritual": "spiritual", "sqaure": "square", "stablility": "stability",
    "stainlees": "stainless", "staion": "station", "standars": "standards", "stange": "strange",
    "startegic": "strategic", "startegies": "strategies", "startegy": "strategy",
    "stateman": "statesman", "statememts": "statements", "statment": "statement",
    "steriods": "steroids", "sterotypes": "stereotypes", "stilus": "stylus",
    "stingent": "stringent", "stiring": "stirring", "stirrs": "stirs", "stlye": "style",
    "stomache": "stomach", "stong": "strong", "stopry": "story", "storeis": "stories",
    "storise": "stories", "stornegst": "strongest", "stoyr": "story", "stpo": "stop",
    "stradegies": "strategies", "stradegy": "strategy", "straght": "straight",
    "stragiht": "straight", "stratagically": "strategically", "streemlining": "streamlining",
    "stregth": "strength", "strenghen": "strengthen", "strenghened": "strengthened",
    "strenghening": "strengthening", "strenght": "strength", "strenghten": "strengthen",
    "strenghtened": "strengthened", "strenghtening": "strengthening", "strengtened": "strengthened",
    "strenous": "strenuous", "strenuos": "strenuous", "strictist": "strictest",
    "strikely": "strikingly", "strnad": "strand", "structual": "structural",
    "structuer": "structure", "stubborness": "stubbornness", "stucture": "structure",
    "stuctured": "structured", "stuggling": "struggling", "sturcture": "structure",
    "sturctural": "structural", "subcatagories": "subcategories", "subcatagory": "subcategory",
    "subconsiously": "subconsciously", "subdivisio": "subdivision", "subjudgation": "subjugation",
    "submachne": "submachine", "subpecies": "subspecies", "subsidary": "subsidiary",
    "subsiduary": "subsidiary", "subsquent": "subsequent", "subsquently": "subsequently",
    "substace": "substance", "substancial": "substantial", "substatial": "substantial",
    "substituded": "substituted", "substract": "subtract", "substracted": "subtracted",
    "substracting": "subtracting", "substraction": "subtraction", "substracts": "subtracts",
    "subtances": "substances", "subterranian": "subterranean", "suburburban": "suburban",
    "succceeded": "succeeded", "succcesses": "successes", "succedded": "succeeded",
    "succeded": "succeeded", "succeds": "succeeds", "succesfully": "successfully",
    "succesfuly": "successfully", "succesion": "succession", "succesive": "successive",
    "successfull": "successful", "successully": "successfully", "succsess": "success",
    "succsessfull": "successful", "suceed": "succeed", "suceeded": "succeeded",
    "suceeding": "succeeding", "suceeds": "succeeds", "sucesful": "successful",
    "sucesfully": "successfully", "sucesfuly": "successfully", "sucesion": "succession",
    "sucess": "success", "sucesses": "successes", "sucessful": "successful",
    "sucessfull": "successful", "sucessfully": "successfully", "sucessfuly": "successfully",
    "sucession": "succession", "sucessive": "successive", "sucessor": "successor",
    "sucessot": "successor", "sucide": "suicide", "sucidial": "suicidal", "sudent": "student",
    "sudents": "students", "sufferage": "suffrage", "sufferred": "suffered",
    "sufferring": "suffering", "sufficent": "sufficient", "sufficently": "sufficiently",
    "sumary": "summary", "sunglases": "sunglasses", "suop": "soup", "superceeded": "superseded",
    "superintendant": "superintendent", "suphisticated": "sophisticated",
    "suplimented": "supplemented", "supose": "suppose", "suposed": "supposed",
    "suposedly": "supposedly", "suposes": "supposes", "suposing": "supposing",
    "supplamented": "supplemented", "suppliementing": "supplementing", "suppoed": "supposed",
    "supposingly": "supposedly", "suppy": "supply", "suprassing": "surpassing",
    "supress": "suppress", "supressed": "suppressed", "supresses": "suppresses",
    "supressing": "suppressing", "suprised": "surprised", "suprising": "surprising",
    "suprisingly": "surprisingly", "suprize": "surprise", "suprized": "surprised",
    "suprizing": "surprising", "suprizingly": "surprisingly", "surfce": "surface",
    "suround": "surround", "surounded": "surrounded", "surounding": "surrounding",
    "suroundings": "surroundings", "surounds": "surrounds", "surplanted": "supplanted",
    "surpress": "suppress", "surpressed": "suppressed", "surprize": "surprise",
    "surprized": "surprised", "surprizing": "surprising", "surprizingly": "surprisingly",
    "surrepetitious": "surreptitious", "surrepetitiously": "surreptitiously",
    "surreptious": "surreptitious", "surreptiously": "surreptitiously", "surronded": "surrounded",
    "surrouded": "surrounded", "surrouding": "surrounding", "surrundering": "surrendering",
    "surveilence": "surveillance", "surveill": "surveil", "surveyer": "surveyor",
    "surviver": "survivor", "survivers": "survivors", "survivied": "survived",
    "suseptable": "susceptible", "suseptible": "susceptible", "suspention": "suspension",
    "swaer": "swear", "swaers": "swears", "swepth": "swept", "swiming": "swimming", "syas": "says",
    "symetrical": "symmetrical", "symetrically": "symmetrically", "symetry": "symmetry",
    "symettric": "symmetric", "symmetral": "symmetric", "symmetricaly": "symmetrically",
    "synagouge": "synagogue", "syncronization": "synchronization", "synonomous": "synonymous",
    "synonymns": "synonyms", "synphony": "symphony", "syphyllis": "syphilis",
    "sypmtoms": "symptoms", "syrap": "syrup", "sysmatically": "systematically", "sytem": "system",
    "sytle": "style", "tabacco": "tobacco", "tahn": "than", "talekd": "talked",
    "targetted": "targeted", "targetting": "targeting", "tast": "taste", "tath": "that",
    "tattooes": "tattoos", "taxanomic": "taxonomic", "taxanomy": "taxonomy", "teached": "taught",
    "techician": "technician", "techicians": "technicians", "techiniques": "techniques",
    "technitian": "technician", "technnology": "technology", "technolgy": "technology",
    "tehy": "they", "telelevision": "television", "televsion": "television",
    "telphony": "telephony", "temerature": "temperature", "tempalte": "template",
    "tempaltes": "templates", "temparate": "temperate", "temperarily": "temporarily",
    "temperment": "temperament", "tempertaure": "temperature", "temperture": "temperature",
    "temprary": "temporary", "tenacle": "tentacle", "tenacles": "tentacles", "tendacy": "tendency",
    "tendancies": "tendencies", "tepmorarily": "temporarily", "terrestial": "terrestrial",
    "terriories": "territories", "terriory": "territory", "territorist": "terrorist",
    "territoy": "territory", "terroist": "terrorist", "testiclular": "testicular",
    "testomony": "testimony", "tghe": "the", "theather": "theater", "theese": "these",
    "theif": "thief", "theives": "thieves", "themselfs": "themselves", "themslves": "themselves",
    "therafter": "thereafter", "therby": "thereby", "theri": "their", "thgat": "that",
    "thge": "the", "thign": "thing", "thigns": "things", "thigsn": "things", "thikn": "think",
    "thikns": "thinks", "thiunk": "think", "thn": "then", "thna": "than", "thne": "then",
    "thnig": "thing", "thnigs": "things", "thoughout": "throughout", "threatend": "threatened",
    "threatning": "threatening", "threee": "three", "thrid": "third", "throrough": "thorough",
    "throughly": "thoroughly", "througout": "throughout", "thsi": "this", "thsoe": "those",
    "thta": "that", "thyat": "that", "tihkn": "think", "tihs": "this", "timne": "time",
    "tje": "the", "tjhe": "the", "tjpanishad": "upanishad", "tkae": "take", "tkaes": "takes",
    "tkaing": "taking", "tlaking": "talking", "tobbaco": "tobacco", "todya": "today",
    "toghether": "together", "tolerence": "tolerance", "tolkein": "tolkien", "tomatos": "tomatoes",
    "tommorrow": "tomorrow", "tongiht": "tonight", "toriodal": "toroidal",
    "tormenters": "tormentors", "tornadoe": "tornado", "torpeados": "torpedoes",
    "torpedos": "torpedoes", "tortise": "tortoise", "toubles": "troubles", "towords": "towards",
    "towrad": "toward", "tradionally": "traditionally", "traditionaly": "traditionally",
    "traditionnal": "traditional", "traditition": "tradition", "tradtionally": "traditionally",
    "trafficed": "trafficked", "trafficing": "trafficking", "trafic": "traffic",
    "trancendent": "transcendent", "trancending": "transcending", "tranform": "transform",
    "tranformed": "transformed", "transcendance": "transcendence", "transcendant": "transcendent",
    "transcendentational": "transcendental", "transending": "transcending",
    "transesxuals": "transsexuals", "transfered": "transferred", "transfering": "transferring",
    "transformaton": "transformation", "transistion": "transition", "translater": "translator",
    "translaters": "translators", "transmissable": "transmissible",
    "transporation": "transportation", "tremelo": "tremolo", "tremelos": "tremolos",
    "trigered": "triggered", "triguered": "triggered", "triology": "trilogy", "troling": "trolling",
    "troup": "troupe", "trustworthyness": "trustworthiness", "tust": "trust", "tution": "tuition",
    "twon": "town", "twpo": "two", "tyhat": "that", "tyhe": "they", "typcial": "typical",
    "typicaly": "typically", "tyranies": "tyrannies", "tyrranies": "tyrannies",
    "tyrrany": "tyranny", "ubiquitious": "ubiquitous", "ublisher": "publisher", "uise": "use",
    "ukranian": "ukrainian", "ultimely": "ultimately", "unacompanied": "unaccompanied",
    "unahppy": "unhappy", "unanymous": "unanimous", "unathorised": "unauthorised",
    "unavailible": "unavailable", "unballance": "unbalance", "unbeknowst": "unbeknownst",
    "unbeleivable": "unbelievable", "uncertainity": "uncertainty",
    "unchallengable": "unchallengeable", "unchangable": "unchangeable",
    "uncompetive": "uncompetitive", "unconcious": "unconscious",
    "unconciousness": "unconsciousness", "unconfortability": "discomfort",
    "uncontitutional": "unconstitutional", "unconvential": "unconventional",
    "undecideable": "undecidable", "understoon": "understood", "undesireable": "undesirable",
    "undetecable": "undetectable", "undoubtely": "undoubtedly", "undreground": "underground",
    "uneccesary": "unnecessary", "unecessary": "unnecessary", "unequalities": "inequalities",
    "unforseen": "unforeseen", "unforetunately": "unfortunately", "unforgetable": "unforgettable",
    "unforgiveable": "unforgivable", "unfortunatley": "unfortunately",
    "unfourtunately": "unfortunately", "unihabited": "uninhabited", "unilateraly": "unilaterally",
    "unilatreal": "unilateral", "unilatreally": "unilaterally", "uninterruped": "uninterrupted",
    "uninterupted": "uninterrupted", "unitesstates": "unitedstates", "univeral": "universal",
    "univeristies": "universities", "univerity": "university", "universtiy": "university",
    "univesities": "universities", "univesity": "university", "unkown": "unknown",
    "unlikey": "unlikely", "unmistakeably": "unmistakably", "unneccesarily": "unnecessarily",
    "unneccesary": "unnecessary", "unneccessarily": "unnecessarily", "unneccessary": "unnecessary",
    "unnecesarily": "unnecessarily", "unnecesary": "unnecessary", "unoffical": "unofficial",
    "unoperational": "nonoperational", "unoticeable": "unnoticeable", "unplease": "displease",
    "unplesant": "unpleasant", "unprecendented": "unprecedented", "unprecidented": "unprecedented",
    "unrepentent": "unrepentant", "unrepetant": "unrepentant", "unrepetent": "unrepentant",
    "unsubstanciated": "unsubstantiated", "unsuccesful": "unsuccessful",
    "unsuccesfully": "unsuccessfully", "unsuccessfull": "unsuccessful",
    "unsucesful": "unsuccessful", "unsucesfuly": "unsuccessfully", "unsucessful": "unsuccessful",
    "unsucessfull": "unsuccessful", "unsucessfully": "unsuccessfully", "unsuprised": "unsurprised",
    "unsuprising": "unsurprising", "unsuprisingly": "unsurprisingly", "unsuprized": "unsurprised",
    "unsuprizing": "unsurprising", "unsuprizingly": "unsurprisingly", "unsurprized": "unsurprised",
    "unsurprizing": "unsurprising", "unsurprizingly": "unsurprisingly",
    "untranslateable": "untranslatable", "unuseable": "unusable", "unusuable": "unusable",
    "unviersity": "university", "unwarrented": "unwarranted", "unweildly": "unwieldy",
    "unwieldly": "unwieldy", "upcomming": "upcoming", "upgradded": "upgraded", "useage": "usage",
    "usefull": "useful", "usefuly": "usefully", "useing": "using", "ususally": "usually",
    "vaccume": "vacuum", "vacinity": "vicinity", "vaguaries": "vagaries", "vaieties": "varieties",
    "vailidty": "validity", "valetta": "valletta", "valuble": "valuable", "valueable": "valuable",
    "varations": "variations", "varient": "variant", "variey": "variety", "varing": "varying",
    "varities": "varieties", "varity": "variety", "vasall": "vassal", "vasalls": "vassals",
    "vegatarian": "vegetarian", "vegitable": "vegetable", "vegitables": "vegetables",
    "vehicule": "vehicle", "vell": "well", "venemous": "venomous", "vengance": "vengeance",
    "vengence": "vengeance", "verfication": "verification", "verison": "version",
    "verisons": "versions", "vermillion": "vermilion", "versitilaty": "versatility",
    "versitlity": "versatility", "vetween": "between", "veyr": "very", "vigilence": "vigilance",
    "vigourous": "vigorous", "villian": "villain", "villification": "vilification",
    "villify": "vilify", "vincinity": "vicinity", "violentce": "violence", "virtualy": "virtually",
    "virutal": "virtual", "virutally": "virtually", "visable": "visible", "visably": "visibly",
    "visting": "visiting", "vistors": "visitors", "vitories": "victories", "volcanoe": "volcano",
    "voleyball": "volleyball", "volontary": "voluntary", "volonteer": "volunteer",
    "volonteered": "volunteered", "volonteering": "volunteering", "volonteers": "volunteers",
    "volounteer": "volunteer", "volounteered": "volunteered", "volounteering": "volunteering",
    "volounteers": "volunteers", "volumne": "volume", "vreity": "variety", "vrey": "very",
    "vriety": "variety", "vulnerablility": "vulnerability", "vyer": "very", "vyre": "very",
    "warantee": "warranty", "wardobe": "wardrobe", "warrent": "warrant", "warrriors": "warriors",
    "wass": "was", "watn": "want", "wayword": "wayward", "weaponary": "weaponry", "weas": "was",
    "wehn": "when", "weilded": "wielded", "wendsay": "wednesday", "wereabouts": "whereabouts",
    "whant": "want", "whants": "wants", "wheras": "whereas", "wherease": "whereas", "whic": "which",
    "whith": "with", "whlch": "which", "wholey": "wholly", "whta": "what", "whther": "whether",
    "widesread": "widespread", "wief": "wife", "wiew": "view", "wille": "will", "willk": "will",
    "willingless": "willingness", "wirting": "writing", "witheld": "withheld", "withh": "with",
    "withold": "withhold", "witht": "with", "witn": "with", "wiull": "will", "wnat": "want",
    "wnated": "wanted", "wnats": "wants", "wohle": "whole", "wokr": "work", "wokring": "working",
    "wonderfull": "wonderful", "wordlwide": "worldwide", "workststion": "workstation",
    "worls": "world", "worstened": "worsened", "woudl": "would", "wresters": "wrestlers",
    "wriet": "write", "wroet": "wrote", "wrok": "work", "wroking": "working", "wupport": "support",
    "xenophoby": "xenophobia", "yaching": "yachting", "yaer": "year", "yaerly": "yearly",
    "yaers": "years", "yatch": "yacht", "yearm": "year", "yeasr": "years", "yeild": "yield",
    "yeilding": "yielding", "yera": "year", "yrea": "year", "yeras": "years", "yersa": "years",
    "yotube": "youtube", "youseff": "yousef", "youself": "yourself", "ytou": "you", "yuo": "you",
    "zeebra": "zebra", "whate": "what", "whrn": "when", "qhere": "where", "wherr": "where",
    "whu": "who", "ehat": "what", "qhat": "what", "ehich": "which", "tjis": "this", "tjay": "that",
    "thst": "that", "hre": "here", "tjere": "there", "ther": "there", "wroye": "wrote",
    "writte": "write", "qrote": "wrote", "notess": "notes", "ntoes": "notes", "notw": "note",
    "noye": "note", "ntoe": "note", "srch": "search", "searchh": "search", "zearch": "search",
    "ssearach": "search", "fnd": "find", "fimd": "find", "dimd": "find", "shlw": "show",
    "shiw": "show", "telll": "tell", "twll": "tell", "lsit": "list", "lidt": "list",
    "todo": "to do", "to-do": "to do", "reming": "remind", "rekjnd": "remind", "remimd": "remind",
    "yeserday": "yesterday", "yestarday": "yesterday", "yeseterday": "yesterday", "todsy": "today",
    "wekk": "week", "wek": "week", "monfh": "month", "momth": "month", "yesr": "year",
    "bcus": "because", "abwt": "about", "gnna": "going to", "gona": "going to", "wana": "want to",
    "tks": "thanks", "plx": "please", "sence": "sense", "frfr": "for real",
    "hella": "very",
})

#: Added 2026-10-10: compliments, complaints and feelings as small talk, a
#: message made only of these is answered by `composer.social`.
SOCIAL.update({
    "good": "compliment", "amazing": "compliment", "best": "compliment", "smart": "compliment",
    "bad": "insult", "stupid": "insult", "dumb": "insult", "useless": "insult", "idiot": "insult",
    "terrible": "insult", "awful": "insult", "worst": "insult", "tired": "emotion",
    "stressed": "emotion", "happy": "glad", "sad": "emotion", "angry": "emotion",
    "frustrated": "emotion", "exhausted": "emotion", "based": "ack", "lit": "ack",
    "sus": "confused", "cap": "confused", "cringe": "reaction", "bruh": "reaction",
    "gyat": "reaction", "skibidi": "reaction", "slay": "reaction", "w": "reaction", "l": "reaction",
    "fr": "ack", "frfr": "ack", "vibes": "ack", "cute": "compliment", "beautiful": "compliment",
    "pretty": "compliment", "handsome": "compliment", "gorgeous": "compliment",
    "stunning": "compliment", "fabulous": "compliment", "superb": "compliment",
    "outstanding": "compliment", "incredible": "compliment", "marvelous": "compliment",
    "genius": "compliment", "clever": "compliment", "intelligent": "compliment",
    "kind": "compliment", "rad": "compliment", "sick": "compliment", "epic": "compliment",
    "ugly": "insult", "horrible": "insult", "crap": "insult", "trash": "insult",
    "garbage": "insult", "rubbish": "insult", "junk": "insult", "sucks": "insult",
    "stinks": "insult", "boring": "insult", "lame": "insult", "weak": "insult",
    "pathetic": "insult", "worthless": "insult", "pointless": "insult", "hurray": "reaction",
    "yippee": "reaction", "jesus": "reaction", "christ": "reaction",
    #: A swear or a groan is frustration, answered calmly with an offer of
    #: help, never "Quite something" (INBOX 1459).
    "shit": "frustrated", "fuck": "frustrated", "fucking": "frustrated", "fuckin": "frustrated",
    "wtf": "frustrated", "ffs": "frustrated", "argh": "frustrated", "arg": "frustrated",
    "grr": "frustrated", "fml": "frustrated",
})
SOCIAL_PHRASES.update({
    "g'day": "greeting", "hiya mate": "greeting", "howdy partner": "greeting",
    "what is happening": "how", "what's happening": "how", "whats happening": "how",
    "how goes it": "how", "how are things going": "how", "my apologies": "sorry",
    "i am sorry": "sorry", "terribly sorry": "sorry", "say what": "confused", "hold up": "confused",
    "come again please": "confused", "i have no idea": "confused", "i do not know": "confused",
    "i am totally lost": "confused", "not making sense": "confused", "no freaking way": "reaction",
    "are you serious": "reaction", "you are kidding": "reaction", "are you kidding me": "reaction",
    "tell me about yourself": "who", "what are you": "who", "what do you do": "who",
    "good bot": "compliment", "good job": "compliment", "you are awesome": "compliment",
    "you're awesome": "compliment", "ur awesome": "compliment", "you are cute": "compliment",
    "you're cute": "compliment", "ur cute": "compliment", "you are the best": "compliment",
    "you're the best": "compliment", "ur the best": "compliment", "good boy": "compliment",
    "good girl": "compliment", "ur so cute": "compliment", "you know that": "ack",
    "u know that": "ack", "shut up": "insult", "fuck you": "insult", "fuck off": "insult",
    "go away": "insult", "for fucks sake": "frustrated", "for fuck's sake": "frustrated",
    "fuck sake": "frustrated", "fucks sake": "frustrated", "fucking hell": "frustrated", "bloody hell": "frustrated",
    "for god's sake": "frustrated", "for gods sake": "frustrated", "this is useless": "frustrated",
    "this sucks": "frustrated", "this is shit": "frustrated", "this is rubbish": "frustrated",
    "this is annoying": "frustrated", "so annoying": "frustrated", "not working": "frustrated",
    "you suck": "insult", "you're great": "compliment", "you are great": "compliment",
    "ur great": "compliment", "nice work": "compliment", "great job": "compliment",
    "great work": "compliment", "love it": "compliment", "feeling down": "emotion",
    #: Agreeing (ledger row 543): "think", "plan" and "idea" are note words,
    #: so "I think so" and "good plan" were searched for.
    "i think so": "ack", "i guess so": "ack", "i suppose so": "ack", "i hope so": "ack",
    "i believe so": "ack", "i think": "ack", "sounds like a plan": "ack", "sure thing": "ack",
    "good plan": "compliment", "gud plan": "compliment", "nice plan": "compliment",
    "great plan": "compliment", "good idea": "compliment", "gud idea": "compliment",
    "nice idea": "compliment", "great idea": "compliment", "good call": "compliment",
    "good point": "compliment", "nice one": "compliment",
})
SOCIAL.update({
    "bored": "emotion", "anxious": "emotion", "lonely": "emotion", "sleepy": "emotion",
    "nervous": "emotion", "upset": "emotion", "worried": "emotion", "overwhelmed": "emotion",
    #: Good news is not sadness: "i'm happy" once got "I'm sorry to hear that".
    "excited": "glad", "glad": "glad", "stoked": "glad", "thrilled": "glad", "relieved": "glad",
})


#: A letter typed three times or more ("yooooo", "heyyy", "thxxx").
_STRETCH = re.compile(r"([A-Za-z])\1{2,}")
_LETTERS = re.compile(r"[A-Za-z]+")


def _unstretched(word: str) -> str:
    """`word` with each run of three or more of a letter cut to one or two,
    whichever reads as a word: a small-talk word first ("heyyy" is "hey"),
    then a dictionary word with the double kept ("goood" is "good", not
    "god"); as typed when neither does or the runs are many."""
    runs = list(_STRETCH.finditer(word))
    if not runs or len(runs) > 3:
        return word
    shapes = [""]
    last = 0
    for run in runs:
        head = word[last:run.start()]
        shapes = [f"{s}{head}{run.group(1) * n}" for s in shapes for n in (1, 2)]
        last = run.end()
    shapes = [f"{s}{word[last:]}" for s in shapes if len(f"{s}{word[last:]}") >= 2]
    social = next((s for s in shapes if s.lower() in SOCIAL or s.lower() in SOCIAL_PHRASES), None)
    if social:
        return social
    return next((s for s in sorted(shapes, key=len, reverse=True) if spelling.is_word(s.lower())), word)


def destretch(text: str) -> str:
    """`text` with each stretched word read as its word (INBOX 1459: "yooooo"
    was answered as stray keys). Words with no run of three are untouched."""
    if not text or not _STRETCH.search(text):
        return text
    return _LETTERS.sub(lambda m: _unstretched(m.group(0)), text)


#: Sounds typed while thinking ("errrmmm", "umm", "uhh", "hmm"): read past,
#: never searched for (INBOX 1485). Not "er", "um" inside a word, or "hum".
_FILLER = re.compile(r"^(?:u+m+|u+h+m*|e+r+m+|e+r{2,}|h+m+|m{2,}|e+h+m+|a+h+m+)$", re.I)
#: A whitespace-bounded run is one word; the shape check is on that run alone
#: (letters, then the punctuation typed after them), so no pattern scans a long
#: run twice (CodeQL 1890, 1894).
_WORD_RUN = re.compile(r"\S+")
_FILLER_SHAPE = re.compile(r"([A-Za-z]+)[.,;:!…]*")


def _without_filler(run: re.Match[str]) -> str:
    word = _FILLER_SHAPE.fullmatch(run.group(0))
    return "" if word and _FILLER.match(word.group(1)) else run.group(0)


def drop_filler(text: str) -> str:
    """`text` without its filler words and the punctuation typed after them
    ("errrmmm. hi test test" is "hi test test"); as typed when nothing else
    is left ("hmm" alone is a turn of its own)."""
    if not text or not re.search(r"(?i)\b(?:u|e|h|m|a)", text):
        return text
    kept = _WORD_RUN.sub(_without_filler, text)
    if kept == text:
        return text
    #: Spaces fold within a line; the line breaks stay (a numbered list after a
    #: colon is steps, and "make this a flowchart:\n1. ..." must keep them).
    lines = [" ".join(line.split()) for line in kept.split("\n")]
    kept = "\n".join(line for line in lines if line).lstrip(",.;: \n")
    return kept if re.search(r"\w", kept) else text


#: "r u an ai??", "are you a real person", "am I talking to a bot", "who are
#: you", "what are you": a question about what it is talking to, answered by
#: Atlas about itself, never searched for in the notes or on the web (INBOX
#: 1485). Read at the end of the message, after any lead-in ("whoa, stop
#: right there"). "are u ok" stays a how-are-you.
_WHAT_I_AM = r"(?:an? )?(?:real )?(?:ai|a i|bot|robot|human|person|real|machine|program|computer|chatbot|llm|chatgpt|gpt|human being|actual person)"
_IDENTITY = re.compile(
    rf"(?:^| )(?:are|r) (?:you|u|ya) (?:even |actually |really |just )?{_WHAT_I_AM}(?: or (?:not|what|an? \w+|\w+))?(?: (?:lol|haha|though|tho|then|too|right|now|or what))*$"
    rf"|^(?:who|what) (?:are|r) (?:you|u|ya)(?: (?:exactly|even|actually|really|then|again|lol|anyway))*$"
    rf"|(?:^| )am i (?:talking|speaking|chatting|texting) (?:to|with) {_WHAT_I_AM}(?: or \w+(?: \w+)?)?$"
    r"|^(?:is this|is it|this is) (?:an? )?(?:ai|bot|robot|chatbot|real person|human|machine)(?: or \w+(?: \w+)?)?$"
)


def asks_identity(message: str) -> bool:
    """Whether `message` asks what Atlas is (`_IDENTITY`)."""
    text = " ".join(re.split(r"[^\w']+", strip_symbols(drop_filler(message or "")).lower())).strip()
    return len(text) <= 80 and bool(_IDENTITY.search(text))


def _social_phrases(text: str) -> tuple[list[str], str]:
    """The kinds of the social phrases in `text`, longest first, and the text without them."""
    kinds: list[str] = []
    for phrase in sorted(SOCIAL_PHRASES, key=len, reverse=True):
        pattern = rf"(?:^|\s){re.escape(phrase)}(?=\s|$)"
        if re.search(pattern, text):
            kinds.append(SOCIAL_PHRASES[phrase])
            text = re.sub(pattern, " ", text)
    return kinds, text


def social_kind(message: str) -> str | None:
    """The kind of conversational turn a message is when every part of it is
    one ("ty", "lol", "ok thx", "right ok", "wait what", "how r u", an emoji
    alone), else None: a turn with a question in it is a question. A question
    about what it is talking to is "who", whatever leads into it."""
    if asks_identity(message):
        return "who"
    raw = destretch(drop_filler((message or "").strip()))
    if raw and not strip_symbols(raw):
        return "reaction" if re.search(r"[\U0001F600-\U0001F64F]", raw) else "ack"
    text = strip_symbols(raw).lower()
    if re.fullmatch(r"[?\s]+", text):
        return "confused"
    text = " ".join(re.split(r"[^\w']+", text)).strip()
    kinds, text = _social_phrases(text)
    words = [w for w in text.split() if w and w not in _SOCIAL_FILLER]
    if not words and not kinds:
        return None
    for word in words:
        if _LAUGH.match(word):
            kinds.append("laugh")
        elif word in SOCIAL:
            kinds.append(SOCIAL[word])
        else:
            return None
    #: "ok thanks" is thanks; "lol ok" is laughter: the most telling part.
    for kind in ("repair", "confused", "thanks", "sorry", "bye", "morning", "greeting", "how", "who", "frustrated", "reaction", "laugh", "compliment", "insult", "emotion", "glad"):
        if kind in kinds:
            return kind
    return "ack"


# --- 2. typo repair ------------------------------------------------------------

#: The words whose spelling decides how a question is read: the asking words,
#: the small words around them, and the words that name a kind of question.
VOCABULARY = frozenset(
    """what when where who whom whose why how which many much often long
    is are was were do does did can could should would will has have had am
    the a an my me i you your about for of on in to with and or
    compare versus between difference latest status progress update explain
    summarise summarize overview anything everything recently recent newest
    remind tell list show give name say said know think mean
    there this that these those it its
    week month year today tomorrow yesterday morning tonight
    time date day""".split()
)

#: Asking words: the ones a typo is repaired towards first, and the only
#: ones a run-together word is split into ("whenis" is "when is").
ASKING = frozenset(
    """what when where who whose why how which many much often long
    is are was were do does did can could should would will has have had
    compare versus between difference latest status progress update explain
    summarise summarize overview remind tell list""".split()
)

#: The long words that name a kind of question, repaired wherever they are.
KIND_WORDS = frozenset(
    """compare versus between difference latest status progress update explain
    summarise summarize overview anything everything recently newest
    written writing thought mentioned""".split()
)

#: Real words one edit from an asking word, never "corrected": "then" is not
#: "when", "show" is not "how", "hat" is not "what". Also the words a
#: question's subject is often made of that sit near one.
REAL_WORDS = frozenset(
    """then than them they there here hat that wet wit shy now new few hen
    ten men hoe hot who how why any man main may mean many much lunch bunch
    such song along last lost late lest list lust state stat plain explains
    goes dues does dose lift gift wish wash with tell tall till fell sell
    well bell when what where which while whole whose those these hare care
    dare were wore wire mire ware wear year near dear bear fear gear hear
    rear tear the then toe tie tea ate eat oat cat car bar far jar tar war
    sing long lung hung rung sung wing king ring thing ling ding pong song
    has his hit hut had hid him her hen ham hay hey hi ho he hm mom mum dad
    one won own now how cow row low bow sow tow vow wow know knew knee
    box fox ox oil all ill well wall will mill fill hill kill pill till
    loan load lord lard list lost dentist""".split()
)

def allowance(word: str) -> float:
    """How far a word may be from the one it is read as, by its length: a
    three-letter word one slip, a long word two edits."""
    n = len(word)
    if n <= 2:
        return 0.0
    if n == 3:
        return 0.6
    if n <= 5:
        return 1.0
    if n <= 8:
        return 1.5
    return 2.0


_HOW_NEXT = frozenset("many much often long do does did to come can should far old big".split())


def nearest(word: str, vocabulary, after: str = "") -> str | None:  # noqa: ANN001
    """The one vocabulary word `word` is a typo of, or None: within its
    allowance, and nearer than any other by a clear margin (a tie is a
    guess, and no guess is made, except "how" against "who", which the next
    word settles)."""
    low = word.lower()
    if low in vocabulary or low in VOCABULARY or low in REAL_WORDS or not low.isalpha():
        return None
    limit = allowance(low)
    if not limit:
        return None
    scored = sorted((distance(low, v), v) for v in vocabulary if abs(len(v) - len(low)) <= 2)
    if not scored or scored[0][0] > limit:
        return None
    best = [v for d, v in scored if d <= scored[0][0] + 0.1]
    if set(best) == {"how", "who"}:
        how = after.lower() in _HOW_NEXT
        return "how" if how else "who"
    return best[0] if len(best) == 1 else None


#: How near a second reading must come to the chosen one, or how far the
#: chosen one may sit within its allowance, before the reading is unsure and
#: a "Did you mean ...?" offers the other (INBOX 741, the owner: "composer
#: could have clean fallback with did you mean to substitute??").
UNSURE_GAP = 0.35
UNSURE_SHARE = 0.75


def alternative(word: str, chosen: str, vocabulary) -> str | None:  # noqa: ANN001
    """The other word `word` could have meant when the reading as `chosen`
    is unsure, else None."""
    low = word.lower()
    limit = allowance(low)
    if not limit:
        return None
    mine = distance(low, chosen)
    others = sorted((distance(low, v), v) for v in vocabulary if v != chosen and abs(len(v) - len(low)) <= 2)
    near = [v for d, v in others if d <= limit and d - mine <= UNSURE_GAP]
    if near:
        return near[0]
    return None


def _split(word: str) -> str | None:
    """"whenis" is "when is", "howmany" is "how many": a run-together word
    whose two halves are an asking word and a vocabulary word."""
    low = word.lower()
    if len(low) < 5 or low in VOCABULARY or low in REAL_WORDS:
        return None
    for cut in range(2, len(low) - 1):
        head, tail = low[:cut], low[cut:]
        if head in ASKING and tail in VOCABULARY:
            return f"{head} {tail}"
    return None


#: A comma with no space after it ("mindmap,a nd"): the space typed late.
_COMMA_RUN = re.compile(r"(?<=[A-Za-z]),(?=[A-Za-z])")


def repair(text: str, report: list | None = None, known=frozenset(), fixed: list | None = None) -> str:  # noqa: ANN001
    """Slang spelled out, asking words put right, run-together words split
    and split words joined, then every other misspelt word read as the word it
    is near (`spelling`, Brief 90). `known` are words that are the person's
    own (their notes' words), never changed; so are names, capitals and
    anything with a digit. An unsure repair is added to `report` as
    {"typed", "chosen", "alternative"}; every misspelling put right (not slang
    spelled out) is added to `fixed` as (typed, chosen), which is what lets an
    answer say how it read the question."""
    #: A small-talk word is a word: "hi test" was glued into "hitest" (INBOX 1485).
    tokens = spelling.rejoin(_COMMA_RUN.sub(", ", strip_symbols(text)).split(" "), known, SLANG.keys() | SOCIAL.keys(), fixed)
    tokens = [spelling.drop_stray(t, known, fixed) for t in tokens]
    out: list[str] = []
    i = 0
    while i < len(tokens):
        i += _repair_token(tokens, i, out, text, report, known, fixed)
    return " ".join(w for w in _real_word_slips(out, fixed) if w)


#: Real-word slips (Brief 104): a word that is a word, read as another only
#: where its neighbour says so. After an intensifier comes an adjective
#: ("insanely god" is "insanely good"); "it's" before a noun is "its" ("it's
#: use of language").
_INTENSIFIERS = frozenset("very really so insanely super pretty too extremely incredibly quite crazy seriously".split())
_AFTER_INTENSIFIER = {"god": "good", "grate": "great"}
_ITS_NOUNS = frozenset(
    """use own name place way job size shape colour color purpose answer answers title content contents settings
    layout design tone voice speed memory language style owner data value text icon label wording choices""".split()
)


def _real_word_slips(tokens: list[str], fixed: list | None) -> list[str]:
    out = list(tokens)
    for i in range(1, len(out)):
        prev = out[i - 1].lower().rstrip("?!.,:;")
        word = out[i].rstrip("?!.,:;")
        tail = out[i][len(word):]
        low = word.lower()
        if prev in _INTENSIFIERS and low in _AFTER_INTENSIFIER and _AFTER_INTENSIFIER[low] != low:
            out[i] = _AFTER_INTENSIFIER[low] + tail
        elif low in _ITS_NOUNS and prev in ("it's", "it’s") and out[i - 1].rstrip("?!.,:;") == out[i - 1]:
            out[i - 1] = "its"
        else:
            continue
        if fixed is not None:
            fixed.append((f"{tokens[i - 1]} {tokens[i]}", f"{out[i - 1]} {out[i]}"))
    return out


def _join_asking(low: str, nxt: str, out: list[str]) -> bool:
    """Two pieces of one asking word ("wh en", "ho w"): joined onto `out`."""
    joined = (low + nxt.rstrip("?!.,:;").lower()) if nxt else ""
    if joined in ASKING and low not in VOCABULARY and len(low) <= 3:
        out.append(joined + nxt[len(nxt.rstrip("?!.,:;")):])
        return True
    return False


def _repair_token(tokens: list[str], i: int, out: list[str], text: str, report, known, fixed) -> int:  # noqa: ANN001
    """Puts the repaired reading of `tokens[i]` on `out`; returns how many
    tokens it used (two when the pieces of one asking word were joined)."""
    token = tokens[i]
    #: str.rstrip, not `(.*?)([?!.,:;]*)$`: that was quadratic on "!!!!" (CodeQL).
    word = token.rstrip("?!.,:;")
    tail = token[len(word):]
    low = word.lower()
    nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
    if _join_asking(low, nxt, out):
        return 2
    if _repair_late_space(low, tail, nxt, tokens, i, out, known):
        pass
    elif low in spelling.CONTRACTION_STEMS and word.islower() and nxt and low not in known:
        out.append(spelling.CONTRACTION_STEMS[low] + tail)
    #: A word of the person's own (a category "Uni", a tag) is never spelled out (audit 1028 E9).
    elif low in SLANG and low not in known and not (low in ("r", "y") and not _at_asking_place(out)):
        _repair_slang(low, word, tail, out, fixed)
    elif _split(low):
        out.append(_split(low) + tail)
        if fixed is not None:
            fixed.append((word, _split(low)))
    else:
        _repair_misspelt(token, word, tail, nxt, text, out, report, known, fixed)
    return 1


def _repair_late_space(low: str, tail: str, nxt: str, tokens: list[str], i: int, out: list[str], known) -> bool:  # noqa: ANN001
    """"as ther 17th": a date follows, so it is "the" (a "there" never is);
    "ther eis" is "there is", the space typed a letter late. True when it
    put a reading on `out`."""
    nxt_core = nxt.rstrip("?!.,:;").lower()
    if low in ("ther", "thr") and nxt_core[:1].isdigit() and low not in known:
        out.append("the" + tail)
        return True
    if not (low in SLANG and len(nxt_core) >= 3 and nxt_core.isalpha() and low not in known):
        return False
    if spelling.is_word(nxt_core, known):
        return False
    cut = spelling._resegment(low, nxt_core, known)
    if not cut:
        return False
    out.append(cut[0])
    tokens[i + 1] = cut[1] + nxt[len(nxt.rstrip("?!.,:;")):]
    return True


def _repair_slang(low: str, word: str, tail: str, out: list[str], fixed) -> None:  # noqa: ANN001
    out.append(SLANG[low] + tail)
    #: The table holds misspellings ("wehn") beside slang ("pls"): a
    #: word one slip from its reading is a typo, and is said.
    if fixed is not None and len(low) >= 3 and " " not in SLANG[low] and distance(low, SLANG[low]) <= 1.0:
        fixed.append((word, SLANG[low]))


def _report_alternative(low: str, word: str, chosen: str, pool, after: str, report: list) -> None:  # noqa: ANN001
    other = alternative(low, chosen, pool)
    #: "hwo many" is how and "hwo asked" is who: the next word
    #: settles it, and nothing is offered.
    if {chosen, other} == {"how", "who"} and (after.lower() in _HOW_NEXT or after.lower().endswith("ed")):
        other = None
    if other:
        report.append({"typed": word, "chosen": chosen, "alternative": other})


def _word_core(token: str) -> str:
    """A token without the punctuation after it."""
    while token and not (token[-1].isalnum() or token[-1] == "_"):
        token = token[:-1]
    return token


def _speller_may_read(word: str, out: list[str]) -> bool:
    """A lower-case word, or a capitalised one opening the question, may be a
    typo; shouting and names may not."""
    return word.isalpha() and not word.isupper() and (word.islower() or not out)


def _is_spelt(low: str, word: str, text: str, known) -> bool:  # noqa: ANN001
    """Already a word or an acronym, so not a typo: the speller knows "weird"
    (it is not "were"), and "API" in a sentence is not shouting."""
    return (len(low) >= 4 and spelling.is_word(low, known, strict=True)) or (len(word) > 1 and word.isupper() and not text.isupper())


def _repair_misspelt(token: str, word: str, tail: str, nxt: str, text: str, out: list[str], report, known, fixed) -> None:  # noqa: ANN001
    low = word.lower()
    after = _word_core(nxt)
    spelt = _is_spelt(low, word, text, known)
    chosen = nearest(low, ASKING, after) if _at_asking_place(out) and not spelt else None
    pool = ASKING
    if not chosen and _speller_may_read(word, out):
        if _repair_by_speller(word, tail, after, out, report, known, fixed):
            return
    #: Past the opening words only the long words that name a kind
    #: of question are repaired ("lastest"): a subject word near a
    #: small word ("slow", "show") is the subject.
    if not chosen and len(low) >= 6 and not spelt:
        chosen, pool = nearest(low, KIND_WORDS, after), KIND_WORDS
    if chosen and report is not None:
        _report_alternative(low, word, chosen, pool, after, report)
    if chosen and fixed is not None and chosen.lower() != low:
        fixed.append((word, chosen))
    out.append((chosen + tail) if chosen else token)


_SMALL_LEADS = frozenset("or an of to in on at by if so do is it as".split())


def _run_on_reading(word: str, known) -> tuple[str, str] | None:  # noqa: ANN001
    """A lower-case word that is two words run together, one of them small
    ("thenthe"), tried only when no list word is near."""
    if not word.islower():
        return None
    run_on = spelling.split_run_on(word, known)
    #: A small word run into a slang word ("orsmth" is "or smth"): the slang
    #: is not a list word, so `split_run_on` cannot see it; it is read as its
    #: own reading so the text is stable under a second repair.
    return run_on or next(
        ((word[:cut], SLANG[word[cut:]]) for cut in (2, 3) if word[:cut] in _SMALL_LEADS and len(word) > cut + 3 and word[cut:] in SLANG),
        None,
    )


def _repair_by_speller(word: str, tail: str, after: str, out: list[str], report, known, fixed) -> bool:  # noqa: ANN001
    """Reads a misspelt word as the word it is near (`spelling.fix`), or as two
    words run together, one of them small ("thenthe"), tried only when no list
    word is near; True when it did and `out` has the reading."""
    low = word.lower()
    read = spelling.fix(
        low, after=after.lower(), before=out[-1].strip("?!.,:;") if out else "", known=known, distance=distance,
    )
    #: A capitalised word read as a name the lists hold is a name of the
    #: person's own, spelled their way: "Cristopher called" is not
    #: "Kristopher called" (Brief 90's list, O3).
    if read and word[:1].isupper() and read[0] not in spelling._common():
        read = None
    if read:
        chosen = read[0].capitalize() if word[0].isupper() else read[0]
        if report is not None and read[1]:
            report.append({"typed": word, "chosen": chosen, "alternative": read[1]})
        out.append(chosen + tail)
        if fixed is not None:
            fixed.append((word, chosen))
        return True
    run_on = _run_on_reading(word, known)
    if not run_on:
        return False
    out.append(" ".join(run_on) + tail)
    if fixed is not None:
        fixed.append((word, " ".join(run_on)))
    return True


def _at_asking_place(before: list[str]) -> bool:
    """The opening words of a question, or the word after "how" or a
    question word: where an asking word goes."""
    last = before[-1].lower().strip("?!.,:;") if before else ""
    #: Not the word after an article: "a ghose cursor" is not "a whose cursor".
    if len(before) <= 1:
        return last not in ("a", "an", "the")
    return last in ("how", "what", "when", "where", "who", "why", "which")


# --- 2b. repair guided by a router ------------------------------------------------
#
# O3 (BACKLOG "Type tolerance everywhere": "every registered command phrase
# with one keyboard-neighbour slip, one swap, one dropped and one doubled
# letter must route as the clean phrase does"). Measured 2026-10-17: 283 of
# 339 such slips routed as the clean phrase. The speller reads a slip as the
# nearest everyday word ("tmie" as "the", "remive" as "remind", "fid" as
# "did") or leaves a real word alone ("form", "concert"), because it cannot
# know which word a router needs. Here the router decides: a word one slip
# from a word the router reads is read as that word only when the router
# then takes the sentence and did not take it as typed.

#: Words a command reads besides the act registry's own: what a note is
#: called and joined by. A real word ("form", "nore") is read as one of these
#: only, never as a content word, so "a form about taxes" is never a command.
_COMMAND_GLUE = frozenset("note notes from about into to with the my called named".split())


def router_words() -> frozenset[str]:
    """Every word the act registry says a command with: verbs, labels,
    examples and the palette's stems, and the glue between them."""
    if _ROUTER_WORDS:
        return _ROUTER_WORDS[0]
    words = set(_COMMAND_GLUE)
    for act in act_registry.ACTS.values():
        for text in (act.verb, act.intent, act.label, act.example, act.stem):
            words.update(w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 2)
    _ROUTER_WORDS.append(frozenset(words))
    return _ROUTER_WORDS[0]


_ROUTER_WORDS: list[frozenset[str]] = []


def guided(text: str, accepts, vocabulary=None, *, real_to=_COMMAND_GLUE, known=frozenset()) -> str | None:  # noqa: ANN001
    """`text` with one word read as the `vocabulary` word it is one slip from
    (`router_words` by default), when `accepts` takes that reading; None when
    no such reading exists. A real word is read only as a word of `real_to`
    (None: any), and a word of the person's own (`known`) never."""
    vocabulary = router_words() if vocabulary is None else vocabulary
    tokens = text.split()
    for i, token in enumerate(tokens):
        core = token.rstrip("?!.,:;")
        low = core.lower()
        if len(low) < 3 or not low.isalpha() or low in vocabulary or low in known or (core[:1].isupper() and i):
            continue
        pool = vocabulary if real_to is None or not spelling.is_word(low) else vocabulary & real_to
        for word in _one_slip_from(low, pool):
            reading = " ".join([*tokens[:i], word + token[len(core):], *tokens[i + 1:]])
            if accepts(reading):
                return reading
    return None


def _one_slip_from(low: str, pool) -> list[str]:  # noqa: ANN001
    """The words of `pool` one slip from `low`, nearest first. One slip
    changes at most two letters of the set, so the weighted distance is
    measured only for words that pass that (13 ms a question without it,
    measured on five ordinary questions)."""
    letters = set(low)
    near = [v for v in pool if abs(len(v) - len(low)) <= 1 and len(letters ^ set(v)) <= 2]
    return [word for gap, word in sorted((distance(low, v), v) for v in near) if gap <= 1.0]


# --- 3. meaning as the fallback --------------------------------------------------

#: Example questions of each kind, read when no rule did. Several wordings
#: each, so the nearest example is about the asking, not the subject.
EXAMPLES: dict[str, tuple[str, ...]] = {
    "when": (
        "what date is it", "what day is it on", "what time is it", "the date of", "due date",
        "how soon", "by when", "what day", "date for the appointment", "when is it happening",
    ),
    "count": (
        "how many are there", "the number of", "how much does it cost", "total count",
        "how many times", "what is the amount", "the price of", "how long does it take",
    ),
    "where": (
        "where is it", "the address of", "the location of", "which place", "where did i put",
        "what room is it in", "where to stay",
    ),
    "who": ("who is it", "which person", "the name of the person", "who said", "who was it"),
    "explain": (
        "why is it", "the reason for", "reason the", "reason why", "how do i do it", "how does it work", "what caused",
        "steps to", "the way to", "how to make",
    ),
    "status": (
        "what is the latest", "how is it going", "any update", "the progress on", "where are we with",
        "status of", "news on",
    ),
    "list": ("list them", "what are all the", "which ones", "all the items", "show me the list"),
    "yesno": ("is it done", "did i do it", "have i finished", "is it true that", "was it paid"),
}

#: How close a question must come to an example, and by how much nearer to
#: one kind than the next, before it is given that kind.
TRIGRAM_FLOOR = 0.36
EMBED_FLOOR = 0.62
MARGIN = 0.06


def _trigrams(text: str) -> Counter:
    padded = f"  {re.sub(r'[^a-z ]', '', text.lower())}  "
    return Counter(padded[i : i + 3] for i in range(len(padded) - 2))


def _cosine(a: Counter, b: Counter) -> float:
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


_EXAMPLE_GRAMS = {kind: [_trigrams(e) for e in examples] for kind, examples in EXAMPLES.items()}
_EMBED_CACHE: dict[int, dict[str, list[list[float]]]] = {}


def _vector_cosine(a, b) -> float:  # noqa: ANN001
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def guess_kind(asking: str, embed=None) -> str | None:  # noqa: ANN001
    """The kind of question `asking` is nearest to, or None when none is
    clearly nearest. `asking` is the question less its subject words, so
    "the date of the dentist" is compared as "the date of the". With
    `embed` (the embedder's `embed_many`), by cosine of meaning; without,
    by character trigrams."""
    text = (asking or "").strip()
    if len(text) < 3:
        return None
    scores: dict[str, float] = {}
    floor = TRIGRAM_FLOOR
    if embed is not None:
        try:
            cache = _EMBED_CACHE.get(id(embed))
            if cache is None:
                cache = {kind: embed(list(examples)) for kind, examples in EXAMPLES.items()}
                _EMBED_CACHE[id(embed)] = cache
            vector = embed([text])[0]
            scores = {kind: max(_vector_cosine(vector, v) for v in vectors) for kind, vectors in cache.items()}
            floor = EMBED_FLOOR
        except Exception:  # noqa: BLE001 - meaning is a fallback; trigrams stand in
            scores = {}
            floor = TRIGRAM_FLOOR
    if not scores:
        grams = _trigrams(text)
        scores = {kind: max(_cosine(grams, g) for g in examples) for kind, examples in _EXAMPLE_GRAMS.items()}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if ranked[0][1] < floor or (len(ranked) > 1 and ranked[0][1] - ranked[1][1] < MARGIN):
        return None
    return ranked[0][0]


#: The Guide reads a question through this (`act_registry.repair`).
act_registry.repair = repair
