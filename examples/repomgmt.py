#!/usr/bin/python
#
#   Copyright 2013 Cisco Systems, Inc.
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
import argparse
import os
from queryset_client import Client
import prettytable
import sys


def list_dict(objs, field_headers, field_names):
    pt = prettytable.PrettyTable(field_headers, caching=False)
    for f in field_headers:
        pt.align[f] = 'l'
    for obj in objs:
        pt.add_row([obj.get(f, '') for f in field_names])
    print pt

def list_objs(objs, field_headers, field_names):
    pt = prettytable.PrettyTable(field_headers, caching=False)
    for f in field_headers:
        pt.align[f] = 'l'
    for obj in objs:
        pt.add_row([getattr(obj, f, '') for f in field_names])
    print pt


package_source_cache = {}
series_cache = {}
repository_cache = {}


def get_package_source(client, uri):
    if not uri in package_source_cache:
        package_source_cache[uri] = client.packagesource.objects.get(id=uri.split('/')[-2])
    return package_source_cache[uri]


def get_series(client, uri):
    if not uri in series_cache:
        series_cache[uri] = client.series.objects.get(id=uri.split('/')[-2])
    return series_cache[uri]


def get_repository(client, uri):
    if not uri in repository_cache:
        repository_cache[uri] = client.repository.objects.get(id=uri.split('/')[-2])
    return repository_cache[uri]


def subscription_to_series(client, subscription):
    return get_series(client, subscription._response['destination_series'])


def subscription_to_package_source(client, subscription):
    return get_package_source(client, subscription._response['package_source'])


def series_str(series):
    return '%s - %s' % (series.repository.name, series.name)


def get_client(args, strict=True):
    return Client(args.url, auth=(args.username, args.password), strict_field=strict)


def repository_list(args):
    client = get_client(args)
    obj_type = client.repository
    list_objs(obj_type.objects.all(), ['Name'], ['name'])

def series_list(args):
    client = get_client(args)
    obj_type = client.series
    objs = list(obj_type.objects.filter(repository__name=args.repository))
    objs.sort(key=lambda x:'%s-%s' % (x.repository, x.name))
    objs = [{'Repository': obj.repository.name,
                 'Name': obj.name} for obj in objs]

    list_dict(objs, ['Repository', 'Name'], ['Repository', 'Name'])

def packagesource_list(args):
    client = get_client(args)
    obj_type = client.packagesource
    objs = obj_type.objects.all()
    list_objs(objs, ['Id', 'Name', 'Code URL', 'Packaging URL', 'Flavor'],
                    ['id', 'name', 'code_url', 'packaging_url', 'flavor'])


def packagesource_create(args):
    client = get_client(args)
    obj_type = client.packagesource
    obj = obj_type(name=args.name, code_url=args.code_url,
                   packaging_url=args.packaging_url, flavor=args.flavor)
    obj.save()


def packagesource_rebuild(args):
    client = get_client(args, strict=False)
    obj_type = client.packagesource
    obj = obj_type.objects.get(id=args.id)
    obj.last_seen_pkg_rev = ''
    obj.save()


def packagesource_delete(args):
    client = get_client(args)
    obj_type = client.packagesource
    objs = obj_type.objects.filter(id=args.id)
    list_objs(objs, ['Id', 'Name', 'Code URL', 'Packaging URL', 'Flavor'],
                    ['id', 'name', 'code_url', 'packaging_url', 'flavor'])
    objs[0].delete()


def subscription_replace(args):
    client = get_client(args)
    obj_type = client.subscription
    obj = obj_type.objects.get(id=args.subscription)
    orig_source = subscription_to_package_source(client, obj)
    new_source = client.packagesource.objects.get(id=args.source)
    obj.model.package_source = new_source.resource_uri
    obj.save()
    print 'Replaced %r with %r in %r' % (orig_source.name, new_source.name, series_str(subscription_to_series(client, obj)))


def subscription_delete(args):
    client = get_client(args)
    obj_type = client.subscription
    obj = obj_type.objects.get(id=args.id)
    obj.delete()


def subscription_create(args):
    client = get_client(args)
    obj_type = client.subscription
    series = client.series.objects.get(name=args.series, repository__name=args.repository)
    source = client.packagesource.objects.get(id=args.source)
    subscription = obj_type(counter=1, destination_series=series, package_source=source)
    subscription.save()
    return True


