import type { TuiPluginApi, TuiPluginModule } from "@opencode-ai/plugin/tui"

const MAX_FEEDBACK_CHARS = 4_000
const MAX_MESSAGES = 50
const MAX_MESSAGE_CHARS = 2_400
const REQUEST_TIMEOUT_MS = 10_000

const categories = [
  { title: "Helpful", value: "helpful", description: "The response worked well" },
  { title: "Incorrect answer", value: "incorrect", description: "The response contains an error" },
  { title: "Revealed too much", value: "answer-leak", description: "Learning mode provided too much solution code" },
  { title: "Too restrictive", value: "too-restrictive", description: "The agent would not provide reasonable help" },
  { title: "Tool failure", value: "tool-failure", description: "A command or tool did not work" },
  { title: "Other", value: "other", description: "Another issue or suggestion" },
] as const

type FeedbackCategory = (typeof categories)[number]["value"]

function clip(value: string) {
  if (value.length <= MAX_MESSAGE_CHARS) return { value, truncated: false }
  const marker = "\n...[truncated]...\n"
  const side = Math.floor((MAX_MESSAGE_CHARS - marker.length) / 2)
  return { value: `${value.slice(0, side)}${marker}${value.slice(-side)}`, truncated: true }
}

function transcript(api: TuiPluginApi, sessionID: string) {
  const all = api.state.session.messages(sessionID).flatMap((message) => {
    const content = api.state
      .part(message.id)
      .flatMap((part) =>
        part.type === "text" && !part.synthetic && !part.ignored ? [part.text] : [],
      )
      .join("\n")
      .trim()

    if (!content) return []
    return [{ id: message.id, role: message.role, created: message.time.created, content }]
  })

  const selected = all.length > MAX_MESSAGES ? [all[0], ...all.slice(-(MAX_MESSAGES - 1))] : all
  let truncated = selected.length !== all.length
  const messages = selected.map((message) => {
    const content = clip(message.content)
    truncated ||= content.truncated
    return { ...message, content: content.value }
  })

  return { messages, truncated }
}

function currentSessionID(api: TuiPluginApi) {
  const route = api.route.current
  if (route.name !== "session" || !("params" in route)) return
  return typeof route.params?.sessionID === "string" ? route.params.sessionID : undefined
}

function payload(api: TuiPluginApi, sessionID: string, category: FeedbackCategory, comment: string) {
  const messages = api.state.session.messages(sessionID)
  const assistant = [...messages].reverse().find((message) => message.role === "assistant")
  const conversation = transcript(api, sessionID)

  return {
    version: 1,
    category,
    comment,
    submitted_at: new Date().toISOString(),
    client: { opencode_version: api.app.version },
    session: {
      id: sessionID,
      title: api.state.session.get(sessionID)?.title,
      agent: assistant?.agent,
      mode: assistant?.role === "assistant" ? assistant.mode : undefined,
      model:
        assistant?.role === "assistant"
          ? `${assistant.providerID}/${assistant.modelID}`
          : undefined,
    },
    conversation: conversation.messages,
    conversation_truncated: conversation.truncated,
  }
}

async function submitFeedback(body: ReturnType<typeof payload>) {
  const endpoint = process.env.HPCGPT_FEEDBACK_URL?.trim()
  if (!endpoint) throw new Error("Feedback destination is not configured")

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    if (!response.ok) throw new Error(`Feedback service returned HTTP ${response.status}`)
  } finally {
    clearTimeout(timeout)
  }
}

function confirm(api: TuiPluginApi, sessionID: string, category: FeedbackCategory, comment: string) {
  const body = payload(api, sessionID, category, comment)
  const count = body.conversation.length
  const suffix = body.conversation_truncated ? " (truncated)" : ""

  api.ui.dialog.replace(() => (
    <api.ui.DialogConfirm
      title="Submit feedback"
      message={`Attach ${count} visible user/assistant messages${suffix}? System prompts, reasoning, tool output, and files are excluded.`}
      onCancel={() => api.ui.dialog.clear()}
      onConfirm={() => {
        api.ui.dialog.clear()
        void submitFeedback(body)
          .then(() => api.ui.toast({ variant: "success", title: "Feedback", message: "Feedback submitted." }))
          .catch((cause) =>
            api.ui.toast({
              variant: "error",
              title: "Feedback",
              message: cause instanceof Error ? cause.message : String(cause),
            }),
          )
      }}
    />
  ))
}

function askForComment(api: TuiPluginApi, sessionID: string, category: FeedbackCategory) {
  api.ui.dialog.replace(() => (
    <api.ui.DialogPrompt
      title="Feedback"
      placeholder="What should hpcGPT improve?"
      onCancel={() => api.ui.dialog.clear()}
      onConfirm={(value) => {
        const comment = value.trim()
        if (!comment) {
          api.ui.toast({ variant: "error", title: "Feedback", message: "Please enter a short comment." })
          return
        }
        if (comment.length > MAX_FEEDBACK_CHARS) {
          api.ui.toast({
            variant: "error",
            title: "Feedback",
            message: `Feedback must be ${MAX_FEEDBACK_CHARS} characters or fewer.`,
          })
          return
        }
        confirm(api, sessionID, category, comment)
      }}
    />
  ))
}

function openFeedback(api: TuiPluginApi, sessionID?: string) {
  if (!sessionID) {
    api.ui.toast({ variant: "error", title: "Feedback", message: "Open a conversation before sending feedback." })
    return
  }

  api.ui.dialog.replace(() => (
    <api.ui.DialogSelect
      title="Feedback category"
      skipFilter={true}
      options={[...categories]}
      onSelect={(option) => askForComment(api, sessionID, option.value as FeedbackCategory)}
    />
  ))
}

const plugin: TuiPluginModule = {
  id: "ncsa-feedback",
  async tui(api) {
    const unregister = api.keymap.registerLayer({
      commands: [
        {
          title: "Send hpcGPT feedback",
          name: "ncsa.feedback.submit",
          desc: "Send feedback with the current conversation attached",
          category: "Feedback",
          namespace: "palette",
          slashName: "feedback",
          run: () => openFeedback(api, currentSessionID(api)),
        },
      ],
    })
    api.lifecycle.onDispose(unregister)

    api.slots.register({
      slots: {
        sidebar_content(context) {
          return (
            <box flexDirection="column" paddingTop={1}>
              <text fg={context.theme.current.text}>
                <b>If you have issue</b>
              </text>
              <text fg={context.theme.current.info} onMouseUp={() => openFeedback(api, context.session_id)}>
                /feedback
              </text>
            </box>
          )
        },
      },
    })
  },
}

export default plugin
