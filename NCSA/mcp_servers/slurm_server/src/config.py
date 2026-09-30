import argparse
from typing import Any, List, Optional

from pydantic import BaseModel, Field, model_validator

DEFAULT_COMMANDS = ["sinfo", "squeue", "scontrol", "accounts", "jobcharge"]

class CommandToolConfig(BaseModel):
    """Maps a command on the host to an MCP tool exposed by this server."""

    name: str = Field(
        description="The command to run, which is also the MCP tool name exposed to clients (e.g. sinfo)",
    )
    description: Optional[str] = Field(
        default=None,
        description=(
            "Option to specify the summary line placed above the command's own "
            "--help output in the tool description, otherwise a generic summary "
            "is used"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _allow_bare_name(cls, value: Any) -> Any:
        # Let a command be written as just its name, e.g. "commands": ["sinfo"]
        if isinstance(value, str):
            return {"name": value}
        return value


class Config(BaseModel):
    host: str = Field(
        default="127.0.0.1", 
        description="The host ip address for the server to listen on")
    port: int = Field(
        default=8001, 
        description="The port for the server to listen on")
    log_file: str = Field(
        default="logs/Latest.log", 
        description="The file to write server logs to")
    commands: List[CommandToolConfig] = Field(
        default_factory=lambda: [CommandToolConfig(name=c) for c in DEFAULT_COMMANDS],
        description=(
            "Commands to expose as MCP tools. Each entry is either a command "
            "name or an object with a name and an optional description. A "
            "command that is not on PATH is skipped at startup."
        ),
    )
    command_timeout: int = Field(
        default=30,
        description="The timeout in seconds for running a command, including the --help probe at startup")
    max_help_chars: int = Field(
        default=4000,
        description="Maximum number of characters of --help output to keep in a tool description, or 0 for no limit")

    @classmethod
    def load_from_json(cls, filepath: str = "config.json") -> "Config":
        with open(filepath, "r") as f:
            return cls.model_validate_json(f.read())

def consolidate_config_and_args(config: Config, args: argparse.Namespace):
    # Merge config and args into a single args, with args taking precedence
    for key, value in config.__dict__.items():
        # argparse stores "--log-file" as "log_file", so look up the key as-is
        if args.__dict__.get(key) is None:
            args.__dict__[key] = value
    return args
