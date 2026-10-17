"""The slash commands' words (name, usage, summary, example), in the order `/help` lists them.

A leaf module: `ai/slash.py` pairs each row with the function that runs it, and the
Guide topic (`help_topics_more`) reads the words from here, so neither needs the other
and the composer is not reached through the topic.
"""

from __future__ import annotations

TABLE: tuple[tuple[str, str, str, str], ...] = (
    ('recent', '/recent [n]', 'your newest notes, five unless you say how many.', '/recent 10'),
    ('count', '/count [tag, category or word]', 'how many notes, or how many carry a tag, sit in a category or mention a word.', '/count golf'),
    ('made', '/made [day or span]', 'the notes written on a day or over a span.', '/made last week'),
    ('untagged', '/untagged', 'the notes with no tags yet.', '/untagged'),
    ('today', '/today', 'the notes you wrote today.', '/today'),
    ('yesterday', '/yesterday', 'the notes you wrote yesterday.', '/yesterday'),
    ('find', '/find <words>', 'the notes that hold every word you give, newest first.', '/find dentist tuesday'),
    ('pinned', '/pinned', 'the notes you have pinned.', '/pinned'),
    ('oldest', '/oldest [n]', 'your oldest notes, five unless you say how many.', '/oldest 3'),
    ('random', '/random', 'one of your notes, picked at random.', '/random'),
    ('tags', '/tags', 'the tags you use, most used first, with how many notes each.', '/tags'),
    ('categories', '/categories', 'your categories and how many notes sit in each.', '/categories'),
    ('todo', '/todo', 'the open checkboxes in your notes.', '/todo'),
    ('due', '/due [week]', 'the reminders due today or overdue, or due this week.', '/due week'),
    ('calc', '/calc <sum>', 'a sum worked out exactly, with + - * / % ^ and brackets.', '/calc 15 * 80 / 100'),
    ('stats', '/stats', 'how many notes, words, tags and days of writing you have.', '/stats'),
    ('orphans', '/orphans', 'the notes that link to no other note.', '/orphans'),
    ('help', '/help [command]', 'these commands, or how to type one.', '/help made'),
)
