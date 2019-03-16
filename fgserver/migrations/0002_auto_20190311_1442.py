# Generated by Django 2.1.7 on 2019-03-11 14:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fgserver', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='circuit',
            name='airport',
        ),
        migrations.RemoveField(
            model_name='circuit',
            name='flightplan_ptr',
        ),
        migrations.RemoveField(
            model_name='circuitwaypoint',
            name='waypoint_ptr',
        ),
        migrations.RemoveField(
            model_name='flightplan',
            name='aircraft',
        ),
        migrations.RemoveField(
            model_name='waypoint',
            name='flightplan',
        ),
        migrations.DeleteModel(
            name='Circuit',
        ),
        migrations.DeleteModel(
            name='CircuitWaypoint',
        ),
        migrations.DeleteModel(
            name='FlightPlan',
        ),
        migrations.DeleteModel(
            name='WayPoint',
        ),
    ]