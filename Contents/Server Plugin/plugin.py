#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Rain Machine Indigo Server Plugin 2
#
# Copyright (c) 2018-2023 Geoff Harris
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the MIT Public License
# which accompanies this distribution, and is available at
# https://github.com/geoffsharris/RainMachine2/blob/main/LICENSE
#
#
# Contributors:
# Geoff Harris
# Huge thank you to Aaron Bach for writing the Regenmaschine library that this plugin uses
# https://github.com/bachya
#
import time
try:
    import indigo
except ImportError:
    pass
from aiohttp import ClientSession
try:
    from regenmaschine import Client
    import asyncio
except ImportError:
    raise ImportError("'Required Python libraries missing.  Run 'pip3 install regenmaschine' in Terminal window, then reload plugin. Xcode install is also required!")

POLL_INTERVAL_DEFAULT = 60
POLL_INTERVAL_MINIMUM = 10
POLL_INTERVAL_MAXIMUM = 3600


################################################################################
class Plugin(indigo.PluginBase):
################################################################################

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = False
        self.rainmachine_devices = {}
        self.client = Client()
        self.next_update_programs = time.time()
        self.update_queue = []
        self.controllers = {}

################################################################################
    def __del__(self):
        indigo.PluginBase.__del__(self)

################################################################################
    def startup(self):
        self.debugLog(u"startup called")
        indigo.server.log("startup called")
        self.controllers = self.client.controllers
        self.logger.info(
            "Polling RainMachine every {} seconds".format(
                self._poll_interval()
            )
        )

################################################################################
    def shutdown(self):
        self.debugLog(u"shutdown called")
        indigo.server.log("shutdown called")

################################################################################
    def validatePrefsConfigUi(self, valuesDict):
        try:
            poll_interval = int(valuesDict.get(
                "pollInterval", POLL_INTERVAL_DEFAULT
            ))
        except (TypeError, ValueError):
            poll_interval = 0

        if not POLL_INTERVAL_MINIMUM <= poll_interval <= POLL_INTERVAL_MAXIMUM:
            errors = indigo.Dict()
            errors["pollInterval"] = (
                "Enter a polling interval from {} to {} seconds.".format(
                    POLL_INTERVAL_MINIMUM,
                    POLL_INTERVAL_MAXIMUM,
                )
            )
            errors["showAlertText"] = errors["pollInterval"]
            return False, valuesDict, errors

        valuesDict["pollInterval"] = str(poll_interval)
        return True, valuesDict

################################################################################
    def _poll_interval(self):
        try:
            value = int(self.pluginPrefs.get(
                "pollInterval", POLL_INTERVAL_DEFAULT
            ))
        except (TypeError, ValueError):
            return POLL_INTERVAL_DEFAULT
        return max(
            POLL_INTERVAL_MINIMUM,
            min(POLL_INTERVAL_MAXIMUM, value),
        )

################################################################################
    def deviceStartComm(self, device):
        self.debugLog("Starting device: " + device.name)
        if device.pluginProps["deviceMAC"]:
            indigo.server.log("device exists MAC: " + str(device.pluginProps["deviceMAC"]))
        else:
            indigo.server.log("new device")
        if device.id not in self.rainmachine_devices:
            indigo.server.log("Added Device id: " + str(device.id) + " to self.rainmachine_devices")
            self.mac_address = device.pluginProps["deviceMAC"]
        if device.id in self.rainmachine_devices:
            indigo.server.log("Existing Device id: " + str(device.id) + " : MAC = " + self.rainmachine_devices[device.id])
        self.rainmachine_devices[device.id] = device.pluginProps["deviceMAC"]
        indigo.server.log("Device Start Communication")
        self.user_name = device.pluginProps["username"]
        self.password = device.pluginProps["password"]
        self.connection_type = device.pluginProps["connectionType"]
        self.ip_address = device.pluginProps["ip_address"]
        self.port = device.pluginProps["port"]
        self.ssl = device.pluginProps["https"]
        self.debugLog("Started device: " + str(device.id))
        self.debugLog(str(device))
        if device.pluginProps["deviceMAC"] not in self.controllers:
            indigo.server.log("Needs to login")
            if self.connection_type == 'Local':
                asyncio.run(self.loginDevicesLocal(self.ip_address, self.password))
            elif self.connection_type == 'Cloud':
                self.client.load_remote(self.user_name, self.password)
            else:
                indigo.server.log("No, key: does not exists in dictionary")
        if device.pluginProps["deviceMAC"] in self.controllers:
            indigo.server.log("Device logged in")
        self.mac_address = self.rainmachine_devices[device.id]
        self.controller = self.client.controllers[self.mac_address]
        self.program_list = asyncio.run(self.controller.programs.all())
        self.zone_list = asyncio.run(self.controller.zones.all())
        dev = indigo.devices[device]
        localPropsCopy = dev.pluginProps
        localPropsCopy.update({'address':self.ip_address})
        dev.replacePluginPropsOnServer(localPropsCopy)

        # Update status on server: #
        device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        device.updateStateOnServer('device_online', value=True, clearErrorState=True)

