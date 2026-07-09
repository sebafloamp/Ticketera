from app.models import Period, User


def user_can_access_period(period: Period, user: User) -> bool:
    """Dueno siempre; en periodos conjuntos tambien cualquier participante."""
    if period.owner_id == user.id:
        return True
    if period.is_joint:
        return any(participant.id == user.id for participant in period.participants)
    return False
