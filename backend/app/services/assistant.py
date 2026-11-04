from __future__ import annotations

import json
import logging
import re
import secrets
import time
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core.config import get_settings
from ..models import Order, OrderItem, Service
from ..schemas import ChatIn, ItemIn
from .pricing import calculate_quote
from .quantities import bounded_message, extract_area_quantities, extract_numbers
from .selection import update_selection
from ..seed import FAQ

logger = logging.getLogger(__name__)
LLM_RETRY_DELAYS = (0.25, 0.75)
LLM_RETRY_STATUSES = {429, 500, 502, 503, 504}
EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[\w.+-]{1,64}@[\w.-]{1,253}(?![\w.-])"
)
PHONE_PATTERN = re.compile(
    r"(?<![\w+])(?:\+7|8)(?:[ ()-]{0,3}\d){10}"
    r"(?!(?:[ ()-]{0,3}\d))"
)
SERVICE_SEGMENT_PATTERN = re.compile(
    r"\s{1,16}(?:и|а\s{1,16}также)\s{1,16}|;",
    re.IGNORECASE,
)
REMOTE_SAFE_TOKEN_PATTERN = re.compile(
    r"(?<![а-яёa-z0-9])[а-яёa-z]{1,32}(?![а-яёa-z0-9])|"
    r"(?<![\w.,+\-])\d{1,5}(?:[.,]\d{1,2})?(?![\d.,])",
    re.IGNORECASE,
)
REMOTE_SAFE_WORD_PATTERN = re.compile(
    r"(?:штукатур[а-яё]{0,12}|механиз[а-яё]{0,14}|ручн(?:ая|ой|ую|ое|ые)|"
    r"покрас[а-яё]{0,12}|окрас[а-яё]{0,12}|краск(?:а|и|ой|у|е)|"
    r"водоэмульс[а-яё]{0,16}|маслян[а-яё]{0,12}|плитк(?:а|и|ой|у|е)|"
    r"облицов[а-яё]{0,14}|стен(?:а|ы|е|у|ой|ах|ам)?|"
    r"пол(?:а|у|ом|ы|ов|ах|ам)?|потол[а-яё]{0,12}|натяжн[а-яё]{0,12}|"
    r"ламин[а-яё]{0,12}|площад[а-яё]{0,10}|квадрат[а-яё]{0,12}|"
    r"метр[а-яё]{0,8}|услуг[а-яё]{0,8}|стоимост[а-яё]{0,6}|цен(?:а|ы|е|у|ой)|"
    r"рассчит[а-яё]{0,12}|расч[её]т[а-яё]{0,8}|корзин[а-яё]{0,8}|"
    r"добав[а-яё]{0,12}|убер[а-яё]{0,10}|удал[а-яё]{0,10}|"
    r"замен[а-яё]{0,10}|измен[а-яё]{0,10}|нуж(?:на|ен|но|ны)|"
    r"хоч(?:у|ет|ете|ется)|сдел[а-яё]{0,10}|помог[а-яё]{0,8}|"
    r"расскаж[а-яё]{0,8}|возможност[а-яё]{0,6}|привет|здравств[а-яё]{0,8})",
    re.IGNORECASE,
)
QUANTITY_CONTEXT_ROOTS = (
    "стен",
    "пол",
    "потол",
    "площад",
    "штукатур",
    "покрас",
    "плит",
    "ламин",
)


def _mask_personal_data(text: str) -> str:
    safe = EMAIL_PATTERN.sub("[персональные данные скрыты]", bounded_message(text))
    return PHONE_PATTERN.sub("[персональные данные скрыты]", safe)


def _remote_safe_text(text: str, *, allow_contextual_numbers: bool = False) -> str:
    """Create a domain-only prompt without forwarding free-form customer data."""
    bounded = bounded_message(text).lower()
    area_values = set(extract_area_quantities(bounded, selection_units=True))
    matches = list(REMOTE_SAFE_TOKEN_PATTERN.finditer(bounded))
    safe_tokens: list[str] = []
    previous_safe_word = ""
    for match in matches:
        token = match.group(0)
        if token[0].isdigit():
            try:
                value = Decimal(token.replace(",", "."))
            except InvalidOperation:
                continue
            has_quantity_context = any(
                root in previous_safe_word for root in QUANTITY_CONTEXT_ROOTS
            )
            if value in area_values or (allow_contextual_numbers and has_quantity_context):
                safe_tokens.append(token)
            continue
        if REMOTE_SAFE_WORD_PATTERN.fullmatch(token) or token in {"м", "м2", "кв"}:
            safe_tokens.append(token)
            previous_safe_word = token
        else:
            previous_safe_word = ""
    if not safe_tokens:
        return "Запрос без безопасных отраслевых параметров."
    return "Безопасные параметры запроса: " + " ".join(safe_tokens)


