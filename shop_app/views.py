from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import yaml

from shop_app.services import import_shop_data_from_yaml


class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика (импорт YAML файла).
    """
    def post(self, request, *args, **kwargs):
        # Проверяем, передал ли пользователь файл
        yaml_file = request.FILES.get('file')
        if not yaml_file:
            return Response(
                {'Status': False, 'Error': 'Необходимо передать файл (поле "file")'},
                status=status.HTTP_400_BAD_REQUEST
            )

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
