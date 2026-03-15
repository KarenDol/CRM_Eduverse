from django.db import models
from django.conf import settings


# Department choices (match WhatsAppFront: manager Dana, Sabina, Faniya)
DEPARTMENT_CHOICES = [
    ("MANAGER_DANA", "manager Dana"),
    ("MANAGER_SABINA", "manager Sabina"),
    ("MANAGER_FANIYA", "manager Faniya"),
]

STATUS_CHOICES = [
    ("NEW_LEAD", "New Lead"),
    ("QUALIFYING", "Qualifying"),
    ("WAITING_PAYMENT", "Waiting Payment"),
    ("ENROLLED", "Enrolled"),
    ("SUPPORT_NEW", "New Ticket"),
    ("SUPPORT_IN_PROGRESS", "In Progress"),
    ("WAITING_CLIENT", "Waiting Client"),
    ("RESOLVED", "Resolved"),
    ("PAYMENT_ISSUE", "Payment Issue"),
    ("REFUND_REQUEST", "Refund"),
    ("ESCALATED", "Escalated"),
    ("SPAM", "Spam"),
    ("CLOSED", "Closed"),
]

PRIORITY_CHOICES = [
    ("LOW", "Low"),
    ("MED", "Medium"),
    ("HIGH", "High"),
]

SLA_STATE_CHOICES = [
    ("OK", "OK"),
    ("WARNING", "Warning"),
    ("BREACHED", "Breached"),
]

MESSAGE_DIRECTION_CHOICES = [
    ("INBOUND", "Inbound"),
    ("OUTBOUND", "Outbound"),
]

MESSAGE_STATUS_CHOICES = [
    ("sending", "Sending"),
    ("sent", "Sent"),
    ("delivered", "Delivered"),
    ("read", "Read"),
    ("failed", "Failed"),
]


class Contact(models.Model):
    """
    WhatsApp contact / conversation. One contact = one WhatsApp chat.
    Stores conversation-level state: status, department, priority, SLA, etc.
    """
    phone = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(default=list, help_text="List of tag strings")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="NEW_LEAD")
    department = models.CharField(max_length=32, choices=DEPARTMENT_CHOICES, default="MANAGER_DANA")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="MED")
    last_message = models.TextField(blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    last_outbound_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)
    sla_state = models.CharField(max_length=16, choices=SLA_STATE_CHOICES, default="OK")
    sla_deadline = models.DateTimeField(null=True, blank=True)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at"]
        verbose_name = "WhatsApp Contact"
        verbose_name_plural = "WhatsApp Contacts"

    def __str__(self):
        return self.name or self.phone


class Message(models.Model):
    """
    Single WhatsApp message, linked to a Contact.
    """
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=8, choices=MESSAGE_DIRECTION_CHOICES)
    text = models.TextField()
    timestamp = models.DateTimeField()
    status = models.CharField(
        max_length=16,
        choices=MESSAGE_STATUS_CHOICES,
        blank=True,
        null=True,
    )
    attachments = models.JSONField(
        default=list,
        help_text="List of {type, url, name}",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]
        verbose_name = "WhatsApp Message"
        verbose_name_plural = "WhatsApp Messages"

    def __str__(self):
        return f"{self.direction} to {self.contact.phone}: {self.text[:50]}..."
