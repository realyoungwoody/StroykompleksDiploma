from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Service
from ..schemas import ChatIn, ItemIn
from .pricing import calculate_quote
from .quantities import bounded_message, extract_area_quantities

logger = logging.getLogger(__name__)

KIND_CANDIDATES: dict[str, tuple[str, ...]] = {
    "plaster": ("mekhanizirovannaya-shtukaturka", "ruchnaya-shtukaturka"),
    "painting": ("pokraska-vodoemulsionnaya", "pokraska-maslyanaya"),
    "tile": ("nastennaya-plitka", "napolnaya-plitka"),
    "ceiling": ("natyazhnoy-potolok",),
    "laminate": ("laminat",),
}
KIND_LABELS = {
    "plaster": "Штукатурка стен",
    "painting": "Покраска стен",
    "tile": "Укладка плитки",
    "ceiling": "Монтаж натяжного потолка",
    "laminate": "Укладка ламината",
}
KIND_PATTERNS = {
    "plaster": r"штукатур|оштукатур",
    "painting": r"покрас|окрас|краск",
    "tile": r"плит|облицов",
    "ceiling": r"потол",
    "laminate": r"ламин",
}
SLUG_PATTERNS = {
    "mekhanizirovannaya-shtukaturka": r"механиз",
    "ruchnaya-shtukaturka": r"ручн\w*(?:ая|ую|ой)?(?:\s+штукатур)?",
    "pokraska-vodoemulsionnaya": r"водоэмульс",
    "pokraska-maslyanaya": r"маслян",
    "nastennaya-plitka": r"настенн\w*\s+плит|плит\w*\s+(?:на\s+)?стен",
    "napolnaya-plitka": r"напольн\w*\s+плит|плит\w*\s+(?:на\s+)?пол",
    "natyazhnoy-potolok": r"натяжн\w*(?:\s+потол)?",
    "laminat": r"ламин",
}
SLUG_KIND = {
    slug: kind for kind, slugs in KIND_CANDIDATES.items() for slug in slugs
}
@dataclass
class SelectionResult:
    selection: dict
    actions: list[dict]
    quote: dict | None
    calculation_id: str | None
    diagnostics: list[str]


def _quantities(text: str) -> list[Decimal]:
    return extract_area_quantities(text, selection_units=True, include_words=True)


def _mentioned_kinds(text: str) -> set[str]:
    normalized = text.lower()
    kinds = {
        kind for kind, pattern in KIND_PATTERNS.items() if re.search(pattern, normalized)
    }
    kinds.update(SLUG_KIND[slug] for slug in _explicit_slugs(text))
    return kinds


def _explicit_slugs(text: str) -> set[str]:
    normalized = text.lower()
    return {
        slug for slug, pattern in SLUG_PATTERNS.items() if re.search(pattern, normalized)
    }


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
        if root in lower:
            return (
                f"Цвет: {color} — пожелание клиента; наличие материала и "
                "окончательная стоимость требуют уточнения."
            )
    return None


def _new_item(kind: str) -> dict:
    candidates = KIND_CANDIDATES[kind]
    return {
        "selection_item_id": f"sel-{secrets.token_urlsafe(8)}",
        "kind": kind,
        "service_id": None,
        "quantity": None,
        "note": None,
        "added": False,
        "candidate_slugs": list(candidates),
    }


def _restore_items(db: Session, payload: ChatIn) -> tuple[list[dict], list[str]]:
    if payload.selection is None:
        return [], []
    if payload.selection.conversation_id != payload.conversation_id:
        logger.info("Selection rejected: code=STALE_SELECTION")
        return [], ["STALE_SELECTION"]
    active = {
        service.id: service
        for service in db.scalars(select(Service).where(Service.is_active.is_(True))).all()
    }
    restored = []
    for source in payload.selection.items:
        candidates = KIND_CANDIDATES[source.kind]
        service = active.get(source.service_id) if source.service_id else None
        service_id = (
            service.id if service is not None and service.slug in candidates else None
        )
        restored.append(
            {
                "selection_item_id": source.selection_item_id,
                "kind": source.kind,
                "service_id": service_id,
                "quantity": source.quantity,
                "note": source.note,
                "added": source.added,
                "candidate_slugs": list(candidates),
            }
        )
    return restored, []


