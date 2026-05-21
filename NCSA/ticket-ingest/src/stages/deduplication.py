import os
import json
import logging
import argparse

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
                    help="JSONL file containing the output of summarization to remove duplicates from.")

    # Optional arguments
    optional_args = parser.add_argument_group('Optional arguments', '')
    optional_args.add_argument('-c', '--slurm-config',
                    default="../../config/slurm_config.json",
                    type=parse_filepath,
                    help="Path to the Slurm configuration file. Defaults to ../config/slurm_config.json")
    optional_args.add_argument('-o', '--output', 
                    type=str, 
                    help='Path to the file to output deduplicated results to. Defaults to data/output/<input_file_name>_deduplicated_results.jsonl.')
    optional_args.add_argument('-m', '--model',
                    type=str, 
                    help="Model to use. Use llmflux --show-models to list available models.")
    optional_args.add_argument('-b', '--batch-size',
                    type=int,
                    help="Batch size to use.")
    optional_args.add_argument('-p', '--prompt',
                    default="../../prompts/deduplication.md",
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

def extract_qa_pairs(data: list[dict]) -> list[dict]:
    pairs = []
    for item in data:
        try:
            content = item["output"]["choices"][0]["message"]["content"]
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            pairs.append({
                "custom_id": item["input"]["custom_id"],
                "content": content
            })
        except (KeyError, IndexError):
            continue
    return pairs


def write_deduplication_prompts(prompt: str, pairs: list[dict], output_file: str):
    with open(output_file, "w") as f:
        for pair in pairs:
            f.write(json.dumps({
                "custom_id": pair["custom_id"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": pair["content"]}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 20
                }
            }) + "\n")

    logging.info(f"Wrote {len(pairs)} prompts to {output_file}")
    return len(pairs)

def dedup_by_topic(pairs: list[dict], topic_results_path: str) -> list[dict]:
    with open(topic_results_path) as f:
        topic_results = json.load(f)

    topic_map = {}
    for item in topic_results:
        try:
            topic = item["output"]["choices"][0]["message"]["content"].strip()
            topic = re.sub(r"<think>.*?</think>", "", topic, flags=re.DOTALL).strip()
            topic_map[item["input"]["custom_id"]] = topic
        except (KeyError, IndexError):
            continue

    seen_topics = {}
    for pair in pairs:
        topic = topic_map.get(pair["custom_id"], pair["custom_id"])
        if topic not in seen_topics:
            seen_topics[topic] = pair

    return list(seen_topics.values())

def remove_duplicates(prompt: str, input_file: str, output_file: str, model: str, batch_size: int, slurm_config_path: str):
    # Load evaluation data
    logging.debug(f"Loading summarization data from: {input_file}")
    with open(input_file, "r") as fh:
        summarization_data = json.load(fh)
    logging.info(f"Loaded {len(summarization_data)} Q/A pairs from {input_file}")

    # Create prompt file for LLMFLUX
    basename = os.path.basename(output_file).split('.')[0]
    if basename.endswith("_dedup_results"): # This is for ease of use in the pipeline
        basename = basename[:-len("_dedup_results")]
    llmflux_prompt_file = os.path.join(".llmflux/data/input", f"{basename}_dedup_prompts.jsonl")
    pairs = extract_qa_pairs(summarization_data)
    write_deduplication_prompts(prompt, pairs, llmflux_prompt_file)

    # Submit deduplication job
    slurm_config = SlurmConfig.load_from_json(slurm_config_path)
    # Override config values if provided on the command line
    model = slurm_config.model if model is None else model
    batch_size = slurm_config.batch_size if batch_size is None else batch_size

    job_id = submit_llmflux_job(llmflux_prompt_file, output_file, model, batch_size, slurm_config, job_name="Deduplication")
    
    # Monitor deduplication job
    monitor_llmflux_job(job_id, output_file, job_name="Deduplication")

    # Deduplicate by topic
    logging.info(f"Deduplicating by topic")
    deduped = dedup_by_topic(pairs, output_file)
    logging.info(f"Reduced {len(pairs)} -> {len(deduped)} unique Q/A pairs")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(deduped, f, indent=2)

if __name__ == "__main__":
    args = parse_command_line()
    if args.output is None:
        basename = os.path.basename(args.data).split('.')[0]
        if basename.endswith("_sum_results"): # This is for ease of use in the pipeline
            basename = basename[:-len("_sum_results")]
        args.output = f"data/output/{basename}_dedup_results.jsonl"

    file_log_level = logging.DEBUG if args.verbose else logging.INFO
    console_log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(args.log_file, file_log_level, console_log_level, use_color=True, writemode='a')

    # Load system prompt
    logger.info(f"Loading system prompt from: {args.prompt}")
    with open(args.prompt, "r") as f:
        system_prompt = f.read()

    remove_duplicates(system_prompt, args.data, args.output, args.model, args.batch_size, args.slurm_config)