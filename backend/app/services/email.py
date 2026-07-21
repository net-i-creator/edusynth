"""Transactional email via SMTP (password reset, support notifications)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def send_email(to: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    """Send an email. Returns True on success. No-ops with a warning if SMTP is not configured."""
    if not smtp_configured():
        logger.warning("SMTP not configured — email to %s skipped: %s", to, subject)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to], msg.as_string())
        logger.info("Email sent to %s (%s)", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_password_reset_email(to: str, reset_url: str) -> bool:
    subject = "Восстановление пароля — УмБаза"
    text = (
        "Здравствуйте!\n\n"
        "Вы запросили восстановление пароля на УмБаза.\n"
        f"Перейдите по ссылке, чтобы задать новый пароль:\n{reset_url}\n\n"
        "Ссылка действует 1 час. Если вы не запрашивали сброс — просто проигнорируйте это письмо.\n"
    )
    html = f"""
    <p>Здравствуйте!</p>
    <p>Вы запросили восстановление пароля на <strong>УмБаза</strong>.</p>
    <p><a href="{reset_url}">Задать новый пароль</a></p>
    <p style="color:#64748b;font-size:13px">Ссылка действует 1 час. Если вы не запрашивали сброс — проигнорируйте это письмо.</p>
    """
    return send_email(to, subject, text, html)


def send_support_notification(from_email: str, message: str) -> bool:
    to = settings.support_email
    subject = f"Обратная связь УмБаза от {from_email}"
    text = f"От: {from_email}\n\n{message}"
    html = f"<p><strong>От:</strong> {from_email}</p><pre style='white-space:pre-wrap;font-family:inherit'>{message}</pre>"
    return send_email(to, subject, text, html)
