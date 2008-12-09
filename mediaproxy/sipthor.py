# Copyright (C) 2008 AG Projects
# Author: Ruud Klaver <ruud@ag-projects.com>
#

"""SIP Thor backend"""

from application import log
from application.configuration import *
from application.system import default_host_ip
from application.process import process

from gnutls.constants import *

from thor.entities import ThorEntities, GenericThorEntity
from thor.eventservice import EventServiceClient, ThorEvent
from thor.tls import X509Credentials

from mediaproxy.relay import SRVMediaRelayBase
from mediaproxy import configuration_filename, default_dispatcher_port, __version__


class SIPThorDomain(str):
    """A SIP Thor domain name or the keyword None"""
    def __new__(typ, name):
        if name.lower() == 'none':
            return None
        return name

class ThorNetworkConfig(ConfigSection):
    _datatypes = {'domain': SIPThorDomain}
    domain = None
    node_ip = default_host_ip

configuration = ConfigFile(configuration_filename)
configuration.read_settings("ThorNetwork", ThorNetworkConfig)

if ThorNetworkConfig.domain is None:
    ## SIP Thor is installed but disabled. Fake an ImportError to start in standalone media relay mode.
    log.warn("SIP Thor is installed but disabled from the configuration")
    raise ImportError("SIP Thor is disabled")


class SIPThorMediaRelayBase(EventServiceClient, SRVMediaRelayBase):
    topics = ["Thor.Members"]

    def __init__(self):
        self.node = GenericThorEntity(ThorNetworkConfig.node_ip, ["media_relay"], version=__version__)
        self.presence_message = ThorEvent('Thor.Presence', self.node.id)
        self.shutdown_message = ThorEvent('Thor.Leave', self.node.id)
        credentials = X509Credentials(cert_name='relay')
        credentials.session_params.compressions = (COMP_LZO, COMP_DEFLATE, COMP_NULL)
        self.sipthor_dispatchers = []
        self.additional_dispatchers = []
        EventServiceClient.__init__(self, ThorNetworkConfig.domain, credentials)
        SRVMediaRelayBase.__init__(self)

    def handle_event(self, event):
        sip_proxy_ips = [node.ip for node in ThorEntities(event.message, role="sip_proxy")]
        self.sipthor_dispatchers = [(ip, default_dispatcher_port) for ip in sip_proxy_ips]
        if not self.shutting_down:
            self.update_dispatchers(self.sipthor_dispatchers + self.additional_dispatchers)

    def _do_update(self, dispatchers):
        self.additional_dispatchers = dispatchers
        if not self.shutting_down:
            self.update_dispatchers(self.sipthor_dispatchers + self.additional_dispatchers)

    def update_dispatchers(self, dispatchers):
        raise NotImplementedError()

    def _handle_SIGHUP(self, *args):
        SRVMediaRelayBase._handle_SIGHUP(self, *args)

    def _handle_SIGINT(self, *args):
        SRVMediaRelayBase._handle_SIGINT(self, *args)

    def _handle_SIGTERM(self, *args):
        SRVMediaRelayBase._handle_SIGTERM(self, *args)

    def shutdown(self, kill_sessions):
        raise NotImplementedError()

