#!/usr/bin/env python3
"""hpcGPT usage-stats ingest server.

Receives session launch/duration reports from the hpc-gpt wrapper and stores
them in SQLite for later analysis.
"""
import argparse
import logging

import uvicorn
from rich_argparse import RichHelpFormatter

from src.app import create_app
from src.config import Config
from src.store import SessionStore


def parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="hpcGPT Usage Stats Server",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.json",
        help="Config file to use. Defaults to config.json",
    )
    parser.add_argument(
        "--host",
        type=str,
        help="Host the server will listen on.",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port the server will listen on.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="SQLite database path for session records.",
    )
    return parser.parse_args()


def main(config: Config) -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    store = SessionStore(config.db_path)
    app = create_app(store)
    logging.info("Starting usage-stats server on %s:%s (db=%s)", config.host, config.port, config.db_path)
    uvicorn.run(app, host=config.host, port=config.port, log_level=config.log_level.lower())


if __name__ == "__main__":
    args = parse_command_line()
    try:
        config = Config.load_from_json(args.config)
    except FileNotFoundError:
        logging.warning("Config file %s not found; using defaults", args.config)
        config = Config()

    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.db_path:
        config.db_path = args.db_path

    config.validate_config()
    main(config)
