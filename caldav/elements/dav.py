#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from caldav.lib.namespace import ns

from .base import BaseElement
from .base import ValuedBaseElement


# Operations
class Propfind(BaseElement):
    tag = ns("D", "propfind")


class PropertyUpdate(BaseElement):
    tag = ns("D", "propertyupdate")


class Mkcol(BaseElement):
    tag = ns("D", "mkcol")


class SyncCollection(BaseElement):
    tag = ns("D", "sync-collection")


# Filters

# Conditions
class SyncToken(BaseElement):
    tag = ns("D", "sync-token")


class SyncLevel(BaseElement):
    tag = ns("D", "sync-level")


# Components / Data


class Prop(BaseElement):
    tag = ns("D", "prop")


class Collection(BaseElement):
    tag = ns("D", "collection")


class Set(BaseElement):
    tag = ns("D", "set")


# Properties
class ResourceType(BaseElement):
    tag = ns("D", "resourcetype")


class DisplayName(ValuedBaseElement):
    tag = ns("D", "displayname")


class GetEtag(ValuedBaseElement):
    tag = ns("D", "getetag")


class Href(BaseElement):
    tag = ns("D", "href")


class SupportedReportSet(BaseElement):
    tag = ns("D", "supported-report-set")


class Response(BaseElement):
    tag = ns("D", "response")


class Status(BaseElement):
    tag = ns("D", "status")


class PropStat(BaseElement):
    tag = ns("D", "propstat")


class MultiStatus(BaseElement):
    tag = ns("D", "multistatus")


class CurrentUserPrincipal(BaseElement):
    tag = ns("D", "current-user-principal")


class PrincipalCollectionSet(BaseElement):
    tag = ns("D", "principal-collection-set")


class Allprop(BaseElement):
    tag = ns("D", "allprop")
