from app.utils.yield_parser import parse_yield


def test_parse_yield_extracts_first_integer():
    assert parse_yield("Makes 12 cookies") == 12


def test_parse_yield_handles_servings_text():
    assert parse_yield("4 servings") == 4


def test_parse_yield_picks_first_in_range():
    assert parse_yield("Serves 2-3") == 2


def test_parse_yield_returns_none_for_non_numeric():
    assert parse_yield("two dozen") is None


def test_parse_yield_returns_none_for_empty():
    assert parse_yield("") is None


def test_parse_yield_returns_none_for_none():
    assert parse_yield(None) is None


def test_parse_yield_ignores_zero():
    assert parse_yield("0 servings, but really makes 8") == 8
