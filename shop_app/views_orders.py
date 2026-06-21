from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from diplom_shop import settings
from shop_app.models import Product, Contact, Order, OrderItem
from shop_app.serializers import BasketSerializer, \
    AddToBasketSerializer, ConfirmOrderSerializer, OrderSerializer


@extend_schema(
    tags=['Basket'],
)
class BasketAPIView(APIView):
    """
    Класс для работы с корзиной пользователя
    """
    serializer_class = BasketSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Получить текущую корзину",
        responses={200: BasketSerializer}
    )
    def get(self, request, *args, **kwargs):
        # Поиск статуса 'basket' у пользователя
        basket = Order.objects.filter(
            user=request.user,
            state='basket'
        ).prefetch_related('ordered_items__product').first()

        # Если корзины нет - вернуть пустой объект
        if not basket:
            return Response({'Status': True, 'Basket': []})

        serializer = BasketSerializer(basket)
        return Response({'Status': True, 'Basket': serializer.data})

    @extend_schema(
        summary="Добавить товар в корзину",
        request=AddToBasketSerializer,
        responses={
            200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = AddToBasketSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'Status': False, 'Errors': serializer.errors}, status=400)

        product_id = serializer.validated_data['product_id']
        shop_id = serializer.validated_data['shop_id']
        quantity = serializer.validated_data['quantity']

        try:
            # Поиск товара и проверка остатка
            product = Product.objects.select_related('category__shop').get(id=product_id)

            # Проверка доступности магазина для заказов
            if not product.category.shop.state:
                return Response(
                    {'Status': False, 'Errors': 'Магазин временно не принимает заказы'}, status=400
                )

            # Проверка что продукт относится к этому же магазину
            if product.category.shop_id != shop_id:
                return Response({'Status': False, 'Errors': 'Этот товар не принадлежит данному магазину'},
                                status=400)

            # Поиск или создание корзины (статус заказа - basket)
            basket, _ = Order.objects.get_or_create(user=request.user, state='basket')

            # Проверка наличия такого же товара от этого магазина в корзине
            item = OrderItem.objects.filter(
                order=basket,
                product=product,
                shop_id=shop_id
            ).first()

            if item:
                # Товар уже в корзине
                new_quantity = item.quantity + quantity
                if new_quantity > product.quantity:
                    return Response(
                        {'Status': False, 'Errors': f'Превышено количество на складе. Доступно: {product.quantity}'},
                        status=400)
                item.quantity = new_quantity
                item.save()
            else:
                # Товара нет в корзине
                if quantity > product.quantity:
                    return Response(
                        {'Status': False, 'Errors': f'Превышено количество на складе. Доступно: {product.quantity}'},
                        status=400)
                # Создание новой позиции
                OrderItem.objects.create(
                    order=basket,
                    product=product,
                    shop_id=shop_id,
                    quantity=quantity,
                    price=product.price  # Фиксация цены товара
                )

            return Response({'Status': True}, status=200)

        except Product.DoesNotExist:
            return Response({'Status': False, 'Errors': 'Товар не найден'}, status=404)


