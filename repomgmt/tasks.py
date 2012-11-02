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
from celery.utils.log import get_task_logger
from django.conf import settings

from repomgmt.models import ChrootTarball

logger = get_task_logger(__name__)

# If we're testing, don't defer anything. Accordingly, these tasks
# should be replaced with mock implementations during testing.
if getattr(settings, 'TESTING', False):
    def task():
        def inner(f):
            def run(*args, **kwargs):
                return f(*args, **kwargs)
            f.delay = run
            return f
        return inner
else:
    from celery import task


@task()
def refresh_tarball(tarball_id):
    tb = ChrootTarball.objects.get(pk=tarball_id)
    logger.info('Refreshing %r' % (tb,))
    tb.refresh()
