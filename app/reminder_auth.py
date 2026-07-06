import hmac
import os

from fastapi import Header, HTTPException


def require_reminder_token(authorization: str = Header(default="")) -> None:
    expected = os.environ.get("REMINDER_TASK_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="REMINDER_TASK_TOKEN no esta configurada.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Token invalido.")
