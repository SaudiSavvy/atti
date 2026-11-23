"""The single, documented text normalization applied to both languages.

Only *layout* whitespace is normalized: every run of whitespace (spaces, PDF
line wraps, HTML ``<br>`` breaks, NBSP) becomes one ASCII space, and the
ends are stripped. No Unicode normalization, no character substitution,
no punctuation or diacritic changes.
"""

import re

_WS = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    return _WS.sub(" ", text).strip()
