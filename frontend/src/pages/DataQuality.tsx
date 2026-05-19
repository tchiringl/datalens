import { useState, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Filter,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import * as Select from '@radix-ui/react-select'
import { clsx } from 'clsx'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TableRowSkeleton } from '../components/ui/LoadingSkeleton'
import { dqApi, MOCK_DQ_RESULTS, type DQResult } from '../lib/api'

// ── Donut chart helpers ────────────────────────────────────────────────────────

const CHART_COLORS = {
  pass: '#10b981',
  fail: '#ef4444',
  warn: '#f59e0b',
  not_null: '#3b82f6',
  unique: '#8b5cf6',
  relationships: '#06b6d4',
  custom: '#f97316',
}

interface DonutCardProps {
  title: string
  data: { name: string; value: number; color: string }[]
  centerLabel?: string
  centerValue?: string | number
}

function DonutCard({ title, data, centerLabel, centerValue }: DonutCardProps) {
  const total = data.reduce((sum, d) => sum + d.value, 0)

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-slate-700 mb-4">{title}</h3>
      <div className="relative" style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={72}
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [
                `${value} (${total > 0 ? Math.round((value / total) * 100) : 0}%)`,
                '',
              ]}
              contentStyle={{
                fontSize: 12,
                borderRadius: 8,
                border: '1px solid #e2e8f0',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        {centerValue !== undefined && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-bold text-slate-900">{centerValue}</span>
            {centerLabel && (
              <span className="text-[10px] text-slate-400 mt-0.5">{centerLabel}</span>
            )}
          </div>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 justify-center">
        {data.map(d => (
          <div key={d.name} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ background: d.color }} />
            {d.name}: <span className="font-semibold">{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Failing test card ──────────────────────────────────────────────────────────

function FailingTestCard({ result }: { result: DQResult }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-xl border border-red-200 bg-red-50 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(prev => !prev)}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-red-100/50 transition-colors"
      >
        <XCircle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-red-800">
              {result.model}
              {result.column_name && (
                <span className="font-mono text-red-600">.{result.column_name}</span>
              )}
            </span>
            <span className="text-xs rounded bg-red-100 text-red-600 px-2 py-0.5 font-medium">
              {result.test_type}
            </span>
            <span className="text-xs text-red-500">
              {result.failures.toLocaleString()} failures
            </span>
          </div>
        </div>
        <div className="flex-shrink-0">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-red-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-red-400" />
          )}
        </div>
      </button>
      {expanded && result.message && (
        <div className="border-t border-red-200 px-4 py-3 bg-white">
          <p className="text-xs font-medium text-slate-600 mb-1">Error details</p>
          <code className="text-xs text-red-700 bg-red-50 rounded px-2 py-1.5 block font-mono">
            {result.message}
          </code>
          <p className="text-xs text-slate-400 mt-2">
            Last run: {formatDistanceToNow(new Date(result.last_run), { addSuffix: true })} ·{' '}
            {result.execution_time}s
          </p>
        </div>
      )}
    </div>
  )
}

// ── Test status icon ───────────────────────────────────────────────────────────

function TestStatusIcon({ status }: { status: DQResult['status'] }) {
  switch (status) {
    case 'pass':
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
    case 'fail':
      return <XCircle className="h-4 w-4 text-red-500" />
    case 'warn':
      return <AlertTriangle className="h-4 w-4 text-amber-500" />
    case 'error':
      return <AlertCircle className="h-4 w-4 text-red-600" />
  }
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function DataQuality() {
  const queryClient = useQueryClient()
  const [filterStatus, setFilterStatus] = useState('all')
  const [filterModel, setFilterModel] = useState('all')
  const [filterType, setFilterType] = useState('all')
  const [rerunning, setRerunning] = useState(false)

  const { data: results, isLoading } = useQuery({
    queryKey: ['dq-results'],
    queryFn: () => dqApi.getResults().catch(() => MOCK_DQ_RESULTS),
  })

  const dqResults = results ?? MOCK_DQ_RESULTS

  // Computed summaries
  const passCount = dqResults.filter(r => r.status === 'pass').length
  const failCount = dqResults.filter(r => r.status === 'fail').length
  const warnCount = dqResults.filter(r => r.status === 'warn').length
  const total = dqResults.length

  const overallPassData = [
    { name: 'Pass', value: passCount, color: CHART_COLORS.pass },
    { name: 'Fail', value: failCount, color: CHART_COLORS.fail },
    { name: 'Warn', value: warnCount, color: CHART_COLORS.warn },
  ]

  const byType = useMemo(() => {
    const counts: Record<string, number> = {}
    dqResults.forEach(r => {
      counts[r.test_type] = (counts[r.test_type] ?? 0) + 1
    })
    const colorMap: Record<string, string> = {
      not_null: CHART_COLORS.not_null,
      unique: CHART_COLORS.unique,
      relationships: CHART_COLORS.relationships,
      custom: CHART_COLORS.custom,
    }
    return Object.entries(counts).map(([name, value]) => ({
      name,
      value,
      color: colorMap[name] ?? '#94a3b8',
    }))
  }, [dqResults])

  const byModel = useMemo(() => {
    const counts: Record<string, { pass: number; fail: number }> = {}
    dqResults.forEach(r => {
      if (!counts[r.model]) counts[r.model] = { pass: 0, fail: 0 }
      if (r.status === 'pass') counts[r.model].pass++
      else counts[r.model].fail++
    })
    const colors = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#f97316', '#ef4444']
    return Object.entries(counts).map(([name, c], i) => ({
      name,
      value: c.pass + c.fail,
      color: colors[i % colors.length] ?? '#94a3b8',
    }))
  }, [dqResults])

  // Filtered results
  const filteredResults = useMemo(() => {
    return dqResults.filter(r => {
      if (filterStatus !== 'all' && r.status !== filterStatus) return false
      if (filterModel !== 'all' && r.model !== filterModel) return false
      if (filterType !== 'all' && r.test_type !== filterType) return false
      return true
    })
  }, [dqResults, filterStatus, filterModel, filterType])

  const failingTests = dqResults.filter(r => r.status === 'fail')

  const uniqueModels = [...new Set(dqResults.map(r => r.model))].sort()
  const uniqueTypes = [...new Set(dqResults.map(r => r.test_type))].sort()

  const handleRerun = async () => {
    setRerunning(true)
    await new Promise(resolve => setTimeout(resolve, 2000))
    void queryClient.invalidateQueries({ queryKey: ['dq-results'] })
    setRerunning(false)
  }

  return (
    <div className="space-y-6">
      {/* ── Summary Row ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            {passCount}/{total} tests passing ({total > 0 ? Math.round((passCount / total) * 100) : 0}%)
          </span>
          {failCount > 0 && (
            <span className="flex items-center gap-1.5 text-red-600 font-medium">
              <ShieldAlert className="h-4 w-4" />
              {failCount} failing
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => void handleRerun()}
          disabled={rerunning}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm"
        >
          {rerunning ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Re-run Tests
        </button>
      </div>

      {/* ── Donut Charts ── */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <DonutCard
          title="Overall Pass Rate"
          data={overallPassData}
          centerValue={`${total > 0 ? Math.round((passCount / total) * 100) : 0}%`}
          centerLabel="pass rate"
        />
        <DonutCard
          title="Tests by Type"
          data={byType}
          centerValue={total}
          centerLabel="total tests"
        />
        <DonutCard
          title="Coverage by Model"
          data={byModel}
          centerValue={uniqueModels.length}
          centerLabel="models"
        />
      </div>

      {/* ── Failing Tests ── */}
      {failingTests.length > 0 && (
        <div className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <AlertCircle className="h-4 w-4 text-red-500" />
            Failing Tests ({failingTests.length})
          </h2>
          <div className="space-y-2">
            {failingTests.map(r => (
              <FailingTestCard key={r.id} result={r} />
            ))}
          </div>
        </div>
      )}

      {/* ── Filter Bar ── */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-slate-100">
          <Filter className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-medium text-slate-500">Filter:</span>

          {/* Status filter */}
          <Select.Root value={filterStatus} onValueChange={setFilterStatus}>
            <Select.Trigger className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none bg-white min-w-[100px]">
              <Select.Value placeholder="Status" />
              <Select.Icon><ChevronDown className="h-3 w-3 text-slate-400" /></Select.Icon>
            </Select.Trigger>
            <Select.Portal>
              <Select.Content className="z-50 rounded-lg border border-slate-200 bg-white shadow-lg py-1">
                <Select.Viewport>
                  {['all', 'pass', 'fail', 'warn', 'error'].map(s => (
                    <Select.Item
                      key={s}
                      value={s}
                      className="flex cursor-pointer items-center px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 outline-none capitalize"
                    >
                      <Select.ItemText>{s === 'all' ? 'All Statuses' : s}</Select.ItemText>
                    </Select.Item>
                  ))}
                </Select.Viewport>
              </Select.Content>
            </Select.Portal>
          </Select.Root>

          {/* Model filter */}
          <Select.Root value={filterModel} onValueChange={setFilterModel}>
            <Select.Trigger className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none bg-white min-w-[130px]">
              <Select.Value placeholder="Model" />
              <Select.Icon><ChevronDown className="h-3 w-3 text-slate-400" /></Select.Icon>
            </Select.Trigger>
            <Select.Portal>
              <Select.Content className="z-50 rounded-lg border border-slate-200 bg-white shadow-lg py-1">
                <Select.Viewport>
                  <Select.Item
                    value="all"
                    className="flex cursor-pointer items-center px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 outline-none"
                  >
                    <Select.ItemText>All Models</Select.ItemText>
                  </Select.Item>
                  {uniqueModels.map(m => (
                    <Select.Item
                      key={m}
                      value={m}
                      className="flex cursor-pointer items-center px-3 py-2 text-xs font-mono text-slate-700 hover:bg-slate-50 outline-none"
                    >
                      <Select.ItemText>{m}</Select.ItemText>
                    </Select.Item>
                  ))}
                </Select.Viewport>
              </Select.Content>
            </Select.Portal>
          </Select.Root>

          {/* Type filter */}
          <Select.Root value={filterType} onValueChange={setFilterType}>
            <Select.Trigger className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none bg-white min-w-[130px]">
              <Select.Value placeholder="Test Type" />
              <Select.Icon><ChevronDown className="h-3 w-3 text-slate-400" /></Select.Icon>
            </Select.Trigger>
            <Select.Portal>
              <Select.Content className="z-50 rounded-lg border border-slate-200 bg-white shadow-lg py-1">
                <Select.Viewport>
                  <Select.Item
                    value="all"
                    className="flex cursor-pointer items-center px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 outline-none"
                  >
                    <Select.ItemText>All Types</Select.ItemText>
                  </Select.Item>
                  {uniqueTypes.map(t => (
                    <Select.Item
                      key={t}
                      value={t}
                      className="flex cursor-pointer items-center px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 outline-none"
                    >
                      <Select.ItemText>{t}</Select.ItemText>
                    </Select.Item>
                  ))}
                </Select.Viewport>
              </Select.Content>
            </Select.Portal>
          </Select.Root>

          <span className="ml-auto text-xs text-slate-400">
            {filteredResults.length} of {total} tests
          </span>
        </div>

        {/* Tests table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100">
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Model
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Column
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Test Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Failures
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Last Run
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRowSkeleton key={i} cols={7} />
                ))
              ) : filteredResults.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-slate-400">
                    No tests match your filters
                  </td>
                </tr>
              ) : (
                filteredResults.map(result => (
                  <tr
                    key={result.id}
                    className={clsx(
                      'border-b border-slate-100 hover:bg-slate-50/70 transition-colors',
                      result.status === 'fail' && 'bg-red-50/30',
                      result.status === 'warn' && 'bg-amber-50/30'
                    )}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs font-medium text-slate-700">
                        {result.model}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-slate-500">
                        {result.column_name ?? <span className="text-slate-300 italic">—</span>}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                        {result.test_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <TestStatusIcon status={result.status} />
                        <StatusBadge status={result.status} size="sm" />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {result.failures > 0 ? (
                        <span className="font-semibold text-red-600">
                          {result.failures.toLocaleString()}
                        </span>
                      ) : result.warn_count > 0 ? (
                        <span className="font-semibold text-amber-600">
                          {result.warn_count.toLocaleString()} warns
                        </span>
                      ) : (
                        <span className="text-emerald-600">0</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {formatDistanceToNow(new Date(result.last_run), { addSuffix: true })}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {result.execution_time}s
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
