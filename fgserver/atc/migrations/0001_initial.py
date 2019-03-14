# Generated by Django 2.1.7 on 2019-03-11 15:24

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('fgserver', '0002_auto_20190311_1442'),
    ]

    operations = [
        migrations.CreateModel(
            name='ATC',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_order_date', models.DateTimeField(blank=True, null=True)),
                ('airport', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='atc', to='fgserver.Airport')),
            ],
        ),
        migrations.CreateModel(
            name='Controller',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Controller', max_length=60)),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', model_utils.fields.StatusField(choices=[('0', 'None'), ('1', 'Stopped'), ('2', 'Pushback'), ('3', 'Taxiing'), ('4', 'Departing'), ('5', 'Turning'), ('6', 'Climbing'), ('7', 'Cruising'), ('8', 'Approaching'), ('9', 'Landing'), ('10', 'Touchdown'), ('11', 'Crosswind'), ('12', 'Downwind'), ('13', 'Base'), ('14', 'Straight'), ('15', 'Final'), ('16', 'Short of runway'), ('17', 'Lined up'), ('18', 'Tunned'), ('19', 'Parking'), ('20', 'Lining up')], default='0', max_length=100, no_check_for_status=True, verbose_name='status')),
                ('status_changed', model_utils.fields.MonitorField(default=django.utils.timezone.now, monitor='status', verbose_name='status changed')),
                ('number', models.IntegerField(default=1)),
                ('ack_order', models.CharField(blank=True, max_length=255, null=True)),
                ('aircraft', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='fgserver.Aircraft')),
                ('airport', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='fgserver.Airport')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Approach',
            fields=[
                ('controller_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='atc.Controller')),
                ('pass_alt', models.IntegerField(default=8000)),
                ('circuit_alt', models.IntegerField(default=1000)),
                ('circuit_type', models.CharField(default='left', max_length=20)),
            ],
            bases=('atc.controller',),
        ),
        migrations.CreateModel(
            name='Departure',
            fields=[
                ('controller_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='atc.Controller')),
            ],
            bases=('atc.controller',),
        ),
        migrations.CreateModel(
            name='Tower',
            fields=[
                ('controller_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='atc.Controller')),
            ],
            bases=('atc.controller',),
        ),
        migrations.AddField(
            model_name='controller',
            name='atc',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='controllers', to='atc.ATC'),
        ),
    ]
