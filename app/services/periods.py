"""Operating period helpers. A period becomes immutable after closing."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.production import BusinessPeriod
from app.models.setting import Setting


class PeriodRuleError(ValueError):
    pass


def period_mode():
    setting = db.session.scalar(select(Setting).where(Setting.key == "period_mode"))
    value = setting.value if setting is not None else "daily"
    return value if value in {"daily", "split"} else "daily"


def suggested_period_code():
    if period_mode() == "daily":
        return "daily"
    now = datetime.now(ZoneInfo("Asia/Aden"))
    return "morning" if now.hour < 12 else "evening"


def get_or_create_open_period(*, business_date=None, period_code=None, actor_id=None):
    business_date = business_date or date.today()
    mode = period_mode()
    selected = period_code or suggested_period_code()
    if mode == "daily":
        selected = "daily"
    elif selected not in {"morning", "evening"}:
        raise PeriodRuleError("اختر فترة الصباح أو المساء.")

    period = db.session.scalar(
        select(BusinessPeriod).where(
            BusinessPeriod.business_date == business_date,
            BusinessPeriod.period_code == selected,
        )
    )
    if period is not None:
        if period.status != "open":
            raise PeriodRuleError("هذه الفترة مختتمة ولا تقبل عمليات جديدة.")
        return period, False

    period = BusinessPeriod(
        business_date=business_date,
        period_code=selected,
        status="open",
        opened_by_id=actor_id,
    )
    db.session.add(period)
    try:
        db.session.commit()
        return period, True
    except IntegrityError:
        db.session.rollback()
        winner = db.session.scalar(
            select(BusinessPeriod).where(
                BusinessPeriod.business_date == business_date,
                BusinessPeriod.period_code == selected,
            )
        )
        if winner is None or winner.status != "open":
            raise PeriodRuleError("تعذر فتح الفترة؛ تحقق من حالة الفترة الحالية.")
        return winner, False


def period_label(code):
    return {
        "daily": "اليوم كاملًا",
        "morning": "الفترة الصباحية",
        "evening": "الفترة المسائية",
    }.get(code, code)
