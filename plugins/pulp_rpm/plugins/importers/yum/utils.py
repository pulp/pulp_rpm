import re
import sys
from cStringIO import StringIO
from collections import namedtuple
from urlparse import urljoin, urlparse, urlunparse

from pulp.common.compat import check_builtin


if sys.version_info < (2, 7):
    from xml.etree import ElementTree as ET
else:
    from xml.etree import cElementTree as ET


# required for converting an element to raw XML
STRIP_NS_RE = re.compile('{.*?}')
Namespace = namedtuple('Namespace', ['name', 'uri'])


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
    tree.write(io, encoding='utf-8')
    ret = io.getvalue()

    for namespace in namespaces_to_register:
        # in python 2.7, these show up only on the root element. in 2.6, these
        # show up on each element that uses the prefix.
        ret = re.sub(' *xmlns:%s="%s" *' % (namespace.name, namespace.uri), ' ', ret)
    return ret


@check_builtin(ET)
def register_namespace(prefix, uri):
    """
    Adapted from xml.etree.ElementTree.register_namespace as implemented
    in Python 2.7.

    This implementation makes no attempt to remove other namespaces. It appears
    that there is a race condition in the python 2.7 stdlib pure python
    implementation. For our purposes, we don't need to be concerned about
    unregistering a namespace or URI, so we can let them remain unless
    overwritten.

    :param prefix:  namespace prefix
    :param uri:     namespace URI. Tags and attributes in this namespace will be
                    serialized with the given prefix, if at all possible.
    """
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


class RepoURLModifier(object):
    """
    Repository URL Modifier

    :ivar conf: URL modifier persistent configuration
    :type conf: dict

    """
    def __init__(self, path_append=None, ensure_trailing_slash=None, query_auth_token=None):
        """
        :ivar conf: URL modifier persistent configuration, populated from optional keyword
                    arguments (see :py:meth:`RepoURLModifier.__call__` for allowed options).
        :type conf: dict

        """
        self.conf = {
            'path_append': path_append,
            'ensure_trailing_slash': ensure_trailing_slash,
            'query_auth_token': query_auth_token,
        }

    def __call__(self, url, **kwargs):
        """
        Modify a URL based on the keys in the url modify conf

        :param url:         URL to modify
        :type:              str

        :return:     The modified URL
        :rtype:      str

        URL modification config keys, which can be overridden with optional keyword args,
        and will be processed in order as described here:

            * path_append: If found, will be appended to the URL path component
            * ensure_trailing_slash: If found and evaluates as true, add a
              trailing slash (if needed) to the URL path component
            * query_auth_token: If found, will become or replace the URLs
              query string, used for authenticating to repositories like SLES 12
              (and higher), which use this mechanism

        """
        modify_conf = self.conf.copy()
        # validate the kwargs against modify_conf keys to keep things DRY but still valid
        for key in kwargs:
            if key not in modify_conf:
                msg = ('Unknown URL modification configuration key: "{0}", '
                       'key must be one of {1}').format(key, ', '.join(modify_conf.keys()))
                raise LookupError(msg)
            modify_conf[key] = kwargs[key]

        scheme, netloc, path, params, query, fragment = urlparse(url)

        if modify_conf['path_append']:
            if not path.endswith('/'):
                path += '/'
            path = urljoin(path, modify_conf['path_append'])

        if modify_conf['ensure_trailing_slash']:
            if not path.endswith('/'):
                path += '/'

        if modify_conf['query_auth_token']:
            query = modify_conf['query_auth_token']

        url = urlunparse(
            (scheme, netloc, path, params, query, fragment)
        )
        return url
