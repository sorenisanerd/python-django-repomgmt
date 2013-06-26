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
from django.conf.urls import url
from django.contrib.auth.models import User
from django.core.serializers import json
from django.db import models
from django.utils import simplejson
from tastypie import fields, http
from tastypie.api import Api
from tastypie.authentication import BasicAuthentication, ApiKeyAuthentication
from tastypie.authorization import DjangoAuthorization
from tastypie.bundle import Bundle
from tastypie.constants import ALL_WITH_RELATIONS
from tastypie.models import create_api_key
from tastypie.resources import ModelResource
from repomgmt.models import Architecture, Repository, PackageSource, Series
from repomgmt.models import Subscription, UbuntuSeries
from tastypie.serializers import Serializer
from tastypie.exceptions import Unauthorized

api = Api(api_name='v1')


class PrettyJSONSerializer(Serializer):
    json_indent = 2

    def to_json(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        return json.json.dumps(data, cls=json.DjangoJSONEncoder, sort_keys=True,
                               ensure_ascii=False, indent=self.json_indent)


# Copied from up-to-date tastypie
class MultiAuthentication(object):
    """
    An authentication backend that tries a number of backends in order.
    """
    def __init__(self, *backends, **kwargs):
        super(MultiAuthentication, self).__init__(**kwargs)
        self.backends = backends

    def is_authenticated(self, request, **kwargs):
        """
        Identifies if the user is authenticated to continue or not.

        Should return either ``True`` if allowed, ``False`` if not or an
        ``HttpResponse`` if you need something custom.
        """
        unauthorized = False

        for backend in self.backends:
            check = backend.is_authenticated(request, **kwargs)

            if check:
                if isinstance(check, http.HttpUnauthorized):
                    unauthorized = unauthorized or check
                else:
                    request._authentication_backend = backend
                    return check

        return unauthorized

    def get_identifier(self, request):
        """
        Provides a unique string identifier for the requestor.

        This implementation returns a combination of IP address and hostname.
        """
        try:
            return request._authentication_backend.get_identifier(request)
        except AttributeError:
            return 'nouser'


class DjangoAuthorizationWithObjLevelPermissions(DjangoAuthorization):
    def create_detail(self, object_list, bundle):
        klass = self.base_checks(bundle.request, bundle.obj.__class__)

        if klass is False:
            raise Unauthorized("You are not allowed to access that resource.")

        permission = '%s.add_%s' % (klass._meta.app_label, klass._meta.module_name)

        if not bundle.request.user.has_perm(permission, bundle.obj):
            raise Unauthorized("You are not allowed to access that resource.")

        return True

    def update_list(self, object_list, bundle):
        klass = self.base_checks(bundle.request, object_list.model)

        if klass is False:
            return []

        permission = '%s.change_%s' % (klass._meta.app_label, klass._meta.module_name)
        if not all(bundle.request.user.has_perm(permission, obj) for obj in object_list):
            return []

        return object_list

    def update_detail(self, object_list, bundle):
        klass = self.base_checks(bundle.request, bundle.obj.__class__)

        if klass is False:
            raise Unauthorized("You are not allowed to access that resource.")

        permission = '%s.change_%s' % (klass._meta.app_label, klass._meta.module_name)

        if not bundle.request.user.has_perm(permission, bundle.obj):
            raise Unauthorized("You are not allowed to access that resource.")

        return True

    def delete_list(self, object_list, bundle):
        klass = self.base_checks(bundle.request, object_list.model)

        if klass is False:
            return []

        permission = '%s.delete_%s' % (klass._meta.app_label, klass._meta.module_name)

        if not all(bundle.request.user.has_perm(permission, obj) for obj in object_list):
            return []

        return object_list

    def delete_detail(self, object_list, bundle):
        klass = self.base_checks(bundle.request, bundle.obj.__class__)

        if klass is False:
            raise Unauthorized("You are not allowed to access that resource.")

        permission = '%s.delete_%s' % (klass._meta.app_label, klass._meta.module_name)

        if not bundle.request.user.has_perm(permission, bundle.obj):
            raise Unauthorized("You are not allowed to access that resource.")

        return True

    def _create_detail(self, object_list, bundle):
        cls = self.base_checks(bundle.request, bundle.obj.__class__)
        if hasattr(cls, 'allow_unprivileged_creation'):
            return cls.allow_unprivileged_creation()
        return super(DjangoAuthorizationWithObjLevelPermissions, self).create_detail(object_list, bundle)


class ApiKeyAuthenticationWithHeaderSupport(ApiKeyAuthentication):
    def extract_credentials(self, request):
        if request.META.get('HTTP_AUTHORIZATION') and request.META['HTTP_AUTHORIZATION'].lower().startswith('apikey '):
            (auth_type, data) = request.META['HTTP_AUTHORIZATION'].split()

            if auth_type.lower() != 'apikey':
                raise ValueError("Incorrect authorization header.")

            username, api_key = data.split(':', 1)
        else:
            username = request.GET.get('username') or request.POST.get('username')
            api_key = request.GET.get('api_key') or request.POST.get('api_key')

        return username, api_key

    def is_authenticated(self, request, **kwargs):
        """
        Finds the user and checks their API key.

        Should return either ``True`` if allowed, ``False`` if not or an
        ``HttpResponse`` if you need something custom.
        """
        try:
            username, api_key = self.extract_credentials(request)
        except ValueError:
            return self._unauthorized()

        try:
            user = User.objects.get(username=username)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return self._unauthorized()

        request.user = user
        return self.get_key(user, api_key)


class ArchitectureResource(ModelResource):
    class Meta:
        queryset = Architecture.objects.all()
        resource_name = 'architecture'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthenticationWithHeaderSupport())
        authorization = DjangoAuthorizationWithObjLevelPermissions()
        serializer = PrettyJSONSerializer()


