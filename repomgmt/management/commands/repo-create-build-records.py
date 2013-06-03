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

from debian_bundle.deb822 import Changes, Dsc

from django.conf import settings
from django.core.management.base import BaseCommand

from repomgmt.models import Architecture, BuildRecord, Repository, Series


def get_repository_name():
    return os.environ['REPREPRO_BASE_DIR'][len(settings.BASE_REPO_DIR):].strip('/')


def parse_changes_file(changes):
    with open(changes, 'r') as fp:
        return Changes(fp)


def parse_dsc_file(dsc):
    with open(dsc, 'r') as fp:
        return Dsc(fp)


def get_dsc_from_changes(changes):
    for file in changes['Files']:
        if file['name'].endswith('.dsc'):
            return file['name']


class Command(BaseCommand):
    args = '<action> <distribution> <source name> <version> <changes file>'
    help = 'Creates build records for new source uploads'

    def handle(self, action, codename, pkg_type, component, architecture,
                     pkg_name, pkg_version, *files, **options):
        if action != 'add' and action != 'replace':
            return

        if os.environ.get('REPREPRO_CAUSING_COMMAND') not in ('processincoming', 'pull'):
            # Only create build record if called by processincoming
            return

        if 'repository' in options:
            repository_name = options['repository']
        else:
            repository_name = get_repository_name()

        repository = Repository.objects.get(name=repository_name)
        series_name = codename[:-len('-proposed')]
        series = Series.objects.get(repository=repository, name=series_name)

        known_archs = dict([(arch.name, arch) for arch in Architecture.objects.all()])

        dsc = None
        for f in files:
            if f.endswith('.dsc'):
                dsc = f
                break
        if dsc is None:
            raise Exception('Adding dsc without .dsc file?!?')

        dsc = parse_dsc_file(os.path.join(repository.reprepro_outdir, dsc))

        requested_archs = dsc['Architecture'].split(' ')

        build_archs = set()

        for arch in requested_archs:
            if arch == 'all':
                build_archs.add(known_archs['i386'])
            elif arch == 'any':
                build_archs.update(known_archs.values())
            elif arch in known_archs:
                build_archs.add(known_archs[arch])

        print build_archs
        for arch in build_archs:
            br = BuildRecord(source_package_name=pkg_name,
                             version=pkg_version,
                             architecture=arch,
                             state=BuildRecord.NEEDS_BUILDING,
                             series=series)
            br.save()
