# Generated migration for Client.user_id

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_alter_deal_product_alter_deal_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='user_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
