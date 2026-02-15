from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from library.models import QueuedEmail


def queue_email(recipient, subject, body, html_body=None):
    """
    Saves email to queue and attempts instant dispatch.
    """
    email = QueuedEmail.objects.create(
        recipient_email=recipient,
        subject=subject,
        body=body,
        html_body=html_body,
    )

    send_queued_email(email)

    return email


def send_queued_email(queued_email: QueuedEmail):
    """
    Sends a single queued email safely.
    """
    try:
        send_mail(
            subject=queued_email.subject,
            message=queued_email.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[queued_email.recipient_email],
            html_message=queued_email.html_body,
            fail_silently=False,
        )

        queued_email.is_sent = True
        queued_email.sent_at = timezone.now()
        queued_email.error_message = ""
        queued_email.save()

        return True

    except Exception as e:
        queued_email.error_message = str(e)
        queued_email.save()
        return False
