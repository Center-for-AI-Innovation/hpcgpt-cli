"""
Single-command update to the ticket knowledge base.

    python update_knowledge_base.py data/raw/new_tickets.csv \\
        data/output/knowledge_base.json data/output/knowledge_base_updated.json

Runs: summarize new tickets -> judge them for PII -> drop PII failures ->
dedup the surviving new tickets against each other -> merge into the
existing knowledge-base JSON. See config/update_config.json for the
per-step model/batch_size/Slurm settings.
"""

import os
import sys
import json
import logging
import argparse

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.log_utils import setup_logger
from src.llmflux_utils import SlurmConfig
from src.stages import summarize_tickets, evaluate_summarization, remove_duplicates
from src.db_utils import load_database, filter_pii_failures, merge_into_database

REQUIRED_STEPS = ("judging_step", "summarization_step")


def parse_command_line() -> argparse.Namespace:
    from rich_argparse import RichHelpFormatter

    def parse_filepath(path: str):
        """Command line argument parser for file paths"""
        if not os.path.exists(path):
            msg = f'Invalid path "{path}" specified : File does not exist.\n'
            raise argparse.ArgumentTypeError(msg)
        return path

    parser = argparse.ArgumentParser(
        prog="update_knowledge_base.py",
        description="Ingest a CSV of new support tickets and merge the resulting " "Q/A pairs into an existing knowledge-base JSON file.",
        formatter_class=RichHelpFormatter,
        add_help=False,
    )

    required_args = parser.add_argument_group('Required arguments', '')
    required_args.add_argument('input_csv', type=parse_filepath, help="CSV of new tickets to ingest. Same Jira export format as ticket_pipeline.py.")
    required_args.add_argument('input_db', type=parse_filepath, help="Existing knowledge-base JSON file to update.")
    required_args.add_argument('output_db', type=str, help="Path to write the updated knowledge-base JSON file to.")

    optional_args = parser.add_argument_group('Optional arguments', '')
    optional_args.add_argument('-c', '--config', default="config/update_config.json", type=parse_filepath,help="Path to the pipeline config file (judging_step / summarization_step, " "each with model, batch_size, and slurm settings). " "Defaults to config/update_config.json.")
    optional_args.add_argument("--log-file", type=str, help="Overrides the log_file set in the config.")

    flag_args = parser.add_argument_group('Flags', '')
    flag_args.add_argument("-h", "--help",action="help", help="Show help message and exit",)
    flag_args.add_argument("-v", "--verbose", action="store_true", help="Change the logging level from INFO to DEBUG",)
    return parser.parse_args()


def validate_config(config: dict) -> None:
    for step_name in REQUIRED_STEPS:
        if step_name not in config:
            raise ValueError(f'Config is missing required section "{step_name}"')
        step = config[step_name]
        for key in ("model", "batch_size", "slurm"):
            if key not in step:
                raise ValueError(f'Config section "{step_name}" is missing "{key}"')


def build_slurm_config(step: dict) -> SlurmConfig:
    """Flatten a {"model", "batch_size", "slurm": {...}} config block into the
    flat SlurmConfig object summarize_tickets/evaluate_summarization/remove_duplicates
    expect (they read a SlurmConfig JSON path, not an object, hence write_step_config)."""
    return SlurmConfig(**step["slurm"], model=step["model"], batch_size=step["batch_size"])


def write_step_config(step: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(build_slurm_config(step).model_dump_json())


def main(args: argparse.Namespace, config: dict, progress: Progress) -> None:
    label = os.path.splitext(os.path.basename(args.input_csv))[0]
    work_dir = f".llmflux/data/output/{label}_update"
    os.makedirs(work_dir, exist_ok=True)

    summarization_cfg_path = f"{work_dir}/summarization_slurm_config.json"
    judging_cfg_path = f"{work_dir}/judging_slurm_config.json"
    write_step_config(config["summarization_step"], summarization_cfg_path)
    write_step_config(config["judging_step"], judging_cfg_path)

    sum_results_path = f"{work_dir}/{label}_sum_results.jsonl"
    eval_results_path = f"{work_dir}/{label}_eval_results.jsonl"
    clean_sum_results_path = f"{work_dir}/{label}_sum_results_clean.jsonl"
    dedup_results_path = f"{work_dir}/{label}_dedup_results.jsonl"


    logging.info("### Step 1/4: Summarizing new tickets")
    task = progress.add_task("Summarizing new tickets", total=1)
    with open("prompts/summarization.md") as f:
        summarization_prompt = f.read()
    summarize_tickets(summarization_prompt, args.input_csv, sum_results_path, None, summarization_cfg_path)
    progress.update(task, completed=1)


    logging.info("### Step 2/4: Judging new Q/A pairs for PII")
    task = progress.add_task("Judging Q/A pairs for PII", total=1)
    with open("prompts/evaluation.md") as f:
        judging_prompt = f.read()
    evaluate_summarization(judging_prompt, sum_results_path, eval_results_path, None, judging_cfg_path)
    progress.update(task, completed=1)


    logging.info("### Step 3/4: Removing tickets that failed the PII judge")
    task = progress.add_task("Filtering PII failures", total=1)
    n_dropped = filter_pii_failures(sum_results_path, label, clean_sum_results_path)
    progress.update(task, completed=1)


    logging.info("### Step 4/4: Deduplicating new tickets and merging into the database")
    task = progress.add_task("Deduplicating + merging into database", total=1)
    with open("prompts/deduplication.md") as f:
        dedup_prompt = f.read()
    remove_duplicates(dedup_prompt, clean_sum_results_path, dedup_results_path, None, judging_cfg_path)

    existing_db = load_database(args.input_db)
    with open(dedup_results_path) as f:
        new_items = json.load(f)
    merged_db, n_added, n_skipped = merge_into_database(existing_db, new_items)

    os.makedirs(os.path.dirname(args.output_db) or ".", exist_ok=True)
    with open(args.output_db, "w") as f:
        json.dump(merged_db, f, indent=2)
    progress.update(task, completed=1)

    logging.info(f"Dropped {n_dropped} PII failure(s), added {n_added} new Q/A pair(s), "
                 f"skipped {n_skipped} ID(s) already in the database")
    logging.info(f"Updated database written to \"{args.output_db}\" ({len(merged_db)} total entries)")


if __name__ == "__main__":
    args = parse_command_line()

    with open(args.config) as f:
        config = json.load(f)
    validate_config(config)

    log_file = args.log_file or config.get("log_file", "logs/Latest.log")
    log_level = logging.DEBUG if args.verbose else logging.INFO


    setup_logger(log_file, log_level, console_log_level=None, use_color=True, writemode='a')
    console = Console()
    rich_handler = RichHandler(console=console, show_path=False, show_time=False, markup=False)
    rich_handler.setLevel(log_level)
    logging.getLogger().addHandler(rich_handler)


    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            main(args, config, progress)
    except Exception:
        logging.exception("Run failed, database was not updated")
        sys.exit(1)
