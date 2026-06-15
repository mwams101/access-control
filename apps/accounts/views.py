from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import VisitorSignUpForm


class SignInView(LoginView):
    template_name = "registration/login.html"


class SignOutView(LogoutView):
    pass


class VisitorSignUpView(CreateView):
    form_class = VisitorSignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("accounts:post_login")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


@login_required
def post_login_redirect(request):
    """Send each role to its home screen."""
    user = request.user
    if user.is_admin_role:
        return redirect("reports:dashboard")
    if user.is_security_role:
        return redirect("visits:gate_dashboard")
    return redirect("visits:my_visits")
