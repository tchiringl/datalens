import { useState, useMemo } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import {
  Search,
  Layers,
  Database,
  Table2,
  User,
  ArrowRight,
  Box,
  BookOpen,
  Tag,
  ShieldCheck,
  Globe,
  HardDrive,
  Edit3,
} from 'lucide-react'
import { clsx } from 'clsx'
import { MOCK_SOURCES, MOCK_CDM_MODELS } from '../lib/api'

// ── Asset Catalog ─────────────────────────────────────────────────────────────

type AssetType = 'source' | 'staging' | 'cdm_dimension' | 'cdm_fact'

interface Asset {
  id: string
  name: string
  type: AssetType
  schema: string
  description: string
  tags: string[]
  owner: string
  lastUpdated: string
  rowCount?: number
}

const STAGING_MODELS: Asset[] = [
  { id: 'stg_orders', name: 'stg_orders', type: 'staging', schema: 'staging', description: 'Cleaned and standardized orders from retail_postgres', tags: ['orders', 'staging'], owner: 'data-engineering', lastUpdated: new Date(Date.now() - 35 * 60000).toISOString() },
  { id: 'stg_order_lines', name: 'stg_order_lines', type: 'staging', schema: 'staging', description: 'Order line items normalized from POS', tags: ['orders', 'staging'], owner: 'data-engineering', lastUpdated: new Date(Date.now() - 35 * 60000).toISOString() },
  { id: 'stg_customers', name: 'stg_customers', type: 'staging', schema: 'staging', description: 'Customer records from CRM and POS', tags: ['customers', 'staging'], owner: 'data-engineering', lastUpdated: new Date(Date.now() - 35 * 60000).toISOString() },
  { id: 'stg_products', name: 'stg_products', type: 'staging', schema: 'staging', description: 'Product catalogue from ERP', tags: ['products', 'staging'], owner: 'data-engineering', lastUpdated: new Date(Date.now() - 35 * 60000).toISOString() },
  { id: 'stg_stores', name: 'stg_stores', type: 'staging', schema: 'staging', description: 'Store location data', tags: ['stores', 'staging'], owner: 'data-engineering', lastUpdated: new Date(Date.now() - 35 * 60000).toISOString() },
  { id: 'stg_returns', name: 'stg_returns', type: 'staging', schema: 'staging', description: 'Return transactions from Iceberg lakehouse', tags: ['returns', 'staging'], owner: 'data-engineering', lastUpdated: new Date(Date.now() - 35 * 60000).toISOString() },
  { id: 'stg_inventory', name: 'stg_inventory', type: 'staging', schema: 'staging', description: 'Inventory snapshots from warehouse system', tags: ['inventory', 'staging'], owner: 'data-engineering', lastUpdated: new Date(Date.now() - 120 * 60000).toISOString() },
  { id: 'stg_crm_accounts', name: 'stg_crm_accounts', type: 'staging', schema: 'staging', description: 'CRM account records from REST API', tags: ['customers', 'crm', 'staging'], owner: 'data-engineering', lastUpdated: new Date(Date.now() - 240 * 60000).toISOString() },
]

function buildAllAssets(): Asset[] {
  const sourceAssets: Asset[] = MOCK_SOURCES.map(s => ({
    id: `source-${s.id}`,
    name: s.name,
    type: 'source' as AssetType,
    schema: s.database,
    description: s.description ?? '',
    tags: [s.type],
    owner: 'data-engineering',
    lastUpdated: s.last_synced ?? s.created_at,
    rowCount: s.table_count,
  }))

  const cdmAssets: Asset[] = MOCK_CDM_MODELS.map(m => ({
    id: `cdm-${m.name}`,
    name: m.name,
    type: m.name.startsWith('dim_') ? 'cdm_dimension' : 'cdm_fact' as AssetType,
    schema: m.schema,
    description: m.description,
    tags: m.tags,
    owner: 'analytics-engineering',
    lastUpdated: m.last_updated,
    rowCount: m.row_count,
  }))

  return [...sourceAssets, ...STAGING_MODELS, ...cdmAssets]
}

const ALL_ASSETS = buildAllAssets()

