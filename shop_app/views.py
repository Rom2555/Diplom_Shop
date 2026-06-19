import yaml
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.db.models import F
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from diplom_shop import settings
from shop_app.models import ConfirmEmailToken
from shop_app.models import Product, Contact, Order, OrderItem
from shop_app.serializers import YAMLUploadSerializer, RegisterSerializer, ContactSerializer, BasketSerializer, \
    AddToBasketSerializer, ConfirmOrderSerializer, OrderSerializer
from shop_app.services import import_shop_data_from_yaml
from .serializers import ProductSerializer


@extend_schema(
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


class RegisterConfirmView(APIView):
    """
    Подтверждение email и активация аккаунта
    """
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        token = request.data.get('token')
        if not token:
            return Response({'Status': False, 'Error': 'Нет токена'}, status=400)

        try:
            token_obj = ConfirmEmailToken.objects.get(key=token)
            if token_obj.user.is_active:
                return Response({'Status': False, 'Error': 'Аккаунт уже подтвержден'}, status=400)

            token_obj.user.is_active = True  # Активация пользователя
            token_obj.user.save()
            token_obj.delete()  # Удаление токена после использования

            return Response(
                {'Status': True, 'Message': 'Успешная регистрация! Вы можете войти под своим логином/паролем'})
        except ConfirmEmailToken.DoesNotExist:
            return Response({'Status': False, 'Error': 'Неверный токен'}, status=400)


@extend_schema(
    tags=['User'],
    request=RegisterSerializer,
    responses={201: {'type': 'object', 'properties': {
        'Status': {'type': 'boolean'},
    }}}
)
class RegisterAccount(APIView):
    """
    Регистрация нового пользователя с выдачей JWT токенов
    и отправкой письма подтверждения
    """
    permission_classes = [AllowAny]  # Права доступа для всех

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # Подтверждение регистрации Яндекс
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=user.id)
        confirm_url = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}/api/v1/user/register/confirm/"

        try:
            # Текст письма
            user.email_user(
                subject=f"Подтверждение регистрации {user.username}",
                message=f'Для подтверждения аккаунта используйте API эндпоинт: {confirm_url}\n\n'
                        f'Вставьте следующий токен в Swagger:\n'
                        f'"token": "{token.key}"',
                fail_silently=False,
            )
        except Exception as e:
            print(f"ОШИБКА ОТПРАВКИ EMAIL: {e}")

        return Response(
            {
                'Status': True,
                'massages': u'На ваш email отправлено письмо для подтверждения регистрации'
            },
            status=status.HTTP_201_CREATED
        )


@extend_schema(
    tags=['Products'],
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
    serializer_class = BasketSerializer
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
    tags=['User'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'email': {'type': 'string', 'format': 'email', 'description': 'Email пользователя'}
            },
            'required': ['email']
        }
    },
    responses={200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}}
)
class ResetPasswordView(APIView):
    """
    Запрос на сброс пароля. Отправляет ссылку с токеном на email
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        if not email:
            return Response({'Status': False, 'Error': 'Укажите email'}, status=400)

        try:
            user = User.objects.get(email=email)
            # Токен
            token = default_token_generator.make_token(user)

            # Ссылка для сброса пароля
            reset_url = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}/api/v1/user/password/reset/confirm/"

            # Текст email
            user.email_user(
                'Сброс пароля',
                f'Для сброса пароля пройдите по ссылке: {reset_url}\n\n'
                f'Вставьте следующие данные:\n'
                f'"user_id": {user.pk}\n'
                f'"token": "{token}"\n'
                f'"new_password": "Ваш_Новый_Пароль"',
                fail_silently=False
            )
        except User.DoesNotExist:
            pass  # Безопасность. Не сообщать что пользователь не найдет

        return Response({'Status': True})


@extend_schema(
    tags=['User'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'user_id': {'type': 'integer', 'description': 'ID пользователя из письма'},
                'token': {'type': 'string', 'description': 'Токен из письма'},
                'new_password': {'type': 'string', 'description': 'Новый пароль'}
            },
            'required': ['user_id', 'token', 'new_password']
        }
    },
    responses={200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}}
)
class ResetPasswordConfirmView(APIView):
    """
    Установка нового пароля после получения токена
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        if not all([user_id, token, new_password]):
            return Response({'Status': False, 'Error': 'Заполните все поля: user_id, token, new_password'}, status=400)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'Status': False, 'Error': 'Пользователь не найден'}, status=400)

        # Проверка валидности токена
        if default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response({'Status': True, 'Message': 'Пароль успешно изменен'})
        else:
            return Response({'Status': False, 'Error': 'Неверный токен'}, status=400)
