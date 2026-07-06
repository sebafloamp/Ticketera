from datetime import date

from app.birthday import calculate_age, is_birthday_today


def test_calculate_age_before_birthday_this_year():
    birth_date = date(1990, 8, 20)
    today = date(2026, 8, 19)
    assert calculate_age(birth_date, today) == 35


def test_calculate_age_on_birthday():
    birth_date = date(1990, 8, 20)
    today = date(2026, 8, 20)
    assert calculate_age(birth_date, today) == 36


def test_calculate_age_after_birthday_this_year():
    birth_date = date(1990, 8, 20)
    today = date(2026, 8, 21)
    assert calculate_age(birth_date, today) == 36


def test_is_birthday_today_true_regardless_of_year():
    assert is_birthday_today(date(1990, 3, 15), date(2026, 3, 15)) is True


def test_is_birthday_today_false_different_day():
    assert is_birthday_today(date(1990, 3, 15), date(2026, 3, 16)) is False
