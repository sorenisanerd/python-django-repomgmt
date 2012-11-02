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
import mock
import textwrap

from django.test import TestCase, client
from django.test.utils import override_settings
from repomgmt.models import Cloud, BuildNode, BuildRecord, KeyPair, Repository, Series

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

        response = c.post('/repositories/', {'action': 'create',
                                             'name': 'foo',
                                             'contact': 'foo@example.com'})
        self.assertRedirects(response, '/repositories/')

        new_repos = set(Repository.objects.all()) - repo_set
        self.assertEquals(len(new_repos), 1)
        new_repo = new_repos.pop()

        self.assertEquals(new_repo.name, 'foo')
        self.assertEquals(new_repo.contact, 'foo@example.com')
