from django.contrib import admin
from .models import Prank, UserProfile

admin.site.site_header = "TechMagnetStudio Admin"
admin.site.site_title = "TechMagnetStudio"
admin.site.index_title = "TechMagnetStudio Control"
admin.site.site_url = "/"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "access_expires_at", "activation_requested", "total_activations")
    list_filter = ("activation_requested",)
    search_fields = ("user__username", "user__email")


@admin.register(Prank)
class PrankAdmin(admin.ModelAdmin):
    list_display = ("caller_name", "owner", "style", "views", "answers", "created_at")
    search_fields = ("caller_name", "owner__username")
