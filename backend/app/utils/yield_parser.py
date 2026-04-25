import re
from typing import Optional


_INTEGER_RE = re.compile(r"\d+")


def parse_yield(yield_text: Optional[str]) -> Optional[int]:
    """Return the first positive integer found in yield_text, or None."""
    if not yield_text:
        return None

    for match in _INTEGER_RE.finditer(yield_text):
        value = int(match.group(0))
        if value > 0:
            return value

    return None