################################################################################
    def deviceStopComm(self, device):
        self.debugLog("Stopping device: " + device.name)
        indigo.server.log("Device Stop Communication")
        if device.id in self.rainmachine_devices:
            device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
            device.updateStateOnServer('device_online', value=False, clearErrorState=True)
            del self.rainmachine_devices[device.id]

################################################################################
    async def update(self):

        self.logger.debug("Update Called")
        if self.update_queue:
            self.debugLog("queue has update")
            deviceId = int(self.update_queue.pop(0))
            self.debugLog("device id:" + str(deviceId))

            device = indigo.devices[deviceId]
            zone_data = await self.activeZone(deviceId)
            self.debugLog("device to update" + str(zone_data))
            counter = 0
            for kd in zone_data: # for kd in zone_data[u'zones']:
                if kd[u'state'] != 0:
                    self.debugLog("zone {} is on for {} seconds".format(kd[u'name'], (kd[u'remaining'])))
                    device.updateStateOnServer('current_zone', kd[u'name'], clearErrorState=True)
                    device.updateStateOnServer('minutes_left', int(round(kd[u'remaining'] / 60)),
                                               uiValue=str(int(round(kd[u'remaining'] / 60))) + " min",
                                               clearErrorState=True)
                    device.updateStateOnServer('active_watering', 'on', clearErrorState=True)
                    device.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOn)
                    counter += 1
            if counter == 0:
                self.debugLog("no active zones")
                device.updateStateOnServer('current_zone', 'all off', clearErrorState=True)
                device.updateStateOnServer('minutes_left', 0, uiValue='0 min', clearErrorState=True)
                device.updateStateOnServer('active_watering', 'off', clearErrorState=True)
                device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            program_data = await self.activeProgram(deviceId)
            if program_data and program_data[0]['name'] != None:
                self.debugLog("program data : " + str(program_data))
                self.debugLog("program data available")
                for kd in program_data:  # for kd in program_data[u'programs']:
                    device.updateStateOnServer('current_program', kd['name'], clearErrorState=True)
            else:
                device.updateStateOnServer('current_program', 'none', clearErrorState=True)
                self.debugLog("program data should be none")

        if time.time() > self.next_update_programs:
            counter = 0
            for key, value in self.rainmachine_devices.items():
                deviceId = key
                device = indigo.devices[deviceId]
                zone_data = await self.activeZone(deviceId)
                for kd in zone_data: # for kd in zone_data[u'zones']:
                    if kd[u'state'] != 0:
                        #self.debugLog("zone {} is on for {} seconds".format(kd[u'name'], (kd[u'remaining'])))
                        device.updateStateOnServer('current_zone', kd[u'name'], clearErrorState=True)
                        device.updateStateOnServer('minutes_left', round(kd[u'remaining'] / 60),
                                                   uiValue = str(int(round(kd[u'remaining'] / 60))) + " min",
                                                   clearErrorState = True)
                        device.updateStateOnServer('active_watering', 'on', clearErrorState=True)
                        device.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOn)
                        counter += 1
                if counter == 0:
                    device.updateStateOnServer('current_zone', 'all off', clearErrorState=True)
                    device.updateStateOnServer('minutes_left', 0, uiValue='0 min', clearErrorState=True)
                    device.updateStateOnServer('active_watering', 'off', clearErrorState=True)
                    device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

                program_data = await self.activeProgram(deviceId)
                if program_data and program_data[0]['name'] != None:
                    self.debugLog("program data : " + str(program_data))
                    for kd in program_data: #for kd in program_data[u'programs']:
                        device.updateStateOnServer('current_program', kd['name'], clearErrorState=True)
                else:
                    device.updateStateOnServer('current_program', 'none', clearErrorState=True)
                    self.debugLog("program data should be none: " + str(program_data))

                flowmeter_data = await self.flowmeter(deviceId)
                if flowmeter_data:
                    self.debugLog("flowmeter data : " + str(flowmeter_data))
                    device.updateStateOnServer('flowmeter', (str(flowmeter_data['flowMeterWateringClicks']+flowmeter_data['flowMeterLeakClicks'])+' gal'), clearErrorState=True)
                else:
                    pass

            self.next_update_programs = (
                time.time() + self._poll_interval()
            )

