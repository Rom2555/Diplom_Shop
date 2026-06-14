from django.contrib.auth.models import User
from rest_framework import serializers


class RegisterSerializer(serializers.ModelSerializer):
    """
    Сериализатор для регистрации нового пользователя
    """
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password')

    def create(self, validated_data):
        # Хеширование пароля перед сохранением
        user = User(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class YAMLUploadSerializer(serializers.Serializer):
    """
    Сериализатор для валидации загружаемого YAML файла.
    """
    file = serializers.FileField(
        help_text='YAML файл с прайс-листом поставщика'
    )
