import yaml
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from shop_app.models import Product, Contact
from shop_app.serializers import YAMLUploadSerializer, RegisterSerializer, ContactSerializer
from shop_app.services import import_shop_data_from_yaml
from .serializers import ProductSerializer


@extend_schema(
    auth=[],
    tags=['Partner'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'file': {
                    'type': 'string',
                    'format': 'binary',
                    'description': 'YAML файл с прайс-листом поставщика'
                }
            },
            'required': ['file']
        }
    },
    responses={200: {'type': 'object', 'properties': {'Status': {'type': 'boolean'}}}}
)
class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика (импорт YAML файла).
    """
    permission_classes = [AllowAny] # Права доступа для всех
    def post(self, request, *args, **kwargs):
        # Валидация входящих данных через сериализатор
        serializer = YAMLUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Проверенный файл
        yaml_file = serializer.validated_data['file']

        try:
            # Чтение файла и парсинг YAML
            # safe_load защита от выполнения кода в YAML
            yaml_data = yaml.safe_load(yaml_file.read())
        except yaml.YAMLError:
            return Response(
                {'Status': False, 'Error': 'Неверный формат YAML файла'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'Status': False, 'Error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Передача данных сервису
        result = import_shop_data_from_yaml(yaml_data)

        if result.get('Status'):
            return Response({'Status': True}, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['User'],
    auth=[],
    request=RegisterSerializer,
    responses={201: {'type': 'object', 'properties': {
        'Status': {'type': 'boolean'},
        'refresh': {'type': 'string'},
        'access': {'type': 'string'}
    }}}
)
class RegisterAccount(APIView):
    """
    Регистрация нового пользователя с выдачей JWT токенов
    """
    permission_classes = [AllowAny] # Права доступа для всех
    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # Генерация JWT токенов
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'Status': True,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            },
            status=status.HTTP_201_CREATED
        )


@extend_schema(
    tags=['Products'],
    auth=[],
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

    permission_classes = [IsAuthenticated] # Допускает только пользователей с токеном
    serializer_class = ContactSerializer

    # http методы только GET/POST/DELETE (кроме PUT/PATCH)
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        # Фильтр. Пользователь видит только свои контакты
        return Contact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Автопривязка контактов к пользователю
        serializer.save(user=self.request.user)