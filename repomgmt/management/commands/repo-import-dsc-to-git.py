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

from debian_bundle.deb822 import Dsc

from django.conf import settings
from django.core.management.base import BaseCommand

from repomgmt import utils
from repomgmt.models import Repository, Series


def get_repository_name(options, environ=os.environ):
    if 'repository' in options:
        return options['repository']
    else:
        return environ['REPREPRO_BASE_DIR'][len(settings.BASE_REPO_DIR):].strip('/')


def parse_dsc_file(dsc):
    with open(dsc, 'r') as fp:
        return Dsc(fp)


class Command(BaseCommand):
    args = '<action> <distribution> <source name> <version> <changes file>'
    help = 'Creates build records for new source uploads'

    def handle(self, action, codename, pkg_type, component, architecture,
                     pkg_name, pkg_version, *files, **options):
        if action != 'add' and action != 'replace':
            return

        repository_name = get_repository_name(options)

        repository = Repository.objects.get(name=repository_name)

        dsc_file = None
        for f in files:
            if f.endswith('.dsc'):
                dsc_file = f
                break
        if dsc_file is None:
            raise Exception('Adding dsc without .dsc file?!?')

        dsc_path = os.path.join(repository.reprepro_outdir, dsc_file)
        dsc = parse_dsc_file(dsc_path)

        git_dir = os.path.join(repository.reprepro_outdir, 'pkgs', dsc['Source'])
        if not os.path.exists(git_dir):
            os.makedirs(git_dir)
            os.chdir(git_dir)
            utils.run_cmd(['git', 'init'])
        else:
            os.chdir(git_dir)

        utils.run_cmd(['git', 'import-dsc', dsc_path])
