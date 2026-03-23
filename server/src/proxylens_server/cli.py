from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
from pathlib import Path

import uvicorn

from proxylens_server.app import create_app
from proxylens_server.config import ServerConfig

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
LOG_LEVELS = ("critical", "error", "warning", "info", "debug", "trace")
DATA_DIR_ENV_VAR = "PROXYLENS_SERVER_CLI_DATA_DIR"
FILTER_SCRIPT_ENV_VAR = "PROXYLENS_SERVER_CLI_FILTER_SCRIPT"


def _parse_bind(value: str) -> tuple[str, int]:
    host, separator, port_text = value.rpartition(":")
    if not separator or not host or not port_text:
        raise argparse.ArgumentTypeError("bind address must be in the form host:port")

    try:
        port = int(port_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc

    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")

    return host, port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proxylens-server",
        description="Run the ProxyLens server with uvicorn.",
    )
    parser.add_argument(
        "--bind",
        metavar="HOST:PORT",
        type=_parse_bind,
        help=f"Bind address for the server (default: {DEFAULT_HOST}:{DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help=f"Server host (default: {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Server port (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVELS,
        default="info",
        help="Uvicorn log level.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory used for server state and SQLite data.",
    )
    parser.add_argument(
        "--filter-script",
        type=Path,
        default=None,
        help="Optional filter script loaded on startup.",
    )
    parser.add_argument(
        "--access-log",
        dest="access_log",
        action="store_true",
        default=True,
        help="Enable uvicorn access logs.",
    )
    parser.add_argument(
        "--no-access-log",
        dest="access_log",
        action="store_false",
        help="Disable uvicorn access logs.",
    )
    return parser


def _build_config(data_dir: Path | None, filter_script: Path | None) -> ServerConfig:
    return ServerConfig(
        data_dir=(data_dir or Path(".proxylens-server-data")).resolve(),
        filter_script=filter_script.resolve() if filter_script is not None else None,
    )


def create_app_from_cli():
    data_dir_value = os.environ.get(DATA_DIR_ENV_VAR)
    filter_script_value = os.environ.get(FILTER_SCRIPT_ENV_VAR)
    config = _build_config(
        Path(data_dir_value) if data_dir_value is not None else None,
        Path(filter_script_value) if filter_script_value is not None else None,
    )
    return create_app(config)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.bind is not None:
        host, port = args.bind
    else:
        host = args.host or DEFAULT_HOST
        port = args.port if args.port is not None else DEFAULT_PORT

    if not 0 <= port <= 65535:
        parser.error("port must be between 0 and 65535")
    if args.workers < 1:
        parser.error("workers must be at least 1")
    if args.reload and args.workers != 1:
        parser.error("workers must be 1 when reload is enabled")

    config = _build_config(args.data_dir, args.filter_script)
    os.environ[DATA_DIR_ENV_VAR] = str(config.data_dir)
    if config.filter_script is None:
        os.environ.pop(FILTER_SCRIPT_ENV_VAR, None)
    else:
        os.environ[FILTER_SCRIPT_ENV_VAR] = str(config.filter_script)

    uvicorn.run(
        "proxylens_server.cli:create_app_from_cli",
        host=host,
        port=port,
        log_level=args.log_level,
        reload=args.reload,
        workers=args.workers,
        access_log=args.access_log,
        factory=True,
    )
    return 0
