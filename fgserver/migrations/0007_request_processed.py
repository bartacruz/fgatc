# Generated by Django 2.1.7 on 2020-04-28 04:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fgserver', '0006_request_received'),
    ]

    operations = [
        migrations.AddField(
            model_name='request',
            name='processed',
            field=models.BooleanField(default=False),
        ),
    ]