def _llm_safe_text(text: str, *, allow_contextual_numbers: bool = False) -> str:
    if _llm_provider() == "local":
        return _mask_personal_data(text)
    return _remote_safe_text(text, allow_contextual_numbers=allow_contextual_numbers)


def _llm_warning(exc: Exception, model: str) -> str:
    is_local = _llm_provider() == "local"
    source = "локальная модель" if is_local else "ИИ API"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            reason = "проверьте API-ключ и права доступа"
        elif status == 404:
            reason = f"модель {model} недоступна"
        elif status == 429:
            reason = "превышен лимит запросов"
        elif status >= 500:
            reason = "провайдер временно недоступен"
        else:
            reason = f"провайдер вернул HTTP {status}"
        logger.warning(
            "LLM request failed: status=%s model=%s error=%s",
            status,
            model,
            type(exc).__name__,
        )
        unavailable = "Локальная модель недоступна" if is_local else "ИИ API недоступен"
        return f"{unavailable}: {reason}. Показан ответ demo-режима."
    if isinstance(exc, httpx.RequestError):
        logger.warning(
            "LLM request failed: model=%s error=%s", model, type(exc).__name__
        )
        return f"Не удалось подключиться к {source}. Показан ответ demo-режима."
    logger.exception("Invalid LLM response: model=%s error=%s", model, type(exc).__name__)
    invalid = "Локальная модель вернула" if is_local else "ИИ API вернул"
    return f"{invalid} некорректный ответ. Показан ответ demo-режима."


