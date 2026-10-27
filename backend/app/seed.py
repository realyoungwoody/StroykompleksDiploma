from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from .core.config import get_settings
from .core.security import hash_password
from .models import AdminUser, Order, OrderItem, OrderStatusHistory, Service

SERVICES = [
    (
        "mekhanizirovannaya-shtukaturka",
        "Механизированная штукатурка стен",
        "Штукатурные работы",
        "Быстрое выравнивание стен с нанесением смеси машинным способом.",
        "Подходит для больших площадей и помогает получить ровное основание под дальнейшую отделку.",
        "Подготовка основания; установка маяков; нанесение смеси; выравнивание; контроль",
        "750.00",
    ),
    (
        "ruchnaya-shtukaturka",
        "Ручная штукатурка стен",
        "Штукатурные работы",
        "Точное ручное выравнивание стен на локальных и сложных участках.",
        "Рациональный выбор для небольших помещений, откосов и поверхностей сложной геометрии.",
        "Осмотр; подготовка; установка маяков; нанесение; затирка",
        "950.00",
    ),
    (
        "pokraska-vodoemulsionnaya",
        "Покраска стен водоэмульсионной краской",
        "Малярные работы",
        "Аккуратное финишное покрытие стен водоэмульсионным составом.",
        "Нанесение краски на подготовленное основание в согласованное число слоёв.",
        "Защита поверхностей; грунтование; окраска; проверка покрытия",
        "420.00",
    ),
    (
        "pokraska-maslyanaya",
        "Покраска стен масляной краской",
        "Малярные работы",
        "Износостойкое покрытие для подходящих подготовленных поверхностей.",
        "Работы выполняются после оценки основания и совместимости материалов.",
        "Подготовка; грунтование; нанесение краски; сушка",
        "520.00",
    ),
    (
        "nastennaya-plitka",
        "Укладка настенной плитки",
        "Плиточные работы",
        "Облицовка подготовленных стен плиткой с выравниванием швов.",
        "Предварительная оценка раскладки помогает уменьшить лишние подрезки.",
        "Разметка; подготовка клея; укладка; затирка швов",
        "1600.00",
    ),
    (
        "napolnaya-plitka",
        "Укладка напольной плитки",
        "Плиточные работы",
        "Укладка плитки на подготовленное основание пола.",
        "Включает разметку, укладку и оформление межплиточных швов.",
        "Проверка основания; разметка; укладка; затирка",
        "1450.00",
    ),
    (
        "natyazhnoy-potolok",
        "Монтаж натяжного потолка",
        "Потолки",
        "Монтаж полотна натяжного потолка по размерам помещения.",
        "Итоговая оценка зависит от геометрии помещения и дополнительных элементов.",
        "Замер; разметка; монтаж профиля; установка полотна; контроль",
        "1100.00",
    ),
    (
        "laminat",
        "Укладка ламината",
        "Напольные покрытия",
        "Монтаж ламината на подготовленное ровное основание.",
        "Перед работой оцениваются состояние основания и схема раскладки.",
        "Проверка основания; подложка; раскладка; монтаж; контроль",
        "650.00",
    ),
]

FAQ = [
    (
        "Как оставить заявку?",
        "Добавьте услуги в корзину, укажите объём, перейдите к оформлению и заполните короткую форму.",
    ),
    (
        "Можно ли выбрать несколько услуг?",
        "Да. В одной заявке можно объединить до 20 разных услуг.",
    ),
    (
        "От чего зависит окончательная стоимость?",
        "От фактического объёма, состояния основания, сложности и согласованных материалов.",
    ),
    (
        "Является ли предварительная цена окончательной?",
        "Нет. Расчёт ориентировочный и уточняется после согласования условий работ.",
    ),
    (
        "Как узнать статус заявки?",
        "Откройте раздел «Проверить заявку» и введите номер заявки вместе с телефоном.",
    ),
    (
        "Нужно ли регистрироваться на сайте?",
        "Нет, для оформления и проверки заявки регистрация не требуется.",
    ),
    (
        "Как выбрать подходящий вид штукатурки?",
        "Механизированная удобна для больших площадей, ручная — для локальных и сложных участков.",
    ),
    (
        "Чем отличаются виды покраски?",
        "Составом покрытия и требованиями к поверхности. Конкретный вариант выбирают с учётом помещения и основания.",
    ),
    (
        "Можно ли указать желаемую дату?",
        "Да, укажите её при оформлении. Это пожелание, а не подтверждённый срок.",
    ),
    (
        "Как происходит согласование объёма работ?",
        "После регистрации заявки параметры уточняются до подтверждения окончательной стоимости.",
    ),
    (
        "Можно ли изменить заявку после отправки?",
        "В MVP прямое редактирование недоступно; детали можно уточнить на этапе обработки.",
    ),
    (
        "Передаются ли заявки настоящей компании?",
        "Нет. Это учебный демонстрационный проект, все заявки остаются в локальной системе.",
    ),
]


def seed_database(db: Session) -> None:
    settings = get_settings()
    if db.scalar(select(Service.id).limit(1)) is None:
        for index, row in enumerate(SERVICES, 1):
            db.add(
                Service(
                    slug=row[0],
                    name=row[1],
                    category=row[2],
                    short_description=row[3],
                    description=row[4],
                    stages=row[5],
                    unit="м²",
                    base_price_rub=Decimal(row[6]),
                    sort_order=index,
                )
            )
        db.commit()
    if db.scalar(select(AdminUser.id).limit(1)) is None:
        db.add(
            AdminUser(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
            )
        )
        db.commit()
    if db.scalar(select(Order.id).limit(1)) is None:
        services = db.scalars(select(Service).order_by(Service.id)).all()
        statuses = [
            "new",
            "new",
            "new",
            "contacted",
            "contacted",
            "in_progress",
            "in_progress",
            "in_progress",
            "completed",
            "completed",
            "cancelled",
        ]
        now = datetime.now(timezone.utc)
        for i, status in enumerate(statuses, 1):
            created = now - timedelta(
                hours=30 + i if status == "new" and i < 3 else i * 3
            )
            service = services[(i - 1) % len(services)]
            qty = Decimal(str(10 + i))
            total = Decimal(service.base_price_rub) * qty
            order = Order(
                public_number=f"SC-DEMO{i:06d}",
                customer_name=f"Тестовый заказчик {i:02d}",
                phone_normalized=f"+700000000{i:02d}",
                email=None,
                object_location="Нижний Новгород",
                comment="Демонстрационная заявка",
                status=status,
                estimated_total_rub=total,
                is_demo=True,
                created_at=created,
                updated_at=created,
                first_processed_at=(
                    created + timedelta(hours=2) if status != "new" else None
                ),
            )
            order.items.append(
                OrderItem(
                    service_id=service.id,
                    service_name_snapshot=service.name,
                    unit_snapshot=service.unit,
                    quantity=qty,
                    unit_price_snapshot=service.base_price_rub,
                    line_total_rub=total,
                )
            )
            order.history.append(
                OrderStatusHistory(
                    old_status=None, new_status="new", created_at=created
                )
            )
            if status != "new":
                order.history.append(
                    OrderStatusHistory(
                        old_status="new",
                        new_status=status,
                        created_at=created + timedelta(hours=2),
                    )
                )
            db.add(order)
        db.commit()
