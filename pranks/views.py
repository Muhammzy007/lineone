import json
import logging
import os
import re
import shutil
import subprocess
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Prank, UserProfile

logger = logging.getLogger(__name__)


# ---------- decorators ----------

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/admin-login/?next={request.path}")
        if not (request.user.is_staff and request.user.is_active):
            return redirect(f"/admin-login/?next={request.path}&denied=1")
        return view_func(request, *args, **kwargs)
    return _wrapped


# ---------- helpers ----------

def invalidate_user_sessions(user_id):
    for s in Session.objects.filter(expire_date__gte=timezone.now()):
        data = s.get_decoded()
        if data.get("_auth_user_id") == str(user_id):
            s.delete()


def crop_video_black_bars(input_path, output_path=None):
    """
    Detect and crop black bars from an uploaded video.
    Returns True if cropped, False otherwise. Never raises.
    """
    if not shutil.which("ffmpeg"):
        logger.warning("ffmpeg not installed, skipping crop")
        return False

    if output_path is None:
        output_path = input_path

    try:
        detect_cmd = [
            "ffmpeg", "-hide_banner", "-i", input_path,
            "-vf", "cropdetect=24:2:0", "-t", "10", "-f", "null", "-"
        ]
        result = subprocess.run(detect_cmd, capture_output=True, text=True, timeout=120)
        matches = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", result.stderr)
        if not matches:
            logger.info("No crop detected for %s", input_path)
            return False

        w, h, x, y = map(int, matches[-1])

        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", input_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        dims = probe_result.stdout.strip().split(",")
        if len(dims) == 2:
            orig_w, orig_h = int(dims[0]), int(dims[1])
            if (w, h) == (orig_w, orig_h):
                logger.info("Crop matches full frame for %s, nothing to do", input_path)
                return False

        tmp_output = output_path + ".cropped.mp4"
        crop_cmd = [
            "ffmpeg", "-hide_banner", "-y", "-i", input_path,
            "-vf", f"crop={w}:{h}:{x}:{y}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            tmp_output
        ]
        crop_result = subprocess.run(crop_cmd, capture_output=True, text=True, timeout=600)
        if crop_result.returncode != 0:
            logger.warning("ffmpeg crop failed: %s", crop_result.stderr[-500:])
            if os.path.exists(tmp_output):
                os.remove(tmp_output)
            return False

        os.replace(tmp_output, output_path)
        logger.info("Cropped %s to %dx%d+%d+%d", input_path, w, h, x, y)
        return True

    except subprocess.TimeoutExpired:
        logger.warning("Crop timed out for %s", input_path)
        return False
    except Exception as exc:
        logger.exception("Crop error for %s: %s", input_path, exc)
        return False


# ---------- forms ----------

class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class PrankForm(forms.ModelForm):
    ring_delay = forms.IntegerField(
        min_value=0, max_value=30, initial=2,
        help_text="Seconds before the call starts ringing.",
    )
    call_timeout = forms.IntegerField(
        min_value=0, max_value=600, initial=0, required=False,
        help_text="Auto-end the call after this many seconds. Leave 0 for no auto-end.",
    )

    class Meta:
        model = Prank
        fields = [
            "caller_name", "style", "avatar_url",
            "media_type", "photo_file", "video_file",
            "ring_delay", "call_timeout", "reveal_message",
        ]
        widgets = {
            "media_type": forms.RadioSelect(),
        }

    def clean_call_timeout(self):
        v = self.cleaned_data.get("call_timeout")
        return v or 0

    def clean(self):
        cleaned = super().clean()
        media_type = cleaned.get("media_type")
        photo = cleaned.get("photo_file")
        video = cleaned.get("video_file")

        if media_type == "photo" and not photo:
            self.add_error("photo_file", "Please upload a photo when 'Upload a photo' is selected.")
        if media_type == "video" and not video:
            self.add_error("video_file", "Please upload a video when 'Upload a video' is selected.")
        if media_type == "video" and video:
            name = (video.name or "").lower()
            if not any(name.endswith(ext) for ext in (".mp4", ".webm", ".mov", ".m4v")):
                self.add_error("video_file", "Please upload an MP4, WEBM, MOV, or M4V file.")
        return cleaned


# ---------- helpers ----------

def get_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _send(to, subject, template, ctx):
    if not to:
        return False
    try:
        body = render_to_string(template, ctx)
        sent = send_mail(subject, "", settings.DEFAULT_FROM_EMAIL, [to], html_message=body, fail_silently=False)
        return bool(sent)
    except Exception as exc:
        logger.exception("Email send failed to %s: %s", to, exc)
        return False


def _safe_next(request, fallback):
    nxt = request.GET.get("next") or request.POST.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback


# ---------- public pages ----------