class BasketDeleteView(APIView):
    """Удаление товара из корзины по ID в URL"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Basket'],
        summary="Удалить позицию из корзины",
        responses={200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}}
    )
    def delete(self, request, *args, **kwargs):
        # ID из URL
        items_id = kwargs.get('items_id')

        try:
            item = OrderItem.objects.get(
                id=items_id,
                order__user=request.user,
                order__state='basket'
            )
            item.delete()
            return Response({'Status': True})
        except OrderItem.DoesNotExist:
            return Response({'Status': False, 'Errors': 'Позиция не найдена в корзине'}, status=404)


class OrderConfirmView(APIView):
    """
    Подтверждение заказа (перевод корзины в статус 'new').
    Списание со склада и привязка контакта
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Orders'],
        request=ConfirmOrderSerializer,
        responses={200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}}
    )
    @transaction.atomic  # Атоматический откат транзакции при падении любой операции внутри post
    def post(self, request, *args, **kwargs):
        # Получение корзины пользователя
        basket = Order.objects.filter(user=request.user, state='basket').select_related('contact').first()
        if not basket:
            return Response({'Status': False, 'Errors': 'Корзина пуста'}, status=400)

        # Валидация ID контакта
        serializer = ConfirmOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'Status': False, 'Errors': serializer.errors}, status=400)

        contact_id = serializer.validated_data['contact_id']

        try:
            # Проверка - контакт принадлежит пользователю
            contact = Contact.objects.get(id=contact_id, user=request.user)
        except Contact.DoesNotExist:
            return Response({'Status': False, 'Errors': 'Контакт не найден'}, status=404)

        # Проверка остатков всех товаров до списания
        for item in basket.ordered_items.all():
            if item.product.quantity < item.quantity:
                return Response(
                    {'Status': False, 'Errors': f'Товар {item.product.name} закончился на складе'},
                    status=400
                )

        # Атомарное списание товаров в БД
        for item in basket.ordered_items.all():
            updated = Product.objects.filter(id=item.product_id).update(
                quantity=F('quantity') - item.quantity
            )
            if updated == 0:  # Ни одна строка не обновлена
                return Response(
                    {'Status': False, 'Errors': f'Товар {item.product.name} закончился на складе'},
                    status=400
                )

        # Изменение статуса заказа и привязка контакта
        basket.state = 'new'
        basket.contact = contact
        basket.save()

        # ******* ОТПРАВКА ПИСЕМ **********

        User = get_user_model()

        # Письмо клиенту (подтверждение)
        try:
            send_mail(
                subject=f'Заказ №{basket.id} оформлен',
                message=f'Здравствуйте! Ваш заказ принят в обработку.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"ОШИБКА ОТПРАВКИ EMAIL КЛИЕНТУ: {e}")

        # Письмо администратору (накладная)
        admin_emails = list(User.objects.filter(is_superuser=True, is_active=True).values_list('email', flat=True))
        if admin_emails:
            # Таблица с товарами
            items_text = "\n".join(
                [f"- {item.product.name} | Количество: {item.quantity} | Цена: {item.price}"
                 for item in basket.ordered_items.all()]
            )

            # Сборка полного адреса доставки
            address_parts = [
                contact.city,
                f"ул. {contact.street}",
                f"д. {contact.house}"
            ]
            if contact.structure: address_parts.append(f"корп. {contact.structure}")
            if contact.building: address_parts.append(f"стр. {contact.building}")
            if contact.apartment: address_parts.append(f"кв. {contact.apartment}")
            full_address = ", ".join(address_parts)

            # Текст накладной
            invoice_text = (
                f"Новый заказ №{basket.id}\n"
                f"Покупатель: {request.user.username} (ID: {request.user.id})\n"
                f"Телефон: {contact.phone}\n"
                f"Адрес доставки: {full_address}\n\n"
                f"Состав заказа:\n{items_text}"
            )

            try:
                send_mail(
                    subject=f'Новая накладная: Заказ №{basket.id}',
                    message=invoice_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=False,
                )
            except Exception as e:
                print(f"ОШИБКА ОТПРАВКИ EMAIL АДМИНИСТРАТОРУ: {e}")
        # ****************************

        return Response({'Status': True, 'Order_ID': basket.id})


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Просмотр истории заказов и деталей конкретного заказа
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    queryset = Order.objects.none()

    def get_queryset(self):
        # Заказы пользователя с исключением корзины
        return Order.objects.filter(user=self.request.user).exclude(state='basket').prefetch_related(
            'ordered_items__product', 'contact')


@extend_schema(
    tags=['Orders'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'order_id': {'type': 'integer', 'description': 'ID заказа'},
                'state': {'type': 'string',
                          'description': 'Новый статус (new, confirmed, assembled, sent, delivered, canceled)'}
            },
            'required': ['order_id', 'state']
        }
    },
    responses={200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}}
)
class OrderStatusView(APIView):
    """
    Редактирование статуса заказа
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        order_id = request.data.get('order_id')
        new_state = request.data.get('state')

        if not order_id or not new_state:
            return Response({'Status': False, 'Errors': 'Укажите order_id и state'}, status=400)

        # Проверка статуса в базе из списка допустимых
        valid_states = [choice[0] for choice in Order.STATUS_CHOICES]
        if new_state not in valid_states:
            return Response({'Status': False, 'Errors': f'Неверный статус. Допустимые: {valid_states}'}, status=400)

        try:
            order = Order.objects.get(id=order_id)
            order.state = new_state
            order.save()

            # Отправка письма клиенту
            try:
                send_mail(
                    subject=f'Обновление статуса заказа № {order.id}',
                    message=f'Статус вашего заказа № {order.id} изменен на: "{order.get_state_display()}".',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.user.email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"ОШИБКА ОТПРАВКИ СТАТУСА: {e}")

            return Response({'Status': True})
        except Order.DoesNotExist:
            return Response({'Status': False, 'Errors': 'Заказ не найден'}, status=404)
