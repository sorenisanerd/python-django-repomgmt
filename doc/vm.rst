.. _vm:

==============================
Virtual Machine usage and flow
==============================

We make heavy use of virtual machines. All binary builds happen in a fresh
cloud instance.

If there are pending builds, a virtual machine is fired up and instructed to
fetch a puppet manifest. The puppet manifest makes sure all the build
infrastructure is installed.

Once the infrastructure is installed and everything is up-to-date, the source package is fetched from the relevant APT repository and the build is performed.

The output of the build is used to determine its success which is recorded accordingly on the build record. If the build isn't succesful, the VM is killed. If it *is* succesful, the VM is killed when the corresponding binary upload has been processed.
