import yaml
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shop_app.models import Order, Shop
from shop_app.serializers import OrderSerializer, ShopIdQuerySerializer, YAMLUploadSerializer
from shop_app.services import import_shop_data_from_yaml


@extend_schema(
    tags=["Partner"],
    summary="Обновление прайса от поставщика (импорт YAML файла)",
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "format": "binary", "description": "YAML файл с прайс-листом поставщика"}
            },
            "required": ["file"],
        }
    },
    responses={200: {"type": "object", "properties": {"Status": {"type": "boolean"}}}},
)
class PartnerUpdate(APIView):

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = YAMLUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        yaml_file = serializer.validated_data["file"]

        try:
            # Чтение файла и парсинг YAML
            # safe_load защита от выполнения кода в YAML
            yaml_data = yaml.safe_load(yaml_file.read())
        except yaml.YAMLError:
            return Response(
                {"Status": False, "Error": "Неверный формат YAML файла"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({"Status": False, "Error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Передача данных сервису
        result = import_shop_data_from_yaml(yaml_data)

        if result.get("Status"):
            return Response({"Status": True}, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Partner"],
    summary="Управление состоянием приёма заказов поставщиком",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "shop_id": {"type": "integer", "description": "ID магазина"},
                "state": {"type": "boolean", "description": "Статус приема заказов (True/False)"},
            },
            "required": ["shop_id", "state"],
        }
    },
    responses={200: {"type": "object", "properties": {"Status": {"type": "boolean"}}}},
)
class PartnerStateView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        shop_id = request.data.get("shop_id")
        state = request.data.get("state")

        if shop_id is None or state is None:
            return Response({"Status": False, "Errors": "Укажите shop_id и state"}, status=400)

        try:
            shop = Shop.objects.get(id=shop_id)
            shop.state = state
            shop.save()
            return Response({"Status": True})
        except Shop.DoesNotExist:
            return Response({"Status": False, "Errors": "Магазин не найден"}, status=404)


@extend_schema(
    tags=["Partner"],
    summary="Список всех заказов у конкретного поставщика",
    parameters=[ShopIdQuerySerializer],
    responses={200: OrderSerializer(many=True)},
)
class PartnerOrdersView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response({"Status": False, "Error": "Укажите shop_id"}, status=400)

        # Поиск заказов с товарами этого магазина, кроме состояния - корзина
        orders = (
            Order.objects.filter(ordered_items__shop_id=shop_id)
            .exclude(state="basket")
            .distinct()
            .prefetch_related("ordered_items__product", "contact")
        )

        serializer = OrderSerializer(orders, many=True, context={"request_shop_id": int(shop_id)})
        return Response(serializer.data)