def _call_llm(messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
    settings = get_settings()
    response = None
    started_at = time.monotonic()
    for attempt in range(len(LLM_RETRY_DELAYS) + 1):
        try:
            request_body: dict[str, Any] = {
                "model": settings.llm_model,
                "messages": messages,
                "max_tokens": getattr(settings, "llm_max_tokens", 350),
                "temperature": 0.2,
                "stream": False,
            }
            if json_mode:
                request_body["response_format"] = {"type": "json_object"}
            response = httpx.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json=request_body,
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            break
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code in LLM_RETRY_STATUSES
            if not retryable or attempt >= len(LLM_RETRY_DELAYS):
                raise
        except httpx.RequestError:
            if attempt >= len(LLM_RETRY_DELAYS):
                raise
        delay = LLM_RETRY_DELAYS[attempt]
        logger.info(
            "Retrying LLM request: attempt=%s model=%s delay_seconds=%s",
            attempt + 2,
            settings.llm_model,
            delay,
        )
        time.sleep(delay)
    if response is None:
        raise RuntimeError("LLM request did not produce a response")
    data: dict[str, Any] = response.json()
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM response does not contain message content")
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if not cleaned:
        raise ValueError("LLM response contains only reasoning")
    logger.info(
        "LLM request completed: provider=%s model=%s duration_seconds=%.2f",
        _llm_provider(),
        settings.llm_model,
        time.monotonic() - started_at,
    )
    return cleaned


def _llm_provider() -> str:
    mode = get_settings().llm_mode.strip().lower()
    if mode == "local":
        return "local"
    if mode in {"remote", "auto", "llm"}:
        return "remote"
    return "demo"


def _llm_configured() -> bool:
    settings = get_settings()
    provider = _llm_provider()
    if provider == "demo":
        return False
    if provider == "local":
        endpoint = urlparse(settings.llm_base_url)
        return bool(
            endpoint.scheme == "http"
            and endpoint.hostname == "ollama"
            and settings.llm_model
        )
    return bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[а-яёa-z0-9]+", text.lower()) if len(w) > 2}


SERVICE_QUERY_PATTERNS: dict[str, tuple[tuple[str, int], ...]] = {
    "mekhanizirovannaya-shtukaturka": (
        (r"механиз\w*\s+штукатур|\bмеханиз", 20),
        (r"штукатур", 6),
    ),
    "ruchnaya-shtukaturka": (
        (r"ручн\w*\s+штукатур", 20),
        (r"штукатур", 6),
    ),
    "pokraska-vodoemulsionnaya": (
        (r"водоэмульс", 20),
        (r"покрас|окрас|краск", 6),
    ),
    "pokraska-maslyanaya": (
        (r"маслян\w*\s+краск|маслян\w*\s+покрас", 20),
        (r"покрас|окрас|краск", 6),
    ),
    "nastennaya-plitka": (
        (r"настенн\w*\s+плит|плит\w*\s+(?:на\s+)?стен", 20),
        (r"плит", 6),
    ),
    "napolnaya-plitka": (
        (r"напольн\w*\s+плит|плит\w*\s+(?:на\s+)?пол", 20),
        (r"плит", 6),
    ),
    "natyazhnoy-potolok": ((r"натяжн\w*\s+потол|потол", 10),),
    "laminat": ((r"ламин", 10),),
}


def search_services(db: Session, query: str) -> list[Service]:
    words = _words(query)
    normalized = query.lower()
    ranked = []
    for service in db.scalars(select(Service).where(Service.is_active.is_(True))).all():
        text = f"{service.name} {service.category} {service.short_description}".lower()
        score = sum(1 for word in words if word in text) + sum(
            weight
            for pattern, weight in SERVICE_QUERY_PATTERNS.get(service.slug, ())
            if re.search(pattern, normalized)
        )
        if score >= 2:
            ranked.append((score, service))
    return [
        service
        for _, service in sorted(ranked, key=lambda row: (-row[0], row[1].sort_order))[
            :5
        ]
    ]


def _extract_areas(text: str) -> list[Decimal]:
    return extract_area_quantities(text)


def _extract_area(text: str) -> Decimal | None:
    quantities = _extract_areas(text)
    return quantities[0] if quantities else None


def _extract_numbers(text: str) -> set[Decimal]:
    return extract_numbers(text)


def _assistant_requested_area(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in ("площад", "квадратн", "м²", "кв. м"))


def _is_affirmative(text: str) -> bool:
    words = re.findall(r"[а-яё]+", text.lower())
    allowed = {
        "да",
        "верно",
        "правильно",
        "точно",
        "тоже",
        "всё",
        "все",
        "так",
        "согласен",
        "согласна",
    }
    return bool(words) and set(words) <= allowed and any(
        word in {"да", "верно", "правильно", "точно", "согласен", "согласна"}
        for word in words
    )


def _confirmed_history_quantities(payload: ChatIn) -> set[Decimal]:
    """Resolve an explicit area that the user confirms with a short affirmative."""
    if not payload.history or not _is_affirmative(payload.message):
        return set()
    previous = payload.history[-1]
    if previous.role != "assistant" or not _assistant_requested_area(previous.content):
        return set()
    proposed = set(_extract_areas(previous.content))
    if not proposed:
        return set()
    user_numbers = {
        quantity
        for message in payload.history[-6:]
        if message.role == "user"
        for quantity in _extract_numbers(message.content)
    }
    return proposed & user_numbers


def _allowed_action_quantities(payload: ChatIn) -> set[Decimal]:
    quantities = set(_extract_areas(payload.message))
    recent_assistant_requested_area = any(
        message.role == "assistant" and _assistant_requested_area(message.content)
        for message in payload.history[-2:]
    )
    if not quantities and recent_assistant_requested_area:
        quantities = _extract_numbers(payload.message)
    if not quantities:
        quantities = _confirmed_history_quantities(payload)
    return quantities


def _explicit_service_slugs(text: str) -> set[str]:
    """Return only variants named by a service-specific catalog pattern."""
    normalized = text.lower()
    return {
        slug
        for slug, patterns in SERVICE_QUERY_PATTERNS.items()
        if patterns and re.search(patterns[0][0], normalized)
    }


def _confirmed_history_cart_actions(
    db: Session, payload: ChatIn
) -> tuple[list[dict], dict | None]:
    """Build actions without an LLM when the user confirms a proposed known area."""
    quantities = _confirmed_history_quantities(payload)
    if len(quantities) != 1:
        return [], None
    quantity = next(iter(quantities))
    if not Decimal("0.1") <= quantity <= Decimal("10000"):
        return [], None
    user_context = "\n".join(
        message.content for message in payload.history[-6:] if message.role == "user"
    )
    slugs = _explicit_service_slugs(user_context)
    if not slugs or len(slugs) > 5:
        return [], None
    services = db.scalars(
        select(Service)
        .where(Service.is_active.is_(True), Service.slug.in_(slugs))
        .order_by(Service.sort_order, Service.name)
    ).all()
    if len(services) != len(slugs):
        return [], None
    quote = calculate_quote(
        db,
        [ItemIn(service_id=service.id, quantity=quantity) for service in services],
    )
    note = _preference_note(user_context)
    actions = [
        {
            "action": "add_to_cart",
            "service_id": line.service_id,
            "name": line.name,
            "unit": line.unit,
            "quantity": line.quantity,
            "unit_price_rub": line.unit_price_rub,
            "line_total_rub": line.line_total_rub,
            "note": note,
        }
        for line in quote.items
    ]
    return actions, quote.model_dump(mode="json")


def _calculated_cart_actions(db: Session, query: str) -> tuple[list[dict], dict | None]:
    """Build cart actions only from catalog services and server-side pricing."""
    segments = [
        part.strip()
        for part in SERVICE_SEGMENT_PATTERN.split(bounded_message(query))
        if part.strip()
    ]
    items: list[ItemIn] = []
    seen: set[int] = set()
    for segment in segments:
        quantity = _extract_area(segment)
        matches = search_services(db, segment)
        if quantity is None or not matches:
            continue
        service = matches[0]
        if service.id in seen or not Decimal("0.1") <= quantity <= Decimal("10000"):
            continue
        items.append(ItemIn(service_id=service.id, quantity=quantity))
        seen.add(service.id)
    if not items:
        return [], None
    quote = calculate_quote(db, items)
    note = _preference_note(query)
    actions = [
        {
            "action": "add_to_cart",
            "service_id": line.service_id,
            "name": line.name,
            "unit": line.unit,
            "quantity": line.quantity,
            "unit_price_rub": line.unit_price_rub,
            "line_total_rub": line.line_total_rub,
            "note": note,
        }
        for line in quote.items
    ]
    return actions, quote.model_dump(mode="json")


def _preference_note(text: str) -> str | None:
    colors = {
        "красн": "красный",
        "син": "синий",
        "зел": "зелёный",
        "бел": "белый",
        "черн": "чёрный",
        "чёрн": "чёрный",
        "сер": "серый",
        "беж": "бежевый",
        "желт": "жёлтый",
        "жёлт": "жёлтый",
    }
    lower = text.lower()
    for root, color in colors.items():
        if root in lower and ("цвет" in lower or "потол" in lower):
            return (
                f"Цвет: {color} — пожелание клиента; наличие материала и "
                "окончательная стоимость требуют уточнения."
            )
    return None


def _llm_cart_actions(db: Session, payload: ChatIn) -> tuple[list[dict], dict | None]:
    """Accept LLM service proposals only after strict catalog and price validation."""
    explicit_quantities = _allowed_action_quantities(payload)
    if not explicit_quantities:
        return [], None
    services = db.scalars(
        select(Service)
        .where(Service.is_active.is_(True))
        .order_by(Service.sort_order, Service.name)
    ).all()
    by_slug = {service.slug: service for service in services}
    catalog = "\n".join(
        f"- {service.slug}: {service.name} ({service.unit})" for service in services
    )
    recent_area_request = any(
        message.role == "assistant" and _assistant_requested_area(message.content)
        for message in payload.history[-2:]
    )
    safe_message = _llm_safe_text(
        payload.message, allow_contextual_numbers=recent_area_request
    )
    safe_history = [
        {
            "role": message.role,
            "content": _llm_safe_text(message.content),
        }
        for message in payload.history[-6:]
    ]
    try:
        raw = _call_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "Ты — машинный классификатор услуг. Верни только JSON вида "
                        '{"items":[{"service_slug":"slug","quantity":"25"}]}. '
                        "Выбирай только slug из каталога. Добавляй позицию только если "
                        "услуга однозначно следует из текущего сообщения или истории, а "
                        "количество явно указано пользователем либо подтверждено коротким "
                        "ответом на вопрос ассистента о той же площади. "
                        "Свяжи каждое число с правильной ранее выбранной услугой. Иначе "
                        "верни {\"items\":[]}. Не вычисляй цены.\n"
                        f"Каталог:\n{catalog}"
                    ),
                },
                *safe_history,
                {"role": "user", "content": safe_message},
            ],
            json_mode=True,
        )
        data = json.loads(raw)
    except Exception as exc:
        logger.info("LLM action proposal ignored: error=%s", type(exc).__name__)
        return [], None
    proposals = data.get("items") if isinstance(data, dict) else None
    if not isinstance(proposals, list) or len(proposals) > 5:
        return [], None
    items: list[ItemIn] = []
    seen: set[int] = set()
    for proposal in proposals:
        if not isinstance(proposal, dict):
            return [], None
        service = by_slug.get(proposal.get("service_slug"))
        try:
            quantity = Decimal(str(proposal.get("quantity")))
        except Exception:
            return [], None
        if (
            service is None
            or quantity not in explicit_quantities
            or service.id in seen
            or not Decimal("0.1") <= quantity <= Decimal("10000")
        ):
            return [], None
        items.append(ItemIn(service_id=service.id, quantity=quantity))
        seen.add(service.id)
    if not items:
        return [], None
    quote = calculate_quote(db, items)
    note = _preference_note(payload.message)
    actions = [
        {
            "action": "add_to_cart",
            "service_id": line.service_id,
            "name": line.name,
            "unit": line.unit,
            "quantity": line.quantity,
            "unit_price_rub": line.unit_price_rub,
            "line_total_rub": line.line_total_rub,
            "note": note,
        }
        for line in quote.items
    ]
    return actions, quote.model_dump(mode="json")


