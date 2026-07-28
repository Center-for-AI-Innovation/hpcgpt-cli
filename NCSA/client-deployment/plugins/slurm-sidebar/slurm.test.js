import assert from "node:assert/strict"
import test from "node:test"

import { parseSacct, parseSqueue } from "./slurm.js"

test("parses and orders active jobs", () => {
  const jobs = parseSqueue([
    "102|PENDING|preprocess",
    "101|RUNNING|training",
    "103|COMPLETING|cleanup",
  ].join("\n"))

  assert.deepEqual(jobs.map((job) => job.id), ["101", "102", "103"])
  assert.equal(jobs[0].name, "training")
})

test("keeps terminal allocations and normalizes state suffixes", () => {
  const jobs = parseSacct([
    "201|COMPLETED|first|2026-07-28T10:00:00",
    "202|RUNNING|active|Unknown",
    "203|CANCELLED by 42|cancelled|2026-07-28T11:00:00",
    "204|FAILED+|failed|2026-07-28T12:00:00",
  ].join("\n"))

  assert.deepEqual(jobs.map((job) => job.id), ["204", "203", "201"])
  assert.deepEqual(jobs.map((job) => job.state), ["FAILED", "CANCELLED", "COMPLETED"])
})
