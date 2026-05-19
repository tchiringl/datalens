import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Layers,
  Table2,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  BarChart3,
  Clock,
  GitBranch,
  Circle,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import * as Tabs from '@radix-ui/react-tabs'
import { clsx } from 'clsx'
import { cdmApi, MOCK_CDM_MODELS, type CDMModel, type CDMColumn } from '../lib/api'

// ── Helpers ───────────────────────────────────────────────────────────────────

function DQIcon({ status }: { status: CDMColumn['dq_status'] }) {
  switch (status) {
    case 'pass':
      return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
    case 'fail':
      return <XCircle className="h-3.5 w-3.5 text-red-500" />
    case 'warn':
      return <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
    default:
      return <Circle className="h-3.5 w-3.5 text-slate-300" />
  }
}

function formatRows(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toLocaleString()
}

const MODEL_ICONS: Record<string, React.ReactNode> = {
  dim_customers: <span className="text-blue-500">👤</span>,
  dim_products: <span className="text-purple-500">📦</span>,
  dim_stores: <span className="text-emerald-500">🏪</span>,
  dim_date: <span className="text-amber-500">📅</span>,
  fact_orders: <span className="text-orange-500">🧾</span>,
  fact_returns: <span className="text-red-500">↩️</span>,
  fact_inventory: <span className="text-cyan-500">📊</span>,
}

const MATERIALIZATION_COLORS: Record<string, string> = {
  table: 'bg-blue-100 text-blue-700',
  incremental: 'bg-purple-100 text-purple-700',
  view: 'bg-emerald-100 text-emerald-700',
  ephemeral: 'bg-slate-100 text-slate-600',
}

// ── Model detail panel ────────────────────────────────────────────────────────

