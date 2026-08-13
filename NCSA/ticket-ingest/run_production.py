import os
import json
import logging
from types import SimpleNamespace

from src.log_utils import setup_logger
from ticket_pipeline import main

MODEL = "gpt-oss-120b"

datasets = [
    ("Delta", "data/raw/Delta_tickets_jan25-jun26.csv"),
    ("DeltaAI", "data/raw/DeltaAI_tickets_jan25-jun26.csv"),
]

with open("config/slurm_config.json", "r") as f:
    default_slurm_config = json.load(f)


def process_dataset(label, data_path):
    model_config = default_slurm_config.copy()
    model_config["model"] = MODEL
    config_path = f"config/slurm_config_{label}_production.json"
    with open(config_path, "w") as f:
        json.dump(model_config, f)
    logging.info(f"Wrote slurm config for {label} production run to {config_path}")

    args = SimpleNamespace(
        data=data_path,
        slurm_config=config_path,
        output=f"results/{label}_knowledge_base_{MODEL}.jsonl",
        model=MODEL
    )
    logging.info(f"Running production pipeline for {label} ({data_path}) with model {MODEL}")
    main(args)
    logging.info(f"Production pipeline for {label} completed")


if __name__ == "__main__":
    logger = setup_logger("logs/production_kb_build.log", logging.INFO, logging.INFO, use_color=True, writemode='w')

    for label, data_path in datasets:
        try:
            logger.info(f"Starting {label}")
            process_dataset(label, data_path)
            logger.info(f"{label} completed successfully")
        except Exception as e:
            logger.exception(f"Failed to process {label}: {e}")
            continue

    logger.info("All production runs completed")
