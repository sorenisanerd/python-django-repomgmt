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
from glob import glob
from datetime import date
import logging
import os
import os.path
import random
import paramiko
import select
import shutil
import StringIO
import socket
import sys
import tempfile
import termios
import textwrap
import time
import tty

from django.conf import settings
from django.contrib.auth.models import User
#from django.core.mail import email_admins
from django.core.urlresolvers import reverse
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

if settings.TESTING:
    import mock
    client = mock.Mock()
else:
    from novaclient.v1_1 import client

from novaclient import exceptions as novaclient_exceptions

from repomgmt import utils
from repomgmt.exceptions import CommandFailed

logger = logging.getLogger(__name__)


class Repository(models.Model):
    name = models.CharField(max_length=200, primary_key=True)
    signing_key_id = models.CharField(max_length=200)
    uploaders = models.ManyToManyField(User)
    contact = models.EmailField()

    class Meta:
        verbose_name_plural = "repositories"

    @classmethod
    def allow_unprivileged_creation(cls):
        return True

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
        return '%s/%s' % (settings.BASE_PUBLIC_REPO_DIR, self.name)

    @property
    def reprepro_incomingdir(self):
        return '%s/%s' % (settings.BASE_INCOMING_DIR, self.name)

    def process_incoming(self):
        self._reprepro('processincoming', 'incoming')

    def not_closed_series(self):
        return self.series_set.exclude(state=Series.CLOSED)

    def build_nodes(self):
        return BuildNode.objects.filter(buildrecord__series__repository=self)

    def create_key(self):
        if self.signing_key_id:
            return

        output = utils.run_cmd(['gpg', '--batch', '--gen-key'],
                                input=textwrap.dedent('''\
                                               Key-Type: 1
                                               Key-Length: 4096
                                               Subkey-Type: ELG-E
                                               Subkey-Length: 4096
                                               Name-Real: %s repository
                                               Expire-Date: 0
                                               %%commit''' % self.name))

        for l in output.split('\n'):
            if l.startswith('gpg: key '):
                key_id = l.split(' ')[2]

        self.signing_key_id = key_id
        self.signing_key.public_key

    def write_configuration(self):
        logger.debug('Writing out config for %s' % (self.name,))

        confdir = '%s/conf' % (self.reprepro_dir,)

        settings_module_name = os.environ['DJANGO_SETTINGS_MODULE']
        settings_module = __import__(settings_module_name)
        settings_module_dir = os.path.dirname(settings_module.__file__)
        basedir = os.path.normpath(os.path.join(settings_module_dir,
                                                os.pardir))

        for d, setgid in [(settings.BASE_PUBLIC_REPO_DIR, False),
                          (confdir, False), (self.reprepro_incomingdir, True)]:
            if not os.path.exists(d):
                os.makedirs(d)
                if setgid:
                    os.chmod(d, 02775)

        for f in ['distributions', 'incoming', 'options', 'pulls',
                  'uploaders', 'create-build-records.sh', 'dput.cf',
                  'process-changes.sh', 'import-dsc-to-git.sh', 'updates']:
            s = render_to_string('reprepro/%s.tmpl' % (f,),
                                 {'repository': self,
                                  'architectures': Architecture.objects.all(),
                                  'settings': settings,
                                  'basedir': basedir,
                                  'outdir': self.reprepro_outdir})
            path = '%s/%s' % (confdir, f)

            with open(path, 'w') as fp:
                fp.write(s)

            if path.endswith('.sh'):
                os.chmod(path, 0755)

        if self.series_set.count() > 0:
            self._reprepro('export')

    def save(self, *args, **kwargs):
        self.write_configuration()
        self.create_key()
        return super(Repository, self).save(*args, **kwargs)

    def can_modify(self, user):
        # A side effect of using the name as the primary key is that
        # this check isn't super useful
        if self.pk is None:
            return True

        # ..instead we need to resort to this :(
        if self.__class__.objects.filter(pk=self.pk).count() == 0:
            return True

        if user.is_superuser:
            return True
        if user in self.uploaders.filter(id=user.id):
            return True
        return False

