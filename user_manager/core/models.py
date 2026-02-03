from django.db import models
from django.contrib.auth.models import User

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