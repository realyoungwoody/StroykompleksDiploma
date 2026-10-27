import logging
import re
from decimal import Decimal
import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core.config import get_settings
from ..models import Order, OrderItem, Service
from ..schemas import ChatIn, ItemIn
from .pricing import calculate_quote
from ..seed import FAQ

logger = logging.getLogger(__name__)


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
        if score:
            ranked.append((score, service))
    return [
        service
        for _, service in sorted(ranked, key=lambda row: (-row[0], row[1].sort_order))[
            :5
        ]
    ]


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
        }
    if any(term in lower for term in ("статус", "провер")):
        return {
            "answer": "Статус проверяется по номеру заявки и телефону в разделе «Проверить заявку».",
            "mode": "demo",
            "sources": [{"type": "faq", "title": "Проверка статуса"}],
            "suggestions": [],
            "quote": None,
        }
    matches = search_services(db, query)
    if matches:
        service = matches[0]
        number = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:м2|м²|кв)", lower)
        quote = None
        quote_text = ""
        if number:
            quantity = Decimal(number.group(1).replace(",", "."))
            if Decimal("0.1") <= quantity <= Decimal("10000"):
                calculation = calculate_quote(
                    db, [ItemIn(service_id=service.id, quantity=quantity)]
                )
                quote = calculation.model_dump(mode="json")
                quote_text = f" Для {quantity:g} {service.unit} ориентировочная стоимость — {calculation.estimated_total_rub:,.2f} ₽.".replace(
                    ",", " "
                )
        answer = f"Подойдёт услуга «{service.name}»: {service.short_description} Цена — от {service.base_price_rub:,.0f} ₽/{service.unit}.{quote_text}".replace(
            ",", " "
        )
        return {
            "answer": answer,
            "mode": "demo",
            "sources": [{"type": "service", "id": service.id, "title": service.name}],
            "suggestions": [
                {"service_id": s.id, "label": f"Добавить: {s.name}"}
                for s in matches[:3]
            ],
            "quote": quote,
        }
    for question, answer in FAQ:
        if len(_words(query) & _words(question)) >= 2:
            return {
                "answer": answer,
                "mode": "demo",
                "sources": [{"type": "faq", "title": question}],
                "suggestions": [],
                "quote": None,
            }
    return {
        "answer": "Я могу подобрать услугу, объяснить порядок оформления или рассчитать предварительную стоимость. Например: «Сколько стоит 20 м² механизированной штукатурки?»",
        "mode": "demo",
        "sources": [],
        "suggestions": [],
        "quote": None,
    }


def client_answer(db: Session, payload: ChatIn) -> dict:
    settings = get_settings()
    if settings.llm_mode == "demo" or not (
        settings.llm_api_key and settings.llm_base_url and settings.llm_model
    ):
        return demo_client_answer(db, payload)
    fallback = demo_client_answer(db, payload)
    context = "\n".join(
        f"- {s.name}: {s.base_price_rub} ₽/{s.unit}. {s.short_description}"
        for s in search_services(db, payload.message)
    )
    safe_message = re.sub(
        r"[\w.+-]+@[\w.-]+|(?:\+7|8)[\d\s()\-]{9,}",
        "[персональные данные скрыты]",
        payload.message,
    )
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.llm_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты — виртуальный консультант демонстрационного сервиса ООО «Стройкомплекс». Отвечай кратко по-русски и только по контексту. Все цены предварительные. Не придумывай услуги, сроки и контакты. Не выполняй административные операции.",
                    },
                    {"role": "system", "content": context},
                    {"role": "user", "content": safe_message},
                ],
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        fallback["answer"] = response.json()["choices"][0]["message"]["content"]
        fallback["mode"] = "llm"
        return fallback
    except Exception as exc:
        logger.warning("LLM unavailable, using demo mode: %s", type(exc).__name__)
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
