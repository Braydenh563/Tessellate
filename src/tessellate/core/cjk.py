"""Scripts written without spaces between words (notes audit 1031, N2 and N15).

The index's tokenizer reads a whole run of Japanese or Chinese as one token, so
a word inside it was never found, and a split on whitespace counts a Japanese
note as "1 word". Two helpers, one rule each: `has` says a term needs a
substring match, and `word_count` counts an ideograph or kana as a word of its
own while every other script is still counted by its spaces.
"""

from __future__ import annotations

import re

#: Han, kana, and the scripts that put no space between words (Thai, Lao,
#: Khmer, Myanmar); Hangul too, for search only: it has spaces, but its
#: particles are glued on ("골프를"), so a word is still a substring of a token.
_UNSEGMENTED = re.compile(
    "[က-႟ក-៿฀-໿⺀-⿟぀-ヿ㄰-㆏ㇰ-ㇿ"
    "㐀-䶿一-鿿가-힯豈-﫿ｦ-ﾟ]"
)
#: What counts one by one in a word count: Han and kana (Hangul and the
#: south-east Asian scripts are not counted by character).
_PER_CHARACTER = re.compile("[⺀-⿟぀-ヿㇰ-ㇿ㐀-䶿一-鿿豈-﫿ｦ-ﾟ]")
#: Ignored: the long-vowel mark, the middle dot, CJK punctuation, and full-width punctuation
#: (the colon, comma, brackets and so on; full-width letters and digits stay words).
_IGNORED = re.compile(r"[ー・\u3000-\u303f\uff01-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65]")


def has(text: str) -> bool:
    """True when the text holds a script a word of it cannot be tokenised from."""
    return bool(_UNSEGMENTED.search(text or ""))


def word_count(text: str) -> int:
    """Words in the text: each Han or kana character is one, the rest by spaces."""
    text = text or ""
    if not has(text):
        return len(text.split())
    text = _IGNORED.sub(" ", text)
    return len(_PER_CHARACTER.findall(text)) + len(_PER_CHARACTER.sub(" ", text).split())
