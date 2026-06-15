"""Envoi de notifications e-mail (SMTP)."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("skills-runner")

DEFAULT_NOTIFY_TO = "chapron.loic@gmail.com"


class NotifyConfigError(RuntimeError):
    """Configuration SMTP incomplète."""


def _smtp_settings() -> tuple[str, int, str, str, str]:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    from_addr = os.environ.get("SMTP_FROM", user).strip() or user
    if not user or not password:
        raise NotifyConfigError("SMTP_USER et SMTP_PASS doivent être renseignés dans .env")
    return host, port, user, password, from_addr


def send_email(*, to: str, subject: str, body: str) -> dict[str, str]:
    """Envoie un e-mail texte brut via SMTP STARTTLS."""
    host, port, user, password, from_addr = _smtp_settings()
    recipient = (to or os.environ.get("NOTIFY_TO", DEFAULT_NOTIFY_TO)).strip()
    if not recipient:
        raise NotifyConfigError("Destinataire e-mail manquant")

    message = EmailMessage()
    message["From"] = from_addr
    message["To"] = recipient
    message["Subject"] = subject.strip() or "Notification CursorAutomation"
    message.set_content(body or "(vide)")

    logger.info("Envoi e-mail to=%s subject=%s", recipient, message["Subject"])
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(user, password)
        smtp.send_message(message)

    return {"to": recipient, "subject": message["Subject"]}
