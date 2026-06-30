from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shop_app.models import Contact, Product
from shop_app.serializers import ContactSerializer

from .serializers import ProductSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Список всех товаров",
        tags=["Products"],
    ),
    retrieve=extend_schema(
        summary="Получить информацию о товаре по ID",
        tags=["Products"],
    ),
)
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Product.objects.all()
        .select_related("category")
        .prefetch_related("product_parameters")
    )
    serializer_class = ProductSerializer
    lookup_field = "original_id"


@extend_schema_view(
    list=extend_schema(
        summary="Список всех контактов",
        tags=["Contacts"],
    ),
    create=extend_schema(
        summary="Добавить новый контакт",
        tags=["Contacts"],
    ),
    retrieve=extend_schema(
        summary="Получить контакт по id",
        tags=["Contacts"],
    ),
    destroy=extend_schema(summary="Удалить контакт по id", tags=["Contacts"]),
)
class ContactViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer

    # http методы только GET/POST/DELETE
    http_method_names = ["get", "post", "delete"]

    queryset = Contact.objects.none()

    def get_queryset(self):
        # Фильтр. Пользователь видит только свои контакты
        return Contact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Автопривязка контактов к пользователю
        serializer.save(user=self.request.user)


@extend_schema(
    tags=["System"],
    summary="Проверка работоспособности сервера",
    responses={200: {"type": "object", "properties": {"status": {"type": "string"}}}},
)
class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})
