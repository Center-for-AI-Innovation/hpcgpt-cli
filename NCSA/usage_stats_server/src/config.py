from pathlib import Path

from pydantic import BaseModel, Field


class Config(BaseModel):
    host: str = Field(
        default="0.0.0.0",
        description="The host ip address for the server to listen on",
    )
    port: int = Field(
        default=8005,
        description="The port for the server to listen on",
    )
    db_path: str = Field(
        default="data/usage.db",
        description="SQLite database path for session records",
    )
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    @classmethod
    def load_from_json(cls, filepath: str = "config.json") -> "Config":
        with open(filepath, "r") as f:
            return cls.model_validate_json(f.read())

    def validate_config(self) -> None:
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid log_level: {self.log_level}")
        if not (0 < self.port < 65536):
            raise ValueError(f"Port out of range: {self.port}")
        db = Path(self.db_path)
        if db.parent and str(db.parent) not in (".", ""):
            db.parent.mkdir(parents=True, exist_ok=True)

    def __str__(self) -> str:
        return (
            f"Config(\n"
            f"\thost='{self.host}',\n"
            f"\tport={self.port},\n"
            f"\tdb_path='{self.db_path}',\n"
            f"\tlog_level='{self.log_level}',\n"
            f")"
        )

    def __repr__(self) -> str:
        return self.__str__()
