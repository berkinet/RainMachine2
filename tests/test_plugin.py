import importlib.util
import asyncio
import logging
import plistlib
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "Contents" / "Server Plugin"


class PluginBase:
    def __init__(self, plugin_id, display_name, version, prefs):
        self.pluginPrefs = prefs
        self.logger = logging.getLogger("test")

    def __del__(self):
        pass

    def debugLog(self, message):
        pass


indigo = ModuleType("indigo")
indigo.PluginBase = PluginBase
indigo.Dict = dict
indigo.server = SimpleNamespace(log=MagicMock())
indigo.kStateImageSel = SimpleNamespace(
    SensorTripped="tripped", SensorOn="on", SprinklerOn="sprinkler"
)
indigo.devices = {}
sys.modules["indigo"] = indigo

aiohttp = ModuleType("aiohttp")
aiohttp.ClientSession = object
sys.modules["aiohttp"] = aiohttp


class Client:
    def __init__(self, *, request_timeout=30):
        self.request_timeout = request_timeout
        self.controllers = {}


regenmaschine = ModuleType("regenmaschine")
regenmaschine.Client = Client
sys.modules["regenmaschine"] = regenmaschine
regenmaschine_errors = ModuleType("regenmaschine.errors")


class RequestError(Exception):
    pass


regenmaschine_errors.RequestError = RequestError
sys.modules["regenmaschine.errors"] = regenmaschine_errors

spec = importlib.util.spec_from_file_location(
    "rainmachine2_plugin", SERVER / "plugin.py"
)
plugin_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin_module)


