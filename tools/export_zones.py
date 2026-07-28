#!/usr/bin/env python3
"""Export a local RainMachine controller's zone list as tab-separated text."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from typing import Any, Mapping, Sequence


def _sort_key(item: tuple[Any, Any]) -> tuple[int, Any]:
    try:
        return 0, int(item[0])
    except (TypeError, ValueError):
        return 1, str(item[0])


def _clean(value: Any) -> str:
    return " ".join(str(value).split())


def _zone_rows(zones: Mapping[Any, Mapping[str, Any]]) -> list[tuple[str, str]]:
    return [
        (_clean(zone_id), _clean(zone.get("name", "")))
        for zone_id, zone in sorted(zones.items(), key=_sort_key)
    ]


def _render_tsv(rows: Sequence[tuple[str, str]]) -> str:
    lines = ["Zone\tName"]
    lines.extend(f"{zone_id}\t{name}" for zone_id, name in rows)
    return "\n".join(lines) + "\n"


async def _fetch_zones(
    host: str,
    password: str,
    port: int | None,
    use_ssl: bool | None,
) -> list[tuple[str, str]]:
    try:
        from aiohttp import ClientSession
        from regenmaschine import Client
    except ImportError as error:
        raise RuntimeError(
            "This tool requires aiohttp and regenmaschine. Install them with "
            "'python3 -m pip install aiohttp regenmaschine'."
        ) from error

    options: dict[str, Any] = {}
    if port is not None:
        options["port"] = port
    if use_ssl is not None:
        options["use_ssl"] = use_ssl

    async with ClientSession() as session:
        client = Client(session=session)
        await client.load_local(host, password, **options)

        controllers = list(client.controllers.values())
        if not controllers:
            raise RuntimeError("RainMachine returned no controllers.")
        if len(controllers) != 1:
            raise RuntimeError(
                f"Expected one local controller, received {len(controllers)}."
            )

        zones = await controllers[0].zones.all()
        return _zone_rows(zones)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export zone numbers and names from a local RainMachine controller."
        )
    )
    parser.add_argument("host", help="RainMachine IP address or hostname")
    parser.add_argument(
        "--port",
        type=int,
        help="override the regenmaschine default port",
    )
    protocol = parser.add_mutually_exclusive_group()
    protocol.add_argument(
        "--https",
        dest="use_ssl",
        action="store_true",
        help="use HTTPS",
    )
    protocol.add_argument(
        "--http",
        dest="use_ssl",
        action="store_false",
        help="use HTTP",
    )
    parser.set_defaults(use_ssl=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    password = os.environ.get("RAINMACHINE_PASSWORD")
    if password is None:
        password = getpass.getpass("RainMachine password: ")

    try:
        rows = asyncio.run(
            _fetch_zones(
                args.host,
                password,
                args.port,
                args.use_ssl,
            )
        )
        output = _render_tsv(rows)
        sys.stdout.write(output)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
