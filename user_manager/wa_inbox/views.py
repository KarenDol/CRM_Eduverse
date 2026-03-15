import json
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from django.db import models as db_models

from .models import Contact
from .services import get_or_create_contact, record_message

# Base URL where the WhatsAppFront Next.js app is served (dev or production).
# Override in settings: WA_INBOX_FRONTEND_URL = "http://localhost:3000"
WA_INBOX_FRONTEND_URL = getattr(
    settings, "WA_INBOX_FRONTEND_URL", "http://localhost:3000"
)


@login_required
def inbox_app(request):
    """
    Launch the WhatsApp Team Inbox frontend (WhatsAppFront).
    If WA_INBOX_FRONTEND_URL is set, redirect there so one WhatsApp
    is used across departments. Otherwise show a simple launch page.
    """
    frontend_url = WA_INBOX_FRONTEND_URL.strip()
    if frontend_url:
        return redirect(frontend_url)
    return render(request, "wa_inbox/launch.html")


@login_required
def inbox_embed(request):
    """
    Serve a page that embeds the WhatsApp Inbox frontend in an iframe.
    Use when you want the inbox inside the CRM layout.
    """
    context = {"frontend_url": WA_INBOX_FRONTEND_URL or "http://localhost:3000"}
    return render(request, "wa_inbox/embed.html", context)


def _check_wa_inbox_api_auth(request):
    """Optional: require X-WA-Inbox-API-Key header if WA_INBOX_API_KEY is set."""
    key = getattr(settings, "WA_INBOX_API_KEY", None)
    if not key:
        return True
    return request.headers.get("X-WA-Inbox-API-Key") == key


@csrf_exempt
@require_http_methods(["POST"])
def api_record_message(request):
    """
    Record an incoming or outgoing message into the CRM (Contact + Message).
    Body (JSON): chat_id, direction ("INBOUND"|"OUTBOUND"), text, timestamp (optional ISO), sender_name (optional).
    Used by the bot after receiving/sending via Green API.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    chat_id = data.get("chat_id")
    direction = (data.get("direction") or "").upper()
    text = data.get("text", "")
    sender_name = data.get("sender_name")

    if not chat_id:
        return JsonResponse({"error": "Missing chat_id"}, status=400)
    if direction not in ("INBOUND", "OUTBOUND"):
        return JsonResponse({"error": "direction must be INBOUND or OUTBOUND"}, status=400)

    timestamp = None
    if data.get("timestamp"):
        try:
            timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    if timestamp is None:
        timestamp = timezone.now()

    try:
        contact = get_or_create_contact(chat_id, name=sender_name)
        msg = record_message(contact, direction, text, timestamp=timestamp)
        return JsonResponse({
            "ok": True,
            "contact_id": contact.pk,
            "message_id": msg.pk,
        })
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


def _parse_green_webhook_message(body):
    """
    Parse Green API webhook body (incomingMessageReceived / outgoingMessageReceived).
    Returns (chat_id, sender_name, text, direction, timestamp) or None if not a supported message.
    See: https://green-api.com/en/docs/api/receiving/notifications-format/incoming-message/TextMessage/
    """
    type_webhook = body.get("typeWebhook")
    if type_webhook not in ("incomingMessageReceived", "outgoingMessageReceived"):
        return None

    sender_data = body.get("senderData") or {}
    chat_id = sender_data.get("chatId")
    if not chat_id:
        return None

    sender_name = (sender_data.get("senderName") or sender_data.get("senderContactName") or "").strip()

    msg_data = body.get("messageData") or {}
    text = (msg_data.get("textMessageData") or {}).get("textMessage", "")
    if not text:
        text = (msg_data.get("extendedTextMessageData") or {}).get("textMessage", "")
    if not text and msg_data.get("typeMessage") in ("imageMessage", "videoMessage", "documentMessage", "audioMessage"):
        text = (msg_data.get("caption") or (msg_data.get("fileMessageData") or {}).get("caption") or "").strip()

    direction = "INBOUND" if type_webhook == "incomingMessageReceived" else "OUTBOUND"

    ts = body.get("timestamp")
    if ts is not None:
        try:
            timestamp = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            timestamp = timezone.now()
    else:
        timestamp = timezone.now()

    return (chat_id, sender_name, text or "", direction, timestamp)


@csrf_exempt
@require_http_methods(["POST"])
def api_green_webhook(request):
    """
    Green API webhook: receives incoming/outgoing message notifications and stores them in CRM.
    Configure this URL in Green API console (or via SetSettings) as the incoming webhook URL.
    POST body: JSON in Green API webhook format (typeWebhook, senderData, messageData, timestamp).
    Always returns 200 so Green API does not retry; errors are logged.
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=200)

    parsed = _parse_green_webhook_message(body)
    if not parsed:
        return JsonResponse({"ok": True, "skipped": "not a message"}, status=200)

    chat_id, sender_name, text, direction, timestamp = parsed
    try:
        contact = get_or_create_contact(chat_id, name=sender_name)
        record_message(contact, direction, text, timestamp=timestamp)
        return JsonResponse({"ok": True, "contact_id": contact.pk}, status=200)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=200)