class PollingTests(unittest.TestCase):
    def make_plugin(self, prefs):
        return plugin_module.Plugin(
            "plugin.id", "RainMachine2", "1.0.4", prefs
        )

    def test_poll_interval_defaults_to_sixty_seconds(self):
        self.assertEqual(self.make_plugin({})._poll_interval(), 60)
        self.assertEqual(
            self.make_plugin({"pollInterval": "invalid"})._poll_interval(),
            60,
        )

    def test_poll_interval_is_configurable_and_bounded(self):
        self.assertEqual(
            self.make_plugin({"pollInterval": "10"})._poll_interval(),
            10,
        )
        self.assertEqual(
            self.make_plugin({"pollInterval": "1"})._poll_interval(),
            10,
        )
        self.assertEqual(
            self.make_plugin({"pollInterval": "7200"})._poll_interval(),
            3600,
        )

    def test_preferences_validation(self):
        plugin = self.make_plugin({})
        valid, values = plugin.validatePrefsConfigUi(
            {"pollInterval": "15"}
        )
        self.assertTrue(valid)
        self.assertEqual(values["pollInterval"], "15")

        valid, _, errors = plugin.validatePrefsConfigUi(
            {"pollInterval": "5"}
        )
        self.assertFalse(valid)
        self.assertIn("pollInterval", errors)

    def test_bundle_metadata_and_configuration(self):
        with (ROOT / "Contents" / "Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        self.assertEqual(info["PluginVersion"], "1.0.4")

        config = ET.parse(SERVER / "PluginConfig.xml").getroot()
        field = config.find("./Field[@id='pollInterval']")
        self.assertIsNotNone(field)
        self.assertEqual(field.attrib["defaultValue"], "60")

        with zipfile.ZipFile(
            ROOT / "RainMachine2.indigoPlugin.zip"
        ) as archive:
            prefix = "RainMachine2.indigoPlugin/Contents/"
            packaged_info = plistlib.loads(
                archive.read(prefix + "Info.plist")
            )
            packaged_config = ET.fromstring(
                archive.read(prefix + "Server Plugin/PluginConfig.xml")
            )
            packaged_menu = ET.fromstring(
                archive.read(prefix + "Server Plugin/MenuItems.xml")
            )
        self.assertEqual(packaged_info["PluginVersion"], "1.0.4")
        self.assertIsNotNone(
            packaged_config.find("./Field[@id='pollInterval']")
        )

        menu_items = ET.parse(SERVER / "MenuItems.xml").getroot()
        menu_names = [
            item.findtext("Name")
            for item in menu_items.findall("./MenuItem")
        ]
        self.assertEqual(
            menu_names,
            ["Toggle Debugging", "Update Devices", "Export Zone List"],
        )
        self.assertEqual(
            [
                item.findtext("Name")
                for item in packaged_menu.findall("./MenuItem")
            ],
            menu_names,
        )

    def test_zone_export_logs_zone_list(self):
        plugin = self.make_plugin({})
        zones = SimpleNamespace(
            all=AsyncMock(
                return_value={
                    "10": {"name": "Pool\nRefill"},
                    "2": {"name": "Below\tPool"},
                    "1": {"name": "Pool Lawn"},
                }
            )
        )
        plugin.controllers = {
            "controller": SimpleNamespace(name="Home", zones=zones)
        }
        indigo.server.log.reset_mock()

        plugin.exportZoneList()

        indigo.server.log.assert_called_once_with(
            "RainMachine zone list for Home:\n"
            "Zone\tName\n"
            "1\tPool Lawn\n"
            "2\tBelow Pool\n"
            "10\tPool Refill"
        )

    @staticmethod
    def controller(zones=None, programs=None, flowmeter=None):
        return SimpleNamespace(
            zones=SimpleNamespace(running=AsyncMock(
                return_value=[] if zones is None else zones)),
            programs=SimpleNamespace(running=AsyncMock(
                return_value=[] if programs is None else programs)),
            watering=SimpleNamespace(flowmeter=AsyncMock(
                return_value=flowmeter)),
        )

    @staticmethod
    def device(device_id=7):
        device = SimpleNamespace(
            id=device_id,
            name="Garden controller",
            pluginProps={"deviceMAC": "controller"},
            updateStateOnServer=MagicMock(),
            updateStateImageOnServer=MagicMock(),
            setErrorStateOnServer=MagicMock(),
        )
        indigo.devices[device_id] = device
        return device

    def test_request_timeout_is_logged_once_and_preserves_status_states(self):
        plugin = self.make_plugin({})
        device = self.device()
        controller = self.controller()
        controller.zones.running.side_effect = RequestError(
            "Timed out while requesting zone data"
        )
        plugin.controllers = {"controller": controller}
        plugin.logger = MagicMock()

        first = asyncio.run(plugin._refreshController(device.id))
        second = asyncio.run(plugin._refreshController(device.id))

        self.assertFalse(first)
        self.assertFalse(second)
        plugin.logger.error.assert_called_once_with(
            "RainMachine temporarily unavailable: device='{}' id={}: {}".format(
                device.name, device.id,
                "Timed out while requesting zone data",
            )
        )
        device.setErrorStateOnServer.assert_called_with("Communication failed")
        updated_keys = [call.args[0]
                        for call in device.updateStateOnServer.call_args_list]
        self.assertEqual(updated_keys, ["device_online", "device_online"])

    def test_successful_retry_publishes_status_and_logs_recovery_once(self):
        plugin = self.make_plugin({})
        device = self.device()
        controller = self.controller(
            zones=[{"state": 1, "name": "Orchard", "remaining": 125}],
            programs=[{"name": "Morning"}],
            flowmeter={
                "flowMeterWateringClicks": 4,
                "flowMeterLeakClicks": 1,
            },
        )
        controller.zones.running.side_effect = RequestError("temporary timeout")
        plugin.controllers = {"controller": controller}
        plugin.logger = MagicMock()
        asyncio.run(plugin._refreshController(device.id))
        controller.zones.running.side_effect = None

        recovered = asyncio.run(plugin._refreshController(device.id))
        recovered_again = asyncio.run(plugin._refreshController(device.id))

        self.assertTrue(recovered)
        self.assertTrue(recovered_again)
        plugin.logger.info.assert_called_once_with(
            "RainMachine recovered: device='{}' id={}".format(
                device.name, device.id
            )
        )
        device.updateStateOnServer.assert_any_call(
            "current_zone", "Orchard", clearErrorState=True
        )
        device.updateStateOnServer.assert_any_call(
            "minutes_left", 2, uiValue="2 min", clearErrorState=True
        )
        device.updateStateOnServer.assert_any_call(
            "current_program", "Morning", clearErrorState=True
        )
        device.updateStateOnServer.assert_any_call(
            "flowmeter", "5 gal", clearErrorState=True
        )
        device.updateStateOnServer.assert_any_call(
            "device_online", value=True, clearErrorState=True
        )

    def test_notification_delay_suppresses_brief_outage_and_updates_state(self):
        plugin = self.make_plugin({"lostDeviceNotificationDelay": "60"})
        plugin.logger = MagicMock()
        device = self.device()
        with patch.object(plugin_module.time, "monotonic", return_value=100):
            plugin._communicationFailed(device, RequestError("timeout"))
        device.updateStateOnServer.assert_called_with("device_online", value=False)
        device.setErrorStateOnServer.assert_called_with("Communication failed")
        with patch.object(plugin_module.time, "monotonic", return_value=159):
            plugin._communicationRecovered(device)
            plugin._flushCommunicationNotifications()
        plugin.logger.error.assert_not_called()
        plugin.logger.info.assert_not_called()

    def test_sustained_outage_logs_without_another_request_and_recovers_once(self):
        plugin = self.make_plugin({"lostDeviceNotificationDelay": "60"})
        plugin.logger = MagicMock()
        device = self.device()
        with patch.object(plugin_module.time, "monotonic", return_value=100):
            plugin._communicationFailed(device, RequestError("timeout"))
        with patch.object(plugin_module.time, "monotonic", return_value=160):
            plugin._flushCommunicationNotifications()
            plugin._communicationFailed(device, RequestError("another timeout"))
            plugin._flushCommunicationNotifications()
            plugin._communicationRecovered(device)
            plugin._communicationRecovered(device)
        plugin.logger.error.assert_called_once()
        plugin.logger.info.assert_called_once()

    def test_delay_changes_apply_to_pending_outage_and_stop_cancels_it(self):
        plugin = self.make_plugin({"lostDeviceNotificationDelay": "60"})
        plugin.logger = MagicMock()
        device = self.device()
        with patch.object(plugin_module.time, "monotonic", return_value=100):
            plugin._communicationFailed(device, RequestError("timeout"))
            plugin.pluginPrefs["lostDeviceNotificationDelay"] = "0"
            plugin._flushCommunicationNotifications()
        plugin.logger.error.assert_called_once()
        plugin.rainmachine_devices[device.id] = "controller"
        plugin.deviceStopComm(device)
        plugin._flushCommunicationNotifications()
        self.assertFalse(plugin._communication_failures)
        plugin.logger.info.assert_not_called()

    def test_timeout_and_notification_preferences(self):
        plugin = self.make_plugin({"requestTimeout": "90"})
        self.assertEqual(plugin.client.request_timeout, 90)
        self.assertEqual(self.make_plugin({}).client.request_timeout, 30)
        for key, values in (("requestTimeout", ("0", "301", "bad")),
                            ("lostDeviceNotificationDelay", ("-1", "bad"))):
            for value in values:
                valid, _, errors = plugin.validatePrefsConfigUi({key: value})
                self.assertFalse(valid)
                self.assertIn(key, errors)
        valid, prefs = plugin.validatePrefsConfigUi({
            "requestTimeout": "90", "lostDeviceNotificationDelay": "60"})
        self.assertTrue(valid)
        self.assertEqual(prefs["requestTimeout"], "90")

    def test_failed_periodic_poll_schedules_ten_second_retry(self):
        plugin = self.make_plugin({"pollInterval": "60"})
        device = self.device()
        controller = self.controller()
        controller.zones.running.side_effect = RequestError("timeout")
        plugin.controllers = {"controller": controller}
        plugin.rainmachine_devices = {device.id: "controller"}
        plugin.next_update_programs = 0
        plugin.logger = MagicMock()

        with patch.object(plugin_module.time, "time", return_value=100.0):
            successful = asyncio.run(plugin.update())

        self.assertFalse(successful)
        self.assertEqual(plugin.next_update_programs, 110.0)


if __name__ == "__main__":
    unittest.main()
