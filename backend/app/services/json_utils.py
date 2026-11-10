from __future__ import annotations

import json
from typing import Any


def loads_untrusted_json(data: str | bytes | bytearray) -> Any:
    """`json.loads` for third-party input, failing only with `ValueError`.

    Pathologically nested JSON (thousands of "[") exhausts the stack and makes
    `json.loads` raise `RecursionError`, which callers guarding against bad
    input with `except ValueError` would not catch. Re-raise it as a
    `ValueError` so one except clause covers every malformed document.
    """
    try:
        return json.loads(data)
    except RecursionError as error:
        raise ValueError("JSON is nested too deeply") from error
