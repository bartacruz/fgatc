# Generated by Django 2.1.7 on 2020-05-20 17:09

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fgserver', '0010_auto_20200429_0015'),
        ('ai', '0002_auto_20200428_1852'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaxiNode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
                ('point', django.contrib.gis.db.models.fields.PointField(srid=4326)),
                ('short', models.BooleanField(default=False)),
                ('adjacents', models.ManyToManyField(related_name='_taxinode_adjacents_+', to='ai.TaxiNode')),
                ('airport', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='taxinodes', to='fgserver.Airport')),
            ],
        ),
        migrations.CreateModel(
            name='TaxiWay',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
                ('airport', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='taxi_ways', to='fgserver.Airport')),
                ('nodes', models.ManyToManyField(to='ai.TaxiNode')),
            ],
        ),
        migrations.AlterField(
            model_name='waypoint',
            name='status',
            field=models.IntegerField(blank=True, choices=[(0, 'None'), (1, 'Stopped'), (2, 'Pushback'), (3, 'Taxiing'), (4, 'Departing'), (5, 'Turning'), (6, 'Climbing'), (7, 'Cruising'), (8, 'Approaching'), (9, 'Landing'), (10, 'Touchdown'), (11, 'Crosswind'), (12, 'Downwind'), (13, 'Base'), (14, 'Straight'), (15, 'Final'), (16, 'Short of runway'), (17, 'Lined up'), (18, 'Tunned'), (19, 'Parking'), (20, 'Lining up'), (21, 'On Hold'), (22, 'Rolling')], null=True),
        ),
    ]
