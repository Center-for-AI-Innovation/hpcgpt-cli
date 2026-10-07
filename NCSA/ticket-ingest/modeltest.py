import os
import re
import json
import logging
from time import sleep
from types import SimpleNamespace

from src.log_utils import setup_logger
from src.stages import summarize_tickets, evaluate_summarization

models = [
    "Qwen3-8B",
    "Qwen3-32B",
    "glm-4-9b-chat-hf",
    "gpt-oss-120b",
    "Mixtral-8x7B-Instruct-v0.1",
]

judges = [
    "gpt-oss-120b",
    "Mixtral-8x7B-Instruct-v0.1",
]

need_perms = [
    "Kimi-K2.5",
    "gemma-2-27b-it",
    "gemma-3-12b-it",
    "gemma-3-27b-it",
]

not_enough_mem = [
    "Mistral-Large-Instruct-2411",
    "Mixtral-8x22B-Instruct-v0.1",
]

# Dropped from active testing: DeepSeek-R1-Distill family
# (Qwen-7B, Qwen-32B unusable - evaluation stage never produces parseable JSON;
#  Llama-70B - worst PII fail rate of any working model, 7/10)
dropped = [
    "DeepSeek-R1-Distill-Qwen-7B",
    "DeepSeek-R1-Distill-Qwen-32B",
    "DeepSeek-R1-Distill-Llama-70B",
]

data = "data/raw/dt25-100s.csv"

with open("config/slurm_config.json", "r") as f:
    default_slurm_config = json.load(f)

import matplotlib.pyplot as plt

def graph_eval_results():
    fail_rates = {}
    for model in models:
        for judge in judges:
            if model == judge:
                continue
            log_path = f"logs/{model}_judged_by_{judge}.log"
            try:
                with open(log_path, "r") as f:
                    lines = f.readlines()
                for line in lines:
                    if "fail rate" in line:
                        match = re.search(r"\(([\d\.]+)%\) fail rate", line)
                        if match:
                            fail_rate = float(match.group(1))
                            fail_rates[f"{model}\n(by {judge})"] = fail_rate
            except Exception as e:
                logging.warning(f"Could not process {log_path}: {e}")

    if not fail_rates:
        print("No fail rates found to plot.")
        return

    models_list = list(fail_rates.keys())
    rates = [fail_rates[m] for m in models_list]
    plt.figure(figsize=(12, 6))
    plt.bar(models_list, rates, color='tomato')
    plt.xlabel("Model (judged by)")
    plt.ylabel("Failure Rate (%)")
    plt.title("Model Summarization Evaluation Failure Rates (dual judges)")
    plt.ylim(0, max(rates) + 5)
    for i, v in enumerate(rates):
        plt.text(i, v + 0.5, f"{v:.2f}%", ha='center', va='bottom')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(f"model_eval_fail_rates.png")


def process_model(model):
    label = os.path.basename(data).split('.')[0]

    # --- Summarization stage: run once per model ---
    sum_config = default_slurm_config.copy()
    sum_config["model"] = model
    sum_config_path = f"config/slurm_config_{model}_sum.json"
    with open(sum_config_path, "w") as f:
        json.dump(sum_config, f)
    logging.info(f"Wrote slurm config for {model} summarization to {sum_config_path}")

    with open("prompts/summarization.md", "r") as f:
        sum_prompt = f.read()

    sum_output = f".llmflux/data/output/{label}_{model}_sum_results.jsonl"
    logging.info(f"Running summarization for {model}")
    summarize_tickets(sum_prompt, data, sum_output, model, sum_config_path)
    logging.info(f"Summarization for {model} completed")

    # --- Evaluation stage: run once per judge ---
    with open("prompts/evaluation.md", "r") as f:
        eval_prompt = f.read()

    for judge in judges:
        if judge == model:
            logging.info(f"Skipping self-eval pairing setup note: {model} judged by {judge} (self-eval)")

        judge_config = default_slurm_config.copy()
        judge_config["model"] = judge
        judge_config_path = f"config/slurm_config_{model}_judged_by_{judge}.json"
        with open(judge_config_path, "w") as f:
            json.dump(judge_config, f)

        eval_output = f"results/{label}_{model}_judged_by_{judge}_results.jsonl"
        logging.info(f"Evaluating {model}'s summaries using judge {judge}")

        # Set up per-(model,judge) logger so graph_eval_results can find fail rate
        pair_logger = logging.getLogger(f"{model}_judged_by_{judge}")
        file_handler = logging.FileHandler(f"logs/{model}_judged_by_{judge}.log", mode='w')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

        try:
            evaluate_summarization(eval_prompt, sum_output, eval_output, judge, judge_config_path)
            logging.info(f"Evaluation of {model} by {judge} completed")
        finally:
            root_logger.removeHandler(file_handler)
            file_handler.close()


if __name__ == "__main__":
    file_log_level = logging.INFO
    console_log_level = logging.INFO
    logger = setup_logger("logs/modeltest.log", file_log_level, console_log_level, use_color=True, writemode='w')

    for model in models:
        try:
            logger.info(f"Running {model}")
            process_model(model)
            logger.info(f"{model} completed")
        except Exception as e:
            logger.exception(f"Failed to run {model}: {e}")
            continue

    logger.info("Models completed")
    logger.info("Graphing evaluation results")
    graph_eval_results()
