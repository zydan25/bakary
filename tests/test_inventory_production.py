from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app import create_app
from app.extensions import db
from app.models.inventory import InventoryItem, InventoryMovement
from app.models.production import BusinessPeriod, DoughBatch, PeriodIngredientUsage
from app.models.product import Product
from app.models.role import Role
from app.models.user import User
from app.services.inventory import create_inventory_item, inventory_balance, register_stock_movement
from app.services.production import create_dough_batch, record_period_flour_usage


def setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        role = Role(name="المالك للمخزون والإنتاج", code="owner", is_system=True)
        user = User(full_name="مدير المخزون", phone="+967771234567", is_active=True)
        user.set_password("Strong-pass-123")
        user.roles.append(role)
        product = Product(
            name="روتي", code="ROTI", unit_label="حبة", is_default=True,
            is_active=True, default_distributor_price=Decimal("8.00"),
            default_customer_price=Decimal("10.00"), shop_price=Decimal("15.00")
        )
        db.session.add_all([role, user, product])
        db.session.commit()
        item = create_inventory_item(
            name="دقيق شتاء", code="FLOUR-W", unit_label="كجم",
            reorder_level=Decimal("10.000"), actor_id=user.id
        )
        register_stock_movement(
            item_id=item.id, quantity="100", direction="in",
            movement_type="opening_balance", business_date=date.today(),
            actor_id=user.id, statement="رصيد بداية الاختبار",
            source_type="inventory_manual_request", source_id=800100
        )
        return app, user.id, product.id, item.id


def cleanup(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_opening_stock_dough_batch_records_production_without_immediate_consumption():
    app, user_id, product_id, item_id = setup()
    try:
        with app.app_context():
            batch, created = create_dough_batch(
                product_id=product_id,
                produced_quantity="250",
                business_date=date.today(),
                period_code="daily",
                statement="عجنة اختبار",
                actor_id=user_id,
                idempotency_key="test-dough-request-001",
            )
            assert created is True
            repeated, created_again = create_dough_batch(
                product_id=product_id,
                produced_quantity="250",
                business_date=date.today(),
                period_code="daily",
                statement="عجنة اختبار",
                actor_id=user_id,
                idempotency_key="test-dough-request-001",
            )
            assert repeated.id == batch.id
            assert created_again is False
            assert inventory_balance(item_id) == Decimal("100.000")
            assert db.session.scalar(select(func.count()).select_from(DoughBatch)) == 1
            movement = db.session.scalar(
                select(InventoryMovement).where(
                    InventoryMovement.source_type == "dough_batch",
                    InventoryMovement.source_id == batch.id,
                )
            )
            assert movement is None
    finally:
        cleanup(app)


def test_legacy_period_total_flour_is_idempotent_and_batch_entry_does_not_consume():
    app, user_id, product_id, item_id = setup()
    other_day = date.today() - timedelta(days=1)
    try:
        with app.app_context():
            usage, created = record_period_flour_usage(
                item_id=item_id, quantity="12.000", business_date=other_day,
                period_code="daily", statement="إجمالي الفترة",
                actor_id=user_id
            )
            assert created is True
            repeated, repeated_created = record_period_flour_usage(
                item_id=item_id, quantity="12.000", business_date=other_day,
                period_code="daily", statement="تكرار الطلب",
                actor_id=user_id
            )
            assert repeated.id == usage.id
            assert repeated_created is False
            assert inventory_balance(item_id) == Decimal("88.000")
            assert db.session.scalar(select(func.count()).select_from(PeriodIngredientUsage)) == 1

            # Batch entry does not consume material. Material use is calculated from
            # the physical count at period close, not entered per batch.
            batch, created = create_dough_batch(
                product_id=product_id, produced_quantity="80",
                business_date=other_day, period_code="daily",
                statement="عجنة دون استهلاك فوري",
                actor_id=user_id, idempotency_key="batch-no-flour-001"
            )
            assert created is True
            assert batch.flour_quantity is None
            assert inventory_balance(item_id) == Decimal("88.000")
    finally:
        cleanup(app)


def test_inventory_and_production_pages_render_for_authorized_user():
    app, _user_id, _product_id, _item_id = setup()
    try:
        client = app.test_client()
        login = client.post(
            "/auth/login",
            data={"phone": "+967771234567", "password": "Strong-pass-123"},
            follow_redirects=True,
        )
        assert login.status_code == 200
        assert client.get("/inventory/").status_code == 200
        assert client.get("/production/").status_code == 200
        assert client.get("/inventory/?action=new").status_code == 200
        assert client.get("/production/?action=batch").status_code == 200
    finally:
        cleanup(app)
