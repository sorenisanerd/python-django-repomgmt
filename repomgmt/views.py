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
import datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sites.models import get_current_site
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.forms import ModelForm
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone


from repomgmt import utils, tasks
from repomgmt.models import Architecture, BuildNode, BuildRecord
from repomgmt.models import ChrootTarball, Repository, Series
from repomgmt.models import UbuntuSeries, PackageSource, Subscription
from repomgmt.models import PackageSourceBuildProblem


class NewArchitectureForm(ModelForm):
    class Meta:
        model = Architecture
        fields = ("name", "builds_arch_all")


class SubscriptionForm(ModelForm):
    class Meta:
        model = Subscription
        fields = ("target_series", "source")


class NewRepositoryForm(ModelForm):
    class Meta:
        model = Repository
        fields = ("name", "contact")


class NewSeriesForm(ModelForm):
    class Meta:
        model = Series
        fields = ("name", "numerical_version", "base_ubuntu_series", "state", "update_from")


class NewPkgSourceForm(ModelForm):
    class Meta:
        model = PackageSource
        fields = ("name", "code_url", "packaging_url", "flavor")


def new_architecture_form(request):
    if request.method == 'POST':
        form = NewArchitectureForm(request.POST)
    else:
        form = NewArchitectureForm()
    return render(request, 'new_architecture_form.html',
                           {'form': form})


def new_repository_form(request):
    if request.method == 'POST':
        form = NewRepositoryForm(request.POST)
    else:
        form = NewRepositoryForm()
    return render(request, 'new_repository_form.html',
                           {'form': form})


def new_series_form(request, repository_name):
    repository = Repository.objects.get(name=repository_name)
    if request.method == 'POST':
        form = NewSeriesForm(request.POST)
    else:
        form = NewSeriesForm()
    return render(request, 'new_series_form.html',
                           {'form': form,
                            'repository': repository})


def new_pkg_source_form(request):
    if request.method == 'POST':
        form = NewPkgSourceForm(request.POST)
    else:
        form = NewPkgSourceForm()
    return render(request, 'new_pkg_source_form.html',
                           {'form': form})


def pkg_sources_list(request):
    if request.method == 'POST':
        if request.POST['action'] == 'create':
            form = NewPkgSourceForm(request.POST)
            if form.is_valid():
                form.save()
                return HttpResponseRedirect(reverse('pkg_sources_list'))
            else:
                return new_pkg_source_form(request)

    t = timezone.now() - datetime.timedelta(hours=1)
    latest_problems = PackageSourceBuildProblem.objects.filter(timestamp__gte=t).order_by('-timestamp')
    return render(request, 'pkg_sources.html',
                          {'pkg_sources': PackageSource.objects.all(),
                           'latest_problems': latest_problems})


def problem_detail(request, problem_id):
    problem = PackageSourceBuildProblem.objects.get(id=problem_id)
    return render(request, 'pkg_src_build_problem.html',
                           {'problem': problem})


def architecture_list(request):
    if request.method == 'POST':
        if request.POST['action'] == 'create':
            form = NewArchitectureForm(request.POST)
            if form.is_valid():
                form.save()
                return HttpResponseRedirect(reverse('architecture_list'))
            else:
                return new_architecture_form(request)

    return render(request, 'architectures.html',
                          {'architectures': Architecture.objects.all()})


def repository_list(request):
    if request.method == 'POST':
        if request.POST['action'] == 'create':
            form = NewRepositoryForm(request.POST)
            if form.is_valid():
                repo = form.save()
                repo.write_configuration()
                return HttpResponseRedirect(reverse('repository_list'))
            else:
                return new_repository_form(request)

    return render(request, 'repositories.html',
                          {'repositories': Repository.objects.all()})


def repository_public_key(request, repository_name):
    repository = Repository.objects.get(name=repository_name)
    return HttpResponse(repository.signing_key.public_key, 'text/plain')


def series_list(request, repository_name):
    repository = Repository.objects.get(name=repository_name)
    if request.method == 'POST':
        if request.POST['action'] == 'create':
            form = NewSeriesForm(request.POST)
            if form.is_valid():
                series = form.save(commit=False)
                series.repository = repository
                series.save()
                form.save_m2m()
                repository.write_configuration()
                kwargs = {'repository_name': repository_name}
                return HttpResponseRedirect(reverse('series_list',
                                                    kwargs=kwargs))
            else:
                return new_series_form(request, repository_name)

    return render(request, 'seriess.html',
                          {'repository': repository,
                           'settings': settings})


