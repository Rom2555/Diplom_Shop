from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from shop_app.mail import send_password_reset_email, send_registration_email
from shop_app.models import ConfirmEmailToken
from shop_app.serializers import (
    RegisterSerializer,
    ResetPasswordQuerySerializer,
    TokenConfirmSerializer, StatusResponseSerializer, PasswordResetConfirmSerializer,
)


@extend_schema(
    tags=["User"],
    summary="Подтверждение email и активация аккаунта",
    request=TokenConfirmSerializer,
    responses={
        200: {
            "type": "object",
            "properties": {
                "Status": {"type": "boolean"},
                "Message": {"type": "string"},
            },
        }
    },
)
class RegisterConfirmView(APIView):

    def post(self, request, *args, **kwargs):
        token = request.data.get("token")
        if not token:
            return Response({"Status": False, "Error": "Нет токена"}, status=400)

        try:
            token_obj = ConfirmEmailToken.objects.get(key=token)
            if token_obj.user.is_active:
                return Response(
                    {"Status": False, "Error": "Аккаунт уже подтвержден"}, status=400
                )

            token_obj.user.is_active = True  # Активация пользователя
            token_obj.user.save()
            token_obj.delete()  # Удаление токена после использования

            return Response(
                {
                    "Status": True,
                    "Message": "Успешная регистрация! Вы можете войти под своим логином/паролем",
                }
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
            {
                "Status": True,
                "messages": "На ваш email отправлено письмо для подтверждения регистрации",
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["User"],
    summary="Запрос на сброс пароля. Отправляет ссылку с токеном на email",
    request=ResetPasswordQuerySerializer,
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
            {
                "Status": True,
                "messages": "На ваш email отправлено письмо для сброса пароля.",
            },
        )


# Класс для проверки ссылки (GET)

class ResetPasswordValidateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["User"],
        summary="Проверка ссылки сброса пароля из письма",
        responses={200: StatusResponseSerializer, 400: StatusResponseSerializer}
    )
    def get(self, request, uidb64, token, *args, **kwargs):
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid).first()

        if user and default_token_generator.check_token(user, token):
            return Response({
                "Status": True,
                "Message": "Сброс пароля подверждён, можно установить новый пароль",
                "uidb64": uidb64,
                "token": token
            })
        return Response({"Status": False, "Error": "Ссылка недействительна"}, status=400)


# Класс для установки пароля (POST)
class ResetPasswordConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["User"],
        summary="Установка нового пароля",
        request=PasswordResetConfirmSerializer,
        responses={200: StatusResponseSerializer, 400: StatusResponseSerializer}
    )
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "Status": False,
                "Error": serializer.errors
            }, status=400)

        # uidb64 и token из тела запроса
        uidb64 = serializer.validated_data.get('uidb64')
        token = serializer.validated_data.get('token')

        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid).first()

        if user and default_token_generator.check_token(user, token):
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({
                "Status": True,
                "Message": "Пароль успешно изменен"
            })

        return Response({
            "Status": False,
            "Error": "Ошибка валидации токена или пользователя"
        }, status=400)


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
