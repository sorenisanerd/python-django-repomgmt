import os
import random
import string

DEBUG = True

DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': ':memory:',
    'TEST_NAME': ':memory:',
  },
}

ROOT_URLCONF = 'repomgmt.urls'
SITE_ID = 1
SECRET_KEY = ''.join([random.choice(string.ascii_letters) for x in range(40)])

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'registration',
    'tastypie',
    'repomgmt',
    'djcelery',
)

TEST_RUNNER = 'django.test.simple.DjangoTestSuiteRunner'

AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',
                           'repomgmt.auth.MyAuthBackend')

PASSWORD_HASHERS = ('django.contrib.auth.hashers.MD5PasswordHasher',)
LOGIN_REDIRECT_URL = '/users/me/'
TIMEZONE = 'UTC'

# repomgmt settings:

import tempfile
from urlparse import urlparse
REPOMGMT_BASE_DIR = tempfile.mkdtemp()
REPOMGMT_BASE_URL = 'http://apt.ctocllab.cisco.com/'

def cleanup(d=REPOMGMT_BASE_DIR):
    import shutil
    shutil.rmtree(d)


APT_REPO_BASE_URL = '%srepos/' % (REPOMGMT_BASE_URL,)

o = urlparse(APT_REPO_BASE_URL)

POST_MK_SBUILD_CUSTOMISATION = ['bash', '-c', 'echo \'Acquire::HTTP::Proxy::%s "DIRECT";\' > /etc/apt/apt.conf.d/99noproxy' % (o.hostname, )]

BASE_URL = 'http://172.29.75.147:8000'
BASE_TARBALL_URL = 'http://172.29.75.147/tarballs/'

BASE_REPO_DIR = os.path.join(REPOMGMT_BASE_DIR, 'repos')
APT_CACHE_DIR = os.path.join(REPOMGMT_BASE_DIR, 'apt')
BASE_PUBLIC_REPO_DIR = os.path.join(REPOMGMT_BASE_DIR, 'public')
TARBALL_DIR = os.path.join(REPOMGMT_BASE_DIR, 'tarballs')
GIT_CACHE_DIR = os.path.join(REPOMGMT_BASE_DIR, 'gitcache')
BASE_INCOMING_DIR = os.path.join(REPOMGMT_BASE_DIR, 'incoming')
TESTING = True
# Celery stuff

import djcelery
djcelery.setup_loader()

BROKER_URL = 'amqp://guest:guest@localhost:5672/'
