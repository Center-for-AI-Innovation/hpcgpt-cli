import os
import shutil
import logging
import argparse

from src.log_utils import setup_logger
from src.stages import summarize_tickets, evaluate_summarization, remove_duplicates, cluster_topics

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
                    default="config/slurm_config.json",
                    type=parse_filepath,
                    help="Path to the Slurm configuration file. Defaults to ../config/slurm_config.json")
    optional_args.add_argument('-o', '--output', 
                    default="data/output/ticket_pipeline_results.jsonl",
                    type=str, 
                    help='Path to the file to output workflow results to.')
    optional_args.add_argument('-m', '--model',
                    type=str, 
                    help="Model to use. Use llmflux --show-models to list available models.")
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

def main(args: argparse.Namespace):
    label = os.path.basename(args.data).split('.')[0]
    # Run Summarization of tickets to Q/A pairs
    logging.info(f"### Starting Pipeline Stage : Summarizing tickets to Q/A pairs")
    with open("prompts/summarization.md", "r") as f:
        system_prompt = f.read()
    summarize_tickets(system_prompt, args.data, f"../llmflux/data/output/{label}_sum_results.jsonl", args.model, args.batch_size, args.slurm_config)

    # Evaluate summarization results
    logging.info(f"### Starting Pipeline Stage : Evaluating summarization results")
    with open("prompts/evaluation.md", "r") as f:
        system_prompt = f.read()
    evaluate_summarization(system_prompt, f"../llmflux/data/output/{label}_sum_results.jsonl", f"../llmflux/data/output/{label}_eval_results.jsonl", args.model, args.batch_size, args.slurm_config)

    shutil.copy(f"../llmflux/data/output/{label}_eval_results.jsonl", args.output)
    logging.info("Exiting early for debugging")
    exit(0)

    # Remove duplicates
    logging.info(f"### Starting Pipeline Stage : Removing duplicates")
    with open("prompts/deduplication.md", "r") as f:
        system_prompt = f.read()
    remove_duplicates(system_prompt, f"../llmflux/data/output/{label}_eval_results.jsonl", f"../llmflux/data/output/{label}_dedup_results.jsonl", args.model, args.batch_size, args.slurm_config)

    # Cluster topics
    logging.info(f"### Starting Pipeline Stage : Clustering topics")
    with open("prompts/clustering.md", "r") as f:
        system_prompt = f.read()
    cluster_topics(system_prompt, f"../llmflux/data/output/{label}_dedup_results.jsonl", f"../llmflux/data/output/{label}_clstr_results.jsonl", args.model, args.batch_size, args.slurm_config)

    # Copy results to final output file
    shutil.copy(f"../llmflux/data/output/{label}_clstr_results.jsonl", args.output)

    logging.info(f"### Pipeline completed successfully")
    logging.info(f"### Results saved to: {args.output}")

if __name__ == "__main__":
    args = parse_command_line()

    file_log_level = logging.DEBUG if args.verbose else logging.INFO
    console_log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(args.log_file, file_log_level, console_log_level, use_color=True, writemode='a')

    main(args)