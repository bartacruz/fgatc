# Generated by Django 2.1.7 on 2019-03-20 12:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('atc', '0002_auto_20190316_1346'),
    ]

    operations = [
        migrations.AddField(
            model_name='atc',
            name='active',
            field=models.BooleanField(default=False),
        ),
    ]