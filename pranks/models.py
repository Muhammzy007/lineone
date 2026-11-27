import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

STYLES = [
    ("whatsapp", "WhatsApp"),
    ("telegram", "Telegram"),
    ("signal", "Signal"),
    ("zangi", "Zangi"),
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("messenger", "Messenger"),
    ("facetime", "FaceTime"),
]

MEDIA_CHOICES = [
    ("none", "No media (avatar only)"),
    ("photo", "Upload a photo"),
    ("video", "Upload a video"),
]


def new_id():
    return secrets.token_urlsafe(6)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    access_expires_at = models.DateTimeField(null=True, blank=True)
    activation_requested = models.BooleanField(default=False)
    activation_requested_at = models.DateTimeField(null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    total_activations = models.PositiveIntegerField(default=0)

    def has_active_access(self):
        return bool(self.access_expires_at and self.access_expires_at > timezone.now())

    def grant_access(self, hours=48):
        now = timezone.now()
        self.access_expires_at = now + timedelta(hours=hours)
        self.payment_verified_at = now
        self.activation_requested = False
        self.activation_requested_at = None
        self.total_activations += 1
        self.save()

    def __str__(self):
        return f"Profile for {self.user.username}"


class Prank(models.Model):
    id = models.CharField(primary_key=True, max_length=16, default=new_id, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pranks")
    caller_name = models.CharField(max_length=80)
    avatar_url = models.URLField(blank=True, help_text="Optional external avatar image URL")
    style = models.CharField(max_length=20, choices=STYLES, default="whatsapp")
    ring_delay = models.PositiveIntegerField(default=2)
    reveal_message = models.CharField(max_length=200, default="Call ended")

    # 0 = never auto-end; >0 = auto-end after N seconds
    call_timeout = models.PositiveIntegerField(
        default=0,
        help_text="Auto-end the call after this many seconds. Leave 0 for no auto-end.",
    )

    media_type = models.CharField(max_length=10, choices=MEDIA_CHOICES, default="none")
    photo_file = models.ImageField(upload_to="prank_photos/", blank=True, null=True)
    video_file = models.FileField(upload_to="prank_videos/", blank=True, null=True)

    views = models.PositiveIntegerField(default=0)
    answers = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.caller_name} ({self.owner.username})"

# ===== Phase 1: live call fields (additive) =====
class CallSignal(models.Model):
    """Ephemeral WebRTC signalling rows (SDP offer/answer, ICE candidates).

    Rows are short-lived. The creator and the victim post to the same room
    (keyed by prank_id + side) and read rows newer than their last cursor.
    Nothing here touches the existing prank playback path.
    """
    SIDE_CHOICES = [("creator", "Creator"), ("victim", "Victim")]
    KIND_CHOICES = [
        ("offer", "Offer"),
        ("answer", "Answer"),
        ("ice", "ICE"),
        ("end", "End"),
        ("bye", "Bye"),
        ("state", "State"),
    ]

    prank = models.ForeignKey(
        Prank, on_delete=models.CASCADE, related_name="signals"
    )
    side = models.CharField(max_length=10, choices=SIDE_CHOICES)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    payload = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["prank", "id"])]

    def __str__(self):
        return f"{self.prank_id}/{self.side}/{self.kind}#{self.id}"


# Extra call-state fields on Prank. All nullable / defaulted, so existing
# rows migrate without data loss and existing code paths are unaffected.
Prank.add_to_class(
    "room_state",
    models.CharField(
        max_length=10,
        choices=[("idle", "Idle"), ("live", "Live"), ("ended", "Ended")],
        default="idle",
    ),
)
Prank.add_to_class("creator_joined_at", models.DateTimeField(null=True, blank=True))
Prank.add_to_class("victim_joined_at", models.DateTimeField(null=True, blank=True))
Prank.add_to_class("ended_at", models.DateTimeField(null=True, blank=True))
Prank.add_to_class(
    "end_reason",
    models.CharField(max_length=20, blank=True, default=""),
)