def _contextual_cart_actions(db: Session, payload: ChatIn) -> tuple[list[dict], dict | None]:
    if not payload.context_actions:
        return [], None
    if not payload.context_calculation_id or any(
        item.calculation_id != payload.context_calculation_id
        or item.conversation_id != payload.conversation_id
        for item in payload.context_actions
    ):
        logger.warning(
            "Rejected stale assistant context: conversation_id=%s",
            payload.conversation_id,
        )
        return [], None
    lower = payload.message.lower()
    preference = _preference_note(payload.message)
    new_quantity = _extract_area(payload.message)
    relevant = new_quantity is not None or preference or any(
        term in lower
        for term in (
            "корзин",
            "добав",
            "заказ",
            "оформ",
            "измени",
            "площад",
            "квадрат",
            "убери",
            "удали",
        )
    )
    if not relevant:
        return [], None
    if new_quantity is not None and len(payload.context_actions) != 1:
        return [], None
    items = [
        ItemIn(
            service_id=item.service_id,
            quantity=new_quantity if new_quantity is not None else item.quantity,
        )
        for item in payload.context_actions
    ]
    quote = calculate_quote(db, items)
    context_by_id = {item.service_id: item for item in payload.context_actions}
    cart_ids = {item.service_id for item in payload.cart}
    if any(term in lower for term in ("убери", "удали")):
        action_type = "remove_from_cart"
    elif any(term in lower for term in ("измени", "замени", "установи")):
        action_type = "set_cart_quantity"
    else:
        action_type = "add_to_cart"
    actions = []
    for line in quote.items:
        context = context_by_id[line.service_id]
        if line.unit != context.unit:
            continue
        operation = action_type
        if operation in ("remove_from_cart", "set_cart_quantity") and line.service_id not in cart_ids:
            operation = "add_to_cart"
        actions.append(
            {
                "action": operation,
                "service_id": line.service_id,
                "name": line.name,
                "unit": line.unit,
                "quantity": line.quantity,
                "unit_price_rub": line.unit_price_rub,
                "line_total_rub": line.line_total_rub,
                "note": preference or context.note,
            }
        )
    if not actions:
        return [], None
    return actions, quote.model_dump(mode="json")


