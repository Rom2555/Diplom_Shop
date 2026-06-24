from django.db import transaction
from django.db.models import F
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shop_app.mail import send_new_order, send_status_change
from shop_app.models import Contact, Order, OrderItem, Product
from shop_app.serializers import (
    AddToBasketSerializer,
    BasketSerializer,
    ConfirmOrderSerializer,
    OrderSerializer,
)


@extend_schema(
    tags=["Basket"],
)
class BasketAPIView(APIView):
    serializer_class = BasketSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Получить текущую корзину", responses={200: BasketSerializer}
    )
    def get(self, request, *args, **kwargs):
        # Поиск статуса 'basket' у пользователя
        basket = (
            Order.objects.filter(user=request.user, state="basket")
            .prefetch_related("ordered_items__product")
            .first()
        )

        # Если корзины нет - вернуть пустой объект
        if not basket:
            return Response({"Status": False, "Basket": []})

        serializer = BasketSerializer(basket)
        return Response({"Status": True, "Basket": serializer.data})

    @extend_schema(
        summary="Добавить товар в корзину",
        request=AddToBasketSerializer,
        responses={
            200: {"type": "object", "properties": {"Status": {"type": "boolean"}}}
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = AddToBasketSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"Status": False, "Errors": serializer.errors}, status=400)

        product_id = serializer.validated_data["product_id"]
        shop_id = serializer.validated_data["shop_id"]
        quantity = serializer.validated_data["quantity"]

        try:
            # Поиск товара и проверка остатка
            product = Product.objects.select_related("category__shop").get(
                original_id=product_id
            )

            # Проверка что продукт относится к этому же магазину
            if product.category.shop_id != shop_id:
                return Response(
                    {
                        "Status": False,
                        "Errors": "Этот товар не принадлежит данному магазину",
                    },
                    status=400,
                )

            # Проверка доступности магазина для заказов
            if not product.category.shop.state:
                return Response(
                    {
                        "Status": False,
                        "Errors": f'Магазин "{product.category.shop.name}" временно не принимает заказы',
                    },
                    status=400,
                )

            # Поиск или создание корзины (статус заказа - basket)
            basket, _ = Order.objects.get_or_create(user=request.user, state="basket")

            # Проверка наличия такого же товара от этого магазина в корзине
            item = OrderItem.objects.filter(
                order=basket, product=product, shop_id=shop_id
            ).first()

            if item:
                # Товар уже в корзине
                new_quantity = item.quantity + quantity
                if new_quantity > product.quantity:
                    return Response(
                        {
                            "Status": False,
                            "Errors": f"Превышено количество на складе. Доступно: {product.quantity}",
                        },
                        status=400,
                    )
                item.quantity = new_quantity
                item.save()
            else:
                # Товара нет в корзине
                if quantity > product.quantity:
                    return Response(
                        {
                            "Status": False,
                            "Errors": f"Превышено количество на складе. Доступно: {product.quantity}",
                        },
                        status=400,
                    )
                # Создание новой позиции
                OrderItem.objects.create(
                    order=basket,
                    product=product,
                    shop_id=shop_id,
                    quantity=quantity,
                    price=product.price,  # Фиксация цены товара
                )

            return Response({"Status": True}, status=200)

        except Product.DoesNotExist:
            return Response({"Status": False, "Errors": "Товар не найден"}, status=404)


class BasketDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Basket"],
        summary="Удалить позицию из корзины",
        responses={
            200: {"type": "object", "properties": {"Status": {"type": "boolean"}}}
        },
    )
    def delete(self, request, *args, **kwargs):
        # ID из URL
        items_id = kwargs.get("items_id")

        try:
            item = OrderItem.objects.get(
                id=items_id, order__user=request.user, order__state="basket"
            )
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except OrderItem.DoesNotExist:
            return Response(
                {"Status": False, "Errors": "Позиция не найдена в корзине"}, status=404
            )


class OrderConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary=f"Подтверждение заказа",
        request=ConfirmOrderSerializer,
        responses={
            200: {"type": "object", "properties": {"Status": {"type": "boolean"}}}
        },
    )
    @transaction.atomic  # Атоматический откат транзакции при падении любой операции внутри post
    def post(self, request, *args, **kwargs):
        # Получение корзины пользователя
        basket = (
            Order.objects.filter(user=request.user, state="basket")
            .select_related("contact")
            .first()
        )
        if not basket:
            return Response({"Status": False, "Errors": "Корзина пуста"}, status=400)

        # Валидация ID контакта
        serializer = ConfirmOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"Status": False, "Errors": serializer.errors}, status=400)

        contact_id = serializer.validated_data["contact_id"]

        try:
            # Проверка - контакт принадлежит пользователю
            contact = Contact.objects.get(id=contact_id, user=request.user)
        except Contact.DoesNotExist:
            return Response(
                {"Status": False, "Errors": "Контакт не найден"}, status=404
            )

        # Проверка остатков всех товаров до списания
        for item in basket.ordered_items.all():
            if item.product.quantity < item.quantity:
                return Response(
                    {
                        "Status": False,
                        "Errors": f"Товар {item.product.name} закончился на складе",
                    },
                    status=400,
                )

        # Атомарное списание товаров в БД
        for item in basket.ordered_items.all():
            updated = Product.objects.filter(id=item.product_id).update(
                quantity=F("quantity") - item.quantity
            )
            if updated == 0:  # Ни одна строка не обновлена
                return Response(
                    {
                        "Status": False,
                        "Errors": f"Товар {item.product.name} закончился на складе",
                    },
                    status=400,
                )

        # Изменение статуса заказа и привязка контакта
        basket.state = "new"
        basket.contact = contact
        basket.save()

        # Отправка писем
        send_new_order(basket)

        return Response(
            {
                "Status": True,
                "Order_ID": basket.id,
                "Message": "Письмо с заказом отправлено на email",
            }
        )


@extend_schema_view(
    list=extend_schema(
        summary="Список заказов пользователя",
        tags=["Orders"],
    ),
    retrieve=extend_schema(
        summary="Детали конкретного заказа",
        tags=["Orders"],
    ),
)
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    queryset = Order.objects.none()

    def get_queryset(self):
        # Заказы пользователя с исключением корзины
        return (
            Order.objects.filter(user=self.request.user)
            .exclude(state="basket")
            .prefetch_related("ordered_items__product", "contact")
        )


@extend_schema(
    tags=["Orders"],
    summary="Изменение состояния заказа",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer", "description": "ID заказа"},
                "state": {
                    "type": "string",
                    "description": "Новый статус (new, confirmed, assembled, sent, delivered, canceled)",
                },
            },
            "required": ["order_id", "state"],
        }
    },
    responses={200: {"type": "object", "properties": {"Status": {"type": "boolean"}}}},
)
class OrderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        order_id = request.data.get("order_id")
        new_state = request.data.get("state")

        if not order_id or not new_state:
            return Response(
                {"Status": False, "Errors": "Укажите order_id и state"}, status=400
            )

        # Проверка статуса в базе из списка допустимых
        valid_states = [choice[0] for choice in Order.STATUS_CHOICES]
        if new_state not in valid_states:
            return Response(
                {
                    "Status": False,
                    "Errors": f"Неверный статус. Допустимые: {valid_states}",
                },
                status=400,
            )

        try:
            order = Order.objects.get(id=order_id)
            order.state = new_state
            order.save()

            # Отправка письма клиенту
            send_status_change(order)

            return Response(
                {
                    "Status": True,
                    "Message": f"Статус изменен на '{order.get_state_display()}', на email отправлено сообщение",
                }
            )
        except Order.DoesNotExist:
            return Response({"Status": False, "Errors": "Заказ не найден"}, status=404)
