# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Airport'
        db.create_table(u'fgserver_airport', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('icao', self.gf('django.db.models.fields.CharField')(max_length=4)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('lat', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=10, decimal_places=6)),
            ('lon', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=10, decimal_places=6)),
            ('altitude', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'fgserver', ['Airport'])

        # Adding model 'Runway'
        db.create_table(u'fgserver_runway', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('airport', self.gf('django.db.models.fields.related.ForeignKey')(related_name='runways', to=orm['fgserver.Airport'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=3)),
            ('bearing', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=5, decimal_places=2)),
        ))
        db.send_create_signal(u'fgserver', ['Runway'])

        # Adding model 'Aircraft'
        db.create_table(u'fgserver_aircraft', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('callsign', self.gf('django.db.models.fields.CharField')(max_length=8)),
            ('freq', self.gf('django.db.models.fields.CharField')(max_length=8, null=True, blank=True)),
            ('lat', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=10, decimal_places=6)),
            ('lon', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=10, decimal_places=6)),
            ('altitude', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('state', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('last_request', self.gf('django.db.models.fields.CharField')(max_length=10, null=True, blank=True)),
            ('last_order', self.gf('django.db.models.fields.CharField')(max_length=10, null=True, blank=True)),
        ))
        db.send_create_signal(u'fgserver', ['Aircraft'])

        # Adding model 'ControllerAlgo'
        db.create_table(u'fgserver_controlleralgo', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'fgserver', ['ControllerAlgo'])


    def backwards(self, orm):
        # Deleting model 'Airport'
        db.delete_table(u'fgserver_airport')

        # Deleting model 'Runway'
        db.delete_table(u'fgserver_runway')

        # Deleting model 'Aircraft'
        db.delete_table(u'fgserver_aircraft')

        # Deleting model 'ControllerAlgo'
        db.delete_table(u'fgserver_controlleralgo')


    models = {
        u'fgserver.aircraft': {
            'Meta': {'object_name': 'Aircraft'},
            'altitude': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'callsign': ('django.db.models.fields.CharField', [], {'max_length': '8'}),
            'freq': ('django.db.models.fields.CharField', [], {'max_length': '8', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_order': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'last_request': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'lat': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'lon': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'state': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'fgserver.airport': {
            'Meta': {'object_name': 'Airport'},
            'altitude': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'icao': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lat': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'lon': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'fgserver.controlleralgo': {
            'Meta': {'object_name': 'ControllerAlgo'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'fgserver.runway': {
            'Meta': {'object_name': 'Runway'},
            'airport': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'runways'", 'to': u"orm['fgserver.Airport']"}),
            'bearing': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '5', 'decimal_places': '2'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '3'})
        }
    }

    complete_apps = ['fgserver']