###################
Management commands
###################

A number of commands are offered to do various backendy or debuggy sorts of things:

``python manage.py repo-add-uploader <repo> <uploader>``
    Adds a named uploader (user must exist prior to running the command) to a named repository.  Without this privilege, a user's uploads to the given repository will be silently dropped.

``python manage.py repo-add-user-key <uplaoder> <key id>``
    Imports key from keyserver and associates it with the given user.

``python manage.py repo-build-tarball <url>``
    This is a weird, old, unused command. Ignore it.

``python manage.py repo-connect-to-node <node name>``
    Connects interactively to the named node

``python manage.py repo-create-build-records``
    Called by reprepro. Not for human consumption.

``python manage.py repo-create-repo-key <repo>``
    Create key for named repo. Not needed anymore. Just ignore it.

``python manage.py repo-freeze <repo> <series>``
    Freezes named series in named repository. This blocks new uploads from being added (handy for ensuring consistent test runs).

``python manage.py repo-import-dsc-to-git``
    Triggered by reprepro to import uploaded source packages into git. Shouldn't be run manually.

``python manage.py repo-poll-upstreams``
    Polls all package sources for changes. Not used anymore (this is done by Celery instead now)

``python manage.py repo-process-build-queue``
    Checks for pending builds and runs one if any are found.

``python manage.py repo-process-changes``
    Called from reprepro. Not for manual use.

``python manage.py repo-processincoming``
    Process incoming source package uploads.

``python manage.py repo-refresh-tarball``
    Refresh chroot

``python manage.py repo-set-repo-key <repo> <key id>``
    If importing existing repository, use this command to specify the key id (which must already be imported into the GPG keyring).

``python manage.py repo-sync-confs``
    Ensure all configuration files are up-to-date by writing them again

``python manage.py repo-unfreeze``
    Opposite of repo-freeze.