class UploaderKey(models.Model):
    key_id = models.CharField(max_length=200, primary_key=True)
    uploader = models.ForeignKey(User)

    def save(self):
        utils.run_cmd(['gpg', '--recv-keys', self.key_id])
        super(UploaderKey, self).save()

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
                             'export-clean', arg, self.key_id])

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
    base_ubuntu_series = models.ForeignKey('UbuntuSeries')
    numerical_version = models.CharField(max_length=200)
    state = models.SmallIntegerField(default=ACTIVE,
                                     choices=SERIES_STATES)
    update_from = models.ForeignKey('Series', null=True, blank=True)

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
            newly_created = False
            old = Series.objects.get(pk=self.pk)
            if old.state != self.state:
                if (old.state == Series.FROZEN and
                         self.state == Series.ACTIVE):
                    self.flush_queue()
        else:
            newly_created = True

        super(Series, self).save(*args, **kwargs)

        if newly_created:
            if self.update_from:
                for subscription in self.update_from.subscription_set.all():
                    # This creates a new subscription
                    subscription.pk = None
                    subscription.target_series = self
                    subscription.save()

            self.update()

    def can_modify(self, user):
        if self.repository_id is None:
            return True
        return self.repository.can_modify(user)

    def freeze(self):
        self.state = Series.FROZEN
        self.save()

    def unfreeze(self):
        self.state = Series.ACTIVE
        self.save()

    def flush_queue(self):
        logger.info('Flushing queue for %s' % (self,))
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

    def update(self):
        self.repository.write_configuration()
        if self.update_from:
            self.repository._reprepro('update', '%s-proposed' % (self.name,))

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


