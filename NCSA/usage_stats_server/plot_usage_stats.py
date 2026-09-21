#!/usr/bin/env python3
"""
Generate usage pie charts from the usage-stats SQLite database.
"""
import os
import sqlite3
import argparse
import pandas as pd
import matplotlib.pyplot as plt

from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as dateutil_parse
from rich_argparse import RichHelpFormatter

def parse_command_line() -> argparse.Namespace:
    def parse_datetime(s: str) -> datetime:
        """Command line argument parser for datetime arguments. Uses dateutil parser to accept any type of datetime format."""
        try:
            return dateutil_parse(s)  # Will accept any type of string
        except (ValueError, TypeError) as exc:
            raise argparse.ArgumentTypeError(f'Invalid datetime string: "{s}"') from exc
    def parse_filepath(s: str) -> Path:
        """Command line argument parser for file path arguments. Validates that file path exists and is a file."""
        path = Path(s)
        if not path.exists():
            raise argparse.ArgumentTypeError(f'File path does not exist: "{s}"')
        if not path.is_file():
            raise argparse.ArgumentTypeError(f'File path is not a file: "{s}"')
        return path

    p = argparse.ArgumentParser(
        description="Plot usage statistics for the hpc-gpt tool from the SQLite database. Generates plots for unique opens and time used by user.",
        formatter_class=RichHelpFormatter
    )
    p.add_argument('-d', '--db-path',
        type=parse_filepath,
        default="data/usage.db",
        help="SQLite database path. Default is data/usage.db.")
    p.add_argument('-o', '--output',
        type=str,
        default="plots",
        help="Output directory for the plots")
    p.add_argument('-s', '--starttime',
        type=parse_datetime,
        default=datetime.now() - relativedelta(months=1),
        help="Include sessions starting on or after this time. Default is one month ago.")
    p.add_argument('-e', '--endtime',
        type=parse_datetime,
        default=datetime.now(),
        help="Include sessions starting on or before this time. Default is now.")
    p.add_argument('-n', '--top-n',
        type=int,
        default=10,
        help='Number of top users to show individually; rest are grouped as "other"')
    return p.parse_args()


def load_sessions(db_path: str, starttime: datetime, endtime: datetime) -> pd.DataFrame:

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            """
            SELECT session_id, username, hostname, started_at, ended_at, duration_sec, exit_code
            FROM sessions
            """,
            conn,
        )

    if df.empty:
        return df

    df["started_at"] = pd.to_datetime(df["started_at"], utc=True)

    # CLI bounds are local system time; DB timestamps are UTC.
    local_tz = datetime.now().astimezone().tzinfo

    def to_utc(ts: pd.Timestamp) -> pd.Timestamp:
        if ts.tzinfo is None:
            ts = ts.tz_localize(local_tz)
        return ts.tz_convert("UTC")

    start = to_utc(pd.Timestamp(starttime))
    end = to_utc(pd.Timestamp(endtime))

    return df[(df["started_at"] >= start) & (df["started_at"] <= end)].copy()


def get_unique_opens(df: pd.DataFrame) -> dict[str, int]:
    """Count sessions (launches) per user — one open per recorded session."""
    if df.empty:
        return {}
    return df.groupby("username").size().astype(int).to_dict()


def get_time_used_minutes(df: pd.DataFrame) -> dict[str, int]:
    """Sum session duration per user, reported in whole minutes."""
    if df.empty:
        return {}
    return df.groupby("username")["duration_sec"].sum().floordiv(60).astype(int).to_dict()


def _pie_top_n(counts: dict[str, int], output_file: str, title_prefix: str, n: int) -> None:
    if not counts:
        raise ValueError("No usage data in the selected time range; nothing to plot")

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top = sorted_items[:n]
    other = sorted_items[n:]
    labels = [name for name, _ in top]
    sizes = [count for _, count in top]
    if other:
        labels.append("other")
        sizes.append(sum(count for _, count in other))

    total = sum(sizes)
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct=lambda pct: f"{int(round(pct * total / 100.0))}")
    ax.set_title(f"{title_prefix} (Total: {total})")
    plt.tight_layout()
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))
    plt.savefig(output_file)
    plt.close()


def plot_unique_opens(unique_opens: dict[str, int], output_file: str, n: int = 10) -> None:
    _pie_top_n(unique_opens, output_file, "Unique Opens by User", n)


def plot_time_used(time_used: dict[str, int], output_file: str, n: int = 10) -> None:
    _pie_top_n(time_used, output_file, "Time Used by User (minutes)", n)


def main(args: argparse.Namespace) -> None:
    df = load_sessions(args.db_path, args.starttime, args.endtime)
    unique_opens = get_unique_opens(df)
    time_used = get_time_used_minutes(df)
    plot_unique_opens(unique_opens, os.path.join(args.output, "unique_opens.png"), n=args.top_n)
    plot_time_used(time_used, os.path.join(args.output, "time_used.png"), n=args.top_n)
    print(f"Wrote {os.path.join(args.output, 'unique_opens.png')} ({sum(unique_opens.values())} opens)")
    print(f"Wrote {os.path.join(args.output, 'time_used.png')} ({sum(time_used.values())} minutes)")


if __name__ == "__main__":
    args = parse_command_line()
    main(args)
