import argparse
from pydantic import BaseModel, Field
from typing import Optional

class ReportMCPEmailConfig(BaseModel):
    recipient_address: str = Field(
        description="The email address to send the support report to")
    sender_address: str = Field(
        description="The email address to send the support report from")
    subject: str = Field(
        description="The subject of the support report email")

    def __str__(self) -> str:
        out =  "ReportMCPEmailConfig(\n"
        out += f"\t\trecipient_address='{self.recipient_address}',\n" 
        out += f"\t\tsender_address='{self.sender_address}',\n" 
        out += f"\t\tsubject='{self.subject}',\n" 
        out += "\t)"
        return out

    def __repr__(self) -> str:
        return self.__str__()

class ReportMCPJiraConfig(BaseModel):
    url: str = Field(
        description="The URL of the Jira instance")
    authentication_method: str = Field(
        default = "personal_access_token",
        description="The method to authenticate with Jira. Options are 'personal_access_token', 'api_key'")
    personal_access_token: Optional[str] = Field(
        default = None,
        description="A personal access token for connecting to Jira. Only used if the authentication method is 'personal_access_token'.")
    username: Optional[str] = Field(
        default = None,
        description="The username for the Jira instance. Only used if the authentication method is 'api_key'.")
    api_key: Optional[str] = Field(
        default = None,
        description="The API key for the Jira instance. Only used if the authentication method is 'api_key'.")
    project: str = Field(
        description="The project to create the issue in")
    issue_type: str = Field(
        description="The type of issue to create")
    default_fields: Optional[dict] = Field(
        default = None,
        description="The default fields to create the issue with")

    def __str__(self) -> str:
        out =  "ReportMCPJiraConfig(\n"
        out += f"\t\turl='{self.url}',\n" 
        out += f"\t\tauthentication_method='{self.authentication_method}',\n" 
        if self.authentication_method == "personal_access_token":
            if self.personal_access_token is not None:
                masked_token = '*' * max(0, len(self.personal_access_token) - 4) + self.personal_access_token[-4:]
            else:
                masked_token = None
            out += f"\t\tpersonal_access_token='{masked_token}',\n" 
        elif self.authentication_method == "api_key":
            if self.username is not None:
                masked_username = '*' * max(0, len(self.username) - 4) + self.username[-4:]
            else:
                masked_username = None
            if self.api_key is not None:
                masked_api_key = '*' * max(0, len(self.api_key) - 4) + self.api_key[-4:]
            else:
                masked_api_key = None
            out += f"\t\tusername='{masked_username}',\n" 
            out += f"\t\tapi_key='{masked_api_key}',\n" 
        out += f"\t\tproject='{self.project}',\n" 
        out += f"\t\tissue_type='{self.issue_type}',\n" 
        out += f"\t\tdefault_fields={self.default_fields},\n" 
        out += "\t)"
        return out

    def __repr__(self) -> str:
        return self.__str__()

class ReportMCPConfig(BaseModel):
    host: str = Field(
        default="127.0.0.1", 
        description="The host ip address for the server to listen on")
    port: int = Field(
        default=8003, 
        description="The port for the server to listen on")
    log_file: str = Field(
        default="logs/Latest.log", 
        description="The file to write server logs to")
    log_level: str = Field(
        default="INFO",
        description="The level to log at. Options are 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'")
    mode: str = Field(
        default="jira",
        description="Which method the server should use to send the support report. Options are 'jira' or 'email'.")
    jira: Optional[ReportMCPJiraConfig] = Field(
        default = None,
        description="The Jira configuration. Only used if the mode is 'jira'.")
    email: Optional[ReportMCPEmailConfig] = Field(
        default = None,
        description="The email configuration. Only used if the mode is 'email'.")

    @classmethod
    def load_from_json(cls, filepath: str = "config.json") -> "Config":
        with open(filepath, "r") as f:
            return cls.model_validate_json(f.read())

    def validate_config(self) -> None:
        if self.mode not in ["jira", "email"]:
            raise ValueError(f"Invalid mode: {self.mode}")
        if self.mode == "jira":
            if self.jira is None:
                raise ValueError("Jira configuration is required when mode is 'jira'")
            if self.jira.authentication_method == "personal_access_token" and self.jira.personal_access_token is None:
                raise ValueError("Personal access token is required when authentication method is 'personal_access_token'")
            if self.jira.authentication_method == "api_key" and (self.jira.api_key is None or self.jira.username is None):
                raise ValueError("API key and username are required when authentication method is 'api_key'")
        if self.mode == "email" and self.email is None:
            raise ValueError("Email configuration is required when mode is 'email'")

    def __str__(self) -> str:
        out =  "ReportMCPConfig(\n"
        out += f"\thost='{self.host}',\n" 
        out += f"\tport='{self.port}',\n" 
        out += f"\tlog_file='{self.log_file}',\n" 
        out += f"\tlog_level='{self.log_level}',\n" 
        out += f"\tmode='{self.mode}',\n"
        if self.mode == "jira": out += f"\tjira='{self.jira}',\n"
        if self.mode == "email": out += f"\temail='{self.email}',\n"
        out += ")"
        return out
    
    def __repr__(self) -> str:
        return self.__str__()


def consolidate_config_and_args(config: ReportMCPConfig, args: argparse.Namespace):
    # Merge config and args into a single args, with args taking precedence
    for key, value in config.__dict__.items():
        if key.replace("_", "-") not in args.__dict__ or args.__dict__[key] is None:
            args.__dict__[key] = value
    return args