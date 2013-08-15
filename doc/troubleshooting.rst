###############
Troubleshooting
###############

This system has bugs. As do other systems that this system interacts with. So occasionally, things will get stuck, etc.

Should a build get stuck for some reason, the easiest way to fix it is probably to identify the build node, and grab the corresponding object from the django shell:

    >>> from repomgmt import models
    >>> bn = models.BuildNode.objects.get(name='buildd-345')
    >>> bn.delete()

That should clean everything up.

Then reset the build record's state to "Needs building":

    >>> from repomgmt import models
    >>> bn = models.BuildRecord.objects.get(id=3432)
    >>> bn.state = models.BuildRecord.NEEDS_BUILDING
    >>> bn.save()

The scheduler should pick that up soon enough.
