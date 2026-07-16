"""Edge-case coverage for ``parse_date``.

A string can match a date pattern yet not be a real date. Those must resolve to
``None`` (the field is simply absent), never to a wrong date or a crash — the
same "missing beats invented" rule the parser follows everywhere.
"""

from datetime import date

from vpat_reviewer.parsing.dates import parse_date


def test_month_year_defaults_to_the_first():
    assert parse_date("August 2020") == date(2020, 8, 1)


def test_impossible_numeric_date_is_ignored():
    # Matches the m/d/y shape but 13/45 is no month or day -> None, not a crash.
    assert parse_date("13/45/2020") is None


def test_impossible_month_year_is_ignored():
    # A real month name but an impossible year -> the month-year fallback bails.
    assert parse_date("August 0000") is None


def test_unparseable_text_is_none():
    assert parse_date("sometime last quarter") is None
