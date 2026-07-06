import re

E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def is_valid_e164(phone: str) -> bool:
    return bool(E164_PATTERN.match(phone))
