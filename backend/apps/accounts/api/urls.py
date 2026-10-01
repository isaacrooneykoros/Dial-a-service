from django.urls import path

from apps.accounts.api import invitation_views as inv
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
    path("auth/invitations/accept", inv.InvitationAcceptView.as_view(), name="invitation-accept"),
    path("auth/invitations/<str:token>", inv.PublicInvitationView.as_view(), name="invitation"),
    path(
        "auth/invitations/<str:token>/send-code",
        inv.InvitationSendCodeView.as_view(),
        name="invitation-send-code",
    ),
    path(
        "auth/invitations/<str:token>/verify",
        inv.InvitationVerifyView.as_view(),
        name="invitation-verify",
    ),
    path("console/invitations", inv.InvitationListCreateView.as_view(), name="invitations"),
    path(
        "console/invitations/<uuid:pk>/resend",
        inv.InvitationResendView.as_view(),
        name="invitation-resend",
    ),
    path(
        "console/invitations/<uuid:pk>/cancel",
        inv.InvitationCancelView.as_view(),
        name="invitation-cancel",
    ),
    path("me/pin", inv.MyPinView.as_view(), name="me-pin"),
    path("me", views.MeView.as_view(), name="me"),
    path("me/branches", views.MyBranchesView.as_view(), name="me-branches"),
]
