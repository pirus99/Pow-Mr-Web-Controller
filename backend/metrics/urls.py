from django.urls import path
from .views import SolaxMetricsView, BatteryMetricsView, PrometheusExportView

urlpatterns = [
    path('solax/', SolaxMetricsView.as_view(), name='metrics-solax'),
    path('battery/', BatteryMetricsView.as_view(), name='metrics-battery'),
    path('prometheus/', PrometheusExportView.as_view(), name='metrics-prometheus'),
]
