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
import textwrap
from django.core.management.base import BaseCommand
from repomgmt.models import Repository
from repomgmt.utils import run_cmd


class Command(BaseCommand):
    args = '<repository>'
    help = 'Sets the signing key for a repository'

    def handle(self, repo_arg, **options):
        repo = Repository.objects.get(name=repo_arg)
        if repo.signing_key_id:
            print 'Repo already has a signing key.'
            return
        output = run_cmd(['gpg', '--batch', '--gen-key'],
                         input=textwrap.dedent('''\
                                               Key-Type: 1
                                               Key-Length: 4096
                                               Subkey-Type: ELG-E
                                               Subkey-Length: 4096
                                               Name-Real: %s repository
                                               Expire-Date: 0
                                               %%commit'''))
        for l in output.split('\n'):
            if l.startswith('gpg: key '):
                key_id = l.split(' ')[2]

        repo.signing_key_id = key_id
        repo.signing_key.public_key
        repo.save()
