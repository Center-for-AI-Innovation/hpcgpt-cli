import argparse
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

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
    transport: Literal["streamable-http", "stdio"] = Field(
        default="streamable-http",
        description="MCP transport: streamable-http or stdio")
    identity_mode: Literal["explicit", "process"] = Field(
        default="explicit",
        description="Use an explicit tool username or the MCP process Unix user")

    @classmethod
    def load_from_json(cls, filepath: str = "config.json") -> "Config":
        path = Path(filepath)
        if not path.exists() and filepath == "config.json":
            return cls()
        return cls.model_validate_json(path.read_text())

def consolidate_config_and_args(config: Config, args: argparse.Namespace):
    # Merge config and args into a single args, with args taking precedence
    for key, value in config.__dict__.items():
        if key not in args.__dict__ or args.__dict__[key] is None:
            args.__dict__[key] = value
    return args
