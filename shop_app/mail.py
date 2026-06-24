from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from diplom_shop import settings
from shop_app.models import Order

User = get_user_model()


def get_address(contact) -> str:
    """Собирает строку адреса"""
    address_parts = [contact.city, f"ул. {contact.street}", f"д. {contact.house}"]
    if contact.structure:
        address_parts.append(f"корп. {contact.structure}")
    if contact.building:
        address_parts.append(f"стр. {contact.building}")
    if contact.apartment:
        address_parts.append(f"кв. {contact.apartment}")
    return ", ".join(address_parts)


def send_new_order(order: Order):
    """Письма при оформлении заказа"""
    total = order.total_sum()

    items_list = "\n".join(
        [
            f"- {item.product.name} (x{item.quantity}) - {item.price * item.quantity} руб."
            for item in order.ordered_items.all()
        ]
    )

    # Письмо клиенту
    client_msg = (
        f"Здравствуйте, {order.user.username}!\n\n"
        f"Ваш заказ № {order.id} от {order.dt.strftime('%d.%m.%Y %H:%M')} принят в обработку.\n\n"
        f"СОСТАВ:\n{items_list}\n\n"
        f"ИТОГО: {total} руб."
    )

    try:
        send_mail(
            subject=f"Ваш заказ № {order.id} оформлен",
            message=client_msg,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"ОШИБКА ОТПРАВКИ EMAIL КЛИЕНТУ: {e}")

    # 2. Письмо-накладная админу
    admin_emails = list(User.objects.filter(is_superuser=True, is_active=True).values_list("email", flat=True))
    if not admin_emails:
        return

    admin_msg = (
        f"НОВЫЙ ЗАКАЗ № {order.id}\n"
        f"Покупатель: {order.user.username}\n"
        f"Тел: {order.contact.phone}\n"
        f"Адрес: {get_address(order.contact)}\n\n"
        f"СОСТАВ:\n{items_list}\n\n"
        f"ИТОГО: {total} руб."
    )

    try:
        send_mail(
            subject=f"Накладная: Заказ № {order.id}",
            message=admin_msg,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=False,
        )
    except Exception as e:
        print(f"ОШИБКА ОТПРАВКИ EMAIL АДМИНУ: {e}")


def send_status_change(order: Order):
    """Письмо о смене статуса"""
    status_text = order.get_state_display()

    msg = (
        f"Здравствуйте, {order.user.username}!\n\n"
        f"Статус заказа № {order.id} изменен на: {status_text}."
    )

    try:
        send_mail(
            subject=f"Статус заказа № {order.id}",
            message=msg,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"ОШИБКА ОТПРАВКИ СТАТУСА: {e}")


def send_registration_email(user, token):
    """Письмо для подтверждения регистрации"""
    swagger_url = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}/api/docs/"

    message = (
        f"Для активации аккаунта перейдите в Swagger: {swagger_url}\n\n"
        f"Найдите эндпоинт Register Confirm (POST) и отправьте следующий JSON:\n\n"
        f"{{\n"
        f'  "token": "{token.key}"\n'
        f"}}"
    )

    try:
        user.email_user(
            subject=f"Подтверждение регистрации {user.username}",
            message=message,
            fail_silently=False,
        )
    except Exception as e:
        print(f"ОШИБКА ОТПРАВКИ EMAIL: {e}")


def send_password_reset_email(user, token):
    """Письмо для сброса пароля"""
    swagger_url = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}/api/docs/"

    message = (
        f"Для сброса пароля перейдите в Swagger: {swagger_url}\n\n"
        f"Найдите эндпоинт Reset Password Confirm (POST) и отправьте следующий JSON:\n\n"
        f"{{\n"
        f'  "user_id": {user.pk},\n'
        f'  "token": "{token}",\n'
        f'  "new_password": "Ваш_Новый_Пароль"\n'
        f"}}"
    )

    try:
        user.email_user(subject="Сброс пароля", message=message, fail_silently=False)
    except Exception as e:
        print(f"ОШИБКА ОТПРАВКИ EMAIL: {e}")
