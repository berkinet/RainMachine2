import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "export_zones", ROOT / "tools" / "export_zones.py"
)
export_zones = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_zones)


class ExportZoneTests(unittest.TestCase):
    def test_zone_rows_are_sorted_numerically_and_cleaned(self):
        rows = export_zones._zone_rows(
            {
                "10": {"name": "Pool\nRefill"},
                "2": {"name": "Below\tPool"},
                "1": {"name": "Pool Lawn"},
            }
        )

        self.assertEqual(
            rows,
            [
                ("1", "Pool Lawn"),
                ("2", "Below Pool"),
                ("10", "Pool Refill"),
            ],
        )

    def test_render_tsv(self):
        self.assertEqual(
            export_zones._render_tsv(
                [("1", "Pool Lawn"), ("2", "Below Pool")]
            ),
            "Zone\tName\n1\tPool Lawn\n2\tBelow Pool\n",
        )

    def test_parser_requires_only_the_controller_host(self):
        args = export_zones._parser().parse_args(["192.0.2.1"])
        self.assertEqual(args.host, "192.0.2.1")


if __name__ == "__main__":
    unittest.main()
