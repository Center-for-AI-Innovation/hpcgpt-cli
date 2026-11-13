import { For, Show, createSignal, onCleanup, onMount } from "solid-js"
import type { TuiPluginModule } from "@opencode-ai/plugin/tui"

import { querySacct, querySqueue } from "./slurm.js"

const MAX_VISIBLE_JOBS = 6

function compactState(state: string) {
  const names: Record<string, string> = {
    COMPLETING: "CG",
    PENDING: "PD",
    RUNNING: "R",
    SUSPENDED: "S",
  }
  return names[state] ?? state.slice(0, 2)
}

function truncate(value: string, width: number) {
  return value.length <= width ? value : `${value.slice(0, width - 1)}~`
}

const plugin: TuiPluginModule = {
  id: "ncsa-slurm-sidebar",
  async tui(api) {
    let panel: { toggle: () => void; refresh: () => void } | undefined
    let enableOnMount = false
    const sessionStarts = new Map<string, Date>()

    const unregister = api.keymap.registerLayer({
      commands: [
        {
          title: "Toggle Slurm jobs",
          name: "ncsa.slurm.jobs.toggle",
          desc: "Enable or disable Slurm jobs in the sidebar",
          category: "HPC",
          namespace: "palette",
          slashName: "jobs",
          run: () => {
            if (panel) panel.toggle()
            else {
              enableOnMount = !enableOnMount
              if (enableOnMount) api.keymap.dispatchCommand("session.sidebar.toggle")
            }
          },
        },
        {
          title: "Refresh Slurm jobs",
          name: "ncsa.slurm.jobs.refresh",
          desc: "Refresh Slurm jobs now",
          category: "HPC",
          namespace: "palette",
          slashName: "jobs-refresh",
          run: () => {
            if (panel) panel.refresh()
            else api.ui.toast({ title: "Slurm jobs", message: "Enable the sidebar with /jobs first." })
          },
        },
      ],
    })
    api.lifecycle.onDispose(unregister)

    api.slots.register({
      slots: {
        sidebar_content(context) {
          const sessionStartedAt = sessionStarts.get(context.session_id) ?? new Date()
          sessionStarts.set(context.session_id, sessionStartedAt)
          const [enabled, setEnabled] = createSignal(enableOnMount)
          const [active, setActive] = createSignal<any[]>([])
          const [completed, setCompleted] = createSignal<any[]>([])
          const [activeExpanded, setActiveExpanded] = createSignal(true)
          const [completedExpanded, setCompletedExpanded] = createSignal(false)
          const [loading, setLoading] = createSignal(false)
          const [error, setError] = createSignal<string>()
          const [updatedAt, setUpdatedAt] = createSignal<Date>()
          let controller: AbortController | undefined
          let refreshing = false
          let generation = 0

          const stop = () => {
            generation += 1
            controller?.abort()
            controller = undefined
            refreshing = false
            setLoading(false)
          }

          const refresh = async () => {
            if (!enabled() || refreshing) return
            refreshing = true
            setLoading(true)
            const request = ++generation
            controller = new AbortController()

            try {
              const jobs = await querySqueue({ signal: controller.signal })
              if (request !== generation || !enabled()) return
              setActive(jobs)

              const history = await querySacct(sessionStartedAt, { signal: controller.signal })
              if (request !== generation || !enabled()) return
              setCompleted(history)

              setError(undefined)
              setUpdatedAt(new Date())
            } catch (cause) {
              if (request === generation && enabled()) {
                setError(cause instanceof Error ? cause.message : String(cause))
              }
            } finally {
              if (request === generation) {
                refreshing = false
                setLoading(false)
                controller = undefined
              }
            }
          }

          const toggle = () => {
            const next = !enabled()
            setEnabled(next)
            enableOnMount = next
            if (next) void refresh()
            else {
              stop()
              setActive([])
              setCompleted([])
              setError(undefined)
              setUpdatedAt(undefined)
            }
          }

          panel = {
            toggle,
            refresh: () => {
              if (enabled()) void refresh()
              else api.ui.toast({ title: "Slurm jobs", message: "Enable the sidebar with /jobs first." })
            },
          }
          onMount(() => {
            if (enabled()) void refresh()
          })
          onCleanup(() => {
            stop()
            if (panel?.toggle === toggle) panel = undefined
          })

          const stateColor = (state: string) => {
            if (state === "RUNNING" || state === "COMPLETED") return context.theme.current.success
            if (state === "PENDING") return context.theme.current.warning
            if (["CANCELLED", "FAILED", "OUT_OF_MEMORY", "TIMEOUT"].includes(state)) {
              return context.theme.current.error
            }
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
                  <text fg={context.theme.current.info} onMouseUp={() => void refresh()}>
                    {loading() ? "Refreshing..." : "[Refresh]"}
                  </text>
                  <Show when={loading() && !updatedAt()}>
                    <text fg={context.theme.current.textMuted}>Loading jobs...</text>
                  </Show>
                  <Show when={error()}>
                    {(message) => <text fg={context.theme.current.error}>{truncate(message(), 34)}</text>}
                  </Show>

                  <text fg={context.theme.current.text} onMouseUp={() => setActiveExpanded((value) => !value)}>
                    {activeExpanded() ? "[-]" : "[+]"} Active ({active().length})
                  </text>
                  <Show when={activeExpanded()}>
                    <Show when={!loading() && !error() && active().length === 0}>
                      <text fg={context.theme.current.textMuted}>  No active jobs</text>
                    </Show>
                    <For each={active().slice(0, MAX_VISIBLE_JOBS)}>
                      {(job) => (
                        <text fg={context.theme.current.textMuted}>
                          <span style={{ fg: stateColor(job.state) }}>{compactState(job.state).padEnd(2)}</span>{" "}
                          <span style={{ fg: context.theme.current.text }}>{truncate(job.id, 10).padEnd(10)}</span>{" "}
                          {truncate(job.name, 14)}
                        </text>
                      )}
                    </For>
                  </Show>

                  <text fg={context.theme.current.text} onMouseUp={() => setCompletedExpanded((value) => !value)}>
                    {completedExpanded() ? "[-]" : "[+]"} Completed ({completed().length})
                  </text>
                  <Show when={completedExpanded()}>
                    <Show when={!error() && completed().length === 0}>
                      <text fg={context.theme.current.textMuted}>  None this session</text>
                    </Show>
                    <For each={completed().slice(0, MAX_VISIBLE_JOBS)}>
                      {(job) => (
                        <text fg={context.theme.current.textMuted}>
                          <span style={{ fg: stateColor(job.state) }}>{compactState(job.state).padEnd(2)}</span>{" "}
                          <span style={{ fg: context.theme.current.text }}>{truncate(job.id, 10).padEnd(10)}</span>{" "}
                          {truncate(job.name, 14)}
                        </text>
                      )}
                    </For>
                  </Show>

                  <Show when={updatedAt()}>
                    {(updated) => (
                      <text fg={context.theme.current.textMuted}>Updated {updated().toLocaleTimeString()}</text>
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
