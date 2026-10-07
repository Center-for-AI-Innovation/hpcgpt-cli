from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class TicketMCPConfig(BaseModel):
    host: str = Field(
        default="0.0.0.0",
        description="The host ip address for the server to listen on")
    port: int = Field(
        default=8000,
        description="The port for the server to listen on")
    log_file: str = Field(
        default="logs/Latest.log",
        description="The file to write server logs to")
    log_level: str = Field(
        default="INFO",
        description="The level to log at. Options are 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'")

    data_dir: str = Field(
        default="/u/rsingal/hpcgpt-cli/NCSA/ticket-ingest/data",
        description="Directory holding clustered.json / dedup/deduplicated.json")
    data_file: Optional[str] = Field(
        default=None,
        description="Explicit path to the ticket JSON to index. Overrides data_dir resolution.")
    db_path: str = Field(
        default=":memory:",
        description="SQLite path for the FTS5 index. ':memory:' rebuilds on each start.")

    @classmethod
    def load_from_json(cls, filepath: str = "config.json") -> "TicketMCPConfig":
        with open(filepath, "r") as f:
            return cls.model_validate_json(f.read())

    def resolve_source(self) -> Path:
        """Pick the JSON knowledge-base file to index (clustered preferred)."""
        candidates = []
        if self.data_file:
            candidates.append(Path(self.data_file))
        d = Path(self.data_dir)
        candidates += [d / "clusters" / "clustered.json", d / "clustered.json", d / "dedup" / "deduplicated.json", d / "deduplicated.json"]
        for c in candidates:
            if c.exists():
                return c
        searched = ", ".join(str(c) for c in candidates)
        raise FileNotFoundError(f"No ticket data file found. Looked at: {searched}")

    def validate_config(self) -> None:
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid log_level: {self.log_level}")
        if not (0 < self.port < 65536):
            raise ValueError(f"Port out of range: {self.port}")
        self.resolve_source()

    def __str__(self) -> str:
        return (f"TicketMCPConfig(\n"
                f"\thost='{self.host}',\n"
                f"\tport={self.port},\n"
                f"\tlog_file='{self.log_file}',\n"
                f"\tlog_level='{self.log_level}',\n"
                f"\tdata_dir='{self.data_dir}',\n"
                f"\tdata_file='{self.data_file}',\n"
                f"\tdb_path='{self.db_path}',\n"
                f")")

    def __repr__(self) -> str:
        return self.__str__()