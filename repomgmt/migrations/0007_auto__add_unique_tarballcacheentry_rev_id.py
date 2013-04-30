# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding unique constraint on 'TarballCacheEntry', fields ['rev_id']
        db.create_unique('repomgmt_tarballcacheentry', ['rev_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'TarballCacheEntry', fields ['rev_id']
        db.delete_unique('repomgmt_tarballcacheentry', ['rev_id'])


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
            'finished': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
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
        'repomgmt.packagesource': {
            'Meta': {'object_name': 'PackageSource'},
            'code_url': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'flavor': ('django.db.models.fields.CharField', [], {'default': "'OpenStack'", 'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_changed': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'last_seen_code_rev': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'last_seen_pkg_rev': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'packaging_url': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'repomgmt.packagesourcebuildproblem': {
            'Meta': {'object_name': 'PackageSourceBuildProblem'},
            'code_rev': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'code_url': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'flavor': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'packaging_url': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'pkg_rev': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'})
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
            'state': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'update_from': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.Series']", 'null': 'True', 'blank': 'True'})
        },
        'repomgmt.subscription': {
            'Meta': {'object_name': 'Subscription'},
            'counter': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.PackageSource']"}),
            'target_series': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['repomgmt.Series']"})
        },
        'repomgmt.tarballcacheentry': {
            'Meta': {'object_name': 'TarballCacheEntry'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'project_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'project_version': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'rev_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200', 'db_index': 'True'})
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