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
import os
import os.path
import random
import paramiko
import select
import StringIO
import socket
import sys
import termios
import time
import tty

from django.conf import settings
from django.contrib import auth
from django.core.urlresolvers import reverse
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

if settings.TESTING:
    import mock
    client = mock.Mock()
else:
    from novaclient.v1_1 import client


from repomgmt import utils


class Repository(models.Model):
    name = models.CharField(max_length=200, primary_key=True)
    signing_key_id = models.CharField(max_length=200)
    uploaders = models.ManyToManyField(auth.models.User)
    contact = models.EmailField()

    class Meta:
        verbose_name_plural = "repositories"

    def __unicode__(self):
        return self.name

    def _reprepro(self, *args):
        arg_list = list(args)
        cmd = ['reprepro', '-b', self.reprepro_dir] + arg_list
        return utils.run_cmd(cmd)

    @property
    def signing_key(self):
        return GPGKey(self.signing_key_id)

    @property
    def reprepro_dir(self):
        return '%s/%s' % (settings.BASE_REPO_DIR, self.name)

    @property
    def reprepro_outdir(self):
        return '%s/repo' % (self.reprepro_dir,)

    def process_incoming(self):
        self._reprepro('processincoming', 'incoming')

    def not_closed_series(self):
        return self.series_set.exclude(state=Series.CLOSED)

    def write_configuration(self):
        confdir = '%s/conf' % (self.reprepro_dir,)

        basedir = os.path.normpath(os.path.join(os.path.dirname(__file__),
                                                os.pardir))

        if not os.path.exists(confdir):
            os.makedirs(confdir)

        for f in ['distributions', 'incoming', 'options', 'pulls',
                  'uploaders', 'create-build-records.sh']:
            s = render_to_string('reprepro/%s.tmpl' % (f,),
                                 {'repository': self,
                                  'architectures': Architecture.objects.all(),
                                  'settings': settings,
                                  'basedir': basedir})
            path = '%s/%s' % (confdir, f)

            with open(path, 'w') as fp:
                fp.write(s)

            if path.endswith('.sh'):
                os.chmod(path, 0755)


class UploaderKey(models.Model):
    key_id = models.CharField(max_length=200, primary_key=True)
    uploader = models.ForeignKey(auth.models.User)

    def __unicode__(self):
        return '%s (%s)' % (self.key_id, self.uploader)


class GPGKey(object):
    def __init__(self, key_id):
        self.key_id = key_id

    def _gpg_export(self, private=False):
        if private:
            arg = '--export-secret-key'
        else:
            arg = '--export'

        out = utils.run_cmd(['gpg', '-a', '--export-options',
                             'export-clean', arg, self.key_id]),

        if 'nothing exported' in out:
            raise Exception('Key with ID %s not found' % self.key_id)

        return out

    @property
    def private_key(self):
        return self._gpg_export(True)

    @property
    def public_key(self):
        return self._gpg_export(False)