def landing(request):
    profile = None
    if request.user.is_authenticated:
        profile = get_profile(request.user)
    return render(request, "pranks/landing.html", {"profile": profile})


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            get_profile(user)
            login(request, user)
            _send(user.email, f"Welcome to {settings.APP_NAME}", "email/welcome.html",
                  {"user": user, "app_name": settings.APP_NAME})
            messages.success(request, "Welcome! Your account is ready.")
            return redirect("payment")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff and request.user.is_active:
        return redirect(_safe_next(request, "/admin-portal/"))

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            error = "Invalid username or password."
        elif not (user.is_staff and user.is_active):
            error = "This account does not have admin access."
        else:
            login(request, user)
            return redirect(_safe_next(request, "/admin-portal/"))

    denied = request.GET.get("denied") == "1"
    return render(request, "registration/admin_login.html", {
        "error": error,
        "denied": denied,
        "next": request.GET.get("next", ""),
    })


# ---------- dashboard ----------

@login_required
def dashboard(request):
    profile = get_profile(request.user)
    if not profile.has_active_access():
        return redirect("payment")

    link = None
    if request.method == "POST":
        form = PrankForm(request.POST, request.FILES)
        if form.is_valid():
            prank = form.save(commit=False)
            prank.owner = request.user
            prank.save()
            # --- Server-side crop: restores the "properly filled" behavior ---
            if prank.media_type == "video" and prank.video_file:
                crop_video_black_bars(prank.video_file.path)
            return redirect(f"/dashboard/?created={prank.id}")
    else:
        form = PrankForm(initial={"style": "whatsapp"})

    created = request.GET.get("created")
    created_prank = None
    if created:
        created_prank = Prank.objects.filter(pk=created, owner=request.user).first()
        if created_prank:
            link = request.build_absolute_uri(f"/call/{created}/")

    mine = Prank.objects.filter(owner=request.user)
    return render(request, "pranks/home.html",
                  {"form": form, "link": link, "prank": created_prank, "mine": mine, "profile": profile})


# ---------- payment ----------

@login_required
def payment(request):
    profile = get_profile(request.user)
    return render(request, "pranks/payment.html", {"profile": profile})


@login_required
@require_POST
def payment_request(request):
    profile = get_profile(request.user)
    profile.activation_requested = True
    profile.activation_requested_at = timezone.now()
    profile.save()
    _send(settings.ADMIN_NOTIFICATION_EMAIL,
          f"New payment approval request from {request.user.username}",
          "email/payment_request.html",
          {"user": request.user, "app_name": settings.APP_NAME})
    messages.success(request, "Request sent. An admin will verify your payment shortly.")
    return redirect("payment")


# ---------- admin ----------

@admin_required
def admin_portal(request):
    pending = UserProfile.objects.filter(activation_requested=True).select_related("user")
    all_profiles = UserProfile.objects.select_related("user").order_by("-payment_verified_at")
    return render(request, "pranks/admin_portal.html", {"pending": pending, "all_profiles": all_profiles})


@admin_required
@require_POST
def admin_activate(request, user_id):
    profile = get_object_or_404(UserProfile, user_id=user_id)
    profile.grant_access(hours=settings.PAYMENT_ACCESS_HOURS)
    invalidate_user_sessions(profile.user_id)
    ok = _send(profile.user.email, f"Your {settings.APP_NAME} access is active",
               "email/activated.html",
               {"user": profile.user, "expires": profile.access_expires_at, "app_name": settings.APP_NAME})
    messages.success(request, f"Activated {profile.user.username}") if ok else messages.warning(
        request, f"Activated {profile.user.username} but email failed — check logs")
    return redirect("admin_portal")


@admin_required
@require_POST
def admin_deactivate(request, user_id):
    profile = get_object_or_404(UserProfile, user_id=user_id)
    profile.access_expires_at = None
    profile.activation_requested = False
    profile.activation_requested_at = None
    profile.save()
    invalidate_user_sessions(profile.user_id)
    _send(profile.user.email, f"Your {settings.APP_NAME} access has been revoked",
          "email/deactivated.html",
          {"user": profile.user, "app_name": settings.APP_NAME})
    messages.success(request, f"Deactivated {profile.user.username} — access revoked")
    return redirect("admin_portal")


@admin_required
@require_POST
def admin_decline(request, user_id):
    profile = get_object_or_404(UserProfile, user_id=user_id)
    profile.activation_requested = False
    profile.activation_requested_at = None
    profile.save()
    invalidate_user_sessions(profile.user_id)
    _send(profile.user.email, f"Your {settings.APP_NAME} request was declined",
          "email/declined.html",
          {"user": profile.user, "app_name": settings.APP_NAME})
    messages.info(request, f"Declined {profile.user.username}")
    return redirect("admin_portal")


