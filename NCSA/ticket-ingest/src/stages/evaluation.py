import os
import re
import json
import logging
import argparse

from math import ceil
from pathlib import Path
from typing import Any, Dict, List

from ..log_utils import setup_logger
from ..llmflux_utils import SlurmConfig, submit_llmflux_job, monitor_llmflux_job

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)

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
                    help="JSONL file containing the output of summarization to evaluate for PII.")

    # Optional arguments
    optional_args = parser.add_argument_group('Optional arguments', '')
    optional_args.add_argument('-c', '--slurm-config',
                    default="../../config/slurm_config.json",
                    type=parse_filepath,
                    help="Path to the Slurm configuration file. Defaults to ../config/slurm_config.json")
    optional_args.add_argument('-o', '--output', 
                    type=str, 
                    help='Path to the file to output evaluation results to. Defaults to data/output/<input_file_name>_evaluation_results.jsonl.')
    optional_args.add_argument('-m', '--model',
                    type=str, 
                    help="Model to use. Use llmflux --show-models to list available models.")
    optional_args.add_argument('-b', '--batch-size',
                    type=int,
                    help="Batch size to use.")
    optional_args.add_argument('-p', '--prompt',
                    default="../../prompts/evaluation.md",
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

def split_thinking_text(text: str) -> tuple[str, str]:
    """Split response into (thinking_text, non_thinking_text)."""
    if not text:
        return "", ""

    thinking_parts = THINK_BLOCK_RE.findall(text)
    non_thinking = THINK_BLOCK_RE.sub("", text).strip()
    thinking_text = "\n".join(part.strip() for part in thinking_parts if part.strip())
    return thinking_text, non_thinking

def prep_qa_pair(content: str) -> Dict[str, Any]:
    thinking_text, qa_text = split_thinking_text(content)
    prompt = (
        "Evaluate the following Q/A response for PII.\n\n"
        f"Q/A RESPONSE:\n{qa_text}\n"
    )

    return prompt

def prep_evaluation_data(data, prompt: str, output_file: str):
    # Write Evaluation Prompts
    with open(output_file, "w") as fh:
        for item in data:
            qa_pair = prep_qa_pair(item["output"]["choices"][0]["message"]["content"])
            fh.write(json.dumps({
                "custom_id": item["input"]["custom_id"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "messages": [
                        {
                            "role": "system",
                            "content": prompt
                        },
                        {
                            "role": "user",
                            "content": qa_pair
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            }) + "\n")

    logging.info(f"Wrote {len(data)} prompts to {output_file}")
    return len(data)

def summarize_results(output_path: str) -> List[Dict[str, Any]]:
    with open(output_path, "r") as fh:
        data = [json.loads(line) for line in fh]
    fails = []
    for item in data:
        think, json_response = split_thinking_text(item["output"]["choices"][0]["message"]["content"])
        try:
            item_data = json.loads(json_response)
            item_data["thinking"] = think
            item_data["id"] = item["input"]["custom_id"]
            item_data["input"] = strip_thinking(item["input"]["body"]["messages"][1]["content"])
            if item_data["pass_fail"] == "FAIL":
                logging.info(f"Failed response: {item['input']['custom_id']}")
                fails.append(item_data)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse JSON: {json_response}")
            continue

    with open("evaluation_failures.json", "w") as fh:
        json.dump(fails, fh, indent=4)
    logging.info(f"{len(fails)}/{len(data)} responses failed ({len(fails)/len(data)*100:.2f}%) fail rate")

    return fails

def evaluate_summarization(prompt: str, input_file: str, output_file: str, model: str, batch_size: int, slurm_config_path: str):
    # Load evaluation data
    logging.debug(f"Loading summarization data from: {input_file}")
    with open(input_file, "r") as fh:
        summarization_data = json.load(fh)
    logging.info(f"Loaded {len(summarization_data)} Q/A pairs from {input_file}")

    # Create prompt file for LLMFLUX
    basename = os.path.basename(output_file).split('.')[0]
    if basename.endswith("_eval_results"): # This is for ease of use in the pipeline
        basename = basename[:-len("_eval_results")]
    llmflux_prompt_file = os.path.join(".llmflux/data/input", f"{basename}_eval_prompts.jsonl")
    prep_evaluation_data(summarization_data, prompt, llmflux_prompt_file)

    # Submit evaluation job
    slurm_config = SlurmConfig.load_from_json(slurm_config_path)
    # Override config values if provided on the command line
    model = slurm_config.model if model is None else model
    batch_size = slurm_config.batch_size if batch_size is None else batch_size

    #job_id = submit_llmflux_job(llmflux_prompt_file, output_file, model, batch_size, slurm_config, job_name="Evaluation")
    
    # Monitor evaluation job
    #monitor_llmflux_job(job_id, output_file, job_name="Evaluation")

    # Summarize results
    summarize_results(output_file)

if __name__ == "__main__":
    args = parse_command_line()
    if args.output is None:
        basename = os.path.basename(args.data).split('.')[0]
        if basename.endswith("_sum_results"): # This is for ease of use in the pipeline
            basename = basename[:-len("_sum_results")]
        args.output = f"data/output/{basename}_eval_results.jsonl"

    file_log_level = logging.DEBUG if args.verbose else logging.INFO
    console_log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(args.log_file, file_log_level, console_log_level, use_color=True, writemode='a')

    # Load system prompt
    logger.info(f"Loading system prompt from: {args.prompt}")
    with open(args.prompt, "r") as f:
        system_prompt = f.read()

    evaluate_summarization(system_prompt, args.data, args.output, args.model, args.batch_size, args.slurm_config)