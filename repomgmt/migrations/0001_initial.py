# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Repository'
        db.create_table('repomgmt_repository', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200, primary_key=True)),
            ('signing_key_id', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('contact', self.gf('django.db.models.fields.EmailField')(max_length=75)),
        ))
        db.send_create_signal('repomgmt', ['Repository'])

        # Adding M2M table for field uploaders on 'Repository'
        db.create_table('repomgmt_repository_uploaders', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('repository', models.ForeignKey(orm['repomgmt.repository'], null=False)),
            ('user', models.ForeignKey(orm['auth.user'], null=False))
        ))
        db.create_unique('repomgmt_repository_uploaders', ['repository_id', 'user_id'])

        # Adding model 'UploaderKey'
        db.create_table('repomgmt_uploaderkey', (
            ('key_id', self.gf('django.db.models.fields.CharField')(max_length=200, primary_key=True)),
            ('uploader', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
        ))
        db.send_create_signal('repomgmt', ['UploaderKey'])

        # Adding model 'Series'
        db.create_table('repomgmt_series', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('repository', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.Repository'])),
            ('base_ubuntu_series', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.UbuntuSeries'])),
            ('numerical_version', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('state', self.gf('django.db.models.fields.SmallIntegerField')(default=1)),
        ))
        db.send_create_signal('repomgmt', ['Series'])

        # Adding unique constraint on 'Series', fields ['name', 'repository']
        db.create_unique('repomgmt_series', ['name', 'repository_id'])

        # Adding model 'Architecture'
        db.create_table('repomgmt_architecture', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200, primary_key=True)),
            ('builds_arch_all', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('repomgmt', ['Architecture'])

        # Adding model 'UbuntuSeries'
        db.create_table('repomgmt_ubuntuseries', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200, primary_key=True)),
        ))
        db.send_create_signal('repomgmt', ['UbuntuSeries'])

        # Adding model 'ChrootTarball'
        db.create_table('repomgmt_chroottarball', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('architecture', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.Architecture'])),
            ('series', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.UbuntuSeries'])),
            ('last_refresh', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('state', self.gf('django.db.models.fields.SmallIntegerField')(default=1)),
        ))
        db.send_create_signal('repomgmt', ['ChrootTarball'])

        # Adding unique constraint on 'ChrootTarball', fields ['architecture', 'series']
        db.create_unique('repomgmt_chroottarball', ['architecture_id', 'series_id'])

        # Adding model 'BuildRecord'
        db.create_table('repomgmt_buildrecord', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('source_package_name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('version', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('architecture', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.Architecture'])),
            ('state', self.gf('django.db.models.fields.SmallIntegerField')(default=8)),
            ('priority', self.gf('django.db.models.fields.IntegerField')(default=100)),
            ('series', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.Series'])),
            ('build_node', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.BuildNode'], null=True, blank=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('repomgmt', ['BuildRecord'])

        # Adding unique constraint on 'BuildRecord', fields ['series', 'source_package_name', 'version', 'architecture']
        db.create_unique('repomgmt_buildrecord', ['series_id', 'source_package_name', 'version', 'architecture_id'])

        # Adding model 'Cloud'
        db.create_table('repomgmt_cloud', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200, primary_key=True)),
            ('endpoint', self.gf('django.db.models.fields.URLField')(max_length=200)),
            ('user_name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('tenant_name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('password', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('region', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('flavor_name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('image_name', self.gf('django.db.models.fields.CharField')(max_length=200)),
        ))
        db.send_create_signal('repomgmt', ['Cloud'])

        # Adding model 'KeyPair'
        db.create_table('repomgmt_keypair', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cloud', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.Cloud'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('private_key', self.gf('django.db.models.fields.TextField')()),
            ('public_key', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('repomgmt', ['KeyPair'])

        # Adding unique constraint on 'KeyPair', fields ['cloud', 'name']
        db.create_unique('repomgmt_keypair', ['cloud_id', 'name'])

        # Adding model 'BuildNode'
        db.create_table('repomgmt_buildnode', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200, primary_key=True)),
            ('cloud', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['repomgmt.Cloud'])),
            ('cloud_node_id', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('state', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('signing_key_id', self.gf('django.db.models.fields.CharField')(max_length=200)),
        ))
        db.send_create_signal('repomgmt', ['BuildNode'])


    def backwards(self, orm):
        # Removing unique constraint on 'KeyPair', fields ['cloud', 'name']
        db.delete_unique('repomgmt_keypair', ['cloud_id', 'name'])

        # Removing unique constraint on 'BuildRecord', fields ['series', 'source_package_name', 'version', 'architecture']
        db.delete_unique('repomgmt_buildrecord', ['series_id', 'source_package_name', 'version', 'architecture_id'])

        # Removing unique constraint on 'ChrootTarball', fields ['architecture', 'series']
        db.delete_unique('repomgmt_chroottarball', ['architecture_id', 'series_id'])

        # Removing unique constraint on 'Series', fields ['name', 'repository']
        db.delete_unique('repomgmt_series', ['name', 'repository_id'])

        # Deleting model 'Repository'
        db.delete_table('repomgmt_repository')

        # Removing M2M table for field uploaders on 'Repository'
        db.delete_table('repomgmt_repository_uploaders')

        # Deleting model 'UploaderKey'
        db.delete_table('repomgmt_uploaderkey')

        # Deleting model 'Series'
        db.delete_table('repomgmt_series')

        # Deleting model 'Architecture'
        db.delete_table('repomgmt_architecture')

        # Deleting model 'UbuntuSeries'
        db.delete_table('repomgmt_ubuntuseries')

        # Deleting model 'ChrootTarball'
        db.delete_table('repomgmt_chroottarball')

        # Deleting model 'BuildRecord'
        db.delete_table('repomgmt_buildrecord')

        # Deleting model 'Cloud'
        db.delete_table('repomgmt_cloud')

        # Deleting model 'KeyPair'
        db.delete_table('repomgmt_keypair')

        # Deleting model 'BuildNode'
        db.delete_table('repomgmt_buildnode')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'repomgmt.architecture': {
            'Meta': {'object_name': 'Architecture'},
            'builds_arch_all': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'})
        },
        'repomgmt.buildnode': {
            'Meta': {'object_name': 'BuildNode'},
            'cloud': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.Cloud']"}),
            'cloud_node_id': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'}),
            'signing_key_id': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'state': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'})
        },
        'repomgmt.buildrecord': {
            'Meta': {'unique_together': "(('series', 'source_package_name', 'version', 'architecture'),)", 'object_name': 'BuildRecord'},
            'architecture': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.Architecture']"}),
            'build_node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.BuildNode']", 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'priority': ('django.db.models.fields.IntegerField', [], {'default': '100'}),
            'series': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.Series']"}),
            'source_package_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'state': ('django.db.models.fields.SmallIntegerField', [], {'default': '8'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'repomgmt.chroottarball': {
            'Meta': {'unique_together': "(('architecture', 'series'),)", 'object_name': 'ChrootTarball'},
            'architecture': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.Architecture']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_refresh': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'series': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.UbuntuSeries']"}),
            'state': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'})
        },
        'repomgmt.cloud': {
            'Meta': {'object_name': 'Cloud'},
            'endpoint': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'flavor_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'image_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'region': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'tenant_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'user_name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'repomgmt.keypair': {
            'Meta': {'unique_together': "(('cloud', 'name'),)", 'object_name': 'KeyPair'},
            'cloud': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.Cloud']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'private_key': ('django.db.models.fields.TextField', [], {}),
            'public_key': ('django.db.models.fields.TextField', [], {})
        },
        'repomgmt.repository': {
            'Meta': {'object_name': 'Repository'},
            'contact': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'}),
            'signing_key_id': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'uploaders': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.User']", 'symmetrical': 'False'})
        },
        'repomgmt.series': {
            'Meta': {'unique_together': "(('name', 'repository'),)", 'object_name': 'Series'},
            'base_ubuntu_series': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.UbuntuSeries']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'numerical_version': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'repository': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.Repository']"}),
            'state': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'})
        },
        'repomgmt.ubuntuseries': {
            'Meta': {'object_name': 'UbuntuSeries'},
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'})
        },
        'repomgmt.uploaderkey': {
            'Meta': {'object_name': 'UploaderKey'},
            'key_id': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'}),
            'uploader': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        }
    }

    complete_apps = ['repomgmt']