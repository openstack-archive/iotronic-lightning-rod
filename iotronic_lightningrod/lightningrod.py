#    Copyright 2017 MDSLAB - University of Messina All Rights Reserved.
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

# Autobahn imports
from autobahn.asyncio.component import Component
from autobahn.wamp import exception

# OSLO imports
from oslo_config import cfg
from oslo_log import log as logging

# MODULES imports
import asyncio
import inspect
import os
import pkg_resources
import psutil
import signal
import ssl
from stevedore import extension
import sys
import txaio

from pip._vendor import pkg_resources

# IoTronic imports
from iotronic_lightningrod.Board import Board
from iotronic_lightningrod.common.exception import timeoutALIVE
from iotronic_lightningrod.common.exception import timeoutRPC
from iotronic_lightningrod.common import utils
from iotronic_lightningrod.common.utils import get_version
import iotronic_lightningrod.wampmessage as WM


# Global variables
LOG = logging.getLogger(__name__)


lr_opts = [
    cfg.StrOpt('lightningrod_home',
               default='/var/lib/iotronic',
               help=('Lightning-rod Home Data')),
    cfg.BoolOpt('skip_cert_verify',
                default=True,
                help=('Flag for skipping the verification of the server cert '
                      '(for the auto-signed ones)')),
    cfg.IntOpt('connection_timer',
               default=10,
               help=('IoTronic connection RPC timer')),
    cfg.IntOpt('alive_timer',
               default=600,
               help=('Wamp websocket check time')),
    cfg.IntOpt('rpc_alive_timer',
               default=3,
               help=('RPC alive response time threshold')),
]

CONF = cfg.CONF
CONF.register_opts(lr_opts)

SESSION = None
global board
board = None
reconnection = False
RPC = {}
RPC_devices = {}
RPC_proxies = {}
zombie_alert = True

# ASYNCIO
loop = None
component = None
txaio.start_logging(level="info")
RUNNER = None
connected = False

global MODULES
MODULES = {}


class LightningRod(object):

    def __init__(self):

        LogoLR()

        LOG.info(' - version: ' +
                 str(get_version("iotronic-lightningrod")))
        LOG.info(' - PID: ' + str(os.getpid()))

        LOG.info("LR available modules: ")
        for ep in pkg_resources.iter_entry_points(group='s4t.modules'):
            LOG.info(" - " + str(ep))

        logging.register_options(CONF)
        DOMAIN = "s4t-lightning-rod"
        CONF(project='iotronic')
        logging.setup(CONF, DOMAIN)

        if (utils.checkIotronicConf(CONF)):

            if CONF.debug:
                txaio.start_logging(level="debug")

            signal.signal(signal.SIGINT, self.stop_handler)

            LogoLR()

            LOG.info('Lightning-rod: ')
            LOG.info(' - version: ' +
                     str(get_version("iotronic-lightningrod")))
            LOG.info(' - PID: ' + str(os.getpid()))
            LOG.info(' - Logs: ' + CONF.log_file)
            LOG.info(" - Home: " + CONF.lightningrod_home)
            LOG.info(" - Alive Check timer: " + str(CONF.alive_timer) +
                     " seconds")
            LOG.info(" - RPC-Alive Check timer: " + str(CONF.rpc_alive_timer) +
                     " seconds")

            global board
            board = Board()

            self.w = WampManager(board.wamp_config)

            self.w.start()

        else:
            Bye()

    def stop_handler(self, signum, frame):

        try:
            # No zombie alert activation
            zombie_alert = False
            LOG.info("LR is shutting down...")
            self.w.stop()
            Bye()
        except Exception as e:
            LOG.error("Error closing LR")


class WampManager(object):
    """WAMP Manager: through this LR manages the connection to Crossbar server.

    """

    def __init__(self, wamp_conf):

        # wampConnect configures and manages the connection to Crossbar server.
        wampConnect(wamp_conf)

    def start(self):
        LOG.info(" - starting Lightning-rod WAMP server...")

        global loop
        loop = asyncio.get_event_loop()
        component.start(loop)
        loop.run_forever()

    def stop(self):
        LOG.info("Stopping WAMP agent server...")
        # Canceling pending tasks and stopping the loop
        asyncio.gather(*asyncio.Task.all_tasks()).cancel()
        LOG.info("WAMP server stopped!")


