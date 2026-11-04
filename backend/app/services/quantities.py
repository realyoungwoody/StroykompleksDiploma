from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ..schemas import (
    CHAT_MESSAGE_MAX_LENGTH,
    MAX_QUANTITY,
    MIN_QUANTITY,
    QUANTITY_DECIMAL_PLACES,
)

# Five integer digits cover the existing upper bound of 10000. The fractional
# bound mirrors the Pydantic quantity fields, and the gap accommodates normal
# human formatting without scanning arbitrarily long whitespace runs.
NUMBER_PATTERN = r"(?<![\w.,+\-])(\d{1,5}(?:[.,]\d{1,2})?)(?![\d.,])"
UNIT_GAP_PATTERN = r"\s{0,16}"
AREA_UNIT_PATTERN = re.compile(
    NUMBER_PATTERN
    + UNIT_GAP_PATTERN
    + (
        r"(?:м2|м²|кв(?:адрат(?:н(?:ых|ого|ые)?)?)?\.?"
        + UNIT_GAP_PATTERN
        + r"(?:м(?:етр(?:а|ов)?)?)?|квадрат(?:а|ов)?)"
    ),
    re.IGNORECASE,
)
SELECTION_AREA_UNIT_PATTERN = re.compile(
    NUMBER_PATTERN
    + UNIT_GAP_PATTERN
    + (
        r"(?:м2|м²|кв\.?"
        + UNIT_GAP_PATTERN
        + r"(?:м(?:етр(?:а|ов)?)?)?|квадрат[а-яё]{0,12}|"
        r"метр(?:а|ов)?(?:\s{1,16}ква[а-яё]{0,12})?)"
    ),
    re.IGNORECASE,
)
AREA_PREFIX_PATTERN = re.compile(
    r"площад(?:ь|ью|и)\s{0,16}"
    r"(?:около\s{1,16}|примерно\s{1,16}|[-—:]\s{0,16})?"
    + NUMBER_PATTERN,
    re.IGNORECASE,
)
BARE_NUMBER_PATTERN = re.compile(NUMBER_PATTERN)

NUMBER_WORDS = {
    "один": 1,
    "десять": 10,
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
    "сто": 100,
}


def bounded_message(text: str) -> str:
    """Apply the same length ceiling enforced by ChatIn and ChatMessage."""
    return text[:CHAT_MESSAGE_MAX_LENGTH]


def _parse_quantity(value: str) -> Decimal | None:
    try:
        quantity = Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None
    fractional_digits = max(0, -quantity.as_tuple().exponent)
    if (
        quantity < MIN_QUANTITY
        or quantity > MAX_QUANTITY
        or fractional_digits > QUANTITY_DECIMAL_PLACES
    ):
        return None
    return quantity


def _numeric_values(pattern: re.Pattern[str], text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for match in pattern.finditer(text):
        quantity = _parse_quantity(match.group(1))
        if quantity is not None:
            values.append(quantity)
    return values


def extract_area_quantities(
    text: str, *, selection_units: bool = False, include_words: bool = False
) -> list[Decimal]:
    normalized = bounded_message(text).lower()
    unit_pattern = SELECTION_AREA_UNIT_PATTERN if selection_units else AREA_UNIT_PATTERN
    values = _numeric_values(unit_pattern, normalized)
    if not values:
        values = _numeric_values(AREA_PREFIX_PATTERN, normalized)
    if include_words:
        for word, value in NUMBER_WORDS.items():
            word_pattern = re.compile(
                rf"(?<![а-яё]){word}(?![а-яё])\s{{1,16}}"
                r"(?:квадрат[а-яё]{0,12}|метр[а-яё]{0,8}|м²)"
            )
            if word_pattern.search(normalized):
                values.append(Decimal(value))
    return list(dict.fromkeys(values))


def extract_numbers(text: str) -> set[Decimal]:
    normalized = bounded_message(text).lower()
    return set(_numeric_values(BARE_NUMBER_PATTERN, normalized))
