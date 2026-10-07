#!/usr/bin/env python3
# HPC-GPT Ticket Knowledge Base MCP Server
# Description : Serves the deduplicated/clustered support-ticket Q&A knowledge
#               base over MCP (FTS5/bm25 search) for hpcGPT.
import logging
import argparse
from rich_argparse import RichHelpFormatter

from src.logging import route_fastmcp_logs_to_root, setup_logging
from src.config import TicketMCPConfig as Config
from src.ticket_mcp import TicketMCP


def parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HPC-GPT Ticket Knowledge Base MCP Server",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("-c", "--config",
        type=str,
        default="config.json",
        help='Option to set the config file to use. Defaults to config.json',
    )
    parser.add_argument("--host",
        type=str,
        help="Option to set the host the server will listen on.",
    )
    parser.add_argument("--port",
        type=int,
        help="Option to set the port the server will listen on.",
    )
    parser.add_argument("--data-file",
        type=str,
        help="Option to set an explicit ticket JSON file to index.",
    )
    parser.add_argument("--log-file",
        type=str,
        help="Option to set the file logging will output to.",
    )
    parser.add_argument("-v", "--verbose",
        action="store_true",
        help="Flag to change the log level of the console from INFO to DEBUG",
    )

    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    file_log_level = logging.DEBUG if args.verbose else args.config.log_level
    console_log_level = None
    setup_logging(
        args.log_file,
        log_level=file_log_level,
        console_log_level=console_log_level,
        use_color=True,
        writemode="a",
    )
    route_fastmcp_logs_to_root(file_log_level)
    server = TicketMCP("Ticket MCP Server", args.config)
    server.run(
        transport="http",
        host=args.host,
        port=args.port,
        log_level=None,
        uvicorn_config={"log_config": None},
    )


if __name__ == "__main__":
    args = parse_command_line()
    config = Config.load_from_json(args.config)
    config.host = args.host if args.host else config.host
    config.port = args.port if args.port else config.port
    config.data_file = args.data_file if args.data_file else config.data_file
    config.log_file = args.log_file if args.log_file else config.log_file

    config.validate_config()

    args.host = config.host
    args.port = config.port
    args.log_file = config.log_file
    args.config = config

    main(args)