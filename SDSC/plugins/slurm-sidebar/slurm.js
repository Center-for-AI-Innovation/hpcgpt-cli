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

function state(value) {
  return String(value || "UNKNOWN").trim().split(/[ +]/, 1)[0].toUpperCase()
}

function rows(output) {
  return output
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.split("|"))
}

export function parseSqueue(output) {
  return rows(output)
    .map(([id, rawState, ...name]) => ({
      id: id.trim(),
      state: state(rawState),
      name: name.join("|").trim(),
    }))
    .filter((job) => job.id)
    .sort((left, right) => {
      const rank = (job) => (job.state === "RUNNING" ? 0 : job.state === "PENDING" ? 1 : 2)
      return rank(left) - rank(right) || right.id.localeCompare(left.id, undefined, { numeric: true })
    })
}

export function parseSacct(output) {
  return rows(output)
    .map(([id, rawState, name, endedAt]) => ({
      id: id.trim(),
      state: state(rawState),
      name: String(name || "").trim(),
      endedAt: String(endedAt || "").trim(),
    }))
    .filter((job) => job.id && TERMINAL_STATES.has(job.state))
    .sort((left, right) => right.endedAt.localeCompare(left.endedAt))
}

function slurmTime(date) {
  const part = (value) => String(value).padStart(2, "0")
  return [
    date.getFullYear(),
    part(date.getMonth() + 1),
    part(date.getDate()),
  ].join("-") + `T${part(date.getHours())}:${part(date.getMinutes())}:${part(date.getSeconds())}`
}

async function run(command, name, { signal, timeoutMs = 5_000 } = {}) {
  const process = Bun.spawn({ cmd: command, stdout: "pipe", stderr: "pipe" })
  let timedOut = false
  const stop = () => process.kill()
  signal?.addEventListener("abort", stop, { once: true })
  const timer = setTimeout(() => {
    timedOut = true
    process.kill()
  }, timeoutMs)

  try {
    const [code, stdout, stderr] = await Promise.all([
      process.exited,
      new Response(process.stdout).text(),
      new Response(process.stderr).text(),
    ])
    if (timedOut) throw new Error(`${name} timed out after ${timeoutMs / 1000}s`)
    if (signal?.aborted) throw new Error(`${name} cancelled`)
    if (code !== 0) throw new Error(stderr.trim() || `${name} exited with code ${code}`)
    return stdout
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener("abort", stop)
  }
}

export async function querySqueue(options = {}) {
  const output = await run(
    ["squeue", "--me", "--noheader", "--format=%i|%T|%j"],
    "squeue",
    options,
  )
  return parseSqueue(output)
}

export async function querySacct(since, options = {}) {
  const output = await run(
    [
      "sacct",
      "--allocations",
      "--noheader",
      "--parsable2",
      "--starttime",
      slurmTime(since),
      "--format=JobIDRaw,State,JobName,End",
    ],
    "sacct",
    options,
  )
  return parseSacct(output)
}