def _serialize_contact(c: Contact):
    """Serialize Contact to frontend Conversation-like shape."""
    return {
        "id": str(c.pk),
        "client": {
            "id": str(c.pk),
            "phone": c.phone,
            "name": c.name or None,
            "tags": c.tags or [],
            "createdAt": c.created_at.isoformat() if c.created_at else None,
        },
        "channel": "whatsapp",
        "status": c.status,
        "department": c.department,
        "ownerId": None,
        "ownerName": None,
        "priority": c.priority,
        "lastMessage": c.last_message or None,
        "lastMessageAt": c.last_message_at.isoformat() if c.last_message_at else None,
        "lastInboundAt": c.last_inbound_at.isoformat() if c.last_inbound_at else None,
        "lastOutboundAt": c.last_outbound_at.isoformat() if c.last_outbound_at else None,
        "unreadCount": c.unread_count or 0,
        "slaState": c.sla_state,
        "slaDeadline": c.sla_deadline.isoformat() if c.sla_deadline else None,
        "open": c.is_open,
        "tags": c.tags or [],
    }


def _serialize_message(m):
    """Serialize Message to frontend Message shape."""
    return {
        "id": str(m.pk),
        "conversationId": str(m.contact_id),
        "direction": m.direction,
        "text": m.text,
        "timestamp": m.timestamp.isoformat() if m.timestamp else None,
        "status": m.status,
        "attachments": m.attachments or [],
    }


@require_http_methods(["GET"])
def api_list_contacts(request):
    """
    GET /wa-inbox/api/contacts/
    Query params: departments (comma), statuses (comma), search, open (true/false).
    Returns list of contacts as conversation-shaped JSON for WhatsAppFront.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    qs = Contact.objects.all().order_by("-last_message_at")

    open_param = request.GET.get("open")
    if open_param is not None:
        if open_param.lower() in ("true", "1", "yes"):
            qs = qs.filter(is_open=True)
        elif open_param.lower() in ("false", "0", "no"):
            qs = qs.filter(is_open=False)

    depts = request.GET.getlist("departments") or request.GET.get("departments", "").split(",")
    depts = [d.strip() for d in depts if d.strip()]
    if depts:
        qs = qs.filter(department__in=depts)

    statuses = request.GET.getlist("statuses") or request.GET.get("statuses", "").split(",")
    statuses = [s.strip() for s in statuses if s.strip()]
    if statuses:
        qs = qs.filter(status__in=statuses)

    search = (request.GET.get("search") or "").strip()
    if search:
        qs = qs.filter(
            db_models.Q(phone__icontains=search)
            | db_models.Q(name__icontains=search)
            | db_models.Q(last_message__icontains=search)
        )

    data = [_serialize_contact(c) for c in qs]
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def api_contact_messages(request, contact_id: int):
    """
    GET /wa-inbox/api/contacts/<id>/messages/
    Returns messages for the contact for WhatsAppFront.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    contact = get_object_or_404(Contact, pk=contact_id)
    messages = contact.messages.all().order_by("timestamp")
    data = [_serialize_message(m) for m in messages]
    return JsonResponse(data, safe=False)
