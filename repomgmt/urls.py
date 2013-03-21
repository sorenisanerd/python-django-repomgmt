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
    url(r'^builders/(?P<builder_name>\S+)/$', 'repomgmt.views.builder_detail',
        name='builder_detail'),
    url(r'^builders/$', 'repomgmt.views.builder_list', name='builder_list'),

    # Builds
    url(r'^builds/(?P<build_id>\w+)/$', 'repomgmt.views.build_detail',
        name='build_detail'),
    url(r'^builds/$', 'repomgmt.views.build_list', name='build_list'),

    # Package Sources
    url(r'^packagesources/$', 'repomgmt.views.pkg_sources_list',
                              name='pkg_sources_list'),
    url(r'^packagesources/new/$', 'repomgmt.views.new_pkg_source_form',
                              name='new_pkg_source_form'),
    url(r'^packagesourcebuildproblems/(?P<problem_id>\w+)/$', 'repomgmt.views.problem_detail',
                              name='pkg_src_build_problem_detail'),

    # Subscriptions
    url(r'^subscriptions/(?P<subscription_id>\d+)/$',
        'repomgmt.views.subscription_detail', name='subscription_detail'),

    url(r'^subscriptions/(?P<subscription_id>\d+)/edit/$',
        'repomgmt.views.subscription_edit', name='subscription_edit'),


    # Architectures
    url(r'^architectures/$', 'repomgmt.views.architecture_list',
                              name='architecture_list'),
    url(r'^architectures/new/$', 'repomgmt.views.new_architecture_form',
                                 name='new_architecture_form'),

    # Tarballs
    url(r'^tarballs/$', 'repomgmt.views.tarball_list', name='tarball_list'),

    # Repositories
    url(r'^repositories/$', 'repomgmt.views.repository_list',
        name='repository_list'),
    url(r'^repositories/new/$', 'repomgmt.views.new_repository_form',
        name='new_repository_form'),

    url(r'^repositories/(?P<repository_name>\S+)/key/$',
        'repomgmt.views.repository_public_key', name='repository_public_key'),
    url(r'^repositories/(?P<repository_name>[^/]+)/$',
        'repomgmt.views.series_list', name='series_list'),
    url(r'^repositories/(?P<repository_name>[^/]+)/new/$', 'repomgmt.views.new_series_form',
        name='new_series_form'),

    url(r'^repositories/(?P<repository_name>\S+)/(?P<series_name>\S+)/$',
        'repomgmt.views.package_list', name='packages_list'),
    url(r'^repositories/promote$',
        'repomgmt.views.promote_series', name='promote_series'),

    # docs
    url(r'^docs/api/$', 'repomgmt.views.docs_api', name='docs_api'),
    url(r'^docs/workflow/$', 'repomgmt.views.docs_workflow', name='docs_workflow'),

    # Puppet
    url(r'^puppet/(?P<build_record_id>\w+)/$',
        'repomgmt.views.puppet_manifest'),

    # User page
    url(r'^users/me/$', 'repomgmt.views.redirect_to_self', name='this_user'),
    url(r'^users/(?P<username>\w+)/$', 'repomgmt.views.user_details'),

    # Front page
    url(r'^$', 'repomgmt.views.front_page'),
)
