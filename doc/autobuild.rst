.. _autobuild:

Automatic building of source packages
=====================================

The repomgmt system is capable of building certain types of source packages.

Great care is taken to mimic with upstream release process at the expense of
generality:

When a change is discovered in a git repository a corresponding tarball is
built.  Compare this to the the general OpenStack packaging workflow
found it the various distributions: A tarball (signed by the release manager)
is taken from upstream and then packaging gets added. We attempt to line up
closely with this workflow to ease collaboration with the distributions's
packaging teams.

"Building a tarball" is easier said than done. That's why we have multiple types:

 * OpenStack
 * Puppet
 * Native

OpenStack
    For OpenStack projects, "python setup.py sdist" is invoked to get the
    tarball, and "python setup.py --name" and "python setup.py --version"
    to get the name and version, respectively.

Puppet
    For Puppet projects, a simple tarball is created from the contents of
    the given code branch, and the final component of the code url string is
    used as the project name. The version string is generated based on today's
    date.

Native
    The native package type blindly trusts what it finds in the packaging
    branch.


Data model
----------

It's worth spending a bit of time on the data model for this
auto-source-package-building system:

There are two data types: Package sources and Subscriptions.

A package source is defined by a type, a code url and a packaging url.

Each package source can have a number of "subscriptions". A subscription
ties a package source to a release series in an APT repository.

Every 5 minutes, each package source is polled for changes. If it finds
changes in the code repository, it fetches the code, builds and caches a
tarball along with the project name and project version. How it
determines the project name and project version depends on the type of
the package source as outlined above.

Using this information, it generates a changelog entry for the
debian/changelog. It contains the code revision and packaging revision,
so that we can see that information once the package is installed. The
version of the changelog entry is generated automatically. This is the
format:

   [<epoch>:]<upstream version>-<counter>-<repo name>1

epoch
    Copied from the topmost entry in the debian/changelog found in the packaging branch.

    The epoch is included to allow for "downgrades": If the version as returned by
    "python setup.py --version" is strictly lower than the current version in the
    repository, it would normally be rejected. Increasing the epoch allows it to
    pass through. This is a manual process, as bumping the epoch should not
    generally be taken lightly (as it hinders reconciliation with upstream later on).

upstream version
    As derived by e.g. "python setup.py --version"

    The upstream version is included to indicate the version the package is
    based on.

counter
    A per-subscription counter

    The counter ensures a monotonically increasing versioning for each
    successive change.

    One might wonder why the counter is per subscription rather than per
    package source. Consider this use case:

        You've created a new APT repository with a new series for a particular
        customer. You specified it as being based on COE Folsom. This means it
        got a copy of all the packages from COE Folsom as well as all the
        subscriptions from COE Folsom. Some time passes, and you need to push
        an experimental change for Nova out to your customer. You create a new
        package source pointing at a git branch with your experimental change
        in it. Then you modify the subscription currently pointing to  COE
        Folsom's nova git branch, and point it to this new package source.
        In order for this package to supersede the one from COE Folsom, the
        generated version must be higher. Had the counter been based on the
        package source (which is brand new), this would not be the case.

    The actual usage patterns have demonstrated, though, that this is not much of a
    real concern, especially in the light of the extra resources spent building the
    same package X times.

repo name
    Name of the target APT repository

    The repo name is embedded to make it clear where the packages comes from.
