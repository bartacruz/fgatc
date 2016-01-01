# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Circuit.enabled'
        db.add_column(u'ai_circuit', 'enabled',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Circuit.enabled'
        db.delete_column(u'ai_circuit', 'enabled')


    models = {
        u'ai.circuit': {
            'Meta': {'object_name': 'Circuit', '_ormbases': [u'ai.FlightPlan']},
            'airport': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'circuits'", 'to': u"orm['fgserver.Airport']"}),
            'altitude': ('django.db.models.fields.FloatField', [], {'default': '304.8'}),
            'enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'flightplan_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ai.FlightPlan']", 'unique': 'True', 'primary_key': 'True'}),
            'radius': ('django.db.models.fields.FloatField', [], {'default': '3704.0'})
        },
        u'ai.circuitwaypoint': {
            'Meta': {'object_name': 'CircuitWaypoint', '_ormbases': [u'ai.WayPoint']},
            'circuit_type': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            u'waypoint_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ai.WayPoint']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'ai.flightplan': {
            'Meta': {'object_name': 'FlightPlan'},
            'aircraft': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'plans'", 'to': u"orm['fgserver.Aircraft']"}),
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
        },
        u'fgserver.airport': {
            'Meta': {'object_name': 'Airport'},
            'altitude': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'icao': ('django.db.models.fields.CharField', [], {'max_length': '4', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lat': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'lon': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['ai']