################################################################################
    def runConcurrentThread(self):
        self.logger.debug(u"runConcurrentThread starting")
        try:
            while True:

                if time.time() > self.next_update_programs:
                    asyncio.run(self.update())

                self.sleep(10.0)

        except self.StopThread:
            self.logger.debug(u"runConcurrentThread ending")
            pass

    def stopConcurrentThread(self):
        self.stopThread = True

    #####################################
    #            Run Program            #
    #####################################
    def actionRunProgram(self, pluginAction):
        deviceId = int(pluginAction.props['indigo_rainmachine_controller'])
        device = indigo.devices[deviceId]
        controller = self.controllers[device.pluginProps["deviceMAC"]]
        asyncio.run(controller.programs.start(pluginAction.props["ProgramValue"]))
        self.debugLog("Starting Program: " + str(pluginAction.props["ProgramValue"]))

        self.update_queue.append(deviceId)
        asyncio.run(self.update())

    def actionStopProgram(self, pluginAction):
        deviceId = int(pluginAction.props['indigo_rainmachine_controller'])
        device = indigo.devices[deviceId]
        controller = self.controllers[device.pluginProps["deviceMAC"]]
        asyncio.run(controller.programs.stop(pluginAction.props["ProgramValue"]))
        self.debugLog("Stopping Program: " + str(pluginAction.props["ProgramValue"]))

        self.update_queue.append(deviceId)
        asyncio.run(self.update())

    #####################################
    #              Run Zones            #
    #####################################
    def actionRunZones(self, pluginAction):
        deviceId = int(pluginAction.props['indigo_rainmachine_controller'])
        device = indigo.devices[int(pluginAction.props['indigo_rainmachine_controller'])]
        controller = self.controllers[device.pluginProps["deviceMAC"]]
        asyncio.run(controller.zones.start(pluginAction.props["ZoneValue"], pluginAction.props["zoneDuration"]))
        self.debugLog("Zone: " + str(pluginAction.props["ZoneValue"]) + " Time: " + str(pluginAction.props["zoneDuration"]))

        self.update_queue.append(deviceId)
        asyncio.run(self.update())

    def actionStopZones(self, pluginAction):
        deviceId = int(pluginAction.props['indigo_rainmachine_controller'])
        device = indigo.devices[int(pluginAction.props['indigo_rainmachine_controller'])]
        controller = self.controllers[device.pluginProps["deviceMAC"]]
        asyncio.run(controller.zones.stop(pluginAction.props["ZoneValue"]))
        self.debugLog("Stopping Zone: " + str(pluginAction.props["ZoneValue"]))

        self.update_queue.append(deviceId)
        asyncio.run(self.update())

    def actionAllOff(self, pluginAction):
        deviceId = int(pluginAction.props['indigo_rainmachine_controller'])
        device = indigo.devices[int(pluginAction.props['indigo_rainmachine_controller'])]
        controller = self.controllers[device.pluginProps["deviceMAC"]]
        asyncio.run(controller.watering.stop_all())
        self.debugLog("Stopping All Called")

        self.update_queue.append(deviceId)
        asyncio.run(self.update())

    #########################################
    #  populate menus for zone and program  #
    #########################################

    def availableSchedules(self, filter="", valuesDict=None, typeId="", targetId=0):
        passed_schedule_list = []
        if 'indigo_rainmachine_controller' in valuesDict:
            device = indigo.devices[int(valuesDict['indigo_rainmachine_controller'])]
            controller = self.controllers[device.pluginProps['deviceMAC']]
            self.program_list = asyncio.run(controller.programs.all())
            passed_schedule_list = [(program_dict_key, program_dict_value["name"]) for program_dict_key, program_dict_value in self.program_list.items()]
            self.debugLog("indigo.device.id : " + str(valuesDict['indigo_rainmachine_controller']))
            self.debugLog("indigo.mac.id : " + str(device.pluginProps['deviceMAC']))
        return passed_schedule_list

    def availableZones(self, filter="", valuesDict=None, typeId="", targetId=0):
        passed_zone_list = []
        if 'indigo_rainmachine_controller' in valuesDict:
            device = indigo.devices[int(valuesDict['indigo_rainmachine_controller'])]
            controller = self.controllers[device.pluginProps['deviceMAC']]
            self.zone_list = asyncio.run(controller.zones.all())
            passed_zone_list = [(zone_dict_key, zone_dict_value["name"]) for zone_dict_key, zone_dict_value in self.zone_list.items()] #[(int(zone_dict["uid"]), zone_dict["name"]) for zone_dict in self.zone_list["zones"]]
        return passed_zone_list

    def availableDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
        controller_list = [(controller.mac, controller.name) for controller in self.client.controllers.values()]
        return controller_list

    #################################
    #  login into existing devices  #
    #################################

    def loginDevices(self, valuesDict, typeId, devId):
        if valuesDict["connectionType"] == 'Local':
            ip_address = valuesDict["ip_address"]
            password = valuesDict["password"]
            asyncio.run(self.loginDevicesLocal(ip_address, password))
        elif valuesDict["connectionType"] == 'Cloud':
            asyncio.run(self.loginDevicesCloud(valuesDict, typeId, devId))
        else:
            indigo.server.log("Error in login")
        pass

    async def loginDevicesLocal(self, ip_address, password):
        await self.client.load_local(ip_address, password)

    async def loginDevicesCloud(self, valuesDict, typeId, devId):
        if valuesDict["connectionType"] == 'Cloud':
            await self.client.load_remote(valuesDict["username"], valuesDict["password"])
        else:
            indigo.server.log("Error in login")
        pass

    ######################
    #  Updates UI menus  #
    ######################
    def menuChanged(self, valuesDict, typeId, devId):
        return valuesDict

