import os
import re
import json
import logging
import pandas as pd

from math import ceil
from typing import Any, Dict, List

from llmflux.slurm import SlurmRunner
from llmflux.core.config import Config, EngineConfig

from src.llmflux_utils import SlurmConfig, submit_llmflux_job, monitor_llmflux_job


# region Summarization Stage
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
    logging.info(f"Wrote {_+1} prompts to \"{output_file}\"")

def summarize_tickets(prompt: str, input_file: str, output_file: str, model: str, slurm_config_path: str):
    # Load ticket data
    logging.debug(f"Loading ticket data from: {input_file}")
    df = pd.read_csv(input_file, dtype=str)
    logging.info(f"Loaded {len(df)} tickets from \"{input_file}\"")

    # Create prompt file for LLMFLUX
    basename = os.path.basename(output_file).split('.')[0]
    if basename.endswith("_sum_results"): # This is for ease of use in the pipeline
        basename = basename[:-len("_sum_results")]
    llmflux_prompt_file = os.path.join(".llmflux/data/input", f"{basename}_sum_prompts.jsonl")
    prep_ticket_data(df, prompt, llmflux_prompt_file)

    # Submit summarization job
    slurm_config = SlurmConfig.load_from_json(slurm_config_path)
    # Override config values if provided on the command line
    if model is not None:
        slurm_config.model = model
    
    job_id = submit_llmflux_job(llmflux_prompt_file, output_file, slurm_config, job_name="Summarization")

    # Monitor summarization job
    monitor_llmflux_job(job_id, output_file, job_name="Summarization")
    
    logging.info(f"Saved Summarization results to \"{output_file}\"")
# endregion Summarization Stage

# region Evaluation Stage
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)

def split_thinking_text(text: str) -> tuple[str, str]:
    """Split response into (thinking_text, non_thinking_text)."""
    if not text:
        return "", ""

    thinking_parts = THINK_BLOCK_RE.findall(text)
    non_thinking = THINK_BLOCK_RE.sub("", text).strip()
    thinking_text = "\n".join(part.strip() for part in thinking_parts if part.strip())
    return thinking_text, non_thinking

def strip_thinking(text: str) -> str:
    """Remove thinking blocks from text."""
    return THINK_BLOCK_RE.sub("", text).strip()

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

    logging.info(f"Wrote {len(data)} prompts to \"{output_file}\"")
    return len(data)

def summarize_results(output_path: str) -> List[Dict[str, Any]]:
    with open(output_path, "r") as fh:
        data = json.load(fh)
    fails = []
    for item in data:
        think, json_response = split_thinking_text(item["output"]["choices"][0]["message"]["content"])
        try:
            item_data = json.loads(json_response)
            item_data["thinking"] = think
            item_data["id"] = item["input"]["custom_id"]
            item_data["input"] = strip_thinking(item["input"]["body"]["messages"][1]["content"])
            if item_data["pass_fail"] == "FAIL":
                logging.warning(f"PII detected in response: {item['input']['custom_id']}")
                fails.append(item_data)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse JSON: {json_response}")
            continue

    if len(fails) > 0:
        basename = os.path.basename(output_path).split('.')[0]
        if basename.endswith("_eval_results"): # This is for ease of use in the pipeline
            basename = basename[:-len("_eval_results")]
        with open(f"logs/{basename}_evaluation_failures.json", "w") as fh:
            fh.write(json.dumps(fails, indent=4))
        logging.info(f"Saved evaluation failures to \"logs/{basename}_evaluation_failures.json\"")
    logging.info(f"{len(fails)}/{len(data)} responses failed ({len(fails)/len(data)*100:.2f}%) fail rate")

    return fails

def evaluate_summarization(prompt: str, input_file: str, output_file: str, model: str, slurm_config_path: str):
    # Load evaluation data
    logging.debug(f"Loading summarization data from: {input_file}")
    with open(input_file, "r") as fh:
        summarization_data = json.load(fh)
    logging.info(f"Loaded {len(summarization_data)} Q/A pairs from \"{input_file}\"")

    # Create prompt file for LLMFLUX
    basename = os.path.basename(output_file).split('.')[0]
    if basename.endswith("_eval_results"): # This is for ease of use in the pipeline
        basename = basename[:-len("_eval_results")]
    llmflux_prompt_file = os.path.join(".llmflux/data/input", f"{basename}_eval_prompts.jsonl")
    prep_evaluation_data(summarization_data, prompt, llmflux_prompt_file)

    # Submit evaluation job
    slurm_config = SlurmConfig.load_from_json(slurm_config_path)
    # Override config values if provided on the command line
    if model is not None:
        slurm_config.model = model

    job_id = submit_llmflux_job(llmflux_prompt_file, output_file, slurm_config, job_name="Evaluation")
    
    # Monitor evaluation job
    monitor_llmflux_job(job_id, output_file, job_name="Evaluation")

    # Summarize results
    summarize_results(output_file)

    logging.info(f"Saved Evaluation results to \"{output_file}\"")
# endregion Evaluation Stage

# region Deduplication Stage
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

    logging.info(f"Wrote {len(pairs)} prompts to \"{output_file}\"")
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

def remove_duplicates(prompt: str, input_file: str, output_file: str, model: str, slurm_config_path: str):
    # Load evaluation data
    logging.debug(f"Loading summarization data from: {input_file}")
    with open(input_file, "r") as fh:
        summarization_data = json.load(fh)
    logging.info(f"Loaded {len(summarization_data)} Q/A pairs from \"{input_file}\"")

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
    if model is not None:
        slurm_config.model = model

    job_id = submit_llmflux_job(llmflux_prompt_file, output_file, slurm_config, job_name="Deduplication")
    
    # Monitor deduplication job
    monitor_llmflux_job(job_id, output_file, job_name="Deduplication")

    # Deduplicate by topic
    logging.info(f"Deduplicating by topic")
    deduped = dedup_by_topic(pairs, output_file)
    logging.info(f"Reduced {len(pairs)} -> {len(deduped)} unique Q/A pairs")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(deduped, f, indent=2)

    logging.info(f"Saved Deduplication results to \"{output_file}\"")
# endregion Deduplication Stage