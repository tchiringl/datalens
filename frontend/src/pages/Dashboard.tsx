import { useQuery } from '@tanstack/react-query'
import {
  Database,
  Layers,
  ShieldCheck,
  Activity,
  ArrowRight,
  Plus,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { KPICard } from '../components/ui/KPICard'
import { KPICardSkeleton, CardSkeleton } from '../components/ui/LoadingSkeleton'
import { StatusBadge } from '../components/ui/StatusBadge'
import {
  mockDataApi,
  pipelinesApi,
  MOCK_STATS,
  MOCK_ACTIVITY,
  MOCK_PIPELINES,
  type ActivityEvent,
  type Pipeline,
} from '../lib/api'
import { clsx } from 'clsx'
import { Link } from 'react-router-dom'

function activityIcon(event: ActivityEvent) {
  switch (event.status) {
    case 'success':
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-500" />
    case 'running':
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
    default:
      return <Clock className="h-4 w-4 text-slate-400" />
  }
}

function activityBg(event: ActivityEvent) {
  switch (event.status) {
    case 'success':
      return 'bg-emerald-50 border-emerald-100'
    case 'failed':
      return 'bg-red-50 border-red-100'
    case 'running':
      return 'bg-blue-50 border-blue-100'
    default:
      return 'bg-slate-50 border-slate-100'
  }
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function PipelineStatusCard({ pipeline }: { pipeline: Pipeline }) {
  const run = pipeline.last_run

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 truncate">{pipeline.dag_id}</p>
          <p className="text-xs text-slate-500 truncate mt-0.5">{pipeline.description}</p>
        </div>
        {run ? (
          <StatusBadge
            status={
              run.state === 'success'
                ? 'success'
                : run.state === 'failed'
                ? 'failed'
                : run.state === 'running'
                ? 'running'
                : 'queued'
            }
            size="sm"
          />
        ) : (
          <StatusBadge status="unknown" size="sm" />
        )}
      </div>

      <div className="flex items-center gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {run?.start_date
            ? formatDistanceToNow(new Date(run.start_date), { addSuffix: true })
            : 'Never run'}
        </span>
        {run?.duration !== undefined && run.duration !== null && (
          <span>{formatDuration(run.duration)}</span>
        )}
        <span className="font-mono bg-slate-100 rounded px-1.5 py-0.5 text-[10px]">
          {pipeline.schedule}
        </span>
      </div>

      {pipeline.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
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
    </div>
  )
}

export default function Dashboard() {
  const statsQuery = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () =>
      mockDataApi.getStats().catch(() => MOCK_STATS),
    staleTime: 30000,
  })

  const activityQuery = useQuery({
    queryKey: ['dashboard-activity'],
    queryFn: () =>
      mockDataApi.getActivity().catch(() => MOCK_ACTIVITY),
    staleTime: 30000,
  })

  const pipelinesQuery = useQuery({
    queryKey: ['pipelines'],
    queryFn: () =>
      pipelinesApi.list().catch(() => MOCK_PIPELINES),
    refetchInterval: 10000,
  })

  const stats = statsQuery.data ?? MOCK_STATS
  const activity = activityQuery.data ?? MOCK_ACTIVITY
  const pipelines = pipelinesQuery.data ?? MOCK_PIPELINES

  return (
    <div className="space-y-6">
      {/* ── KPI Cards ── */}
      <section>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {statsQuery.isLoading ? (
            Array.from({ length: 4 }).map((_, i) => <KPICardSkeleton key={i} />)
          ) : (
            <>
              <KPICard
                title="Total Sources"
                value={stats.total_sources}
                subtitle="Connected data sources"
                icon={Database}
                iconBg="bg-blue-50"
                iconColor="text-blue-600"
                trend={{ value: 1, label: 'vs last week', positive: true }}
              />
              <KPICard
                title="CDM Models Built"
                value={stats.cdm_models}
                subtitle="Active dbt models"
                icon={Layers}
                iconBg="bg-purple-50"
                iconColor="text-purple-600"
              />
              <KPICard
                title="DQ Tests Passing"
                value={`${stats.dq_passing}/${stats.dq_total}`}
                subtitle={`${Math.round((stats.dq_passing / stats.dq_total) * 100)}% pass rate`}
                icon={ShieldCheck}
                iconBg="bg-emerald-50"
                iconColor="text-emerald-600"
                trend={{
                  value: 2,
                  label: 'improvement this week',
                  positive: true,
                }}
              />
              <KPICard
                title="Pipeline Runs Today"
                value={stats.pipeline_runs_today}
                subtitle={`${stats.pipeline_success_today} successful`}
                icon={Activity}
                iconBg="bg-orange-50"
                iconColor="text-orange-600"
              />
            </>
          )}
        </div>
      </section>

      {/* ── Pipeline Status + Activity ── */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Pipeline Status (2/3) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Pipeline Status</h2>
            <Link
              to="/pipelines"
              className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700"
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {pipelinesQuery.isLoading ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <CardSkeleton key={i} lines={2} />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {pipelines.slice(0, 6).map(p => (
                <PipelineStatusCard key={p.dag_id} pipeline={p} />
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity (1/3) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Recent Activity</h2>
            <span className="text-xs text-slate-400">Live</span>
          </div>

          <div className="space-y-2">
            {activityQuery.isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className="animate-pulse rounded-lg border bg-slate-50 p-3 space-y-2"
                  >
                    <div className="h-3 bg-slate-200 rounded w-3/4" />
                    <div className="h-3 bg-slate-200 rounded w-1/2" />
                  </div>
                ))
              : activity.map(event => (
                  <div
                    key={event.id}
                    className={clsx(
                      'flex items-start gap-3 rounded-lg border p-3 transition-colors',
                      activityBg(event)
                    )}
                  >
                    <div className="mt-0.5 flex-shrink-0">{activityIcon(event)}</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-800 truncate">
                        {event.title}
                      </p>
                      <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                        {event.description}
                      </p>
                      <p className="text-[10px] text-slate-400 mt-1">
                        {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                      </p>
                    </div>
                  </div>
                ))}
          </div>
        </div>
      </section>

      {/* ── Quick Actions ── */}
      <section>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Quick Actions</h2>
          <div className="flex flex-wrap gap-3">
            <Link
              to="/pipelines"
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors shadow-sm"
            >
              <Play className="h-4 w-4" />
              Trigger Pipeline
            </Link>
            <Link
              to="/sources"
              className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
            >
              <Plus className="h-4 w-4" />
              Add Source
            </Link>
            <Link
              to="/governance"
              className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
            >
              <Layers className="h-4 w-4" />
              View Lineage
            </Link>
            <Link
              to="/data-quality"
              className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
            >
              <ShieldCheck className="h-4 w-4" />
              DQ Report
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