function ModelDetail({ model }: { model: CDMModel }) {
  const passCount = model.columns.filter(c => c.dq_status === 'pass').length
  const failCount = model.columns.filter(c => c.dq_status === 'fail').length

  return (
    <Tabs.Root defaultValue="columns" className="flex flex-col h-full">
      {/* Model header */}
      <div className="border-b border-slate-100 px-5 pt-5 pb-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <code className="text-lg font-bold text-slate-900">{model.name}</code>
              <span
                className={clsx(
                  'rounded-full px-2.5 py-0.5 text-xs font-medium',
                  MATERIALIZATION_COLORS[model.materialization] ?? 'bg-slate-100 text-slate-600'
                )}
              >
                {model.materialization}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">{model.description}</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg bg-slate-50 px-3 py-2.5">
            <p className="text-[10px] text-slate-400 uppercase tracking-wide">Rows</p>
            <p className="mt-0.5 text-sm font-bold text-slate-800">{formatRows(model.row_count)}</p>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2.5">
            <p className="text-[10px] text-slate-400 uppercase tracking-wide">Columns</p>
            <p className="mt-0.5 text-sm font-bold text-slate-800">{model.columns.length}</p>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2.5">
            <p className="text-[10px] text-slate-400 uppercase tracking-wide">DQ Pass</p>
            <p className="mt-0.5 text-sm font-bold text-emerald-600">
              {passCount}/{model.columns.length}
            </p>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2.5">
            <p className="text-[10px] text-slate-400 uppercase tracking-wide">Updated</p>
            <p className="mt-0.5 text-sm font-bold text-slate-800">
              {formatDistanceToNow(new Date(model.last_updated), { addSuffix: true })}
            </p>
          </div>
        </div>

        {failCount > 0 && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-600">
            <XCircle className="h-4 w-4" />
            {failCount} column{failCount > 1 ? 's have' : ' has'} failing DQ tests
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs.List className="flex border-b border-slate-100 px-5">
        {['columns', 'lineage', 'depends'].map(tab => (
          <Tabs.Trigger
            key={tab}
            value={tab}
            className="px-4 py-3 text-xs font-semibold text-slate-500 border-b-2 border-transparent data-[state=active]:border-blue-600 data-[state=active]:text-blue-600 capitalize transition-colors"
          >
            {tab === 'depends' ? 'Dependencies' : tab}
          </Tabs.Trigger>
        ))}
      </Tabs.List>

      {/* Columns tab */}
      <Tabs.Content value="columns" className="flex-1 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 sticky top-0">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Column</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Nullable</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">DQ</th>
            </tr>
          </thead>
          <tbody>
            {model.columns.map(col => (
              <tr key={col.name} className="border-b border-slate-100 hover:bg-slate-50/50">
                <td className="px-4 py-2.5">
                  <div>
                    <p className="font-mono text-xs font-medium text-slate-800">{col.name}</p>
                    {col.description && (
                      <p className="text-[10px] text-slate-400 mt-0.5 truncate max-w-[180px]">
                        {col.description}
                      </p>
                    )}
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <code className="text-xs bg-slate-100 rounded px-1.5 py-0.5 text-slate-600">
                    {col.data_type}
                  </code>
                </td>
                <td className="px-4 py-2.5">
                  <span className={clsx(
                    'text-xs font-medium',
                    col.nullable ? 'text-slate-400' : 'text-slate-600'
                  )}>
                    {col.nullable ? 'Yes' : 'No'}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <DQIcon status={col.dq_status ?? null} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Tabs.Content>

      {/* Lineage tab */}
      <Tabs.Content value="lineage" className="p-5 overflow-y-auto">
        <div className="space-y-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Data Lineage</p>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs font-medium text-orange-700">
              Source System
            </div>
            <ChevronRight className="h-4 w-4 text-slate-400" />
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700">
              Raw Layer (S3/Iceberg)
            </div>
            <ChevronRight className="h-4 w-4 text-slate-400" />
            {model.depends_on.length > 0 ? (
              model.depends_on.map(dep => (
                <div
                  key={dep}
                  className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-mono font-medium text-amber-700"
                >
                  {dep}
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-400 italic">
                No dependencies
              </div>
            )}
            <ChevronRight className="h-4 w-4 text-slate-400" />
            <div className="rounded-lg border-2 border-blue-300 bg-blue-50 px-3 py-2 text-xs font-mono font-bold text-blue-700">
              {model.name}
            </div>
          </div>

          <div className="mt-4 rounded-lg bg-slate-50 border border-slate-200 p-4">
            <p className="text-xs font-semibold text-slate-600 mb-2">Full lineage path</p>
            <div className="font-mono text-xs text-slate-500 space-y-1">
              {model.depends_on.map(dep => (
                <p key={dep}>
                  <span className="text-orange-500">source</span>
                  {' → '}
                  <span className="text-amber-600">{dep}</span>
                  {' → '}
                  <span className="text-blue-600 font-semibold">{model.name}</span>
                </p>
              ))}
              {model.depends_on.length === 0 && (
                <p>
                  <span className="text-slate-400 italic">No upstream dependencies</span>
                  {' → '}
                  <span className="text-blue-600 font-semibold">{model.name}</span>
                </p>
              )}
            </div>
          </div>
        </div>
      </Tabs.Content>

      {/* Dependencies tab */}
      <Tabs.Content value="depends" className="p-5 overflow-y-auto">
        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Upstream Dependencies ({model.depends_on.length})
          </p>
          {model.depends_on.length === 0 ? (
            <p className="text-sm text-slate-400 italic">This model has no dependencies</p>
          ) : (
            model.depends_on.map(dep => (
              <div
                key={dep}
                className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3"
              >
                <GitBranch className="h-4 w-4 text-slate-400" />
                <code className="text-xs font-mono font-medium text-slate-700">{dep}</code>
                <span
                  className={clsx(
                    'ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium',
                    dep.startsWith('stg_')
                      ? 'bg-amber-100 text-amber-700'
                      : dep.startsWith('dim_') || dep.startsWith('fact_')
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-slate-100 text-slate-600'
                  )}
                >
                  {dep.startsWith('stg_')
                    ? 'staging'
                    : dep.startsWith('dim_')
                    ? 'dimension'
                    : dep.startsWith('fact_')
                    ? 'fact'
                    : 'model'}
                </span>
              </div>
            ))
          )}
        </div>
      </Tabs.Content>
    </Tabs.Root>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function CDMExplorer() {
  const [selectedModel, setSelectedModel] = useState<string>('fact_orders')

  const { data: models, isLoading } = useQuery({
    queryKey: ['cdm-models'],
    queryFn: () => cdmApi.getModels().catch(() => MOCK_CDM_MODELS),
  })

  const displayModels = models ?? MOCK_CDM_MODELS
  const selected = displayModels.find(m => m.name === selectedModel) ?? displayModels[0]

  const dims = displayModels.filter(m => m.name.startsWith('dim_'))
  const facts = displayModels.filter(m => m.name.startsWith('fact_'))

  return (
    <div className="flex gap-5 h-[calc(100vh-8rem)]">
      {/* ── Left panel: Model tree ── */}
      <div className="w-72 flex-shrink-0 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
        <div className="border-b border-slate-100 px-4 py-3">
          <p className="text-xs font-semibold text-slate-700 flex items-center gap-2">
            <Layers className="h-4 w-4 text-blue-500" />
            CDM Models ({displayModels.length})
          </p>
        </div>

        {isLoading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="animate-pulse h-8 bg-slate-100 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-2">
            {/* Dimensions */}
            <div className="mb-1">
              <p className="px-2 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                Dimensions
              </p>
              {dims.map(m => (
                <button
                  key={m.name}
                  type="button"
                  onClick={() => setSelectedModel(m.name)}
                  className={clsx(
                    'w-full flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition-colors',
                    selectedModel === m.name
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-slate-50 border border-transparent'
                  )}
                >
                  <span className="text-base leading-none">{MODEL_ICONS[m.name]}</span>
                  <div className="flex-1 min-w-0">
                    <p
                      className={clsx(
                        'text-xs font-mono font-semibold truncate',
                        selectedModel === m.name ? 'text-blue-700' : 'text-slate-700'
                      )}
                    >
                      {m.name}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {formatRows(m.row_count)} rows
                    </p>
                  </div>
                  {selectedModel === m.name && (
                    <ChevronRight className="h-3 w-3 text-blue-400 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>

            {/* Facts */}
            <div>
              <p className="px-2 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                Facts
              </p>
              {facts.map(m => (
                <button
                  key={m.name}
                  type="button"
                  onClick={() => setSelectedModel(m.name)}
                  className={clsx(
                    'w-full flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition-colors',
                    selectedModel === m.name
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-slate-50 border border-transparent'
                  )}
                >
                  <span className="text-base leading-none">{MODEL_ICONS[m.name]}</span>
                  <div className="flex-1 min-w-0">
                    <p
                      className={clsx(
                        'text-xs font-mono font-semibold truncate',
                        selectedModel === m.name ? 'text-blue-700' : 'text-slate-700'
                      )}
                    >
                      {m.name}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {formatRows(m.row_count)} rows
                    </p>
                  </div>
                  {selectedModel === m.name && (
                    <ChevronRight className="h-3 w-3 text-blue-400 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Footer stats */}
        <div className="border-t border-slate-100 px-4 py-3">
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <BarChart3 className="h-3 w-3" />
              {dims.length} dims
            </span>
            <span className="flex items-center gap-1">
              <Table2 className="h-3 w-3" />
              {facts.length} facts
            </span>
            <span className="flex items-center gap-1 ml-auto">
              <Clock className="h-3 w-3" />
              Live
            </span>
          </div>
        </div>
      </div>

      {/* ── Right panel: Model detail ── */}
      <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {selected ? (
          <ModelDetail model={selected} />
        ) : (
          <div className="flex h-full items-center justify-center text-slate-400">
            <div className="text-center">
              <Layers className="h-10 w-10 mx-auto mb-3 text-slate-300" />
              <p className="text-sm">Select a model to explore</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