class PackageSourceResource(ModelResource):
    class Meta:
        queryset = PackageSource.objects.all()
        resource_name = 'packagesource'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthenticationWithHeaderSupport())
        authorization = DjangoAuthorizationWithObjLevelPermissions()
        serializer = PrettyJSONSerializer()
        filtering = {'id': ALL_WITH_RELATIONS}


class RepositoryResource(ModelResource):
    series = fields.ToManyField("repomgmt.api.SeriesResource", 'series_set',
                                related_name='repository', null=True)

    class Meta:
        queryset = Repository.objects.all()
        resource_name = 'repository'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthenticationWithHeaderSupport())
        authorization = DjangoAuthorizationWithObjLevelPermissions()
        serializer = PrettyJSONSerializer()
        filtering = {'name': ALL_WITH_RELATIONS}

    def hydrate_m2m(self, bundle):
        bundle.obj.uploaders.add(bundle.request.user)
        return super(RepositoryResource, self).hydrate_m2m(bundle)

class HttpAccepted(http.HttpResponse):
    status_code = 202


class SeriesResource(ModelResource):
    repository = fields.ForeignKey(RepositoryResource, 'repository')
    base_ubuntu_series = fields.CharField()
    based_on = fields.ForeignKey('repomgmt.api.SeriesResource', 'update_from', null=True)
    subscriptions = fields.ToManyField("repomgmt.api.SubscriptionResource", 'subscription_set')


    class Meta:
        queryset = Series.objects.all()
        resource_name = 'series'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthenticationWithHeaderSupport())
        authorization = DjangoAuthorizationWithObjLevelPermissions()
        serializer = PrettyJSONSerializer()
        filtering = {'repository': ALL_WITH_RELATIONS,
                     'name': ALL_WITH_RELATIONS,
                     'id': ALL_WITH_RELATIONS}


    @classmethod
    def api_field_from_django_field(cls, f, default=fields.CharField):
        result = default
        
        if f.name == 'state':
            return fields.CharField
        elif f.get_internal_type() in ('DateField', 'DateTimeField'):
            result = fields.DateTimeField
        elif f.get_internal_type() in ('BooleanField', 'NullBooleanField'):
            result = fields.BooleanField
        elif f.get_internal_type() in ('DecimalField', 'FloatField'):
            result = fields.FloatField
        elif f.get_internal_type() in ('IntegerField', 'PositiveIntegerField', 'PositiveSmallIntegerField', 'SmallIntegerField'):
            result = fields.IntegerField
        elif f.get_internal_type() in ('FileField', 'ImageField'):
            result = fields.FileField
        return result

    def post_detail(self, request, **kwargs):
        deserialized = self.deserialize(request, request.raw_post_data,
                                        format=request.META.get('CONTENT_TYPE', 'application/json'))
        deserialized = self.alter_deserialized_detail_data(request,
                                                           deserialized)

        basic_bundle = self.build_bundle(request=request)
        obj = self.cached_obj_get(bundle=basic_bundle, **self.remove_api_resource_names(kwargs))
        if deserialized.get('action', None) == 'promote':
            obj.promote()
            return HttpAccepted()
        return http.HttpBadRequest()

    def __get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_list'):
        if bundle_or_obj is None:
            return super(SeriesResource, self).get_resource_uri(bundle_or_obj, url_name)

        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        else:
            obj = bundle_or_obj

        kwargs = {
            'resource_name': self._meta.resource_name,
            'repository__name': obj.repository.name,
            'name': obj.name
        }

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name

        return self._build_reverse_url("api_dispatch_detail",
                                       kwargs=kwargs)

    def __override_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<repository__name>[\w\d_.-]+)/(?P<name>[\w\d_.-]+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
            ]

    def hydrate_base_ubuntu_series(self, bundle):
        bundle.obj.base_ubuntu_series = UbuntuSeries.objects.filter(name__iendswith=bundle.data['base_ubuntu_series'])[0]
        return bundle

    def dehydrate_base_ubuntu_series(self, bundle):
        return bundle.obj.base_ubuntu_series.name

    def hydrate_state(self, bundle):
        try:
            state_id = int(bundle.data['state'])
            bundle.data['state'] = state_id
        except ValueError:
            for state_id, state_name in Series.SERIES_STATES:
                if bundle.data['state'] == state_name:
                    bundle.data['state'] = state_id
                    break

        return bundle

    def dehydrate_state(self, bundle):
        return bundle.obj.get_state_display()

class SubscriptionResource(ModelResource):
    package_source = fields.ToOneField(PackageSourceResource, 'source')
    destination_series = fields.ForeignKey(SeriesResource, 'target_series')

    class Meta:
        queryset = Subscription.objects.all()
        resource_name = 'subscription'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthenticationWithHeaderSupport())
        authorization = DjangoAuthorizationWithObjLevelPermissions()
        serializer = PrettyJSONSerializer()
        filtering = {'destination_series': ALL_WITH_RELATIONS,
                     'package_source': ALL_WITH_RELATIONS,
                     'id': ALL_WITH_RELATIONS}


api.register(ArchitectureResource())
api.register(RepositoryResource())
api.register(SeriesResource())
api.register(SubscriptionResource())
api.register(PackageSourceResource())

models.signals.post_save.connect(create_api_key, sender=User)
