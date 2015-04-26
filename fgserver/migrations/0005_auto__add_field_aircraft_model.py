# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Aircraft.model'
        db.add_column(u'fgserver_aircraft', 'model',
                      self.gf('django.db.models.fields.CharField')(max_length=96, null=True, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Aircraft.model'
        db.delete_column(u'fgserver_aircraft', 'model')


    models = {
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
        },
        u'fgserver.order': {
            'Meta': {'object_name': 'Order'},
            'confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'receiver': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['fgserver.Aircraft']"}),
            'sender': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['fgserver.Airport']"})
        },
        u'fgserver.request': {
            'Meta': {'object_name': 'Request'},
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'request': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'sender': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['fgserver.Aircraft']"})
        },
        u'fgserver.runway': {
            'Meta': {'object_name': 'Runway'},
            'airport': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'runways'", 'to': u"orm['fgserver.Airport']"}),
            'bearing': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '5', 'decimal_places': '2'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lat': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'length': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'lon': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '3'}),
            'width': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['fgserver']