import assert from "node:assert/strict"
import test from "node:test"

import { formatDuration, normalizeSacct, normalizeSqueue, summarizeJobs } from "./slurm.js"

const payload = {
  jobs: [
    {
      job_id: 1234,
      name: "training",
      partition: "gpu",
      job_state: ["RUNNING"],
      time: { elapsed: 65 },
    },
    {
      job_id: 1235,
      array: { task_id: { set: true, infinite: false, number: 2 } },
      name: "preprocess",
      partition: "cpu",
      state: { current: ["PENDING"], reason: "Priority" },
      time: { elapsed: 0 },
    },
    {
      job_id: 1200,
      name: "finished",
      job_state: ["COMPLETED"],
    },
  ],
}

test("normalizes and sorts active squeue jobs", () => {
  const jobs = normalizeSqueue(payload)
  assert.deepEqual(jobs.map((job) => job.id), ["1234", "1235_2"])
  assert.equal(jobs[0].elapsedSeconds, 65)
  assert.equal(jobs[1].reason, "Priority")
})

test("summarizes states and formats elapsed time", () => {
  const jobs = normalizeSqueue(payload)
  assert.deepEqual(summarizeJobs(jobs), { running: 1, pending: 1, other: 0 })
  assert.equal(formatDuration(90061), "1-01:01:01")
})

test("normalizes completed allocations and excludes active jobs", () => {
  const jobs = normalizeSacct({
    jobs: [
      { job_id: 2001, name: "done", state: { current: ["COMPLETED"] }, time: { end: 200 } },
      { job_id: 2002, name: "failed", state: { current: ["FAILED"] }, time: { end: 300 } },
      { job_id: 2003, name: "active", state: { current: ["RUNNING"] }, time: { end: 0 } },
    ],
  })
  assert.deepEqual(jobs.map((job) => job.id), ["2002", "2001"])
})
