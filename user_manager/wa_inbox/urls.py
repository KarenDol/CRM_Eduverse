from django.urls import path
from . import views

app_name = "wa_inbox"

urlpatterns = [
    path("", views.inbox_app, name="inbox"),
    path("embed/", views.inbox_embed, name="inbox_embed"),
    path("api/record-message/", views.api_record_message, name="api_record_message"),
    path("api/send-message/", views.api_send_message, name="api_send_message"),
    path("api/green-webhook/", views.api_green_webhook, name="api_green_webhook"),
    path("api/me/", views.api_me, name="api_me"),
    path("api/contacts/", views.api_list_contacts, name="api_list_contacts"),
    path("api/crm-users/", views.api_list_crm_users, name="api_list_crm_users"),
    path("api/contacts/<int:contact_id>/messages/", views.api_contact_messages, name="api_contact_messages"),
    path("api/contacts/<int:contact_id>/notes/", views.api_contact_notes, name="api_contact_notes"),
    path("api/contacts/<int:contact_id>/notes/create/", views.api_contact_notes_create, name="api_contact_notes_create"),
    path("api/contacts/<int:contact_id>/history/", views.api_contact_history, name="api_contact_history"),
    path("api/contacts/<int:contact_id>/assign/", views.api_contact_assign, name="api_contact_assign"),
    path("api/contacts/<int:contact_id>/update/", views.api_contact_update, name="api_contact_update"),
    path("api/contacts/<int:contact_id>/mark-read/", views.api_mark_contact_read, name="api_mark_contact_read"),
]