def subscription_list(args):
    client = get_client(args)
    obj_type = client.subscription
    kwargs = {}
    if args.repository:
        kwargs['destination_series__repository__name'] = args.repository
    if args.series:
        kwargs['destination_series__name'] = args.series

    objs = list(obj_type.objects.filter(**kwargs))
    objs = [{'Id': obj.id,
             'Package Source': subscription_to_package_source(client, obj).name,
             'Destination Series': series_str(subscription_to_series(client, obj)),
             'Counter': obj.counter} for obj in objs]
    list_dict(objs, ['Id', 'Package Source', 'Destination Series', 'Counter'],
                    ['Id', 'Package Source', 'Destination Series', 'Counter'])


def main(argv=sys.argv):
    parser = argparse.ArgumentParser(description='Interact with repomgmt system')
    parser.add_argument('--username', action='store',
                        default=os.environ.get('REPOMGMT_USERNAME'),
                        help='Your username on the repomgmt system')
    parser.add_argument('--password', action='store',
                        default=os.environ.get('REPOMGMT_PASSWORD'),
                        help='Your password on the repomgmt system')
    parser.add_argument('--url', dest='url', action='store',
                        default='http://apt.ctocllab.cisco.com/api/v1/',
                        help='The URL of the repomgmt system')
    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands')

    repo_list_parser = subparsers.add_parser('repository-list', description='List repositories')
    repo_list_parser.set_defaults(func=repository_list)

    series_list_parser = subparsers.add_parser('series-list', description='List series')
    series_list_parser.add_argument('repository', nargs='?', help='Only show series belonging to this repository')
    series_list_parser.set_defaults(func=series_list)

    package_source_list_parser = subparsers.add_parser('packagesource-list', description='List package sources')
    package_source_list_parser.set_defaults(func=packagesource_list)

    package_source_create_parser = subparsers.add_parser('packagesource-create', description='Create package source')
    package_source_create_parser.add_argument('name', help='Name of this package source')
    package_source_create_parser.add_argument('code_url', help='URL to code (If a git url, you must include a branch name by appending \'#branchname\')')
    package_source_create_parser.add_argument('packaging_url', help='URL for the packaging code (same syntx as code_url)')
    package_source_create_parser.add_argument('flavor', help='Flavor (options are "Puppet", "OpenStack", and "Native")')
    package_source_create_parser.set_defaults(func=packagesource_create)

    package_source_delete_parser = subparsers.add_parser('packagesource-delete', description='Delete package source')
    package_source_delete_parser.add_argument('id', help='id of the package source to be deleted')
    package_source_delete_parser.set_defaults(func=packagesource_delete)

    package_source_rebuild_parser = subparsers.add_parser('packagesource-rebuild', description='Trigger rebuild of package source')
    package_source_rebuild_parser.add_argument('id', help='id of the package source to trigger a rebuild of')
    package_source_rebuild_parser.set_defaults(func=packagesource_rebuild)

    subscription_create_parser = subparsers.add_parser('subscription-create', description='Create subscription')
    subscription_create_parser.add_argument('repository', help='Repository name')
    subscription_create_parser.add_argument('series', help='Series name')
    subscription_create_parser.add_argument('source', help='Package source ID')
    subscription_create_parser.set_defaults(func=subscription_create)

    subscription_delete_parser = subparsers.add_parser('subscription-delete', description='Delete subscription')
    subscription_delete_parser.add_argument('id', help='id of the subscription to delete')
    subscription_delete_parser.set_defaults(func=subscription_delete)

    subscription_list_parser = subparsers.add_parser('subscription-list', description='List subscriptions')
    subscription_list_parser.add_argument('repository', nargs='?', help='If given, only show subscriptions in this repository')
    subscription_list_parser.add_argument('series', nargs='?', help='If given, only show subscriptions in this series')
    subscription_list_parser.set_defaults(func=subscription_list)

    subscription_replace_parser = subparsers.add_parser('subscription-replace', description='Replace subscription')
    subscription_replace_parser.add_argument('subscription', help='id of the subscription')
    subscription_replace_parser.add_argument('source', help='id of the new package source')
    subscription_replace_parser.set_defaults(func=subscription_replace)

    args = parser.parse_args()
    args.func(args)
    return True


if __name__ == '__main__':
    sys.exit([1, 0][main()])

