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
from django.conf.urls import patterns, url, include
from repomgmt.api import api

urlpatterns = patterns('',
    url(r'^api/', include(api.urls)),

    # Builders
    url(r'^builders/new/$', 'repomgmt.views.builder_new', name='builder_new'),
    url(r'^builders/$', 'repomgmt.views.builder_list', name='builder_list'),

    # Builds
    url(r'^builds/$', 'repomgmt.views.build_list', name='build_list'),

    # Tarballs
    url(r'^tarballs/$', 'repomgmt.views.tarball_list', name='tarball_list'),

    # Repositories
    url(r'^repositories/$', 'repomgmt.views.repository_list',
        name='repository_list'),
    url(r'^repositories/new/$', 'repomgmt.views.new_repository_form',
        name='new_repository_form'),

    url(r'^repositories/(?P<repository_name>\w+)/$',
        'repomgmt.views.series_list', name='series_list'),
    url(r'^repositories/(?P<repository_name>\w+)/new/$', 'repomgmt.views.new_series_form',
        name='new_series_form'),

    url(r'^repositories/(?P<repository_name>\w+)/(?P<series_name>\w+)/$',
        'repomgmt.views.package_list', name='packages_list'),
    url(r'^repositories/promote$',
        'repomgmt.views.promote_series', name='promote_series'),

    # Puppet
    url(r'^puppet/(?P<build_record_id>\w+)/$',
        'repomgmt.views.puppet_manifest'),

    # Front page
    url(r'^$', 'repomgmt.views.front_page'),
)
