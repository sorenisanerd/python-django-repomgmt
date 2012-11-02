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
import re
import subprocess

from django.conf import settings


def run_cmd(cmd, input=None):
    if settings.TESTING:
        from repomgmt import mock_data
        return mock_data.run_cmd(cmd, input)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    return stdout


def get_image_by_regex(cl, regex):
    rx = re.compile(regex)
    for image in cl.images.list():
        if rx.match(image.name):
            return image


def get_flavor_by_name(cl, name):
    for flavor in cl.flavors.list():
        if flavor.name == name:
            return flavor
