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
from repomgmt.models import Series, UpstreamSeries


class Command(BaseCommand):
    args = ''
    help = 'Poll all upstream archives and update local db accordingly'

    def handle(self, **options):
        all_source_packages = set()
        for series in Series.objects.all():
            series_pkgs = series.get_source_packages()
            for pocket in series_pkgs:
                all_source_packages.update(series_pkgs[pocket].keys())

        # all_source_packages now holds the source package names of all
        # packages we have locally
        for upstream_series in UpstreamSeries.objects.all():
            upstream_series.update()
            upstream_series.update_pkg_versions(all_source_packages)



