"""Operating period helpers. A period becomes immutable after closing."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.production import BusinessPeriod
from app.models.setting import Setting
from app.services.clock import business_today


class PeriodRuleError(ValueError):
    pass


def period_mode():
    setting = db.session.scalar(select(Setting).where(Setting.key == "period_mode"))
    if setting is None:
        setting = db.session.scalar(
            select(Setting).where(Setting.key == "operating_period_mode")
        )
    value = setting.value if setting is not None else "daily"
    if value in {"split", "morning_evening", "morning-evening"}:
        return "split"
    return "daily"


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


ARABIC_WEEKDAYS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")


def period_day_name(value):
    return ARABIC_WEEKDAYS[value.weekday()]


def selectable_open_periods(*, actor_id=None, limit=21):
    """Ensure today's period exists when possible and return open periods."""
    today = business_today()
    code = suggested_period_code()
    existing = db.session.scalar(select(BusinessPeriod).where(
        BusinessPeriod.business_date == today,
        BusinessPeriod.period_code == code,
    ))
    if existing is None:
        try:
            get_or_create_open_period(business_date=today, period_code=code, actor_id=actor_id)
        except PeriodRuleError:
            pass
    rows = db.session.scalars(
        select(BusinessPeriod).where(BusinessPeriod.status == "open")
        .order_by(BusinessPeriod.business_date.desc(), BusinessPeriod.opened_at.desc(), BusinessPeriod.id.desc())
        .limit(limit)
    ).all()
    rows.sort(key=lambda row: (
        row.business_date == today and row.period_code == code,
        row.business_date, row.opened_at, row.id,
    ), reverse=True)
    return rows


def period_option_label(period):
    today = business_today()
    current = period.business_date == today and period.period_code == suggested_period_code()
    prefix = "الفترة الحالية" if current else "فترة سابقة"
    return f"{prefix} — {period_day_name(period.business_date)} · {period_label(period.period_code)}"
