#
#   Copyright 2012 Cisco Systems, Inc.
#
#   Author: Soren Hansen <sorhanse@cisco.com>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
from base64 import b64encode
from contextlib import contextmanager
import json
import mock
import textwrap
from StringIO import StringIO

from django.contrib.auth.models import User
from django.test import TestCase, client
from django.test.utils import override_settings
from repomgmt.models import Cloud, BuildNode, BuildRecord, KeyPair, Repository
from repomgmt.models import Series, UploaderKey, PackageSource, Subscription


class CloudTests(TestCase):
    test_user = 'testuser1'
    test_tenant = 'testtenant1'
    test_password = 'testpassword1'
    test_endpoint = 'http://example.com/v2.0'

    def _create(self):
        cloud = Cloud(name='testcloud1',
                      endpoint=self.test_endpoint,
                      user_name=self.test_user,
                      tenant_name=self.test_tenant,
                      password=self.test_password)
        cloud.save()
        return cloud

    def test_create(self):
        self._create()

    def test_cloud_client(self):
        cloud = self._create()
        with mock.patch('repomgmt.models.client') as client:
            cloud.client
            client.Client.assert_called_with(self.test_user,
                                             self.test_password,
                                             self.test_tenant,
                                             self.test_endpoint,
                                             service_type='compute',
                                             no_cache=True)

    def test_cloud_client_conn_reused(self):
        cloud = self._create()
        with mock.patch('repomgmt.models.client') as client:
            cloud.client
            cloud.client
            self.assertEquals(client.Client.call_count, 1)

    def test_unicode(self):
        cloud = self._create()
        self.assertEquals('%s' % (cloud,), 'testcloud1')


class KeyPairTests(TestCase):
    fixtures = ['test_cloud.yaml']

    def _create(self):
        cloud = Cloud.objects.get(pk='test_cloud')

        with open('repomgmt/fixtures/test-ssh-key') as fp:
            private_key = fp.read()

        with open('repomgmt/fixtures/test-ssh-key.pub') as fp:
            public_key = fp.read()

        keypair = KeyPair(name='keypair1',
                          cloud=cloud,
                          private_key=private_key,
                          public_key=public_key)

        keypair.save()
        return keypair

    def test_create(self):
        self._create()

    def test_unicode(self):
        keypair = self._create()
        self.assertEquals('%s' % (keypair,), 'keypair1@test_cloud')


class BuildNodeTests(TestCase):
    fixtures = ['test_cloud.yaml', 'test_keypair.yaml']

    test_name = 'build-345'
    test_id = 'f8c9785b-0146-41ca-accc-8e0b73913f48'
    test_ip = '10.11.12.13'

    def _create(self):
        cloud = Cloud.objects.get(name='test_cloud')

        build_node = BuildNode(name=self.test_name, cloud=cloud,
                               cloud_node_id=self.test_id)
        build_node.save()
        return build_node

    def test_create(self):
        self._create()

    def test_keypair(self):
        bn = self._create()
        self.assertEquals(bn.keypair, KeyPair.objects.get(pk=1))

    def test_paramiko_private_key(self):
        bn = self._create()

        with open('repomgmt/fixtures/test-ssh-key.pub') as fp:
            self.assertEquals(fp.read().split(' ')[1],
                              bn.paramiko_private_key.get_base64())

    def test_ip(self):
        bn = self._create()
        with mock.patch.object(Cloud, 'client') as client:
            networks = {'somenet': [self.test_ip]}
            client.servers.get.return_value.networks = networks

            self.assertEquals(bn.ip, self.test_ip)
            client.servers.get.assert_called_with(self.test_id)


class BuildSchedulerTests(TestCase):
    fixtures = ["test_series.yaml", "test_cloud.yaml"]

    def test_pending_builds(self):
        self.assertEquals(BuildRecord.pending_build_count(), 0)

        BuildRecord(series_id=1, architecture_id=1, priority=100,
                    source_package_name='foo1', version='1.2-2ubuntu2').save()
        self.assertEquals(BuildRecord.pending_build_count(), 1)

        BuildRecord(series_id=1, architecture_id=1, priority=200,
                    source_package_name='foo2', version='1.2-2ubuntu2').save()
        self.assertEquals(BuildRecord.pending_build_count(), 2)

    def test_no_pending_builds(self):
        bn = BuildNode(cloud_id=1).save()
        br = BuildRecord.pick_build(bn)
        self.assertIsNone(br)

    def test_high_priority_takes_precedence(self):
        br1 = BuildRecord(series_id=1, architecture_id=1, priority=100,
                          source_package_name='foo1', version='1.2-2ubuntu2')
        br1.save()

        br2 = BuildRecord(series_id=1, architecture_id=1, priority=200,
                          source_package_name='foo2', version='1.2-2ubuntu2')
        br2.save()

        br3 = BuildRecord(series_id=1, architecture_id=1, priority=150,
                          source_package_name='foo3', version='1.2-2ubuntu2')
        br3.save()

        self.assertEquals(BuildRecord.pending_build_count(), 3)
        bn = BuildNode(cloud_id=1).save()
        br = BuildRecord.pick_build(bn)
        self.assertEquals(br, br2)


