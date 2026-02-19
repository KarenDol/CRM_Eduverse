from django.db import models
from django.contrib.auth.models import User
import uuid

client_status = [
    ('Лид', 'В работе'),
    ('Акт', 'Подтвердил'),
    ('Арх', 'Отказ'),
]

# Create your models here.
class CRM_User(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    picture = models.CharField(max_length=150, default='Avatar.png') #user_picture
    user_type = models.CharField(max_length=50, default='Админ')
    phone = models.CharField(max_length=20, null=True)
    email = models.CharField(max_length=100, null=True)

class Product(models.Model):
    name = models.CharField(max_length=100)

class Client(models.Model):
    participant_id = models.IntegerField()
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=100)
    email = models.CharField(max_length=100, null=True)
    phone = models.CharField(max_length=20)
    results = models.TextField()
    note = models.TextField(null=True)
    grade = models.IntegerField()
    school = models.CharField(max_length=150)
    countryId = models.IntegerField()

class WhatsAppAccount(models.Model):
    phone = models.CharField(max_length=20)
    idInstance = models.CharField(max_length=10)
    apiTokenInstance = models.CharField(max_length=50)

class Deal(models.Model):
    product = models.ForeignKey(
        "Product",
        on_delete=models.PROTECT,
        related_name="deals",
    )
    client = models.ForeignKey(
        "Client",
        on_delete=models.CASCADE,
        related_name="deals",
    )
    status = models.CharField(max_length=30, choices=client_status, default='Лид')

    created_at = models.DateTimeField(auto_now_add=True)

class EmailTemplate(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    # the raw HTML string
    html = models.TextField()

    # optional metadata (nice to have)
    title = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # If you want per-user ownership later:
    # owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.uuid} ({self.created_at:%Y-%m-%d %H:%M})"