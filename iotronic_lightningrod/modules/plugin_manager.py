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

from __future__ import absolute_import

from datetime import datetime
import imp
import inspect
import json
import os
from Queue import Queue
import shutil
import time
from twisted.internet.defer import returnValue

from iotronic_lightningrod.config import iotronic_home
from iotronic_lightningrod.modules import Module
from iotronic_lightningrod.plugins import PluginSerializer
import iotronic_lightningrod.wampmessage as WM


from oslo_log import log as logging
LOG = logging.getLogger(__name__)

PLUGINS_THRS = {}
PLUGINS_CONF_FILE = iotronic_home + "/plugins.json"


def getFuncName():
    return inspect.stack()[1][3]


def createPluginsConf():
    """Create plugins.json file if it does not exist.

    """
    if not os.path.exists(PLUGINS_CONF_FILE):
        LOG.debug("plugins.json does not exist: creating...")
        plugins_conf = {'plugins': {}}
        with open(PLUGINS_CONF_FILE, 'w') as f:
            json.dump(plugins_conf, f, indent=4)


def loadPluginsConf():
    """Load plugins.json JSON configuration.

    :return: JSON Plugins configuration

    """

    try:

        with open(PLUGINS_CONF_FILE) as settings:
            plugins_conf = json.load(settings)

    except Exception as err:
        LOG.error("Parsing error in " + PLUGINS_CONF_FILE + ": " + str(err))
        plugins_conf = None

    return plugins_conf


def getEnabledPlugins():
    """This function gets the list of all asynchronous plugins.

    We considered only those plugins with 'callable' flag set to False
    and 'onboot' flag set to True.

    :return: enabledPlugins List

    """
    enabledPlugins = []
    plugins_conf = loadPluginsConf()

    for plugin in plugins_conf['plugins']:

        if plugins_conf['plugins'][plugin]['callable'] is False:

            if plugins_conf['plugins'][plugin]['onboot'] is True:

                if plugins_conf['plugins'][plugin]['status'] == "operative":
                    enabledPlugins.append(plugin)

    if len(enabledPlugins) != 0:
        LOG.info(" - Enabled plugins list: " + str(enabledPlugins))

    return enabledPlugins


def makeNothing():
    """Sandbox function.

    """
    pass


def RebootOnBootPlugins():
    """Reboot at boot each enabled asynchronous plugin

    :return:

    """

    rpc_name = getFuncName()
    LOG.info("Rebooting enabled plugins:")

    enabledPlugins = getEnabledPlugins()

    if enabledPlugins.__len__() == 0:

        message = "No plugin to reboot!"
        LOG.info(" - " + message)

    else:

        for plugin_uuid in enabledPlugins:

            plugins_conf = loadPluginsConf()
            plugin_name = plugins_conf['plugins'][plugin_uuid]['name']
            # plugin_status = plugins_conf['plugins'][plugin_uuid]['status']

            try:

                if (plugin_uuid in PLUGINS_THRS) and (
                        PLUGINS_THRS[plugin_uuid].isAlive()
                ):

                    LOG.warning(" - Plugin "
                                + plugin_uuid + " already started!")

                else:

                    LOG.info(" - Rebooting plugin " + plugin_uuid)

                    plugin_home = iotronic_home + "/plugins/" + plugin_uuid
                    plugin_filename = plugin_home + "/" + plugin_uuid + ".py"
                    plugin_params_file = \
                        plugin_home + "/" + plugin_uuid + ".json"

                    if os.path.exists(plugin_filename):

                        task = imp.load_source("plugin", plugin_filename)

                        if os.path.exists(plugin_params_file):

                            with open(plugin_params_file) as conf:
                                plugin_params = json.load(conf)

                            worker = task.Worker(
                                plugin_uuid,
                                plugin_name,
                                q_result=None,
                                params=plugin_params
                            )

                            PLUGINS_THRS[plugin_uuid] = worker
                            LOG.info("   - Starting plugin " + str(worker))

                            worker.start()

                        else:
                            message = "ERROR " \
                                      + plugin_params_file + " does not exist!"

                            LOG.error("   - "
                                      + worker.complete(rpc_name, message))

                    else:
                        message = "ERROR " \
                                  + plugin_filename + " does not exist!"

                        LOG.error("   - " + worker.complete(rpc_name, message))

                message = "rebooted!"

                LOG.info("   - " + worker.complete(rpc_name, message))

            except Exception as err:
                message = "Error rebooting plugin " \
                          + plugin_uuid + ": " + str(err)
                LOG.error(" - " + message)


