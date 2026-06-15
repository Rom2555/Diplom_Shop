from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import PartnerUpdate, RegisterAccount, ProductListView

urlpatterns = [
    # Обновление прайса поставщика
    path('partner/update', PartnerUpdate.as_view(), name='partner-update'),

    # Регистрация пользователя
    path('user/register', RegisterAccount.as_view(), name='user-register'),

    # JWT (вход и обновление токена)
    path('user/login', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('user/token/refresh', TokenRefreshView.as_view(), name='token_refresh'),

    # Продукты
    path('products/', ProductListView.as_view(), name='product-list'),
]
