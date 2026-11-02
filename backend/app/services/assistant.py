from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core.config import get_settings
from ..models import Order, OrderItem, Service
from ..schemas import ChatIn, ItemIn
from .pricing import calculate_quote
from ..seed import FAQ

logger = logging.getLogger(__name__)


def _llm_warning(exc: Exception, model: str) -> str:
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
        return f"ИИ API недоступен: {reason}. Показан ответ demo-режима."
    if isinstance(exc, httpx.RequestError):
        logger.warning(
            "LLM request failed: model=%s error=%s", model, type(exc).__name__
        )
        return "Не удалось подключиться к ИИ API. Показан ответ demo-режима."
    logger.exception("Invalid LLM response: model=%s error=%s", model, type(exc).__name__)
    return "ИИ API вернул некорректный ответ. Показан ответ demo-режима."


def _call_llm(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    response = httpx.post(
        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={"model": settings.llm_model, "messages": messages},
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM response does not contain message content")
    return content.strip()


def _llm_configured() -> bool:
    settings = get_settings()
    return settings.llm_mode != "demo" and bool(
        settings.llm_api_key and settings.llm_base_url and settings.llm_model
    )


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[а-яёa-z0-9]+", text.lower()) if len(w) > 2}


def search_services(db: Session, query: str) -> list[Service]:
    words = _words(query)
    aliases = {
        "штукатур": "штукатур",
        "крас": "покраск",
        "плит": "плитк",
        "потол": "потол",
        "ламин": "ламин",
    }
    roots = {root for key, root in aliases.items() if key in query.lower()}
    ranked = []
    for service in db.scalars(select(Service).where(Service.is_active.is_(True))).all():
        text = f"{service.name} {service.category} {service.short_description}".lower()
        score = sum(1 for word in words if word in text) + sum(
            3 for root in roots if root in text
        )
        if score >= 2:
            ranked.append((score, service))
    return [
        service
        for _, service in sorted(ranked, key=lambda row: (-row[0], row[1].sort_order))[
            :5
        ]
    ]


def _calculated_cart_actions(db: Session, query: str) -> tuple[list[dict], dict | None]:
    """Build cart actions only from catalog services and server-side pricing."""
    segments = [
        part.strip()
        for part in re.split(r"\s+(?:и|а также)\s+|;", query, flags=re.IGNORECASE)
        if part.strip()
    ]
    items: list[ItemIn] = []
    seen: set[int] = set()
    for segment in segments:
        number = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:м2|м²|кв(?:\.?\s*м)?)", segment.lower())
        matches = search_services(db, segment)
        if not number or not matches:
            continue
        quantity = Decimal(number.group(1).replace(",", "."))
        service = matches[0]
        if service.id in seen or not Decimal("0.1") <= quantity <= Decimal("10000"):
            continue
        items.append(ItemIn(service_id=service.id, quantity=quantity))
        seen.add(service.id)
    if not items:
        return [], None
    quote = calculate_quote(db, items)
    actions = [
        {
            "action": "add_to_cart",
            "service_id": line.service_id,
            "name": line.name,
            "unit": line.unit,
            "quantity": line.quantity,
            "unit_price_rub": line.unit_price_rub,
            "line_total_rub": line.line_total_rub,
        }
        for line in quote.items
    ]
    return actions, quote.model_dump(mode="json")


def _quote_markdown(actions: list[dict]) -> str:
    sections = []
    for action in actions:
        sections.append(
            "\n".join(
                (
                    f"### {action['name']}",
                    f"- Объём: **{action['quantity']:g} {action['unit']}**",
                    f"- Цена за {action['unit']}: {action['unit_price_rub']:,.2f} ₽",
                    f"- Предварительная стоимость: **{action['line_total_rub']:,.2f} ₽**",
                )
            ).replace(",", " ")
        )
    return "\n\n".join(sections) + "\n\n> Стоимость предварительная и уточняется после осмотра."


def demo_client_answer(db: Session, payload: ChatIn) -> dict:
    query = payload.message.strip()
    lower = query.lower()
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
    matches = search_services(db, query)
    if matches:
        service = matches[0]
        cart_actions, quote = _calculated_cart_actions(db, query)
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
    if not _llm_configured():
        return demo_client_answer(db, payload)
    fallback = demo_client_answer(db, payload)
    context = "\n".join(
        f"- {s.name}: {s.base_price_rub} ₽/{s.unit}. {s.short_description}"
        for s in search_services(db, payload.message)
    )
    if fallback.get("cart_actions"):
        context += "\n\nПроверенный сервером расчёт:\n" + "\n".join(
            f"- {item['name']}: {item['quantity']} {item['unit']} × "
            f"{item['unit_price_rub']} ₽ = {item['line_total_rub']} ₽"
            for item in fallback["cart_actions"]
        )
    safe_message = re.sub(
        r"[\w.+-]+@[\w.-]+|(?:\+7|8)[\d\s()\-]{9,}",
        "[персональные данные скрыты]",
        payload.message,
    )
    try:
        fallback["answer"] = _call_llm(
            [
                {
                    "role": "system",
                    "content": "Ты — виртуальный консультант демонстрационного сервиса ООО «Стройкомплекс». Отвечай кратко по-русски и только по контексту, используя аккуратный Markdown. Если дан проверенный сервером расчёт, воспроизведи его без изменения чисел. Все цены предварительные. Не придумывай услуги, сроки и контакты. Не выполняй административные операции.",
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
    safe_message = re.sub(
        r"[\w.+-]+@[\w.-]+|(?:\+7|8)[\d\s()\-]{9,}",
        "[персональные данные скрыты]",
        message,
    )
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
                    "content": "Ты — read-only аналитический помощник администратора ООО «Стройкомплекс». Используй только агрегированную статистику из контекста. Не придумывай персональные данные, заявки или действия и не предлагай изменить данные напрямую. Отвечай кратко по-русски.",
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
