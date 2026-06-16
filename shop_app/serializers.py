from django.contrib.auth.models import User
from rest_framework import serializers

from shop_app.models import ProductParameter, Product, Contact, Order, OrderItem


class RegisterSerializer(serializers.ModelSerializer):
    """
    Сериализатор для регистрации нового пользователя
    """
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password')

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
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
            'id', 'name', 'model', 'category',
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

    def get_total_sum(self, obj):
        # Сумма корзины
        return sum(item.quantity * item.price for item in obj.ordered_items.all())


class AddToBasketSerializer(serializers.Serializer):
    """
    Сериализатор для валидации данных при добавлении товара в корзину
    """
    product_id = serializers.IntegerField(write_only=True, help_text='ID товара')
    shop_id = serializers.IntegerField(write_only=True, help_text='ID магазина (поставщика)')
    quantity = serializers.IntegerField(write_only=True, default=1, help_text='Количество (по умолчанию 1)')
