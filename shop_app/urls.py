from django.urls import path
from .views import PartnerUpdate

urlpatterns = [
    # Обновление прайса поставщика
    path('partner/update', PartnerUpdate.as_view(), name='partner-update'),
]