from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.mixins import AdminRequiredMixin
from apps.reports.services import log_action

from .forms import BlacklistForm, ZoneForm
from .models import Blacklist, Zone


class ZoneListView(AdminRequiredMixin, ListView):
    model = Zone
    template_name = "access/zone_list.html"
    context_object_name = "zones"


class ZoneCreateView(AdminRequiredMixin, CreateView):
    model = Zone
    form_class = ZoneForm
    template_name = "access/zone_form.html"
    success_url = reverse_lazy("access:zones")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, "zone.created", self.object)
        messages.success(self.request, f"Zone '{self.object.name}' created.")
        return response


class ZoneUpdateView(AdminRequiredMixin, UpdateView):
    model = Zone
    form_class = ZoneForm
    template_name = "access/zone_form.html"
    success_url = reverse_lazy("access:zones")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, "zone.updated", self.object)
        return response


class BlacklistListView(AdminRequiredMixin, ListView):
    model = Blacklist
    template_name = "access/blacklist_list.html"
    context_object_name = "entries"
    paginate_by = 25


class BlacklistCreateView(AdminRequiredMixin, CreateView):
    model = Blacklist
    form_class = BlacklistForm
    template_name = "access/blacklist_form.html"
    success_url = reverse_lazy("access:blacklist")

    def form_valid(self, form):
        form.instance.added_by = self.request.user
        response = super().form_valid(form)
        log_action(self.request.user, "blacklist.added", self.object,
                   metadata={"reason": self.object.reason})
        messages.success(self.request, "Blacklist entry added.")
        return response


class BlacklistUpdateView(AdminRequiredMixin, UpdateView):
    model = Blacklist
    form_class = BlacklistForm
    template_name = "access/blacklist_form.html"
    success_url = reverse_lazy("access:blacklist")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, "blacklist.updated", self.object)
        return response
