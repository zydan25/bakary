"""Phone input normalization shared by sign-in and account administration."""

import re


_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)


def normalize_phone(value):
    """Normalize numerals and common visual separators without guessing a country code."""
    if value is None:
        return ""
    value = str(value).translate(_DIGIT_TRANSLATION).strip()
    value = re.sub(r"[\s().-]+", "", value)
    if value.startswith("00"):
        value = "+" + value[2:]
    return value
