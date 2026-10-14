"""Idempotent seeding for baseline roles and granular permissions."""

from app.extensions import db
from app.models.role import Permission, Role


PERMISSIONS = [
    ("عرض الرئيسية", "dashboard.view", "عرض لوحة التحكم"),
    ("إدارة المستخدمين", "users.manage", "إدارة الحسابات والأدوار"),
    ("إدارة الإعدادات", "settings.manage", "تغيير إعدادات النظام"),
    ("عرض الأصناف", "products.view", "عرض الأصناف والأسعار الأساسية"),
    ("إدارة الأصناف", "products.manage", "إضافة الأصناف وتعديل أسعارها"),
    ("عرض الأطراف", "parties.view", "عرض الموزعين والعملاء"),
    ("إدارة الأطراف", "parties.manage", "إضافة وتعديل وتعطيل الموزعين والعملاء"),
    ("صرف البضاعة", "distribution.issue", "تسجيل صرف البضاعة"),
    ("التحصيل النقدي", "distribution.payment", "تسجيل مدفوعات الموزعين والعملاء"),
    ("تقارير التوزيع", "distribution.reports", "عرض تقارير الصرف وكشوف الحساب"),
    ("عرض المخزون", "inventory.view", "عرض الأرصدة وحركات المخزون"),
    ("إدارة المخزون", "inventory.manage", "إدخال المواد وتسوية المخزون"),
    ("عرض الإنتاج", "production.view", "عرض العجنات والإقفال وتقارير الإنتاج"),
    ("إدارة الإنتاج", "production.manage", "تسجيل العجنات والإنتاج والإقفال"),
    ("إدارة التوزيع المجاني", "free_distribution.manage", "إدارة المستفيدين وصرف الكميات المجانية"),
    ("تسجيل التسليمات", "handover.manage", "تسجيل تسليمات المستلم والفترة"),
    ("عرض المالية", "finance.view", "عرض الصندوق والحسابات"),
    ("إدارة المالية", "finance.manage", "تسجيل القبض والصرف والتحويل"),
    ("إدارة المصروفات", "expenses.manage", "تسجيل ومراجعة مصروفات المخبز"),
    ("إدارة الحسابات النقدية", "cash.accounts.manage", "إدارة الصناديق والحسابات النقدية"),
    ("إدارة الموظفين", "employees.manage", "إدارة ملفات الموظفين"),
    ("عرض التقارير", "reports.view", "عرض التقارير المسموح بها"),
    ("تصدير التقارير", "reports.export", "تصدير التقارير المسموح بها"),
]

ROLE_PERMISSIONS = {
    "owner": [code for _, code, _ in PERMISSIONS],
    "accountant": [
        "dashboard.view", "products.view", "parties.view", "distribution.payment",
        "distribution.reports", "finance.view", "finance.manage", "expenses.manage",
        "reports.view", "reports.export", "inventory.view", "production.view",
    ],
    "distribution": [
        "dashboard.view", "products.view", "parties.view", "parties.manage",
        "distribution.issue", "distribution.payment", "distribution.reports",
        "reports.view",
    ],
    "production": [
        "dashboard.view", "products.view", "inventory.view", "production.view",
        "production.manage", "free_distribution.manage", "handover.manage", "reports.view",
    ],
    "storekeeper": [
        "dashboard.view", "inventory.view", "inventory.manage", "reports.view",
    ],
    "receiver": [
        "dashboard.view", "handover.manage", "finance.view",
    ],
    "read_only": [
        "dashboard.view", "products.view", "parties.view", "distribution.reports",
        "inventory.view", "finance.view", "production.view", "reports.view",
    ],
}

ROLE_LABELS = {
    "owner": ("المالك/المدير", "جميع صلاحيات النظام"),
    "accountant": ("المحاسب", "التحصيل والصندوق والمصروفات والتقارير المالية"),
    "distribution": ("مسؤول التوزيع", "الموزعون والعملاء والصرف والتحصيل"),
    "production": ("مسؤول الإنتاج", "العجنات والإنتاج والتوزيع المجاني والتسليمات"),
    "storekeeper": ("أمين المخزون", "المواد الخام والأرصدة"),
    "receiver": ("المستلم/الكاشير", "التسليمات المصرح بها"),
    "read_only": ("عرض فقط", "عرض الصفحات والتقارير المسموح بها"),
}


def seed_default_roles():
    permission_map = {}
    for name, code, description in PERMISSIONS:
        permission = db.session.query(Permission).filter_by(code=code).one_or_none()
        if permission is None:
            permission = Permission(name=name, code=code, description=description)
            db.session.add(permission)
        else:
            permission.name = name
            permission.description = description
        permission_map[code] = permission

    role_map = {}
    for code, (name, description) in ROLE_LABELS.items():
        role = db.session.query(Role).filter_by(code=code).one_or_none()
        if role is None:
            role = Role(name=name, code=code, description=description, is_system=True)
            db.session.add(role)
        else:
            role.name = name
            role.description = description
            role.is_system = True
        role_map[code] = role

    db.session.flush()
    for code, permission_codes in ROLE_PERMISSIONS.items():
        role_map[code].permissions = [permission_map[item] for item in permission_codes]

    db.session.commit()
    return role_map
