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
from django.contrib.auth.models import User
from django.core.serializers import json
from django.db import models
from django.utils import simplejson
from tastypie import fields
from tastypie.api import Api
from tastypie.authentication import BasicAuthentication, ApiKeyAuthentication
from tastypie.authorization import DjangoAuthorization
from tastypie.http import HttpUnauthorized
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
                if isinstance(check, HttpUnauthorized):
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


class ArchitectureResource(ModelResource):
    class Meta:
        queryset = Architecture.objects.all()
        resource_name = 'architecture'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthentication())
        authorization = DjangoAuthorization()
        serializer = PrettyJSONSerializer()


class RepositoryResource(ModelResource):
    series = fields.ToManyField("repomgmt.api.SeriesResource", 'series_set',
                                related_name='repository')

    class Meta:
        queryset = Repository.objects.all()
        resource_name = 'repository'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthentication())
        authorization = DjangoAuthorization()
        serializer = PrettyJSONSerializer()


class SeriesResource(ModelResource):
    repository = fields.ForeignKey(RepositoryResource, 'repository')

    class Meta:
        queryset = Series.objects.all()
        resource_name = 'series'
        authentication = MultiAuthentication(BasicAuthentication(),
                                             ApiKeyAuthentication())
        authorization = DjangoAuthorization()
        serializer = PrettyJSONSerializer()

    def dehydrate_state(self, bundle):
        return bundle.obj.get_state_display()

api.register(ArchitectureResource())
api.register(RepositoryResource())
api.register(SeriesResource())

models.signals.post_save.connect(create_api_key, sender=User)
