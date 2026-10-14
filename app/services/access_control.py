"""Idempotent seeding for baseline roles and permissions."""

from app.extensions import db
from app.models.role import Permission, Role


PERMISSIONS = [
    ("عرض الرئيسية", "dashboard.view", "عرض لوحة التحكم"),
    ("إدارة المستخدمين", "users.manage", "إدارة الحسابات والأدوار"),
    ("إدارة الإعدادات", "settings.manage", "تغيير إعدادات النظام"),
    ("عرض الأطراف", "parties.view", "عرض الموزعين والعملاء"),
    ("إدارة الأطراف", "parties.manage", "إضافة وتعديل وتعطيل الموزعين والعملاء"),
    ("صرف البضاعة", "distribution.issue", "تسجيل صرف البضاعة"),
    ("التحصيل النقدي", "distribution.payment", "تسجيل مدفوعات الموزعين والعملاء"),
    ("تقارير التوزيع", "distribution.reports", "عرض تقارير الصرف وكشوف الحساب"),
    ("عرض المخزون", "inventory.view", "عرض الأرصدة وحركات المخزون"),
    ("إدارة المخزون", "inventory.manage", "إدخال المواد وتسوية المخزون"),
    ("إدارة الإنتاج", "production.manage", "تسجيل العجنات والإنتاج والإقفال"),
    ("تسجيل التسليمات", "handover.manage", "تسجيل تسليمات المستلم والفترة"),
    ("عرض المالية", "finance.view", "عرض الصندوق والحسابات"),
    ("إدارة المالية", "finance.manage", "تسجيل القبض والصرف والتحويل"),
    ("عرض التقارير", "reports.view", "عرض التقارير المسموح بها"),
    ("تصدير التقارير", "reports.export", "تصدير التقارير المسموح بها"),
]

ROLE_PERMISSIONS = {
    "owner": [code for _, code, _ in PERMISSIONS],
    "accountant": [
        "dashboard.view", "parties.view", "distribution.payment",
        "distribution.reports", "finance.view", "finance.manage",
        "reports.view", "reports.export", "inventory.view",
    ],
    "distribution": [
        "dashboard.view", "parties.view", "parties.manage",
        "distribution.issue", "distribution.payment", "distribution.reports",
        "reports.view",
    ],
    "production": [
        "dashboard.view", "inventory.view", "production.manage",
        "handover.manage", "reports.view",
    ],
    "storekeeper": [
        "dashboard.view", "inventory.view", "inventory.manage",
        "reports.view",
    ],
    "receiver": [
        "dashboard.view", "handover.manage", "finance.view",
    ],
    "read_only": [
        "dashboard.view", "parties.view", "distribution.reports",
        "inventory.view", "finance.view", "reports.view",
    ],
}

ROLE_LABELS = {
    "owner": ("المالك/المدير", "جميع صلاحيات النظام"),
    "accountant": ("المحاسب", "التحصيل والصندوق والتقارير المالية"),
    "distribution": ("مسؤول التوزيع", "الموزعون والعملاء والصرف والتحصيل"),
    "production": ("مسؤول الإنتاج", "العجنات والإنتاج والتسليمات"),
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