class SeriesTests(TestCase):
    fixtures = ['test_series.yaml']
    reprepro_list = '''\
        folsom-proposed|main|i386: cinder-api 2012.2.1~+cisco-folsom1260-53
        folsom-proposed|main|i386: cinder-common 2012.2.1~+cisco-folsom1260-53
        folsom-proposed|main|amd64: cinder-api 2012.2.1~+cisco-folsom1260-53
        folsom-proposed|main|amd64: cinder-common 2012.2.1~+cisco-folsom1260-53
        folsom-proposed|main|source: cinder 2012.2.1~+cisco-folsom1260-53'''

    @override_settings(BASE_REPO_DIR='/base/repo/dir')
    def test_get_packages(self):
        with mock.patch('repomgmt.utils.run_cmd') as run_cmd:
            series = Series.objects.get(name='folsom')
            run_cmd.return_value = textwrap.dedent(self.reprepro_list)
            pkg_list = list(series.get_source_packages())
            calls = []
            calls += [mock.call(['reprepro', '-b',
                                 '/base/repo/dir/cisco', '-A', 'source',
                                 'list', 'folsom-queued'])]
            calls += [mock.call(['reprepro', '-b',
                                 '/base/repo/dir/cisco', '-A', 'source',
                                 'list', 'folsom-proposed'])]
            calls += [mock.call(['reprepro', '-b',
                                 '/base/repo/dir/cisco', '-A', 'source',
                                 'list', 'folsom'])]
            run_cmd.assert_has_calls(calls, any_order=True)
            self.assertEquals(len(pkg_list), 3)

class RepositoryTests(TestCase):
    def test_repository_unicode(self):
        repo = Repository(name='foo')
        self.assertEquals('%s' % (repo,), 'foo')

    def test_create_new_repository(self):
        repo_set = set(Repository.objects.all())

        c = client.Client()
        response = c.get('/repositories/')
        self.assertContains(response,
                            '<a href="/repositories/new/" class="btn pull-right">Create new</a>',
                            html=True)

        response = c.get('/repositories/new/')
        self.assertContains(response,
                            '<form action="/repositories/" method="post">')

        with mock.patch('repomgmt.models.Repository.create_key') as create_key:
            response = c.post('/repositories/', {'action': 'create',
                                                 'name': 'foo',
                                                 'contact': 'foo@example.com'})
            self.assertRedirects(response, '/repositories/')
            create_key.assert_called_with()

        new_repos = set(Repository.objects.all()) - repo_set
        self.assertEquals(len(new_repos), 1)
        new_repo = new_repos.pop()

        self.assertEquals(new_repo.name, 'foo')
        self.assertEquals(new_repo.contact, 'foo@example.com')

class ImportDscToGitCommandTests(TestCase):
    def setUp(self):
        mod = __import__("repomgmt.management.commands.repo-import-dsc-to-git")
        self.module = getattr(mod.management.commands, 'repo-import-dsc-to-git')
        return super(ImportDscToGitCommandTests, self).setUp()

    def test_get_repository_name(self):
        basedir = '/base/dir'
        with self.settings(BASE_REPO_DIR=basedir):
            name = self.module.get_repository_name({}, {'REPREPRO_BASE_DIR': '/base/dir/myrepo'})
            self.assertEquals(name, 'myrepo')

    def test_get_repository_name_trailing_slash(self):
        basedir = '/base/dir'
        with self.settings(BASE_REPO_DIR=basedir):
            name = self.module.get_repository_name({}, {'REPREPRO_BASE_DIR': '/base/dir/myrepo/'})
            self.assertEquals(name, 'myrepo')

    def test_get_repository_name_from_options(self):
        basedir = '/base/dir'
        with self.settings(BASE_REPO_DIR=basedir):
            name = self.module.get_repository_name({'repository': 'otherrepo'},
                                                   {'REPREPRO_BASE_DIR': '/base/dir/myrepo'})
            self.assertEquals(name, 'otherrepo')

    def test_parse_dsc_file(self):
        f = StringIO()
        @contextmanager
        def fake_open(filename, mode):
            self.assertEquals(mode, 'r')
            yield f
            f.close()

        with mock.patch('__builtin__.open', fake_open):
            with mock.patch('repomgmt.management.commands.repo-import-dsc-to-git.Dsc') as Dsc:
                self.module.parse_dsc_file('foo')
                self.assertTrue(f.closed)
                Dsc.assert_called_with(f)


