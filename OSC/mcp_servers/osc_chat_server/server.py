import argparse
import logging
import requests
from fastmcp import FastMCP
from rich_argparse import RichHelpFormatter

from src.config import Config, consolidate_config_and_args
from src.logging import route_fastmcp_logs_to_root, setup_logging

class ChatMCP(FastMCP):
    """
    OSC Chat documentation MCP server.
    """

    def __init__(self, name: str, args: argparse.Namespace):
        super().__init__(name)
        self.osc_chat_url = args.osc_chat_url
        self.osc_chat_api_key = args.osc_chat_api_key
        self.osc_chat_model = args.osc_chat_model
        self.osc_chat_system_prompt = args.osc_chat_system_prompt

        self.add_tool(self.query_osc_documentation)

    async def _send_request_to_osc_chat(self, course_name: str, query: str) -> str:
        request_data = {
            "model": self.osc_chat_model,
            "messages": [
                {"role": "system", "content": self.osc_chat_system_prompt},
                {"role": "user", "content": query},
            ],
            "api_key": self.osc_chat_api_key,
            "course_name": course_name,
            "stream": False,
            "temperature": 0.3,
            "retrieval_only": False,
        }
        response = requests.post(self.osc_chat_url, json=request_data)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to send request to OSC Chat API: "
                f"{response.status_code} {response.text}"
            )
        data = response.json()
        logging.info("OSC Chat API Response: %s", data)
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

    async def query_osc_documentation(self, query: str) -> str:
        """
        Query the OSC documentation with the given query and return the output.

        Args:
            query: The query to pass to the osc-docs command.

        Returns:
            The output of the osc-docs command.
        """
        return await self._send_request_to_osc_chat("OSCDocs", query)

    def verify_chat_connection(self, timeout: float = 30) -> None:
        """
        Verify the connection to the chat API. POST a minimal chat request to confirm the URL is reachable and the API key is accepted.

        Raises:
            RuntimeError: If the URL cannot be reached, returns unexpected status, or the response is not JSON.
        """
        verification_prompt = "This is a test message to verify the connection to the chat API is valid. Please respond with a simple message saying 'Hello, world!'."
        payload = {
            "model": self.osc_chat_model,
            "messages": [
                {"role": "system", "content": self.osc_chat_system_prompt},
                {"role": "user", "content": verification_prompt},
            ],
            "api_key": self.osc_chat_api_key,
            "course_name": "OSCDocs",
            "stream": False,
            "temperature": 0.3,
            "retrieval_only": True,
        }
        try:
            response = requests.post(
                self.osc_chat_url,
                json=payload,
                timeout=timeout,
                headers={"x-osc-wait": "true"}
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"OSC Chat URL is unreachable or invalid: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"OSC Chat API rejected the API key (HTTP {response.status_code})."
            )
        if response.status_code == 404:
            raise RuntimeError(
                "OSC Chat API returned HTTP 404; check osc_chat_url."
            )
        if response.status_code != 200:
            snippet = (response.text or "")[:500]
            raise RuntimeError(
                f"OSC Chat API check failed: HTTP {response.status_code} {snippet}"
            )

        try:
            response.json()
        except ValueError as exc:
            raise RuntimeError(
                "OSC Chat API returned a non-JSON body; check osc_chat_url."
            ) from exc

        logging.info("Chat API connection verified.")

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
    parser.add_argument("--osc-chat-url",
        type=str,
        help="Option to set the URL of the OSC Chat API.",
    )
    parser.add_argument("--osc-chat-api-key",
        type=str,
        help="Option to set the API key of the OSC Chat API.",
    )
    parser.add_argument("--osc-chat-model",
        type=str,
        help="Option to set the OSC Chat model name.",
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

    server = ChatMCP("OSC Chat MCP Server", args)
    server.verify_chat_connection()
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
