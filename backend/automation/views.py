from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AutomationLog, AutomationRule
from .serializers import AutomationLogSerializer, AutomationRuleSerializer


class AutomationRuleListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/automation/rules/"""
    queryset = AutomationRule.objects.all()
    serializer_class = AutomationRuleSerializer


class AutomationRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/automation/rules/<id>/"""
    queryset = AutomationRule.objects.all()
    serializer_class = AutomationRuleSerializer


class AutomationRuleToggleView(APIView):
    """POST /api/automation/rules/<id>/toggle/ – enable/disable a rule."""

    def post(self, request, pk):
        try:
            rule = AutomationRule.objects.get(pk=pk)
        except AutomationRule.DoesNotExist:
            return Response({'error': 'Rule not found'}, status=status.HTTP_404_NOT_FOUND)
        rule.enabled = not rule.enabled
        rule.save(update_fields=['enabled'])
        return Response({'id': rule.id, 'enabled': rule.enabled})


class AutomationLogListView(generics.ListAPIView):
    """GET /api/automation/logs/ – list automation log entries."""
    serializer_class = AutomationLogSerializer

    def get_queryset(self):
        qs = AutomationLog.objects.select_related('rule').order_by('-timestamp')
        rule_id = self.request.query_params.get('rule')
        if rule_id:
            qs = qs.filter(rule_id=rule_id)
        return qs[:100]
