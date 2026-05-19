import os
import json
import argparse
import logging

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
                    help="JSONL file containing the output of de-duplication to cluster into groups.")

    # Optional arguments
    optional_args = parser.add_argument_group('Optional arguments', '')
    optional_args.add_argument('-c', '--slurm-config',
                    default="../../config/slurm_config.json",
                    type=parse_filepath,
                    help="Path to the Slurm configuration file. Defaults to ../config/slurm_config.json")
    optional_args.add_argument('-o', '--output', 
                    type=str, 
                    help='Path to the file to output clustering results to. Defaults to data/output/<input_file_name>_clustering_results.jsonl.')
    optional_args.add_argument('-m', '--model',
                    type=str, 
                    help="Model to use. Use llmflux --show-models to list available models.")
    optional_args.add_argument('-b', '--batch-size',
                    type=int,
                    help="Batch size to use.")
    optional_args.add_argument('-p', '--prompt',
                    default="../../prompts/clustering.md",
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

def cluster_topics(prompt: str, input_file: str, output_file: str, model: str, batch_size: int, slurm_config_path: str):
    # Load clustering data
    logging.info(f"Loading clustering data from: {input_file}")
    with open(input_file, "r") as fh:
        clustering_data = json.load(fh)
    logging.info(f"Loaded {len(clustering_data)} topics from {input_file}")

    # Create prompt file for LLMFLUX
    basename = os.path.basename(input_file).split('.')[0]
    if basename.endswith("_deduplicated_results"): # This is for ease of use in the pipeline
        basename = basename[:-len("_deduplicated_results")]
    llmflux_prompt_file = os.path.join(os.path.dirname(input_file), f"{basename}_clustering_prompts.jsonl")
    
    

if __name__ == "__main__":
    args = parse_command_line()
    if args.output is None:
        if basename.endswith("_deduplicated_results"): # This is for ease of use in the pipeline
            basename = os.path.basename(args.data).split('.')[0]
        args.output = f"data/output/{basename}_clustering_results.jsonl"

    file_log_level = logging.DEBUG if args.verbose else logging.INFO
    console_log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(args.log_file, file_log_level, console_log_level, use_color=True, writemode='a')

    # Load system prompt
    logger.info(f"Loading system prompt from: {args.prompt}")
    with open(args.prompt, "r") as f:
        system_prompt = f.read()

    cluster_topics(system_prompt, args.data, args.output, args.model, args.batch_size, args.slurm_config)