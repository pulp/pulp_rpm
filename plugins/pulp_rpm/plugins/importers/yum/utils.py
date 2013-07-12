# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from cStringIO import StringIO
from collections import namedtuple
import itertools
import re
import sys

from pulp.common.compat import check_builtin

if sys.version_info < (2, 7):
    from xml.etree import ElementTree as ET
else:
    from xml.etree import cElementTree as ET


DEFAULT_PAGE_SIZE = 1000

# required for converting an element to raw XML
STRIP_NS_RE = re.compile('{.*?}')
Namespace = namedtuple('Namespace', ['name', 'uri'])


# TODO: probably should move this to pulp.common
def paginate(iterable, page_size=DEFAULT_PAGE_SIZE):
    """
    Takes any kind of iterable and chops it up into tuples of size "page_size".
    A generator is returned, so this can be an efficient way to chunk items from
    some other generator.

    :param iterable:    any iterable such as a list, tuple, or generator
    :type  iterable:    iterable
    :param page_size:   how many items should be in each returned tuple
    :type  page_size:   int

    :return:    generator of tuples, each including "page_size" number of items
                from "iterable", except the last tuple, which may contain
                fewer.
    :rtype:     generator
    """
    # this won't work properly if we give islice something that isn't a generator
    generator = (x for x in iterable)
    while True:
        page = tuple(itertools.islice(generator, 0, page_size))
        if not page:
            return
        yield page


def element_to_raw_xml(element, namespaces_to_register=None, default_namespace_uri=None):
    """
    Convert an Element to a raw XML block. Namespaces are preserved on element
    tags, but any namespace declaration on the root element will be removed.
    This function is intended to be used in a case where multiple XML string
    snippets will be concatenated into a valid XML document later. This function
    will not necessarily return a valid XML document.

    :param element:                 XML element that should be output as an XML string
    :type  element:                 xml.etree.ElementTree.Element
    :param namespaces_to_register:  collection of Namespace instances that should
                                    be registered while converting to a string.
                                    Any "xmlns" declarations for a prefix that
                                    appears in this collection will be removed.
    :type  namespaces_to_register:  list or tuple
    :param default_namespace_uri:   URI of the default namespace, if any. This
                                    will be stripped from the tag of the given
                                    element and any of its descendants.
    :type  default_namespace_uri:   basestring

    :return:    XML as a string
    :rtype:     str
    """
    namespaces_to_register = namespaces_to_register or tuple()
    for namespace in namespaces_to_register:
        if not isinstance(namespace, Namespace):
            raise TypeError('"namespaces" must be an iterable of Namespace instances')
        register_namespace(namespace.name, namespace.uri)

    if default_namespace_uri:
        strip_ns(element, default_namespace_uri)

    tree = ET.ElementTree(element)
    io = StringIO()
    tree.write(io)
    ret = io.getvalue()

    for namespace in namespaces_to_register:
        # clean up, since this is global
        register_namespace(namespace.name, '')
        # in python 2.7, these show up only on the root element. in 2.6, these
        # show up on each element that uses the prefix.
        ret = re.sub(' *xmlns:%s="%s" *' % (namespace.name, namespace.uri), ' ', ret)
    return ret


@check_builtin(ET)
def register_namespace(prefix, uri):
    """
    Adapted from xml.etree.ElementTree.register_namespace as implemented
    in Python 2.7.

    :param prefix:  namespace prefix
    :param uri:     namespace URI. Tags and attributes in this namespace will be
                    serialized with the given prefix, if at all possible.
    """
    for k, v in ET._namespace_map.items():
        if v == prefix:
            del ET._namespace_map[k]
    ET._namespace_map[uri] = prefix


def strip_ns(element, uri=None):
    """
    Given an Element object, recursively strip the namespace info from its tag
    and all of its children. If a URI is specified, only that URI will be removed
    from the tag.

    :param element: the element whose tag namespace should be modified
    :type  element: xml.etree.ElementTree.Element
    :param uri:     The URI of a namespace that should be stripped. If specified,
                    only this URI will be removed, and all others will be left
                    alone.
    :type  uri:     basestring
    """
    if uri is None:
        element.tag = re.sub(STRIP_NS_RE, '', element.tag)
    else:
        element.tag = element.tag.replace('{%s}' % uri, '')
    for child in list(element):
        strip_ns(child, uri)
