"""Bounded English number words for operational grammars, not an LLM parser."""
from __future__ import annotations
import re

_UNITS = dict(zip('zero one two three four five six seven eight nine'.split(), range(10)))
_SMALL = dict(zip('ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(10, 20)))
_TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
_WHOLE = rf"(?:{'|'.join(_TENS)})(?:[ -](?:{'|'.join(_UNITS)}))?|(?:{'|'.join(_SMALL)}|{'|'.join(_UNITS)})"
_PATTERN = re.compile(rf"\b(?P<sign>minus |negative )?(?P<whole>{_WHOLE})(?: point (?P<frac>(?:{'|'.join(_UNITS)})(?: (?:{'|'.join(_UNITS)}))?))?\b")


def normalize_spoken_numbers(text: str) -> str:
    """Recognize zero to ninety-nine, optionally two decimal digits and sign.

    Does not translate articles, discard minus signs, or parse arbitrary arithmetic.
    Larger/ambiguous forms are left to the strict outer grammar to refuse.
    """
    if not isinstance(text, str) or len(text) > 4096:
        return ''
    def replace(match: re.Match) -> str:
        words = match['whole'].replace('-', ' ').split()
        value = sum(_TENS.get(w, _SMALL.get(w, _UNITS.get(w, 0))) for w in words)
        result = ('-' if match['sign'] else '') + str(value)
        if match['frac']:
            result += '.' + ''.join(str(_UNITS[w]) for w in match['frac'].split())
        return result
    return _PATTERN.sub(replace, text)
