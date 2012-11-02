python-django-repomgmt

This Django app implements everything you need to create APT repositories,
buildd infrastructure as well as automatic package building.

It expects access to an OpenStack Compute cloud to perform builds and uses
reprepro on the backend to manage the APT repositories, process incoming,
etc.

Setting it up should be fairly simple.

You need Django, django-tastypie, django-celery, sbuild and devscripts
installed.

These are the configuration options you need to add to your settings.py:

APT_REPO_BASE_URL

    The base URL by which your repositories will be reachable.

    E.g. if set to http://apt.example.com/, it's assumed that
    your web server is configured to expose e.g. the "cisco" repository
    under http://apt.example.com/cisco

POST_MK_SBUILD_CUSTOMISATION

    An argv to be executed in the schroot after mk-sbuild is done.

    E.g. to avoid using a proxy for a apt.example.com, you can do
    something like:

    POST_MK_SBUILD_CUSTOMISATION = ['bash', '-c', 'echo \'Acquire::HTTP::Proxy::apt.example.com "DIRECT";\' > /etc/apt/apt.conf.d/99noproxy']

BASE_URL

    The base URL of the repomgmt app. This is used to construct URLs
    where build nodes can fetch their puppet manifest.

BASE_TARBALL_URL

    A URL where the generated tarballs can be found. The tarballs generally
    land in /var/lib/schroot/tarballs, so you should configure a web server to
    serve that directory at this URL.

BASE_REPO_DIR

    The base directory where the repositories should be kept.
    Each repository will be represented by a subdirectory here.

It is also expected that django-celery is already configured. This should be as simple as adding something like this near the end of your settings.py:

    INSTALLED_APPS += ("djcelery", )
    import djcelery
    djcelery.setup_loader()

    BROKER_URL = 'amqp://guest:guest@localhost:5672/'
