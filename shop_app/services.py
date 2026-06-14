from django.db import transaction

from shop_app.models import Shop, Category, Product, Parameter, ProductParameter


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
        Category.objects.get_or_create(
            id=cat_data['id'],
            defaults={
                'name': cat_data['name'],
                'shop': shop
            }
        )

    # Удаление старых товаров магазина перед обновлением прайса
    Product.objects.filter(category__shop=shop).delete()

    # Загрузка товаров
    for item in yaml_data.get('goods', []):
        category = Category.objects.get(id=item['category'], shop=shop)

        product, _ = Product.objects.get_or_create(
            id=item['id'],
            defaults={
                'name': item['name'],
                'model': item.get('model', ''),
                'category': category,
                'price': item['price'],
                'price_rrc': item['price_rrc'],
                'quantity': item['quantity']
            }
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
                defaults={'value': str(param_value)}  # строка
            )

    return {'Status': True}
