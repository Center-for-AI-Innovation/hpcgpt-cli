---
name: slurm
description: >
  Use the Slurm Workload Manager, write batch job scripts, debug common
  job submission and/or scheduling problems, and execute its client
  commands such as sbatch, squeue, and scancel. Use when a command-line
  call to a Slurm client command is required to respond to a user prompt.
license: MIT
compatibility: opencode
metadata:
  author: Marty Kandes (mkandes@sdsc.edu)
  updated: 2026-07-30
  version: 0.1.0
---

## Overview

[Slurm Workload Manager](https://en.wikipedia.org/wiki/Slurm_Workload_Manager) 
is an open-source, fault-tolerant, and highly-scalable 
[cluster](https://en.wikipedia.org/wiki/Computer_cluster) management
and [batch](https://en.wikipedia.org/wiki/Batch_processing) 
[job](https://en.wikipedia.org/wiki/Job_(computing))
[scheduling system](https://en.wikipedia.org/wiki/Job_scheduler) for
Linux used by the majority of the world's 
[supercomputers](https://en.wikipedia.org/wiki/Supercomputer) and 
[high-performance computing (HPC)](https://en.wikipedia.org/wiki/High-performance_computing)
systems. 

Slurm has three key functions. First, it allocates exclusive and/or
non-exclusive access to resources (compute nodes) to users for some
duration of time so they can perform work. Second, it provides a 
framework for starting, executing, and monitoring work 
([jobs](https://en.wikipedia.org/wiki/Job_(computing))) on the
set of allocated resources (compute nodes). Finally, it arbitrates
contention for resources by managing a 
[queue](https://en.wikipedia.org/wiki/Job_queue) of pending work.

## Documentation

The official documentation for the Slurm Workload Manager is available 
online at [https://slurm.schedmd.com](https://slurm.schedmd.com).

## Source Code

The official source code for the Slurm Workload Manager is available 
online at [https://github.com/SchedMD/slurm.git](https://github.com/SchedMD/slurm.git).

## How It Works

The Slurm architecture consists of:

- [`slurmd`](https://slurm.schedmd.com/slurmd.html), a compute node 
  [daemon](https://en.wikipedia.org/wiki/Daemon_(computing)) that monitors
  all [tasks](https://en.wikipedia.org/wiki/Task_(computing)) running on 
  compute nodes within a cluster, accepts work (tasks), launches tasks, 
  and [kills](https://en.wikipedia.org/wiki/Kill_(command)) running tasks 
  upon request;

- [`slurmctld`](https://slurm.schedmd.com/slurmctld.html), a central 
  management daemon that monitors all other Slurm daemons and resources, 
  accepts work (jobs), and allocates resources to those jobs; and

- [`slurmdbd`](https://slurm.schedmd.com/slurmdbd.html), a database 
  interface daemon used for archiving accounting records.

The entities managed by Slurm are:

- *nodes*, compute resources managed by Slurm,
- *partitions*, groups of nodes assigned to logical sets,
- *jobs*, allocations of resources assigned to a user for a specified
  amount of time, and
- *job steps*, the tasks assigned by the user within a job.

Partitions can be considered job queues, each of which represents a 
distinct set of compute resources or constraints such as job size limit, 
job time limit, users permitted to use it, etc. 

Jobs are allocated nodes in order of their prority within a given
partition on a cluster until the compute resources (nodes, processors, 
memory, GPUs, etc.) within that partition are exhausted. 

Once a job is assigned a set of nodes, the user is able to perform work
in the form of job steps in any configuration within the allocation. For
instance, a single job step may be started that executes a single command
across all nodes and their resources allocated to the job, or several job
steps may independently use a portion of the job allocation.

## Client Commands

The client commands for the Slurm Workload Manager are as follows: 

- [`sacct`](https://slurm.schedmd.com/sacct.html) is used to report job
  or job step accounting information about active or completed jobs.

- [`salloc`](https://slurm.schedmd.com/salloc.html) is used to allocate
  resources for a job in real time. Typically this is used to allocate 
  resources and spawn a shell. The shell is then used to execute srun 
  commands to launch parallel tasks.

- [`sattach`](https://slurm.schedmd.com/sattach.html) is used to attach
  standard input, output, and error plus signal capabilities to a 
  currently running job or job step. One can attach to and detach from
  jobs multiple times.

- [`sbatch`](https://slurm.schedmd.com/sbatch.html) is used to submit a
  job script for later execution. The script will typically contain one
  or more srun commands to launch parallel tasks.

- [`sbcast`](https://slurm.schedmd.com/sbcast.html) is used to transfer
  a file from local disk to local disk on the nodes allocated to a job. 
  This can be used to effectively use diskless compute nodes or provide
  improved performance relative to a shared file system.

- [`scancel`](https://slurm.schedmd.com/scancel.html) is used to cancel
  a pending or running job or job step. It can also be used to send an 
  arbitrary signal to all processes associated with a running job or job
  step.

- [`scontrol`](https://slurm.schedmd.com/scontrol.html) is the administrative
  tool used to view and/or modify Slurm state. Note that many scontrol
  commands can only be executed as user root. 

- [`sinfo`](https://slurm.schedmd.com/sinfo.html) reports the state of 
  partitions and nodes managed by Slurm. It has a wide variety of 
  filtering, sorting, and formatting options.

- [`sprio`](https://slurm.schedmd.com/sprio.html) is used to display a 
  detailed view of the components affecting a job's priority.

- [`squeue`](https://slurm.schedmd.com/squeue.html) reports the state of
  jobs or job steps. It has a wide variety of filtering, sorting, and
  formatting options. By default, it reports the running jobs in priority
  order and then the pending jobs in priority order.

- [`srun`](https://slurm.schedmd.com/srun.html) is used to submit a job
  for execution or initiate job steps in real time. srun has a wide 
  variety of options to specify resource requirements, including: minimum
  and maximum node count, processor count, specific nodes to use or not
  use, and specific node characteristics (so much memory, disk space, 
  certain required features, etc.). A job can contain multiple job steps
  executing sequentially or in parallel on independent or shared resources
  within the job's node allocation. It is also often used to create an 
  interactive shell session on a compute node.

- [`sshare`](https://slurm.schedmd.com/sshare.html) displays detailed
  information about fairshare usage on the cluster. Note that this is 
  only viable when using the priority/multifactor plugin.

- [`sstat`](https://slurm.schedmd.com/sstat.html) is used to get 
  information about the resources utilized by a running job or job step.

- [`strigger`](https://slurm.schedmd.com/strigger.html) is used to set,
  get or view event triggers. Event triggers include things such as nodes
  going down or jobs approaching their time limit.

- [`sview`](https://slurm.schedmd.com/sview.html) is a graphical user 
  interface to get and update state information for jobs, partitions,
  and nodes managed by Slurm.

## Guidelines

The following guidelines are a set of general rules, advice, and 
instructions on how an agent or subagent should interact with and
utilize the Slurm Workload Manager for common use cases.

- Whenever possible, related work should be placed within a single Slurm
  job with multiple job steps both for performance reasons and ease of 
  management. Each Slurm job can contain a multitude of job steps and
  the overhead in Slurm for managing job steps is much lower than that
  of individual jobs.

- Slurm [job arrays](https://slurm.schedmd.com/job_array.html) are an 
  efficient mechanism of managing a collection of batch jobs with
  identical resource requirements. Most Slurm client commands can manage
  job arrays either as individual elements (tasks) or as a single 
  entity (e.g., delete an entire job array in a single command).

- Whenever possible, Slurm should directly launch 
  [Message Passing Interface (MPI)](https://en.wikipedia.org/wiki/Message_Passing_Interface) 
  processes  and perform communication initialization via its PMI2 or 
  PMIx APIs, which are generally supported by most modern MPI 
  implementations. See the Slurm [MPI Users Guide](https://slurm.schedmd.com/mpi_guide.html) 
  for more information.

- Use the `squeue --me` command to check the status of a user's 
  running (`R`) and/or pending (`PD`) jobs

- Use the `sacct -j <SLURM_JOB_ID> --format=JobID,State,ExitCode,MaxRSS,Elapsed,NodeList`
  command to check the status of a user's completed jobs

- Copy and/or write temporary data to `$SLURM_TMPDIR`, which is available
  only while a job is running.

- Do not use a `premept` partition, unless the user confirms their jobs
  are restartable.

- Verify that all file and directory paths used within a batch job
  script exist before any job submission.

- Always test new jobs scripts using a `debug` partition, when available.

## Gaurdrails

The following guardrails are a set of safety rules, policies, and technical
controls that aim to limit and/or restrict an agent or subagent's use of the
Slurm Workload Manager.

- Never submit a job using the `sbatch` command without a confirmation
  by the user.

## Common Problems

The following list includes a number of commom problems, including the error
messages associated with different failure modes, often encountered when 
working with the Slurm Workload Manager.

- [Out-Of-Memory (OOM)](https://www.osc.edu/documentation/knowledge_base/out_of_memory_oom_or_excessive_memory_usage)

## References

Use any of the additional references listed below when necessary:

- [Frequently Asked Questions (FAQ)](https://slurm.schedmd.com/faq.html)