class Series(models.Model):
    ACTIVE = 1
    MAINTAINED = 2
    FROZEN = 3
    CLOSED = 4
    SERIES_STATES = (
        (ACTIVE, 'Active development'),
        (MAINTAINED, 'Maintenance mode'),
        (FROZEN, 'Frozen for testing'),
        (CLOSED, 'No longer maintained')
    )

    name = models.CharField(max_length=200)
    repository = models.ForeignKey(Repository)
    base_ubuntu_series = models.CharField(max_length=200)
    numerical_version = models.CharField(max_length=200)
    state = models.SmallIntegerField(default=ACTIVE,
                                     choices=SERIES_STATES)

    class Meta:
        verbose_name_plural = "series"
        unique_together = ('name', 'repository')

    def __unicode__(self):
        return '%s-%s' % (self.repository, self.name)

    def get_absolute_url(self):
        kwargs = {'series_name': self.name,
                  'repository_name': self.repository.name}
        return reverse('packages_list', kwargs=kwargs)

    def accept_uploads_into(self):
        # If frozen, stuff uploads into -queued. If active (or
        # maintained) put them in -proposed.
        if self.state in (Series.ACTIVE, Series.MAINTAINED):
            return '%s-proposed' % (self.name,)
        elif self.state == Series.FROZEN:
            return '%s-queued' % (self.name,)

    def save(self, *args, **kwargs):
        self.repository.write_configuration()
        if self.pk:
            old = Series.objects.get(pk=self.pk)
            if old.state != self.state:
                if (old.state == Series.FROZEN and
                         self.state == Series.ACTIVE):
                    print 'flushing'
                    self.flush_queue()
        return super(Series, self).save(*args, **kwargs)

    def freeze(self):
        self.state = Series.FROZEN
        self.save()

    def unfreeze(self):
        self.state = Series.ACTIVE
        self.save()

    def flush_queue(self):
        self.repository._reprepro('pull', '%s-proposed' % (self.name, ))

    def get_source_packages(self):
        pkgs = {}

        def get_pkglist(distribution):
            pkglist = self.repository._reprepro('-A', 'source', 'list', distribution)
            for l in pkglist.split('\n'):
                if l.strip() == '':
                    continue
                repo_info = pkglist.split(':')[0]
                _distribution, _section, arch = repo_info.split('|')
                pkg_name, pkg_version = l.split(' ')[1:]
                yield (pkg_name, pkg_version)

        for distribution_fmt, key in [('%s', 'stable'),
                                      ('%s-proposed', 'proposed'),
                                      ('%s-queued', 'queued')]:
            distribution = distribution_fmt % (self.name,)
            pkgs[key] = {}
            for pkg_name, pkg_version in get_pkglist(distribution):
                pkgs[key][pkg_name] = pkg_version

        return pkgs

    def promote(self):
        self.repository._reprepro('pull', self.name)


