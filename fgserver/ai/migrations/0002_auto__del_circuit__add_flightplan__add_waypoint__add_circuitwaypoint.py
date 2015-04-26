# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'Circuit'
        db.delete_table(u'ai_circuit')

        # Adding model 'FlightPlan'
        db.create_table(u'ai_flightplan', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=8)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('aircraft', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['fgserver.Aircraft'])),
        ))
        db.send_create_signal(u'ai', ['FlightPlan'])

        # Adding model 'WayPoint'
        db.create_table(u'ai_waypoint', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('flightplan', self.gf('django.db.models.fields.related.ForeignKey')(related_name='waypoints', to=orm['ai.FlightPlan'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('lat', self.gf('django.db.models.fields.FloatField')(default=0)),
            ('lon', self.gf('django.db.models.fields.FloatField')(default=0)),
            ('altitude', self.gf('django.db.models.fields.FloatField')(default=0)),
            ('type', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('order', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'ai', ['WayPoint'])

        # Adding model 'CircuitWaypoint'
        db.create_table(u'ai_circuitwaypoint', (
            (u'waypoint_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['ai.WayPoint'], unique=True, primary_key=True)),
            ('circuit_type', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'ai', ['CircuitWaypoint'])


    def backwards(self, orm):
        # Adding model 'Circuit'
        db.create_table(u'ai_circuit', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=8)),
            ('altitude', self.gf('django.db.models.fields.FloatField')(default=304.8)),
            ('airport', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['fgserver.Airport'])),
            ('radius', self.gf('django.db.models.fields.FloatField')(default=3704.0)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
        ))
        db.send_create_signal(u'ai', ['Circuit'])

        # Deleting model 'FlightPlan'
        db.delete_table(u'ai_flightplan')

        # Deleting model 'WayPoint'
        db.delete_table(u'ai_waypoint')

        # Deleting model 'CircuitWaypoint'
        db.delete_table(u'ai_circuitwaypoint')


    models = {
        u'ai.circuitwaypoint': {
            'Meta': {'object_name': 'CircuitWaypoint', '_ormbases': [u'ai.WayPoint']},
            'circuit_type': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            u'waypoint_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ai.WayPoint']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'ai.flightplan': {
            'Meta': {'object_name': 'FlightPlan'},
            'aircraft': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['fgserver.Aircraft']"}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '8'})
        },
        u'ai.waypoint': {
            'Meta': {'object_name': 'WayPoint'},
            'altitude': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'flightplan': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'waypoints'", 'to': u"orm['ai.FlightPlan']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lat': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'lon': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'status': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        u'fgserver.aircraft': {
            'Meta': {'object_name': 'Aircraft'},
            'altitude': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'callsign': ('django.db.models.fields.CharField', [], {'max_length': '8'}),
            'freq': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'heading': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.CharField', [], {'max_length': '15', 'null': 'True', 'blank': 'True'}),
            'last_order': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True', 'blank': 'True'}),
            'last_request': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True', 'blank': 'True'}),
            'lat': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'lon': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '96', 'null': 'True', 'blank': 'True'}),
            'port': ('django.db.models.fields.CharField', [], {'max_length': '5', 'null': 'True', 'blank': 'True'}),
            'state': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['ai']