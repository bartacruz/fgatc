# Generated by Django 2.1.7 on 2019-03-18 04:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fgserver', '0002_auto_20190311_1442'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='lost',
            field=models.BooleanField(default=False),
        ),
    ]