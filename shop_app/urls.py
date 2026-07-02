from django.urls import include, path
from rest_framework.routers import DefaultRouter

from shop_app.views import ContactViewSet, HealthCheckView, ProductViewSet
from shop_app.views_orders import (
    BasketAPIView,
    BasketDeleteView,
    OrderConfirmView,
    OrderStatusView,
    OrderViewSet,
)
from shop_app.views_partner import PartnerOrdersView, PartnerStateView, PartnerUpdate
from shop_app.views_user import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    RegisterAccount,
    RegisterConfirmView,
    ResetPasswordConfirmView,
    ResetPasswordView, ResetPasswordValidateView,
)

# Роутер для ViewSet
router = DefaultRouter()
# Товары
router.register(r"products", ProductViewSet)
# Контакты
router.register(r"contacts", ContactViewSet, basename="contact")

# Заказы
router.register(r"orders", OrderViewSet, basename="order")

urlpatterns = [
    # Здоровье сервера
    path("health/", HealthCheckView.as_view(), name="health_check"),
    # Обновление прайса поставщика
    path("partner/update", PartnerUpdate.as_view(), name="partner-update"),
    # Управление состоянием магазина
    path("partner/state", PartnerStateView.as_view(), name="partner-state"),
    # Получение заказов поставщиком
    path("partner/orders/", PartnerOrdersView.as_view(), name="partner-orders"),
    # Регистрация и подтверждение пользователя
    path("user/register/", RegisterAccount.as_view(), name="user-register"),
    path(
        "user/register/confirm/", RegisterConfirmView.as_view(), name="register-confirm"
    ),
    # JWT (вход и обновление токена)
    path("user/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("user/token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    # Корзина
    path("basket/", BasketAPIView.as_view(), name="basket"),
    path("basket/<int:items_id>/", BasketDeleteView.as_view(), name="basket-delete"),
    # Подтверждение заказа
    path("order/confirm/", OrderConfirmView.as_view(), name="order-confirm"),
    # Изменение статуса заказа
    path("order/status/", OrderStatusView.as_view(), name="order-status"),
    # Восстановление пароля
    path("user/password/reset/", ResetPasswordView.as_view(), name="password-reset"),
    path('user/password/reset/confirm/', ResetPasswordConfirmView.as_view(), name='password-reset-set-new'),
    path(
        "user/password/reset/confirm/<str:uidb64>/<str:token>/",
        ResetPasswordValidateView.as_view(),
        name="password-reset-confirm"
    ),
    # Подключение роутера с ViewSet
    path("", include(router.urls)),
]
