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
from repomgmt.models import BuildNode


class Command(BaseCommand):
    args = '<build_node_name> <command>'
    help = 'Runs command on the given build node'

    def handle(self, build_node_name, cmd, **options):
        bn = BuildNode.objects.get(name=build_node_name)
        for data in bn.run_cmd(cmd):
            self.stdout.write(data)
