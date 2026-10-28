"""Realistic Guide questions that the keyword rules answer with the wrong
topic (audit 1028 E31), named by what they ask.

The Guide scores a question against each topic's keywords. That is right for
a question that uses the feature's own word, and wrong for the ones people
actually type: "how do I export to PDF" shares "pdf" with the scanned-PDF
reader, "how do I stop the AI" shares "AI" with Models, "how do I edit my
question" has no keyword at all. Each row below is one intent, written as a
pattern over the words that make it that intent (the verb and the thing, in
either order, with the phrasings people use) and the topics that answer it,
best first. The rows are read before the keyword rules, and only a row whose
topics exist is ever used (`tests/test_guide_aliases.py` checks every id).

`did_you_mean` is the other half: a question no keyword and no row reached
is offered the three nearest topic names by the words they share, so a miss
is a short menu instead of a dead end.
"""

from __future__ import annotations

import re

#: Words that open a how-to, so a row can say "how do I <verb> <thing>"
#: without repeating the frame. Optional in every row that uses it.
_ASK = r"(?:how (?:do|can|would|should|could) (?:i|you|we)|how to|can i|can you|where (?:do|can) i|is there a way to|i want to|i need to|i'?d like to)"

#: (intent, pattern, topics). A pattern is matched against the lowered
#: question; `.{0,40}` joins a verb to its thing without caring about the
#: words between ("export my notes to a pdf").
_ROWS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("pdf-out", r"\b(?:export|save|download|print|turn|convert|make|get|send)\b.{0,40}\bpdf\b(?!.{0,20}\b(?:scan|scanned|ocr|read|text)\b)|\bpdf\b.{0,12}\b(?:export|output)\b", ("documents", "import-export", "board-library")),
    ("print", r"\bprint(?:ing|out)?\b|\bhard copy\b", ("documents", "import-export")),
    ("edit-question", r"\b(?:edit|change|fix|correct|redo|reword|rephrase|amend)\b.{0,25}\b(?:my |a |the |that |last )?(?:question|message|prompt|query|reply|text i sent)\b|\bsent (?:it|that|a message) (?:wrong|by mistake)\b|\btypo in (?:my|a) (?:question|message)\b", ("chat-controls", "ask-chat")),
    ("regenerate", r"\b(?:regenerate|redo|retry|try again|ask again|another answer|different answer|answer again)\b.{0,25}\b(?:answer|reply|response|that|it)\b|\bregenerate\b", ("chat-controls", "ask-chat")),
    ("attach-chat", r"\b(?:attach|add|upload|send|include|drop|put|give)\b.{0,30}\b(?:file|files|document|documents|image|picture|photo|pdf|note|notes|screenshot)\b.{0,30}\b(?:chat|message|question|ask|prompt|conversation|atlas|ai)\b|\b(?:chat|ask|message|conversation)\b.{0,30}\b(?:attach|upload|paperclip)\b|\bpaperclip\b", ("chat-controls", "ask-chat")),
    ("stop-ai", r"\b(?:stop|cancel|interrupt|abort|halt|end|kill|shut up|quit)\b.{0,20}\b(?:the |my )?(?:ai|answer|reply|response|model|atlas|chat|generating|generation|writing|typing|it)\b|\bstop generat|\bmake it stop\b|\btoo (?:long|much text)\b.{0,15}\bstop\b", ("chat-controls", "activity")),
    ("delete-all", r"\b(?:delete|erase|wipe|remove|clear|purge|destroy|reset|get rid of)\b.{0,15}\b(?:all|every|everything|whole|entire)\b.{0,25}\b(?:data|notes|notebook|my stuff|content|info|information|files|history)\b|\bstart (?:over|from scratch|fresh)\b|\bwipe (?:it|everything|the app)\b|\bfactory reset\b|\b(?:delete|erase|wipe|remove|clear|purge|destroy|get rid of)\b.{0,8}\b(?:everything|it all|all of it)\b", ("delete-data", "storage")),
    ("delete-account", r"\b(?:delete|close|remove|cancel)\b.{0,10}\b(?:my )?(?:account|profile|login)\b|\buninstall\b", ("delete-data", "lock")),
    ("model-for-laptop", r"\b(?:which|what|best|right|good|recommend\w*|suggest\w*|pick|choose|choosing|should i (?:use|get|pick|download|choose|install))\b.{0,40}\bmodels?\b.{0,40}\b(?:laptop|computer|pc|machine|mac|macbook|hardware|ram|memory|gpu|graphics|spec|specs|device|old|cheap|weak|small|low)\b|\b(?:laptop|computer|pc|machine|mac|macbook|hardware|gpu|device)\b.{0,40}\bmodels?\b|\bmodel\b.{0,20}\b(?:fit|fits|run on|work on|suit)\b|\bwhat can (?:my|this) (?:laptop|computer|pc|machine|mac)\b.{0,20}\brun\b|\bwill (?:it|a model|the model) run on\b", ("model-downloads", "model-bench", "models")),
    ("ram-need", r"\b(?:how much|how many|what|enough|minimum|required|requirements?|need|needs|use|uses|using|eat|eats)\b.{0,30}\b(?:ram|memory|gigabytes|gb|vram|cpu)\b|\b(?:ram|vram|memory)\b.{0,20}\b(?:need|needed|required|enough|use|usage|requirement)\b|\bsystem requirements?\b|\bminimum specs?\b|\bspecs? (?:do i|i) need\b", ("performance", "model-downloads")),
    ("ai-slow", r"\b(?:why|how come)\b.{0,15}\b(?:is|are|does|do)\b.{0,15}\b(?:the |my )?(?:ai|model|atlas|chat|answers?|replies|responses?|it|app|everything)\b.{0,15}\b(?:slow|so slow|lag|laggy|laggin\w*|taking (?:so )?long|take (?:so )?long|takes (?:so )?long|ages|forever|freez\w*|stuck|hang\w*|sluggish)\b|\b(?:ai|model|chat|answers?|replies|responses?)\b.{0,20}\b(?:slow|takes? (?:so |too )?long|taking (?:so |too )?long|takes forever|ages|sluggish|laggy)\b|\bspeed up\b.{0,15}\b(?:ai|model|answers?|chat|replies|responses?)\b|\bfaster (?:answers?|replies|responses?|ai|model)\b|\bmake (?:the )?(?:ai|model|answers?|chat)\b.{0,10}\bfaster\b", ("performance", "model-downloads", "models")),
    ("app-slow", r"\b(?:app|page|screen|tab|everything|ui|interface|scrolling|typing|animations?)\b.{0,15}\b(?:slow|laggy|lags|janky|stutter\w*|freez\w*|sluggish|heavy)\b|\b(?:slow|laggy|janky|stutter\w*)\b.{0,15}\b(?:app|page|screen|ui|interface|scrolling|typing)\b", ("performance", "appearance")),
    ("use-chatgpt", r"\b(?:chat ?gpt|openai|gpt-?\d?|claude|gemini|anthropic|api key|cloud model|online model|open ?router|groq|deepseek)\b", ("models", "privacy")),
    ("no-answer", r"\b(?:ai|model|atlas|chat)\b.{0,20}\b(?:not (?:answering|replying|responding|working)|doesn'?t (?:answer|reply|respond|work)|won'?t (?:answer|reply|respond|work)|no answer|never answers?|nothing happens|gives no answer|is dead|is down|offline)\b|\bno (?:answer|reply|response) from\b|\b(?:chat|ask)\b.{0,15}\b(?:empty|blank|nothing)\b", ("troubleshooting", "models")),
    ("connect-model", r"\b(?:connect|set up|setup|install|add|get|start|use|link|hook up|enable|turn on|switch on)\b.{0,25}\b(?:an? |the |my )?(?:ai|model|llm|ollama|local model|language model|assistant)\b|\bhow (?:do|can) i (?:get|have) (?:an? )?ai\b", ("models", "model-downloads")),
    ("switch-model", r"\b(?:switch|change|swap|pick|choose|select|use another|use a different)\b.{0,20}\b(?:the |my |a )?(?:ai|model|llm)\b", ("models", "chat-controls")),
    ("copy-answer", r"\b(?:copy|save|keep|store|turn)\b.{0,25}\b(?:an |the |this |that )?(?:answer|reply|response|chat|conversation)\b.{0,25}\b(?:note|clipboard|text|markdown|file)?\b", ("chat-controls", "ask-chat")),
    ("export-chat", r"\b(?:export|download|save|back ?up)\b.{0,20}\b(?:my |the |this )?(?:chat|chats|conversation|conversations|chat history)\b", ("chat-controls", "import-export")),
    ("clear-chat", r"\b(?:clear|delete|remove|erase|reset|wipe|start (?:a )?new|new)\b.{0,15}\b(?:the |my |this |a )?(?:chat|chats|conversation|conversations|chat history|thread)\b", ("chat-controls", "ask-chat")),
    ("fork-chat", r"\b(?:branch|fork|split|copy)\b.{0,15}\b(?:chat|conversation|thread)\b", ("chat-controls",)),
    ("backup", r"\b(?:back ?up|backup|backing up|save a copy|copy (?:everything|all)|keep a copy)\b", ("import-export", "storage")),
    ("restore", r"\b(?:restore|recover|get back|bring back|undelete|retrieve|undo)\b.{0,25}\b(?:backup|deleted|lost|note|notes|everything|data|file|files)\b|\b(?:deleted|lost|disappeared|vanished|missing)\b.{0,20}\b(?:note|notes|my stuff|file|files)\b", ("undo-bin", "import-export")),
    ("export-notes", r"\b(?:export|download|get)\b.{0,25}\b(?:all )?(?:my )?(?:notes|data|notebook|everything)\b|\bexport\b.{0,15}\b(?:to|as|into)\b.{0,10}\b(?:markdown|json|csv|word|docx|html|zip|obsidian)\b", ("import-export", "storage")),
    ("import-notes", r"\b(?:import|bring in|move|migrate|transfer|load)\b.{0,25}\b(?:notes|files|folder|documents|data|obsidian|notion|evernote|word|markdown|pdf|apple notes|onenote|google keep|keep)\b", ("import-export", "import-apps")),
    ("move-computers", r"\b(?:move|transfer|copy|sync|share|use)\b.{0,25}\b(?:another|new|second|other|my) (?:computer|laptop|pc|machine|mac|device|phone)\b|\b(?:new|another) (?:computer|laptop|pc)\b|\bsync\b.{0,15}\b(?:devices|computers|phone|laptop)\b", ("two-computers", "phone", "import-export")),
    ("phone-use", r"\b(?:on|from|with|using)\b.{0,6}\b(?:my )?(?:phone|iphone|android|tablet|ipad|mobile)\b|\b(?:phone|iphone|android|tablet|ipad|mobile)\b.{0,15}\b(?:app|use|access|open)\b", ("phone", "lan-networks", "install-app")),
    ("forgot-password", r"\b(?:forgot|forgotten|lost|reset|recover|change|can'?t remember|cannot remember|don'?t remember|locked out|can'?t (?:log|sign) in|can'?t get in)\b.{0,20}\b(?:my |the )?(?:password|passcode|pin|login|account)\b|\blocked out\b", ("lock", "security")),
    ("lock-app", r"\b(?:lock|protect|secure|password protect|put a password)\b.{0,20}\b(?:the |my )?(?:app|notebook|notes|screen|computer|everything|it)\b|\bauto-?lock\b", ("lock", "security", "encryption")),
    ("is-private", r"\b(?:is|are)\b.{0,15}\b(?:my )?(?:notes|data|stuff|information|chats?|it|this)\b.{0,15}\b(?:private|safe|secure|sent|uploaded|shared|tracked|stored online|in the cloud|read by|seen)\b|\b(?:does|do|will) (?:it|this|the app|atlas)\b.{0,20}\b(?:send|upload|share|track|collect|store|phone home|spy)\b|\bwho can (?:see|read)\b", ("privacy", "encryption")),
    ("works-offline", r"\b(?:work|works|working|use|run|runs)\b.{0,12}\b(?:offline|without (?:the )?(?:internet|wifi|wi-fi|network|connection)|no internet)\b|\boffline\b", ("privacy", "models")),
    ("where-data", r"\b(?:where|which folder|what folder)\b.{0,25}\b(?:are|is|do|does)\b.{0,15}\b(?:my |the )?(?:notes|data|files|notebook|database|everything)\b.{0,15}\b(?:stored|saved|kept|live|lives|go|located|put)\b|\bdata (?:folder|directory|location)\b", ("storage", "import-export")),
    ("tag-note", r"\b(?:add|put|give|set|apply|attach|remove|delete|change|edit|rename)\b.{0,15}\b(?:a |the |some )?(?:tags?|categor(?:y|ies)|labels?)\b", ("tags-categories", "tag-manager")),
    ("find-note", r"\b(?:find|search|look for|locate|look up|get to|open|go to)\b.{0,20}\b(?:a |an |my |the |old |older )?(?:note|notes|something|anything|file|document|thing i wrote|what i wrote)\b|\b(?:can'?t|cannot|couldn'?t) find\b.{0,15}\b(?:note|notes|something|it)\b", ("search", "find-anything", "find-a-place")),
    ("link-notes", r"\b(?:link|connect|relate|join|tie|associate|reference)\b.{0,20}\b(?:two |a |my |some |these |the )?(?:notes?|pages?|ideas?|things)\b|\bbacklinks?\b|\[\[", ("links", "graph")),
    ("new-note", r"\b(?:make|create|write|add|start|take|jot|new|capture|save)\b.{0,15}\b(?:a |an |my |the )?(?:new )?(?:note|notes|entry|thought|idea|memo)\b", ("capture", "quick-note")),
    ("pin-note", r"\b(?:pin|star|favou?rite|bookmark|keep at the top|put at the top)\b.{0,20}\b(?:a |the |my |this )?(?:note|notes|document|chat|page)\b|\bpin\b", ("favourites", "bookmarks")),
    ("archive-note", r"\b(?:archive|hide|shelve|put away|get (?:it |this )?out of the way)\b.{0,20}\b(?:a |the |my |this )?(?:note|notes|document|chat)\b", ("archive",)),
    ("reminder-set", r"\b(?:remind|reminder|reminders|alert me|notify me|nudge me|don'?t let me forget|due date|deadline)\b", ("reminders", "quick-add")),
    ("recurring", r"\b(?:repeat|repeating|recurring|every (?:day|week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|daily|weekly|monthly)\b.{0,20}\b(?:reminder|task|todo|to-do)\b|\b(?:reminder|task|todo|to-do)\b.{0,20}\b(?:repeat|repeating|recurring|every)\b", ("reminders", "reminders-controls")),
    ("todo-list", r"\b(?:to-?do|to do|task|tasks|checklist|check list|checkbox|checkboxes)\b", ("reminders", "editor-offers", "documents")),
    ("dark-mode", r"\b(?:dark|night|light|black|white)\b.{0,10}\b(?:mode|theme)\b|\b(?:too bright|hurts my eyes|easier on the eyes)\b", ("appearance", "themes")),
    ("text-size", r"\b(?:bigger|larger|smaller|increase|decrease|change|make)\b.{0,15}\b(?:the )?(?:text|font|writing|letters|words)\b|\b(?:text|font)\b.{0,10}\b(?:size|too small|too big|too large|bigger|smaller)\b|\bcan'?t read\b", ("themes", "accessibility", "appearance")),
    ("shortcuts", r"\b(?:keyboard|key|keys|hot ?key|short ?cut|shortcuts|ctrl|control|cmd|command)\b.{0,15}\b(?:for|to|combo|combination|list|everything)\b|\blist of (?:keys|shortcuts)\b|\bwhat keys\b", ("shortcuts", "hidden-features")),
    ("voice-dictate", r"\b(?:dictate|dictation|speak|talk|voice|say)\b.{0,15}\b(?:to|into|a note|my notes|instead of typing|instead)\b|\b(?:record|recording|audio|microphone|mic)\b.{0,15}\b(?:note|notes|a meeting|lecture|voice)\b|\bspeech to text\b|\btranscri\w+\b", ("voice", "live-captions", "meetings")),
    ("read-aloud", r"\b(?:read|reads|say|speak)\b.{0,15}\b(?:it |this |that |the answer |my notes |a note )?(?:aloud|out loud|to me)\b|\btext to speech\b|\btts\b", ("voice", "chat-controls")),
    ("ocr-scan", r"\b(?:scan|scanned|scanning|photograph|photo of|picture of|image of)\b.{0,25}\b(?:text|page|pages|notes|handwriting|handwritten|document|book|whiteboard|receipt)\b|\bhandwriting\b|\bextract text\b|\btext from (?:an? )?(?:image|picture|photo|pdf)\b|\bocr\b", ("ocr-workspace", "files-images", "ocr-engine")),
    ("images-in-notes", r"\b(?:paste|drag|drop|insert|add|put|embed|upload)\b.{0,15}\b(?:an? |the |my |some )?(?:image|images|picture|pictures|photo|photos|screenshot|screenshots|file|files|pdf)\b.{0,20}\b(?:note|notes|document|page|entry)\b", ("attachments", "files-images")),
    ("translate-text", r"\b(?:translate|translation|translating)\b|\bin (?:spanish|french|german|italian|japanese|chinese|korean|portuguese|russian|arabic|hindi)\b", ("translate", "translate-offline")),
    ("write-for-me", r"\b(?:write|draft|compose|generate|rewrite|improve|polish|proofread|summari[sz]e|shorten|expand)\b.{0,15}\b(?:for me|this|my|it|a note|an essay|an email|a letter|text)\b", ("write-with-atlas", "capture", "writing-checks")),
    ("summarise", r"\b(?:summari[sz]e|summary|sum up|tl;?dr|recap|digest|boil down|condense)\b", ("studyhelp", "answers-from-notes", "write-with-atlas")),
    ("study", r"\b(?:quiz|test|revise|revision|flash ?cards?|study|exam|learn|memori[sz]e|cram)\b", ("studyhelp", "mind-map-study")),
    ("ask-notes", r"\b(?:ask|question|talk|chat|speak|query)\b.{0,20}\b(?:my |the |about my |about |to my |with my )?(?:notes|notebook|knowledge|documents|files|stuff)\b|\bwhat did i (?:write|say|note|save)\b", ("ask-chat", "answers-from-notes", "notebook-questions")),
    ("wrong-answer", r"\b(?:ai|answer|answers|atlas|model|reply|it)\b.{0,15}\b(?:is|was|are|were|gave|gives|said|says|got)\b.{0,15}\b(?:wrong|incorrect|made up|invented|false|hallucinat\w*|not true|lying|nonsense|rubbish|garbage)\b|\bhallucinat\w*\b|\bmade (?:it |that )?up\b|\bwhy did (?:it|you) say\b", ("why-this-answer", "line-verdicts")),
    ("sources", r"\b(?:where|which note|what note|how|source|sources|cite|citation|citations|reference|references|evidence|proof)\b.{0,20}\b(?:did (?:it|you|the ai|atlas)|does (?:it|the ai|atlas)|is this|come from|get that|know that|from|came)\b.{0,15}\b(?:get|come|from|know|that|this|answer|note|source|answer)\b", ("why-this-answer", "chat-controls")),
    ("whiteboard-draw", r"\b(?:draw|sketch|diagram|flow ?chart|mind ?map|whiteboard|canvas|shapes?|arrows?|sticky)\b", ("whiteboard", "mind-maps", "quick-sketch")),
    ("graph-view", r"\b(?:graph|network|map of my notes|how (?:my )?notes (?:connect|link|relate)|connections between)\b", ("graph", "graph-controls")),
    ("settings-where", r"\b(?:where|how)\b.{0,15}\b(?:are|is|do i (?:open|find|get to)|can i (?:open|find|get to))\b.{0,12}\b(?:the |my )?(?:settings|preferences|options|config|configuration)\b", ("settings-overview",)),
    ("reset-settings", r"\b(?:reset|restore|undo|revert|default)\b.{0,15}\b(?:the |my |all )?(?:settings|preferences|options|defaults)\b|\bback to default\b|\bfactory settings\b", ("settings-reset",)),
    ("update-app", r"\b(?:update|upgrade|new version|latest version|newer version|check for updates?|get the latest)\b.{0,20}\b(?:app|tessellate|atlas|memorymap|version|it)?\b", ("updates",)),
    ("report-bug", r"\b(?:report|send|file|log|submit)\b.{0,15}\b(?:a |an |the )?(?:bug|problem|issue|crash|error|feedback|complaint)\b|\b(?:found|got|have|hit)\b.{0,10}\b(?:a |an )?(?:bug|crash)\b|\bsupport\b|\bcontact\b", ("logs", "troubleshooting")),
    ("app-broken", r"\b(?:app|page|it|everything|this|tessellate|notes?|buttons?|screen)\b.{0,15}\b(?:crash\w*|broke\w*|won'?t (?:load|open|start|work)|doesn'?t (?:load|open|start|work)|isn'?t (?:loading|working|opening)|is (?:blank|white|empty|frozen|stuck|broken)|keeps? (?:crashing|failing|closing))\b|\bblank (?:screen|page)\b|\bwhite screen\b|\bnothing (?:loads|opens|happens)\b", ("troubleshooting", "logs", "maintenance")),
    ("server-away", r"\b(?:failed to fetch|server (?:is )?(?:down|away|gone|not running)|can'?t (?:connect|reach)|connection (?:lost|refused|failed)|lost connection|unsaved|didn'?t save|not saving|won'?t save)\b", ("note-outbox", "troubleshooting")),
    ("duplicates", r"\b(?:duplicates?|duplicated|same note twice|twice|two copies|repeated notes?|merge (?:notes|two notes)|clean up (?:my )?notes|tidy)\b", ("tidy", "import-export")),
    ("what-is-this", r"\b(?:what (?:is|does)|who (?:is|are)|tell me about|explain)\b.{0,12}\b(?:this|the app|tessellate|atlas|memorymap)\b(?: app| program| thing)?\b", ("what-is-atlas", "tabs-overview", "guide")),
    ("get-started", r"\b(?:get started|getting started|where (?:do|should) i (?:start|begin)|first steps?|new here|how to begin|beginner|first time|just (?:installed|started)|walk me through)\b", ("first-steps", "tour", "tabs-overview")),
)

