from datetime import date
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.role import Role
from app.models.user import User
from app.services.inventory import (
    create_inventory_item,
    inventory_balance,
    inventory_valuation,
    register_stock_movement,
)


def setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        role = Role(name="مالك المخزون", code="owner", is_system=True)
        user = User(full_name="مدير المخزون", phone="+967771234567", is_active=True)
        user.set_password("Strong-pass-123")
        user.roles.append(role)
        db.session.add_all([role, user])
        db.session.commit()
        item = create_inventory_item(
            name="دقيق القيمة", code="FLOUR-V", unit_label="كجم",
            reorder_level=Decimal("1.000"), actor_id=user.id
        )
        return app, user.id, item.id


def cleanup(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def movement(item_id, actor_id, quantity, direction, kind, request_id, unit_cost=None):
    return register_stock_movement(
        item_id=item_id,
        quantity=quantity,
        direction=direction,
        movement_type=kind,
        business_date=date.today(),
        actor_id=actor_id,
        statement=kind,
        unit_cost=unit_cost,
        source_type="test_inventory_valuation",
        source_id=request_id,
    )


def test_moving_average_value_reduces_with_consumption():
    app, actor_id, item_id = setup()
    try:
        with app.app_context():
            movement(item_id, actor_id, "10", "in", "opening_balance", 101, "2.00")
            movement(item_id, actor_id, "10", "in", "addition", 102, "3.00")
            before = inventory_valuation(item_id)
            assert before["quantity"] == Decimal("20.000")
            assert before["average_unit_cost"] == Decimal("2.50")
            assert before["stock_value"] == Decimal("50.00")
            movement(item_id, actor_id, "5", "out", "production_consumption", 103)
            after = inventory_valuation(item_id)
            assert after["quantity"] == Decimal("15.000")
            assert after["average_unit_cost"] == Decimal("2.50")
            assert after["stock_value"] == Decimal("37.50")
    finally:
        cleanup(app)


def test_valuation_stays_unknown_when_remaining_stock_has_missing_cost():
    app, actor_id, item_id = setup()
    try:
        with app.app_context():
            movement(item_id, actor_id, "10", "in", "opening_balance", 201, None)
            movement(item_id, actor_id, "5", "in", "addition", 202, "4.00")
            unknown = inventory_valuation(item_id)
            assert unknown["quantity"] == Decimal("15.000")
            assert unknown["stock_value"] is None
            assert unknown["is_valued"] is False

            movement(item_id, actor_id, "15", "out", "stock_consumption", 203)
            movement(item_id, actor_id, "4", "in", "addition", 204, "5.00")
            known = inventory_valuation(item_id)
            assert known["quantity"] == Decimal("4.000")
            assert known["average_unit_cost"] == Decimal("5.00")
            assert known["stock_value"] == Decimal("20.00")
    finally:
        cleanup(app)
