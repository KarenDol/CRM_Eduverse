from django.urls import path
from . import views

app_name = "wa_inbox"

urlpatterns = [
    path("", views.inbox_app, name="inbox"),
    path("embed/", views.inbox_embed, name="inbox_embed"),
    path("api/record-message/", views.api_record_message, name="api_record_message"),
    path("api/green-webhook/", views.api_green_webhook, name="api_green_webhook"),
    path("api/contacts/", views.api_list_contacts, name="api_list_contacts"),
    path("api/contacts/<int:contact_id>/messages/", views.api_contact_messages, name="api_contact_messages"),
]