class UrlMatchingTests(TestCase):
    fixtures = ['repos.yaml']

    def test_repository_list(self):
        c = client.Client()
        response = c.get('/repositories/')
        self.assertEquals(response.status_code, 200)

    def test_series_list(self):
        for repo in Repository.objects.all():
            c = client.Client()
            response = c.get('/repositories/%s/' % (repo.name,))
            self.assertEquals(response.status_code, 200)
            self.assertIn('seriess.html',
                          [t.name for t in response.templates])

    def test_package_list(self):
        with mock.patch('repomgmt.models.Series.get_source_packages') as get_source_packages:
            for series in Series.objects.all():
                c = client.Client()
                url = '/repositories/%s/%s/' % (series.repository.name, series.name)
                response = c.get(url)
                self.assertEquals(response.status_code, 200)
                self.assertIn('packages.html',
                              [t.name for t in response.templates])

    def test_new_repository_form(self):
        c = client.Client()
        response = c.get('/repositories/new/')
        self.assertEquals(response.status_code, 200)
        self.assertIn('new_repository_form.html',
                      [t.name for t in response.templates])

    def test_new_series_form(self):
        for repo in Repository.objects.all():
            c = client.Client()
            response = c.get('/repositories/%s/new/' % (repo.name,))
            self.assertEquals(response.status_code, 200)
            self.assertIn('new_series_form.html',
                          [t.name for t in response.templates])

    def test_repository_key(self):
        for repo in Repository.objects.all():
            c = client.Client()
            response = c.get('/repositories/%s/key/' % (repo.name,))
            self.assertEquals(response.status_code, 200)

class PermissionsTests(TestCase):
    def setUp(self):
        self._create_users()
        super(PermissionsTests, self).setUp()

    def _create_users(self):
        self.user1 = User(username='user1')
        self.user1.save()

        self.user2 = User(username='user2')
        self.user2.save()

        self.user3 = User(username='user3')
        self.user3.save()

        self.superuser = User(username='superuser')
        self.superuser.is_superuser = True
        self.superuser.save()

    def _test_dump(self):
        for x in Cloud, BuildNode, BuildRecord, KeyPair, Repository, User, UploaderKey:
            print x.objects.all()

    def test_repo_perm(self):
        repo = Repository(name='repo1')
        repo.save()
        repo.uploaders.add(self.user1)

        self.assertTrue(repo.can_modify(self.user1), 'User1 cannot modify repository')
        self.assertFalse(repo.can_modify(self.user2), 'User2 can modify repository')
        self.assertTrue(repo.can_modify(self.superuser), 'Super user cannot modify repository')

    def test_series_perm(self):
        repo = Repository(name='repo1')
        repo.save()
        repo.uploaders.add(self.user1)
        repo.save()

        series = Series(name='series1', base_ubuntu_series_id='precise', repository=repo)
        series.save()

        self.assertTrue(series.can_modify(self.user1), 'User1 cannot modify repository')
        self.assertFalse(series.can_modify(self.user2), 'User2 can modify repository')
        self.assertTrue(series.can_modify(self.superuser), 'Super user cannot modify repository')

    def test_subscription_perm(self):
        repo = Repository(name='repo1')
        repo.save()
        repo.uploaders.add(self.user1)
        repo.save()

        series = Series(name='series1', base_ubuntu_series_id='precise', repository=repo)
        series.save()

        pkg_src = PackageSource(code_url='scheme://foo/bar', packaging_url='scheme://foo/bar',
                                flavor='OpenStack')
        pkg_src.save()

        sub = Subscription(target_series=series, source=pkg_src, counter=1)
        sub.save()
        self.assertTrue(sub.can_modify(self.user1), 'User1 cannot modify repository')
        self.assertFalse(sub.can_modify(self.user2), 'User2 can modify repository')
        self.assertTrue(sub.can_modify(self.superuser), 'Super user cannot modify repository')

    def test_pkg_src_perm(self):
        repo1 = Repository(name='repo1')
        repo1.save()
        repo1.uploaders.add(self.user1)
        repo1.uploaders.add(self.user3)
        repo1.save()

        repo2 = Repository(name='repo2')
        repo2.save()
        repo2.uploaders.add(self.user2)
        repo2.uploaders.add(self.user3)
        repo2.save()

        series1 = Series(name='series1', base_ubuntu_series_id='precise', repository=repo1)
        series1.save()

        series2 = Series(name='series2', base_ubuntu_series_id='precise', repository=repo2)
        series2.save()

        pkg_src = PackageSource(code_url='scheme://foo/bar', packaging_url='scheme://foo/bar', flavor='OpenStack')
        pkg_src.save()

        sub1 = Subscription(target_series=series1, source=pkg_src, counter=1)
        sub1.save()
        sub2 = Subscription(target_series=series2, source=pkg_src, counter=1)
        sub2.save()
        self.assertFalse(pkg_src.can_modify(self.user1), 'User1 can modify repository')
        self.assertFalse(pkg_src.can_modify(self.user2), 'User2 can modify repository')
        self.assertTrue(pkg_src.can_modify(self.user3), 'User3 cannot modify repository')
        self.assertTrue(pkg_src.can_modify(self.superuser), 'Super user cannot modify repository')

