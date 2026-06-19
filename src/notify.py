"""Failure / missed-message alerts. Sends to Slack webhook and/or email."""
import logging
import smtplib
from email.message import EmailMessage

import requests

log = logging.getLogger("notify")


def send_alert(settings, subject, body):
    """Best-effort alert to every configured channel. Never raises."""
    sent = False
    alerts = settings.get("alerts", {}) or {}

    webhook = alerts.get("slack_webhook")
    if webhook:
        try:
            requests.post(webhook, json={"text": f"*{subject}*\n{body}"}, timeout=10)
            sent = True
        except Exception as e:  # noqa: BLE001
            log.error("Slack alert failed: %s", e)

    if alerts.get("email_to"):
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = alerts["email_from"]
            msg["To"] = alerts["email_to"]
            msg.set_content(body)
            with smtplib.SMTP(alerts["smtp_host"], 587, timeout=15) as s:
                s.starttls()
                s.login(alerts["smtp_user"], alerts["smtp_password"])
                s.send_message(msg)
            sent = True
        except Exception as e:  # noqa: BLE001
            log.error("Email alert failed: %s", e)

    if not sent:
        log.warning("ALERT not delivered (no channel configured): %s", subject)
    return sent
