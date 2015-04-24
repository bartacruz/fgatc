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
            ('icao', self.gf('django.db.models.fields.CharField')(max_length=4, db_index=True)),
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
            ('width', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('length', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('lat', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=10, decimal_places=6)),
            ('lon', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=10, decimal_places=6)),
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
            ('ip', self.gf('django.db.models.fields.CharField')(max_length=15, null=True, blank=True)),
            ('port', self.gf('django.db.models.fields.CharField')(max_length=5, null=True, blank=True)),
        ))
        db.send_create_signal(u'fgserver', ['Aircraft'])

        # Adding model 'Request'
        db.create_table(u'fgserver_request', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')()),
            ('sender', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['fgserver.Aircraft'])),
            ('request', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'fgserver', ['Request'])

        # Adding model 'Order'
        db.create_table(u'fgserver_order', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')()),
            ('receiver', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['fgserver.Aircraft'])),
            ('sender', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['fgserver.Airport'])),
            ('order', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('message', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('confirmed', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'fgserver', ['Order'])


    def backwards(self, orm):
        # Deleting model 'Airport'
        db.delete_table(u'fgserver_airport')

        # Deleting model 'Runway'
        db.delete_table(u'fgserver_runway')

        # Deleting model 'Aircraft'
        db.delete_table(u'fgserver_aircraft')

        # Deleting model 'Request'
        db.delete_table(u'fgserver_request')

        # Deleting model 'Order'
        db.delete_table(u'fgserver_order')


    models = {
        u'fgserver.aircraft': {
            'Meta': {'object_name': 'Aircraft'},
            'altitude': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'callsign': ('django.db.models.fields.CharField', [], {'max_length': '8'}),
            'freq': ('django.db.models.fields.CharField', [], {'max_length': '8', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.CharField', [], {'max_length': '15', 'null': 'True', 'blank': 'True'}),
            'last_order': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'last_request': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'lat': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
            'lon': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '10', 'decimal_places': '6'}),
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