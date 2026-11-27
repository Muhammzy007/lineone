from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = "Create a superuser from environment variables (one-off, safe to re-run)."

    def handle(self, *args, **kwargs):
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        email = os.environ.get("ADMIN_EMAIL", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")

        if not username or not password:
            self.stderr.write("ADMIN_USERNAME and ADMIN_PASSWORD must be set. Skipping.")
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User '{username}' already exists. Nothing to do.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
