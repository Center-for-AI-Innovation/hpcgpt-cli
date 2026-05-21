import os
import logging
import argparse

from src.log_utils import setup_logger
from src.stages import summarize_tickets

def parse_command_line() -> argparse.Namespace:
    from rich_argparse import RichHelpFormatter

    def parse_filepath(path: str):
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
                    default="../config/slurm_config.json",
                    type=parse_filepath,
                    help="Path to the Slurm configuration file. Defaults to ../config/slurm_config.json")
    optional_args.add_argument('-o', '--output', 
                    type=str, 
                    help='Path to the file to output summarization results to. Defaults to results/<input_file_name>_sum_results.jsonl.')
    optional_args.add_argument('-m', '--model',
                    type=str, 
                    help="Model to use. Use llmflux --show-models to list available models.")
    optional_args.add_argument('-p', '--prompt',
                    default="../prompts/summarization.md",
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

if __name__ == "__main__":
    args = parse_command_line()

    if args.output is None:
        args.output = f"results/{os.path.basename(args.data).split('.')[0]}_sum_results.jsonl"

    file_log_level = logging.DEBUG if args.verbose else logging.INFO
    console_log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logger(args.log_file, file_log_level, console_log_level, use_color=True, writemode='a')

    # Load system prompt
    logging.debug(f"Loading system prompt from: {args.prompt}")
    with open(args.prompt, "r") as f:
        system_prompt = f.read()

    summarize_tickets(system_prompt, args.data, args.output, args.model, args.slurm_config)