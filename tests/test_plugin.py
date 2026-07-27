import importlib.util
import logging
import plistlib
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "Contents" / "Server Plugin"


class PluginBase:
    def __init__(self, plugin_id, display_name, version, prefs):
        self.pluginPrefs = prefs
        self.logger = logging.getLogger("test")

    def __del__(self):
        pass


indigo = ModuleType("indigo")
indigo.PluginBase = PluginBase
indigo.Dict = dict
sys.modules["indigo"] = indigo

aiohttp = ModuleType("aiohttp")
aiohttp.ClientSession = object
sys.modules["aiohttp"] = aiohttp


class Client:
    def __init__(self):
        self.controllers = {}


regenmaschine = ModuleType("regenmaschine")
regenmaschine.Client = Client
sys.modules["regenmaschine"] = regenmaschine

spec = importlib.util.spec_from_file_location(
    "rainmachine2_plugin", SERVER / "plugin.py"
)
plugin_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin_module)


class PollingTests(unittest.TestCase):
    def make_plugin(self, prefs):
        return plugin_module.Plugin(
            "plugin.id", "RainMachine2", "1.0.1", prefs
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
        self.assertEqual(info["PluginVersion"], "1.0.1")

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
        self.assertEqual(packaged_info["PluginVersion"], "1.0.1")
        self.assertIsNotNone(
            packaged_config.find("./Field[@id='pollInterval']")
        )


if __name__ == "__main__":
    unittest.main()
