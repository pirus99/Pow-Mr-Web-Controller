from django.contrib import admin
from django.urls import path, include
from metrics.views import PrometheusExportView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/inverter/', include('inverter.urls')),
    path('api/metrics/', include('metrics.urls')),
    path('api/automation/', include('automation.urls')),
    # Prometheus-compatible metrics endpoint at root /metrics
    path('metrics', PrometheusExportView.as_view(), name='prometheus-metrics'),
]
