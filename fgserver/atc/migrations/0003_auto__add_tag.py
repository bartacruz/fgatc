# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Tag'
        db.create_table(u'atc_tag', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('status', self.gf('model_utils.fields.StatusField')(default='0', max_length=100, no_check_for_status=True)),
            ('status_changed', self.gf('model_utils.fields.MonitorField')(default=datetime.datetime.now, monitor=u'status')),
            ('atc', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['atc.ATC'])),
            ('aircraft', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['fgserver.Aircraft'])),
            ('number', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('ack_order', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
        ))
        db.send_create_signal(u'atc', ['Tag'])


    def backwards(self, orm):
        # Deleting model 'Tag'
        db.delete_table(u'atc_tag')


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
        u'atc.tag': {
            'Meta': {'object_name': 'Tag'},
            'ack_order': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'aircraft': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['fgserver.Aircraft']"}),
            'atc': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['atc.ATC']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'status': ('model_utils.fields.StatusField', [], {'default': "'0'", 'max_length': '100', u'no_check_for_status': 'True'}),
            'status_changed': ('model_utils.fields.MonitorField', [], {'default': 'datetime.datetime.now', u'monitor': "u'status'"})
        },
        u'atc.tower': {
            'Meta': {'object_name': 'Tower', '_ormbases': [u'atc.Controller']},
            u'controller_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['atc.Controller']", 'unique': 'True', 'primary_key': 'True'})
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

    complete_apps = ['atc']