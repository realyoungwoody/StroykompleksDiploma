from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import CHAT_MESSAGE_MAX_LENGTH, ChatIn
from app.services.assistant import (
    _extract_areas,
    _extract_numbers,
    _mask_personal_data,
)
from app.services.quantities import extract_area_quantities
from app.services.selection import _quantities


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Нужно покрасить 50 м²", Decimal("50")),
        ("Нужно покрасить 50м2", Decimal("50")),
        ("Площадь стен 50,5 м²", Decimal("50.5")),
        ("Плитка на 50.5 кв", Decimal("50.5")),
        ("Натяжной потолок на 50 квадратов", Decimal("50")),
        ("Штукатурка на 50 квадратных метров", Decimal("50")),
        ("Площадь около 50,5", Decimal("50.5")),
        ("Ламинат 0,1 м²", Decimal("0.1")),
        ("Покраска 10000 м²", Decimal("10000")),
    ],
)
def test_supported_area_formats_use_shared_quantity_rules(message, expected):
    assert extract_area_quantities(message) == [expected]
    assert _extract_areas(message) == [expected]
    assert _quantities(message) == [expected]


def test_selection_preserves_meters_with_misspelled_square_qualifier():
    message = "Штукатурка 90 метров кважратных"
    assert _quantities(message) == [Decimal("90")]
    assert _extract_areas(message) == []


@pytest.mark.parametrize(
    "message",
    [
        "123456 м²",
        "abc50 м²",
        "-50 м²",
        "+50 м²",
        "50.123 м²",
        "50, м²",
        "0 м²",
        "0.01 м²",
        "10001 м²",
        "10000.01 м²",
    ],
)
def test_invalid_or_out_of_range_areas_are_not_recognized(message):
    assert extract_area_quantities(message, include_words=True) == []
    assert _extract_numbers(message) == set()


def test_long_digit_sequence_is_not_split_into_false_quantity():
    message = "9" * (CHAT_MESSAGE_MAX_LENGTH - 3) + " м²"
    assert extract_area_quantities(message, include_words=True) == []
    assert _extract_numbers(message) == set()


def test_long_whitespace_sequence_is_bounded_and_not_recognized():
    message = "50" + " " * 100_000 + "м²"
    assert extract_area_quantities(message, include_words=True) == []


def test_internal_scanners_apply_chat_message_length_limit():
    message = "9" * 100_000
    assert extract_area_quantities(message) == []
    assert len(_mask_personal_data("+" * 100_000)) == CHAT_MESSAGE_MAX_LENGTH


def test_chat_schema_rejects_messages_above_shared_limit():
    with pytest.raises(ValidationError):
        ChatIn(message="9" * (CHAT_MESSAGE_MAX_LENGTH + 1))


def test_personal_data_masking_stays_functional_with_bounded_patterns():
    masked = _mask_personal_data(
        "Напишите test.user+demo@example.com или позвоните +7 (999) 123-45-67"
        + " " * 1000
    )
    assert "test.user" not in masked
    assert "999" not in masked
    assert masked.count("[персональные данные скрыты]") == 2


def test_fractional_area_produces_verified_cart_action(client):
    response = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "Натяжной потолок 50,5 м²",
            "conversation_id": "fractional-area",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["selection"]["items"][0]["status"] == "ready"
    assert data["selection"]["items"][0]["can_add_to_cart"] is True
    assert Decimal(str(data["cart_actions"][0]["quantity"])) == Decimal("50.5")


def test_oversized_chat_message_is_rejected_before_regex_processing(client):
    response = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "9" * (CHAT_MESSAGE_MAX_LENGTH + 1),
            "conversation_id": "oversized-message",
        },
    )
    assert response.status_code == 422