def _find_or_create(items: list[dict], kind: str, service_id: int | None = None) -> dict:
    if service_id is not None:
        for item in items:
            if item["service_id"] == service_id:
                return item
    for item in reversed(items):
        if item["kind"] == kind and (
            item["service_id"] is None or service_id is None
        ):
            return item
    item = _new_item(kind)
    items.append(item)
    return item


def _clauses(text: str) -> list[str]:
    service_start = r"(?:штукатур|покрас|окрас|краск|плит|облицов|потол|ламин|механиз|ручн|водоэмульс|маслян|натяжн)"
    return [
        part.strip()
        for part in re.split(
            rf"[,;]|\s{{1,16}}и\s{{1,16}}(?={service_start})",
            bounded_message(text).lower(),
        )
        if part.strip()
    ]


def _apply_message(db: Session, items: list[dict], text: str) -> list[str]:
    diagnostics: list[str] = []
    normalized = text.lower()
    mentioned = _mentioned_kinds(text)
    explicit = _explicit_slugs(text)
    services = {
        service.slug: service
        for service in db.scalars(select(Service).where(Service.is_active.is_(True))).all()
    }

    if any(term in normalized for term in ("отмени", "убери", "удали", "не нужна", "не нужен")):
        before = len(items)
        items[:] = [item for item in items if item["kind"] not in mentioned]
        if len(items) != before:
            diagnostics.append("SELECTION_REMOVED")
        return diagnostics

    targets_by_kind: dict[str, list[dict]] = {}
    for slug in explicit:
        service = services.get(slug)
        if service is None:
            diagnostics.append("SERVICE_NOT_IDENTIFIED")
            continue
        kind = SLUG_KIND[slug]
        item = _find_or_create(items, kind, service.id)
        item["service_id"] = service.id
        item["added"] = False
        targets_by_kind.setdefault(kind, []).append(item)
    for kind in mentioned - {SLUG_KIND[slug] for slug in explicit}:
        candidates = KIND_CANDIDATES[kind]
        item = _find_or_create(items, kind)
        if len(candidates) == 1:
            service = services.get(candidates[0])
            item["service_id"] = service.id if service else None
        targets_by_kind.setdefault(kind, []).append(item)

    assigned = False
    for clause in _clauses(text):
        quantities = _quantities(clause)
        if len(quantities) != 1:
            continue
        clause_kinds = _mentioned_kinds(clause)
        if not clause_kinds:
            continue
        for kind in clause_kinds:
            targets = targets_by_kind.get(kind) or [
                item for item in items if item["kind"] == kind
            ][-1:]
            for item in targets:
                item["quantity"] = quantities[0]
                item["added"] = False
                assigned = True

    quantities = _quantities(text)
    if not assigned and len(quantities) == 1:
        targets = [item for values in targets_by_kind.values() for item in values]
        if targets:
            for item in targets:
                item["quantity"] = quantities[0]
                item["added"] = False
            assigned = True
        else:
            missing = [item for item in items if item["quantity"] is None]
            if len(missing) == 1:
                missing[0]["quantity"] = quantities[0]
                missing[0]["added"] = False
                assigned = True
            elif len(items) == 1 and any(
                term in normalized for term in ("нет", "точно", "вместо", "измени")
            ):
                items[0]["quantity"] = quantities[0]
                items[0]["added"] = False
                assigned = True
            elif len(missing) > 1:
                diagnostics.append("AMBIGUOUS_SELECTION")

    note = _preference_note(text)
    if note:
        note_targets = targets_by_kind.get("ceiling") or (
            [items[-1]] if len(items) == 1 else []
        )
        for item in note_targets:
            item["note"] = note
            item["added"] = False

    if mentioned and not explicit and any(
        len(KIND_CANDIDATES[kind]) > 1 for kind in mentioned
    ):
        diagnostics.append("SERVICE_NOT_IDENTIFIED")
    if quantities and not assigned:
        diagnostics.append("AMBIGUOUS_SELECTION")
    return diagnostics


