#!/usr/bin/env python3
# HPC-GPT Ticket Reporting MCP Server
# Author : Albert Bode
# Description : 

import logging
import argparse
from rich_argparse import RichHelpFormatter

from src.logging import route_fastmcp_logs_to_root, setup_logging
from src.config import ReportMCPConfig as Config
from src.report_mcp import ReportMCP, SupportReportToolParameters

def parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HPC-GPT Support Reporting MCP Server",
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
    parser.add_argument("--log-file",
        type=str,
        help="Option to set the file logging will output to.",
    )
    parser.add_argument("-v","--verbose",
        action="store_true",
        help="Flag to change the log level of the console from INFO to DEBUG",
    )
    
    return parser.parse_args()

def test_issue_creation(server: ReportMCP) -> None:
    """
    Test the issue creation functionality of the MCP server. This submits a single pre-defined issue to the Jira instance.
    """
    import asyncio
    asyncio.run(server.send_support_report(
        SupportReportToolParameters(
            title="Test Issue Creation",
            description="This is a test of the issue creation functionality of the MCP server.",
            conversation_history=[{"role": "assistant", "content": "Provide me a prompt."}, {"role": "user", "content": "this is some thing that the user said"}],
            hostname="dummy.mycenter.edu",
            user="fakeuser",
            current_working_directory="/home/testing/"
        )
    ))

    # available_fields = server.jira.get_custom_field_ids(project=server.config.jira.project, issue_type=server.config.jira.issue_type)
    # for field in server.config.jira.default_fields:
    #     log.info(f"Setting field {field} to {server.config.jira.default_fields[field]}")
    #     if field in available_fields:
    #         server.jira.set_issue_field(issue_key="CMAAS-38", field_name=field, field_value=server.config.jira.default_fields[field])


def main(args: argparse.Namespace) -> None:
    # Setup logging
    file_log_level = logging.DEBUG if args.verbose else args.config.log_level
    console_log_level = None
    log = setup_logging(
        args.log_file,
        log_level=file_log_level,
        console_log_level=console_log_level,
        use_color=True,
        writemode="a",
    )
    route_fastmcp_logs_to_root(file_log_level)

    # Initialize server
    server = ReportMCP("Report MCP Server", args.config)
    if args.config.mode == "jira":
        server.jira.connect(auth_method=server.config.jira.authentication_method)

    ### For testing issue creation
    # test_issue_creation(server)

    ### Normal Use
    server.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        log_level=None,
        uvicorn_config={"log_config": None},
    )

if __name__ == "__main__":
    # Load config and args
    args = parse_command_line()
    config = Config.load_from_json(args.config)
    config.validate_config()

    # Merge config values into args, with args taking precedence
    args.host = config.host if config.host else args.host
    args.port = config.port if config.port else args.port
    args.log_file = config.log_file if config.log_file else args.log_file
    args.config = config
    
    main(args)
