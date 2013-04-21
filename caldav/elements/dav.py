#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from caldav.lib.namespace import ns
from base import BaseElement, NamedBaseElement, ValuedBaseElement


## Operations
class Propfind(BaseElement):
    tag = ns("D", "propfind")


class PropertyUpdate(BaseElement):
    tag = ns("D", "propertyupdate")


class Mkcol(BaseElement):
    tag = ns("D", "mkcol")

## Filters

## Conditions

## Components / Data


class Prop(BaseElement):
    tag = ns("D", "prop")


class Collection(BaseElement):
    tag = ns("D", "collection")


class Set(BaseElement):
    tag = ns("D", "set")


## Properties
class ResourceType(BaseElement):
    tag = ns("D", "resourcetype")


class DisplayName(ValuedBaseElement):
    tag = ns("D", "displayname")


class Href(BaseElement):
    tag = ns("D", "href")


class Response(BaseElement):
    tag = ns("D", "response")


class Status(BaseElement):
    tag = ns("D", "status")