class APIPermissionsTest(TestCase):
    def setUp(self):
        self._create_users()
        super(APIPermissionsTest, self).setUp()

    def _get_client(self, username):
        class Client(object):
            def __init__(self, username):
                self.client = client.Client(HTTP_AUTHORIZATION=('Basic ' + b64encode(('%s:%s' % (username, 'password')))))

            def post(self, uri, data):
                return self.client.post(uri, json.dumps(data), content_type='application/json')

            def delete(self, uri):
                return self.client.delete(uri)

        return Client(username)

    def _create_users(self):
        self.user1 = User(username='user1')
        self.user1.set_password('password')
        self.user1.save()

        self.user2 = User(username='user2')
        self.user2.set_password('password')
        self.user2.save()

        self.superuser = User(username='superuser')
        self.superuser.set_password('password')
        self.superuser.is_superuser = True
        self.superuser.save()

    def test_superuser_can_create_architecture(self):
        c = self._get_client('superuser')
        response = c.post('/api/v1/architecture/', {'name': 'aarch64'})
        self.assertEquals(response.status_code, 201)

    def test_regular_user_cannot_create_architecture(self):
        c = self._get_client('user1')
        response = c.post('/api/v1/architecture/', {'name': 'aarch64'})
        self.assertEquals(response.status_code, 401)

    def test_regular_user_can_create_repository(self):
        c = self._get_client('user1')
        response = c.post('/api/v1/repository/', {'name': 'testuserrepo'})
        self.assertEquals(response.status_code, 201)

    def test_superuser_can_create_repository(self):
        c = self._get_client('superuser')
        response = c.post('/api/v1/repository/', {'name': 'testuserrepo'})
        self.assertEquals(response.status_code, 201)

    def test_user_can_delete_own_repository(self):
        c = self._get_client('user1')
        response = c.post('/api/v1/repository/', {'name': 'testuserrepo'})
        self.assertEquals(response.status_code, 201)
        response = c.delete('/api/v1/repository/testuserrepo/')
        self.assertEquals(response.status_code, 204)

    def test_user_cannot_delete_someone_elses_repository(self):
        c = self._get_client('user1')
        response = c.post('/api/v1/repository/', {'name': 'testuserrepo'})
        self.assertEquals(response.status_code, 201)
        c = self._get_client('user2')
        response = c.delete('/api/v1/repository/testuserrepo/')
        self.assertEquals(response.status_code, 401)

    def test_user_can_create_series_on_own_repository(self):
        c = self._get_client('user1')
        response = c.post('/api/v1/repository/', {'name': 'testuserrepo'})
        self.assertEquals(response.status_code, 201)
        location = response['Location']
        repouri = location[location.index('/api/v1'):]
        response = c.post('/api/v1/series/', {'name': 'series1',
                                              'repository': repouri,
                                              'base_ubuntu_series': 'precise',
                                              'state': 1,
                                              'subscriptions': []})
        self.assertEquals(response.status_code, 201)

    def test_user_cannot_create_series_on_someone_elses_repository(self):
        c = self._get_client('user1')
        response = c.post('/api/v1/repository/', {'name': 'testuserrepo'})
        self.assertEquals(response.status_code, 201)
        location = response['Location']
        repouri = location[location.index('/api/v1'):]
        c = self._get_client('user2')
        response = c.post('/api/v1/series/', {'name': 'series1',
                                              'repository': repouri,
                                              'base_ubuntu_series': 'precise',
                                              'state': 1,
                                              'subscriptions': []})
        self.assertEquals(response.status_code, 401)

