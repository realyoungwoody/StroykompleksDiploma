from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Service
from ..schemas import ItemIn, QuoteLine, QuoteOut

MONEY = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_quote(
    db: Session, items: list[ItemIn], require_active: bool = True
) -> QuoteOut:
    if not items:
        raise HTTPException(422, "Корзина не должна быть пустой")
    ids = [item.service_id for item in items]
    services = {
        s.id: s for s in db.scalars(select(Service).where(Service.id.in_(ids))).all()
    }
    lines: list[QuoteLine] = []
    for item in items:
        service = services.get(item.service_id)
        if service is None:
            raise HTTPException(422, f"Услуга {item.service_id} не найдена")
        if require_active and not service.is_active:
            raise HTTPException(409, f"Услуга «{service.name}» временно недоступна")
        quantity = Decimal(item.quantity).quantize(MONEY)
        price = money(Decimal(service.base_price_rub))
        lines.append(
            QuoteLine(
                service_id=service.id,
                name=service.name,
                unit=service.unit,
                quantity=quantity,
                unit_price_rub=price,
                line_total_rub=money(quantity * price),
            )
        )
    return QuoteOut(
        items=lines,
        estimated_total_rub=money(
            sum((line.line_total_rub for line in lines), Decimal("0"))
        ),
    )