function AssetTypeChip({ type }: { type: AssetType }) {
  const cfg = {
    source: { label: 'Source', icon: Database, classes: 'bg-blue-100 text-blue-700' },
    staging: { label: 'Staging', icon: Table2, classes: 'bg-amber-100 text-amber-700' },
    cdm_dimension: { label: 'Dimension', icon: Layers, classes: 'bg-purple-100 text-purple-700' },
    cdm_fact: { label: 'Fact', icon: Layers, classes: 'bg-orange-100 text-orange-700' },
  }[type]
  const Icon = cfg.icon
  return (
    <span className={clsx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold', cfg.classes)}>
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  )
}

function AssetCatalog() {
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')

  const filtered = useMemo(() => {
    return ALL_ASSETS.filter(a => {
      const q = search.toLowerCase()
      if (q && !a.name.includes(q) && !a.description.toLowerCase().includes(q)) return false
      if (typeFilter !== 'all' && a.type !== typeFilter) return false
      return true
    })
  }, [search, typeFilter])

  return (
    <div className="space-y-4">
      {/* Search + filter */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search assets by name or description..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full rounded-lg border border-slate-200 pl-9 pr-4 py-2.5 text-sm text-slate-700 placeholder-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>
        <div className="flex items-center gap-2">
          {(['all', 'source', 'staging', 'cdm_dimension', 'cdm_fact'] as const).map(t => (
            <button
              key={t}
              type="button"
              onClick={() => setTypeFilter(t)}
              className={clsx(
                'rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
                typeFilter === t
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              )}
            >
              {t === 'all' ? 'All' : t === 'cdm_dimension' ? 'Dimension' : t === 'cdm_fact' ? 'Fact' : t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="text-xs text-slate-400">{filtered.length} assets</div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-100">
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Asset</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Schema</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Tags</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Owner</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-400">
                  No assets match your search
                </td>
              </tr>
            ) : (
              filtered.map(asset => (
                <tr key={asset.id} className="border-b border-slate-100 hover:bg-slate-50/70 transition-colors">
                  <td className="px-4 py-3">
                    <div>
                      <code className="text-xs font-mono font-semibold text-slate-800">{asset.name}</code>
                      <p className="text-[11px] text-slate-400 mt-0.5 truncate max-w-[260px]">{asset.description}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <AssetTypeChip type={asset.type} />
                  </td>
                  <td className="px-4 py-3">
                    <code className="text-xs bg-slate-100 rounded px-1.5 py-0.5 text-slate-600">{asset.schema}</code>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {asset.tags.map(tag => (
                        <span key={tag} className="inline-flex items-center gap-0.5 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                          <Tag className="h-2.5 w-2.5" /> {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 text-xs text-slate-600">
                      <User className="h-3 w-3 text-slate-400" />
                      {asset.owner}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Lineage View ──────────────────────────────────────────────────────────────

interface LineageBlock {
  id: string
  label: string
  sublabel?: string
  color: string
  icon: React.ReactNode
}

const SOURCE_BLOCKS: LineageBlock[] = [
  {
    id: 'retail_postgres',
    label: 'retail_postgres',
    sublabel: 'PostgreSQL · 14 tables',
    color: 'border-blue-300 bg-blue-50',
    icon: <Database className="h-4 w-4 text-blue-500" />,
  },
  {
    id: 'minio_iceberg',
    label: 'minio / iceberg',
    sublabel: 'Lakehouse · 7 tables',
    color: 'border-purple-300 bg-purple-50',
    icon: <HardDrive className="h-4 w-4 text-purple-500" />,
  },
  {
    id: 'crm_api',
    label: 'crm_api',
    sublabel: 'REST API · 3 endpoints',
    color: 'border-emerald-300 bg-emerald-50',
    icon: <Globe className="h-4 w-4 text-emerald-500" />,
  },
]

const STAGING_BLOCKS: LineageBlock[] = [
  { id: 'stg_customers', label: 'stg_customers', color: 'border-amber-200 bg-amber-50', icon: <Box className="h-3.5 w-3.5 text-amber-500" /> },
  { id: 'stg_orders', label: 'stg_orders', color: 'border-amber-200 bg-amber-50', icon: <Box className="h-3.5 w-3.5 text-amber-500" /> },
  { id: 'stg_order_lines', label: 'stg_order_lines', color: 'border-amber-200 bg-amber-50', icon: <Box className="h-3.5 w-3.5 text-amber-500" /> },
  { id: 'stg_products', label: 'stg_products', color: 'border-amber-200 bg-amber-50', icon: <Box className="h-3.5 w-3.5 text-amber-500" /> },
  { id: 'stg_stores', label: 'stg_stores', color: 'border-amber-200 bg-amber-50', icon: <Box className="h-3.5 w-3.5 text-amber-500" /> },
  { id: 'stg_returns', label: 'stg_returns', color: 'border-amber-200 bg-amber-50', icon: <Box className="h-3.5 w-3.5 text-amber-500" /> },
  { id: 'stg_inventory', label: 'stg_inventory', color: 'border-amber-200 bg-amber-50', icon: <Box className="h-3.5 w-3.5 text-amber-500" /> },
  { id: 'stg_crm_accounts', label: 'stg_crm_accounts', color: 'border-amber-200 bg-amber-50', icon: <Box className="h-3.5 w-3.5 text-amber-500" /> },
]

const CDM_BLOCKS: LineageBlock[] = MOCK_CDM_MODELS.map(m => ({
  id: m.name,
  label: m.name,
  sublabel: m.materialization,
  color: m.name.startsWith('dim_')
    ? 'border-blue-300 bg-blue-50'
    : 'border-orange-300 bg-orange-50',
  icon: <Layers className={clsx('h-4 w-4', m.name.startsWith('dim_') ? 'text-blue-500' : 'text-orange-500')} />,
}))

function Block({ b, size = 'md' }: { b: LineageBlock; size?: 'sm' | 'md' }) {
  return (
    <div className={clsx('rounded-lg border-2 px-3 py-2.5 shadow-sm', b.color, size === 'sm' ? 'text-[11px]' : 'text-xs')}>
      <div className="flex items-center gap-1.5 font-semibold font-mono text-slate-800">
        {b.icon}
        {b.label}
      </div>
      {b.sublabel && <p className="text-[10px] text-slate-400 mt-0.5 ml-5">{b.sublabel}</p>}
    </div>
  )
}

function LineageTab() {
  return (
    <div className="overflow-x-auto pb-4">
      <div className="min-w-[800px]">
        {/* Legend */}
        <div className="flex items-center gap-4 mb-6 flex-wrap text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded border-2 border-blue-300 bg-blue-50" /> Sources / Dimensions
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded border-2 border-amber-200 bg-amber-50" /> Staging Models
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded border-2 border-orange-300 bg-orange-50" /> Fact Models
          </div>
        </div>

        <div className="flex items-start gap-6">
          {/* Sources */}
          <div className="flex flex-col gap-3 w-52">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Sources</p>
            {SOURCE_BLOCKS.map(b => (
              <Block key={b.id} b={b} />
            ))}
          </div>

          {/* Arrow */}
          <div className="flex flex-col items-center pt-8 gap-1">
            <ArrowRight className="h-5 w-5 text-slate-300" />
            <div className="h-32 border-l-2 border-dashed border-slate-200" />
            <ArrowRight className="h-5 w-5 text-slate-300" />
          </div>

          {/* Staging */}
          <div className="flex flex-col gap-2 w-48">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Staging Layer</p>
            {STAGING_BLOCKS.map(b => (
              <Block key={b.id} b={b} size="sm" />
            ))}
          </div>

          {/* Arrow */}
          <div className="flex flex-col items-center pt-8 gap-1">
            <ArrowRight className="h-5 w-5 text-slate-300" />
            <div className="h-48 border-l-2 border-dashed border-slate-200" />
            <ArrowRight className="h-5 w-5 text-slate-300" />
          </div>

          {/* CDM */}
          <div className="flex flex-col gap-2 w-52">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">CDM Layer</p>
            {CDM_BLOCKS.map(b => (
              <Block key={b.id} b={b} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Ownership Tab ─────────────────────────────────────────────────────────────

const OWNERSHIP_DATA = [
  { team: 'data-engineering', assets: ALL_ASSETS.filter(a => a.owner === 'data-engineering').length, description: 'Responsible for ingestion pipelines and staging models', members: ['Alice Chen', 'Bob Martinez', 'Carol Kim'] },
  { team: 'analytics-engineering', assets: ALL_ASSETS.filter(a => a.owner === 'analytics-engineering').length, description: 'Owns CDM models, dbt transformations, and DQ checks', members: ['Dan Park', 'Eva Singh'] },
  { team: 'platform', assets: 0, description: 'Manages infrastructure, Airflow, MinIO, and Trino', members: ['Frank Liu', 'Grace Osei'] },
]

function OwnershipTab() {
  const [editingAsset, setEditingAsset] = useState<string | null>(null)

  return (
    <div className="space-y-6">
      {/* Team ownership cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {OWNERSHIP_DATA.map(team => (
          <div key={team.team} className="rounded-xl border border-slate-200 bg-white shadow-sm p-5">
            <div className="flex items-center gap-2 mb-2">
              <div className="h-8 w-8 rounded-lg bg-blue-100 flex items-center justify-center">
                <ShieldCheck className="h-4 w-4 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">{team.team}</p>
                <p className="text-xs text-slate-400">{team.assets} assets</p>
              </div>
            </div>
            <p className="text-xs text-slate-500 mb-3">{team.description}</p>
            <div className="flex flex-wrap gap-1">
              {team.members.map(m => (
                <span key={m} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
                  <User className="h-2.5 w-2.5" /> {m}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Asset ownership table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3">
          <p className="text-sm font-semibold text-slate-700">Asset Ownership</p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-100">
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Asset</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Owner Team</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Tags</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Actions</th>
            </tr>
          </thead>
          <tbody>
            {ALL_ASSETS.map(asset => (
              <tr key={asset.id} className="border-b border-slate-100 hover:bg-slate-50/70 transition-colors">
                <td className="px-4 py-3">
                  <code className="text-xs font-mono font-medium text-slate-800">{asset.name}</code>
                </td>
                <td className="px-4 py-3">
                  <AssetTypeChip type={asset.type} />
                </td>
                <td className="px-4 py-3">
                  {editingAsset === asset.id ? (
                    <select
                      className="rounded border border-blue-300 px-2 py-1 text-xs focus:outline-none"
                      defaultValue={asset.owner}
                      onBlur={() => setEditingAsset(null)}
                    >
                      <option>data-engineering</option>
                      <option>analytics-engineering</option>
                      <option>platform</option>
                    </select>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs text-slate-600">
                      <User className="h-3 w-3 text-slate-400" />
                      {asset.owner}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {asset.tags.map(t => (
                      <span key={t} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{t}</span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => setEditingAsset(editingAsset === asset.id ? null : asset.id)}
                    className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-slate-500 hover:bg-slate-50 transition-colors"
                  >
                    <Edit3 className="h-3 w-3" />
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function Governance() {
  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-blue-50 flex items-center justify-center">
          <BookOpen className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Data Governance</h2>
          <p className="text-xs text-slate-500">
            {ALL_ASSETS.length} registered assets · {MOCK_SOURCES.length} sources · {MOCK_CDM_MODELS.length} CDM models
          </p>
        </div>
      </div>

      <Tabs.Root defaultValue="catalog">
        <Tabs.List className="flex border-b border-slate-200 gap-1">
          {[
            { value: 'catalog', label: 'Asset Catalog', icon: BookOpen },
            { value: 'lineage', label: 'Lineage', icon: Layers },
            { value: 'ownership', label: 'Ownership', icon: User },
          ].map(tab => (
            <Tabs.Trigger
              key={tab.value}
              value={tab.value}
              className="flex items-center gap-2 px-5 py-3 text-sm font-medium text-slate-500 border-b-2 border-transparent data-[state=active]:border-blue-600 data-[state=active]:text-blue-600 transition-colors"
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <div className="mt-5">
          <Tabs.Content value="catalog">
            <AssetCatalog />
          </Tabs.Content>
          <Tabs.Content value="lineage">
            <LineageTab />
          </Tabs.Content>
          <Tabs.Content value="ownership">
            <OwnershipTab />
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </div>
  )
}
