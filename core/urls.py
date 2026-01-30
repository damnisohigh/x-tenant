from django.urls import path

from core.views import LoginView, MeView, OrganizationCreateView, RegisterView

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path(
        "organizations",
        OrganizationCreateView.as_view(),
        name="organizations-create",
    ),
    path("users/me", MeView.as_view(), name="users-me"),
]