def _version_actions(actions: list[dict], conversation_id: str) -> str | None:
    if not actions:
        return None
    calculation_id = secrets.token_urlsafe(12)
    for action in actions:
        action["calculation_id"] = calculation_id
        action["conversation_id"] = conversation_id
    return calculation_id


def _quote_markdown(actions: list[dict]) -> str:
    sections = []
    for action in actions:
        lines = [
            f"### {action['name']}",
            f"- Объём: **{action['quantity']:g} {action['unit']}**",
            f"- Цена за {action['unit']}: {action['unit_price_rub']:,.2f} ₽",
            f"- Предварительная стоимость: **{action['line_total_rub']:,.2f} ₽**",
        ]
        if action.get("note"):
            lines.append(f"- Пожелание: {action['note']}")
        sections.append("\n".join(lines).replace(",", " "))
    return "\n\n".join(sections) + "\n\n> Стоимость предварительная и уточняется после осмотра."


def demo_client_answer(db: Session, payload: ChatIn) -> dict:
    query = payload.message.strip()
    lower = query.lower()
    if payload.cart and ("что дальше" in lower or "перейти к оформ" in lower):
        return {
            "answer": "Услуга уже находится в корзине. Перейдите в корзину, проверьте объём и пожелания, затем нажмите **«Перейти к оформлению»**.",
            "mode": "demo",
            "sources": [{"type": "process", "title": "Оформление заявки"}],
            "suggestions": [],
            "quote": None,
            "cart_actions": [],
            "navigate_to": "/cart",
        }
    if payload.cart and any(term in lower for term in ("покажи корзин", "что в корзин")):
        quote = calculate_quote(
            db,
            [
                ItemIn(service_id=item.service_id, quantity=item.quantity)
                for item in payload.cart
            ],
        )
        lines = "\n".join(
            f"- **{line.name}** — {line.quantity:g} {line.unit}, {line.line_total_rub:,.2f} ₽"
            for line in quote.items
        ).replace(",", " ")
        return {
            "answer": f"### В корзине\n\n{lines}\n\n**Итого: {quote.estimated_total_rub:,.2f} ₽**".replace(",", " "),
            "mode": "demo",
            "sources": [{"type": "cart", "title": "Текущая корзина"}],
            "suggestions": [],
            "quote": quote.model_dump(mode="json"),
            "cart_actions": [],
            "navigate_to": "/cart",
        }
    if any(term in lower for term in ("заявк", "оформ")):
        return {
            "answer": "Выберите услуги, задайте объём, проверьте расчёт в корзине и заполните форму. Регистрация не нужна.",
            "mode": "demo",
            "sources": [{"type": "process", "title": "Порядок оформления"}],
            "suggestions": [],
            "quote": None,
            "cart_actions": [],
        }
    if any(term in lower for term in ("статус", "провер")):
        return {
            "answer": "Статус проверяется по номеру заявки и телефону в разделе «Проверить заявку».",
            "mode": "demo",
            "sources": [{"type": "faq", "title": "Проверка статуса"}],
            "suggestions": [],
            "quote": None,
            "cart_actions": [],
        }
    if any(
        term in lower
        for term in ("какие услуги", "что можно заказать", "что вы делаете")
    ):
        services = db.scalars(
            select(Service)
            .where(Service.is_active.is_(True))
            .order_by(Service.sort_order, Service.name)
        ).all()
        names = "\n".join(f"- {service.name}" for service in services)
        return {
            "answer": f"### Доступные услуги\n\n{names}\n\nНазовите услугу и площадь — я выполню предварительный расчёт.",
            "mode": "demo",
            "sources": [{"type": "catalog", "title": "Каталог услуг"}],
            "suggestions": [],
            "quote": None,
            "cart_actions": [],
        }
    # An explicitly named service starts a fresh calculation. Conversation
    # context is only used for genuine follow-ups such as "а если 75 м²".
    matches = search_services(db, query)
    contextual_actions, contextual_quote = (
        ([], None) if matches else _contextual_cart_actions(db, payload)
    )
    if contextual_actions:
        calculation_id = _version_actions(
            contextual_actions, payload.conversation_id
        )
        operation = contextual_actions[0]["action"]
        if operation == "remove_from_cart":
            answer = "Нашёл выбранную услугу в корзине. Подтвердите удаление кнопкой ниже."
        elif operation == "set_cart_quantity":
            answer = _quote_markdown(contextual_actions) + "\n\nПодтвердите изменение объёма кнопкой ниже."
        else:
            answer = _quote_markdown(contextual_actions) + "\n\nНажмите кнопку ниже — услуга будет добавлена в корзину «Стройкомплекса»."
        return {
            "answer": answer,
            "mode": "demo",
            "sources": [{"type": "conversation", "title": "Текущий расчёт"}],
            "suggestions": [],
            "quote": contextual_quote,
            "cart_actions": contextual_actions,
            "calculation_id": calculation_id,
        }
    if matches:
        service = matches[0]
        cart_actions, quote = _calculated_cart_actions(db, query)
        calculation_id = _version_actions(cart_actions, payload.conversation_id)
        answer = (
            _quote_markdown(cart_actions)
            if cart_actions
            else (
                f"### {service.name}\n\n{service.short_description}\n\n"
                f"Цена — **от {service.base_price_rub:,.0f} ₽/{service.unit}**. "
                f"Укажите объём в {service.unit}, чтобы получить расчёт и добавить услугу в корзину."
            ).replace(",", " ")
        )
        return {
            "answer": answer,
            "mode": "demo",
            "sources": [{"type": "service", "id": service.id, "title": service.name}],
            "suggestions": [],
            "quote": quote,
            "cart_actions": cart_actions,
            "calculation_id": calculation_id,
        }
    for question, answer in FAQ:
        if len(_words(query) & _words(question)) >= 2:
            return {
                "answer": answer,
                "mode": "demo",
                "sources": [{"type": "faq", "title": question}],
                "suggestions": [],
                "quote": None,
                "cart_actions": [],
            }
    return {
        "answer": "Я могу подобрать услугу, объяснить порядок оформления или рассчитать предварительную стоимость. Например: «Сколько стоит 20 м² механизированной штукатурки?»",
        "mode": "demo",
        "sources": [],
        "suggestions": [],
        "quote": None,
        "cart_actions": [],
    }


