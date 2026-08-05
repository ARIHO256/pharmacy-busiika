from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView, ForgotPasswordView, GoogleLoginView, MeView, MfaVerifyView,
    MyProfileView, MySecurityEventsView, PhoneLoginRequestView, PhoneLoginVerifyView,
    RegisterView, RequestEmailVerificationView, ResetPasswordView,
    SecureTokenView, SecuritySettingsView, VerifyEmailView, RequestPhoneVerificationView,
    VerifyPhoneView, LogoutView, SessionListRevokeView,
    DependentListCreateView, DependentDetailView, PatientRelationshipActionView,
    PatientRelationshipDocumentView,
)

urlpatterns = [
    path("token/", SecureTokenView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("mfa/verify/", MfaVerifyView.as_view(), name="mfa_verify"),
    path("email-verification/request/", RequestEmailVerificationView.as_view(), name="email_verification_request"),
    path("email-verification/verify/", VerifyEmailView.as_view(), name="email_verification_verify"),
    path("phone-verification/request/", RequestPhoneVerificationView.as_view(), name="phone_verification_request"),
    path("phone-verification/verify/", VerifyPhoneView.as_view(), name="phone_verification_verify"),
    path("phone-login/request/", PhoneLoginRequestView.as_view(), name="phone_login_request"),
    path("phone-login/verify/", PhoneLoginVerifyView.as_view(), name="phone_login_verify"),
    path("google/", GoogleLoginView.as_view(), name="google_login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("sessions/", SessionListRevokeView.as_view(), name="sessions"),
    path("password/forgot/", ForgotPasswordView.as_view(), name="password_forgot"),
    path("password/reset/", ResetPasswordView.as_view(), name="password_reset"),
    path("password/change/", ChangePasswordView.as_view(), name="password_change"),
    path("security/", SecuritySettingsView.as_view(), name="security_settings"),
    path("security/events/", MySecurityEventsView.as_view(), name="security_events"),
    path("register/", RegisterView.as_view(), name="register"),
    path("dependents/", DependentListCreateView.as_view(), name="dependents"),
    path("dependents/<int:pk>/", DependentDetailView.as_view(), name="dependent-detail"),
    path("dependents/<int:pk>/action/", PatientRelationshipActionView.as_view(), name="dependent-action"),
    path("dependents/<int:pk>/authority-document/", PatientRelationshipDocumentView.as_view(), name="dependent-authority-document"),
    path("me/", MeView.as_view(), name="me"),
    path("me/profile/", MyProfileView.as_view(), name="me_profile"),
]
