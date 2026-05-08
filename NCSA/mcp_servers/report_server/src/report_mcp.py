from __future__ import annotations

import logging
import subprocess
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.config import ReportMCPConfig
from src.jira_connector import JiraConnectionManager

log = logging.getLogger("REPORT_MCP_SERVER")

class ConversationHistoryMessage(BaseModel):
    role: str = Field(
        description="The role of the message, should be either 'user' or 'assistant' or 'system'.")
    content: str = Field(
        description="The content of the message.")

class SupportReportToolParameters(BaseModel):
    title: str = Field(
        description="The title of the report ticket to send.")
    description: str = Field(
        description="A short one paragraph description of the issue that is being reported.")
    conversation_history: list[ConversationHistoryMessage] = Field(
        description="The history of the conversation that led to this ticket report.")
    hostname: str = Field(
        description="The hostname of the system that is reporting the issue, should be the output of `hostname` command.")
    user: str = Field(
        description="The user who is reporting the issue, should be the output of `whoami` command.")
    current_working_directory: str = Field(
        description="The current working directory of the user who is reporting the issue, should be the output of `pwd` command.")

class ReportMCP(FastMCP):
    """
    HPC-GPT Support Reporting MCP Server.
    """

    def __init__(self, name: str, config: ReportMCPConfig):
        super().__init__(name)
        self.config = config
        self.jira = JiraConnectionManager(
            server_url=self.config.jira.url,
            personal_access_token=self.config.jira.personal_access_token,
            username=self.config.jira.username,
            api_key=self.config.jira.api_key,
        )

        self.add_tool(self.send_support_report)
        log.info(f"Initialized Report MCP Server with config: {self.config}")

    async def send_support_report(self, parameters: SupportReportToolParameters) -> str:
        """
        MCP Tool: send_support_report
        Description: Creates an issue for the user in at their systems service endpoint.
        Parameters:
            - title: The title of the issue to create.
            - description: A short one paragraph description of the issue that is being reported.
            - conversation_history: The history of the conversation between the chatbot and the user that led to this ticket report.
            - hostname: The hostname of the system that is reporting the issue
            - user: The user who is reporting the issue
            - current_working_directory: The current working directory of the user who is reporting the issue
        Returns:
            - The key of the issue that was created.
        """
        # Get the user's information from the local system.
        user_info = self._get_local_user_info(parameters.user)

        if self.config.mode == "jira":
            return self._send_jira_support_report(parameters, user_info)
        elif self.config.mode == "email":
            return self._send_email_support_report(parameters, user_info)
        else:
            raise ValueError(f"Unsupported report mode: {self.config.mode}")

    def _send_jira_support_report(self, parameters: SupportReportToolParameters, user_info: dict[str, Any]) -> str:
        """
        Send a support report to Jira.
        """
        # Find the user to report the issue to
        try:
            # Try and validate the user's identity in Jira.
            if user_info is not None:
                reporter = self.jira.find_user(email=user_info["email"]).get("name")
            else:
                reporter = self.jira.find_user(username=parameters.user).get("name")
        except Exception as e:
            # Otherwise, just failback to the provided username.
            log.error(f"Error identifying user in Jira: {e}")
            reporter = parameters.user
        
        description = parameters.description + "\n\n### Conversation History ###"
        for message in parameters.conversation_history:
            description += f"\n*{message.role}*: {message.content}"
        
        # Submit issue
        issue = self.jira.create_issue(
            self.config.jira.project,
            self.config.jira.issue_type,
            reporter,
            parameters.title,
            description,
            fields=self.config.jira.default_fields,
        )

        # Add comment containing addtional user info for staff.
        if user_info is not None:
            comment = f"User: {user_info['username']}\nHostname: {parameters.hostname}\nCurrent Working Directory: {parameters.current_working_directory}\nGroups: {user_info['groups']}"
        else:
            comment = f"User: {parameters.user}\nHostname: {parameters.hostname}\nCurrent Working Directory: {parameters.current_working_directory}"
        self.jira.add_comment(issue.key, comment, visibility="Staff")

        issue_url = f"{self.jira.server_url}/browse/{issue.key}"
        log.info(f"Issue {issue.key} created: {issue_url}")
        return f"Issue {issue.key} created: {issue_url}"

    def _get_local_user_info(self, username: str) -> dict[str, Any] | None:
        """
        Runs the ``userinfo`` command and returns parsed fields as a dict.

        Args:
            username: The username of the user to get information for.

        Returns:
            A dictionary of the user's information, with the following keys, or None if the user info cannot be retrieved:
            - username: The username of the user.
            - user_#: The user number of the user.
            - name: The name of the user.
            - email: The email of the user.
            - shell: The shell of the user.
            - ispi: Whether the user is a PI.
            - primary_group_id: The primary group ID of the user.
            - groups: The groups the user is a member of.
        """
        
        # TODO Check username for shell injection
        try:
            raw_text = subprocess.run(["userinfo", username], capture_output=True, text=True)
        except Exception as e:
            log.error(f"Error getting user info for user {username}: {e}")
            return None

        user_dict = {}
        for raw_line in raw_text.stdout.splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            label, _, value = line.partition(":")
            label = label.strip()
            value = value.strip()
            key = label.lower().replace(" ", "_")

            if key == "ispi":
                user_dict[key] = value.upper() == "TRUE"
            elif key == "groups":
                user_dict[key] = value.split() if value else []
            else:
                user_dict[key] = value


        if user_dict.get("error"):
            log.warning(f"Could not retrieve user info for user \"{username}\". Error: {user_dict.get('error')}")
            return None

        log.debug(f"Userinfo for user \"{username}\": {user_dict}")
        return user_dict

    def _send_email_support_report(self, parameters: SupportReportToolParameters, user_info: dict[str, Any] | None) -> str:
        """
        Send a support report to email.
        """
        if self.config.email is None:
            raise ValueError("Email configuration is required when mode is 'email'")

        description = parameters.description + "\n\n### Conversation History ###"
        for message in parameters.conversation_history:
            description += f"\n*{message.role}*: {message.content}"

        report_lines = [
            f"Title: {parameters.title}",
            "",
            "Description:",
            description,
            "",
            "Environment:",
            f"  User: {user_info.get('username') if user_info else parameters.user}",
            f"  Hostname: {parameters.hostname}",
            f"  Current Working Directory: {parameters.current_working_directory}",
        ]
        if user_info and user_info.get("groups"):
            report_lines.append(f"  Groups: {' '.join(user_info['groups'])}")

        report_lines.extend(["", "Conversation History:"])
        for message in parameters.conversation_history:
            report_lines.append(f"  {message.role}: {message.content}")

        body = "\n".join(report_lines)
        self._send_email(
            recipient_address=self.config.email.recipient_address,
            subject=self.config.email.subject,
            body=body,
            sender_address=self.config.email.sender_address,
        )
        log.info(
            "Support email sent to %s",
            self.config.email.recipient_address,
        )
        return f"Support email sent to {self.config.email.recipient_address}"

    def _send_email(self, recipient_address: str, subject: str, body: str, sender_address: str = None) -> str:
        """
        Send an email using the system `mail` command.
        """
        command = ["mail", "-s", subject]
        if sender_address:
            command.extend(["-r", sender_address])
        command.append(recipient_address)

        try:
            result = subprocess.run(
                command,
                input=body,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "The `mail` command was not found. Install mailx/mailutils on this system."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to invoke mail command: {exc}") from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"mail command failed with exit code {result.returncode}: {result.stderr.strip()}"
            )

        log.debug(
            "mail command succeeded for recipient=%s sender=%s",
            recipient_address,
            sender_address,
        )
        return "Email sent successfully"
