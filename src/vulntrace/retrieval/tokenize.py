"""Code-aware tokenisation for BM25 (CP4 deliverable 3) and the fake models.

Choices (documented because they change scores):

- Words are maximal runs of ASCII letters, digits and `_`; everything else separates them, so
  dots, slashes, brackets and operators split `pkg/sub.Type.Method` into its parts. Non-ASCII
  letters are separators too (Go identifiers in the corpus are essentially all ASCII).
- Each word is split at `_` and at case changes: `readFile` -> `read`, `file`;
  `HTTPServer` -> `http`, `server`; `parseHTTP2Frame` -> `parse`, `http`, `2`, `frame`.
  Digit runs are their own parts.
- Everything is lower-cased.
- A word made of more than one part is also kept whole (lower-cased, underscores kept), so
  an exact identifier match (`readfile`) scores above matching its parts separately.
- No stop-word list: English stop-word lists do not fit code (`if`, `for`, `go`, `string`
  are meaningful there) and inventing a code list would be an untested tuning knob. BM25's
  IDF already down-weights terms that occur in most chunks of a range.
- Single-character parts are kept (`s`, `b`, `x` are common Go receiver names; IDF handles
  them).
"""

import re

_WORD = re.compile(r"[A-Za-z0-9_]+")
_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")


def word_parts(word: str) -> list[str]:
    return [p.lower() for seg in word.split("_") for p in _PART.findall(seg)]


def code_tokens(text: str) -> list[str]:
    out: list[str] = []
    for word in _WORD.findall(text):
        parts = word_parts(word)
        out.extend(parts)
        if len(parts) > 1:
            out.append(word.lower())
    return out
