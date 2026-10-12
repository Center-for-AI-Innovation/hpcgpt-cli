import { mkdtemp, rmdir, unlink, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"

const MAX_SESSION_EXPORT_BYTES = 5 * 1024 * 1024
const MAIL_TIMEOUT_MS = 10_000

export async function sendFeedback(feedback) {
  const recipient = process.env.HPCGPT_FEEDBACK_EMAIL?.trim()
  const sender = process.env.HPCGPT_FEEDBACK_FROM?.trim()
  if (!recipient || !/^[^@\s]+@[^@\s]+$/.test(recipient)) {
    throw new Error("Feedback email is not configured")
  }
  if (!sender || !/^[^@\s]+@[^@\s]+$/.test(sender)) {
    throw new Error("Feedback sender is not configured")
  }

  const session = JSON.stringify(feedback.session_export)
  if (new TextEncoder().encode(session).byteLength > MAX_SESSION_EXPORT_BYTES) {
    throw new Error("This session is too large to attach (5 MiB maximum)")
  }

  const directory = await mkdtemp(join(tmpdir(), "hpcgpt-feedback-"))
  const attachment = join(directory, "hpcgpt-session.json")
  try {
    await writeFile(attachment, session, "utf8")
    const child = Bun.spawn({
      cmd: [
        "mail",
        "-r",
        sender,
        "-s",
        `hpcGPT Feedback [${feedback.uid}] [${feedback.category}]`,
        "-a",
        attachment,
        recipient,
      ],
      stdin: "pipe",
      stdout: "ignore",
      stderr: "pipe",
    })
    child.stdin.write(`${feedback.comment}\n`)
    child.stdin.end()

    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      child.kill()
    }, MAIL_TIMEOUT_MS)
    try {
      const [code, stderr] = await Promise.all([
        child.exited,
        new Response(child.stderr).text(),
      ])
      if (timedOut) throw new Error("Feedback delivery timed out")
      if (code !== 0) throw new Error(stderr.trim() || `mail exited with code ${code}`)
    } finally {
      clearTimeout(timer)
    }
  } finally {
    await unlink(attachment).catch(() => {})
    await rmdir(directory).catch(() => {})
  }
}