class UbuntuSeries(models.Model):
    name = models.CharField(max_length=200, primary_key=True)

    def __unicode__(self):
        return 'Ubuntu %s' % (self.name.capitalize())


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
    series = models.ForeignKey(UbuntuSeries)
    last_refresh = models.DateTimeField(null=True, blank=True)
    state = models.SmallIntegerField(default=1, choices=BUILD_STATES)

    class Meta:
        unique_together = ('architecture', 'series')

    def __unicode__(self):
        return '%s-%s' % (self.series, self.architecture)

    def download_link(self):
        return '%s%s-%s.tgz' % (settings.BASE_TARBALL_URL,
                               self.series.name,
                               self.architecture.name)

    def refresh(self, proxy=False, mirror=False):
        if self.state == self.CURRENTLY_BUILDING:
            logger.info('Already building %s. '
                        'Ignoring request to refresh.' % (self,))
            return
        logger.info('Refreshing %s tarball.' % (self,))

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
        expected = 'source:%s-%s' % (self.series.name,
                                        self.architecture.name)

        if expected not in stdout.split('\n'):
            logger.info('Existing schroot for %s not found. '
                        'Starting from scratch.' % (self,))

            def _run_in_chroot(cmd, input=None):
                series_name = self.series.name
                arch_name = self.architecture.name
                return utils.run_cmd(['schroot',
                                      '-c', '%s-%s-source' % (series_name,
                                                              arch_name),
                                      '-u', 'root', '--'] + cmd, input)

            mk_sbuild_extra_args = []
            if proxy:
                mk_sbuild_extra_args += ["--debootstrap-proxy=%s" % (proxy,)]

            if mirror:
                mk_sbuild_extra_args += ["--debootstrap-mirror=%s" % (mirror,)]

            cmd = ['mk-sbuild']
            cmd += ['--name=%s' % (self.series.name,)]
            cmd += ['--arch=%s' % (self.architecture.name)]
            cmd += ['--eatmydata']
            cmd += ['--type=file']
            cmd += mk_sbuild_extra_args
            cmd += [self.series.name]

            utils.run_cmd(cmd)
            utils.run_cmd(['sudo', 'sed', '-i', '-e', 's/^#source/source/g',
                           ('/etc/schroot/chroot.d/sbuild-%s-%s' %
                                                  (self.series.name,
                                                   self.architecture.name))])

            if hasattr(settings, 'POST_MK_SBUILD_CUSTOMISATION'):
                _run_in_chroot(settings.POST_MK_SBUILD_CUSTOMISATION)

        logger.info("sbuild-update'ing %s tarball." % (self,))
        utils.run_cmd(['sbuild-update',
                       '-udcar',
                       '%s' % (self.series.name,),
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
    finished = models.DateTimeField(db_index=True, null=True, blank=True)

    def get_tarball(self):
        return self.series.base_ubuntu_series.chroottarball_set.get(architecture=self.architecture)

    class Meta:
        unique_together = ('series', 'source_package_name',
                           'version', 'architecture')

    def __unicode__(self):
        return ('Build of %s_%s_%s' %
                (self.source_package_name, self.version, self.architecture))

    def update_state(self, new_state):
        self.__class__.objects.filter(pk=self.pk).update(state=new_state)
        # Also update this cached object
        self.state = new_state

    @classmethod
    def pending_builds(cls):
        return cls.objects.filter(state=cls.NEEDS_BUILDING,
                                        build_node__isnull=True)

    @classmethod
    def pending_build_count(cls):
        return cls.pending_builds().count()

    def superseded(self):
        pkginfo = self.series.get_source_packages()
        for pocket in pkginfo:
            if pocket.endswith('-queued'):
                continue
            if self.source_package_name in pkginfo[pocket]:
                version = pkginfo[pocket][self.source_package_name]
                if self.version == version:
                    return False
        return True

    @classmethod
    def perform_single_build(cls):
        if cls.pending_build_count() > 0:
            bn = BuildNode.start_new()
            br = BuildRecord.pick_build(bn)
            bn.prepare(br)
            bn.build(br)

    def allow_rebuild(self):
        return (self.state in [BuildRecord.DEPENDENCY_WAIT,
                               BuildRecord.FAILED_TO_BUILD]
                and not self.superseded())

    def build_log_url(self):
        return '%s/%s' % (settings.BASE_BUILD_LOG_URL, '%s.log.txt' % self.pk)

    def logfile(self):
        return os.path.join(settings.BUILD_LOG_DIR, '%s.log.txt' % self.pk)

    def log_tail(self, max_lines=20):
        last_lines = []
        try:
            with open(self.logfile(), 'r') as fp:
                for l in fp:
                    last_lines.append(l)

                last_lines = last_lines[-max_lines:]

            return ''.join(last_lines)
        except:
            return ''

    def parse_summary(self):
        lines = self.log_tail(40).split('\n')
        if not lines:
            return {'Status': 'Unknown'}

        for i in range(len(lines) - 1, 0, -1):
            if 'Summary' in lines[i]:
                break

        # The ith line is the summary heading.
        # i+1 is the bottem of the heading box.
        # i+2 is a blank line
        summary = {}
        for j in range(i + 3, len(lines)):
            if not ':' in lines[j]:
                break

            k, v = lines[j].split(':', 1)
            summary[k] = v.strip()
        return summary

    def update_state_from_build_log(self):
        logger.debug('Setting build state if %r from build log' % (self,))

        summary = self.parse_summary()
        if summary['Status'] == 'successful':
            logger.debug('Build summary says build %r completed succesfully. '
                         'Setting state accordingly.' % (self,))
            # Everything worked beautifully
            self.update_state(self.SUCCESFULLY_BUILT)
            return
        elif summary['Status'] == 'attempted':
            # The infrastructure performed as expected. The build failed.
            # There's nothing more for us to do
            logger.debug('Build summary says build %r failed. '
                         'Setting state accordingly.' % (self,))
            self.update_state(self.FAILED_TO_BUILD)
            return
        elif summary['Status'] == 'failed':
            # Some dependencies could not be fulfilled.
            if summary['Fail-Stage'] == 'install-deps':
                logger.debug('Build summary says installing deps failed for '
                             'build %r. Setting state accordingly.' % (self,))
                self.update_state(self.DEPENDENCY_WAIT)
                return
            # We failed to fetch the source pkg. Put it back in the queue
            if summary['Fail-Stage'] == 'fetch-src':
                logger.debug('Build summary says fetching source for build %r '
                             'failed. Setting state to NEEDS_BUILDING to '
                             'retry.' % (self,))
                if self.superseded():
                    self.update_state(self.BUILD_FOR_SUPERSEDED_SOURCE)
                else:
                    self.update_state(self.NEEDS_BUILDING)
                return

        logger.debug("Setting a default of NEEDS_BUILDING for build summary:"
                     "%r" % (summary,))
        self.update_state(self.NEEDS_BUILDING)

    @classmethod
    def pick_build(cls, build_node):
        """Picks the highest priority build"""
        while True:
            builds = cls.pending_builds()
            try:
                next_build = builds.order_by('-priority')[0]
            except IndexError:
                return None
            # This ensures that assigning a build node is atomic,x
            # since the filter only matches if noone else has done
            # a similar update.
            matches = cls.objects.filter(id=next_build.id,
                                         build_node__isnull=True
                                        ).update(build_node=build_node)
            # If we didn't find a single match, someone else must have
            # grabbed the build and we start over
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
    region = models.CharField(max_length=200, blank=True)
    flavor_name = models.CharField(max_length=200)
    image_name = models.CharField(max_length=200)

    def __unicode__(self):
        return self.name

    @property
    def client(self):
        if not hasattr(self, '_client'):
            kwargs = {}
            if self.region:
                kwargs['region_name'] = self.region

            self._client = client.Client(self.user_name,
                                         self.password,
                                         self.tenant_name,
                                         self.endpoint,
                                         service_type="compute",
                                         no_cache=True,
                                         **kwargs)
            self._client.cloud = self

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
    signing_key_id = models.CharField(max_length=200)

    def __unicode__(self):
        return self.name

    def _run_cmd(self, cmd, *args, **kwargs):
        def log(s):
            logger.info('%-15s: %s' % (self.name, s))

        def log_whole_lines(lbuf):
            while '\n' in lbuf:
                line, lbuf = lbuf.split('\n', 1)
                log(line)
            return lbuf

        output_callback = kwargs.pop('output_callback', lambda _: None)

        out = ''
        lbuf = ''
        for data in self.run_cmd(cmd, *args, **kwargs):
            output_callback(data)
            out += data
            lbuf += data
            lbuf = log_whole_lines(lbuf)

        lbuf = log_whole_lines(lbuf)
        log(lbuf)
        return out

    def update_state(self, new_state):
        self.__class__.objects.filter(pk=self.pk).update(state=new_state)
        # Also update this cached object
        self.state = new_state

    def prepare(self, build_record):
        self.state = self.BOOTING
        self.save()
        try:
            while True:
                try:
                    self._run_cmd('id')
                    break
                except Exception, e:
                    print e
                time.sleep(5)
            self.state = self.PREPARING
            self.save()
            self._run_cmd('sudo apt-get update')
            self._run_cmd('sudo DEBIAN_FRONTEND=noninteractive '
                          'apt-get -y --force-yes install puppet')
            self._run_cmd('sudo wget -O puppet.pp %s/puppet/%s/' %
                                          (settings.BASE_URL, build_record.id))
            self._run_cmd('sudo -H puppet apply --verbose puppet.pp')
            self._run_cmd(textwrap.dedent('''\n
                          cat <<EOF > keygen.param
                          Key-Type: 1
                          Key-Length: 2048
                          Subkey-Type: ELG-E
                          Subkey-Length: 2048
                          Name-Real: %s signing key
                          Expire-Date: 0
                          %%commit
                          EOF''' % (self,)))
            out = self._run_cmd('''gpg --gen-key --batch keygen.param''')
            for l in out.split('\n'):
                if l.startswith('gpg: key '):
                    key_id = l.split(' ')[2]
            self.signing_key_id = key_id

            public_key_data = self._run_cmd('gpg -a --export %s' %
                                            (self.signing_key_id))
            utils.run_cmd(['gpg', '--import'], input=public_key_data)

            self.state = self.READY
            self.save()
            build_record.series.repository.write_configuration()
        except Exception, e:
            logger.info('Preparing build node %s failed' % (self.name),
                         exc_info=True)
            self.delete()

    def build(self, build_record):
        self.update_state(BuildNode.BUILDING)
        build_record.update_state(BuildRecord.BUILDING)
        try:
            series = build_record.series
            self._run_cmd('mkdir build')
            sbuild_cmd = ('cd build; sbuild -d %s ' % (series.name,) +
                          '--arch=%s ' % build_record.architecture.name +
                          '-c buildchroot ' +
                          '-n -k%s ' % self.signing_key_id)

            if build_record.architecture.builds_arch_all:
                sbuild_cmd += '-A '

            sbuild_cmd += ('%s_%s' % (build_record.source_package_name,
                                      build_record.version))

            if not os.path.exists(settings.BUILD_LOG_DIR):
                os.makedirs(settings.BUILD_LOG_DIR)

            with open(build_record.logfile(), 'a') as fp:
                def write_and_flush(s):
                    fp.write(s)
                    fp.flush()

                self._run_cmd(sbuild_cmd, output_callback=write_and_flush)

            self._run_cmd('cd build; dput return *.changes')
        except Exception:
            pass

        build_record.update_state_from_build_log()
        build_record.finished = timezone.now()
        build_record.save()

        if build_record.state != build_record.SUCCESFULLY_BUILT:
            # If the build succeeded, defer deleting the build node record
            # until the upload has been processed.
            self.delete()

    @classmethod
    def get_unique_keypair_name(cls, cl):
        existing_keypair_names = [kp.name for kp in cl.keypairs.list()]
        while True:
            name = 'buildd-%d' % random.randint(1, 1000)
            if name not in existing_keypair_names:
                return name

    @classmethod
    def get_unique_buildnode_name(cls, cl):
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
        logger.info('Picked cloud %s' % (cloud,))
        cl = cloud.client
        if cloud.keypair_set.count() < 1:
            logger.info('Cloud %s does not have a keypair yet. '
                        'Creating' % (cloud,))
            name = cls.get_unique_keypair_name(cl)
            kp = cl.keypairs.create(name=name)
            keypair = KeyPair(cloud=cloud, name=name,
                              private_key=kp.private_key,
                              public_key=kp.public_key)
            keypair.save()
            logger.info('KeyPair %s created' % (keypair,))
        else:
            keypair = cloud.keypair_set.all()[0]
        logger.debug('Using cached keypair: %s' % (keypair,))

        name = cls.get_unique_buildnode_name(cl)
        flavor = utils.get_flavor_by_name(cl, cl.cloud.flavor_name)
        image = utils.get_image_by_regex(cl, cl.cloud.image_name)

        logger.info('Creating server %s on cloud %s' % (name, cloud))
        srv = cl.servers.create(name, image, flavor, key_name=keypair.name)

        timeout = time.time() + 120
        succeeded = False
        while timeout > time.time():
            if srv.status == 'BUILD':
                time.sleep(3)
                srv = cl.servers.get(srv.id)
            else:
                succeeded = True
                break

        if not succeeded:
            srv.delete()
            raise Exception('Failed to launch instance')

        if getattr(settings, 'USE_FLOATING_IPS', False):
            logger.info('Grabbing floating ip for server %s on cloud %s' %
                        (name, cloud))
            floating_ip = cl.floating_ips.create()
            logger.info('Got floating ip %s for server %s on cloud %s' %
                        (floating_ip.ip, name, cloud))

            logger.debug('Assigning floating ip %s to server %s on cloud %s.'
                         'Timing out in 20 seconds.' % (floating_ip.ip,
                                                        name, cloud))

            timeout = time.time() + 20
            succeeded = False
            while timeout > time.time():
                try:
                    srv.add_floating_ip(floating_ip.ip)
                    succeeded = True
                    break
                except:
                    pass
                time.sleep(1)

            if succeeded:
                logger.info('Assigned floating ip %s to server %s on cloud %s.'
                            % (floating_ip.ip, name, cloud))
            else:
                logger.error('Failed to assign floating ip %s to server %s on '
                             'cloud %s' % (floating_ip.ip, name, cloud))
                logger.info('Deleting server %s on cloud %s' % (name, cloud))
                srv.delete()
                logger.info('Deleting floating ip %s on cloud %s' %
                            (floating_ip.ip, cloud))
                floating_ip.delete()
                raise Exception('Failed to spawn node')

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
        if getattr(settings, 'USE_FLOATING_IPS', False):
            index = -1
        else:
            index = 0

        return self.cloud_server.networks.values()[0][index]

    def delete(self):
        if getattr(settings, 'USE_FLOATING_IPS', False):
            try:
                floating_ip = self.ip
                ref = self.cloud.client.floating_ips.find(ip=floating_ip)
                logger.info('Unassigning floating ip %s from server %s on '
                            'cloud %s.' % (floating_ip, self, self.cloud))
                self.cloud_server.remove_floating_ip(floating_ip)
                logger.info('Deleting floating ip %s on cloud %s.' %
                            (floating_ip, self.cloud))
                ref.delete()
            except novaclient_exceptions.NotFound:
                logger.info('Node already gone, unable to release floating ip')

        logger.info('Deleting server %s on cloud %s.' %
                    (self, self.cloud))
        try:
            self.cloud_server.delete()
        except novaclient_exceptions.NotFound:
            logger.info('Node already gone, unable to delete it')

        if self.signing_key_id:
            logger.info('Deleting signing key for build node %s: %s' %
                        (self, self.signing_key_id))
            utils.run_cmd(['gpg', '--batch', '--yes',
                           '--delete-keys', self.signing_key_id])

        logger.debug('Removing all references from BuildRecords to '
                     'BuildNode %s' % (self,))
        self.buildrecord_set.all().update(build_node=None)

        logger.info('Deleting BuildNode %s' % (self,))
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
        logger.debug('Running: %s' % (cmd,))

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


class TarballCacheEntry(models.Model):
    project_name = models.CharField(max_length=200)
    project_version = models.CharField(max_length=200)
    rev_id = models.CharField(max_length=200, db_index=True, unique=True)

    def project_tarball_dir(self):
        return os.path.join(settings.TARBALL_DIR, self.project_name)

    def filename(self):
        return '%s.tar.gz' % (self.rev_id,)

    def filepath(self):
        return os.path.join(self.project_tarball_dir(), self.filename())

    def store_file(self, filename):
        if not os.path.exists(self.project_tarball_dir()):
            os.makedirs(self.project_tarball_dir())

        shutil.copy(filename, self.filepath())

class PackageSourceBuildProblem(models.Model):
    name = models.CharField(max_length=200)
    code_url = models.CharField(max_length=200)
    packaging_url = models.CharField(max_length=200)
    code_rev = models.CharField(max_length=200)
    pkg_rev = models.CharField(max_length=200)
    flavor = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    def save_log(self, contents):
        with open(self.log_file(), 'w') as fp:
            return fp.write(contents)

    def log_file(self):
        return os.path.join(settings.SRC_PKG_BUILD_FAILURE_LOG_DIR, str(self.pk))

    def log_file_contents(self):
        with open(self.log_file(), 'r') as fp:
            return fp.read()


class PackageSource(models.Model):
    OPENSTACK = 'OpenStack'
    PUPPET = 'Puppet'
    NATIVE = 'Native'

    PACKAGING_FLAVORS = (
        (OPENSTACK, 'OpenStack'),
        (PUPPET, 'Puppet'),
        (NATIVE, 'Native'),
    )

    class SourcePackageBuilder(object):
        ORIG_VERSION_FORMAT = '%(upstream_version)s-%(counter)s'
        PKG_VERSION_FORMAT = '%(epoch)s%(orig_version)s-%(repository_name)s1'

        def __init__(self, source, code_revision, pkg_revision):
            self.source = source
            self.code_revision = code_revision
            self.pkg_revision = pkg_revision

            self.tmpdir = tempfile.mkdtemp()
            self.codedir = os.path.join(self.tmpdir, 'code')
            self.pkgdir = os.path.join(self.tmpdir, 'packaging')

        def cleanup(self):
            shutil.rmtree(self.tmpdir)

        def get_project_name(self):
            raise NotImplementedError()

        def get_project_version(self):
            raise NotImplementedError()

        def build_tarball(self):
            raise NotImplementedError()

        def checkout_code(self):
            logger.debug('Checking out %s' % (self.code_revision,))
            PackageSource._checkout_code(self.source.code_url, self.codedir,
                                         self.code_revision)

        def prepare_code(self, create_cache_entry=True):
            """Prepares the code directory

            Sideeffects: Must make sure self.project_name and
                         self.project_version are set"""
            try:
                logger.debug('Checking to see if we already have %s cached' % (self.code_revision,))
                cache_entry = TarballCacheEntry.objects.get(rev_id=self.code_revision)
                self.project_name = cache_entry.project_name
                self.project_version = cache_entry.project_version
            except TarballCacheEntry.DoesNotExist:
                logger.debug('Did not have %s cached' % (self.code_revision,))
                logger.info('Building tarball for %s (%s)' % (self, self.code_revision,))

                self.checkout_code()
                self.project_name = self.get_project_name()
                self.project_version = self.get_project_version()

                logger.debug('Project name: %s, Version: %s' % (self.project_name, self.project_version))

                cache_entry = TarballCacheEntry(project_name=self.project_name,
                                                project_version=self.project_version,
                                                rev_id=self.code_revision)

                tarball = self.build_tarball()

                if settings.TESTING or not create_cache_entry:
                    print 'Got %s' % (tarball,)
                else:
                    cache_entry.store_file(tarball)
                    cache_entry.save()

            self.cache_entry = cache_entry

        def symlink_orig_tarball(self, subscription, orig_version):
            os.symlink(self.cache_entry.filepath(),
                       '%s/%s_%s.orig.tar.gz' % (subscription.tmpdir,
                                                 self.cache_entry.project_name.replace('_', '-'),
                                                 orig_version))

        def prepare_packaging(self, subscription):
            tmpdir = tempfile.mkdtemp(dir=self.tmpdir)
            pkgdir = os.path.join(tmpdir, 'checkout')
            subscription.tmpdir = tmpdir
            subscription.pkgdir = pkgdir

            PackageSource._checkout_code(self.source.packaging_url, pkgdir,
                                         self.pkg_revision)

            orig_version = self.ORIG_VERSION_FORMAT % {'upstream_version': self.project_version,
                                                       'counter': subscription.counter}

            self.symlink_orig_tarball(subscription, orig_version)

            changelog = utils.run_cmd(['dpkg-parsechangelog'], cwd=pkgdir)

            for l in changelog.split('\n'):
                if l.startswith('Version: '):
                    version = l[len('Version: '):]

            if ':' in version:
                epoch = '%s:' % (version.split(':')[0],)
            else:
                epoch = ''

            return self.PKG_VERSION_FORMAT % {'epoch': epoch,
                                              'orig_version': orig_version,
                                              'repository_name': subscription.target_series.repository.name.replace('-', '')}

        def changelog_entry(self):
            return ('Automated PPA build. Code revision: %s. '
                    'Packaging revision: %s.' % (self.code_revision,
                                                 self.pkg_revision))

        def build_packages(self):
            logger.debug('Building source packages for %r.' % (self,))

            for subscription in self.source.subscription_set.all():
                logger.debug('Building %s for %s.' %
                             (self, subscription.target_series))

                pkg_version = self.prepare_packaging(subscription)
                utils.run_cmd(['dch', '-b',
                              '--force-distribution',
                              '-v', pkg_version,
                              self.changelog_entry(),
                              '-D', subscription.target_series.name],
                              cwd=subscription.pkgdir,
                              override_env={'DEBEMAIL': 'not-valid@example.com',
                                            'DEBFULLNAME': '%s Autobuilder' % (subscription.target_series.repository.name)})

                try:
                    utils.run_cmd(['bzr', 'bd', '-S',
                                  '--builder=dpkg-buildpackage -nc -k%s' % subscription.target_series.repository.signing_key_id,
                                  ],
                                  cwd=subscription.pkgdir)
                except CommandFailed, e:
                    errmsg = ('%r failed.\nExit code: %d\nStdout: %s\n\n'
                              'Stderr: %s\n' % (e.cmd, e.returncode,
                                                e.stdout, e.stderr))
                    psbp = PackageSourceBuildProblem(name=self.source.name,
                                                     code_url=self.source.code_url,
                                                     packaging_url=self.source.packaging_url,
                                                     code_rev=self.code_revision,
                                                     pkg_rev=self.pkg_revision,
                                                     flavor=self.source.flavor)
                    psbp.save()
                    psbp.save_log(errmsg)

#                    email_admins('"bzr bd" failed for %r' % (self,), errmsg)
                    raise

                changes_files = glob(os.path.join(subscription.tmpdir, '*.changes'))

                if len(changes_files) != 1:
                    raise Exception('Unexpected number of changes files: %d' % len(changes_files))

                utils.run_cmd(['dput', '-c', '%s/conf/dput.cf' % subscription.target_series.repository.reprepro_dir,
                               'autopush', changes_files[0]])
                subscription.counter += 1
                subscription.save()

        def build(self):
            self.prepare_code()
            self.build_packages()
            self.cleanup()

    class PuppetPackageBuilder(SourcePackageBuilder):
        def get_project_name(self):
            url = self.source.code_url.split('#')[0]
            project_name = os.path.split(url)[-1]

            if project_name.endswith('.git'):
                project_name = project_name[:-4]

            return project_name

        def get_project_version(self):
            return date.today().strftime('%Y%m%d')

        def build_tarball(self):
            tarball = os.path.join(self.tmpdir,
                                   '%s-%s.tar.gz' % (self.project_name,
                                                     self.project_version))

            utils.run_cmd(['tar', 'cvzf', tarball,
                           '--xform=s,%s,%s-%s,g' % (self.codedir[1:],
                                                     self.project_name,
                                                     self.project_version),
                           '--exclude=%s' % (os.path.join(self.codedir, '.git'),),
                           '--exclude=%s' % (os.path.join(self.codedir, '.bzr'),),
                           self.codedir])

            return tarball

    class NativePackageBuilder(PuppetPackageBuilder):
        ORIG_VERSION_FORMAT = '%(upstream_version)s.%(counter)s'
        PKG_VERSION_FORMAT = '%(epoch)s%(orig_version)s%(repository_name)s1'

        def checkout_code(self):
            pass

        def build_tarballs(self):
            pass

        def prepare_code(self):
            self.project_name = self.get_project_name()
            self.project_version = self.get_project_version()

        def symlink_orig_tarball(self, subscription, orig_version):
            pass

        def changelog_entry(self):
            return ('Automated PPA build. Packaging revision: %s.' %
                    (self.pkg_revision,))

    class OpenStackPackageBuilder(SourcePackageBuilder):
        def get_project_name(self):
            return utils.run_cmd(['python', 'setup.py', '--name'],
                                 cwd=self.codedir).strip().split('\n')[-1]

        def get_project_version(self):
            return utils.run_cmd(['python', 'setup.py', '--version'],
                                 cwd=self.codedir).strip().split('\n')[-1]

        def build_tarball(self):
            utils.run_cmd(['python', 'setup.py', 'sdist'], cwd=self.codedir)
            tarballs_in_dist = glob(os.path.join(self.codedir, 'dist', '*.tar.gz'))

            if len(tarballs_in_dist) != 1:
                raise Exception('Found %d tarballs after "python setup.py sdist". '
                                'Expected 1.')

            return tarballs_in_dist[0]

    PACKAGE_BUILDER_CLASS = {OPENSTACK: OpenStackPackageBuilder,
                             PUPPET: PuppetPackageBuilder,
                             NATIVE: NativePackageBuilder}

    name = models.CharField(max_length=200)
    code_url = models.CharField(max_length=200,
                                help_text="(To specify a specific branch, add "
                                          "'#branchname' to the end of the url)")
    packaging_url = models.CharField(max_length=200,
                                     help_text="(To specify a specific branch,"
                                               " add '#branchname' to the end "
                                               "of the url)")
    last_seen_code_rev = models.CharField(max_length=200)
    last_seen_pkg_rev = models.CharField(max_length=200)
    flavor = models.CharField(max_length=200, choices=PACKAGING_FLAVORS,
                              default=OPENSTACK)
    last_changed = models.DateTimeField(null=True, blank=True, db_index=True)

    def __unicode__(self):
        return self.name

    @classmethod
    def _guess_vcs_type(cls, url):
        if 'launchpad' in url:
            return 'bzr'
        elif 'github' in url:
            return 'git'
        elif url.startswith('git:'):
            return 'git'
        raise Exception('No idea what to do with %r' % url)

    @classmethod
    def lookup_revision(cls, url):
        if not url:
            logger.debug("Empty url. Not going to poll.")
            return ''

        logger.debug("Looking up current revision of %s" % (url,))
        vcstype = cls._guess_vcs_type(url)

        if vcstype == 'bzr':
            out = utils.run_cmd(['bzr', 'revision-info', '-d', url])
            return out.split('\n')[0].split(' ')[1]

        if vcstype == 'git':
            if '#' in url:
                url, branch = url.split('#')
            else:
                branch = 'master'
            out = utils.run_cmd(['git', 'ls-remote', url, branch])
            return out.split('\n')[0].split('\t')[0]

    def poll(self):
        logger.info('Polling %s' % (self,))

        current_code_revision = self.lookup_revision(self.code_url)
        logger.info('Current code revision for %s: %s' %
                    (self, current_code_revision))

        current_pkg_revision = self.lookup_revision(self.packaging_url)
        logger.info('Current packaging revision for %s: %s' %
                    (self, current_pkg_revision))

        logger.debug('Last known code revision for %s: %s' %
                     (self, self.last_seen_code_rev))
        logger.debug('Last known packaging revision for %s: %s' %
                     (self, self.last_seen_pkg_rev))

        something_changed = False

        if self.last_seen_code_rev != current_code_revision:
            logger.debug('Code for %s was updated.' % (self,))
            something_changed = True

        if self.last_seen_pkg_rev != current_pkg_revision:
            logger.debug('Packaging for %s was updated.' % (self,))
            something_changed = True

        if something_changed:
            package_builder_class = self.PACKAGE_BUILDER_CLASS[self.flavor]
            package_builder = package_builder_class(self,
                                                    current_code_revision,
                                                    current_pkg_revision)
            package_builder.build()

            self.last_seen_code_rev = current_code_revision
            self.last_seen_pkg_rev = current_pkg_revision
            self.last_changed = timezone.now()
            self.save()
        return something_changed

    @classmethod
    def vcs_browser_url(self, url, revision):
        if url.startswith('http://bazaar.launchpad.net'):
            return '%s/revision/%s' % (url, revision)
        elif (url.startswith('http://github.com/')
           or url.startswith('https://github.com')):
            if '#' in url:
                url, branch = url.split('#')
            if url.endswith('.git'):
                url = url[:-4]
            return '%s/commit/%s' % (url, revision)
        return '#'

    def vcs_code_url(self):
        return self.vcs_browser_url(self.code_url, self.last_seen_code_rev)

    def vcs_packaging_url(self):
        return self.vcs_browser_url(self.packaging_url, self.last_seen_pkg_rev)

    @classmethod
    def _checkout_code(cls, url, destdir, revision):
        print ("Checking out revision %s of %s" % (revision, url))
        vcstype = cls._guess_vcs_type(url)

        if vcstype == 'bzr':
            if os.path.exists(destdir):
                utils.run_cmd(['bzr', 'pull',
                               '-r', revision,
                               '-d', destdir, url])
                utils.run_cmd(['bzr', 'revert', '-r', revision], cwd=destdir)
                utils.run_cmd(['bzr', 'clean-tree',
                                '--unknown', '--detritus',
                                '--ignored', '--force'], cwd=destdir)
            else:
                utils.run_cmd(['bzr', 'checkout',
                                      '--lightweight',
                                      '-r', revision,
                                      url, destdir])
        elif vcstype == 'git':
            if not os.path.exists(settings.GIT_CACHE_DIR):
                utils.run_cmd(['git', 'init', settings.GIT_CACHE_DIR])

            try:
                # If it's already here, don't fetch.
                utils.run_cmd(['git', 'show', revision, '--'],
                              cwd=settings.GIT_CACHE_DIR)
            except CommandFailed:
                # Fetch all the needed objects and store them in the cache
                if '#' in url:
                    branchless_url, branch = url.split('#')
                else:
                    branchless_url = url

                sanitized_url = branchless_url.replace(':', '_'
                                             ).replace('/', '_')

                remotes = utils.run_cmd(['git', 'remote'],
                                        cwd=settings.GIT_CACHE_DIR).split('\n')

                if not sanitized_url in remotes:
                    utils.run_cmd(['git', 'remote', 'add', sanitized_url,
                                   branchless_url],
                                  cwd=settings.GIT_CACHE_DIR)

                utils.run_cmd(['git', 'fetch', sanitized_url],
                              cwd=settings.GIT_CACHE_DIR)

            if not os.path.exists(destdir):
                # Clones the real repo, but uses the cache as a reference.
                # This saves bandwidth (we know for sure the objects are
                # already there, and gets us a fully usable repo with tags
                # and everything.
                clone_cmd = ['git', 'clone', '--reference',
                             settings.GIT_CACHE_DIR]

                if '#' in url:
                    clone_url, clone_branch = url.split('#')
                    clone_cmd += ['-b', clone_branch, clone_url]
                else:
                    clone_cmd += [url]

                clone_cmd += [destdir]

                utils.run_cmd(clone_cmd)

            utils.run_cmd(['git', 'reset', '--hard', revision], cwd=destdir)
            utils.run_cmd(['git', 'clean', '-dfx'], cwd=destdir)

    def can_modify(self, user):
        return all(x.can_modify(user) for x in self.subscription_set.all())


class Subscription(models.Model):
    source = models.ForeignKey(PackageSource)
    target_series = models.ForeignKey(Series)
    counter = models.IntegerField()

    def can_modify(self, user):
        return self.target_series.can_modify(user)

