from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from shop_app.models import ProductParameter, Product, Contact, Order, OrderItem


class RegisterSerializer(serializers.ModelSerializer):
    """
    Сериализатор для регистрации нового пользователя
    """
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(
        help_text='Имя пользователя',
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="Пользователь с таким именем уже существует"
            )
        ]
    )
    email = serializers.EmailField(
        help_text='Электронная почта',
        required=True,  # Обязательное поле для регистрации
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="Пользователь с такой почтой уже зарегистрирован"
            )
        ]
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password')

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_active=False
        )
        # Хеширование пароля перед сохранением
        user.set_password(validated_data['password'])
        user.save()
        return user


class YAMLUploadSerializer(serializers.Serializer):
    """
    Сериализатор для валидации загружаемого YAML файла
    """
    file = serializers.FileField(
        help_text='YAML файл с прайс-листом поставщика'
    )


class ProductParameterSerializer(serializers.ModelSerializer):
    """
    Сериализатор для вывода названия параметра и его значения
    """
    parameter = serializers.StringRelatedField()

    class Meta:
        model = ProductParameter
        fields = ['parameter', 'value']


class ProductSerializer(serializers.ModelSerializer):
    """
    Сериализатор для вывода товара вместе с его характеристиками
    """
    product_parameters = ProductParameterSerializer(many=True, read_only=True)
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = (
            'original_id', 'name', 'model', 'category',
            'price', 'price_rrc', 'quantity', 'product_parameters'
        )


class ContactSerializer(serializers.ModelSerializer):
    """
    Сериализатор для адресов доставки
    """

    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure', 'building', 'apartment', 'phone')
        read_only_fields = ('id',)


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Сериализатор для позиции в корзине
    """
    # Название товара
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'shop', 'quantity', 'price')


class BasketSerializer(serializers.ModelSerializer):
    """
    Сериализатор для корзины (Статус заказа - basket)
    """
    ordered_items = OrderItemSerializer(many=True, read_only=True)
    total_sum = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ('id', 'ordered_items', 'total_sum', 'state', 'dt')

    def get_total_sum(self, obj) -> int:
        # Сумма корзины
        return obj.total_sum()


class AddToBasketSerializer(serializers.Serializer):
    """
    Сериализатор для валидации данных при добавлении товара в корзину
    """
    product_id = serializers.IntegerField(write_only=True, help_text='ID товара')
    shop_id = serializers.IntegerField(write_only=True, help_text='ID магазина (поставщика)')
    quantity = serializers.IntegerField(write_only=True, default=1, help_text='Количество (по умолчанию 1)')


class ConfirmOrderSerializer(serializers.Serializer):
    """
    Сериализатор для подтверждения заказа из корзины
    """
    contact_id = serializers.IntegerField(write_only=True, help_text='ID адреса доставки')


class OrderItemForOrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор для позиций внутри истории заказов
    """
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'shop', 'quantity', 'price')


class ContactForOrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор для вывода контакта в заказе
    """

    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure', 'building', 'apartment', 'phone')


class OrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор для вывода истории заказов и деталей заказа
    """
    ordered_items = OrderItemForOrderSerializer(many=True, read_only=True)
    contact = ContactForOrderSerializer(read_only=True)
    total_sum = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ('id', 'dt', 'state', 'contact', 'ordered_items', 'total_sum')
        read_only_fields = fields

    def get_total_sum(self, obj) -> int:
        return obj.total_sum()


class TokenConfirmSerializer(serializers.Serializer):
    """
    Сериализатор для приема токена из письма
    """
    token = serializers.CharField(help_text='Токен подтверждения из письма')


class ShopIdQuerySerializer(serializers.Serializer):
    """ Сериализатор для поля id магазина поставщика """
    shop_id = serializers.IntegerField(help_text='ID магазина поставщика')
