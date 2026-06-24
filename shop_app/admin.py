from django.contrib import admin

from .models import Category, Parameter, Product, ProductParameter, Shop

# Register your models here.


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "state")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("original_id", "name", "shop")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("original_id", "name", "model", "price", "quantity", "category")


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ("product", "parameter", "value")
