import json
import logging
import re
import secrets
from datetime import datetime

import requests

logger = logging.getLogger(__name__)
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from django.db import models as db_models
from django.db.models import Case, When, Value, IntegerField, Q

User = get_user_model()

from .models import Contact, Message, Note, ContactHistory, STATUS_CHOICES, PRIORITY_CHOICES
from .services import get_or_create_contact, record_message

try:
    from core.models import CRM_User
except ImportError:
    CRM_User = None

# Base URL where the WhatsAppFront Next.js app is served (dev or production).
# Override in settings: WA_INBOX_FRONTEND_URL = "http://localhost:3000"
WA_INBOX_FRONTEND_URL = getattr(
    settings, "WA_INBOX_FRONTEND_URL", "http://localhost:3000"
)


# Cache key prefix and TTL for one-time inbox token (cross-origin auth when opening from CRM).
WA_INBOX_TOKEN_PREFIX = "wa_inbox_token_"
WA_INBOX_TOKEN_TTL = 300  # 5 minutes


@login_required
def inbox_app(request):
    """
    Launch the WhatsApp Team Inbox frontend (WhatsAppFront).
    If WA_INBOX_FRONTEND_URL is set, redirect there with a short-lived token
    so the frontend can authenticate API calls even when on a different origin.
    Otherwise show a simple launch page.
    """
    frontend_url = WA_INBOX_FRONTEND_URL.strip()
    if frontend_url:
        token = secrets.token_urlsafe(32)
        cache.set(
            WA_INBOX_TOKEN_PREFIX + token,
            {"user_id": request.user.pk},
            timeout=WA_INBOX_TOKEN_TTL,
        )
        sep = "&" if "?" in frontend_url else "?"
        return redirect(f"{frontend_url}{sep}wa_inbox_token={token}")
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
    """
    Require one of: (1) Django session auth, (2) X-WA-Inbox-API-Key header,
    or (3) X-WA-Inbox-Token header (short-lived token from opening inbox from CRM).
    When (3) is used, request.wa_inbox_user is set for api_me and other views.
    """
    if request.user.is_authenticated:
        return True
    key = getattr(settings, "WA_INBOX_API_KEY", None)
    if key and request.headers.get("X-WA-Inbox-API-Key") == key:
        return True
    token = (request.headers.get("X-WA-Inbox-Token") or "").strip()
    if token:
        data = cache.get(WA_INBOX_TOKEN_PREFIX + token)
        if data and data.get("user_id"):
            try:
                request.wa_inbox_user = User.objects.get(pk=data["user_id"])
                return True
            except User.DoesNotExist:
                pass
    return False


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
        contact, created = get_or_create_contact(chat_id, name=sender_name)
        if created:
            _add_contact_history(contact, "CREATED", "Conversation created from inbound message", request)
        msg = record_message(contact, direction, text, timestamp=timestamp)
        return JsonResponse({
            "ok": True,
            "contact_id": contact.pk,
            "message_id": msg.pk,
        })
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


def _phone_to_chat_id(phone: str) -> str:
    """Normalize phone to Green API chatId (e.g. 77071234567 -> 77071234567@c.us)."""
    digits = re.sub(r"\D", "", str(phone).split("@")[0])
    return f"{digits}@c.us" if digits else ""


def _get_green_api_credentials():
    """Return (id_instance, api_token) for Green API from settings, or (None, None)."""
    instance = getattr(settings, "GREEN_API_INSTANCE", None) or ""
    token = getattr(settings, "GREEN_API_TOKEN", None) or ""
    if not instance or not token:
        return None, None
    # GREEN_API_INSTANCE may be "waInstance7103163711" -> id_instance = 7103163711
    id_instance = instance.replace("waInstance", "", 1) if instance.startswith("waInstance") else instance
    return id_instance, token


