from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.database import SessionLocal
from app.schemas import ChatIn
from app.services import assistant


SERVICES = [
    (1, "механизированная штукатурка"),
    (2, "ручная штукатурка"),
    (3, "водоэмульсионная покраска"),
    (4, "масляная покраска"),
    (5, "настенная плитка"),
    (6, "напольная плитка"),
    (7, "натяжной потолок"),
    (8, "укладка ламината"),
]
QUANTITIES = [1, 5, 20, 53, 90]
TEMPLATES = [
    "Нужна {service}, {quantity} м²",
    "Нужно {quantity} квадратов: {service}",
    "{service}, площадь {quantity} квадратных метров",
]


@pytest.mark.parametrize(
    ("service_id", "service", "quantity", "template"),
    [
        (service_id, service, quantity, template)
        for service_id, service in SERVICES
        for quantity in QUANTITIES
        for template in TEMPLATES
    ],
)
def test_120_complete_dialogs_always_return_verified_action(
    client, service_id, service, quantity, template
):
    response = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": template.format(service=service, quantity=quantity),
            "conversation_id": f"scenario-{service_id}-{quantity}-{TEMPLATES.index(template)}",
            "selection": {
                "conversation_id": f"scenario-{service_id}-{quantity}-{TEMPLATES.index(template)}",
                "revision": 0,
                "items": [],
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["cart_actions"]) == 1
    action = data["cart_actions"][0]
    assert action["service_id"] == service_id
    assert Decimal(str(action["quantity"])) == Decimal(quantity)
    assert Decimal(str(action["line_total_rub"])) > 0
    assert data["selection"]["items"][0]["status"] == "ready"
    assert data["selection"]["items"][0]["can_add_to_cart"] is True


def chat(client, conversation_id, message, selection=None, cart=None):
    return client.post(
        "/api/v1/assistant/chat",
        json={
            "message": message,
            "conversation_id": conversation_id,
            "selection": selection
            or {"conversation_id": conversation_id, "revision": 0, "items": []},
            "cart": cart or [],
        },
    ).json()


def test_quantity_arrives_later_and_immediately_makes_item_ready(client):
    first = chat(client, "selection-later", "Хочу натяжной потолок")
    assert first["selection"]["items"][0]["status"] == "incomplete"
    assert first["cart_actions"] == []

    second = chat(client, "selection-later", "50 квадратов", first["selection"])
    assert second["selection"]["items"][0]["status"] == "ready"
    assert Decimal(str(second["cart_actions"][0]["quantity"])) == Decimal("50")


def test_quantity_correction_replaces_old_revision(client):
    first = chat(client, "selection-correction", "Натяжной потолок 40 м²")
    second = chat(
        client,
        "selection-correction",
        "Нет, точно 53 квадратных метра",
        first["selection"],
    )
    assert first["calculation_id"] != second["calculation_id"]
    assert Decimal(str(second["cart_actions"][0]["quantity"])) == Decimal("53")
    assert second["selection"]["revision"] == first["selection"]["revision"] + 1


def test_preference_survives_until_quantity_is_known(client):
    first = chat(client, "selection-color", "Хочу красный натяжной потолок")
    second = chat(client, "selection-color", "50 квадратов", first["selection"])
    assert "красный" in second["cart_actions"][0]["note"]


def test_ready_item_survives_long_unrelated_dialog(client):
    current = chat(client, "selection-long", "Натяжной потолок 25 м²")
    for index in range(10):
        current = chat(
            client,
            "selection-long",
            f"Расскажи подробнее о технологии, вопрос {index}",
            current["selection"],
        )
        assert len(current["cart_actions"]) == 1
        assert Decimal(str(current["cart_actions"][0]["quantity"])) == Decimal("25")


def test_three_services_have_independent_actions(client):
    result = chat(
        client,
        "selection-three",
        "Механизированная штукатурка 30 м², масляная покраска 50 м² "
        "и натяжной потолок 25 м²",
    )
    assert {action["service_id"] for action in result["cart_actions"]} == {1, 4, 7}
    assert {
        action["service_id"]: Decimal(str(action["quantity"]))
        for action in result["cart_actions"]
    } == {1: Decimal("30"), 4: Decimal("50"), 7: Decimal("25")}