async def wamp_checks(session):

    while (True):

        try:

            # LOG.debug("ALIVE sending...")

            with timeoutALIVE(seconds=CONF.rpc_alive_timer, action="ws_alive"):
                res = await session.call(
                    str(board.agent) + u'.stack4things.wamp_alive',
                    board_uuid=board.uuid,
                    board_name=board.name
                )

            LOG.debug("WampCheck attempt " + str(res))

        except exception.ApplicationError as e:
            LOG.error(" - Iotronic Connection RPC error: " + str(e))
            # Iotronic is offline the board can not call
            # the "stack4things.alive" RPC.
            # The board will disconnect from WAMP agent and retry later.
            global reconnection
            reconnection = True
            utils.destroyWampSocket()

        try:
            await asyncio.sleep(CONF.alive_timer)
        except Exception as e:
            LOG.warning(" - asyncio alert: " + str(e))


async def IotronicLogin(board, session, details):
    """Function called to connect the board to Iotronic.

    The board:
     1. logs in to Iotronic
     2. loads the modules

    :param board:
    :param session:
    :param details:

    """

    LOG.info("IoTronic Authentication:")

    global reconnection

    try:

        rpc = str(board.agent) + u'.stack4things.connection'

        with timeoutRPC(seconds=CONF.connection_timer, action=rpc):
            res = await session.call(
                rpc,
                uuid=board.uuid,
                session=details.session
            )

            w_msg = WM.deserialize(res)

            if w_msg.result == WM.SUCCESS:

                LOG.info(" - Access granted to Iotronic.")

                # WS ALIVE
                asyncio.run_coroutine_threadsafe(wamp_checks(session), loop)

                # LOADING BOARD MODULES
                try:

                    modulesLoader(session)

                except Exception as e:
                    LOG.warning("WARNING - Could not load modules: " + str(e))
                    utils.LR_restart()

                # Reset flag to False
                # reconnection = False

            else:
                LOG.error(" - Access denied to Iotronic.")
                Bye()

    except exception.ApplicationError as e:
        LOG.error(" - Iotronic Connection RPC error: " + str(e))
        # Iotronic is offline the board can not call
        # the "stack4things.connection" RPC.
        # The board will disconnect from WAMP agent and retry later.
        reconnection = True

        # We restart Lightning-rod if RPC 'stack4things.connection' is not
        # available, this means Wagent is unreachable
        utils.LR_restart()

    except Exception as e:
        LOG.warning("Iotronic board connection error: " + str(e))


