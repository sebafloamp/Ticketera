from datetime import date


def calculate_age(birth_date: date, today: date) -> int:
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def is_birthday_today(birth_date: date, today: date) -> bool:
    return (birth_date.month, birth_date.day) == (today.month, today.day)
