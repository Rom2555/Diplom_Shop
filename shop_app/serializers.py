from rest_framework import serializers


class YAMLUploadSerializer(serializers.Serializer):
    """
    Сериализатор для валидации загружаемого YAML файла.
    """
    file = serializers.FileField(
        help_text='YAML файл с прайс-листом поставщика'
    )