def wampConnect(wamp_conf):
    """WAMP connection procedures.

    :param wamp_conf: WAMP configuration from settings.json file

    """

    LOG.info("WAMP connection precedures:")

    try:

        LOG.info(
            "WAMP status @ boot:" +
            "\n- board = " + str(board.status) +
            "\n- reconnection = " + str(reconnection) +
            "\n- connected = " + str(connected)
        )

        wamp_transport = wamp_conf['url']
        wurl_list = wamp_transport.split(':')
        is_wss = False

        if wurl_list[0] == "wss":
            is_wss = True
        whost = wurl_list[1].replace('/', '')
        wport = int(wurl_list[2].replace('/', ''))

        if is_wss and CONF.skip_cert_verify:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            wamp_transport = [
                {
                    "url": wamp_transport,
                    "serializers": ["json"],
                    "endpoint": {
                        "type": "tcp",
                        "host": whost,
                        "port": wport,
                        "tls": ctx
                    },
                },
            ]

        # LR creates the Autobahn Asyncio Component that points to the
        # WAMP Agent (main/registration agent)
        global component
        component = Component(
            transports=wamp_transport,
            realm=wamp_conf['realm']
        )

        # To manage the registration stage: we got the info for the main
        # WAMP agent and LR is going to connect to it starting the Component
        # with the new WAMP configuration.
        if connected == False and board.status == "registered" \
                and reconnection == False:
            component.start(loop)

        @component.on_join
        async def join(session, details):
            """Execute the following procedures when the board connects
            to Crossbar.

            :param details: WAMP session details

            """

            print("WAMP SOCKET: " + str(psutil.Process().connections()[0]))

            global connected
            connected = True

            # LIGHTNING-ROD STATES:
            # - REGISTRATION STATE: the first connection to Iotronic
            # - FIRST CONNECTION: the board become operative after registration
            # - LIGHTNING-ROD BOOT: the first connection to WAMP
            #                       after Lightning-rod starting
            # - WAMP RECOVERY: when the established WAMP connection fails

            global reconnection

            # reconnection flag is False when the board is:
            # - LIGHTNING-ROD BOOT
            # - REGISTRATION STATE
            # - FIRST CONNECTION
            #
            # reconnection flag is True when the board is:
            # - WAMP RECOVERY

            global SESSION
            SESSION = session

            # LOG.debug(" - session: " + str(details))

            board.session_id = details.session

            LOG.info(" - Joined in realm " + board.wamp_config['realm'] + ":")
            LOG.info("   - WAMP Agent: " + str(board.agent))
            print(" - WAMP Agent: " + str(board.agent) + " - "
                  + str(wamp_conf['url']))
            LOG.info("   - Session ID: " + str(board.session_id))
            print(" - Session ID: " + str(board.session_id))
            LOG.info("   - Board status:  " + str(board.status))

            if reconnection is False:

                if board.uuid is None:

                    ######################
                    # REGISTRATION STATE #
                    ######################
                    # If in the LR configuration file there is not the
                    # Board UUID specified it means the board is a new one
                    # and it has to call IoTronic in order to complete
                    # the registration.

                    try:

                        LOG.info(" - Board needs to be registered.")

                        rpc = u'stack4things.register'

                        with timeoutRPC(seconds=5, action=rpc):
                            res = await session.call(
                                rpc,
                                code=board.code,
                                session=board.session_id
                            )

                        w_msg = WM.deserialize(res)

                        # LOG.info(" - Board registration result: \n" +
                        #         json.loads(w_msg.message, indent=4))

                        if w_msg.result == WM.SUCCESS:

                            LOG.info("Registration authorized by IoTronic:\n"
                                     + str(w_msg.message))

                            # the 'message' field contains
                            # the board configuration to load
                            board.setConf(w_msg.message)

                            # We need to disconnect the client from the
                            # registration-agent in order to reconnect
                            # to the WAMP agent assigned by Iotronic
                            # at the provisioning stage
                            LOG.info(
                                "\n\nDisconnecting from Registration Agent "
                                "to load new settings...\n\n")

                            # We restart Lightning-rod if RPC
                            # 'stack4things.connection' is not available,
                            # this means Wagent is unreachable
                            utils.LR_restart()

                        else:
                            LOG.error("Registration denied by Iotronic: "
                                      + str(w_msg.message))
                            Bye()

                    except exception.ApplicationError as e:
                        LOG.error("IoTronic registration error: " + str(e))
                        # Iotronic is offline the board can not call the
                        # "stack4things.connection" RPC. The board will
                        # disconnect from WAMP agent and retry later.

                        # TO ACTIVE BOOT CONNECTION RECOVERY MODE
                        reconnection = True

                        # We restart Lightning-rod if RPC
                        # 'stack4things.connection' is not available,
                        # this means Wagent is unreachable
                        utils.LR_restart()

                    except Exception as e:
                        LOG.warning(
                            " - Board registration call error: " + str(e))
                        Bye()

                else:

                    if board.status == "registered":
                        ####################
                        # FIRST CONNECTION #
                        ####################

                        # In this case we manage the first connection
                        # after the registration stage:
                        # Lightining-rod sets its status to "operative"
                        # completing the provisioning and configuration stage.
                        LOG.info("\n\n\nBoard is becoming operative...\n\n\n")
                        board.updateStatus("operative")
                        board.loadSettings()
                        LOG.info("WAMP status @ first connection:" +
                                 "\n- board = " + str(board.status) +
                                 "\n- reconnection = " + str(reconnection) +
                                 "\n- connected = " + str(connected)
                                 )
                        await IotronicLogin(board, session, details)

                    elif board.status == "operative":
                        ######################
                        # LIGHTNING-ROD BOOT #
                        ######################

                        # After join to WAMP agent, Lightning-rod will:
                        # - authenticate to Iotronic
                        # - load the enabled modules

                        # The board will keep at this stage until
                        # it will succeed to connect to Iotronic.
                        await IotronicLogin(board, session, details)

                    else:
                        LOG.error("Wrong board status '" + board.status + "'.")
                        Bye()

            else:

                #################
                # WAMP RECOVERY #
                #################

                LOG.info("IoTronic connection recovery:")

                try:

                    rpc = str(board.agent) + u'.stack4things.connection'

                    with timeoutRPC(seconds=CONF.connection_timer, action=rpc):
                        res = await session.call(
                            rpc,
                            uuid=board.uuid,
                            session=details.session
                        )

                    w_msg = WM.deserialize(res)

                    if w_msg.result == WM.SUCCESS:

                        LOG.info(" - Access granted to Iotronic (recovery).")

                        # LOADING BOARD MODULES
                        # If the board is in WAMP connection recovery state
                        # we need to register again the RPCs of each module
                        try:

                            moduleReloadInfo(session)

                            # Reset flag to False
                            reconnection = False

                            LOG.info("WAMP Session Recovered!")

                            LOG.info("\n\nListening...\n\n")

                            # WS ALIVE
                            asyncio.run_coroutine_threadsafe(
                                wamp_checks(session),
                                loop
                            )

                        except Exception as e:
                            LOG.warning(
                                "WARNING - Could not reload modules: "
                                + str(e))
                            Bye()

                    else:
                        LOG.error("Access to IoTronic denied: "
                                  + str(w_msg.message))
                        Bye()

                except exception.ApplicationError as e:
                    LOG.error("IoTronic connection error:\n" + str(e))
                    # Iotronic is offline the board can not call
                    # the "stack4things.connection" RPC.
                    # The board will disconnect from WAMP agent and retry later

                    # TO ACTIVE WAMP CONNECTION RECOVERY MODE
                    reconnection = False

                    # We restart Lightning-rod if RPC 'stack4things.connection'
                    # is not available, this means Wagent is unreachable
                    utils.LR_restart()

                except Exception as e:
                    LOG.warning("Board connection error after WAMP recovery: "
                                + str(e))
                    Bye()

        @component.on_leave
        async def onLeave(session, details):
            LOG.warning("WAMP Session Left: reason = " + str(details.reason))

        @component.on_disconnect
        async def onDisconnect(session, was_clean):
            """Procedure triggered on WAMP connection lost.
            :param session:
            :param was_clean:
            :return:
            """

            LOG.warning('WAMP Transport Left: was_clean = ' + str(was_clean))
            global connected
            connected = False

            global reconnection

            LOG.info(
                "WAMP status on disconnect:" +
                "\n- board = " + str(board.status) +
                "\n- reconnection = " + str(reconnection) +
                "\n- connected = " + str(connected)
            )

            if board.status == "operative" and reconnection is False:

                #################
                # WAMP RECOVERY #
                #################
                # we need to recover wamp session and
                # we set reconnection flag to True in order to activate
                # the module-RPCs registration procedure for each module

                reconnection = True

                # LR needs to reconncet to WAMP
                if not connected:
                    LOG.warning(".............WAMP DISCONNECTION.............")
                    LOG.info(
                        "WAMP status on disconnect:" +
                        "\n- board = " + str(board.status) +
                        "\n- reconnection = " + str(reconnection) +
                        "\n- connected = " + str(connected)
                    )

                    # component.start(loop)

            elif board.status == "operative" and reconnection is True:

                ######################
                # LIGHTNING-ROD BOOT #
                ######################
                # At this stage if the reconnection flag was set to True
                # it means that we forced the reconnection procedure
                # because of the board is not able to connect to IoTronic
                # calling "stack4things.connection" RPC...
                # it means IoTronic is offline!

                # We need to reset the reconnection flag to False in order to
                # do not enter in module-RPCs registration procedure...
                # At this stage the board tries to reconnect to
                # IoTronic until it will come online again.
                reconnection = False

                # LR needs to reconncet to WAMP
                LOG.warning(".............WAMP DISCONNECTION.............")
                LOG.info("WAMP status on disconnect:" +
                         "\n- board = " + str(board.status) +
                         "\n- reconnection = " + str(reconnection) +
                         "\n- connected = " + str(connected)
                         )

                # component.start(loop)

            elif (board.status == "registered"):
                ######################
                # REGISTRATION STATE #
                ######################

                # LR was disconnected from Registration Agent
                # in order to connect it to the assigned WAMP Agent.

                LOG.debug("\n\nReconnecting after registration...\n\n")

                # LR load the new configuration and gets the new WAMP Agent
                board.loadSettings()

                # LR has to connect to the assigned WAMP Agent
                wampConnect(board.wamp_config)

            else:
                LOG.error("Reconnection wrong status!")

    except Exception as err:
        LOG.error(" - WAMP connection error: " + str(err))
        Bye()


