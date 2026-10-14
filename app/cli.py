"""Safe administrative commands for initial setup and account recovery."""

import click
from sqlalchemy import select

from app.extensions import db
from app.models.user import User
from app.models.role import Role
from app.services.access_control import seed_default_roles
from app.services.phone import normalize_phone


def register_cli(app):
    @app.cli.command("seed-roles")
    def seed_roles_command():
        """Create or update baseline roles and permissions idempotently."""
        seed_default_roles()
        click.echo("تم إعداد الأدوار والصلاحيات الأساسية.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt="اسم المدير", help="Full display name.")
    @click.option("--phone", prompt="رقم الهاتف", help="Sign-in phone number.")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Initial password (never printed or stored in the repository).",
    )
    def create_admin_command(name, phone, password):
        """Create the first owner account after running database migrations."""
        normalized_phone = normalize_phone(phone)
        if not normalized_phone:
            raise click.ClickException("رقم الهاتف غير صالح.")

        existing = db.session.scalar(
            select(User).where(User.phone == normalized_phone)
        )
        if existing is not None:
            raise click.ClickException("يوجد حساب مسجل بهذا الرقم بالفعل.")

        owner = db.session.scalar(select(Role).where(Role.code == "owner"))
        if owner is None:
            seed_default_roles()
            owner = db.session.scalar(select(Role).where(Role.code == "owner"))

        user = User(full_name=name.strip(), phone=normalized_phone, is_active=True)
        try:
            user.set_password(password)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

        user.must_change_password = True
        user.roles.append(owner)
        db.session.add(user)
        db.session.commit()
        click.echo(f"تم إنشاء حساب المدير للرقم {normalized_phone}. غيّر كلمة المرور بعد أول دخول.")

    @app.cli.command("reset-password")
    @click.option("--phone", prompt="رقم هاتف الحساب")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Temporary password; it is not echoed.",
    )
    def reset_password_command(phone, password):
        """Administrator-assisted password recovery when no SMS provider is configured."""
        normalized_phone = normalize_phone(phone)
        user = db.session.scalar(select(User).where(User.phone == normalized_phone))
        if user is None:
            raise click.ClickException("لم يتم العثور على حساب بهذا الرقم.")

        try:
            user.set_password(password)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

        user.must_change_password = True
        db.session.commit()
        click.echo("تمت إعادة تعيين كلمة المرور. يجب تغييرها بعد تسجيل الدخول.")
