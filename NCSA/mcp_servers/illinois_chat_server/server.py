import argparse
import asyncio
import json
import logging
import requests
from fastmcp import FastMCP
from rich_argparse import RichHelpFormatter

from src.config import Config, CourseToolConfig, consolidate_config_and_args
from src.logging import route_fastmcp_logs_to_root, setup_logging

class ChatMCP(FastMCP):
    """
    Illinois Chat documentation MCP server.
    """

    def __init__(self, name: str, args: argparse.Namespace):
        super().__init__(name)
        self.illinois_chat_url = args.illinois_chat_url
        self.illinois_chat_api_key = args.illinois_chat_api_key
        self.illinois_chat_model = args.illinois_chat_model
        self.illinois_chat_system_prompt = args.illinois_chat_system_prompt
        self.illinois_chat_timeout = args.illinois_chat_timeout
        self.courses: list[CourseToolConfig] = list(args.courses or [])

        if not self.courses:
            raise ValueError(
                "No courses configured. Add at least one entry to the 'courses' "
                "list in config.json."
            )

        registered_tools = 0
        for course in self.courses:
            # If the model or system prompt is not specified, use the default values
            if not course.model:
                course.model = self.illinois_chat_model
            if not course.system_prompt:
                course.system_prompt = self.illinois_chat_system_prompt
            try:
                if self._verify_course(course):
                    self._register_course_tool(course)
                    registered_tools += 1
            except RuntimeError as e:
                logging.error(f"Failed to verify course {course.name}: {e}")
                continue

        if registered_tools == 0:
            raise RuntimeError(
                "No course tools were verified and registered. "
                "Check illinois_chat_url, illinois_chat_api_key, and course names."
            )

    def _register_course_tool(self, course: CourseToolConfig) -> None:
        """Register an MCP tool that retrieves against one Illinois Chat course."""

        # Factory keeps each course_name correctly bound without exposing it as
        # an MCP tool parameter.
        def make_tool(course: CourseToolConfig):
            async def tool_fn(query: str) -> str:
                return await self._send_request_to_illinois_chat(course, query)

            return tool_fn

        tool_name = "query_" + course.name
        tool_fn = make_tool(course)
        tool_fn.__name__ = tool_name
        tool_fn.__doc__ = f"""
        {course.description}

        Args:
            query: The user query to retrieve documentation for.

        Returns:
            Retrieved documentation context from the Illinois Chat course.
        """
        self.add_tool(tool_fn)
        logging.info(
            "Registered course tool %s -> course_name=%s", tool_name, course.name
        )

    async def _send_request_to_illinois_chat(self, course: CourseToolConfig, query: str) -> str:
        request_data = {
            "model": course.model,
            "messages": [
                {"role": "system", "content": course.system_prompt},
                {"role": "user", "content": query},
            ],
            "api_key": self.illinois_chat_api_key,
            "course_name": course.name,
            "stream": False,
            "temperature": 0.3,
            "retrieval_only": True,
            "top_n": 10,
        }
        try:
            response = await asyncio.to_thread(
                requests.post,
                self.illinois_chat_url,
                json=request_data,
                timeout=self.illinois_chat_timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Illinois Chat retrieval failed: {exc}") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to send request to Illinois Chat API: "
                f"{response.status_code} {response.text}"
            )
        data = response.json()
        logging.info("Illinois Chat API Response: %s", data)
        if "contexts" in data:
            contexts = data["contexts"]
            if not contexts:
                return "No relevant documentation context was found."
            if isinstance(contexts, str):
                return contexts
            return json.dumps(contexts, ensure_ascii=True)
        if "message" in data:
            return data["message"]
        if (
            "choices" in data
            and data["choices"]
            and data["choices"][0]
            and "message" in data["choices"][0]
        ):
            return data["choices"][0]["message"]["content"]
        if "response" in data:
            return data["response"]
        raise RuntimeError(f"Unexpected response format: {data}")

    def _verify_course(self, course: CourseToolConfig) -> None:
        """
        Verify the connection to the chat API. POST a minimal chat request to confirm the URL is reachable and the API key is accepted.

        Raises:
            RuntimeError: If the URL cannot be reached, returns unexpected status, or the response is not JSON.
        """
        verification_prompt = "This is a test message to verify the connection to the chat API is valid. Please respond with a simple message saying 'Hello, world!'."
        payload = {
            "model": course.model,
            "messages": [
                {"role": "system", "content": course.system_prompt},
                {"role": "user", "content": verification_prompt},
            ],
            "api_key": self.illinois_chat_api_key,
            "course_name": course.name,
            "stream": False,
            "temperature": 0.3,
            "retrieval_only": True,
        }
        try:
            response = requests.post(
                self.illinois_chat_url,
                json=payload,
                timeout=self.illinois_chat_timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Illinois Chat URL is unreachable or invalid: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"Illinois Chat API rejected the API key (HTTP {response.status_code})."
            )
        if response.status_code == 404:
            raise RuntimeError(
                "Illinois Chat API returned HTTP 404; check illinois_chat_url."
            )
        if response.status_code != 200:
            snippet = (response.text or "")[:500]
            raise RuntimeError(
                f"Failed to connect to the Illinois Chat API: HTTP {response.status_code} {snippet}"
            )

        try:
            response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Illinois Chat API returned a non-JSON body; check illinois_chat_url."
            ) from exc

        logging.info(f"Chat API connection verified for course {course.name}.")
        return True


def parse_command_line():
    parser = argparse.ArgumentParser(
        description="HPC-GPT Documentation retrieval MCP server",
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
    parser.add_argument("--illinois-chat-url",
        type=str,
        help="Option to set the URL of the Illinois Chat API.",
    )
    parser.add_argument("--illinois-chat-api-key",
        type=str,
        help="Option to set the API key of the Illinois Chat API.",
    )
    parser.add_argument("--illinois-chat-model",
        type=str,
        help="Option to set the Illinois Chat model name.",
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


def main(args):
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

    server = ChatMCP("Illinois Chat MCP Server", args)
    server.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        log_level=None,
        uvicorn_config={"log_config": None},
    )


if __name__ == "__main__":
    # Load config
    args = parse_command_line()
    config = Config.load_from_json(args.config)
    args = consolidate_config_and_args(config, args)

    main(args)