#: The rows that outrank the keyword rules: each was measured to be answered
#: with the wrong topic by keywords alone, and its pattern needs the verb and
#: the thing together. Every other row is soft: it names the topics only when
#: the keyword rules reached nothing, so it can add a phrasing but never move
#: an answer the question bank already gets right.
HARD = frozenset(
    {
        "pdf-out", "edit-question", "regenerate", "attach-chat", "stop-ai", "delete-all", "model-for-laptop",
        "ram-need", "ai-slow", "app-slow", "use-chatgpt", "no-answer", "export-chat", "clear-chat", "fork-chat",
        "delete-account", "connect-model", "switch-model",
    }
)

_COMPILED = tuple((name, re.compile(pattern, re.I), ids) for name, pattern, ids in _ROWS)


def intents(question: str) -> list[tuple[str, tuple[str, ...]]]:
    """Every row the question reads as, in table order: (intent, topic ids)."""
    lowered = " ".join((question or "").lower().replace("’", "'").split())
    return [(name, ids) for name, rx, ids in _COMPILED if rx.search(lowered)]


def topic_ids(question: str, *, hard: bool = True) -> list[str]:
    """The topic ids the question's intents name, the first row's first:
    the hard rows' (`HARD`) or, with `hard=False`, the soft rows'.

    Rows are ordered most specific first, so the first row that reads wins
    its topics; a second row's topics follow, so a question that reads two
    ways still reaches both, without repeating one.
    """
    seen: list[str] = []
    for name, ids in intents(question):
        if (name in HARD) != hard:
            continue
        for topic_id in ids:
            if topic_id not in seen:
                seen.append(topic_id)
    return seen


_WORD = re.compile(r"[a-z0-9]+")
_FILLER = frozenset(
    "a an the i me my we you your do does did how what why when where which who is are was can could would should will "
    "to of in on at for from with and or it this that there some any about into onto up out be been get got something anything thing things".split()
)


def did_you_mean(question: str, topics: list[dict], title_of, limit: int = 3) -> list[dict]:
    """The nearest topics by the words a question shares with their names and
    keywords, best first; empty when nothing is shared. Used only when
    nothing else answered, so it is a menu, never a verdict."""
    words = {w for w in _WORD.findall((question or "").lower()) if w not in _FILLER and len(w) > 2}
    if not words:
        return []
    scored = []
    for order, topic in enumerate(topics):
        named = set(_WORD.findall(f"{title_of(topic)} {' '.join(topic['keywords'])}".lower()))
        shared = words & named
        if shared:
            scored.append((-len(shared), -sum(len(w) for w in shared), order, topic))
    scored.sort(key=lambda row: row[:3])
    return [row[3] for row in scored[:limit]]
