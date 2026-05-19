import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  ChevronDown,
  ChevronRight,
  Clock,
  Zap,
  RotateCcw,
  Loader2,
  Calendar,
  Activity,
  CheckCircle2,
  XCircle,
  Circle,
} from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { clsx } from 'clsx'
import { StatusBadge } from '../components/ui/StatusBadge'
import { CardSkeleton } from '../components/ui/LoadingSkeleton'
import { pipelinesApi, MOCK_PIPELINES, type Pipeline, type PipelineRun } from '../lib/api'

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function RunHistoryRow({ run }: { run: PipelineRun }) {
  const icon = {
    success: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />,
    failed: <XCircle className="h-3.5 w-3.5 text-red-500" />,
    running: <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" />,
    queued: <Circle className="h-3.5 w-3.5 text-amber-400" />,
  }[run.state]

  return (
    <div className="flex items-center gap-3 py-1.5 border-b border-slate-100 last:border-0 text-xs">
      <div className="flex-shrink-0">{icon}</div>
      <span className="font-mono text-slate-600 truncate flex-1">{run.run_id}</span>
      <span className="text-slate-400 flex-shrink-0 w-28 text-right">
        {run.start_date
          ? format(new Date(run.start_date), 'MMM d, HH:mm')
          : '—'}
      </span>
      <span className="text-slate-400 flex-shrink-0 w-16 text-right">
        {formatDuration(run.duration)}
      </span>
    </div>
  )
}

function PipelineCard({ pipeline }: { pipeline: Pipeline }) {
  const queryClient = useQueryClient()
  const [showRuns, setShowRuns] = useState(false)

  const triggerMutation = useMutation({
    mutationFn: () => pipelinesApi.trigger(pipeline.dag_id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['pipelines'] })
    },
  })

  const { data: runs, isLoading: runsLoading } = useQuery({
    queryKey: ['pipeline-runs', pipeline.dag_id],
    queryFn: () =>
      pipelinesApi.getRuns(pipeline.dag_id).catch(() =>
        pipeline.last_run ? [pipeline.last_run] : []
      ),
    enabled: showRuns,
  })

  const run = pipeline.last_run
  const isRunning = run?.state === 'running'

  const stateMap = {
    success: 'success' as const,
    failed: 'failed' as const,
    running: 'running' as const,
    queued: 'queued' as const,
  }

  return (
    <div
      className={clsx(
        'bg-white rounded-xl border shadow-sm overflow-hidden transition-all',
        !pipeline.is_active ? 'border-slate-200 opacity-70' : 'border-slate-200',
        isRunning && 'border-blue-200 shadow-blue-50'
      )}
    >
      {/* Running indicator strip */}
      {isRunning && (
        <div className="h-0.5 w-full bg-gradient-to-r from-blue-400 via-blue-600 to-blue-400 animate-pulse" />
      )}

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <div
                className={clsx(
                  'h-2 w-2 rounded-full flex-shrink-0',
                  isRunning
                    ? 'bg-blue-500 animate-pulse'
                    : run?.state === 'success'
                    ? 'bg-emerald-500'
                    : run?.state === 'failed'
                    ? 'bg-red-500'
                    : 'bg-slate-300'
                )}
              />
              <p className="text-sm font-semibold text-slate-800 font-mono truncate">
                {pipeline.dag_id}
              </p>
            </div>
            <p className="mt-1 text-xs text-slate-500 leading-relaxed">{pipeline.description}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {!pipeline.is_active && (
              <span className="text-xs text-slate-400 font-medium">Inactive</span>
            )}
            {run && <StatusBadge status={stateMap[run.state] ?? 'unknown'} size="sm" />}
          </div>
        </div>

        {/* Meta */}
        <div className="grid grid-cols-2 gap-2 text-xs text-slate-500 mb-4">
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-slate-400" />
            <span>
              {run?.start_date
                ? formatDistanceToNow(new Date(run.start_date), { addSuffix: true })
                : 'Never run'}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5 text-slate-400" />
            <span>{formatDuration(run?.duration ?? null)}</span>
          </div>
          <div className="flex items-center gap-1.5 col-span-2">
            <Calendar className="h-3.5 w-3.5 text-slate-400" />
            <code className="font-mono text-[11px] bg-slate-100 rounded px-1.5 py-0.5">
              {pipeline.schedule}
            </code>
            {pipeline.next_run && (
              <span className="text-slate-400">
                · next{' '}
                {formatDistanceToNow(new Date(pipeline.next_run), { addSuffix: true })}
              </span>
            )}
          </div>
        </div>

        {/* Tags */}
        {pipeline.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-4">
            {pipeline.tags.map(tag => (
              <span
                key={tag}
                className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending || isRunning || !pipeline.is_active}
            className={clsx(
              'flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition-colors',
              pipeline.is_active
                ? 'bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed'
            )}
          >
            {triggerMutation.isPending || isRunning ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            {isRunning ? 'Running…' : 'Trigger'}
          </button>

          <button
            type="button"
            onClick={() => setShowRuns(prev => !prev)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
          >
            {showRuns ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            Runs
          </button>
        </div>
      </div>

      {/* Run history */}
      {showRuns && (
        <div className="border-t border-slate-100 px-5 py-3 bg-slate-50">
          <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-2">
            Run History
          </p>
          {runsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="animate-pulse h-6 bg-slate-200 rounded" />
              ))}
            </div>
          ) : runs && runs.length > 0 ? (
            <div>
              {runs.slice(0, 8).map(r => (
                <RunHistoryRow key={r.run_id} run={r} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-2">No runs found</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function Pipelines() {
  const queryClient = useQueryClient()

  const { data: pipelines, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => pipelinesApi.list().catch(() => MOCK_PIPELINES),
    refetchInterval: 5000,
  })

  const triggerAllMutation = useMutation({
    mutationFn: async () => {
      const active = pipelines?.filter(p => p.is_active) ?? []
      await Promise.allSettled(active.map(p => pipelinesApi.trigger(p.dag_id)))
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['pipelines'] })
    },
  })

  const displayPipelines = pipelines ?? MOCK_PIPELINES

  const summary = {
    total: displayPipelines.length,
    running: displayPipelines.filter(p => p.last_run?.state === 'running').length,
    success: displayPipelines.filter(p => p.last_run?.state === 'success').length,
    failed: displayPipelines.filter(p => p.last_run?.state === 'failed').length,
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
            {summary.running} running
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            {summary.success} success
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            {summary.failed} failed
          </span>
          {dataUpdatedAt > 0 && (
            <span className="text-slate-400">
              · Updated {formatDistanceToNow(new Date(dataUpdatedAt), { addSuffix: true })}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void queryClient.invalidateQueries({ queryKey: ['pipelines'] })}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => triggerAllMutation.mutate()}
            disabled={triggerAllMutation.isPending}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm"
          >
            {triggerAllMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4" />
            )}
            Trigger All
          </button>
        </div>
      </div>

      {/* Pipeline cards grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <CardSkeleton key={i} lines={4} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {displayPipelines.map(pipeline => (
            <PipelineCard key={pipeline.dag_id} pipeline={pipeline} />
          ))}
        </div>
      )}

      {/* Polling indicator */}
      <div className="flex items-center justify-center gap-2 text-xs text-slate-400 py-2">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Live polling every 5 seconds
      </div>
    </div>
  )
}
