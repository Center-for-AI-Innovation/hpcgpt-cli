import argparse
import asyncio
import json
import logging
import requests
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from rich_argparse import RichHelpFormatter
from starlette.requests import Request

from src.config import Config, consolidate_config_and_args
from src.logging import route_fastmcp_logs_to_root, setup_logging

class ChatMCP(FastMCP):
    """
    hpcGPT Chat documentation MCP server.
    """

    def __init__(self, name: str, args: argparse.Namespace):
        super().__init__(name)
        self.url = args.url
        self.api_key = args.api_key
        self.model = args.model
        self.system_prompt = args.system_prompt
        self.timeout = args.timeout
        self.add_tool(self.query_docs)

    async def _send_request(self, course_name: str, query: str) -> str:
        request_data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": query},
            ],
            "api_key": self.api_key,
            "course_name": course_name,
            "stream": False,
            "temperature": 0.3,
            "retrieval_only": True,
        }
        response = requests.post(self.url, json=request_data)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to send request to hpcGPT Chat API: "
                f"{response.status_code} {response.text}"
            )
        data = response.json()
        logging.info("hpcGPT Chat API Response: %s", data)
        if "contexts" in data:
            contexts = data["contexts"]
            if not contexts:
                return "No relevant documentation context was found."
            if isinstance(contexts, str):
                return contexts
            return json.dumps(contexts[:10], ensure_ascii=True)
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

    async def query_docs(self, query: str) -> str:
        """
        Query the documentation with the given query and return the output.

        Args:
            query: The query to pass to the sdsctest command.

        Returns:
            The output of the sdsctest command.
        """
        return await self._send_request("sdsctest-072326", query)

    def verify_connection(self) -> None:
        """
        Verify the connection to the hpcGPT Chat API. POST a minimal chat request to confirm the URL is reachable and the API key is accepted.

        Raises:
            RuntimeError: If the URL cannot be reached, returns unexpected status, or the response is not JSON.
        """
        verification_prompt = "This is a test message to verify the connection to the hpcGPT Chat API is valid. Please respond with a simple message saying 'Hello, world!'."
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": verification_prompt},
            ],
            "api_key": self.api_key,
            "course_name": "sdsctest-072326",
            "stream": False,
            "temperature": 0.3,
            "retrieval_only": True,
        }
        try:
            response = requests.post(
                self.url,
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"hpcGPT Chat URL is unreachable or invalid: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"hpcGPT Chat API rejected the API key (HTTP {response.status_code})."
            )
        if response.status_code == 404:
            raise RuntimeError(
                "hpcGPT Chat API returned HTTP 404; check url."
            )
        if response.status_code != 200:
            snippet = (response.text or "")[:500]
            raise RuntimeError(
                f"hpcGPT Chat API check failed: HTTP {response.status_code} {snippet}"
            )

        try:
            response.json()
        except ValueError as exc:
            raise RuntimeError(
                "hpcGPT Chat API returned a non-JSON body; check url."
            ) from exc

        logging.info("hpcGPT Chat API connection verified.")

def parse_command_line():
    parser = argparse.ArgumentParser(
        description="hpcGPT Chat Documentation Retrieval MCP Server",
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
    parser.add_argument("--url",
        type=str,
        help="Option to set the URL of the Chat API.",
    )
    parser.add_argument("--api-key",
        type=str,
        help="Option to set the API key of the Chat API.",
    )
    parser.add_argument("--model",
        type=str,
        help="Option to set the Chat model name.",
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

    server = ChatMCP("Chat MCP Server", args)
    server.verify_connection()
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
