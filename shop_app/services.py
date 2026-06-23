from django.db import transaction

from shop_app.models import Shop, Category, Product, Parameter, ProductParameter, OrderItem


# Декоратор транзакции
@transaction.atomic
def import_shop_data_from_yaml(yaml_data):
    """
    Функция импорта товаров из YAML
    """
    shop_name = yaml_data.get('shop')
    if not shop_name:
        return {'Status': False, 'Error': 'В файле не указано название магазина'}

    # Создание магазина
    shop, _ = Shop.objects.get_or_create(
        name=shop_name,
        defaults={'state': True}
    )

    # Загрузка категорий
    for cat_data in yaml_data.get('categories', []):
        try:
            Category.objects.get(original_id=cat_data['id'], shop=shop)
        except Category.DoesNotExist:
            Category.objects.create(
                original_id=cat_data['id'],
                name=cat_data['name'],
                shop=shop
            )

    # Удаление товаров магазина, которых нет в заказах, перед обновлением прайса
    safe_to_delete = Product.objects.filter(
        category__shop=shop
    ).exclude(
        original_id__in=OrderItem.objects.values_list('product_id', flat=True)
    )
    safe_to_delete.delete()

    # Загрузка товаров
    for item in yaml_data.get('goods', []):
        category = Category.objects.get(original_id=item['category'], shop=shop)

        try:
            product = Product.objects.get(original_id=item['id'], category=category)
            # Товар найден - обновление данных
            product.name = item['name']
            product.model = item.get('model', '')
            product.price = item['price']
            product.price_rrc = item['price_rrc']
            product.quantity = item['quantity']
            product.save()
        except Product.DoesNotExist:
            # Товар не найден - создание
            product = Product.objects.create(
                original_id=item['id'],
                name=item['name'],
                model=item.get('model', ''),
                category=category,
                price=item['price'],
                price_rrc=item['price_rrc'],
                quantity=item['quantity']
            )

        # Загрузка характеристик товара
        parameters_data = item.get('parameters', {})
        for param_name, param_value in parameters_data.items():
            # Получение или создание названия характеристики (например, Диагональ (дюйм))
            param, _ = Parameter.objects.get_or_create(name=param_name)

            # Привязка значения к товару.
            ProductParameter.objects.update_or_create(
                product=product,
                parameter=param,
                defaults={'value': str(param_value)}
            )

    return {'Status': True}