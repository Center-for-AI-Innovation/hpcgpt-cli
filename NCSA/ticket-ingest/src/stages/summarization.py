import os
import json
import argparse
import logging
import pandas as pd

from pathlib import Path
from llmflux.slurm import SlurmRunner
from llmflux.core.config import Config, EngineConfig

from ..log_utils import setup_logger
from ..llmflux_utils import SlurmConfig, submit_llmflux_job, monitor_llmflux_job

def parse_command_line() -> argparse.Namespace:
    from rich_argparse import RichHelpFormatter

    def parse_filepath(path: str) -> Path:
        """Command line argument parser for file paths"""
        # Check path exists
        if not os.path.exists(path):
            msg = f'Invalid path "{path}" specified : File does not exist.\n'
            raise argparse.ArgumentTypeError(msg)
        return path
    
    parser = argparse.ArgumentParser(formatter_class=RichHelpFormatter, add_help=False)
    

    # Required arguments
    required_args = parser.add_argument_group('Required arguments', '')
    required_args.add_argument('data',
                    type=parse_filepath,                     
                    help="CSV file containing ticket data to summarize. See README.md for more details on CSV format.")

    # Optional arguments
    optional_args = parser.add_argument_group('Optional arguments', '')
    optional_args.add_argument('-c', '--slurm-config',
                    default="../../config/slurm_config.json",
                    type=parse_filepath,
                    help="Path to the Slurm configuration file. Defaults to ../config/slurm_config.json")
    optional_args.add_argument('-o', '--output', 
                    type=str, 
                    help='Path to the file to output summarization results to.')
    optional_args.add_argument('-m', '--model',
                    type=str, 
                    help="Model to use. Use llmflux --show-models to list available models.")
    optional_args.add_argument('-b', '--batch-size',
                    type=int,
                    help="Batch size to use.")
    optional_args.add_argument('-p', '--prompt',
                    default="../../prompts/summarization.md",
                    type=parse_filepath, 
                    help='Path to the file to use as the system prompt for the LLM.')
    optional_args.add_argument("--log-file",
                    default="logs/Latest.log",
                    type=str,
                    help="Option to set the file logging will output to. Defaults to logs/Latest.log.")
    
    # Flags
    flag_args = parser.add_argument_group('Flags', '')
    flag_args.add_argument("-h", "--help",
                    action="help",
                    help="Show help message and exit",)
    flag_args.add_argument("-v","--verbose",
                    action="store_true",
                    help="Change the logging level from INFO to DEBUG",)
    
    return parser.parse_args()

def prep_ticket(row: pd.Series) -> str:
    """
    Generates the user text for an individual ticket.
    Args:
        row: A pandas series containing the ticket data.
    Returns:
        A string containing the user text for the ticket.
    """
    ticket_data = f"---\n"
    ticket_data += f"Title: {row['Summary']}\n"
    ticket_data += f"Description: {row['Description']}\n"
    ticket_data += f"Comments:\n"
    if pd.notnull(row["Comment"]):
        ticket_data += f"Comment: {row['Comment']}\n"
    for i in range(1, 110):
        if f"Comment.{i}" in row.keys() and pd.notnull(row[f"Comment.{i}"]):
            ticket_data += f"Comment {i}: {row[f'Comment.{i}']}\n"
        else:
            break
    ticket_data += "---"
    return ticket_data

def prep_ticket_data(df: pd.DataFrame, system_prompt: str, output_file: str) -> str:
    """
    Takes ticket data from a pandas dataframe and writes it as a list of prompts in jsonl format to a file.
    Args:
        df: A pandas dataframe containing the ticket data.
        output_file: The name of the file to output the prompts to. Defaults to prompts.jsonl.
    Returns:
        None. Writes the prompts to the output file.
    """
    # Create directory if necessary
    dirname = os.path.dirname(output_file)
    if not os.path.exists(dirname) and dirname != '':
        os.makedirs(os.path.dirname(output_file))

    # Write the prompts to the output file
    with open(output_file, "w") as f:
        for _, row in df.iterrows():
            ticket_data = prep_ticket(row)
            f.write(json.dumps({
                "custom_id": row["Issue key"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "messages": [
                        {
                            "role": "system", 
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": ticket_data
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            }) + "\n")
    logging.info(f"Wrote {_+1} prompts to {output_file}")

def summarize_tickets(prompt: str, input_file: str, output_file: str, model: str, batch_size: int, slurm_config_path: str):
    # Load ticket data
    logging.info(f"Loading ticket data from: {input_file}")
    df = pd.read_csv(input_file, dtype=str)
    logging.info(f"Loaded {len(df)} tickets from {input_file}")

    # Create prompt file for LLMFLUX
    llmflux_prompt_file = os.path.join(os.path.dirname(input_file), f"{os.path.basename(input_file).split('.')[0]}_summarization_prompts.jsonl")
    prep_ticket_data(df, prompt, llmflux_prompt_file)

    # Submit summarization job
    slurm_config = SlurmConfig.load_from_json(slurm_config_path)
    # Override config values if provided on the command line
    model = slurm_config.model if model is None else model
    batch_size = slurm_config.batch_size if batch_size is None else batch_size
    
    job_id = submit_llmflux_job(llmflux_prompt_file, output_file, model, batch_size, slurm_config, job_name="Summarization")

    # Monitor summarization job
    monitor_llmflux_job(job_id, job_name="Summarization")

if __name__ == "__main__":
    args = parse_command_line()
    if args.output is None:
        args.output = f"data/output/{os.path.basename(args.data).split('.')[0]}_summarization_results.jsonl"

    file_log_level = logging.DEBUG if args.verbose else logging.INFO
    console_log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(args.log_file, file_log_level, console_log_level, use_color=True, writemode='a')

    # Load system prompt
    logger.info(f"Loading system prompt from: {args.prompt}")
    with open(args.prompt, "r") as f:
        system_prompt = f.read()

    summarize_tickets(system_prompt, args.data, args.output, args.model, args.batch_size, args.slurm_config)