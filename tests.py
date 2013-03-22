import os
import sys

os.environ["DJANGO_SETTINGS_MODULE"] = 'repomgmt.testsettings'
from repomgmt import testsettings as settings


def run_tests(settings):
    from django.test.utils import get_runner

    TestRunner = get_runner(settings)
    test_runner = TestRunner(interactive=False)
    failures = test_runner.run_tests(['repomgmt'])
    return failures


def main():
    failures = run_tests(settings)
    settings.cleanup()
    sys.exit(failures)

if __name__ == '__main__':
    main()
