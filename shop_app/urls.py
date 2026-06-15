from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import PartnerUpdate, RegisterAccount, ProductViewSet

# Роутер для ViewSet
router = DefaultRouter()
# Регистрация товаров в router
router.register(r'products', ProductViewSet)

urlpatterns = [
    # Обновление прайса поставщика
    path('partner/update', PartnerUpdate.as_view(), name='partner-update'),

    # Регистрация пользователя
    path('user/register', RegisterAccount.as_view(), name='user-register'),

    # JWT (вход и обновление токена)
    path('user/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('user/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Подключение роутера с ViewSet
    path('api/v1/', include(router.urls)),
]