def client_answer(db: Session, payload: ChatIn) -> dict:
    settings = get_settings()
    selection = update_selection(db, payload)
    fallback = demo_client_answer(db, payload)
    fallback["selection"] = selection.selection
    if selection.actions:
        fallback["cart_actions"] = selection.actions
        fallback["quote"] = selection.quote
        fallback["calculation_id"] = selection.calculation_id
        fallback["answer"] = _quote_markdown(selection.actions)
        fallback["sources"] = [
            {"type": "catalog", "title": "Проверенный каталог услуг"}
        ]
    elif selection.selection["items"]:
        fallback["cart_actions"] = []
        fallback["quote"] = selection.quote
        fallback.pop("calculation_id", None)
        incomplete = [
            item
            for item in selection.selection["items"]
            if item["status"] == "incomplete"
        ]
        if incomplete:
            details = "; ".join(
                f"{item['name']}: {', '.join(item['missing_parameters'])}"
                for item in incomplete
            )
            fallback["answer"] = f"Для завершения расчёта уточните: {details}."
    elif not fallback.get("cart_actions") and not fallback.get("navigate_to"):
        proposed_actions, proposed_quote = _confirmed_history_cart_actions(db, payload)
        if not proposed_actions:
            proposed_actions, proposed_quote = _llm_cart_actions(db, payload)
        if proposed_actions:
            fallback["cart_actions"] = proposed_actions
            fallback["quote"] = proposed_quote
            fallback["calculation_id"] = _version_actions(
                proposed_actions, payload.conversation_id
            )
            fallback["answer"] = _quote_markdown(proposed_actions)
            fallback["sources"] = [
                {"type": "catalog", "title": "Проверенный каталог услуг"}
            ]
    if not _llm_configured():
        return fallback
    lower = payload.message.lower()
    if fallback.get("navigate_to") or (
        payload.context_actions
        and any(
            term in lower
            for term in (
                "корзин",
                "что дальше",
                "оформ",
                "добав",
                "измени",
                "замени",
                "установи",
                "убери",
                "удали",
            )
        )
    ):
        return fallback
    catalog = db.scalars(
        select(Service)
        .where(Service.is_active.is_(True))
        .order_by(Service.sort_order, Service.name)
    ).all()
    context = "Доступный каталог (это полный список услуг):\n" + "\n".join(
        f"- {service.name}: {service.base_price_rub} ₽/{service.unit}. "
        f"{service.short_description}"
        for service in catalog
    )
    relevant_faq = [
        (question, answer)
        for question, answer in FAQ
        if _words(question) & _words(payload.message)
    ][:3]
    if relevant_faq:
        context += "\n\nПодходящие ответы FAQ:\n" + "\n".join(
            f"- {question}: {answer}" for question, answer in relevant_faq
        )
    if fallback.get("cart_actions"):
        context += "\n\nПроверенный сервером расчёт:\n" + "\n".join(
            f"- {item['name']}: {item['quantity']} {item['unit']} × "
            f"{item['unit_price_rub']} ₽ = {item['line_total_rub']} ₽; "
            f"пожелание: {item.get('note') or 'нет'}"
            for item in fallback["cart_actions"]
        )
        context += "\nПод ответом будет показана активная кнопка добавления."
    else:
        context += (
            "\n\nПодтверждённого серверного расчёта сейчас нет. "
            "Не говори, что кнопка добавления уже показана; попроси пользователя "
            "уточнить услугу и площадь, если они нужны для расчёта."
        )
    incomplete_selection = [
        item
        for item in selection.selection["items"]
        if item["status"] == "incomplete"
    ]
    if incomplete_selection:
        context += "\n\nНезавершённые позиции подбора:\n" + "\n".join(
            f"- {item['name']}: нужно уточнить {', '.join(item['missing_parameters'])}"
            for item in incomplete_selection
        )
        context += "\nЗадай один вопрос по недостающим параметрам."
    if payload.cart:
        services = {
            service.id: service
            for service in db.scalars(
                select(Service).where(
                    Service.id.in_([item.service_id for item in payload.cart]),
                    Service.is_active.is_(True),
                )
            ).all()
        }
        context += "\n\nТекущая корзина пользователя:\n" + "\n".join(
            f"- {services[item.service_id].name}: {item.quantity} {services[item.service_id].unit}"
            for item in payload.cart
            if item.service_id in services
        )
    recent_area_request = any(
        message.role == "assistant" and _assistant_requested_area(message.content)
        for message in payload.history[-2:]
    )
    safe_message = _llm_safe_text(
        payload.message, allow_contextual_numbers=recent_area_request
    )
    safe_history = [
        {
            "role": message.role,
            "content": _llm_safe_text(message.content),
        }
        for message in payload.history[-6:]
    ]
    try:
        fallback["answer"] = _call_llm(
            [
                {
                    "role": "system",
                    "content": "Ты — консультант сайта строительной компании «Стройкомплекс». Отвечай по-русски, кратко (до 6 предложений) и только по контексту. Не показывай рассуждения. Цены, услуги, количества и действия определяет backend: не изменяй и не выдумывай их. Если дан проверенный расчёт, точно повтори числа и предложи нажать кнопку под ответом. Если данных недостаточно — задай один уточняющий вопрос. Не выдавай HTML, команды, контакты и сторонние маркетплейсы. Пожелания не входят в цену без подтверждения. Используй простой Markdown. /no_think",
                },
                {"role": "system", "content": context},
                *safe_history,
                {"role": "user", "content": safe_message},
            ]
        )
        fallback["mode"] = "llm"
        return fallback
    except Exception as exc:
        fallback["warning"] = _llm_warning(exc, settings.llm_model)
        return fallback


