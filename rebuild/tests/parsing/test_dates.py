from datetime import date

from vpat_reviewer.parsing.dates import parse_date


def test_month_name_day_year():
    assert parse_date("March 5, 2023") == date(2023, 3, 5)
    assert parse_date("March 5 2023") == date(2023, 3, 5)


def test_day_month_name_year():
    assert parse_date("5 March 2023") == date(2023, 3, 5)


def test_iso_and_slash():
    assert parse_date("2023-03-05") == date(2023, 3, 5)
    assert parse_date("03/05/2023") == date(2023, 3, 5)
    assert parse_date("3-5-23") == date(2023, 3, 5)


def test_ordinal_suffix_stripped():
    assert parse_date("March 5th, 2023") == date(2023, 3, 5)


def test_month_year_only_becomes_first(  # v9 FIX D
):
    assert parse_date("August 2020") == date(2020, 8, 1)


def test_unparseable_returns_none():
    assert parse_date("") is None
    assert parse_date("sometime last year") is None