@csrf_exempt
@require_http_methods(["POST"])
def api_send_message(request):
    """
    Send a WhatsApp message via Green API and record it in the CRM.
    Body (JSON): contact_id (int, optional) or phone (str), and text (str).
    If contact_id is given, that contact is used; otherwise phone is used to get or create a contact.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    contact_id = data.get("contact_id")
    phone = (data.get("phone") or "").strip()
    text = (data.get("text") or "").strip()

    if not text:
        return JsonResponse({"error": "Missing text"}, status=400)

    if contact_id is not None:
        contact = get_object_or_404(Contact, pk=int(contact_id))
        phone = contact.phone
    elif not phone:
        return JsonResponse({"error": "Missing contact_id or phone"}, status=400)
    else:
        contact, _ = get_or_create_contact(phone)

    chat_id = _phone_to_chat_id(phone)
    if not chat_id:
        return JsonResponse({"error": "Invalid phone"}, status=400)

    id_instance, api_token = _get_green_api_credentials()
    if not id_instance or not api_token:
        return JsonResponse(
            {"error": "Green API not configured (GREEN_API_INSTANCE, GREEN_API_TOKEN)"},
            status=500,
        )

    url = f"https://7103.api.greenapi.com/waInstance{id_instance}/sendMessage/{api_token}"
    payload = {"chatId": chat_id, "message": text}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if not resp.ok:
            try:
                err_body = resp.json()
            except Exception:
                err_body = {"text": resp.text[:500] if resp.text else None}
            logger.warning(
                "Green API sendMessage failed: status=%s url=%s body=%s",
                resp.status_code,
                url,
                err_body,
            )
            return JsonResponse(
                {
                    "error": "Green API send failed",
                    "detail": str(resp.reason),
                    "status_code": resp.status_code,
                    "green_api": err_body,
                },
                status=502,
            )
    except requests.RequestException as e:
        return JsonResponse(
            {"error": "Green API request failed", "detail": str(e)},
            status=502,
        )

    try:
        msg = record_message(contact, "OUTBOUND", text)
        return JsonResponse({"ok": True, "message_id": msg.pk, "contact_id": contact.pk}, status=200)
    except Exception as e:
        return JsonResponse({"error": "Record failed", "detail": str(e)}, status=500)


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
        contact, created = get_or_create_contact(chat_id, name=sender_name)
        if created:
            _add_contact_history(contact, "CREATED", "Conversation created from inbound message", request)
        record_message(contact, direction, text, timestamp=timestamp)
        return JsonResponse({"ok": True, "contact_id": contact.pk}, status=200)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=200)


def _get_actor_name(request) -> str:
    """Return display name of the current user (session or token) for history/audit."""
    user = getattr(request, "wa_inbox_user", None)
    if user:
        return getattr(user, "name", None) or getattr(user, "username", str(user))
    if getattr(request, "user", None) and request.user.is_authenticated:
        if CRM_User:
            try:
                crm = CRM_User.objects.get(user=request.user)
                return crm.name
            except CRM_User.DoesNotExist:
                pass
        return getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "Unknown")
    return "System"


def _add_contact_history(contact: Contact, event_type: str, description: str, request=None):
    """Append an audit event to the contact's history."""
    actor = _get_actor_name(request) if request else "System"
    ContactHistory.objects.create(
        contact=contact,
        event_type=event_type,
        actor=actor,
        description=description,
    )


