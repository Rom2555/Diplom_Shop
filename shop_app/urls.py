from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from shop_app.views import PartnerUpdate, RegisterAccount, ProductViewSet, ContactViewSet, BasketAPIView, \
    BasketDeleteView

# Роутер для ViewSet
router = DefaultRouter()
# Регистрация товаров в router
router.register(r'products', ProductViewSet)
# Регистрация контактов
router.register(r'contacts', ContactViewSet, basename="contact")

urlpatterns = [
    # Обновление прайса поставщика
    path('partner/update', PartnerUpdate.as_view(), name='partner-update'),

    # Регистрация пользователя
    path('user/register', RegisterAccount.as_view(), name='user-register'),

    # JWT (вход и обновление токена)
    path('user/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('user/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Корзина
    path('basket/', BasketAPIView.as_view(), name='basket'),

    path('basket/<int:items_id>/', BasketDeleteView.as_view(), name='basket-delete'),

    # Подключение роутера с ViewSet
    path('', include(router.urls)),
]