def update_selection(db: Session, payload: ChatIn) -> SelectionResult:
    items, diagnostics = _restore_items(db, payload)
    diagnostics.extend(_apply_message(db, items, payload.message))
    revision = (payload.selection.revision if payload.selection else 0) + 1
    active = {
        service.id: service
        for service in db.scalars(
            select(Service).where(Service.is_active.is_(True))
        ).all()
    }
    cart = {item.service_id: item for item in payload.cart}
    ready_inputs = []
    ready_items = []
    for item in items:
        missing = []
        service = active.get(item["service_id"])
        if service is None:
            missing.append("вариант услуги")
        if item["quantity"] is None:
            missing.append("площадь")
        elif not Decimal("0.1") <= item["quantity"] <= Decimal("10000"):
            missing.append("корректная площадь")
        item["missing_parameters"] = missing
        item["name"] = service.name if service else KIND_LABELS[item["kind"]]
        item["unit"] = service.unit if service else "м²"
        if missing:
            item["status"] = "incomplete"
            item["can_add_to_cart"] = False
            diagnostics.append(
                "SERVICE_NOT_IDENTIFIED" if service is None else "QUANTITY_MISSING"
            )
            continue
        ready_inputs.append(ItemIn(service_id=service.id, quantity=item["quantity"]))
        ready_items.append(item)

    actions: list[dict] = []
    quote_dict = None
    calculation_id = None
    if ready_inputs:
        try:
            quote = calculate_quote(db, ready_inputs)
            quote_dict = quote.model_dump(mode="json")
            calculation_id = f"sel-{revision}-{secrets.token_urlsafe(8)}"
            for item, line in zip(ready_items, quote.items):
                item["unit_price_rub"] = line.unit_price_rub
                item["line_total_rub"] = line.line_total_rub
                item["quote_id"] = calculation_id
                cart_item = cart.get(line.service_id)
                already_added = bool(
                    cart_item is not None and cart_item.quantity == line.quantity
                )
                item["status"] = "added" if already_added else "ready"
                item["added"] = already_added
                item["can_add_to_cart"] = not already_added
                if already_added:
                    continue
                actions.append(
                    {
                        "action": (
                            "set_cart_quantity"
                            if cart_item is not None
                            else "add_to_cart"
                        ),
                        "service_id": line.service_id,
                        "name": line.name,
                        "unit": line.unit,
                        "quantity": line.quantity,
                        "unit_price_rub": line.unit_price_rub,
                        "line_total_rub": line.line_total_rub,
                        "note": item["note"],
                        "calculation_id": calculation_id,
                        "conversation_id": payload.conversation_id,
                        "selection_item_id": item["selection_item_id"],
                        "selection_revision": revision,
                    }
                )
            if actions:
                diagnostics.append("ACTION_READY")
        except Exception:
            logger.exception("Selection quote failed: code=QUOTE_FAILED")
            diagnostics.append("QUOTE_FAILED")
            for item in ready_items:
                item["status"] = "invalid"
                item["can_add_to_cart"] = False

    state = {
        "conversation_id": payload.conversation_id,
        "revision": revision,
        "items": items,
        "diagnostics": list(dict.fromkeys(diagnostics)),
    }
    logger.info(
        "Selection transition: conversation_id=%s revision=%s items=%s codes=%s",
        payload.conversation_id,
        revision,
        len(items),
        ",".join(state["diagnostics"]) or "NO_CHANGE",
    )
    return SelectionResult(
        selection=state,
        actions=actions,
        quote=quote_dict,
        calculation_id=calculation_id,
        diagnostics=state["diagnostics"],
    )