class PluginManager(Module.Module):

    """Plugin module to manage board plugins.

    """

    def __init__(self, board, session):
        """Init function for PluginManager module.

        :param board:
        :param session:

        """

        # Module declaration
        super(PluginManager, self).__init__("PluginManager", board)

        # Creation of plugins.json configuration file
        createPluginsConf()

    def finalize(self):
        """Function called at the end of module loading.

        This function in this module reloads
        the enabled (asynchronous) plugins at boot.

        """

        # Reboot boot enabled plugins
        RebootOnBootPlugins()

    def PluginInject(self, plugin, onboot):
        """Plugin injection procedure into the board:

         1. get Plugin files
         2. deserialize files
         3. store files

        :param plugin:
        :param onboot:
        :return:

        """

        rpc_name = getFuncName()

        try:

            plugin_uuid = plugin['uuid']
            plugin_name = plugin['name']
            code = plugin['code']
            callable = plugin['callable']

            LOG.info("RPC " + rpc_name + " for plugin '"
                     + plugin_name + "' (" + plugin_uuid + ")")

            # Deserialize the plugin code received
            ser = PluginSerializer.ObjectSerializer()
            loaded = ser.deserialize_entity(code)
            # LOG.debug("- plugin loaded code:\n" + loaded)

            plugin_path = iotronic_home + "/plugins/" + plugin_uuid + "/"
            plugin_filename = plugin_path + plugin_uuid + ".py"

            # Plugin folder creation if does not exist
            if not os.path.exists(plugin_path):
                os.makedirs(plugin_path)

            # Plugin code file creation
            with open(plugin_filename, "w") as pluginfile:
                pluginfile.write(loaded)

            # Load plugins.json configuration file
            plugins_conf = loadPluginsConf()

            # LOG.debug("Plugin setup:\n"
            #          + json.dumps(plugin, indent=4, sort_keys=True))

            # Save plugin settings in plugins.json
            if plugin_uuid not in plugins_conf['plugins']:

                # It is a new plugin
                plugins_conf['plugins'][plugin_uuid] = {}
                plugins_conf['plugins'][plugin_uuid]['name'] = plugin_name
                plugins_conf['plugins'][plugin_uuid]['onboot'] = onboot
                plugins_conf['plugins'][plugin_uuid]['callable'] = callable
                plugins_conf['plugins'][plugin_uuid]['injected_at'] = \
                    datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
                plugins_conf['plugins'][plugin_uuid]['updated_at'] = ""
                plugins_conf['plugins'][plugin_uuid]['status'] = "injected"

                LOG.info("Plugin " + plugin_name + " created!")
                message = rpc_name + " result: INJECTED"

            else:
                # The plugin was already injected and we are updating it
                plugins_conf['plugins'][plugin_uuid]['name'] = plugin_name
                plugins_conf['plugins'][plugin_uuid]['onboot'] = onboot
                plugins_conf['plugins'][plugin_uuid]['callable'] = callable
                plugins_conf['plugins'][plugin_uuid]['updated_at'] = \
                    datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
                plugins_conf['plugins'][plugin_uuid]['status'] = "updated"

                LOG.info("Plugin " + plugin_name
                         + " (" + str(plugin_uuid) + ") updated!")
                message = rpc_name + " result: UPDATED"

            LOG.info("Plugin setup:\n" + json.dumps(
                plugins_conf['plugins'][plugin_uuid],
                indent=4,
                sort_keys=True
            ))

            # Apply the changes to plugins.json
            with open(PLUGINS_CONF_FILE, 'w') as f:
                json.dump(plugins_conf, f, indent=4)

            LOG.info(" - " + message)
            w_msg = yield WM.WampSuccess(message)

        except Exception as err:
            message = "Plugin injection error: " + str(err)
            LOG.error(" - " + message)
            w_msg = yield WM.WampError(str(err))
            returnValue(w_msg.serialize())

        returnValue(w_msg.serialize())

    def PluginStart(self, plugin_uuid, parameters=None):
        """To start an asynchronous plugin;

        the plugin will run until the PluginStop is called.

        :param plugin_uuid:
        :param parameters:
        :return: return a response to RPC request

        """

        try:

            rpc_name = getFuncName()
            LOG.info("RPC " + rpc_name + " called for '"
                     + plugin_uuid + "' plugin:")

            plugins_conf = loadPluginsConf()

            if plugin_uuid in plugins_conf['plugins']:

                plugin_name = plugins_conf['plugins'][plugin_uuid]['name']

                # Check if the plugin is already running
                if (plugin_uuid in PLUGINS_THRS) and (
                        PLUGINS_THRS[plugin_uuid].isAlive()
                ):

                    message = "ALREADY STARTED!"
                    LOG.warning(" - Plugin "
                                + plugin_uuid + " already started!")
                    w_msg = yield WM.WampError(message)

                else:

                    plugin_home = \
                        iotronic_home + "/plugins/" + plugin_uuid
                    plugin_filename = \
                        plugin_home + "/" + plugin_uuid + ".py"
                    plugin_params_file = \
                        plugin_home + "/" + plugin_uuid + ".json"

                    # Import plugin (as python module)
                    if os.path.exists(plugin_filename):

                        task = imp.load_source("plugin", plugin_filename)

                        LOG.info(" - Plugin '" + plugin_uuid + "' imported!")

                        # Store input parameters of the plugin
                        if parameters is not None:

                            with open(plugin_params_file, 'w') as f:
                                json.dump(parameters, f, indent=4)

                            with open(plugin_params_file) as conf:
                                plugin_params = json.load(conf)

                            LOG.info(" - plugin with parameters:")
                            LOG.info("   " + str(plugin_params))

                        else:
                            plugin_params = None

                        worker = task.Worker(
                            plugin_uuid,
                            plugin_name,
                            params=plugin_params
                        )

                        PLUGINS_THRS[plugin_uuid] = worker
                        LOG.debug(" - Starting plugin " + str(worker))

                        worker.start()

                        # Apply the changes to plugins.json
                        with open(PLUGINS_CONF_FILE, 'w') as f:
                            plugins_conf['plugins'][plugin_uuid]['status'] = \
                                'operative'
                            json.dump(plugins_conf, f, indent=4)

                        response = "STARTED"
                        LOG.info(" - " + worker.complete(rpc_name, response))
                        w_msg = yield WM.WampSuccess(response)

                    else:
                        message = \
                            rpc_name + " - ERROR " \
                            + plugin_filename + " does not exist!"
                        LOG.error(" - " + message)
                        w_msg = yield WM.WampError(message)

            else:
                message = "Plugin " + plugin_uuid \
                          + " does not exist in this board!"
                LOG.warning(" - " + message)
                w_msg = yield WM.WampError(message)

        except Exception as err:
            message = \
                rpc_name + " - ERROR - plugin (" + plugin_uuid + ") - " \
                + str(err)
            LOG.error(" - " + message)
            w_msg = yield WM.WampError(str(err))
            returnValue(w_msg.serialize())

        returnValue(w_msg.serialize())

    def PluginStop(self, plugin_uuid, parameters=None):
        """To stop an asynchronous plugin

        :param plugin_uuid: ID of plufin to stop
        :param parameters: JSON OPTIONAL stop parameters; 'delay' in seconds
        :return: return a response to RPC request

        """
        rpc_name = getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED for '"
                 + plugin_uuid + "' plugin:")

        if parameters is not None:
            LOG.info(" - " + rpc_name + " parameters: " + str(parameters))
            if 'delay' in parameters:
                delay = parameters['delay']
                LOG.info(" --> stop delay: " + str(delay))

        try:

            if plugin_uuid in PLUGINS_THRS:

                worker = PLUGINS_THRS[plugin_uuid]
                LOG.debug(" - Stopping plugin " + str(worker))

                if worker.isAlive():

                    if 'delay' in parameters:
                        time.sleep(delay)

                    yield worker.stop()

                    del PLUGINS_THRS[plugin_uuid]

                    message = "STOPPED"
                    LOG.info(" - " + worker.complete(rpc_name, message))
                    w_msg = yield WM.WampSuccess(message)

                else:
                    message = \
                        rpc_name \
                        + " - ERROR - plugin (" + plugin_uuid \
                        + ") is instantiated but is not running anymore!"
                    LOG.error(" - " + message)
                    w_msg = yield WM.WampError(message)

            else:
                message = \
                    rpc_name + " - WARNING " \
                    + plugin_uuid + "  is not running!"
                LOG.warning(" - " + message)
                w_msg = yield WM.WampWarning(message)

        except Exception as err:
            message = \
                rpc_name \
                + " - ERROR - plugin (" + plugin_uuid + ") - " + str(err)
            LOG.error(" - " + message)
            w_msg = yield WM.WampError(str(err))
            returnValue(w_msg.serialize())

        returnValue(w_msg.serialize())

    def PluginCall(self, plugin_uuid, parameters=None):
        """To execute a synchronous plugin into the board

        :param plugin_uuid:
        :param parameters:
        :return: return a response to RPC request

        """

        rpc_name = getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED for " + plugin_uuid + " plugin:")

        try:

            if (plugin_uuid in PLUGINS_THRS) and (
                    PLUGINS_THRS[plugin_uuid].isAlive()
            ):

                message = "Plugin " + plugin_uuid + " already started!"
                LOG.warning(" - " + message)
                w_msg = yield WM.WampWarning(message)

            else:

                plugin_home = iotronic_home + "/plugins/" + plugin_uuid
                plugin_filename = plugin_home + "/" + plugin_uuid + ".py"
                plugin_params_file = plugin_home + "/" + plugin_uuid + ".json"

                plugins_conf = loadPluginsConf()
                plugin_name = plugins_conf['plugins'][plugin_uuid]['name']

                # Import plugin (as python module)
                if os.path.exists(plugin_filename):

                    try:

                        task = imp.load_source("plugin", plugin_filename)

                        LOG.info(" - Plugin " + plugin_uuid + " imported!")

                        q_result = Queue()

                    except Exception as err:
                        message = "Error importing plugin " \
                                  + plugin_filename + ": " + str(err)
                        LOG.error(" - " + message)
                        w_msg = yield WM.WampError(str(err))
                        returnValue(w_msg.serialize())

                    try:

                        # Store input parameters of the plugin
                        if parameters is not None:
                            with open(plugin_params_file, 'w') as f:
                                json.dump(parameters, f, indent=4)

                            with open(plugin_params_file) as conf:
                                plugin_params = json.load(conf)

                            LOG.info(" - Plugin configuration:\n"
                                     + str(plugin_params))

                        else:
                            plugin_params = None

                        worker = task.Worker(
                            plugin_uuid,
                            plugin_name,
                            q_result=q_result,
                            params=plugin_params
                        )

                        PLUGINS_THRS[plugin_uuid] = worker
                        LOG.debug(" - Executing plugin " + str(worker))

                        worker.start()

                        while q_result.empty():
                            pass

                        response = q_result.get()

                        LOG.info(" - " + worker.complete(rpc_name, response))
                        w_msg = yield WM.WampSuccess(response)

                    except Exception as err:
                        message = "Error spawning plugin " \
                                  + plugin_filename + ": " + str(err)
                        LOG.error(" - " + message)
                        w_msg = yield WM.WampError(str(err))
                        returnValue(w_msg.serialize())

                else:
                    message = \
                        rpc_name \
                        + " - ERROR " + plugin_filename + " does not exist!"
                    LOG.error(" - " + message)
                    w_msg = yield WM.WampError(message)

        except Exception as err:
            message = \
                rpc_name \
                + " - ERROR - plugin (" + plugin_uuid + ") - " + str(err)
            LOG.error(" - " + message)
            w_msg = yield WM.WampError(str(err))
            returnValue(w_msg.serialize())

        returnValue(w_msg.serialize())

    def PluginRemove(self, plugin_uuid):
        """To remove a plugin from the board

        :param plugin_uuid:
        :return: return a response to RPC request

        """

        rpc_name = getFuncName()

        LOG.info("RPC " + rpc_name + " for plugin " + plugin_uuid)

        plugin_path = iotronic_home + "/plugins/" + plugin_uuid + "/"

        if os.path.exists(plugin_path) is False \
                or os.path.exists(PLUGINS_CONF_FILE) is False:

            message = "Plugin paths or files do not exist!"
            LOG.error(message)
            w_msg = yield WM.WampError(message)
            returnValue(w_msg.serialize())

        else:

            LOG.info(" - Removing plugin...")

            try:

                try:

                    shutil.rmtree(
                        plugin_path,
                        ignore_errors=False,
                        onerror=None
                    )

                except Exception as err:
                    message = "Removing plugin's files error in " \
                              + plugin_path + ": " + str(err)
                    LOG.error(" - " + message)
                    w_msg = yield WM.WampError(str(err))
                    returnValue(w_msg.serialize())

                # Remove from plugins.json file its configuration
                try:

                    plugins_conf = loadPluginsConf()

                    if plugin_uuid in plugins_conf['plugins']:

                        plugin_name = \
                            plugins_conf['plugins'][plugin_uuid]['name']

                        del plugins_conf['plugins'][plugin_uuid]

                        with open(PLUGINS_CONF_FILE, 'w') as f:
                            json.dump(plugins_conf, f, indent=4)

                        if plugin_uuid in PLUGINS_THRS:
                            worker = PLUGINS_THRS[plugin_uuid]
                            if worker.isAlive():
                                LOG.info(" - Plugin "
                                         + plugin_name + " is running...")
                                worker.stop()
                                LOG.info("   ...stopped!")

                            del PLUGINS_THRS[plugin_uuid]

                        message = "PluginRemove result: " \
                                  + plugin_uuid + " removed!"
                        LOG.info(" - " + message)

                    else:
                        message = "PluginRemove result:  " \
                                  + plugin_uuid + " already removed!"
                        LOG.warning(" - " + message)

                    w_msg = yield WM.WampSuccess(message)
                    returnValue(w_msg.serialize())

                except Exception as err:
                    message = "Updating plugins.json error: " + str(err)
                    LOG.error(" - " + message)
                    w_msg = yield WM.WampError(str(err))
                    returnValue(w_msg.serialize())

            except Exception as err:
                message = "Plugin removing error: {0}".format(err)
                LOG.error(" - " + message)
                w_msg = yield WM.WampError(str(err))
                returnValue(w_msg.serialize())

    def PluginReboot(self, plugin_uuid):
        """To reboot an asynchronous plugin (callable = false) into the board.

        :return: return a response to RPC request

        """

        rpc_name = getFuncName()

        LOG.info("RPC " + rpc_name + " CALLED for '"
                 + plugin_uuid + "' plugin:")

        try:

            plugin_home = iotronic_home + "/plugins/" + plugin_uuid
            plugin_filename = plugin_home + "/" + plugin_uuid + ".py"
            plugin_params_file = plugin_home + "/" + plugin_uuid + ".json"

            plugins_conf = loadPluginsConf()
            plugin_name = plugins_conf['plugins'][plugin_uuid]['name']
            callable = plugins_conf['plugins'][plugin_uuid]['callable']

            if callable is False:

                if plugin_uuid in PLUGINS_THRS:

                    worker = PLUGINS_THRS[plugin_uuid]

                    if worker.isAlive():
                        # STOP PLUGIN------------------------------------------
                        LOG.info(" - Thread "
                                 + plugin_uuid + " is running, stopping...")
                        LOG.debug(" - Stopping plugin " + str(worker))
                        worker.stop()

                    # Remove from plugin thread list
                    del PLUGINS_THRS[plugin_uuid]

                # START PLUGIN-------------------------------------------------
                if os.path.exists(plugin_filename):

                    # Import plugin python module
                    task = imp.load_source("plugin", plugin_filename)

                    if os.path.exists(plugin_params_file):

                        with open(plugin_params_file) as conf:
                            plugin_params = json.load(conf)

                    else:
                        plugin_params = None

                    worker = task.Worker(
                        plugin_uuid,
                        plugin_name,
                        params=plugin_params
                    )

                    PLUGINS_THRS[plugin_uuid] = worker
                    LOG.info("   - Starting plugin " + str(worker))

                    worker.start()

                    message = "REBOOTED"
                    LOG.info(" - " + worker.complete(rpc_name, message))
                    w_msg = yield WM.WampSuccess(message)

                else:
                    message = "ERROR '" + plugin_filename + "' does not exist!"
                    LOG.error(" - " + message)
                    w_msg = yield WM.WampError(message)

        except Exception as err:
            message = "Error rebooting plugin '" \
                      + plugin_uuid + "': " + str(err)
            LOG.error(" - " + message)
            w_msg = yield WM.WampError(str(err))
            returnValue(w_msg.serialize())

        returnValue(w_msg.serialize())

    def PluginStatus(self, plugin_uuid):
        """Check status thread plugin

        :param plugin_uuid:
        :return:

        """

        rpc_name = getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED for '"
                 + plugin_uuid + "' plugin:")

        try:

            if plugin_uuid in PLUGINS_THRS:

                worker = PLUGINS_THRS[plugin_uuid]

                if worker.isAlive():
                    result = "ALIVE"
                else:
                    result = "DEAD"

                LOG.info(" - " + worker.complete(rpc_name, result))
                w_msg = yield WM.WampSuccess(result)

            else:
                result = "DEAD"
                LOG.info(" - " + rpc_name + " result for "
                         + plugin_uuid + ": " + result)
                w_msg = yield WM.WampSuccess(result)

        except Exception as err:
            message = \
                rpc_name \
                + " - ERROR - plugin (" + plugin_uuid + ") - " + str(err)
            LOG.error(" - " + message)
            w_msg = yield WM.WampError(str(err))
            returnValue(w_msg.serialize())

        returnValue(w_msg.serialize())