def test_sequential_services_do_not_remove_previous_ready_item(client):
    plaster = chat(
        client, "selection-sequential", "Механизированная штукатурка 30 м²"
    )
    painting = chat(
        client,
        "selection-sequential",
        "Ещё нужна масляная покраска 50 м²",
        plaster["selection"],
    )
    assert {action["service_id"] for action in painting["cart_actions"]} == {1, 4}


def test_incomplete_item_does_not_block_ready_item(client):
    result = chat(
        client,
        "selection-partial",
        "Механизированная штукатурка 30 м² и натяжной потолок",
    )
    assert [action["service_id"] for action in result["cart_actions"]] == [1]
    statuses = {item["kind"]: item["status"] for item in result["selection"]["items"]}
    assert statuses == {"plaster": "ready", "ceiling": "incomplete"}


def test_changing_one_item_keeps_other_quantities(client):
    first = chat(
        client,
        "selection-update-one",
        "Механизированная штукатурка 30 м², масляная покраска 50 м² "
        "и натяжной потолок 25 м²",
    )
    second = chat(
        client,
        "selection-update-one",
        "Покраску давай на 70 квадратов",
        first["selection"],
    )
    quantities = {
        action["service_id"]: Decimal(str(action["quantity"]))
        for action in second["cart_actions"]
    }
    assert quantities == {1: Decimal("30"), 4: Decimal("70"), 7: Decimal("25")}


def test_cancel_removes_only_named_selection(client):
    first = chat(
        client,
        "selection-cancel",
        "Механизированная штукатурка 30 м² и масляная покраска 50 м²",
    )
    second = chat(
        client, "selection-cancel", "Убери покраску", first["selection"]
    )
    assert [action["service_id"] for action in second["cart_actions"]] == [1]


def test_matching_cart_item_is_marked_added_and_cannot_be_added_twice(client):
    first = chat(client, "selection-added", "Натяжной потолок 50 м²")
    second = chat(
        client,
        "selection-added",
        "Что дальше?",
        first["selection"],
        cart=[{"service_id": 7, "quantity": "50"}],
    )
    assert second["cart_actions"] == []
    assert second["selection"]["items"][0]["status"] == "added"
    assert second["selection"]["items"][0]["can_add_to_cart"] is False


def test_selection_from_another_conversation_is_not_reused(client):
    first = chat(client, "selection-owner", "Натяжной потолок 50 м²")
    response = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "Расскажи подробнее",
            "conversation_id": "selection-other",
            "selection": first["selection"],
        },
    )
    assert response.status_code == 200
    assert response.json()["selection"]["items"] == []
    assert "STALE_SELECTION" in response.json()["selection"]["diagnostics"]
    assert response.json()["cart_actions"] == []


@pytest.mark.parametrize(
    ("mode", "base_url", "api_key"),
    [
        ("remote", "https://provider.example/v1", "remote-key"),
        ("local", "http://ollama:11434/v1", ""),
    ],
)
def test_ready_actions_survive_remote_and_local_provider_failures(
    monkeypatch, mode, base_url, api_key
):
    settings = SimpleNamespace(
        llm_mode=mode,
        llm_base_url=base_url,
        llm_api_key=api_key,
        llm_model="qwen3:1.7b" if mode == "local" else "remote-model",
        llm_timeout_seconds=1,
        llm_max_tokens=100,
    )
    monkeypatch.setattr(assistant, "get_settings", lambda: settings)
    monkeypatch.setattr(
        assistant,
        "_call_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()),
    )
    conversation_id = f"provider-{mode}"
    with SessionLocal() as db:
        result = assistant.client_answer(
            db,
            ChatIn(
                message="Натяжной потолок 50 м²",
                conversation_id=conversation_id,
                selection={
                    "conversation_id": conversation_id,
                    "revision": 0,
                    "items": [],
                },
            ),
        )
    assert result["cart_actions"][0]["service_id"] == 7
    assert Decimal(str(result["cart_actions"][0]["quantity"])) == Decimal("50")
    assert result["selection"]["items"][0]["status"] == "ready"
    assert result["warning"]
