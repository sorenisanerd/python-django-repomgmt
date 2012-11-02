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
from django.core.urlresolvers import reverse
from django.forms import ModelForm
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render

from repomgmt import utils, tasks
from repomgmt.models import Architecture, BuildNode, BuildRecord
from repomgmt.models import ChrootTarball, Repository, Series


class NewRepositoryForm(ModelForm):
    class Meta:
        model = Repository
        fields = ("name", "contact")


class NewSeriesForm(ModelForm):
    class Meta:
        model = Series
        fields = ("name", "numerical_version", "base_ubuntu_series", "state")


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
                          {'repository': repository})


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

    return render(request, 'packages.html',
                          {'series': series,
                            'pkg_data': pkg_data})


def promote_series(request):
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
                          {'repositories': Repository.objects.all(),
                           'build_record': build_record},
                          content_type='text/plain')


def builder_list(request):
    return render(request, 'builders.html',
                          {'build_nodes': BuildNode.objects.all()})


def build_list(request):
    return render(request, 'builds.html',
                          {'build_records': BuildRecord.objects.all()})


def tarball_list(request):
    msg = None
    if request.method == 'POST':
        for x in request.POST:
            if request.POST[x] == 'Build it':
                series_name, repository_name, architecture_name = x.split('-')
                filter = {'series__name': series_name,
                          'series__repository__name': repository_name,
                          'architecture__name': architecture_name}
                tb = ChrootTarball.objects.get(**filter)
                tb.state = tb.WAITING_TO_BUILD
                tb.save()
                tasks.refresh_tarball.delay(tb.id)
                request.session['msg'] = 'Refresh triggered'
                return HttpResponseRedirect(reverse('tarball_list'))
    tarballs = {}
    for repository in Repository.objects.all():
        tarballs[repository] = {}
        for series in repository.series_set.all():
            tarballs[repository][series] = {}
            for architecture in Architecture.objects.all():
                try:
                    tb = ChrootTarball.objects.get(series=series,
                                                   architecture=architecture)
                except ChrootTarball.DoesNotExist:
                    tb = ChrootTarball(series=series,
                                       architecture=architecture)
                    tb.save()
                tarballs[repository][series][architecture] = tb

    msg = request.session.pop('msg', None)
    return render(request, 'tarballs.html',
                          {'tarballs': tarballs,
                           'msg': msg})


def builder_new(request):
    utils.start_new_worker_node()
    return HttpResponse('created', 'text/plain')


def front_page(request):
    return render(request, 'front.html')
