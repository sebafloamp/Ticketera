from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.email_sender import EmailSendError, send_email
from app.models import Period, User
from app.reminder_auth import require_reminder_token
from app.reminders import build_admin_reminder, build_user_reminder

router = APIRouter(prefix="/internal/reminders")


@router.post("/run", dependencies=[Depends(require_reminder_token)])
def run_reminders(db: Session = Depends(get_db)):
    today_weekday = datetime.now().weekday()  # 0=lunes .. 6=domingo
    due_users = db.query(User).filter(User.reminder_day == today_weekday).all()

    sent, skipped, failed = [], [], []

    def _send(user: User, content) -> None:
        if content is None:
            skipped.append(user.email)
            return
        subject, html = content
        try:
            send_email(user.email, subject, html)
            sent.append(user.email)
        except EmailSendError:
            failed.append(user.email)

    for user in due_users:
        # Todo usuario (admin incluido) recibe su propio resumen de pendientes.
        own_periods = db.query(Period).filter(Period.owner_id == user.id).order_by(Period.start_date.desc()).all()
        _send(user, build_user_reminder(user, own_periods))

        # El admin ademas recibe el consolidado del resto del equipo.
        if user.role == "admin":
            other_members = db.query(User).filter(User.id != user.id).all()
            members_periods = {
                member: db.query(Period).filter(Period.owner_id == member.id).order_by(Period.start_date.desc()).all()
                for member in other_members
            }
            _send(user, build_admin_reminder(members_periods))

    return {"sent": sent, "skipped": skipped, "failed": failed}
