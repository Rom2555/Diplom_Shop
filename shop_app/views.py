import yaml
from django.db import transaction
from django.db.models import F
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from shop_app.models import Product, Contact, Order, OrderItem
from shop_app.serializers import YAMLUploadSerializer, RegisterSerializer, ContactSerializer, BasketSerializer, \
    AddToBasketSerializer, ConfirmOrderSerializer
from shop_app.services import import_shop_data_from_yaml
from .serializers import ProductSerializer


@extend_schema(
    auth=[],
    tags=['Partner'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'file': {
                    'type': 'string',
                    'format': 'binary',
                    'description': 'YAML файл с прайс-листом поставщика'
                }
            },
            'required': ['file']
        }
    },
    responses={200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}}
)
class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика (импорт YAML файла).
    """
    permission_classes = [AllowAny]  # Права доступа для всех

    def post(self, request, *args, **kwargs):
        # Валидация входящих данных через сериализатор
        serializer = YAMLUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Проверенный файл
        yaml_file = serializer.validated_data['file']

        try:
            # Чтение файла и парсинг YAML
            # safe_load защита от выполнения кода в YAML
            yaml_data = yaml.safe_load(yaml_file.read())
        except yaml.YAMLError:
            return Response(
                {'Status': False, 'Error': 'Неверный формат YAML файла'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'Status': False, 'Error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Передача данных сервису
        result = import_shop_data_from_yaml(yaml_data)

        if result.get('Status'):
            return Response({'Status': True}, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['User'],
    auth=[],
    request=RegisterSerializer,
    responses={201: {'type': 'object', 'properties': {
        'Status': {'type': 'boolean'},
        'refresh': {'type': 'string'},
        'access': {'type': 'string'}
    }}}
)
class RegisterAccount(APIView):
    """
    Регистрация нового пользователя с выдачей JWT токенов
    """
    permission_classes = [AllowAny]  # Права доступа для всех

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # Генерация JWT токенов
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'Status': True,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            },
            status=status.HTTP_201_CREATED
        )


@extend_schema(
    tags=['Products'],
    auth=[],
)
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Просмотр каталога товаров и информации по товару
    """
    queryset = Product.objects.all().select_related('category').prefetch_related('product_parameters')
    serializer_class = ProductSerializer


@extend_schema(
    tags=['Contacts'],
)
class ContactViewSet(viewsets.ModelViewSet):
    """
    Управление контактами (адресами доставки) пользователя.
    Доступно только авторизованным пользователям
    """

    permission_classes = [IsAuthenticated]  # Допускает только пользователей с токеном
    serializer_class = ContactSerializer

    # http методы только GET/POST/DELETE (кроме PUT/PATCH)
    http_method_names = ['get', 'post', 'delete']

    queryset = Contact.objects.none()

    def get_queryset(self):
        # Фильтр. Пользователь видит только свои контакты
        return Contact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Автопривязка контактов к пользователю
        serializer.save(user=self.request.user)


@extend_schema(
    tags=['Basket'],
)
class BasketAPIView(APIView):
    """
    Класс для работы с корзиной пользователя
    """
    permission_classes = [IsAuthenticated]  # Допускает только пользователей с токеном

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
        request=AddToBasketSerializer,
        responses={
            200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}
        }
    )
    def post(self, request, *args, **kwargs):
        # Валидация входящих данных
        serializer = AddToBasketSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'Status': False, 'Errors': serializer.errors}, status=400)

        product_id = serializer.validated_data['product_id']
        shop_id = serializer.validated_data['shop_id']
        quantity = serializer.validated_data['quantity']

        try:
            # Поиск товара и проверка остатка
            product = Product.objects.select_related('category__shop').get(id=product_id)

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
                    price=product.price  # Сохранение текущей цены товара
                )

            return Response({'Status': True}, status=200)

        except Product.DoesNotExist:
            return Response({'Status': False, 'Errors': 'Товар не найден'}, status=404)



        except OrderItem.DoesNotExist:
            return Response({'Status': False, 'Errors': 'Позиция не найдена в корзине'}, status=404)


class BasketDeleteView(APIView):
    """Удаление товара из корзины по ID в URL"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Basket'],
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
    @transaction.atomic    # Атоматический откат транзакции при падении любой операции внутри post
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

        # Атомарное списание ВСЕХ товаров
        for item in basket.ordered_items.all():
            updated = Product.objects.filter(id=item.product_id).update(
                quantity=F('quantity') - item.quantity
            )
            if updated == 0: # Ни одна строка не обновлена
                return Response(
                    {'Status': False, 'Errors': f'Товар {item.product.name} закончился на складе'},
                    status=400
                )

        # Изменение статуса заказа и привязка контакта
        basket.state = 'new'
        basket.contact = contact
        basket.save()

        return Response({'Status': True, 'Order_ID': basket.id})