def moduleWampRegister(session, meth_list):
    """This function register for each module methods the relative RPC.

    :param session:
    :param meth_list:

    """

    if len(meth_list) == 2:

        LOG.info("   - No procedures to register!")

    else:

        for meth in meth_list:
            # We don't considere the "__init__", "finalize" and
            # "restore" methods
            if (meth[0] != "__init__") & (meth[0] != "finalize") \
                    & (meth[0] != "restore"):

                rpc_addr = u'iotronic.' + str(board.session_id) + '.' + \
                           board.uuid + '.' + meth[0]

                if not meth[0].startswith('_'):
                    session.register(meth[1], rpc_addr)
                    LOG.info("   --> " + str(meth[0]))


def modulesLoader(session):
    """Modules loader method thorugh stevedore libraries.

    :param session:

    """

    LOG.info("Available modules: ")

    ep = []

    for ep in pkg_resources.iter_entry_points(group='s4t.modules'):
        LOG.info(" - " + str(ep))

    if not ep:

        LOG.info("No modules available!")
        sys.exit()

    else:

        modules = extension.ExtensionManager(
            namespace='s4t.modules',
            # invoke_on_load=True,
            # invoke_args=(session,),
        )

        LOG.info('Modules to load:')

        for ext in modules.extensions:

            # LOG.debug(ext.name)

            if (ext.name == 'gpio') & (board.type == 'server'):
                LOG.info("- GPIO module disabled for 'server' devices")

            else:
                mod = ext.plugin(board, session)

                global MODULES
                MODULES[mod.name] = mod

                # Methods list for each module
                meth_list = inspect.getmembers(mod, predicate=inspect.ismethod)

                global RPC
                RPC[mod.name] = meth_list

                if len(meth_list) == 3:
                    # there are at least two methods for each module:
                    # "__init__" and "finalize"

                    LOG.info(" - No RPC to register for "
                             + str(ext.name) + " module!")

                else:
                    LOG.info(" - RPC list of " + str(mod.name) + ":")
                    moduleWampRegister(SESSION, meth_list)

                # Call the finalize procedure for each module
                mod.finalize()

        LOG.info("Lightning-rod modules loaded.")
        LOG.info("\n\nListening...")


def moduleReloadInfo(session):
    """This function is used in the reconnection stage to register

    again the RPCs of each module and for device.

    :param session: WAMP session object.

    """

    LOG.info("\n\nModules reloading after WAMP recovery...\n\n")

    try:

        # Call module restore procedures and
        # register RPCs for each Lightning-rod module
        for mod_name in MODULES:
            LOG.info("- Registering RPCs for module " + str(mod_name))
            moduleWampRegister(session, RPC[mod_name])

            LOG.info("- Restoring module " + str(mod_name))
            MODULES[mod_name].restore()

        # Register RPCs for the device
        for dev in RPC_devices:
            LOG.info("- Registering RPCs for device " + str(dev))
            moduleWampRegister(session, RPC_devices[dev])

    except Exception as err:
        LOG.warning("Board modules reloading error: " + str(err))
        utils.LR_restart()


def Bye():
    LOG.info("Bye!")
    os._exit(1)


def LogoLR():
    LOG.info('##############################')
    LOG.info('  Stack4Things Lightning-rod')
    LOG.info('##############################')


def main():
    LightningRod()
