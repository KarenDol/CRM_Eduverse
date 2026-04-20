"""
Service layer for wa_inbox: sync Green API messages into Contact and Message models.
Used by the poll_green management command and by the record-message API.
"""
import re
from datetime import datetime
from django.utils import timezone

from .models import Contact, Message


def normalize_phone(chat_id: str) -> str:
    """
    Green API chatId is like "77071234567@c.us". Return digits only for Contact.phone.
    """
    if not chat_id:
        return ""
    return re.sub(r"\D", "", chat_id.split("@")[0])


def get_or_create_contact(phone: str, name: str = None):
    """Get or create a Contact by phone. Returns (contact, created). Optionally set name if provided and contact is new."""
    phone = normalize_phone(phone)
    if not phone:
        raise ValueError("Invalid chat_id or phone")
    contact, created = Contact.objects.get_or_create(
        phone=phone,
        defaults={
            "name": (name or "").strip() or "",
            "status": "NEW_LEAD",
            "department": "MANAGER_DANA",
            "priority": "MED",
        },
    )
    if created and name and (name or "").strip():
        contact.name = (name or "").strip()
        contact.save(update_fields=["name"])
    return contact, created


def record_message(
    contact: Contact,
    direction: str,
    text: str,
    timestamp: datetime = None,
    status: str = None,
) -> Message:
    """
    Create a Message for the contact and update contact's last_message*, unread_count.
    direction: "INBOUND" or "OUTBOUND"
    """
    if timestamp is None:
        timestamp = timezone.now()
    if timezone.is_naive(timestamp):
        timestamp = timezone.make_aware(timestamp)

    msg = Message.objects.create(
        contact=contact,
        direction=direction,
        text=text or "",
        timestamp=timestamp,
        status=status or "sent",
    )

    contact.last_message = (text or "")[:10000]
    contact.last_message_at = timestamp
    if direction == "INBOUND":
        contact.last_inbound_at = timestamp
        contact.unread_count = (contact.unread_count or 0) + 1
    else:
        contact.last_outbound_at = timestamp
    contact.updated_at = timezone.now()
    contact.save(
        update_fields=[
            "last_message",
            "last_message_at",
            "last_inbound_at",
            "last_outbound_at",
            "unread_count",
            "updated_at",
        ]
    )

    return msg
