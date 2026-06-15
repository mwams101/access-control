from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.SignInView.as_view(), name="login"),
    path("logout/", views.SignOutView.as_view(), name="logout"),
    path("signup/", views.VisitorSignUpView.as_view(), name="signup"),
    path("post-login/", views.post_login_redirect, name="post_login"),
]
