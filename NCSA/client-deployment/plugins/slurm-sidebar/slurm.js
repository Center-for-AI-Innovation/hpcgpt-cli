const ACTIVE_STATES = new Set([
  "CONFIGURING",
  "COMPLETING",
  "PENDING",
  "RUNNING",
  "RESIZING",
  "REQUEUED",
  "REQUEUE_FED",
  "REQUEUE_HOLD",
  "SIGNALING",
  "STAGE_OUT",
  "SUSPENDED",
])
const TERMINAL_STATES = new Set([
  "BOOT_FAIL",
  "CANCELLED",
  "COMPLETED",
  "DEADLINE",
  "FAILED",
  "NODE_FAIL",
  "OUT_OF_MEMORY",
  "PREEMPTED",
  "TIMEOUT",
])

function numberValue(value) {
  if (value && typeof value === "object" && "number" in value) {
    if (value.set === false || value.infinite === true) return undefined
    return value.number
  }
  return typeof value === "number" ? value : undefined
}

function stateValue(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    value = value.current ?? value.state
  }
  if (Array.isArray(value)) return String(value[0] ?? "UNKNOWN")
  return String(value ?? "UNKNOWN")
}

function reasonValue(job) {
  const state = job.state
  const reason =
    (state && typeof state === "object" && !Array.isArray(state) ? state.reason : undefined) ??
    job.state_reason ??
    job.reason
  if (!reason || reason === "None") return undefined
  return String(reason)
}

function jobID(job) {
  const raw = job.job_id ?? job.job_id_str ?? job.id
  let id = raw === undefined || raw === null ? "" : String(raw)
  const array = job.array && typeof job.array === "object" ? job.array : {}
  const task = numberValue(array.task_id ?? job.array_task_id)
  if (task !== undefined && !id.includes("_")) id = `${id}_${task}`
  return id
}

function elapsedSeconds(job) {
  const time = job.time && typeof job.time === "object" ? job.time : {}
  const elapsed = numberValue(time.elapsed ?? job.time_used)
  if (elapsed !== undefined) return elapsed
  const start = numberValue(time.start ?? job.start_time)
  if (!start) return 0
  return Math.max(0, Math.floor(Date.now() / 1000) - start)
}

export function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const clock = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
  return days ? `${days}-${clock}` : clock
}

export function normalizeSqueue(payload) {
  if (!payload || !Array.isArray(payload.jobs)) return []
  return payload.jobs
    .map((job) => {
      const state = stateValue(job.state ?? job.job_state)
      return {
        id: jobID(job),
        name: String(job.name ?? job.job_name ?? ""),
        state,
        reason: reasonValue(job),
        partition: String(job.partition ?? ""),
        elapsedSeconds: elapsedSeconds(job),
      }
    })
    .filter((job) => job.id && ACTIVE_STATES.has(job.state))
    .sort((left, right) => {
      const stateOrder = (state) => (state === "RUNNING" ? 0 : state === "PENDING" ? 1 : 2)
      return stateOrder(left.state) - stateOrder(right.state) || Number(right.id.split("_")[0]) - Number(left.id.split("_")[0])
    })
}

export function normalizeSacct(payload) {
  if (!payload || !Array.isArray(payload.jobs)) return []
  return payload.jobs
    .map((job) => {
      const state = stateValue(job.state ?? job.job_state)
      const time = job.time && typeof job.time === "object" ? job.time : {}
      return {
        id: jobID(job),
        name: String(job.name ?? job.job_name ?? ""),
        state,
        endedAt: numberValue(time.end ?? job.end_time) ?? 0,
      }
    })
    .filter((job) => job.id && TERMINAL_STATES.has(job.state))
    .sort((left, right) => right.endedAt - left.endedAt || Number(right.id) - Number(left.id))
}

export function summarizeJobs(jobs) {
  return jobs.reduce(
    (summary, job) => {
      if (job.state === "RUNNING") summary.running += 1
      else if (job.state === "PENDING") summary.pending += 1
      else summary.other += 1
      return summary
    },
    { running: 0, pending: 0, other: 0 },
  )
}

async function querySlurm(command, commandName, normalize, { timeoutMs = 5000, signal } = {}) {
  const process = Bun.spawn({ cmd: command, stdout: "pipe", stderr: "pipe" })
  let timedOut = false
  const stop = () => process.kill()
  signal?.addEventListener("abort", stop, { once: true })
  const timer = setTimeout(() => {
    timedOut = true
    process.kill()
  }, timeoutMs)

  try {
    const [exitCode, stdout, stderr] = await Promise.all([
      process.exited,
      new Response(process.stdout).text(),
      new Response(process.stderr).text(),
    ])
    if (timedOut) throw new Error(`${commandName} timed out after ${timeoutMs / 1000} seconds`)
    if (signal?.aborted) throw new Error(`${commandName} query cancelled`)
    if (exitCode !== 0) throw new Error(stderr.trim() || `${commandName} exited with code ${exitCode}`)
    const payload = JSON.parse(stdout)
    if (Array.isArray(payload.errors) && payload.errors.length) {
      throw new Error(payload.errors.map((item) => item.description ?? String(item)).join("; "))
    }
    return normalize(payload)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener("abort", stop)
  }
}

export function querySqueue(options = {}) {
  return querySlurm(["squeue", "--me", "--json"], "squeue", normalizeSqueue, options)
}

export function querySacct({ since, ...options } = {}) {
  if (!(since instanceof Date) || Number.isNaN(since.valueOf())) throw new Error("querySacct requires a valid start time")
  const local = new Date(since.getTime() - since.getTimezoneOffset() * 60_000).toISOString().slice(0, 19)
  return querySlurm(["sacct", "--allocations", "--json", "--starttime", local], "sacct", normalizeSacct, options)
}
