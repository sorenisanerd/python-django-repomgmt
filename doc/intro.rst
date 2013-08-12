============
Introduction
============

This document (and its siblings) will attempt to describe some of the inner
workings as well as some of the rationales behind these design choices of this
project..

At the center sits the APT repostiory management system. It's modeled after the
"real" APT repository mamagement systems (Ubuntu's and Debian's), yet taylored
to meet specific use cases that will be covered later.

At its core, an APT repository management system takes source packages
as input, generates binary packages and publishes them in an APT
repository. Many packages these days are Python or Puppet code, so "binary
packages" is perhaps a bit of a misnomer. See :ref:`model-packages` for more an explanation.

Everything makes it way into these APT repositories by first being
uploaded as a source package. This goes for OpenStack components, Puppet
modules, the Linux kernel (if you were to ship a special build of that),
etc.

There's some difference in how these source package are created, though.

Some are uploaded manually. This is mostly true for components that are simply
provided because the packages that we really care about need them, but they're
not themselves a focus of our development efforts.

Others are built from git. This is mostly true for things that we're
likely to want to actually put some effort into working on. The goal is
to allow developers to focus on these components and allow someone else to deal
with packaging as a separate effort. Wrapping your head around a big project
(like e.g. OpenStack which was the original use case for this system) is
daunting enough as it is. There's (generally) no need to add the complexity of
packaging on top of it.

The repository management system has an auxilliary component that polls
git and bzr repositories looking for changes. Once it finds changes, it
builds source packages and uploads them to the APT repository management
system at which point it's treated like any other source package upload. For
more information on this auto-build system, please see :ref:`autobuild`.

The core deliverable for the APT repository management system
is binary packages. When a source package is uploaded, the system
verifies the uploader (based on a GPG signature). If it's correctly
signed, a VM will be created in an OpenStack deployment, and the build
will be performed there. Once the builds completes, the resulting
package is sent back to the APT repo mgmt system and the binaries are
published into the relevant release series.


