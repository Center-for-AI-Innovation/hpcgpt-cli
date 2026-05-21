import os
import logging
import subprocess

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

_ACTIVE_SACCT_STATES = frozenset({
    "PENDING", "RUNNING", "CONFIGURING", "COMPLETING", "REQUEUED", "RESIZING", "SUSPENDED",
})
_SUCCESS_SACCT_STATES = frozenset({"COMPLETED"})
_FAILED_SACCT_STATES = frozenset({
    "FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL", "PREEMPTED", "OUT_OF_MEMORY",
    "BOOT_FAIL", "DEADLINE", "REVOKED",
})


def _get_sacct_state(job_id: str) -> str | None:
    """Return the Slurm job state from sacct, or None if not yet in accounting."""
    result = subprocess.run(
        ["sacct", "-j", str(job_id), "-X", "-n", "-o", "State"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"sacct failed for job {job_id}: {stderr or result.stdout.strip()}")

    for line in result.stdout.splitlines():
        state = line.strip().split()[0] if line.strip() else ""
        if not state:
            continue
        # States may include a suffix (e.g. COMPLETED+).
        return state.split("+", 1)[0]
    return None


def monitor_llmflux_job(job_id: str, output_file: str, job_name: str = "LLMFlux", poll_interval: float = 2.0):
    """
    Monitor an LLMFlux Slurm job until it finishes and the output file exists.

    Uses sacct to poll job state instead of watching log or output files on disk.

    Args:
        job_id: Slurm Job ID to monitor.
        output_file: Path to the output file.
        job_name: Name of the job (only used for logging).
        poll_interval: Seconds between sacct polls.

    Returns:
        None.

    Raises:
        RuntimeError: If sacct fails or the job ends in a non-success state.
    """
    logged_running = False

    while True:
        state = _get_sacct_state(job_id)

        if state is None:
            sleep(poll_interval)
            continue

        if state in _ACTIVE_SACCT_STATES:
            if state == "RUNNING" and not logged_running:
                logging.info(f"{job_name} job {job_id} started")
                logged_running = True
            sleep(poll_interval)
            continue

        if state in _SUCCESS_SACCT_STATES:
            break

        if state in _FAILED_SACCT_STATES:
            raise RuntimeError(f"{job_name} job {job_id} ended with state {state}")

        raise RuntimeError(f"{job_name} job {job_id} ended with unknown state {state}")

    while not os.path.exists(output_file):
        sleep(poll_interval)
    logging.info(f"{job_name} job {job_id} completed")