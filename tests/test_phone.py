from app.phone import is_valid_e164


def test_accepts_valid_e164():
    assert is_valid_e164("+56912345678") is True


def test_rejects_missing_plus():
    assert is_valid_e164("56912345678") is False


def test_rejects_spaces():
    assert is_valid_e164("+56 9 1234 5678") is False


def test_rejects_leading_zero_after_plus():
    assert is_valid_e164("+0912345678") is False


def test_rejects_too_short():
    assert is_valid_e164("+123") is False
