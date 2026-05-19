import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Database,
  Server,
  Globe,
  HardDrive,
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Table2,
  FileText,
  Play,
  ExternalLink,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import * as Dialog from '@radix-ui/react-dialog'
import * as Select from '@radix-ui/react-select'
import { clsx } from 'clsx'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TableRowSkeleton } from '../components/ui/LoadingSkeleton'
import {
  assessmentApi,
  sourcesApi,
  MOCK_SOURCES,
  type AssessmentReport,
  type SourceCreate,
  type SourceTable,
} from '../lib/api'

const SOURCE_TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  postgres: Database,
  mysql: Database,
  redshift: Database,
  bigquery: Database,
  iceberg: HardDrive,
  api: Globe,
  default: Server,
}

const SOURCE_TYPE_COLORS: Record<string, string> = {
  postgres: 'bg-blue-100 text-blue-700',
  mysql: 'bg-orange-100 text-orange-700',
  redshift: 'bg-red-100 text-red-700',
  bigquery: 'bg-yellow-100 text-yellow-700',
  iceberg: 'bg-purple-100 text-purple-700',
  api: 'bg-emerald-100 text-emerald-700',
}

function SourceTypeBadge({ type }: { type: string }) {
  const color = SOURCE_TYPE_COLORS[type] ?? 'bg-slate-100 text-slate-600'
  const Icon = SOURCE_TYPE_ICONS[type] ?? SOURCE_TYPE_ICONS.default
  return (
    <span className={clsx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', color)}>
      <Icon className="h-3 w-3" />
      {type}
    </span>
  )
}

interface AddSourceForm {
  name: string
  type: string
  host: string
  port: string
  database: string
  username: string
  password: string
  description: string
}

const EMPTY_FORM: AddSourceForm = {
  name: '',
  type: 'postgres',
  host: '',
  port: '5432',
  database: '',
  username: '',
  password: '',
  description: '',
}

const SOURCE_TYPES = [
  { value: 'postgres', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'redshift', label: 'Amazon Redshift' },
  { value: 'bigquery', label: 'Google BigQuery' },
  { value: 'iceberg', label: 'Apache Iceberg' },
  { value: 'api', label: 'REST API' },
]

function ExpandedTables({ sourceId }: { sourceId: string }) {
  const { data: tables, isLoading } = useQuery({
    queryKey: ['source-tables', sourceId],
    queryFn: () =>
      sourcesApi.getTables(sourceId).catch(() =>
        Array.from({ length: 5 }, (_, i) => ({
          name: `table_${i + 1}`,
          schema: 'public',
          row_count: Math.floor(Math.random() * 500000),
          last_updated: new Date(Date.now() - Math.random() * 7200000).toISOString(),
        } satisfies SourceTable))
      ),
  })

  if (isLoading) {
    return (
      <div className="px-4 py-3 bg-slate-50 border-t border-slate-100">
        <div className="animate-pulse space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-4 bg-slate-200 rounded w-1/2" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-slate-50 border-t border-slate-100 px-4 py-3">
      <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
        <Table2 className="h-3.5 w-3.5" /> Tables ({tables?.length ?? 0})
      </p>
      <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
        {tables?.map(t => (
          <div
            key={t.name}
            className="flex items-center justify-between rounded-md bg-white border border-slate-200 px-3 py-1.5"
          >
            <span className="text-xs font-mono text-slate-700 truncate">{t.schema}.{t.name}</span>
            <span className="ml-2 text-[10px] text-slate-400 flex-shrink-0">
              {t.row_count.toLocaleString()} rows
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Sources() {
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [form, setForm] = useState<AddSourceForm>(EMPTY_FORM)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set())
  const [assessmentSourceId, setAssessmentSourceId] = useState<string>('')

  const { data: sources, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: () => sourcesApi.list().catch(() => MOCK_SOURCES),
  })
  const { data: reports = [], isLoading: reportsLoading } = useQuery({
    queryKey: ['assessment-reports', assessmentSourceId],
    queryFn: () => assessmentApi.listReports(assessmentSourceId || undefined),
  })

  const createMutation = useMutation({
    mutationFn: (data: SourceCreate) => sourcesApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['sources'] })
      setAddOpen(false)
      setForm(EMPTY_FORM)
    },
  })
  const generateAssessmentMutation = useMutation({
    mutationFn: () => assessmentApi.generateReport(assessmentSourceId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['assessment-reports'] })
    },
  })

  const handleCreate = () => {
    if (!form.name || !form.host || !form.database) return
    createMutation.mutate({
      name: form.name,
      type: form.type,
      host: form.host,
      port: parseInt(form.port, 10),
      database: form.database,
      username: form.username,
      password: form.password,
      description: form.description,
    })
  }

  const handleSync = async (id: string) => {
    setSyncingIds(prev => new Set(prev).add(id))
    try {
      await sourcesApi.sync(id)
      void queryClient.invalidateQueries({ queryKey: ['sources'] })
    } catch {
      // swallow — in POC mode the API may not be available
    } finally {
      setSyncingIds(prev => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const toggleExpand = (id: string) => {
    setExpandedId(prev => (prev === id ? null : id))
  }

  const openReport = (report: AssessmentReport) => {
    window.open(`http://localhost:8000${report.report_url}`, '_blank', 'noopener,noreferrer')
  }

  const field = (key: keyof AddSourceForm) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm(prev => ({ ...prev, [key]: e.target.value })),
  })

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">
            {sources?.length ?? 0} connected source{(sources?.length ?? 0) !== 1 ? 's' : ''}
          </h2>
        </div>
        <Dialog.Root open={addOpen} onOpenChange={setAddOpen}>
          <Dialog.Trigger asChild>
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors shadow-sm"
            >
              <Plus className="h-4 w-4" />
              Add Source
            </button>
          </Dialog.Trigger>

          {/* ── Modal ── */}
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
            <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-6 shadow-xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
              <div className="flex items-center justify-between mb-5">
                <Dialog.Title className="text-base font-semibold text-slate-900">
                  Add Data Source
                </Dialog.Title>
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </Dialog.Close>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Source Name *
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. retail_postgres"
                      {...field('name')}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Source Type *
                    </label>
                    <Select.Root
                      value={form.type}
                      onValueChange={(v) => setForm(prev => ({ ...prev, type: v }))}
                    >
                      <Select.Trigger className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100 bg-white">
                        <Select.Value />
                        <Select.Icon>
                          <ChevronDown className="h-4 w-4 text-slate-400" />
                        </Select.Icon>
                      </Select.Trigger>
                      <Select.Portal>
                        <Select.Content className="z-[100] rounded-lg border border-slate-200 bg-white shadow-lg py-1">
                          <Select.Viewport>
                            {SOURCE_TYPES.map(st => (
                              <Select.Item
                                key={st.value}
                                value={st.value}
                                className="flex cursor-pointer items-center px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 focus:bg-slate-50 outline-none"
                              >
                                <Select.ItemText>{st.label}</Select.ItemText>
                              </Select.Item>
                            ))}
                          </Select.Viewport>
                        </Select.Content>
                      </Select.Portal>
                    </Select.Root>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Host *</label>
                    <input
                      type="text"
                      placeholder="localhost"
                      {...field('host')}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Port</label>
                    <input
                      type="number"
                      placeholder="5432"
                      {...field('port')}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Database *</label>
                    <input
                      type="text"
                      placeholder="my_database"
                      {...field('database')}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Username</label>
                    <input
                      type="text"
                      {...field('username')}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-slate-700 mb-1">Password</label>
                    <input
                      type="password"
                      {...field('password')}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-slate-700 mb-1">Description</label>
                    <textarea
                      rows={2}
                      placeholder="Optional description..."
                      value={form.description}
                      onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100 resize-none"
                    />
                  </div>
                </div>

                {createMutation.isError && (
                  <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-600">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    Failed to create source. Please check connection details.
                  </div>
                )}

                <div className="flex gap-3 pt-1">
                  <Dialog.Close asChild>
                    <button
                      type="button"
                      className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      Cancel
                    </button>
                  </Dialog.Close>
                  <button
                    type="button"
                    onClick={handleCreate}
                    disabled={createMutation.isPending || !form.name || !form.host || !form.database}
                    className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {createMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Plus className="h-4 w-4" />
                    )}
                    Create Source
                  </button>
                </div>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3 justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-800">Data Assessment Reports</h3>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={assessmentSourceId}
              onChange={e => setAssessmentSourceId(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
            >
              <option value="">All sources</option>
              <option value="__default__">POC Default Tables</option>
              {sources?.map(source => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => generateAssessmentMutation.mutate()}
              disabled={!assessmentSourceId || generateAssessmentMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              {generateAssessmentMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              Generate
            </button>
          </div>
        </div>
        {generateAssessmentMutation.isError && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            Failed to generate report. Ensure selected source has queryable tables.
          </div>
        )}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-slate-500">
                <th className="py-2 text-left font-semibold">Source</th>
                <th className="py-2 text-left font-semibold">Table</th>
                <th className="py-2 text-left font-semibold">Rows</th>
                <th className="py-2 text-left font-semibold">Columns</th>
                <th className="py-2 text-left font-semibold">Created</th>
                <th className="py-2 text-right font-semibold">Report</th>
              </tr>
            </thead>
            <tbody>
              {reportsLoading ? (
                <tr>
                  <td colSpan={6} className="py-4 text-slate-400">Loading reports...</td>
                </tr>
              ) : reports.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-4 text-slate-400">No reports generated yet.</td>
                </tr>
              ) : (
                reports.slice(0, 12).map(report => (
                  <tr key={`${report.file_name}`} className="border-b border-slate-100">
                    <td className="py-2 text-slate-700">{report.source_id}</td>
                    <td className="py-2 font-mono text-slate-600">{report.table_fqn}</td>
                    <td className="py-2 text-slate-600">{report.row_count_profiled.toLocaleString()}</td>
                    <td className="py-2 text-slate-600">{report.column_count}</td>
                    <td className="py-2 text-slate-500">
                      {formatDistanceToNow(new Date(report.created_at), { addSuffix: true })}
                    </td>
                    <td className="py-2 text-right">
                      <button
                        type="button"
                        onClick={() => openReport(report)}
                        className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-slate-700 hover:bg-slate-50"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Open
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              <th className="w-8 px-4 py-3" />
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Name
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Type
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Tables
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Last Synced
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <TableRowSkeleton key={i} cols={7} />)
            ) : sources?.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <Database className="h-10 w-10 text-slate-300" />
                    <p className="text-sm font-medium text-slate-500">No sources connected</p>
                    <p className="text-xs text-slate-400">
                      Add your first data source to get started
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              sources?.map(source => (
                <>
                  <tr
                    key={source.id}
                    className={clsx(
                      'border-b border-slate-100 hover:bg-slate-50/70 transition-colors',
                      expandedId === source.id && 'bg-slate-50'
                    )}
                  >
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => toggleExpand(source.id)}
                        className="rounded p-0.5 text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        {expandedId === source.id ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-slate-800">{source.name}</p>
                        {source.description && (
                          <p className="text-xs text-slate-400 truncate max-w-[220px]">
                            {source.description}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <SourceTypeBadge type={source.type} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        status={
                          source.status === 'healthy'
                            ? 'success'
                            : source.status === 'error'
                            ? 'failed'
                            : source.status === 'syncing'
                            ? 'running'
                            : 'unknown'
                        }
                        size="sm"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-slate-700">
                        <Table2 className="h-3.5 w-3.5 text-slate-400" />
                        {source.table_count}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">
                      {source.last_synced
                        ? formatDistanceToNow(new Date(source.last_synced), { addSuffix: true })
                        : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => void handleSync(source.id)}
                        disabled={syncingIds.has(source.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors"
                      >
                        {syncingIds.has(source.id) ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3 w-3" />
                        )}
                        Sync Now
                      </button>
                    </td>
                  </tr>
                  {expandedId === source.id && (
                    <tr key={`${source.id}-expanded`}>
                      <td colSpan={7} className="p-0">
                        <ExpandedTables sourceId={source.id} />
                      </td>
                    </tr>
                  )}
                </>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Status summary */}
      {sources && sources.length > 0 && (
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
            {sources.filter(s => s.status === 'healthy').length} healthy
          </span>
          <span className="flex items-center gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 text-red-500" />
            {sources.filter(s => s.status === 'error').length} errors
          </span>
          <span className="flex items-center gap-1.5">
            <RefreshCw className="h-3.5 w-3.5 text-blue-500" />
            {sources.filter(s => s.status === 'syncing').length} syncing
          </span>
        </div>
      )}
    </div>
  )
}
