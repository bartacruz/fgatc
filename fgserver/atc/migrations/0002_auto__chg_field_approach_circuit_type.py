# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'Approach.circuit_type'
        db.alter_column(u'atc_approach', 'circuit_type', self.gf('django.db.models.fields.CharField')(max_length=20))

    def backwards(self, orm):

        # Changing field 'Approach.circuit_type'
        db.alter_column(u'atc_approach', 'circuit_type', self.gf('django.db.models.fields.IntegerField')())

    models = {
        u'atc.approach': {
            'Meta': {'object_name': 'Approach', '_ormbases': [u'atc.Controller']},
            'circuit_alt': ('django.db.models.fields.IntegerField', [], {'default': '1000'}),
            'circuit_type': ('django.db.models.fields.CharField', [], {'default': "'left'", 'max_length': '20'}),
            u'controller_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['atc.Controller']", 'unique': 'True', 'primary_key': 'True'}),
            'pass_alt': ('django.db.models.fields.IntegerField', [], {'default': '8000'})
        },
        u'atc.atc': {
            'Meta': {'object_name': 'ATC'},
            'airport': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'atc'", 'to': u"orm['fgserver.Airport']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'atc.controller': {
            'Meta': {'object_name': 'Controller'},
            'atc': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'controllers'", 'to': u"orm['atc.ATC']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Controller'", 'max_length': '60'})
        },
        u'atc.departure': {
            'Meta': {'object_name': 'Departure', '_ormbases': [u'atc.Controller']},
            u'controller_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['atc.Controller']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'atc.tower': {
            'Meta': {'object_name': 'Tower', '_ormbases': [u'atc.Controller']},
            u'controller_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['atc.Controller']", 'unique': 'True', 'primary_key': 'True'})
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

    complete_apps = ['atc']