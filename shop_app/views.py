from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import yaml

from shop_app.services import import_shop_data_from_yaml
from shop_app.serializers import YAMLUploadSerializer


class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика (импорт YAML файла).
    """
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