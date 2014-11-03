import os

from yum.plugins import TYPE_CORE
from rhsm.profile import get_profile
from pulp.bindings.server import PulpConnection
from pulp.bindings.bindings import Bindings
from pulp.common.bundle import Bundle as BundleImpl
from pulp.client.consumer.config import read_config


requires_api_version = '2.5'
plugin_type = (TYPE_CORE,)
cfg = read_config()

#
# Pulp Integration
#

class Bundle(BundleImpl):
    """
    Consumer certificate (bundle)
    """

    def __init__(self):
        path = os.path.join(
            cfg['filesystem']['id_cert_dir'],
            cfg['filesystem']['id_cert_filename'])
        BundleImpl.__init__(self, path)


class PulpBindings(Bindings):
    """
    Pulp (REST) API.
    """

    def __init__(self):
        host = cfg['server']['host']
        port = int(cfg['server']['port'])
        cert = os.path.join(
            cfg['filesystem']['id_cert_dir'],
            cfg['filesystem']['id_cert_filename'])
        ssl = cfg.parse_bool(cfg['server']['verify_ssl'])
        connection = PulpConnection(host, port, cert_filename=cert, verify_ssl=ssl)
        Bindings.__init__(self, connection)

#
# yum plugin
#

def posttrans_hook(conduit):
    """
    Send content unit profile to Pulp.
    """
    try:
        bundle = Bundle()
        myid = bundle.cn()
        if not myid:
            return # not registered
        bindings = PulpBindings()
        profile = get_profile('rpm').collect()
        http = bindings.profile.send(myid, 'rpm', profile)
        msg = 'pulp: profile sent, status=%d' % http.response_code
        conduit.info(2, msg)
    except Exception, e:
        conduit.error(2, str(e))
