import os
import re
import json
import logging
from time import sleep
from types import SimpleNamespace
from ticket_pipeline import main

from src.log_utils import setup_logger

models = [
    "Qwen3-8B",
    "Qwen3-32B",
    "glm-4-9b-chat-hf",
    "DeepSeek-R1-Distill-Qwen-7B",
    "DeepSeek-R1-Distill-Qwen-32B",
    "DeepSeek-R1-Distill-Llama-70B",
    "gpt-oss-120b",
    "Mistral-Large-Instruct-2411",
    "Mixtral-8x7B-Instruct-v0.1",
    "Mixtral-8x22B-Instruct-v0.1",
]

need_perms = [
    "Kimi-K2.5",
    "gemma-2-27b-it",
    "gemma-3-12b-it",
    "gemma-3-27b-it",
]

# models = [
#     "Qwen3-8B",
#     "DeepSeek-R1-Distill-Qwen-7B"
# ]
data = "data/raw/dt25-10s.csv"

with open("config/slurm_config.json", "r") as f:
    default_slurm_config = json.load(f)

import concurrent.futures

def graph_eval_results():
    fail_rates = {}
    for model in models:
        with open(f"logs/{model}.log", "r") as f:
            lines = f.readlines()
        for line in lines:
            if "fail rate" in line:
                # Extract the percentage value for fail rate from the line
                
                match = re.search(r"\(([\d\.]+)%\) fail rate", line)
                if match:
                    fail_rate = float(match.group(1))
                    fail_rates[model] = fail_rate
        
import matplotlib.pyplot as plt

def graph_eval_results():
    fail_rates = {}
    for model in models:
        log_path = f"logs/{model}.log"
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
            for line in lines:
                if "fail rate" in line:
                    match = re.search(r"\(([\d\.]+)%\) fail rate", line)
                    if match:
                        fail_rate = float(match.group(1))
                        fail_rates[model] = fail_rate
        except Exception as e:
            logging.warning(f"Could not process {log_path}: {e}")

    if not fail_rates:
        print("No fail rates found to plot.")
        return

    # Plot
    models_list = list(fail_rates.keys())
    rates = [fail_rates[m] for m in models_list]
    plt.figure(figsize=(8, 5))
    plt.bar(models_list, rates, color='tomato')
    plt.xlabel("Model")
    plt.ylabel("Failure Rate (%)")
    plt.title("Model Summarization Evaluation Failure Rates")
    plt.ylim(0, max(rates) + 5)
    for i, v in enumerate(rates):
        plt.text(i, v + 0.5, f"{v:.2f}%", ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig(f"model_eval_fail_rates.png")


def process_model(model):
    logger = setup_logger(f"logs/{model}.log", logging.INFO, use_color=True, writemode='w')

    # Delay submission between models to avoid file conflicts
    sleep(0.1 * models.index(model))

    # Setup config for model
    model_config = default_slurm_config.copy()
    model_config["model"] = model
    with open(f"config/slurm_config_{model}.json", "w") as f:
        json.dump(model_config, f)
    logging.info(f"Wrote slurm config for {model} to config/slurm_config_{model}.json")

    # Run pipeline
    args = SimpleNamespace(
        data=data,
        slurm_config=f"config/slurm_config_{model}.json",
        output=f"results/{os.path.basename(data).split('.')[0]}_{model}_results.jsonl",
        model=model
    )
    logging.info(f"Running pipeline for {model} with data {data} and slurm config {args.slurm_config}")
    main(args)
    logging.info(f"Pipeline for {model} completed")

if __name__ == "__main__":
    file_log_level = logging.INFO
    console_log_level = logging.INFO
    logger = setup_logger("logs/modeltest.log", file_log_level, console_log_level, use_color=True, writemode='w')
    
    logger.info(f"Running modeltest with data {data} and models {models}")
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(models)) as executor:
        for model, exc in zip(models, executor.map(process_model, models)):
            if exc:
                logger.exception("Failed for %s", model)
    logger.info("Models completed")
    logger.info("Graphing evaluation results")
    graph_eval_results()