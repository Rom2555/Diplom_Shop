from django.core.validators import MinValueValidator
from django.db import models


class Shop(models.Model):
    """
    Модель поставщика (магазина).
    Содержит информацию о магазине и флаг, разрешающий или запрещающий
    прием заказов от данного поставщика.
    """
    name = models.CharField(
        max_length=100,
        verbose_name='Название',
        unique=True,
        help_text='Уникальное название магазина (поставщика)'
    )
    url = models.URLField(
        verbose_name='Ссылка',
        null=True,
        blank=True,
        help_text='URL поставщика'
    )
    state = models.BooleanField(
        verbose_name='Статус приёма заказов',
        default=True,
        db_index=True,  # Индекс для быстрого поиска активных магазинов в БД
        help_text='Включено - магазин принимает заказы, Выключено - импорт идет, но заказы не принимаются'
    )

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'
        ordering = ['name']

    def __str__(self):
        return self.name


class Category(models.Model):
    """
    Категория товаров.
    Привязана к магазину. ID категорий у разных
    поставщиков могут совпадать, но означать разное.
    """
    id = models.PositiveIntegerField(
        primary_key=True,
        verbose_name='ID категории',
        help_text='ID категории из прайс-листа поставщика'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название',
        help_text='Название категории (например: Смартфоны)'
    )
    shop = models.ForeignKey(
        Shop,
        verbose_name='Магазин',
        related_name='categories',
        on_delete=models.CASCADE,
        help_text='Магазин, к которому относится данная категория'
    )

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        constraints = [
            models.UniqueConstraint(
                fields=['id', 'shop'],
                name='unique_category_per_shop'
            )
        ]

    def __str__(self):
        return f'{self.name} (ID: {self.id})'


class Product(models.Model):
    """
    Модель товара.
    Содержит цены и наличие.
    """
    id = models.PositiveIntegerField(
        primary_key=True,
        verbose_name='ID товара',
        help_text='Уникальный идентификатор товара из системы поставщика'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Название',
        help_text='Полное название товара'
    )
    model = models.CharField(
        max_length=255,
        verbose_name='Модель',
        blank=True,
        help_text='Техническое название модели (например: apple/iphone/xs-max)'
    )
    category = models.ForeignKey(
        Category,
        verbose_name='Категория',
        related_name='products',
        on_delete=models.CASCADE,
        help_text='Категория, к которой принадлежит товар'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Цена',
        validators=[MinValueValidator(0)],
        help_text='Текущая цена закупки'
    )
    price_rrc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Рекомендуемая розничная цена',
        validators=[MinValueValidator(0)],
        help_text='Рекомендуемая розничная цена (РРЦ)'
    )
    quantity = models.PositiveIntegerField(
        verbose_name='Количество на складе',
        help_text='Текущий остаток на складе поставщика'
    )

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        constraints = [
            models.UniqueConstraint(
                fields=['id', 'category'],
                name='unique_product_per_category'
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.model})'


