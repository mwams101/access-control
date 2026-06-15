from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView

from apps.accounts.mixins import SecurityRequiredMixin, VisitorRequiredMixin
from apps.reports.services import log_action

from . import services
from .forms import DecisionForm, PartyFormSet, VerifyForm, VisitRequestForm, WalkInForm
from .models import Pass, VisitRequest
from .utils import qr_data_uri


# ---------------------------------------------------------------------------
# Visitor-facing views
# ---------------------------------------------------------------------------

class MyVisitsView(VisitorRequiredMixin, ListView):
    template_name = "visits/my_visits.html"
    context_object_name = "visits"
    paginate_by = 20

    def get_queryset(self):
        return VisitRequest.objects.filter(visitor=self.request.user)


class VisitCreateView(VisitorRequiredMixin, CreateView):
    model = VisitRequest
    form_class = VisitRequestForm
    template_name = "visits/visit_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["party_formset"] = PartyFormSet(self.request.POST or None)
        return ctx

    def get_initial(self):
        u = self.request.user
        return {
            "full_name": u.get_full_name(),
            "phone": u.phone,
            "email": u.email,
        }

    def form_valid(self, form):
        form.instance.visitor = self.request.user
        form.instance.email = form.instance.email or self.request.user.email
        response = super().form_valid(form)
        party = PartyFormSet(self.request.POST, instance=self.object)
        if party.is_valid():
            party.save()
        log_action(self.request.user, "visit.requested", self.object)
        messages.success(
            self.request,
            f"Request {self.object.reference} submitted — you'll be emailed once it's reviewed.",
        )
        return response

    def get_success_url(self):
        return reverse("visits:visit_detail", args=[self.object.pk])


class VisitDetailView(DetailView):
    """Visitors see their own; staff see any (object-level check below)."""

    model = VisitRequest
    template_name = "visits/visit_detail.html"
    context_object_name = "visit"

    def get_queryset(self):
        u = self.request.user
        qs = VisitRequest.objects.select_related("host", "visitor")
        if u.is_authenticated and u.is_staff_role:
            return qs
        if u.is_authenticated:
            return qs.filter(visitor=u)
        return qs.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        access_pass = getattr(self.object, "access_pass", None)
        ctx["access_pass"] = access_pass
        if access_pass and not access_pass.revoked:
            ctx["qr_uri"] = qr_data_uri(access_pass.token)
        return ctx


# ---------------------------------------------------------------------------
# Security-facing views (gate operations)
# ---------------------------------------------------------------------------

class GateDashboardView(SecurityRequiredMixin, TemplateView):
    template_name = "security/gate_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        ctx["pending"] = VisitRequest.objects.filter(
            status=VisitRequest.Status.PENDING
        ).select_related("host")[:20]
        ctx["expected_today"] = VisitRequest.objects.filter(
            status=VisitRequest.Status.APPROVED, expected_start__date=today
        ).select_related("host")
        ctx["inside"] = services.currently_inside()
        ctx["verify_form"] = VerifyForm()
        return ctx


class VerifyPassView(SecurityRequiredMixin, FormView):
    template_name = "security/verify.html"
    form_class = VerifyForm

    def form_valid(self, form):
        code = form.cleaned_data["code"].strip()
        gate = form.cleaned_data["gate"]
        if code.upper().startswith("VR-"):
            result = services.verify_by_reference(code, actor=self.request.user, gate=gate)
        else:
            result = services.verify_pass(code, actor=self.request.user, gate=gate)
        return self.render_to_response(
            self.get_context_data(form=VerifyForm(initial={"gate": gate}), result=result, gate=gate)
        )


class CheckInActionView(SecurityRequiredMixin, TemplateView):
    """POST-only state changes from the verify screen."""

    http_method_names = ["post"]

    def post(self, request, pk, action):
        access_pass = get_object_or_404(Pass.objects.select_related("visit"), pk=pk)
        gate = request.POST.get("gate", "Main Gate")
        try:
            if action == "in":
                services.check_in(access_pass, request.user, gate=gate)
                messages.success(request, f"{access_pass.visit.display_name} checked in.")
            elif action == "out":
                services.check_out(access_pass, request.user, gate=gate)
                messages.success(request, f"{access_pass.visit.display_name} checked out.")
            else:
                messages.error(request, "Unknown action.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(request.POST.get("next") or "visits:gate_dashboard")


class WalkInCreateView(SecurityRequiredMixin, CreateView):
    model = VisitRequest
    form_class = WalkInForm
    template_name = "security/walkin_form.html"
    success_url = reverse_lazy("visits:gate_dashboard")

    def form_valid(self, form):
        form.instance.expected_start = form.instance.expected_start or timezone.now()
        self.object = form.save()
        result = services.register_walk_in(
            self.object, self.request.user,
            gate=form.cleaned_data["gate"], zones=form.cleaned_data["zones"],
        )
        if result.allowed:
            messages.success(self.request, f"Walk-in {self.object.display_name} checked in.")
        else:
            messages.error(self.request, f"Entry denied: {result.reason}")
        return redirect(self.success_url)


class PendingApprovalsView(SecurityRequiredMixin, ListView):
    template_name = "security/pending_list.html"
    context_object_name = "visits"
    paginate_by = 25

    def get_queryset(self):
        return VisitRequest.objects.filter(
            status=VisitRequest.Status.PENDING
        ).select_related("host", "visitor")


class DecideVisitView(SecurityRequiredMixin, FormView):
    """Approve or deny a pending request (FR-07)."""

    template_name = "security/decide.html"
    form_class = DecisionForm

    def dispatch(self, request, *args, **kwargs):
        self.visit = get_object_or_404(VisitRequest, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["visit"] = self.visit
        return ctx

    def form_valid(self, form):
        decision = self.request.POST.get("decision")
        try:
            if decision == "approve":
                services.approve_visit(
                    self.visit, self.request.user,
                    zones=form.cleaned_data["zones"],
                    single_entry=form.cleaned_data["single_entry"],
                )
                messages.success(self.request, f"{self.visit.reference} approved — pass issued.")
            else:
                services.deny_visit(self.visit, self.request.user, form.cleaned_data["reason"])
                messages.warning(self.request, f"{self.visit.reference} denied.")
        except ValueError as exc:
            messages.error(self.request, str(exc))
        return redirect("visits:pending")


class OccupancyView(SecurityRequiredMixin, ListView):
    """Live 'currently inside' list (FR-15)."""

    template_name = "security/occupancy.html"
    context_object_name = "inside"

    def get_queryset(self):
        qs = services.currently_inside()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(full_name__icontains=q) | Q(entity_name__icontains=q)
                | Q(host__first_name__icontains=q) | Q(host__last_name__icontains=q)
            )
        return qs
