import logging
import argparse
import asyncio
import re
import shlex
import shutil
import subprocess
from rich_argparse import RichHelpFormatter
from fastmcp import FastMCP
from fastmcp.tools import Tool

from src.config import CommandToolConfig, Config, consolidate_config_and_args
from src.logging import route_fastmcp_logs_to_root, setup_logging

# Flags tried, in order, when reading a command's help text at startup.
HELP_FLAGS = ("--help", "-h")

class SlurmMCP(FastMCP):
    """
    Slurm MCP Server.

    Exposes one tool per command listed in the `commands` config entry. Each
    tool's description is built from that command's own help output, which is
    read once at startup.
    """
    def __init__(self, name: str, args: argparse.Namespace):
        super().__init__(name)
        self.command_timeout = args.command_timeout
        self.max_help_chars = args.max_help_chars
        self.commands: list[CommandToolConfig] = list(args.commands or [])

        if not self.commands:
            raise ValueError(
                "No commands configured. Add at least one entry to the "
                "'commands' list in config.json."
            )

        registered_tools = 0
        for command in self.commands:
            try:
                self._register_command_tool(command)
                registered_tools += 1
            except FileNotFoundError as exc:
                logging.warning("Skipping command %s: %s", command.name, exc)
                continue
            except Exception as exc:
                logging.error(
                    "Failed to register tool for command %s: %s", command.name, exc
                )
                continue

        if registered_tools == 0:
            raise RuntimeError(
                "No command tools were registered. Check that the commands in "
                "the 'commands' list of config.json exist on PATH."
            )

        logging.info(
            "Registered %d of %d configured command tools.",
            registered_tools,
            len(self.commands),
        )

    def _register_command_tool(self, command: CommandToolConfig) -> None:
        """Register an MCP tool that runs one configured command."""

        executable = shutil.which(command.name)
        if executable is None:
            raise FileNotFoundError(f"command not found on PATH: {command.name}")

        tool_name = re.sub(r"[^A-Za-z0-9_-]", "_", command.name)

        # Factory keeps each command correctly bound without exposing it as an
        # MCP tool parameter.
        def make_tool(command_name: str):
            async def tool_fn(args: str = "") -> str:
                return await asyncio.to_thread(self._run_command, command_name, args)

            return tool_fn

        tool_fn = make_tool(command.name)
        tool_fn.__name__ = tool_name
        # Only the Args section of this docstring is used; the tool description
        # is passed to from_function instead so the help text is not reindented.
        tool_fn.__doc__ = f"""
        Run the {command.name} command.

        Args:
            args: Arguments to pass to the {command.name} command, as a single shell-style string. Pass an empty string to run it with no arguments.

        Returns:
            The output of the {command.name} command.
        """
        self.add_tool(
            Tool.from_function(
                tool_fn,
                name=tool_name,
                description=self._build_description(command),
            )
        )
        logging.info("Registered command tool %s -> %s", tool_name, executable)

    def _build_description(self, command: CommandToolConfig) -> str:
        """Build a tool description from the command's own help output."""
        summary = command.description or (
            f"Run the {command.name} command on this cluster and return its output."
        )
        help_text = self._read_help_text(command.name)
        if not help_text:
            return summary
        return (
            f"{summary}\n\n"
            f"Usage and supported flags, from `{command.name} {HELP_FLAGS[0]}`:\n\n"
            f"{help_text}"
        )

    def _read_help_text(self, command_name: str) -> str:
        """
        Read a command's help output, trying each flag in HELP_FLAGS in turn.

        Returns an empty string if no flag produced any output, in which case
        the tool is still registered with a generic description.
        """
        fallback = ""
        for flag in HELP_FLAGS:
            try:
                result = subprocess.run(
                    [command_name, flag],
                    capture_output=True,
                    text=True,
                    check=False,
                    stdin=subprocess.DEVNULL,
                    timeout=self.command_timeout,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                logging.warning("Could not run %s %s: %s", command_name, flag, exc)
                continue

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            # Some commands print their usage to stderr, so take whichever
            # stream has content.
            if result.returncode == 0 and (stdout or stderr):
                return self._truncate_help_text(command_name, stdout or stderr)
            fallback = fallback or stdout or stderr

        if fallback:
            # Every flag exited non-zero, but the command still printed
            # something usage-like; better than no description at all.
            logging.warning(
                "%s exited non-zero for every flag in %s; using its output as "
                "the tool description anyway.",
                command_name,
                ", ".join(HELP_FLAGS),
            )
            return self._truncate_help_text(command_name, fallback)

        logging.warning(
            "No help output from %s; registering it with a generic description.",
            command_name,
        )
        return ""

    def _truncate_help_text(self, command_name: str, help_text: str) -> str:
        """Cap help text so one verbose command cannot dominate the tool list."""
        if self.max_help_chars <= 0 or len(help_text) <= self.max_help_chars:
            return help_text
        logging.info(
            "Truncated help output for %s from %d to %d characters.",
            command_name,
            len(help_text),
            self.max_help_chars,
        )
        return help_text[: self.max_help_chars].rstrip() + "\n... (help output truncated)"

    def _run_command(self, base_command: str, arg_string: str = "") -> str:
        """
        Run a command with optional shell-style args and return output.
        """
        command = [base_command]
        if arg_string and arg_string.strip():
            try:
                command.extend(shlex.split(arg_string))
            except ValueError as exc:
                return f"Error: could not parse arguments for {base_command}: {exc}"

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                stdin=subprocess.DEVNULL,
                timeout=self.command_timeout,
            )
        except FileNotFoundError:
            return f"Error: command not found: {base_command}"
        except subprocess.TimeoutExpired:
            return (
                f"Error: {' '.join(command)} timed out after "
                f"{self.command_timeout} seconds"
            )
        except Exception as exc:
            return f"Error running {' '.join(command)}: {exc}"

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            details = stderr or stdout or "No error output"
            return f"Error ({result.returncode}) running {' '.join(command)}: {details}"

        return result.stdout

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
    parser.add_argument("--command-timeout",
        type=int,
        help="Option to set the timeout in seconds for running a command.",
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
