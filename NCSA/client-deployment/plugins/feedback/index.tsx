import type { TuiPluginApi, TuiPluginModule } from "@opencode-ai/plugin/tui"

import { sendFeedback } from "./mail.js"

const MAX_FEEDBACK_CHARS = 4_000

const categories = [
  { title: "Helpful", value: "helpful", description: "The response worked well" },
  { title: "Incorrect answer", value: "incorrect", description: "The response contains an error" },
  { title: "Revealed too much", value: "answer-leak", description: "Learning mode provided too much solution code" },
  { title: "Too restrictive", value: "too-restrictive", description: "The agent would not provide reasonable help" },
  { title: "Tool failure", value: "tool-failure", description: "A command or tool did not work" },
  { title: "Other", value: "other", description: "Another issue or suggestion" },
] as const

type FeedbackCategory = (typeof categories)[number]["value"]

function currentSessionID(api: TuiPluginApi) {
  const route = api.route.current
  if (route.name !== "session" || !("params" in route)) return
  return typeof route.params?.sessionID === "string" ? route.params.sessionID : undefined
}

function payload(api: TuiPluginApi, sessionID: string, category: FeedbackCategory, comment: string) {
  const info = api.state.session.get(sessionID)
  if (!info) throw new Error("The current session is unavailable")
  const uid = (process.env.USER?.trim() || "unknown")
    .replace(/[^A-Za-z0-9._-]/g, "_")
    .slice(0, 64)

  return {
    uid: uid || "unknown",
    category,
    comment,
    session_export: {
      info,
      messages: api.state.session.messages(sessionID).map((message) => ({
        info: message,
        parts: api.state.part(message.id),
      })),
    },
  }
}

function confirm(api: TuiPluginApi, sessionID: string, category: FeedbackCategory, comment: string) {
  const count = api.state.session.messages(sessionID).length

  api.ui.dialog.replace(() => (
    <api.ui.DialogConfirm
      title="Submit feedback"
      message={`Attach the full ${count}-message OpenCode session? It may include reasoning, tool output, and file content.`}
      onCancel={() => api.ui.dialog.clear()}
      onConfirm={() => {
        api.ui.dialog.clear()
        void Promise.resolve()
          .then(() => payload(api, sessionID, category, comment))
          .then(sendFeedback)
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
                <b>Having an issue?</b>
              </text>
              <text fg={context.theme.current.textMuted}>/feedback</text>
            </box>
          )
        },
      },
    })
  },
}

export default plugin
