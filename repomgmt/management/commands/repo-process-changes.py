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
import logging
import os

from debian_bundle.deb822 import Changes, Dsc

from django.conf import settings
from django.core.management.base import BaseCommand

from repomgmt.models import Architecture, BuildRecord, Repository, Series

logger = logging.getLogger(__name__)


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

    def handle(self, action, codename, pkg_name, pkg_version, changes_file,
               *args, **options):

        if action != 'accepted':
            logger.debug('Was called with %r != "accepted". Bailing.'
                         % (action,))
            return

        logger.debug('Parsing changes file %s' % (changes_file,))
        changes = parse_changes_file(changes_file)

        if changes['Architecture'] == 'source':
            logger.debug("Architecture %r == 'source'. Bailing."
                         % (changes['Architecture'],))
            return

        archs_contained = changes['Architecture'].split(' ')

        logger.debug("Architectures contained in this file: %r" %
                     (archs_contained,))
        build_archs = set()

        for arch_name in archs_contained:
            if arch_name == 'all':
                arch = Architecture.objects.get(builds_arch_all=True)
            else:
                arch = Architecture.objects.get(name=arch_name)
            build_archs.add(arch)

        logger.debug("Build architectures: %r" % (build_archs,))

        if len(build_archs) != 1:
            raise Exception("changes file claims Architecture: %r, but that "
                            "doesn't make sense." % changes['Architecture'])

        architecture = build_archs.pop()

        if 'repository' in options:
            repository_name = options['repository']
        else:
            repository_name = get_repository_name()

        logger.debug('Fetching repository obj by name: %s'
                     % (repository_name,))
        repository = Repository.objects.get(name=repository_name)

        series_name = codename[:-len('-proposed')]
        logger.debug('Given codename "%s" yielded series name "%s"'
                     % (codename, series_name))
        series = Series.objects.get(repository=repository, name=series_name)

        logger.debug('Fetching build record given series %r, architecture %r,'
                     ' source_package_name %s and version %s'
                     % (series, architecture, pkg_name, pkg_version))

        br = BuildRecord.objects.get(series=series, architecture=architecture,
                                     source_package_name=pkg_name,
                                     version=pkg_version)
        br.update_state(BuildRecord.SUCCESFULLY_BUILT)

        logger.info('Finished processing build record %r. Deleting associated '
                    'build node %r' % (br, br.build_node))
        br.build_node.delete()
