from django.urls import path
from .views import (
    AutomationRuleListCreateView,
    AutomationRuleDetailView,
    AutomationRuleToggleView,
    AutomationLogListView,
)

urlpatterns = [
    path('rules/', AutomationRuleListCreateView.as_view(), name='automation-rule-list'),
    path('rules/<int:pk>/', AutomationRuleDetailView.as_view(), name='automation-rule-detail'),
    path('rules/<int:pk>/toggle/', AutomationRuleToggleView.as_view(), name='automation-rule-toggle'),
    path('logs/', AutomationLogListView.as_view(), name='automation-log-list'),
]