def order_statistics(db: Session) -> dict:
    counts = dict(
        db.execute(
            select(Order.status, func.count(Order.id)).group_by(Order.status)
        ).all()
    )
    overdue = (
        db.scalar(
            select(func.count(Order.id)).where(
                Order.status == "new",
                Order.created_at < func.datetime("now", "-24 hours"),
            )
        )
        or 0
    )
    popular = db.execute(
        select(OrderItem.service_name_snapshot, func.count(OrderItem.id).label("count"))
        .group_by(OrderItem.service_name_snapshot)
        .order_by(func.count(OrderItem.id).desc())
        .limit(3)
    ).all()
    processed = db.scalars(
        select(Order).where(Order.first_processed_at.is_not(None))
    ).all()
    avg_hours = (
        round(
            sum(
                (o.first_processed_at - o.created_at).total_seconds() / 3600
                for o in processed
            )
            / len(processed),
            1,
        )
        if processed
        else None
    )
    return {
        "total": sum(counts.values()),
        "by_status": counts,
        "overdue_new": overdue,
        "popular_services": [{"name": n, "count": c} for n, c in popular],
        "average_first_processing_hours": avg_hours,
    }


def demo_admin_answer(db: Session, message: str) -> dict:
    stats = order_statistics(db)
    popular = (
        ", ".join(f"{x['name']} ({x['count']})" for x in stats["popular_services"])
        or "данных пока нет"
    )
    answer = f"Всего заявок: {stats['total']}. Новых: {stats['by_status'].get('new', 0)}; в работе: {stats['by_status'].get('in_progress', 0)}; завершённых: {stats['by_status'].get('completed', 0)}. Новых старше 24 часов: {stats['overdue_new']}. Популярные услуги: {popular}."
    if stats["overdue_new"]:
        answer += (
            " Рекомендуется начать с заявок, ожидающих первичной обработки более суток."
        )
    return {"answer": answer, "mode": "demo", "statistics": stats}


def admin_answer(db: Session, message: str) -> dict:
    settings = get_settings()
    fallback = demo_admin_answer(db, message)
    if not _llm_configured():
        return fallback
    stats = fallback["statistics"]
    safe_message = _llm_safe_text(message)
    context = (
        f"Всего заявок: {stats['total']}; по статусам: {stats['by_status']}; "
        f"новых старше 24 часов: {stats['overdue_new']}; "
        f"популярные услуги: {stats['popular_services']}; "
        f"среднее время первичной обработки: {stats['average_first_processing_hours']} ч."
    )
    try:
        fallback["answer"] = _call_llm(
            [
                {
                    "role": "system",
                    "content": "Ты — read-only помощник администратора ООО «Стройкомплекс». Отвечай по-русски, кратко и только по агрегированной статистике из контекста. Не показывай рассуждения. Не придумывай заявки, персональные данные или действия и не предлагай менять данные напрямую. /no_think",
                },
                {"role": "system", "content": context},
                {"role": "user", "content": safe_message},
            ]
        )
        fallback["mode"] = "llm"
        return fallback
    except Exception as exc:
        fallback["warning"] = _llm_warning(exc, settings.llm_model)
        return fallback
