def test_hash_and_verify_password_roundtrip():
    from app.auth import hash_password, verify_password

    hashed = hash_password("mypassword123")
    assert hashed != "mypassword123"
    assert verify_password("mypassword123", hashed) is True
    assert verify_password("wrongpassword", hashed) is False
