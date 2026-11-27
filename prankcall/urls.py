from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from pranks import views

admin.site.site_header = "TechMagnetStudio Admin"
admin.site.site_title = "TechMagnetStudio"
admin.site.index_title = "Welcome TechMagnetStudio"

urlpatterns = [
    path("", views.landing, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/login/"), name="logout"),
    path("admin-login/", views.admin_login, name="admin_login"),

    path("password-reset/",
         auth_views.PasswordResetView.as_view(
             template_name="registration/password_reset_form.html",
             email_template_name="email/password_reset_email.txt",
             subject_template_name="email/password_reset_subject.txt",
         ), name="password_reset"),
    path("password-reset/done/",
         auth_views.PasswordResetDoneView.as_view(
             template_name="registration/password_reset_done.html"
         ), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(
             template_name="registration/password_reset_confirm.html",
             success_url="/password-reset/complete/",
         ), name="password_reset_confirm"),
    path("password-reset/complete/",
         auth_views.PasswordResetCompleteView.as_view(
             template_name="registration/password_reset_complete.html"
         ), name="password_reset_complete"),

    path("payment/", views.payment, name="payment"),
    path("payment/request/", views.payment_request, name="payment_request"),
    path("admin-portal/", views.admin_portal, name="admin_portal"),
    path("admin-portal/logout/", auth_views.LogoutView.as_view(next_page="/admin-login/"), name="admin_logout"),
    path("admin-portal/activate/<int:user_id>/", views.admin_activate, name="admin_activate"),
    path("admin-portal/deactivate/<int:user_id>/", views.admin_deactivate, name="admin_deactivate"),
    path("admin-portal/decline/<int:user_id>/", views.admin_decline, name="admin_decline"),
    path("admin-portal/test-email/", views.admin_test_email, name="admin_test_email"),
    path("call/<str:pid>/", views.call, name="call"),
    path("api/pranks/<str:pid>/track/", views.track, name="track"),
    path("api/pranks/<str:pid>/delete/", views.delete, name="delete"),
    path("django-admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ===== Phase 1: live call routes (additive) =====
from pranks import views as _pranks_views
urlpatterns += [
    path("creator-call/<str:pid>/", _pranks_views.creator_call, name="creator_call"),
    path("api/pranks/<str:pid>/signal/post/", _pranks_views.api_signal_post, name="signal_post"),
    path("api/pranks/<str:pid>/signal/get/", _pranks_views.api_signal_get, name="signal_get"),
    path("api/turn-credentials/", _pranks_views.api_turn_credentials, name="turn_credentials"),
    path("api/pranks/<str:pid>/state/", _pranks_views.api_state, name="call_state"),
]
