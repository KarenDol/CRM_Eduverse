# WhatsApp Team Inbox (wa_inbox)

This app serves the **WhatsAppFront** Next.js UI so one WhatsApp number can be used across departments (SALES, SUPPORT, FINANCE, ADMIN, ACADEMIC).

## URLs

- **`/wa-inbox/`** – Redirects to the WhatsAppFront app (or shows a launch page if `WA_INBOX_FRONTEND_URL` is not set).
- **`/wa-inbox/embed/`** – Same frontend embedded in the CRM layout (iframe).

## Settings

In `user_manager/settings.py`:

- **`WA_INBOX_FRONTEND_URL`** – Base URL of the WhatsAppFront Next.js app.
  - Dev: `http://localhost:3000`
  - Production: e.g. `https://wa-inbox.yourdomain.com`

## Running the frontend

1. Start WhatsAppFront: `cd WhatsAppFront && npm run dev` (port 3000).
2. Start CRM Django: `python manage.py runserver`.
3. Log in to the CRM and open **/wa-inbox/** to be redirected to the inbox, or **/wa-inbox/embed/** to see it inside the CRM.

## CORS

The CRM already allows `http://localhost:3000` and `http://127.0.0.1:3000` in `CORS_ALLOWED_ORIGINS`. For production, add your WhatsAppFront origin.

## Wiring WhatsAppFront to CRM API (future)

WhatsAppFront currently uses in-memory mock data (`lib/store.ts`). To use the CRM backend:

1. In WhatsAppFront, add e.g. `NEXT_PUBLIC_CRM_API_URL=http://localhost:8000` (or your CRM base URL).
2. Replace `lib/store.ts` calls with `fetch(NEXT_PUBLIC_CRM_API_URL + '/wa-inbox/api/...')`.
3. Add API views in `wa_inbox/views.py` (and URLs under `/wa-inbox/api/`) for conversations, messages, notes, transfer, etc., using existing CRM models and `core` WhatsApp (Green API) where needed.

Existing CRM WhatsApp endpoints (in `core`) that may be reused:

- `POST /whatsapp/send_one/` – send one message (number, waText, optional file).
- `POST /wa_exists_one/` – check if a number has WhatsApp (JSON `{ "phone": "..." }`).

---

## Storing messages and contacts (Green API)

All messages are stored in the CRM as **Contact** (one per WhatsApp chat) and **Message** (each message points to a contact).

### Option 1: Green API webhook (recommended)

Green API can **push** each incoming/outgoing message to your CRM. No poller needed.

**1. Expose your webhook URL**

Your CRM must be reachable from the internet so Green API can POST to it.

- **Production:** Use your real domain, e.g.  
  `https://your-crm-domain.com/wa-inbox/api/green-webhook/`
- **Local dev:** Use a tunnel (e.g. [ngrok](https://ngrok.com)):  
  `ngrok http 8000` → use the HTTPS URL, e.g.  
  `https://abc123.ngrok.io/wa-inbox/api/green-webhook/`

**2. Set the URL in Green API**

- Go to [Green API Console](https://console.green-api.com).
- Open your instance (or create one).
- In **Settings** / **Notifications** (or **Webhook**), find **“Incoming webhook URL”** (or **“URL for incoming notifications”**).
- Paste your full URL, e.g.:  
  `https://your-crm-domain.com/wa-inbox/api/green-webhook/`
- Ensure **“Receive notifications about incoming messages and files”** (or equivalent) is **enabled**.
- Save.

**Via API (SetSettings):**  
If your plan supports it, you can set the webhook programmatically by calling [SetSettings](https://green-api.com/en/docs/api/account/SetSettings/) with `incomingWebhook` set to your webhook URL.

**3. (Optional) Turn off the poller**

If you were running `wa_inbox_poll_green`, you can stop it; messages will arrive via the webhook instead.

**Webhook endpoint:** `POST /wa-inbox/api/green-webhook/`  
- Expects JSON in [Green API webhook format](https://green-api.com/en/docs/api/receiving/notifications-format/incoming-message/TextMessage/) (`typeWebhook`, `senderData`, `messageData`, `timestamp`).
- Handles `incomingMessageReceived` and `outgoingMessageReceived` (text and extended text; other types store caption or empty text).
- Always returns HTTP 200 so Green API does not retry; errors are returned in the body as `{"ok": false, "error": "..."}`.

---

### Option 2: CRM polls Green API

Run the management command so the CRM fetches notifications and populates the DB:

```bash
cd user_manager
python manage.py wa_inbox_poll_green
```

Uses `GREEN_API_INSTANCE` and `GREEN_API_TOKEN` from settings (or env `GREEN_INSTANCE`, `GREEN_TOKEN`). Same credentials as the bot. Use `--interval 5` (default) or `--once` to process one batch and exit.

**Note:** Only one process should poll the same Green API instance (either this command or the bot). If you use the **webhook** (Option 1), you can stop the poller.

### Option 3: Bot pushes to CRM

In `ais_bot/wa_bot_3.py`, set:

- `CRM_BASE_URL = "http://127.0.0.1:8000"` (your CRM base URL)
- Optionally `CRM_API_KEY` if you set `WA_INBOX_API_KEY` in Django settings

The bot will POST each incoming and outgoing message to `POST /wa-inbox/api/record-message/` so Contact and Message stay in sync.

### Record-message API

- **`POST /wa-inbox/api/record-message/`**  
  Body (JSON): `chat_id`, `direction` (`"INBOUND"` | `"OUTBOUND"`), `text`, optional `timestamp` (ISO), optional `sender_name`.  
  If `WA_INBOX_API_KEY` is set in settings, send header `X-WA-Inbox-API-Key`.
