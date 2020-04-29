# Generated by Django 2.1.7 on 2020-04-29 00:15

import django.contrib.gis.db.models.fields
import django.contrib.gis.geos.point
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fgserver', '0009_auto_20200428_2041'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aircraftstatus',
            name='angular_accel',
            field=django.contrib.gis.db.models.fields.PointField(default=django.contrib.gis.geos.point.Point(0, 0, 0), dim=3, srid=4326, verbose_name='Angular acceleration'),
        ),
        migrations.AlterField(
            model_name='aircraftstatus',
            name='angular_vel',
            field=django.contrib.gis.db.models.fields.PointField(default=django.contrib.gis.geos.point.Point(0, 0, 0), dim=3, srid=4326, verbose_name='Angular velocity'),
        ),
        migrations.AlterField(
            model_name='aircraftstatus',
            name='freq',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='aircraftstatus',
            name='linear_accel',
            field=django.contrib.gis.db.models.fields.PointField(default=django.contrib.gis.geos.point.Point(0, 0, 0), dim=3, srid=4326, verbose_name='Linear acceleration'),
        ),
        migrations.AlterField(
            model_name='aircraftstatus',
            name='linear_vel',
            field=django.contrib.gis.db.models.fields.PointField(default=django.contrib.gis.geos.point.Point(0, 0, 0), dim=3, srid=4326, verbose_name='Linear velocity'),
        ),
        migrations.AlterField(
            model_name='aircraftstatus',
            name='message',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='aircraftstatus',
            name='orientation',
            field=django.contrib.gis.db.models.fields.PointField(default=django.contrib.gis.geos.point.Point(0, 0, 0), dim=3, srid=4326, verbose_name='Orientation'),
        ),
        migrations.AlterField(
            model_name='aircraftstatus',
            name='position',
            field=django.contrib.gis.db.models.fields.PointField(default=django.contrib.gis.geos.point.Point(0, 0, 0), dim=3, srid=4326, verbose_name='Position'),
        ),
    ]
