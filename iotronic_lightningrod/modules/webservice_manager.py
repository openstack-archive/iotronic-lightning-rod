# Copyright 2017 MDSLAB - University of Messina
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

__author__ = "Nicola Peditto <n.peditto@gmail.com>"

from iotronic_lightningrod.modules import Module

from oslo_config import cfg
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

CONF = cfg.CONF

import importlib as imp
import inspect
import json
import os

from iotronic_lightningrod.config import package_path
from iotronic_lightningrod.lightningrod import RPC_proxies
from iotronic_lightningrod.lightningrod import SESSION
from iotronic_lightningrod.modules import utils
import iotronic_lightningrod.wampmessage as WM


class WebServiceManager(Module.Module):

    def __init__(self, board, session):
        super(WebServiceManager, self).__init__("WebServiceManager", board)

        LOG.info(" - Proxy used: " + CONF.proxy.upper())

        proxy_type = CONF.proxy
        path = package_path + "/proxies/" + proxy_type + ".py"

        if os.path.exists(path):

            proxy_module = imp.import_module("iotronic_lightningrod.proxies."
                                             + proxy_type)
            LOG.info(" --> " + proxy_type.upper() + " module imported!")

            proxy = proxy_module.ProxyManager()

            proxy_meth_list = inspect.getmembers(
                proxy,
                predicate=inspect.ismethod
            )

            RPC_proxies[proxy_type] = proxy_meth_list

            board.proxy = proxy

            self._proxyWampRegister(proxy_meth_list, board)

        else:
            LOG.warning("Proxy '" + proxy_type + "' not supported!")

    def finalize(self):

        proxy_status = json.loads(self.board.proxy._proxyInfo())
        LOG.info("--> Proxy " + self.board.proxy.type.upper()
                 + " status:\n Active: " + str(proxy_status['status'])
                 + "\n Info: " + str(proxy_status['log']))

        LOG.info("Webservice exposed on device:")
        active_webservice_list = self.board.proxy._webserviceList()
        if len(active_webservice_list) != 0:
            for ws in active_webservice_list:
                LOG.info("-> " + ws)
        else:
            LOG.info("-> NO WebService!")

        LOG.info("WebService Manager initialized!")

    def restore(self):
        LOG.info("WebService Manager restored.")

    def _proxyWampRegister(self, proxy_meth_list, board):

        LOG.info(" - " + str(board.proxy.type).upper()
                 + " proxy registering RPCs:")

        for meth in proxy_meth_list:
            if (meth[0] != "__init__") & (meth[0] != "finalize") \
                    & (meth[0] != "restore"):
                # LOG.info(" - " + str(meth[0]))
                rpc_addr = u'iotronic.' + board.uuid + '.' + meth[0]
                # LOG.debug(" --> " + str(rpc_addr))
                if not meth[0].startswith('_'):
                    SESSION.register(meth[1], rpc_addr)
                    LOG.info("   --> " + str(meth[0]))

    async def ExposeWebservice(self, service_name, local_port):

        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        response = self.board.proxy._exposeWebservice(service_name, local_port)

        response = json.loads(response)

        if(response['result'] == "SUCCESS"):
            message = "Webservice '" + service_name + "' successfully exposed!"
            LOG.info("--> " + str(message))
            w_msg = WM.WampSuccess(response)
        else:
            message = "Error exposing webservice '" + service_name + "'"
            LOG.warning("--> " + str(response['message']))
            w_msg = WM.WampWarning(response)

        return w_msg.serialize()

    async def UnexposeWebservice(self, service_name):

        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        response = self.board.proxy._disableWebservice(service_name)

        response = json.loads(response)

        if (response['result'] == "SUCCESS"):
            LOG.info("--> " + str(response['message']))
            w_msg = WM.WampSuccess(response)
        else:
            LOG.warning("--> " + str(response['message']))
            w_msg = WM.WampWarning(response)

        return w_msg.serialize()

    async def BoardDnsCertsSetup(self, board_dns, owner_email):

        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        message = self.board.proxy._proxyBoardDnsSetup(board_dns, owner_email)
        w_msg = WM.WampSuccess(message)

        return w_msg.serialize()
