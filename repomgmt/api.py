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
from tastypie.models import create_api_key
from tastypie.resources import ModelResource
from repomgmt.models import Architecture, Repository, Series
from tastypie.serializers import Serializer

api = Api(api_name='v1')


class PrettyJSONSerializer(Serializer):
    json_indent = 2

    def to_json(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        return simplejson.dumps(data, cls=json.DjangoJSONEncoder,
                sort_keys=True, ensure_ascii=False, indent=self.json_indent)


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
        from django.contrib.auth.models import User
        
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
        authorization = DjangoAuthorization()
        serializer = PrettyJSONSerializer()


class RepositoryResource(ModelResource):
    series = fields.ToManyField("repomgmt.api.SeriesResource", 'series_set',
                                related_name='repository')

    class Meta:
        queryset = Repository.objects.all()
        resource_name = 'repository'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthenticationWithHeaderSupport())
        authorization = DjangoAuthorization()
        serializer = PrettyJSONSerializer()


class HttpAccepted(http.HttpResponse):
    status_code = 202


class SeriesResource(ModelResource):
    repository = fields.ForeignKey(RepositoryResource, 'repository')

    class Meta:
        queryset = Series.objects.all()
        resource_name = 'series'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthenticationWithHeaderSupport())
        authorization = DjangoAuthorization()
        serializer = PrettyJSONSerializer()

    def post_detail(self, request, **kwargs):
        deserialized = self.deserialize(request, request.raw_post_data, format=request.META.get('CONTENT_TYPE', 'application/json'))
        deserialized = self.alter_deserialized_detail_data(request, deserialized)
        obj = self.obj_get(request)
        if deserialized.get('action', None) == 'promote':
            obj.promote()
            return HttpAccepted()
        return http.HttpBadRequest()

    def get_resource_uri(self, bundle_or_obj):
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

    def override_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<repository__name>[\w\d_.-]+)/(?P<name>[\w\d_.-]+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
            ]

    def dehydrate_state(self, bundle):
        return bundle.obj.get_state_display()

api.register(ArchitectureResource())
api.register(RepositoryResource())
api.register(SeriesResource())

models.signals.post_save.connect(create_api_key, sender=User)
