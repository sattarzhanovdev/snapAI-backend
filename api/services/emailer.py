from django.core.mail import EmailMultiAlternatives
from django.conf import settings

def send_otp_email(to_email: str, otp: str):
    subject = "Код подтверждения"
    from_email = settings.DEFAULT_FROM_EMAIL

    # простой текст (fallback, если у клиента нет HTML)
    text_content = f"Ваш код подтверждения: {otp}\nКод действует 10 минут."

    # HTML версия
    html_content = f"""
        <p>Ваш код подтверждения: <b>{otp}</b></p>
        <p>Код действует 10 минут.</p>
    """

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()