def _serialize_contact(c: Contact):
    """Serialize Contact to frontend Conversation-like shape."""
    assigned = c.assigned_to
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
        "department": assigned.name if assigned else c.department,
        "assignedToId": assigned.pk if assigned else None,
        "assignedToName": assigned.name if assigned else None,
        "ownerId": str(assigned.pk) if assigned else None,
        "ownerName": assigned.name if assigned else None,
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
    Query params: departments, statuses, priority, tags (comma), search, open, sort (newest|priority).
    sort=priority: order by HIGH then MED then LOW, then newest first.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    qs = Contact.objects.all()

    open_param = request.GET.get("open")
    if open_param is not None:
        if open_param.lower() in ("true", "1", "yes"):
            qs = qs.filter(is_open=True)
        elif open_param.lower() in ("false", "0", "no"):
            qs = qs.filter(is_open=False)

    assigned_to_ids = request.GET.getlist("assigned_to") or request.GET.getlist("assigned_to_id") or (request.GET.get("assigned_to", "") or request.GET.get("assigned_to_id", "")).split(",")
    assigned_to_ids = [x.strip() for x in assigned_to_ids if x.strip()]
    if assigned_to_ids:
        try:
            ids = [int(i) for i in assigned_to_ids]
            qs = qs.filter(assigned_to_id__in=ids)
        except ValueError:
            pass
    depts = request.GET.getlist("departments") or request.GET.get("departments", "").split(",")
    depts = [d.strip() for d in depts if d.strip()]
    if depts:
        qs = qs.filter(department__in=depts)

    statuses = request.GET.getlist("statuses") or request.GET.get("statuses", "").split(",")
    statuses = [s.strip() for s in statuses if s.strip()]
    if statuses:
        qs = qs.filter(status__in=statuses)

    priority_param = (request.GET.get("priority") or "").strip()
    if priority_param and priority_param in [c[0] for c in PRIORITY_CHOICES]:
        qs = qs.filter(priority=priority_param)

    tags_param = request.GET.getlist("tags") or request.GET.get("tags", "").split(",")
    tags_param = [t.strip() for t in tags_param if t.strip()]
    if tags_param:
        tag_q = Q()
        for t in tags_param:
            tag_q |= Q(tags__contains=[t])
        qs = qs.filter(tag_q)

    search = (request.GET.get("search") or "").strip()
    if search:
        qs = qs.filter(
            db_models.Q(phone__icontains=search)
            | db_models.Q(name__icontains=search)
            | db_models.Q(last_message__icontains=search)
        )

    sort_param = (request.GET.get("sort") or "newest").strip().lower()
    if sort_param == "priority":
        qs = qs.order_by(
            Case(
                When(priority="HIGH", then=Value(0)),
                When(priority="MED", then=Value(1)),
                When(priority="LOW", then=Value(2)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            "-last_message_at",
        )
    else:
        qs = qs.order_by("-last_message_at")

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


def _serialize_note(n):
    """Serialize Note to frontend InternalNote shape."""
    creator = n.creator
    return {
        "id": str(n.pk),
        "conversationId": str(n.contact_id),
        "authorId": str(creator.pk) if creator else "",
        "authorName": creator.name if creator else "Unknown",
        "note": n.content,
        "createdAt": n.created_at.isoformat() if n.created_at else None,
    }


def _serialize_history_event(h):
    """Serialize ContactHistory to frontend AuditEvent shape."""
    return {
        "id": str(h.pk),
        "conversationId": str(h.contact_id),
        "type": h.event_type,
        "actor": h.actor or "System",
        "description": h.description,
        "timestamp": h.created_at.isoformat() if h.created_at else None,
    }


@require_http_methods(["GET"])
def api_contact_history(request, contact_id: int):
    """
    GET /wa-inbox/api/contacts/<id>/history/
    Returns audit/history events for the contact (newest first).
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    contact = get_object_or_404(Contact, pk=contact_id)
    events = contact.history.all().order_by("-created_at")
    data = [_serialize_history_event(e) for e in events]
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def api_contact_notes(request, contact_id: int):
    """
    GET /wa-inbox/api/contacts/<id>/notes/
    Returns internal notes for the contact (newest first).
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    contact = get_object_or_404(Contact, pk=contact_id)
    notes = contact.notes.all().order_by("-created_at")
    data = [_serialize_note(n) for n in notes]
    return JsonResponse(data, safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def api_contact_notes_create(request, contact_id: int):
    """
    POST /wa-inbox/api/contacts/<id>/notes/
    Body (JSON): content (str), optional creator_id (int, CRM_User pk).
    Creates an internal note on the contact.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    contact = get_object_or_404(Contact, pk=contact_id)
    content = (data.get("content") or "").strip()
    if not content:
        return JsonResponse({"error": "Missing content"}, status=400)
    creator_id = data.get("creator_id")
    creator = None
    if creator_id is not None and CRM_User:
        try:
            creator = CRM_User.objects.get(pk=int(creator_id))
        except (ValueError, TypeError, CRM_User.DoesNotExist):
            pass
    note = Note.objects.create(contact=contact, creator=creator, content=content)
    _add_contact_history(contact, "NOTE_ADDED", "Internal note added", request)
    return JsonResponse(_serialize_note(note), status=201)


@require_http_methods(["GET"])
def api_me(request):
    """
    GET /wa-inbox/api/me/
    Returns the current user (CRM session, token, or API key context).
    Used by the frontend to know who is logged in; 401 if not authenticated.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    user = getattr(request, "wa_inbox_user", None) or (request.user if request.user.is_authenticated else None)
    if user and CRM_User:
        try:
            crm_user = CRM_User.objects.get(user=user)
            return JsonResponse({
                "id": crm_user.pk,
                "name": crm_user.name,
                "picture": getattr(crm_user, "picture", None) or None,
            })
        except CRM_User.DoesNotExist:
            pass
    if user:
        return JsonResponse({
            "id": user.pk,
            "name": getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", ""),
            "picture": None,
        })
    return JsonResponse({"id": 0, "name": "API", "picture": None})


@require_http_methods(["GET"])
def api_list_crm_users(request):
    """
    GET /wa-inbox/api/crm-users/
    Returns list of CRM users (id, name) for inbox filters and assignment dropdown.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if not CRM_User:
        return JsonResponse([], safe=False)
    users = list(CRM_User.objects.values("id", "name").order_by("name"))
    return JsonResponse([{"id": u["id"], "name": u["name"]} for u in users], safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def api_contact_assign(request, contact_id: int):
    """
    POST /wa-inbox/api/contacts/<id>/assign/
    Body (JSON): assigned_to_id (int, optional). Set to null to unassign.
    Updates the contact's assigned CRM user (department).
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    contact = get_object_or_404(Contact, pk=contact_id)
    raw_id = data.get("assigned_to_id")
    if raw_id is None:
        contact.assigned_to_id = None
    else:
        try:
            uid = int(raw_id)
        except (ValueError, TypeError):
            return JsonResponse({"error": "assigned_to_id must be an integer or null"}, status=400)
        if CRM_User and CRM_User.objects.filter(pk=uid).exists():
            contact.assigned_to_id = uid
        else:
            return JsonResponse({"error": "CRM user not found"}, status=404)
    contact.save(update_fields=["assigned_to_id"])
    assigned = contact.assigned_to
    desc = f"Assigned to {assigned.name}" if assigned else "Unassigned"
    _add_contact_history(contact, "ASSIGNED", desc, request)
    return JsonResponse({
        "ok": True,
        "assignedToId": assigned.pk if assigned else None,
        "assignedToName": assigned.name if assigned else None,
    }, status=200)


@csrf_exempt
@require_http_methods(["POST", "PATCH"])
def api_contact_update(request, contact_id: int):
    """
    POST/PATCH /wa-inbox/api/contacts/<id>/update/
    Body (JSON): status (str, optional), priority (str, optional), open (bool, optional), tags (list of str, optional).
    Updates the contact's status, priority, is_open, and/or tags.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    contact = get_object_or_404(Contact, pk=contact_id)
    update_fields = []

    if "tags" in data:
        raw = data["tags"]
        if not isinstance(raw, list):
            return JsonResponse({"error": "tags must be a list of strings"}, status=400)
        tags_list = [str(x).strip() for x in raw if str(x).strip()]
        Contact.objects.filter(pk=contact_id).update(tags=tags_list)
        contact.tags = tags_list
        update_fields.append("tags")
        _add_contact_history(
            contact, "TAG_CHANGED",
            f"Tags updated: {', '.join(tags_list) or '(none)'}",
            request,
        )

    status_val = data.get("status")
    if status_val is not None:
        status_val = (status_val or "").strip()
        valid_statuses = [c[0] for c in STATUS_CHOICES]
        if status_val not in valid_statuses:
            return JsonResponse({"error": f"status must be one of: {', '.join(valid_statuses)}"}, status=400)
        contact.status = status_val
        update_fields.append("status")
        _add_contact_history(contact, "STATUS_CHANGED", f"Status changed to {status_val}", request)
        if status_val == "CLOSED":
            contact.is_open = False
            update_fields.append("is_open")
            _add_contact_history(contact, "CLOSED", "Conversation closed", request)

    priority_val = data.get("priority")
    if priority_val is not None:
        priority_val = (priority_val or "").strip()
        valid_priorities = [c[0] for c in PRIORITY_CHOICES]
        if priority_val not in valid_priorities:
            return JsonResponse({"error": f"priority must be one of: {', '.join(valid_priorities)}"}, status=400)
        contact.priority = priority_val
        update_fields.append("priority")
        _add_contact_history(
            contact, "STATUS_CHANGED",
            f"Priority set to {priority_val}",
            request,
        )

    if "open" in data:
        new_open = bool(data["open"])
        contact.is_open = new_open
        update_fields.append("is_open")
        if new_open:
            _add_contact_history(contact, "REOPENED", "Conversation reopened", request)

    if update_fields:
        contact.save(update_fields=update_fields)

    # Reload from DB so response (especially tags) reflects what was persisted
    contact.refresh_from_db()
    return JsonResponse({
        "ok": True,
        "status": contact.status,
        "priority": contact.priority,
        "open": contact.is_open,
        "tags": contact.tags if contact.tags is not None else [],
    }, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def api_mark_contact_read(request, contact_id: int):
    """
    POST /wa-inbox/api/contacts/<id>/mark-read/
    Marks the contact as read: sets unread_count=0 and all INBOUND messages to status='read'.
    Call this when the user opens a conversation so the list shows 0 unread.
    """
    if not _check_wa_inbox_api_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    contact = get_object_or_404(Contact, pk=contact_id)
    contact.unread_count = 0
    contact.save(update_fields=["unread_count"])
    contact.messages.filter(direction="INBOUND").update(status="read")
    return JsonResponse({"ok": True}, status=200)
