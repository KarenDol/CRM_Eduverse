"""
Poll Green API receiveNotification and populate wa_inbox Contact + Message.
Run: python manage.py wa_inbox_poll_green

Uses settings: GREEN_API_INSTANCE, GREEN_API_TOKEN (or env GREEN_INSTANCE, GREEN_TOKEN).
Same credentials as wa_bot_3.py so this process can be the single poller and only records
to CRM; run the bot separately for GPT replies, or extend this command to send replies.
"""
import os
import time
import requests
from django.core.management.base import BaseCommand
from django.conf import settings

from wa_inbox.services import get_or_create_contact, record_message


class Command(BaseCommand):
    help = "Poll Green API for incoming/outgoing messages and store them in wa_inbox Contact + Message."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=float,
            default=5,
            help="Seconds between poll cycles (default 5)",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process one batch of notifications and exit",
        )

    def handle(self, *args, **options):
        instance = getattr(settings, "GREEN_API_INSTANCE", None) or os.environ.get("GREEN_INSTANCE")
        token = getattr(settings, "GREEN_API_TOKEN", None) or os.environ.get("GREEN_TOKEN")
        if not instance or not token:
            self.stderr.write(
                "Set GREEN_API_INSTANCE and GREEN_API_TOKEN in settings or env (GREEN_INSTANCE, GREEN_TOKEN)."
            )
            return

        base_url = f"https://7103.api.greenapi.com/{instance}"
        interval = options["interval"]
        once = options["once"]

        self.stdout.write(f"Polling Green API (instance={instance}), interval={interval}s. Ctrl+C to stop.")

        while True:
            try:
                self._poll_once(base_url, token)
            except Exception as e:
                self.stderr.write(f"Poll error: {e}")

            if once:
                break
            time.sleep(interval)

    def _poll_once(self, base_url, token):
        url = f"{base_url}/receiveNotification/{token}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        response = resp.json()

        while response:
            receipt_id = response.get("receiptId")
            body = response.get("body", {})
            type_webhook = body.get("typeWebhook")

            if type_webhook in ("incomingMessageReceived", "outgoingMessageReceived"):
                self._process_message(body, type_webhook)

            if receipt_id:
                delete_url = f"{base_url}/deleteNotification/{token}/{receipt_id}"
                requests.delete(delete_url, timeout=10)

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            response = resp.json()

    def _process_message(self, body, type_webhook):
        try:
            chat_id = body.get("senderData", {}).get("chatId")
            if not chat_id:
                return
            sender_name = (body.get("senderData") or {}).get("senderName") or ""

            msg_data = body.get("messageData") or {}
            content = (msg_data.get("textMessageData") or {}).get("textMessage", "")
            if not content:
                content = (msg_data.get("extendedTextMessageData") or {}).get("textMessage", "")

            direction = "INBOUND" if type_webhook == "incomingMessageReceived" else "OUTBOUND"
            contact = get_or_create_contact(chat_id, name=sender_name)
            record_message(contact, direction, content)
            self.stdout.write(f"Recorded {direction} for {contact.phone}: {content[:50]}...")
        except Exception as e:
            self.stderr.write(f"Process message error: {e}")
