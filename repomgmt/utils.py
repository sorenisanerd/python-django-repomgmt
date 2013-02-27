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
import re
import subprocess

from django.conf import settings

from repomgmt.exceptions import CommandFailed

logger = logging.getLogger(__name__)


def run_cmd(cmd, input=None, cwd=None, override_env=None,
            discard_stderr=False):
    logger.debug('Executing %r with input=%r' % (cmd, input))
    if settings.TESTING:
        from repomgmt import mock_data
        return mock_data.run_cmd(cmd, input)

    environ = dict(os.environ)

    for k in override_env or []:
        if override_env[k] is None and k in environ:
            del environ[k]
        else:
            environ[k] = override_env[k]

    if discard_stderr:
        stderr_arg = subprocess.PIPE
    else:
        stderr_arg = subprocess.STDOUT

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=stderr_arg, cwd=cwd, env=environ)
    stdout, stderr = proc.communicate(input)
    logger.debug('%r with input=%r returned %r' % (cmd, input, stdout))

    if proc.returncode != 0:
        raise CommandFailed('%r returned %d. Output: %s (stderr: %s)' %
                            (cmd, proc.returncode, stdout, stderr),
                            cmd, proc.returncode, stdout, stderr)

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
