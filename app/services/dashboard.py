"""Shared defaults and validation for dashboard navigation shortcuts."""

from urllib.parse import urlsplit


DEFAULT_QUICK_ACTIONS = [
    {"label": "دفع موزع", "url": "/distribution/payment/distributor", "enabled": True},
    {"label": "دفع عميل", "url": "/distribution/payment/customer", "enabled": True},
    {"label": "صرف موزع", "url": "/distribution/issue/distributor", "enabled": True},
    {"label": "صرف عميل", "url": "/distribution/issue/customer", "enabled": True},
    {"label": "إضافة صنف", "url": "/products/?action=new", "enabled": True},
    {"label": "إضافة مادة خام", "url": "/inventory/?action=new", "enabled": True},
    {"label": "تسجيل عجنة", "url": "/production/?action=batch", "enabled": True},
    {"label": "موزعون وعملاء", "url": "/parties/", "enabled": True},
    {"label": "مستفيد مجاني", "url": "/operations/free-distribution/?action=recipient", "enabled": True},
    {"label": "تسجيل مصروف", "url": "/finance/expenses/?action=new", "enabled": True},
]


def validate_internal_path(value):
    """Only allow same-site relative paths; never store external or script URLs."""
    value = (value or "").strip()
    if (
        not value
        or len(value) > 500
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or any(ord(char) < 32 for char in value)
    ):
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return None
    return value


def normalize_quick_actions(value):
    """Return sanitized persisted shortcuts; None means use defaults."""
    if not isinstance(value, list):
        return [dict(action) for action in DEFAULT_QUICK_ACTIONS]
    if value and all(isinstance(item, str) for item in value):
        legacy = {
            "product_new": "/products/?action=new",
            "inventory_new": "/inventory/?action=new",
            "production_batch": "/production/?action=batch",
            "employee_new": "/staff/employees/?action=new",
            "free_recipient": "/operations/free-distribution/?action=recipient",
            "expense_new": "/finance/expenses/?action=new",
            "products": "/products/",
            "distributor_new": "/parties/distributors/?action=new",
            "customer_new": "/parties/customers/?action=new",
            "account": "/auth/account",
        }
        labels = {key: key.replace("_", " ").title() for key in legacy}
        return [
            {"label": labels[key], "url": legacy[key], "enabled": True}
            for key in value if key in legacy
        ]
    result = []
    for action in value[:20]:
        if not isinstance(action, dict):
            continue
        label = str(action.get("label") or "").strip()[:50]
        url = validate_internal_path(str(action.get("url") or ""))
        if label and url:
            result.append({"label": label, "url": url, "enabled": bool(action.get("enabled", True))})
    return result
