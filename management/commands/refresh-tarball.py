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
from django.core.management.base import BaseCommand
from repomgmt.models import Architecture, ChrootTarball, Repository


class Command(BaseCommand):
    args = '<repository> <series> <architecture>'
    help = 'Refreshes (or builds from scratch if it does not yet exist) tarball'

    def handle(self, repo_arg, series_arg, arch_arg, **options):
        repo = Repository.objects.get(name=repo_arg)
        series = repo.series_set.get(name=series_arg)
        arch = Architecture.objects.get(name=arch_arg)
        try:
            tb = ChrootTarball.objects.get(series=series, architecture=arch)
        except ChrootTarball.DoesNotExist:
            tb = ChrootTarball(series=series, architecture=arch)
            tb.save()
        tb.refresh()
