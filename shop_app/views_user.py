from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from shop_app.mail import send_password_reset_email, send_registration_email
from shop_app.models import ConfirmEmailToken
from shop_app.serializers import RegisterSerializer, TokenConfirmSerializer


@extend_schema(
    tags=["User"],
    summary="Подтверждение email и активация аккаунта",
    request=TokenConfirmSerializer,
    responses={200: {"type": "object", "properties": {"Status": {"type": "boolean"}, "Message": {"type": "string"}}}},
)
class RegisterConfirmView(APIView):

    def post(self, request, *args, **kwargs):
        token = request.data.get("token")
        if not token:
            return Response({"Status": False, "Error": "Нет токена"}, status=400)

        try:
            token_obj = ConfirmEmailToken.objects.get(key=token)
            if token_obj.user.is_active:
                return Response({"Status": False, "Error": "Аккаунт уже подтвержден"}, status=400)

            token_obj.user.is_active = True  # Активация пользователя
            token_obj.user.save()
            token_obj.delete()  # Удаление токена после использования

            return Response(
                {"Status": True, "Message": "Успешная регистрация! Вы можете войти под своим логином/паролем"}
            )
        except ConfirmEmailToken.DoesNotExist:
            return Response({"Status": False, "Error": "Неверный токен"}, status=400)


@extend_schema(
    tags=["User"],
    summary="Регистрация нового пользователя с выдачей JWT токенов и отправкой письма подтверждения",
    request=RegisterSerializer,
    responses={
        201: {
            "type": "object",
            "properties": {
                "Status": {"type": "boolean"},
            },
        }
    },
)
class RegisterAccount(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # Подтверждение регистрации Яндекс
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=user.id)

        # Отправка письма
        send_registration_email(user, token)

        return Response(
            {"Status": True, "messages": "На ваш email отправлено письмо для подтверждения регистрации"},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["User"],
    summary="Запрос на сброс пароля. Отправляет ссылку с токеном на email",
    request={
        "application/json": {
            "type": "object",
            "properties": {"email": {"type": "string", "format": "email", "description": "Email пользователя"}},
            "required": ["email"],
        }
    },
    responses={200: {"type": "object", "properties": {"Status": {"type": "boolean"}}}},
)
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        if not email:
            return Response({"Status": False, "Error": "Укажите email"}, status=400)

        try:
            user = User.objects.filter(email=email).first()
            if not user:
                pass
            else:
                # Токен
                token = default_token_generator.make_token(user)
                # Отправка письма
                send_password_reset_email(user, token)
        except User.DoesNotExist:
            pass  # Безопасность. Не сообщать что пользователь не найден

        return Response(
            {"Status": True, "messages": "На ваш email отправлено письмо для сброса пароля."},
        )


@extend_schema(
    tags=["User"],
    summary="Установка нового пароля после получения токена",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID пользователя из письма"},
                "token": {"type": "string", "description": "Токен из письма"},
                "new_password": {"type": "string", "description": "Новый пароль"},
            },
            "required": ["user_id", "token", "new_password"],
        }
    },
    responses={200: {"type": "object", "properties": {"Status": {"type": "boolean"}}}},
)
class ResetPasswordConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not all([user_id, token, new_password]):
            return Response({"Status": False, "Error": "Заполните все поля: user_id, token, new_password"}, status=400)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"Status": False, "Error": "Пользователь не найден"}, status=400)

        # Проверка валидности токена
        if default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response({"Status": True, "Message": "Пароль успешно изменен"})
        else:
            return Response({"Status": False, "Error": "Неверный токен"}, status=400)


# Обертка для TokenObtainPairView
@extend_schema(
    tags=["User"],
    summary="Вход по логину и паролю, получение токенов",
)
class CustomTokenObtainPairView(TokenObtainPairView):
    pass


# Обертка для TokenRefreshView
@extend_schema(
    tags=["User"],
    summary="Обновление access-токена",
)
class CustomTokenRefreshView(TokenRefreshView):
    pass