class Package(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version

    def __unicode__(self):
        return '%s-%s' % (self.name,
                          self.version)

    def __repr__(self):
        return '<Package name=%r version=%r>' % (self.name,
                                                 self.version)


class Architecture(models.Model):
    name = models.CharField(max_length=200, primary_key=True)
    builds_arch_all = models.BooleanField(default=False)

    def __unicode__(self):
        return self.name


class ChrootTarball(models.Model):
    NOT_AVAILABLE = 1
    WAITING_TO_BUILD = 2
    CURRENTLY_BUILDING = 3
    READY = 4

    BUILD_STATES = (
        (NOT_AVAILABLE, 'Not available'),
        (WAITING_TO_BUILD, 'Build scheduled'),
        (CURRENTLY_BUILDING, 'Currently building'),
        (READY, 'Ready'))

    architecture = models.ForeignKey(Architecture)
    series = models.ForeignKey(Series)
    last_refresh = models.DateTimeField(null=True, blank=True)
    state = models.SmallIntegerField(default=1, choices=BUILD_STATES)

    class Meta:
        unique_together = ('architecture', 'series')

    def __unicode__(self):
        return '%s-%s' % (self.series, self.architecture)

    def download_link(self):
        return '%s%s-%s-%s.tgz' % (settings.BASE_TARBALL_URL,
                               self.series.name,
                               self.series.repository.name,
                               self.architecture.name)

    def refresh(self, proxy=False, mirror=False):
        if self.state == self.CURRENTLY_BUILDING:
            return
        self.state = self.CURRENTLY_BUILDING
        self.save()

        for k in os.environ.keys():
            if k.startswith('LC_'):
                del os.environ[k]
            elif k.startswith('LANG'):
                del os.environ[k]

        saved_cwd = os.getcwd()
        os.chdir('/')
        stdout = utils.run_cmd(['schroot', '-l'])
        expected = 'source:%s-%s-%s' % (self.series.name,
                                        self.series.repository.name,
                                        self.architecture.name)

        if expected not in stdout.split('\n'):
            def _run_in_chroot(cmd, input=None):
                series_name = self.series.name
                repo_name = self.series.repository.name
                arch_name = self.architecture.name
                return utils.run_cmd(['schroot',
                                      '-c', '%s-%s-%s-source' % (series_name,
                                                                 repo_name,
                                                                 arch_name),
                                      '-u', 'root', '--'] + cmd, input)

            mk_sbuild_extra_args = []
            if proxy:
                mk_sbuild_extra_args += ["--debootstrap-proxy=%s" % (proxy,)]

            if mirror:
                mk_sbuild_extra_args += ["--debootstrap-mirror=%s" % (mirror,)]

            cmd = ['mk-sbuild']
            cmd += ['--name=%s-%s' % (self.series.name,
                                      self.series.repository.name)]
            cmd += ['--arch=%s' % (self.architecture.name)]
            cmd += ['--type=file']
            cmd += mk_sbuild_extra_args
            cmd += [self.series.base_ubuntu_series]

            utils.run_cmd(cmd)
            utils.run_cmd(['sudo', 'sed', '-i', '-e', 's/^#source/source/g',
                           ('/etc/schroot/chroot.d/sbuild-%s-%s-%s' %
                                                  (self.series.name,
                                                   self.series.repository.name,
                                                   self.architecture.name))])

            format_args = tuple([settings.APT_REPO_BASE_URL,
                                 self.series.repository.name,
                                 self.series.name] * 4)
            srcs = ('deb %s%s %s main\n'
                    'deb-src %s%s %s main\n'
                    'deb %s%s %s-proposed main\n'
                    'deb-src %s%s %s-proposed main\n' % format_args)
            _run_in_chroot(['tee', '--append', '/etc/apt/sources.list'], srcs)

            public_key = self.series.repository.signing_key.public_key
            _run_in_chroot(['apt-key', 'add', '-'], public_key)
            if hasattr(settings, 'POST_MK_SBUILD_CUSTOMISATION'):
                _run_in_chroot(settings.POST_MK_SBUILD_CUSTOMISATION)

        utils.run_cmd(['sbuild-update',
                       '-udcar',
                       '%s-%s' % (self.series.name, self.series.repository.name),
                       '--arch=%s' % (self.architecture.name,)])
        os.chdir(saved_cwd)
        self.last_refresh = timezone.now()
        self.state = self.READY
        self.save()


class BuildRecord(models.Model):
    BUILDING = 1
    SUCCESFULLY_BUILT = 2
    CHROOT_PROBLEM = 3
    BUILD_FOR_SUPERSEDED_SOURCE = 4
    FAILED_TO_BUILD = 5
    DEPENDENCY_WAIT = 6
    FAILED_TO_UPLOAD = 7
    NEEDS_BUILDING = 8

    BUILD_STATES = (
        (BUILDING, 'Building'),
        (SUCCESFULLY_BUILT, 'Succesfully Built'),
        (CHROOT_PROBLEM, 'Chroot Problem'),
        (BUILD_FOR_SUPERSEDED_SOURCE, 'Build for superseded source'),
        (FAILED_TO_BUILD, 'Failed to build'),
        (DEPENDENCY_WAIT, 'Dependency wait'),
        (FAILED_TO_UPLOAD, 'Failed to upload'),
        (NEEDS_BUILDING, 'Needs building'),
    )

    source_package_name = models.CharField(max_length=200)
    version = models.CharField(max_length=200)
    architecture = models.ForeignKey(Architecture)
    state = models.SmallIntegerField(default=NEEDS_BUILDING,
                                     choices=BUILD_STATES)
    priority = models.IntegerField(default=100)
    series = models.ForeignKey(Series)
    build_node = models.ForeignKey('BuildNode', null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def get_tarball(self):
        return self.series.chroottarball_set.get(architecture=self.architecture)

    class Meta:
        unique_together = ('series', 'source_package_name',
                           'version', 'architecture')

    def __unicode__(self):
        return ('Build of %s_%s_%s' %
                (self.source_package_name, self.version, self.architecture))

    @classmethod
    def pending_build_count(cls):
        return cls.objects.filter(state=cls.NEEDS_BUILDING).count()

    @classmethod
    def pick_build(cls, build_node):
        while True:
            builds = cls.objects.filter(state=cls.NEEDS_BUILDING)
            try:
                next_build = builds.order_by('-priority')[0]
            except IndexError:
                return None
            matches = cls.objects.filter(id=next_build.id, build_node__isnull=True).update(build_node=build_node)
            if matches != 1:
                continue
            else:
                return cls.objects.get(id=next_build.id)


class Cloud(models.Model):
    name = models.CharField(max_length=200, primary_key=True)
    endpoint = models.URLField(max_length=200)
    user_name = models.CharField(max_length=200)
    tenant_name = models.CharField(max_length=200)
    password = models.CharField(max_length=200)

    def __unicode__(self):
        return self.name

    @property
    def client(self):
        if not hasattr(self, '_client'):
            self._client = client.Client(self.user_name,
                                         self.password,
                                         self.tenant_name,
                                         self.endpoint,
                                         service_type="compute",
                                         no_cache=True)

        return self._client


class KeyPair(models.Model):
    cloud = models.ForeignKey(Cloud)
    name = models.CharField(max_length=200)
    private_key = models.TextField()
    public_key = models.TextField()

    def __unicode__(self):
        return '%s@%s' % (self.name, self.cloud)

    class Meta:
        verbose_name_plural = "series"
        unique_together = ('cloud', 'name')


class BuildNode(models.Model):
    NEW = 0
    BOOTING = 1
    PREPARING = 2
    READY = 3
    BUILDING = 4
    SHUTTING_DOWN = 5

    NODE_STATES = (
        (NEW, 'Newly created'),
        (BOOTING, 'Booting (not yet available)'),
        (PREPARING, 'Preparing (Installing build infrastructure)'),
        (READY, 'Ready to build'),
        (BUILDING, 'Building'),
        (SHUTTING_DOWN, 'Shutting down'),
    )

    name = models.CharField(max_length=200, primary_key=True)
    cloud = models.ForeignKey(Cloud)
    cloud_node_id = models.CharField(max_length=200)
    state = models.SmallIntegerField(default=NEW,
                                     choices=NODE_STATES)

    def __unicode__(self):
        return self.name

    def prepare(self, build_record):
        self.state = self.BOOTING
        self.save()
        try:
            def _run_cmd(cmd, *args, **kwargs):
                for data in self.run_cmd(cmd, *args, **kwargs):
                    pass
            while True:
                try:
                    _run_cmd('id')
                    break
                except Exception, e:
                    print e
                time.sleep(5)
            self.state = self.PREPARING
            self.save()
            _run_cmd('sudo apt-get update')
            _run_cmd('sudo DEBIAN_FRONTEND=noninteractive '
                     'apt-get -y --force-yes install puppet')
            _run_cmd('sudo wget -O puppet.pp %s/puppet/%s/' %
                                          (settings.BASE_URL, build_record.id))
            _run_cmd('sudo -H puppet apply --verbose puppet.pp')
            self.state = self.READY
            self.save()
        except Exception, e:
            self.delete()

    def build(self, build_record):
        self.state = self.BUILDING
        self.save()
        try:
            series = build_record.series
            utils.run_cmd('mkdir build')
            sbuild_cmd = ('cd build; sbuild -d %s ' % (series.name,) +
                          '--arch=%s ' % build_record.architecture.name +
                          '-c buildchroot ' +
                          '-n -k%s ' % series.repository.signing_key_id)

            if build_record.architecture.name == 'i386':
                sbuild_cmd += '-A '

            sbuild_cmd += ('%s_%s' % (build_record.source_package_name,
                                      build_record.version))
            utils.run_cmd(sbuild_cmd)
        except Exception:
            pass
        self.delete()

        self.state = self.SHUTTING_DOWN
        self.save()

    @classmethod
    def get_unique_keypair_name(cls, cl):
        existing_keypair_names = [kp.name for kp in cl.keypairs.list()]
        while True:
            name = 'buildd-%d' % random.randint(1, 1000)
            if name not in existing_keypair_names:
                return name

    @classmethod
    def get_unique_buildnode_name(cls):
        existing_server_names = [srv.name for srv in cl.servers.list()]
        old_build_node_names = [bn.name for bn in BuildNode.objects.all()]
        names_to_avoid = set(existing_server_names + old_build_node_names)
        while True:
            name = 'buildd-%d' % random.randint(1, 1000)
            if name not in names_to_avoid:
                return name

    @classmethod
    def start_new(cls):
        cloud = random.choice(Cloud.objects.all())
        cl = cloud.client
        if len(cloud.keypair_set.all()) < 1:
            name = cls.get_unique_keypair_name(cl)
            kp = cl.keypairs.create(name=name)
            keypair = KeyPair(cloud=cloud, name=name,
                              private_key=kp.private_key,
                              public_key=kp.public_key)
            keypair.save()
        else:
            keypair = cloud.keypair_set.all()[0]

        name = cls.get_unique_buildnode_name(cl)
        flavor = utils.get_flavor_by_name(cl, 'm1.medium')
        image = utils.get_image_by_regex(cl, 'Ubuntu Precise')

        srv = cl.servers.create(name, image, flavor, key_name=keypair.name)
        bn = BuildNode(name=name, cloud=cloud, cloud_node_id=srv.id)
        bn.save()
        return bn

    @property
    def cloud_server(self):
        cloud = self.cloud
        client = cloud.client
        return client.servers.get(self.cloud_node_id)

    @property
    def ip(self):
        return self.cloud_server.networks.values()[0][0]

    def delete(self):
        self.cloud_server.delete()
        super(BuildNode, self).delete()

    @property
    def keypair(self):
        return self.cloud.keypair_set.all()[0]

    @property
    def paramiko_private_key(self):
        private_key = self.keypair.private_key
        priv_key_file = StringIO.StringIO(private_key)
        return paramiko.RSAKey.from_private_key(priv_key_file)

    def ssh_client(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, username='ubuntu', pkey=self.paramiko_private_key)
        return ssh

    def run_cmd(self, cmd, input=None):
        print 'Running: %s' % (cmd,)

        ssh = self.ssh_client()
        transport = ssh.get_transport()

        chan = transport.open_session()
        chan.exec_command(cmd)
        chan.set_combine_stderr(True)
        if input:
            chan.sendall(input)
            chan.shutdown_write()

        while True:
            r, _, __ = select.select([chan], [], [], 1)
            if r:
                if chan in r:
                    if chan.recv_ready():
                        s = chan.recv(4096)
                        if len(s) == 0:
                            break
                        yield s
                    else:
                        status = chan.recv_exit_status()
                        if status != 0:
                            raise Exception('Command %s failed' % cmd)
                        break

        ssh.close()

    def _posix_shell(self, chan):
        oldtty = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
            chan.settimeout(0.0)

            while True:
                r, w, e = select.select([chan, sys.stdin], [], [])
                if chan in r:
                    try:
                        x = chan.recv(1024)
                        if len(x) == 0:
                            print '\r\n*** EOF\r\n',
                            break
                        sys.stdout.write(x)
                        sys.stdout.flush()
                    except socket.timeout:
                        pass
                if sys.stdin in r:
                    x = sys.stdin.read(1)
                    if len(x) == 0:
                        break
                    chan.send(x)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)

    def interactive_ssh(self):
        ssh = self.ssh_client()
        shell = ssh.invoke_shell(os.environ.get('TERM', 'vt100'))
        self._posix_shell(shell)