class Parameter(models.Model):
    """
    Справочник названий характеристик.
    Используется для реализации динамических (настраиваемых) полей товаров.
    Например: "Диагональ (дюйм)", "Цвет", "Встроенная память (Гб)".
    """
    name = models.CharField(
        max_length=100,
        verbose_name='Название характеристики',
        unique=True,
        help_text='Название свойства товара (например: "Диагональ (дюйм)")'
    )

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Параметры'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    """
    Связь товара с его характеристиками.
    """
    product = models.ForeignKey(
        Product,
        verbose_name='Продукт',
        related_name='product_parameters',
        on_delete=models.CASCADE,
        help_text='Товар, к которому привязана характеристика'
    )
    parameter = models.ForeignKey(
        Parameter,
        verbose_name='Параметр',
        related_name='product_parameters',
        on_delete=models.CASCADE,
        help_text='Наименование характеристики из справочника'
    )
    value = models.CharField(
        max_length=255,
        verbose_name='Значение',
        help_text='Значение характеристики (например: "6.5" или "золотистый")'
    )

    class Meta:
        verbose_name = 'Параметр товара'
        verbose_name_plural = 'Параметры товаров'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'parameter'],
                name='unique_parameter_for_product'
            )
        ]

    def __str__(self):
        return f'{self.product.name} - {self.parameter.name}: {self.value}'


class Contact(models.Model):
    """
    Адреса доставки пользователей.
    Один пользователь может иметь несколько адресов для оформления заказов.
    """
    user = models.ForeignKey(
        'auth.User',
        verbose_name='Пользователь',
        related_name='contacts',
        on_delete=models.CASCADE,
        help_text='Владелец адреса доставки'
    )
    city = models.CharField(
        max_length=50,
        verbose_name='Город',
        help_text='Город доставки'
    )
    street = models.CharField(
        max_length=100,
        verbose_name='Улица',
        help_text='Улица доставки'
    )
    house = models.CharField(
        max_length=15,
        verbose_name='Дом',
        blank=True,
        help_text='Номер дома'
    )
    structure = models.CharField(
        max_length=15,
        verbose_name='Корпус',
        blank=True,
        help_text='Номер корпуса'
    )
    building = models.CharField(
        max_length=15,
        verbose_name='Строение',
        blank=True,
        help_text='Номер строения'
    )
    apartment = models.CharField(
        max_length=15,
        verbose_name='Квартира',
        blank=True,
        help_text='Номер квартиры')

    phone = models.CharField(
        max_length=20,
        verbose_name='Телефон',
        help_text='Контактный номер телефона'
    )

    class Meta:
        verbose_name = 'Контакт'
        verbose_name_plural = 'Контакты'

    def __str__(self):
        return f'{self.city}, ул. {self.street}, д. {self.house}'


class Order(models.Model):
    """
    Модель заказа.
    Статус 'basket' используется для реализации функционала корзины покупок.
    Остальные статусы отражают жизненный цикл заказа.
    """
    STATUS_CHOICES = (
        ('basket', 'Статус корзины'),
        ('new', 'Новый'),
        ('confirmed', 'Подтвержден'),
        ('assembled', 'Собран'),
        ('sent', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('canceled', 'Отменен'),
    )

    user = models.ForeignKey(
        'auth.User',
        verbose_name='Пользователь',
        related_name='orders',
        on_delete=models.CASCADE,
        db_index=True,
        help_text='Покупатель, оформивший заказ'
    )
    dt = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    state = models.CharField(
        max_length=15,
        verbose_name='Статус',
        choices=STATUS_CHOICES,
        default='basket',
        db_index=True,
        help_text='Текущий статус заказа'
    )
    contact = models.ForeignKey(
        Contact,
        verbose_name='Контакт',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Адрес доставки (заполняется при подтверждении заказа из корзины)'
    )

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ('-dt',)

    def __str__(self):
        return f'Заказ №{self.id} от {self.dt.strftime("%d.%m.%Y %H:%M")}'


class OrderItem(models.Model):
    """
    Состав заказа (позиции).
    Дублирует поле shop для возможности быстрой группировки товаров
    по поставщикам при формировании накладных.
    """
    order = models.ForeignKey(
        Order,
        verbose_name='Заказ',
        related_name='ordered_items',
        on_delete=models.CASCADE,
        help_text='Заказ, в который входит данная позиция'
    )
    product = models.ForeignKey(
        Product,
        verbose_name='Продукт',
        on_delete=models.PROTECT,
        help_text='Ссылка на карточку товара'
    )
    shop = models.ForeignKey(
        Shop,
        verbose_name='Магазин',
        on_delete=models.PROTECT,
        help_text='Поставщик данного товара в момент заказа'
    )
    quantity = models.PositiveIntegerField(
        verbose_name='Количество',
        help_text='Заказанное количество'
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Цена',
        help_text='Цена за единицу товара на момент оформления'
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product.name} (x{self.quantity})'
