import re
from typing import Any, Optional

from bs4 import BeautifulSoup


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        text = str(value)
    elif isinstance(value, str):
        text = value
    else:
        return None

    if "<" in text or "&" in text:
        stripped = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    else:
        stripped = text.strip()

    collapsed = re.sub(r"\s+", " ", stripped).strip()
    return collapsed or None


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)

    return result
