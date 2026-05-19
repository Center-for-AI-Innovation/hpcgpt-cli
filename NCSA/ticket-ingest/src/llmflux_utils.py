import os
import logging

from time import sleep
from pathlib import Path
from pydantic import BaseModel, Field
from llmflux.slurm import SlurmRunner
from llmflux.core.config import Config, EngineConfig

class SlurmConfig(BaseModel):
    account: str = Field(description="Slurm account name.")
    partition: str = Field(description="Slurm partition name.")
    time: str = Field(description="Time limit in HH:MM:SS format.")
    mem: str = Field(description="Memory.")
    gpus_per_node: int = Field(description="Number of GPUs per node.")
    nodes: int = Field(description="Number of nodes to use.")
    cpus_per_task: int = Field(description="Number of CPUs per task.")
    model: str = Field(description="Model to use.")
    batch_size: int = Field(description="Batch size to use.")

    @classmethod
    def load_from_json(cls, filepath: str) -> "SlurmConfig":
        with open(filepath, "r") as fh:
            return cls.model_validate_json(fh.read())

def submit_llmflux_job(input_file: str, output_file: str, model: str, batch_size: int, my_slurm_config: SlurmConfig, job_name: str = "LLMFLUX"):
    """
    Wrapper function to submit a job with LLMFlux.

    Args:
        input_file: Path to the input file (JSONL file containing the prompts for the LLM).
        output_file: Path to the output file.
        model: Model to use.
        batch_size: Batch size to use.
        my_slurm_config: Slurm configuration to use.
        job_name: Name of the job.

    Returns:
        Job ID.
    """
    # Create Job workspace directories if necessary
    cwd = Path.cwd().resolve()
    os.makedirs(cwd / ".llmflux" / "logs", exist_ok=True)
    os.makedirs(cwd / ".llmflux" / "data", exist_ok=True)
    os.makedirs(cwd / ".llmflux" / "models", exist_ok=True)
    os.makedirs(cwd / ".llmflux" / "tmp", exist_ok=True)
    os.makedirs(cwd / ".llmflux" / "containers", exist_ok=True)
    os.environ["LLMFLUX_LOGS_DIR"] = str(cwd / ".llmflux" / "logs")
    os.environ["LLMFLUX_DATA_DIR"] = str(cwd / ".llmflux" / "data")
    os.environ["LLMFLUX_MODELS_DIR"] = str(cwd / ".llmflux" / "models") 
    os.environ["LLMFLUX_TMP_DIR"] = str(cwd / ".llmflux" / "tmp")
    os.environ["LLMFLUX_CONTAINERS_DIR"] = str(cwd / ".llmflux" / "containers")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Set Slurm parameters for llmflux
    config = Config()
    slurm_config = config.get_slurm_config()
    slurm_config.account = my_slurm_config.account
    slurm_config.partition = my_slurm_config.partition
    slurm_config.time = my_slurm_config.time
    slurm_config.mem = my_slurm_config.mem
    slurm_config.gpus_per_node = my_slurm_config.gpus_per_node
    slurm_config.nodes = my_slurm_config.nodes
    slurm_config.cpus_per_task = my_slurm_config.cpus_per_task
    #slurm_config.job_name = job_name

    # Submit the job to Slurm
    runner = SlurmRunner(
        config=slurm_config,
        workspace=str(cwd),
        engine_config=EngineConfig(engine="vllm", home=str(cwd / ".vllm")),
    )

    job_id = runner.run(
        input_path=input_file,
        output_path=output_file,
        model=model,
        batch_size=batch_size,
    )

    logging.info(f"{job_name} job {job_id} submitted")
    return job_id

def monitor_llmflux_job(job_id: str, job_name: str = "LLMFLUX"):
    """
    Convenience function to monitor the progress of an LLMFlux job.

    Args:
        job_id: Slurm Job ID to monitor.
        job_name: Name of the job. (only used for logging purposes)

    Returns:
        None.
    """
    while not os.path.exists(str(Path.cwd().resolve() / "logs" / f"{job_id}.out")):
        sleep(1)
    logging.info(f"{job_name} job {job_id} started")
    while not os.path.exists(output_file):
        sleep(1)
    logging.info(f"{job_name} job {job_id} completed")