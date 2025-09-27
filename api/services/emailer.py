from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_email_html(email, otp, ttl_minutes=10):
    subject = "Ваш код подтверждения"
    text_body = f"Ваш код: {otp}. Действует {ttl_minutes} мин."
    html_body = f"Ваш код подтверждения: <b>{otp}</b><br/>Код действует {ttl_minutes} минут."
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)        # <— важно
        return True
    except Exception:
        logger.exception("Ошибка при отправке письма")  # выведет стек
        return False