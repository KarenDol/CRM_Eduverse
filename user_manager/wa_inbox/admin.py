from django.contrib import admin
from .models import Contact, Message, Note, ContactHistory


class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("timestamp", "created_at")
    ordering = ("-timestamp",)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("phone", "name", "department", "status", "priority", "unread_count", "is_open", "last_message_at")
    list_filter = ("department", "status", "priority", "sla_state", "is_open")
    search_fields = ("phone", "name")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MessageInline, NoteInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("contact", "direction", "text_preview", "timestamp", "status")
    list_filter = ("direction", "status")
    search_fields = ("text", "contact__phone", "contact__name")
    raw_id_fields = ("contact",)
    readonly_fields = ("created_at",)

    def text_preview(self, obj):
        return (obj.text[:60] + "...") if len(obj.text) > 60 else obj.text

    text_preview.short_description = "Text"


@admin.register(ContactHistory)
class ContactHistoryAdmin(admin.ModelAdmin):
    list_display = ("contact", "event_type", "actor", "description_short", "created_at")
    list_filter = ("event_type",)
    search_fields = ("description", "actor", "contact__phone")
    raw_id_fields = ("contact",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def description_short(self, obj):
        return (obj.description[:60] + "...") if len(obj.description) > 60 else obj.description

    description_short.short_description = "Description"
