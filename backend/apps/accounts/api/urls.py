from django.urls import path

from apps.accounts.api import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path(
        "auth/password-reset/request",
        views.PasswordResetRequestView.as_view(),
        name="auth-password-reset-request",
    ),
    path(
        "auth/password-reset/verify",
        views.PasswordResetVerifyView.as_view(),
        name="auth-password-reset-verify",
    ),
    path(
        "auth/password-reset/confirm",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("auth/password/change", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("me", views.MeView.as_view(), name="me"),
    path("me/branches", views.MyBranchesView.as_view(), name="me-branches"),
]
