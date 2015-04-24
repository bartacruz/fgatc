# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Circuit'
        db.create_table(u'ai_circuit', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('airport', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['fgserver.Airport'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=8)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('radius', self.gf('django.db.models.fields.FloatField')(default=3704.0)),
            ('altitude', self.gf('django.db.models.fields.FloatField')(default=304.8)),
        ))
        db.send_create_signal(u'ai', ['Circuit'])


    def backwards(self, orm):
        # Deleting model 'Circuit'
        db.delete_table(u'ai_circuit')


    models = {
        u'ai.circuit': {
            'Meta': {'object_name': 'Circuit'},
            'airport': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['fgserver.Airport']"}),
            'altitude': ('django.db.models.fields.FloatField', [], {'default': '304.8'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '8'}),
            'radius': ('django.db.models.fields.FloatField', [], {'default': '3704.0'})
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