from shop_app.models import Shop, Category, Product


def import_shop_data_from_yaml(yaml_data):
    """
    Функция импорта товаров из YAML
    """
    shop_name = yaml_data.get('shop')
    if not shop_name:
        return {'Status': False, 'Error': 'В файле не указано название магазина'}

    # Создание магазина
    shop, is_created = Shop.objects.get_or_create(
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

    # Загрузка товаров
    for item in yaml_data.get('goods', []):
        category = Category.objects.get(id=item['category'], shop=shop)

        Product.objects.get_or_create(
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

    return {'Status': True}