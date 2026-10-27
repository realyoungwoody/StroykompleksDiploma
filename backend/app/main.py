from __future__ import annotations

import hashlib
import json
import secrets
import string
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from .core.config import get_settings
from .core.database import Base, SessionLocal, engine, get_db
from .core.security import (
    get_admin_id,
    make_session,
    normalize_phone,
    rate_limiter,
    verify_origin,
    verify_password,
)
from .models import AdminUser, Order, OrderItem, OrderStatusHistory, Service
from .schemas import (
    AdminLogin,
    ChatIn,
    OrderCreate,
    OrderCreated,
    OrderPatch,
    QuoteIn,
    QuoteOut,
    ServiceOut,
    ServicePatch,
    ServiceWrite,
    TrackIn,
    TrackOut,
)
from .seed import FAQ, seed_database
from .services.assistant import client_answer, demo_admin_answer, order_statistics
from .services.pricing import calculate_quote

settings = get_settings()
app = FastAPI(
    title="Стройкомплекс API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse(
        {"error": {"code": exc.status_code, "message": exc.detail}},
        status_code=exc.status_code,
    )


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_database(db)


def require_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    admin = db.get(AdminUser, get_admin_id(request))
    if admin is None or not admin.is_active:
        raise HTTPException(401, "Требуется вход администратора")
    return admin


def order_created(order: Order) -> OrderCreated:
    return OrderCreated(
        public_number=order.public_number,
        status=order.status,
        estimated_total_rub=order.estimated_total_rub,
        created_at=order.created_at,
    )


def order_dict(order: Order, include_private: bool = True) -> dict:
    data = {
        "id": order.id,
        "public_number": order.public_number,
        "customer_name": order.customer_name,
        "phone": order.phone_normalized,
        "email": order.email,
        "object_location": order.object_location,
        "desired_date": order.desired_date,
        "comment": order.comment,
        "status": order.status,
        "estimated_total_rub": order.estimated_total_rub,
        "admin_note": order.admin_note,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "first_processed_at": order.first_processed_at,
        "items": order.items,
        "history": order.history,
    }
    if not include_private:
        for key in (
            "id",
            "customer_name",
            "phone",
            "email",
            "object_location",
            "desired_date",
            "comment",
            "admin_note",
            "first_processed_at",
            "history",
        ):
            data.pop(key, None)
    return data


@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "connected", "ai_mode": settings.llm_mode}


@app.get("/api/v1/services", response_model=list[ServiceOut])
def services(db: Session = Depends(get_db)):
    return db.scalars(
        select(Service)
        .where(Service.is_active.is_(True))
        .order_by(Service.sort_order, Service.name)
    ).all()


@app.get("/api/v1/services/{slug}", response_model=ServiceOut)
def service_detail(slug: str, db: Session = Depends(get_db)):
    service = db.scalar(
        select(Service).where(Service.slug == slug, Service.is_active.is_(True))
    )
    if service is None:
        raise HTTPException(404, "Услуга не найдена")
    return service


@app.get("/api/v1/faq")
def faq():
    return [{"question": q, "answer": a} for q, a in FAQ]


@app.post("/api/v1/quotes", response_model=QuoteOut)
def quote(payload: QuoteIn, db: Session = Depends(get_db)):
    return calculate_quote(db, payload.items)


@app.post("/api/v1/orders", response_model=OrderCreated)
def create_order(
    response: Response,
    payload: OrderCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key and len(idempotency_key) > 64:
        raise HTTPException(422, "Некорректный ключ идемпотентности")
    canonical = payload.model_dump(mode="json")
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    if idempotency_key:
        previous = db.scalar(
            select(Order).where(Order.idempotency_key == idempotency_key)
        )
        if previous:
            if previous.request_fingerprint != fingerprint:
                raise HTTPException(
                    409, "Ключ идемпотентности уже использован с другими данными"
                )
            response.status_code = status.HTTP_200_OK
            return order_created(previous)
    try:
        phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    calculation = calculate_quote(db, payload.items)
    alphabet = string.ascii_uppercase + string.digits
    public_number = ""
    while not public_number or db.scalar(
        select(Order.id).where(Order.public_number == public_number)
    ):
        public_number = "SC-" + "".join(secrets.choice(alphabet) for _ in range(10))
    order = Order(
        public_number=public_number,
        customer_name=payload.customer_name,
        phone_normalized=phone,
        email=str(payload.email) if payload.email else None,
        object_location=payload.object_location,
        desired_date=payload.desired_date,
        comment=payload.comment,
        status="new",
        estimated_total_rub=calculation.estimated_total_rub,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        is_demo=True,
    )
    for line in calculation.items:
        order.items.append(
            OrderItem(
                service_id=line.service_id,
                service_name_snapshot=line.name,
                unit_snapshot=line.unit,
                quantity=line.quantity,
                unit_price_snapshot=line.unit_price_rub,
                line_total_rub=line.line_total_rub,
            )
        )
    order.history.append(OrderStatusHistory(old_status=None, new_status="new"))
    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Конфликт при создании заявки")
    db.refresh(order)
    response.status_code = status.HTTP_201_CREATED
    return order_created(order)


@app.post("/api/v1/orders/track", response_model=TrackOut)
def track(payload: TrackIn, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check(
        f"track:{request.client.host if request.client else 'unknown'}", 30, 60
    )
    try:
        phone = normalize_phone(payload.phone)
    except ValueError:
        raise HTTPException(404, "Не удалось найти заявку по указанным данным")
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.public_number == payload.public_number,
            Order.phone_normalized == phone,
        )
    )
    if order is None:
        raise HTTPException(404, "Не удалось найти заявку по указанным данным")
    return order_dict(order, include_private=False)


