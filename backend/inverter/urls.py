from django.urls import path
from .views import InverterStatusView, InverterControlView, InverterOptionsView

urlpatterns = [
    path('status/', InverterStatusView.as_view(), name='inverter-status'),
    path('control/', InverterControlView.as_view(), name='inverter-control'),
    path('options/', InverterOptionsView.as_view(), name='inverter-options'),
]
