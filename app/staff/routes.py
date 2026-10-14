"""Employee CRUD and role-permission assignment."""

import re

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select

from app.extensions import db
from app.models.employee import Employee
from app.models.role import Permission, Role
from app.models.user import User
from app.services.phone import normalize_phone
from app.staff import staff_bp
from app.staff.forms import EmployeeForm


def _require(permission):
    if not current_user.has_permission(permission):
        abort(403)


def _assignable_roles():
    return db.session.scalars(
        select(Role).where(Role.code != "owner").order_by(Role.name.asc())
    ).all()


@staff_bp.route("/employees/", methods=["GET", "POST"])
@login_required
def employees():
    _require("employees.manage")
    query = (request.args.get("q") or "").strip()
    status = request.args.get("status", "active")
    if status not in {"active", "inactive", "all"}:
        status = "active"
    action = request.args.get("action", "")
    edit_id = request.args.get("edit", type=int)
    form = EmployeeForm()
    roles = _assignable_roles()
    selected_role_codes = []

    if request.method == "GET" and action == "edit" and edit_id:
        employee = db.session.get(Employee, edit_id)
        if employee is None:
            abort(404)
        form.full_name.data = employee.full_name
        form.phone.data = employee.phone or ""
        form.job_title.data = employee.job_title or ""
        form.notes.data = employee.notes or ""
        form.is_active.data = employee.is_active
        selected_role_codes = [role.code for role in employee.user.roles if role.code != "owner"] if employee.user else []

    if request.method == "POST":
        if form.validate_on_submit():
            employee = db.session.get(Employee, edit_id) if edit_id else None
            if edit_id and employee is None:
                abort(404)
            phone = normalize_phone(form.phone.data)
            if not phone:
                form.phone.errors.append("رقم الهاتف غير صالح.")
            else:
                account_for_phone = db.session.scalar(
                    select(User).where(User.phone == phone)
                )
                if employee and employee.user and account_for_phone is not None and account_for_phone.id != employee.user.id:
                    form.phone.errors.append("رقم الهاتف مرتبط بحساب دخول آخر.")
                elif employee is None and account_for_phone is not None:
                    already_linked = db.session.scalar(
                        select(Employee).where(Employee.user_id == account_for_phone.id)
                    )
                    if already_linked is not None:
                        form.phone.errors.append("حساب الدخول مرتبط بملف موظف آخر.")
                    elif any(role.code == "owner" for role in account_for_phone.roles):
                        form.phone.errors.append("لا يمكن ربط حساب المدير الرئيسي بملف موظف؛ اختر رقمًا آخر.")
                role_codes = list(dict.fromkeys(request.form.getlist("role_codes")))
                role_map = {
                    role.code: role
                    for role in db.session.scalars(
                        select(Role).where(Role.code.in_(role_codes), Role.code != "owner")
                    ).all()
                } if role_codes else {}
                if not role_map:
                    form.notes.errors.append("اختر دورًا واحدًا على الأقل لحساب الموظف.")
                if account_for_phone is None and not (form.user_password.data or "").strip():
                    form.user_password.errors.append("أدخل كلمة مرور للحساب الجديد.")
                if not form.errors:
                    try:
                        user = employee.user if employee and employee.user else account_for_phone
                        if user is None:
                            user = User(
                                full_name=form.full_name.data.strip(),
                                phone=phone,
                                is_active=bool(form.is_active.data),
                            )
                            user.set_password(form.user_password.data)
                            db.session.add(user)
                            db.session.flush()
                        else:
                            user.full_name = form.full_name.data.strip()
                            user.phone = phone
                            user.is_active = bool(form.is_active.data)
                            if (form.user_password.data or "").strip():
                                user.set_password(form.user_password.data)
                        user.roles = list(role_map.values())

                        if employee is None:
                            employee = Employee(created_by_id=current_user.id)
                            db.session.add(employee)
                        employee.user = user
                        employee.full_name = form.full_name.data.strip()
                        employee.phone = phone
                        employee.job_title = (form.job_title.data or "").strip() or None
                        employee.notes = (form.notes.data or "").strip() or None
                        employee.is_active = bool(form.is_active.data)
                        db.session.commit()
                        flash("تم حفظ الموظف وحساب الدخول والصلاحيات بنجاح.", "success")
                        return redirect(url_for("staff.employees", status=status, q=query or None))
                    except ValueError as exc:
                        db.session.rollback()
                        form.user_password.errors.append(str(exc))
                    except Exception:
                        db.session.rollback()
                        flash("تعذر حفظ الموظف. لم يتم تأكيد التغييرات.", "error")
            action = "edit" if edit_id else "new"
            selected_role_codes = role_codes if "role_codes" in locals() else []

    stmt = select(Employee)
    if status == "active":
        stmt = stmt.where(Employee.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(Employee.is_active.is_(False))
    if query:
        needle = "%" + query + "%"
        stmt = stmt.where(
            or_(
                Employee.full_name.ilike(needle),
                Employee.phone.ilike(needle),
                Employee.job_title.ilike(needle),
            )
        )
    items = db.session.scalars(stmt.order_by(Employee.full_name.asc())).all()
    return render_template(
        "staff/employees.html",
        items=items,
        form=form,
        roles=roles,
        selected_role_codes=selected_role_codes,
        query=query,
        status=status,
        show_form=action in {"new", "edit"} or (request.method == "POST" and bool(form.errors)),
        editing_employee_id=edit_id,
    )


@staff_bp.route("/roles", methods=["GET", "POST"])
@login_required
def roles():
    _require("users.manage")
    role_form_error = None
    role_name = (request.form.get("role_name") or "").strip()
    role_code = (request.form.get("role_code") or "").strip().lower()
    if request.method == "POST" and request.form.get("action") == "create_role":
        if not role_name:
            role_form_error = "اسم الدور مطلوب."
        elif not re.fullmatch(r"[a-z][a-z0-9_]{1,79}", role_code):
            role_form_error = "رمز الدور يجب أن يبدأ بحرف لاتيني ويحتوي أحرفًا صغيرة وأرقامًا وشرطة سفلية فقط."
        elif db.session.scalar(select(Role.id).where((Role.code == role_code) | (Role.name == role_name))):
            role_form_error = "اسم الدور أو رمزه مستخدم بالفعل."
        if role_form_error is None:
            db.session.add(Role(name=role_name, code=role_code, description=(request.form.get("role_description") or "").strip(), is_system=False))
            db.session.commit()
            flash("تم إنشاء الدور. اضبط صلاحياته من قائمة الأدوار.", "success")
            return redirect(url_for("staff.roles"))

    role_list = _assignable_roles()
    selected_id = request.args.get("role_id", type=int)
    selected_role = next((role for role in role_list if role.id == selected_id), None)
    if selected_role is None and role_list:
        selected_role = role_list[0]

    if request.method == "POST" and request.form.get("action") == "save_permissions":
        selected_id = request.form.get("role_id", type=int)
        selected_role = next((role for role in role_list if role.id == selected_id), None)
        if selected_role is None:
            abort(404)
        permission_codes = set(request.form.getlist("permission_codes"))
        allowed = db.session.scalars(
            select(Permission).where(Permission.code.in_(permission_codes))
        ).all()
        if len({permission.code for permission in allowed}) != len(permission_codes):
            role_form_error = "توجد صلاحية غير معروفة؛ أعد تحميل الصفحة."
        else:
            selected_role.permissions = allowed
            db.session.commit()
            flash("تم تحديث صلاحيات الدور.", "success")
            return redirect(url_for("staff.roles", role_id=selected_role.id))

    permissions = db.session.scalars(select(Permission).order_by(Permission.code.asc())).all()
    selected_permission_codes = {permission.code for permission in selected_role.permissions} if selected_role else set()

    group_names = {
        "dashboard": "الرئيسية",
        "products": "الأصناف والتسعير",
        "parties": "الموزعون والعملاء",
        "distribution": "الصرف والتحصيل",
        "inventory": "المخزون والمواد الخام",
        "production": "الإنتاج والعجنات",
        "free_distribution": "التوزيع المجاني",
        "handover": "الإقفال والتسليم",
        "reports": "التقارير",
        "finance": "الصندوق والحسابات",
        "cash": "الصندوق والحسابات",
        "expenses": "المصروفات",
        "employees": "إدارة الموظفين",
        "users": "إدارة المستخدمين والأدوار",
        "settings": "إعدادات النظام",
        "auth": "الدخول والحسابات",
    }
    grouped_permissions = {}
    for permission in permissions:
        group_key = permission.code.split(".", 1)[0]
        grouped_permissions.setdefault(group_key, []).append(permission)

    group_order = [key for key in group_names if key in grouped_permissions]
    group_order.extend(sorted(key for key in grouped_permissions if key not in group_names))
    permission_groups = [
        {
            "key": key,
            "name": group_names.get(key, "صلاحيات أخرى"),
            "permissions": grouped_permissions[key],
        }
        for key in group_order
    ]

    return render_template(
        "staff/roles.html",
        roles=role_list,
        selected_role=selected_role,
        permissions=permissions,
        permission_groups=permission_groups,
        selected_permission_codes=selected_permission_codes,
        role_form_error=role_form_error,
    )
