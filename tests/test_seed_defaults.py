from sqlalchemy import func, select

from app import create_app
from app.extensions import db
from app.models.finance import CashAccount
from app.models.product import Product
from app.models.setting import Setting
from app.services.seed_defaults import seed_default_data


def test_default_bakery_data_is_created_and_idempotent():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        try:
            seed_default_data()
            seed_default_data()

            roti = db.session.scalar(select(Product).where(Product.code == "ROTI"))
            assert roti is not None
            assert roti.name == "روتي"
            assert roti.is_default is True

            assert db.session.scalar(select(func.count()).select_from(Product)) == 1
            assert db.session.scalar(select(func.count()).select_from(CashAccount)) == 1

            main_account = db.session.scalar(
                select(CashAccount).where(CashAccount.is_main.is_(True))
            )
            assert main_account is not None
            assert main_account.code == "MAIN"
            assert main_account.name == "الصندوق الرئيسي"

            default_product_setting = db.session.scalar(
                select(Setting).where(Setting.key == "default_product_id")
            )
            assert default_product_setting is not None
            assert default_product_setting.value == roti.id
        finally:
            db.session.remove()
            db.drop_all()
