import argparse
from typing import List, Optional

from pydantic import BaseModel, Field

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant that can answer questions about high-performance computing (HPC) systems, software, and general HPC concepts. You provide clear, accurate, and concise responses to a wide range of HPC-related topics."
)

class CourseToolConfig(BaseModel):
    """Maps an Illinois Chat course to an MCP tool exposed by this server."""

    name: str = Field(
        description="MCP tool name exposed to clients (e.g. query_delta_documentation)",
    )
    description: str = Field(
        description="Tool description shown to the model for when to use this tool",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Option to specify the system prompt to prepend to the tool's request, otherwise the default system prompt will be used",
    )
    model: Optional[str] = Field(
        default=None,
        description="Option to specify the model to use for the tool, otherwise the default model will be used",
    )


class Config(BaseModel):
    host: str = Field(
        default="0.0.0.0",
        description="The host ip address for the server to listen on")
    port: int = Field(
        default=8000,
        description="The port for the server to listen on")
    log_file: str = Field(
        default="logs/Latest.log",
        description="The file to write server logs to")
    illinois_chat_url: str = Field(
        description="The URL of the Illinois Chat API, can also be set with the ILLINOIS_CHAT_URL environment variable",
        json_schema_extra={"env": "ILLINOIS_CHAT_URL"})
    illinois_chat_api_key: str = Field(
        description="API key for the Illinois Chat API, can also be set with the ILLINOIS_CHAT_API_KEY environment variable",
        json_schema_extra={"env": "ILLINOIS_CHAT_API_KEY"})
    illinois_chat_model: str = Field(
        description="The model to use for the Illinois Chat API, can also be set with the ILLINOIS_CHAT_MODEL environment variable",
        json_schema_extra={"env": "ILLINOIS_CHAT_MODEL"})
    illinois_chat_system_prompt: str = Field(
        default=DEFAULT_SYSTEM_PROMPT,
        description="System message prepended to each Illinois Chat API request")
    illinois_chat_timeout: int = Field(
        default=30,
        description="The timeout in seconds for the Illinois Chat API request")
    courses: List[CourseToolConfig] = Field(
        default_factory=lambda: [CourseToolConfig.model_validate(c) for c in DEFAULT_COURSES],
        description=(
            "Illinois Chat courses to expose as MCP tools. Each entry maps a "
            "tool_name to a course_name and description."
        ),
    )

    @classmethod
    def load_from_json(cls, filepath: str = "config.json") -> "Config":
        with open(filepath, "r") as f:
            return cls.model_validate_json(f.read())


def consolidate_config_and_args(config: Config, args: argparse.Namespace):
    # Merge config and args into a single args, with args taking precedence
    for key, value in config.__dict__.items():
        if key.replace("_", "-") not in args.__dict__ or args.__dict__[key] is None:
            args.__dict__[key] = value
    return args
