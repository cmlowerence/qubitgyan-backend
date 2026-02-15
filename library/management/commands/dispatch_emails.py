from django.core.management.base import BaseCommand
from library.models import QueuedEmail
from library.services.email_service import send_queued_email


class Command(BaseCommand):
    help = "Dispatch pending queued emails"

    def handle(self, *args, **kwargs):
        pending = QueuedEmail.objects.filter(is_sent=False)

        for email in pending:
            send_queued_email(email)

        self.stdout.write(self.style.SUCCESS("Email dispatch completed"))
