from app.services.amount_words import (
    amount_to_arabic_words,
    integer_to_arabic_words,
    quantity_to_arabic_words,
)


def test_arabic_words_for_money_and_quantity():
    amount = amount_to_arabic_words("12.50")
    assert amount.startswith("اثنا عشر ريال")
    assert "فلس" in amount
    assert quantity_to_arabic_words(5, "حبة") == "خمسة حبة"
    assert integer_to_arabic_words(1000) == "ألف"
