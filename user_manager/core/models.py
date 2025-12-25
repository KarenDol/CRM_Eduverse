from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class CRM_User(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    picture = models.CharField(max_length=150, default='Avatar.png') #user_picture
    user_type = models.CharField(max_length=50, default='Админ')
    phone = models.CharField(max_length=20, null=True)
    email = models.CharField(max_length=100, null=True)