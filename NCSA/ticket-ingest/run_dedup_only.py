import logging
from src.stages import remove_duplicates
from src.log_utils import setup_logger

MODEL = "gpt-oss-120b"

datasets = [
    ("Delta", f".llmflux/data/output/Delta_knowledge_base_{MODEL}_sum_results.jsonl"),
    ("DeltaAI", f".llmflux/data/output/DeltaAI_knowledge_base_{MODEL}_sum_results.jsonl"),
]

if __name__ == "__main__":
    logger = setup_logger("logs/dedup_only_run.log", logging.INFO, logging.INFO, use_color=True, writemode='w')

    with open("prompts/deduplication.md", "r") as f:
        system_prompt = f.read()

    for label, sum_file in datasets:
        try:
            logger.info(f"Starting dedup for {label}")
            output_file = f"results/{label}_knowledge_base_{MODEL}_deduped.jsonl"
            remove_duplicates(
                system_prompt,
                sum_file,
                output_file,
                MODEL,
                "config/slurm_config.json"
            )
            logger.info(f"Dedup for {label} completed successfully -> {output_file}")
        except Exception as e:
            logger.exception(f"Failed dedup for {label}: {e}")
            continue

    logger.info("All dedup runs completed")
