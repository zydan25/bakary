"""Business services for distributor and customer accounts."""

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.party import Party, PartyPrice
from app.models.product import Product
from app.services.catalog import CatalogRuleError, _price
from app.services.phone import normalize_phone


class PartyRuleError(ValueError):
    """Validation error for customer/distributor records."""


def save_party(*, party_type, name, phone=None, notes=None, prices=None, party_id=None, actor_id=None):
    if party_type not in {"distributor", "customer"}:
        raise PartyRuleError("نوع الحساب غير صالح.")
    name = (name or "").strip()
    phone = normalize_phone(phone) or None
    notes = (notes or "").strip() or None
    if not name:
        raise PartyRuleError("اسم الحساب مطلوب.")
    if len(name) > 160:
        raise PartyRuleError("الاسم طويل جدًا.")

    record = None
    if party_id:
        record = db.session.scalar(
            select(Party).where(Party.id == party_id, Party.party_type == party_type).with_for_update()
        )
        if record is None:
            raise PartyRuleError("لم يتم العثور على الحساب المطلوب.")

    inputs = prices or {}
    products = db.session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.id.asc())
    ).all()
    try:
        if record is None:
            record = Party(
                party_type=party_type, name=name, phone=phone, notes=notes,
                is_active=True, created_by_id=actor_id,
            )
            db.session.add(record)
            db.session.flush()
        else:
            record.name = name
            record.phone = phone
            record.notes = notes

        existing = {item.product_id: item for item in record.prices}
        for product in products:
            submitted = inputs.get(str(product.id))
            if submitted is None or str(submitted).strip() == "":
                if product.id in existing:
                    value = _price(existing[product.id].unit_price, "سعر الصنف")
                else:
                    value = _price(product.default_price_for(party_type), "سعر الصنف")
            else:
                value = _price(submitted, f"سعر {product.name}")

            default_value = _price(product.default_price_for(party_type), "السعر العام")
            price_row = existing.get(product.id)
            if price_row is None:
                db.session.add(PartyPrice(
                    party_id=record.id, product_id=product.id, unit_price=value,
                    is_custom=(value != default_value),
                ))
            else:
                price_row.unit_price = value
                price_row.is_custom = (value != default_value)

        db.session.commit()
        return record
    except (CatalogRuleError, PartyRuleError):
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise PartyRuleError("تعذر حفظ الحساب؛ تحقق من البيانات وحاول مجددًا.") from exc
    except Exception:
        db.session.rollback()
        raise


def set_party_active(record_id, party_type, is_active):
    record = db.session.scalar(
        select(Party).where(Party.id == record_id, Party.party_type == party_type).with_for_update()
    )
    if record is None:
        raise PartyRuleError("لم يتم العثور على الحساب.")
    record.is_active = bool(is_active)
    db.session.commit()
    return record


def list_parties(party_type, *, query=None, status="active"):
    stmt = select(Party).where(Party.party_type == party_type)
    if status == "active":
        stmt = stmt.where(Party.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(Party.is_active.is_(False))
    if query and query.strip():
        needle = "%" + query.strip() + "%"
        stmt = stmt.where(or_(Party.name.ilike(needle), Party.phone.ilike(needle)))
    return db.session.scalars(
        stmt.order_by(Party.is_active.desc(), Party.name.asc())
    ).all()
