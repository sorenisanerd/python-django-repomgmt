======================
Data model/Terminology
======================

Most of what this project does will seem pretty opaque without some basic knowledge of Debian style repositories. I'll both attempt to explain them in general terms, but also use examples from Debian or Ubuntu.

Repository
----------
Repositories are the top level division. They essentially form a common namespace for a (number of) series. As an example, Ubuntu and Debian each have a single repository (of relevance) which contains all of their release series (Lucid, Precise, Quantual, etc. for Ubuntu and ethc, lenny, squeeze, and wheezy for Debian).

Series
------

A series is a subdivision of an apt repository. They're typically sequential (e.g. precice, oneiric, quantal and raring are all examples of series in Ubuntu), although they strictly need not be.

Pockets
-------

Series are further subdivided into pockets. Pockets serve various release management purposes. In Ubuntu, the pockets are:
 * The release pocket (e.g. for Ubuntu Precise, this is simply called "precise"),
 * the updates pocket (e.g. "precise-updates"),
 * the proposed pocket (e.g. "precise-proposed"), and
 * the security pcoket (e.g. "precise-security").

Components
----------

Finally, APT repositories have a notion of components. This project does not actually implement them (the need has yet to arise), so I'll just mention that Ubuntu's components are "main", "universe", "restricted", and "multiverse".

.. model-packages:

Packages
--------

Packages are either binary packages or source packages. Binary packages are single files with a ``.deb`` extension. Source packages are made up of three packages: An ``.orig.tar.gz``, a ``.diff.gz`` and a ``.dsc``. The ``.orig.tar.gz`` is the original tarball, as it is found on the upstream project's download page. The ``.diff.gz`` is a diff that gets applied after unpacking the original tarball. Finally, the ``.dsc`` contains some metadata describing the other two (like name, version, etc.).

A package can belong to multiple series. This is especially common just after version X is released, and version X+1 is opened for development. At that point, version X+1 is identical to version X. They share all the same .deb files in the repository (by way of both simply referring to the same URLs in the Packages index). As changes are added to version X+1, it simply stops referring to the same files as version X.

Example: When Ubuntu Precise was released, Ubuntu Quantal was created as a copy of Ubuntu Precise. No files were copied, only metadata. As changes were uploaded to Ubuntu Quantal, these changes took the place of the packages from Ubuntu Precise.

Repository layout
-----------------

The top level of a repository has two directories:

 * ``pool``
 * ``dists``

``pool``
    this is where all the package files reside. Under ``pool``, you find one directory per component. In this project, we only have ``main``, so that's all you'll find. In the ``pool/main`` directory, you'll find a number of directories, named ``a`` through ``z`` as well as ``liba`` through ``libz``.
   
    * Source packages with names starting with ``a`` go into ``pool/main/a``.
    * Source packages with names starting with ``b`` go into ``pool/main/b``.
    * etc.
    * Source packages with names starting with ``liba`` go into ``pool/main/liba``.
    * Source packages with names starting with ``libb`` go into ``pool/main/libb``,
    * etc.
    
    Each source package has its own directory, so e.g. ``apt`` has a directory called ``pool/main/a/apt`` that holds ``apt``'s source packages as well as their binary package (regardless of the name of the binary packages).


``dists``
    this is where all the metadata resides.

    First, there's a directory per pocket (using Ubuntu precise as the example):

    * ``dists/precise/``
    * ``dists/precise-security/``
    * ``dists/precise-updates/``
    * ``dists/precise-proposed/``
    * etc.
    
    Each of these directories are equivalent, they just list different files. If we for example look at ``dists/precise``, we find:

    ``dists/precise/Contents-amd64.gz``
        a list of files in every package found in Ubuntu Precice's release
        pocket for the amd64 architecture.. It's used by ``apt-file`` to lookup
        which package holds a named file (if the package isn't installed, that
        is).

    ``dists/precise/Contents-i386.gz``
        ditto for the i386 architecure

    ``dists/precise/Release``
        the "Release" file. It includes some metadata about the release (actually about the pocket) as well as list all the other files (Package lists, etc.) in this directory struture along with their MD5Sums,  SHA1Sums and SHA256Sums.

    ``dists/precise/Release.gpg``
        cryptographic signature of ``dists/precise/Release``. This is the only thing that is signed in the repository. Individual packages's authenticity is verified by way of this signature (through the SHA256Sum of the Package indices which list the SHA256Sum of the individual package files).

    ``dists/precise/main``
    ``dists/precise/multiverse``
    ``dists/precise/restricted``
    ``dists/precise/universe``
        These hold the next level of metadata. Like the directories for the individual pockets, these a equivalent, so we'll just look at one of them:


        ``dists/precise/main/binary-amd64``
            the directory holding the indices for binary packages for the amd64 architecture:

            ``dists/precise/main/binary-amd64/Packages.bz2``
                The bzip2 compressed package index. The package index is an rfc-822 style listing of all the package offered for the amd64 architecture along with their name, version, MD5Sum, SHA256Sum, their path in the ``/pool/`` directory, etc.

            ``dists/precise/main/binary-amd64/Packages.gz``
                The gzip compressed ditto

            ``dists/precise/main/binary-amd64/Release``
                Metadata describing the context (component, architecture, etc.)

        ``dists/precise/main/binary-i386``
             ditto for i386   

        ``dists/precise/main/source``
             analogous to the binary-* directories, this holds the Source package index

            ``dists/precise/main/source/Sources.bz2``
                The bzip2 compressed package index

            ``dists/precise/main/source/Sources.gz``
                The gzip compressed ditto

            ``dists/precise/main/source/Release``
                Metadata describing the context (component, architecture (i.e. "source"), etc.)

        ``dists/precise/main/debian-installer``
        ``dists/precise/main/installer-amd64``
        ``dists/precise/main/installer-i386``
             stuff pertaining to the debian-installer



APT
===

When configuring apt, you specify sources in ``/etc/apt/sources.list`` (or ``/etc/apt/sources.list.d/XXX.list`` ). Each line has the following format::

    deb scheme://host/path/ pocket component [component] [component]...

or::

    deb-src scheme://host/path/ pocket component [component] [component]...

Lines beginning with ``deb`` denote binary package sources, while lines beginning with ``deb-src`` denote source package sources.

When multiple components are specified, the cartesian product of ``pocket`` and ``component,component,...`` is used.

From each source, it will fetch the package index. When asked to install a package, it will (unless instructed otherwise) choose the highest versioned package it can find across all its configured sources. For example, if both ``precise`` and ``quantal`` were configured, the package from ``quantal`` would most likely take precedence (as it would have a version higher than that found in Precise). Note that this comparison is done per-package. The fact that ``quantal`` sorts after ``precise`` is irrelevant.