################################################################################
    def exportZoneList(self):
        if not self.controllers:
            indigo.server.log(
                "No connected RainMachine controllers are available.",
                isError=True,
            )
            return

        for controller in sorted(
            self.controllers.values(),
            key=lambda value: str(getattr(value, "name", "")),
        ):
            try:
                zones = asyncio.run(controller.zones.all())
            except Exception as error:
                indigo.server.log(
                    "Unable to export RainMachine zones: {}".format(error),
                    isError=True,
                )
                continue

            controller_name = (
                getattr(controller, "name", None)
                or getattr(controller, "mac", "RainMachine")
            )
            lines = [
                "RainMachine zone list for {}:".format(controller_name),
                "Zone\tName",
            ]
            for zone_id, zone in sorted(
                zones.items(),
                key=self._zoneSortKey,
            ):
                zone_name = " ".join(str(zone.get("name", "")).split())
                lines.append("{}\t{}".format(zone_id, zone_name))
            indigo.server.log("\n".join(lines))

################################################################################
    @staticmethod
    def _zoneSortKey(item):
        try:
            return 0, int(item[0])
        except (TypeError, ValueError):
            return 1, str(item[0])

    ######################
    #  Update functions  #
    ######################
    async def activeZone(self, deviceId):
        device = indigo.devices[deviceId]
        controller = self.controllers[device.pluginProps['deviceMAC']]
        current_zone = await controller.zones.running()
        self.debugLog("active zone called")
        return current_zone

    async def activeProgram(self, deviceId):
        device = indigo.devices[deviceId]
        controller = self.controllers[device.pluginProps['deviceMAC']]
        current_program = await controller.programs.running()
        self.debugLog("active program called")
        return current_program

    async def flowmeter(self, deviceId):
        device = indigo.devices[deviceId]
        controller = self.controllers[device.pluginProps['deviceMAC']]
        flowmeter = await controller.watering.flowmeter()
        self.debugLog("flowmeter called")
        self.debugLog(str(flowmeter))
        return flowmeter

    ######################
    #  Debugger Toggle   #
    ######################
    def toggleDebugging(self):
        if self.debug:
            self.logger.info("Turning off debug logging")
            self.pluginPrefs["showDebugInfo"] = False
        else:
            self.logger.info("Turning on debug logging")
            self.pluginPrefs["showDebugInfo"] = True
        self.debug = not self.debug
