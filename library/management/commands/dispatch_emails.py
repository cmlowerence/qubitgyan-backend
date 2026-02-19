from django.core.management.base import BaseCommand
from library.models import QueuedEmail
from library.services.email_service import send_queued_email


class Command(BaseCommand):
    help = "Dispatch pending queued emails"

    def handle(self, *args, **kwargs):

        MAX_RETRIES = 3
    
        pending = QueuedEmail.objects.filter(
            is_sent=False,
            retry_count__lt=MAX_RETRIES
        )
    
        sent_count = 0
        failed_count = 0
    
        for email in pending:
            success = send_queued_email(email)
    
            if success:
                sent_count += 1
            else:
                failed_count += 1
    
        self.stdout.write(
            self.style.SUCCESS(
                f"Dispatch completed — Sent: {sent_count}, Failed: {failed_count}"
            )
        )