def package_list(request, repository_name, series_name):
    repository = Repository.objects.get(name=repository_name)
    series = repository.series_set.get(name=series_name)
    packages = series.get_source_packages()
    pkg_data = {}
    for distribution_name in packages:
        for pkg_name, pkg_version in packages[distribution_name].iteritems():
            if not pkg_name in pkg_data:
                pkg_data[pkg_name] = {}
            pkg_data[pkg_name][distribution_name] = pkg_version

    l = [dict(name=pkg_name, **data) for pkg_name, data in pkg_data.iteritems()]

    return render(request, 'packages.html',
                          {'series': series,
                           'subscriptions': series.subscription_set.all(),
                           'pkg_data': l})


def promote_series(request):
    # Disabled until we have authorization in place
    return
    if request.method == 'POST':
        if not 'repository' in request.POST or not 'series' in request.POST:
            return

        series_name = request.POST['series']
        repository_name = request.POST['repository']
        series = Series.objects.get(name=series_name,
                                    repository__name=repository_name)
        series.promote()
        return HttpResponseRedirect(reverse('packages_list',
                                    kwargs={'repository_name': repository_name,
                                            'series_name': series_name}))


def puppet_manifest(request, build_record_id):
    build_record = BuildRecord.objects.get(pk=build_record_id)
    return render(request, 'buildd.puppet.pp.tmpl',
                          {'build_record': build_record,
                           'settings': settings},
                          content_type='text/plain')


def builder_detail(request, builder_name):
    bn = get_object_or_404(BuildNode, name=builder_name)
    return render(request, 'builder.html',
                          {'build_node': bn})


def builder_list(request):
    return render(request, 'builders.html',
                          {'build_nodes': BuildNode.objects.all()})


def build_detail(request, build_id):
    br = get_object_or_404(BuildRecord, id=build_id)
    if request.method == 'POST':
        if request.POST['action'] == 'Rebuild':
            if br.allow_rebuild():
                br.update_state(br.NEEDS_BUILDING)
            return HttpResponseRedirect(
                      reverse('build_detail', kwargs={'build_id': build_id}))

    return render(request, 'build.html',
                          {'build': br})


def build_list(request):
    builds = BuildRecord.objects.order_by('-created')
    paginator = Paginator(builds, 25)

    page = request.GET.get('page')
    try:
        builds = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        builds = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        builds = paginator.page(paginator.num_pages)
    return render(request, 'builds.html',
                          {'build_records': builds})


def tarball_list(request):
    msg = None
    if request.method == 'POST':
        for x in request.POST:
            if request.POST[x] == 'Build it':
                series_name, architecture_name = x.split('-')
                filter = {'series__name': series_name,
                          'architecture__name': architecture_name}
                tb = ChrootTarball.objects.get(**filter)
                tb.state = tb.WAITING_TO_BUILD
                tb.save()
                tasks.refresh_tarball.delay(tb.id)
                request.session['msg'] = 'Refresh triggered'
                return HttpResponseRedirect(reverse('tarball_list'))
    tarballs = {}
    for ubuntu_series in UbuntuSeries.objects.all():
        tarballs[ubuntu_series] = {}
        for architecture in Architecture.objects.all():
            try:
                tb = ChrootTarball.objects.get(series=ubuntu_series,
                                               architecture=architecture)
            except ChrootTarball.DoesNotExist:
                tb = ChrootTarball(series=ubuntu_series,
                                   architecture=architecture)
                tb.save()
            tarballs[ubuntu_series][architecture] = tb

    msg = request.session.pop('msg', None)
    return render(request, 'tarballs.html',
                          {'tarballs': tarballs,
                           'msg': msg})


def builder_new(request):
    utils.start_new_worker_node()
    return HttpResponse('created', 'text/plain')


def docs_api(request):
    return render(request, 'docs/api.html',
                           {'site': get_current_site(request)})


def docs_workflow(request):
    return render(request, 'docs/workflow.html',
                           {'site': get_current_site(request)})


@login_required
def redirect_to_self(request):
    return HttpResponseRedirect('/users/%s' % (request.user.username,))


def user_details(request, username):
    user = get_object_or_404(User, username=username)
    return render(request, 'user.html',
                          {'userobj': user})


def subscription_edit(request, subscription_id):
    subscription = get_object_or_404(Subscription, id=subscription_id)
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('subscription_detail', args=[subscription.id]))
    else:
        form = SubscriptionForm(instance=subscription)
    return render(request, 'subscription_edit.html', {'form': form,
                                                      'subscription': subscription})


def subscription_detail(request, subscription_id):
    subscription = get_object_or_404(Subscription, id=subscription_id)
    return render(request, 'subscription.html',
                           {'subscription': subscription})


def front_page(request):
    latest_builds = BuildRecord.objects.order_by('-created')[:10]
    latest_code_updates = PackageSource.objects.order_by('-last_changed')[:10]
    return render(request, 'front.html',
                  {'latest_builds': latest_builds,
                   'latest_code_updates': latest_code_updates})
