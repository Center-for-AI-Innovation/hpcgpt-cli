import { For, Show, createSignal, onCleanup, onMount } from "solid-js"
import type { TuiPluginModule } from "@opencode-ai/plugin/tui"

import { querySacct, querySqueue, summarizeJobs } from "./slurm.js"

const REFRESH_INTERVAL_MS = 15_000
const COMPLETED_REFRESH_INTERVAL_MS = 60_000
const MAX_VISIBLE_JOBS = 6

function compactState(state: string) {
  const names: Record<string, string> = {
    CONFIGURING: "CF",
    COMPLETING: "CG",
    PENDING: "PD",
    RUNNING: "R",
    SUSPENDED: "S",
  }
  return names[state] ?? state.slice(0, 2)
}

function truncate(value: string, width: number) {
  if (value.length <= width) return value
  return `${value.slice(0, Math.max(0, width - 1))}~`
}

const plugin: TuiPluginModule = {
  id: "ncsa-slurm-sidebar",
  async tui(api) {
    let activePanel: { toggle: () => void; refresh: () => void } | undefined
    let enableOnMount = false
    const sessionStarts = new Map<string, Date>()

    const unregisterCommand = api.keymap.registerLayer({
      commands: [
        {
          title: "Toggle Slurm job tracker",
          name: "ncsa.slurm.jobs.toggle",
          desc: "Enable or disable live Slurm jobs in the sidebar",
          category: "HPC",
          namespace: "palette",
          slashName: "jobs",
          run: () => {
            if (activePanel) {
              activePanel.toggle()
              return
            }
            enableOnMount = true
            api.keymap.dispatchCommand("session.sidebar.toggle")
          },
        },
        {
          title: "Refresh Slurm jobs",
          name: "ncsa.slurm.jobs.refresh",
          desc: "Refresh the enabled Slurm sidebar tracker now",
          category: "HPC",
          namespace: "palette",
          slashName: "jobs-refresh",
          run: () => {
            if (activePanel) activePanel.refresh()
            else api.ui.toast({ title: "Slurm jobs", message: "Enable the tracker with /jobs first." })
          },
        },
      ],
    })

    api.lifecycle.onDispose(unregisterCommand)

    api.slots.register({
      slots: {
        sidebar_content(context) {
          const sessionStartedAt = sessionStarts.get(context.session_id) ?? new Date()
          sessionStarts.set(context.session_id, sessionStartedAt)
          const [enabled, setEnabled] = createSignal(enableOnMount)
          const [jobs, setJobs] = createSignal<any[]>([])
          const [completedJobs, setCompletedJobs] = createSignal<any[]>([])
          const [activeExpanded, setActiveExpanded] = createSignal(true)
          const [completedExpanded, setCompletedExpanded] = createSignal(false)
          const [loading, setLoading] = createSignal(false)
          const [error, setError] = createSignal<string>()
          const [completedError, setCompletedError] = createSignal<string>()
          const [updatedAt, setUpdatedAt] = createSignal<Date>()
          let timer: ReturnType<typeof setTimeout> | undefined
          let controller: AbortController | undefined
          let requestID = 0
          let inFlight = false
          let lastCompletedRefresh = 0

          const cancelTimer = () => {
            if (timer) clearTimeout(timer)
            timer = undefined
          }

          const stop = () => {
            requestID += 1
            cancelTimer()
            controller?.abort()
            controller = undefined
            inFlight = false
          }

          const schedule = () => {
            cancelTimer()
            if (!enabled()) return
            timer = setTimeout(() => void refresh(false), REFRESH_INTERVAL_MS)
          }

          const refresh = async (includeCompleted = true) => {
            if (!enabled() || inFlight) return
            inFlight = true
            setLoading(true)
            const currentRequest = ++requestID
            const requestController = new AbortController()
            controller = requestController
            try {
              const next = await querySqueue({ signal: requestController.signal })
              if (currentRequest !== requestID || requestController.signal.aborted) return
              setJobs(next)
              setError(undefined)
              if (includeCompleted || Date.now() - lastCompletedRefresh >= COMPLETED_REFRESH_INTERVAL_MS) {
                try {
                  const completed = await querySacct({ since: sessionStartedAt, signal: requestController.signal })
                  if (currentRequest !== requestID || requestController.signal.aborted) return
                  setCompletedJobs(completed)
                  setCompletedError(undefined)
                  lastCompletedRefresh = Date.now()
                } catch (cause) {
                  if (currentRequest === requestID && !requestController.signal.aborted) {
                    setCompletedError(cause instanceof Error ? cause.message : String(cause))
                  }
                }
              }
              setUpdatedAt(new Date())
            } catch (cause) {
              if (currentRequest === requestID && !requestController.signal.aborted) {
                setError(cause instanceof Error ? cause.message : String(cause))
              }
            } finally {
              if (currentRequest === requestID) {
                inFlight = false
                setLoading(false)
                controller = undefined
                schedule()
              }
            }
          }

          const toggle = () => {
            const next = !enabled()
            setEnabled(next)
            enableOnMount = next
            if (next) {
              lastCompletedRefresh = 0
              void refresh(true)
            } else {
              stop()
              setJobs([])
              setCompletedJobs([])
              setError(undefined)
              setCompletedError(undefined)
              setUpdatedAt(undefined)
            }
          }

          activePanel = { toggle, refresh: () => void refresh(true) }

          onMount(() => {
            if (enabled()) void refresh(true)
          })
          onCleanup(() => {
            stop()
            if (activePanel?.toggle === toggle) activePanel = undefined
          })

          const summary = () => summarizeJobs(jobs())
          const stateColor = (state: string) => {
            if (state === "RUNNING") return context.theme.current.success
            if (state === "PENDING") return context.theme.current.warning
            return context.theme.current.info
          }

          return (
            <box flexDirection="column" gap={1} paddingTop={1}>
              <text fg={context.theme.current.text}>
                <b>SLURM JOBS</b>{" "}
                <span style={{ fg: enabled() ? context.theme.current.success : context.theme.current.textMuted }}>
                  {enabled() ? "on" : "off"}
                </span>
              </text>

              <Show when={!enabled()}>
                <text fg={context.theme.current.textMuted}>/jobs to enable</text>
              </Show>

              <Show when={enabled()}>
                <box flexDirection="column">
                  <Show when={loading() && !updatedAt()}>
                    <text fg={context.theme.current.textMuted}>Loading jobs...</text>
                  </Show>
                  <Show when={error()}>
                    {(message) => <text fg={context.theme.current.error}>{truncate(message(), 34)}</text>}
                  </Show>
                  <text fg={context.theme.current.text} onMouseUp={() => setActiveExpanded((value) => !value)}>
                    {activeExpanded() ? "[-]" : "[+]"} Active ({jobs().length})
                  </text>
                  <Show when={activeExpanded()}>
                    <Show when={!loading() && !error() && jobs().length === 0}>
                      <text fg={context.theme.current.textMuted}>  No active jobs</text>
                    </Show>
                    <For each={jobs().slice(0, MAX_VISIBLE_JOBS)}>
                      {(job) => (
                        <text fg={context.theme.current.textMuted}>
                          <span style={{ fg: stateColor(job.state) }}>{compactState(job.state).padEnd(2)}</span>{" "}
                          <span style={{ fg: context.theme.current.text }}>{truncate(job.id, 10).padEnd(10)}</span>{" "}
                          {truncate(job.name, 14)}
                        </text>
                      )}
                    </For>
                    <Show when={jobs().length > MAX_VISIBLE_JOBS}>
                      <text fg={context.theme.current.textMuted}>+{jobs().length - MAX_VISIBLE_JOBS} more</text>
                    </Show>
                  </Show>
                  <Show when={jobs().length > 0}>
                    <text fg={context.theme.current.textMuted}>
                      {summary().running} running | {summary().pending} pending
                    </text>
                  </Show>
                  <text fg={context.theme.current.text} onMouseUp={() => setCompletedExpanded((value) => !value)}>
                    {completedExpanded() ? "[-]" : "[+]"} Completed ({completedJobs().length})
                  </text>
                  <Show when={completedExpanded()}>
                    <Show when={completedError()}>
                      {(message) => <text fg={context.theme.current.error}>  {truncate(message(), 32)}</text>}
                    </Show>
                    <Show when={!completedError() && completedJobs().length === 0}>
                      <text fg={context.theme.current.textMuted}>  None this session</text>
                    </Show>
                    <For each={completedJobs().slice(0, MAX_VISIBLE_JOBS)}>
                      {(job) => (
                        <text fg={context.theme.current.textMuted}>
                          <span style={{ fg: job.state === "COMPLETED" ? context.theme.current.success : context.theme.current.error }}>
                            {compactState(job.state).padEnd(2)}
                          </span>{" "}
                          <span style={{ fg: context.theme.current.text }}>{truncate(job.id, 10).padEnd(10)}</span>{" "}
                          {truncate(job.name, 14)}
                        </text>
                      )}
                    </For>
                    <Show when={completedJobs().length > MAX_VISIBLE_JOBS}>
                      <text fg={context.theme.current.textMuted}>+{completedJobs().length - MAX_VISIBLE_JOBS} more</text>
                    </Show>
                  </Show>
                  <Show when={updatedAt()}>
                    {(updated) => (
                      <text fg={context.theme.current.textMuted}>
                        {loading() ? "Refreshing" : `Updated ${updated().toLocaleTimeString()}`} | 15s
                      </text>
                    )}
                  </Show>
                </box>
              </Show>
            </box>
          )
        },
      },
    })
  },
}

export default plugin
