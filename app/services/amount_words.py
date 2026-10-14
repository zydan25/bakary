"""Arabic wording helpers for amounts and quantities."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


ONES = {
    0: "صفر", 1: "واحد", 2: "اثنان", 3: "ثلاثة", 4: "أربعة",
    5: "خمسة", 6: "ستة", 7: "سبعة", 8: "ثمانية", 9: "تسعة",
}
TEENS = {
    10: "عشرة", 11: "أحد عشر", 12: "اثنا عشر", 13: "ثلاثة عشر",
    14: "أربعة عشر", 15: "خمسة عشر", 16: "ستة عشر",
    17: "سبعة عشر", 18: "ثمانية عشر", 19: "تسعة عشر",
}
TENS = {
    2: "عشرون", 3: "ثلاثون", 4: "أربعون", 5: "خمسون",
    6: "ستون", 7: "سبعون", 8: "ثمانون", 9: "تسعون",
}
HUNDREDS = {
    1: "مائة", 2: "مائتان", 3: "ثلاثمائة", 4: "أربعمائة",
    5: "خمسمائة", 6: "ستمائة", 7: "سبعمائة", 8: "ثمانمائة",
    9: "تسعمائة",
}
SCALES = [
    (10**9, "مليار", "مليار", "مليارات"),
    (10**6, "مليون", "مليون", "ملايين"),
    (10**3, "ألف", "ألف", "آلاف"),
]


def _under_thousand(number):
    if number == 0:
        return ""
    parts = []
    hundreds = number // 100
    rest = number % 100
    if hundreds:
        parts.append(HUNDREDS[hundreds])
    if 1 <= rest <= 9:
        parts.append(ONES[rest])
    elif 10 <= rest <= 19:
        parts.append(TEENS[rest])
    elif rest >= 20:
        unit, ten = rest % 10, rest // 10
        if unit:
            parts.append(ONES[unit])
        parts.append(TENS[ten])
    return " و ".join(parts)


def integer_to_arabic_words(value):
    number = int(value)
    if number < 0:
        return "سالب " + integer_to_arabic_words(abs(number))
    if number == 0:
        return "صفر"

    parts = []
    remainder = number
    for scale, singular, dual, plural in SCALES:
        group, remainder = divmod(remainder, scale)
        if not group:
            continue
        if group == 1:
            parts.append(singular)
        elif group == 2:
            parts.append(dual)
        elif 3 <= group <= 10:
            parts.append(_under_thousand(group) + " " + plural)
        else:
            parts.append(_under_thousand(group) + " " + singular)
    if remainder:
        parts.append(_under_thousand(remainder))
    return " و ".join(parts)


def amount_to_arabic_words(value, currency="ريال"):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if not amount.is_finite():
        return ""
    prefix = "سالب " if amount < 0 else ""
    amount = abs(amount)
    whole = int(amount)
    fraction = int((amount - Decimal(whole)) * 100)
    phrase = f"{integer_to_arabic_words(whole)} {currency}"
    if fraction:
        phrase += f" و {integer_to_arabic_words(fraction)} فلس"
    return prefix + phrase


def quantity_to_arabic_words(value, unit="حبة"):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if not number.is_finite() or number < 0:
        return ""
    integer = int(number)
    fraction = number - Decimal(integer)
    phrase = f"{integer_to_arabic_words(integer)} {unit}"
    if fraction:
        phrase += f" و {format(fraction.normalize(), 'f')} من {unit}"
    return phrase
