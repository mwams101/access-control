"""REST API (Section 8). Mirrors the web workflows via the service layer."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOwnerVisitor, IsSecurity

from . import services
from .models import Pass, VisitRequest
from .serializers import PassSerializer, VisitRequestSerializer


class VisitRequestViewSet(viewsets.ModelViewSet):
    serializer_class = VisitRequestSerializer
    permission_classes = [IsAuthenticated, IsOwnerVisitor]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        u = self.request.user
        qs = VisitRequest.objects.select_related("host").prefetch_related("party")
        if u.role in ("SECURITY", "ADMIN") or u.is_superuser:
            status_param = self.request.query_params.get("status")
            return qs.filter(status=status_param) if status_param else qs
        return qs.filter(visitor=u)

    def perform_create(self, serializer):
        u = self.request.user
        visitor = u if u.role == "VISITOR" else None
        serializer.save(visitor=visitor)

    @action(detail=True, methods=["post"], permission_classes=[IsSecurity])
    def approve(self, request, pk=None):
        visit = self.get_object()
        try:
            access_pass = services.approve_visit(visit, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PassSerializer(access_pass).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsSecurity])
    def deny(self, request, pk=None):
        visit = self.get_object()
        try:
            services.deny_visit(visit, request.user, request.data.get("reason", ""))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": visit.status})


class VerifyPassView(APIView):
    """POST /api/v1/passes/verify/ — contract for future hardware clients (v2)."""

    permission_classes = [IsSecurity]

    def post(self, request):
        token = request.data.get("token", "")
        gate = request.data.get("gate", "Main Gate")
        result = services.verify_pass(token, actor=request.user, gate=gate)
        payload = {"allowed": result.allowed, "reason": result.reason}
        if result.access_pass:
            payload["pass"] = PassSerializer(result.access_pass).data
        return Response(payload, status=200 if result.allowed else 403)


class CheckInView(APIView):
    permission_classes = [IsSecurity]

    def post(self, request, pk):
        access_pass = get_object_or_404(Pass, pk=pk)
        try:
            services.check_in(access_pass, request.user,
                              gate=request.data.get("gate", "Main Gate"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "CHECKED_IN"})


class CheckOutView(APIView):
    permission_classes = [IsSecurity]

    def post(self, request, pk):
        access_pass = get_object_or_404(Pass, pk=pk)
        try:
            services.check_out(access_pass, request.user,
                               gate=request.data.get("gate", "Main Gate"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "CHECKED_OUT"})


class OccupancyView(APIView):
    permission_classes = [IsSecurity]

    def get(self, request):
        data = VisitRequestSerializer(services.currently_inside(), many=True).data
        return Response({"count": len(data), "results": data})