@admin_required
@require_POST
def admin_test_email(request):
    ok = _send(settings.ADMIN_NOTIFICATION_EMAIL,
               f"{settings.APP_NAME} test email", "email/welcome.html",
               {"user": request.user, "app_name": settings.APP_NAME})
    messages.success(request, f"Test email sent") if ok else messages.error(request, "Test email FAILED")
    return redirect("admin_portal")


# ---------- call screen ----------

def call(request, pid):
    prank = get_object_or_404(Prank, pk=pid)
    data = {
        "id": prank.id,
        "callerName": prank.caller_name,
        "avatarUrl": prank.avatar_url,
        "style": prank.style,
        "ringDelay": prank.ring_delay,
        "revealMessage": prank.reveal_message,
        "mediaType": prank.media_type,
        "photoUrl": prank.photo_file.url if prank.photo_file else "",
        "videoUrl": prank.video_file.url if prank.video_file else "",
        "callTimeout": prank.call_timeout or 0,
    }
    return render(request, "pranks/call.html", {"prank": prank, "data": data})


@csrf_exempt
@require_POST
def track(request, pid):
    try:
        event = json.loads(request.body or b"{}").get("event")
    except ValueError:
        event = None
    field = "answers" if event == "answer" else "views"
    Prank.objects.filter(pk=pid).update(**{field: F(field) + 1})
    return JsonResponse({"ok": True})


@login_required
@require_POST
def delete(request, pid):
    Prank.objects.filter(pk=pid, owner=request.user).delete()
    return redirect("dashboard")

# ===== Phase 1: live call signalling (polling) =====
import json as _json
from django.http import JsonResponse as _JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import CallSignal
from .turn import get_ice_servers


@login_required
def creator_call(request, pid):
    """Creator-side call screen. Owner-only. Loads the same call.js with role=creator."""
    prank = get_object_or_404(Prank, pk=pid, owner=request.user)
    data = {
        "id": prank.id,
        "callerName": prank.caller_name,
        "avatarUrl": prank.avatar_url,
        "style": prank.style,
        "ringDelay": prank.ring_delay,
        "revealMessage": prank.reveal_message,
        "mediaType": prank.media_type,
        "photoUrl": prank.photo_file.url if prank.photo_file else "",
        "videoUrl": prank.video_file.url if prank.video_file else "",
        "callTimeout": prank.call_timeout or 0,
        "role": "creator",
    }
    return render(request, "pranks/creator_call.html", {"prank": prank, "data": data})


@require_http_methods(["POST"])
def api_signal_post(request, pid):
    """Both sides POST signalling rows here. Victim identified by pid + side=victim."""
    prank = get_object_or_404(Prank, pk=pid)
    try:
        body = _json.loads(request.body or b"{}")
    except ValueError:
        return _JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    side = body.get("side")
    kind = body.get("kind")
    payload = body.get("payload", "")

    if side not in ("creator", "victim"):
        return _JsonResponse({"ok": False, "error": "bad side"}, status=400)
    if kind not in ("offer", "answer", "ice", "end", "bye", "state"):
        return _JsonResponse({"ok": False, "error": "bad kind"}, status=400)

    # Creator side must be authenticated and be the owner.
    if side == "creator":
        if not request.user.is_authenticated or prank.owner_id != request.user.id:
            return _JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    sig = CallSignal.objects.create(
        prank=prank, side=side, kind=kind, payload=payload
    )

    # If this is an "end" from creator, mark room ended.
    if kind == "end" and side == "creator":
        Prank.objects.filter(pk=pid).update(
            room_state="ended", ended_at=timezone.now(), end_reason="creator"
        )

    return _JsonResponse({"ok": True, "id": sig.id})


@require_http_methods(["GET"])
def api_signal_get(request, pid):
    """Long-poll: return signals with id > since, excluding own side."""
    prank = get_object_or_404(Prank, pk=pid)
    try:
        since = int(request.GET.get("since", "0"))
    except ValueError:
        since = 0
    side = request.GET.get("side", "victim")
    exclude = "creator" if side == "victim" else "victim"

    qs = CallSignal.objects.filter(prank=prank, id__gt=since).exclude(side=exclude)
    rows = list(qs.values("id", "side", "kind", "payload")[:50])
    return _JsonResponse({"ok": True, "signals": rows})


@login_required
@require_http_methods(["GET"])
def api_turn_credentials(request):
    """Return Twilio iceServers to the authenticated caller (creator or victim if logged in)."""
    return _JsonResponse({"ok": True, "iceServers": get_ice_servers(ttl=3600)})


@require_http_methods(["GET"])
def api_state(request, pid):
    """Poll room state (idle / live / ended). Used by both sides."""
    prank = get_object_or_404(Prank, pk=pid)
    return _JsonResponse({
        "ok": True,
        "room_state": prank.room_state,
        "end_reason": prank.end_reason,
    })
