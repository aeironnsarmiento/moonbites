import pytest

from app.services.json_utils import loads_untrusted_json
from app.services.tiktok.extractor import parse_tiktok_page


def test_loads_untrusted_json_parses_normal_documents():
    assert loads_untrusted_json('{"a": [1, 2]}') == {"a": [1, 2]}
    assert loads_untrusted_json(b"[1]") == [1]


def test_loads_untrusted_json_reports_deep_nesting_as_value_error():
    with pytest.raises(ValueError):
        loads_untrusted_json("[" * 100_000)


def test_tiktok_page_with_deeply_nested_hydration_json_is_not_a_crash():
    html = (
        '<html><body><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" '
        'type="application/json">' + "[" * 100_000 + "</script></body></html>"
    )

    assert parse_tiktok_page(html) is None
