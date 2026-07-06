import os

import httpx

RESEND_API_URL = "https://api.resend.com/emails"


class EmailSendError(Exception):
    pass


def send_email(to_email: str, subject: str, html_body: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise EmailSendError("RESEND_API_KEY no esta configurada.")

    from_address = os.environ.get("REMINDER_FROM_EMAIL", "onboarding@resend.dev")
    response = httpx.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"from": from_address, "to": [to_email], "subject": subject, "html": html_body},
        timeout=10,
    )
    if response.status_code >= 400:
        raise EmailSendError(f"Resend respondio {response.status_code}: {response.text}")
