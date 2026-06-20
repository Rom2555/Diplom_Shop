from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from shop_app.models import Product, Contact
from shop_app.serializers import ContactSerializer
from .serializers import ProductSerializer


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

    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer

    # http методы только GET/POST/DELETE
    http_method_names = ['get', 'post', 'delete']

    queryset = Contact.objects.none()

    def get_queryset(self):
        # Фильтр. Пользователь видит только свои контакты
        return Contact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Автопривязка контактов к пользователю
        serializer.save(user=self.request.user)