@app.post("/api/v1/assistant/chat")
def assistant_chat(payload: ChatIn, db: Session = Depends(get_db)):
    return client_answer(db, payload)


@app.post("/api/v1/admin/auth/login")
def login(
    payload: AdminLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    rate_limiter.check(
        f"login:{request.client.host if request.client else 'unknown'}", 10, 300
    )
    admin = db.scalar(
        select(AdminUser).where(AdminUser.email == str(payload.email).lower())
    )
    if (
        admin is None
        or not admin.is_active
        or not verify_password(admin.password_hash, payload.password)
    ):
        raise HTTPException(401, "Неверный email или пароль")
    response.set_cookie(
        "admin_session",
        make_session(admin.id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=12 * 3600,
        path="/",
    )
    return {"id": admin.id, "email": admin.email}


@app.post("/api/v1/admin/auth/logout")
def logout(request: Request, response: Response, _: AdminUser = Depends(require_admin)):
    verify_origin(request)
    response.delete_cookie("admin_session", path="/")
    return {"ok": True}


@app.get("/api/v1/admin/auth/me")
def me(admin: AdminUser = Depends(require_admin)):
    return {"id": admin.id, "email": admin.email}


@app.get("/api/v1/admin/orders")
def admin_orders(
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    search: str | None = None,
    sort: str = "desc",
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    stmt = select(Order)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Order.public_number.ilike(term),
                Order.customer_name.ilike(term),
                Order.phone_normalized.ilike(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    direction = Order.created_at.asc() if sort == "asc" else Order.created_at.desc()
    orders = db.scalars(
        stmt.order_by(direction).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [order_dict(o) for o in orders],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/api/v1/admin/orders/{order_id}")
def admin_order(
    order_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)
):
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.history))
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(404, "Заявка не найдена")
    return order_dict(order)


@app.patch("/api/v1/admin/orders/{order_id}")
def update_order(
    order_id: int,
    payload: OrderPatch,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_admin),
):
    verify_origin(request)
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.history))
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(404, "Заявка не найдена")
    if payload.status is not None and payload.status != order.status:
        old = order.status
        order.status = payload.status
        order.history.append(
            OrderStatusHistory(
                old_status=old, new_status=payload.status, changed_by_admin_id=admin.id
            )
        )
        if (
            old == "new"
            and payload.status != "new"
            and order.first_processed_at is None
        ):
            order.first_processed_at = datetime.now(timezone.utc)
    if "admin_note" in payload.model_fields_set:
        order.admin_note = payload.admin_note.strip() if payload.admin_note else None
    db.commit()
    db.refresh(order)
    return order_dict(order)


@app.get("/api/v1/admin/services", response_model=list[ServiceOut])
def admin_services(
    db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)
):
    return db.scalars(select(Service).order_by(Service.sort_order, Service.name)).all()


@app.post("/api/v1/admin/services", response_model=ServiceOut, status_code=201)
def create_service(
    payload: ServiceWrite,
    request: Request,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    verify_origin(request)
    service = Service(**payload.model_dump())
    db.add(service)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Slug уже используется")
    db.refresh(service)
    return service


@app.patch("/api/v1/admin/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    payload: ServicePatch,
    request: Request,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    verify_origin(request)
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(404, "Услуга не найдена")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Slug уже используется")
    db.refresh(service)
    return service


@app.get("/api/v1/admin/metrics")
def metrics(db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    return order_statistics(db)


@app.post("/api/v1/admin/assistant/chat")
def admin_assistant(
    payload: ChatIn,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    return demo_admin_answer(db, payload.message)
