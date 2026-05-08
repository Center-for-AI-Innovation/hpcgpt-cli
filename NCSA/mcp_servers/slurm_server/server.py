import logging
import argparse
import shlex
import subprocess
from rich_argparse import RichHelpFormatter
from fastmcp import FastMCP

from src.config import Config, consolidate_config_and_args
from src.logging import route_fastmcp_logs_to_root, setup_logging

class SlurmMCP(FastMCP):
    """
    Slurm MCP Server.
    """
    def __init__(self, name: str, args: argparse.Namespace):
        super().__init__(name)

        self.add_tool(self.accounts)
        self.add_tool(self.sinfo)
        self.add_tool(self.squeue)
        self.add_tool(self.scontrol)

    def _run_command(self, base_command: str, arg_string: str = "") -> str:
        """
        Run a command with optional shell-style args and return output.
        """
        command = [base_command]
        if arg_string and arg_string.strip():
            command.extend(shlex.split(arg_string))

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return f"Error: command not found: {base_command}"
        except Exception as exc:
            return f"Error running {' '.join(command)}: {exc}"

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            details = stderr or stdout or "No error output"
            return f"Error ({result.returncode}) running {' '.join(command)}: {details}"

        return result.stdout

    async def accounts(self, username: str) -> str:
        """
        Run the accounts command with the given username and return the output.

        Args:
            username: The system username to run the accounts command for.

        Returns:
            The output of the accounts command.
        """
        result = subprocess.run(["accounts", "-u", username], capture_output=True, text=True)
        return result.stdout

    async def sinfo(self, sinfo_args: str = "") -> str:
        """
        Run the sinfo command with the given arguments and return the output.

        Args:
            sinfo_args: The arguments to pass to the sinfo command.

        Returns:
            The output of the sinfo command.
        """
        return self._run_command("sinfo", sinfo_args)

    async def squeue(self, squeue_args: str = "") -> str:
        """
        Run the squeue command with the given arguments and return the output.

        Args:
            squeue_args: The arguments to pass to the squeue command.

        Returns:
            The output of the squeue command.
        """
        return self._run_command("squeue", squeue_args)

    async def scontrol(self, job_id: str, scontrol_args: str = "") -> str:
        """
        Run the scontrol command with the given arguments and return the output.

        Args:
            job_id: The job ID to run the scontrol command for.
            scontrol_args: The arguments to pass to the scontrol command.

        Returns:
            The output of the scontrol command.
        """
        command_args = scontrol_args.strip()
        if job_id and job_id.strip():
            command_args = f"show job {job_id}" + (f" {command_args}" if command_args else "")
        return self._run_command("scontrol", command_args)

def parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Slurm MCP Server",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("-c", "--config",
        type=str,
        default="config.json",
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

def main(args: argparse.Namespace) -> None:
    file_log_level = logging.DEBUG if args.verbose else logging.INFO
    console_log_level = None
    setup_logging(
        args.log_file,
        log_level=file_log_level,
        console_log_level=console_log_level,
        use_color=True,
        writemode="a",
    )
    route_fastmcp_logs_to_root(file_log_level)

    server = SlurmMCP("Slurm MCP Server", args)
    server.run(transport="streamable-http", host=args.host, port=args.port, log_level=None, uvicorn_config={"log_config": None})

if __name__ == "__main__":
    # Load config and args
    args = parse_command_line()
    config = Config.load_from_json(args.config)
    args = consolidate_config_and_args(config, args)

    main(args)
