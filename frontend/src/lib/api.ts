import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 10000 })
const mockApi = axios.create({ baseURL: '/mock', timeout: 5000 })

// ─── TypeScript types ─────────────────────────────────────────────────────────

export interface SourceCreate {
  name: string
  type: string
  host: string
  port: number
  database: string
  username: string
  password: string
  description?: string
}

export interface DataSource {
  id: string
  name: string
  type: string
  status: 'healthy' | 'error' | 'syncing' | 'unknown'
  host: string
  port: number
  database: string
  description?: string
  table_count: number
  last_synced: string | null
  created_at: string
}

export interface SourceTable {
  name: string
  schema: string
  row_count: number
  last_updated: string
}

export interface PipelineRun {
  run_id: string
  dag_id: string
  state: 'success' | 'failed' | 'running' | 'queued'
  start_date: string | null
  end_date: string | null
  duration: number | null
}

export interface Pipeline {
  dag_id: string
  description: string
  schedule: string
  is_active: boolean
  last_run: PipelineRun | null
  next_run: string | null
  tags: string[]
}

function normalizePipelineTags(tags: unknown): string[] {
  if (!Array.isArray(tags)) return []
  return tags
    .map(tag => {
      if (typeof tag === 'string') return tag
      if (tag && typeof tag === 'object' && 'name' in tag) {
        const name = (tag as { name?: unknown }).name
        return typeof name === 'string' ? name : null
      }
      return null
    })
    .filter((tag): tag is string => Boolean(tag))
}

function normalizePipeline(pipeline: Pipeline): Pipeline {
  return {
    ...pipeline,
    tags: normalizePipelineTags(pipeline.tags),
  }
}

export interface PipelineSummary {
  total: number
  success: number
  failed: number
  running: number
  queued: number
}

export interface DQResult {
  id: string
  model: string
  column_name: string | null
  test_type: string
  status: 'pass' | 'fail' | 'warn' | 'error'
  failures: number
  warn_count: number
  execution_time: number
  last_run: string
  message?: string
}

export interface DQSummary {
  total_tests: number
  passing: number
  failing: number
  warnings: number
  pass_rate: number
  by_type: Record<string, { pass: number; fail: number }>
  by_model: Record<string, { pass: number; fail: number }>
}

export interface CDMColumn {
  name: string
  data_type: string
  nullable: boolean
  description?: string
  dq_status?: 'pass' | 'fail' | 'warn' | null
}

export interface CDMModel {
  name: string
  schema: string
  materialization: string
  description: string
  row_count: number
  last_updated: string
  columns: CDMColumn[]
  tags: string[]
  depends_on: string[]
}

export interface CDMStats {
  total_models: number
  total_columns: number
  total_rows: number
  last_build: string
}

export interface LineageNode {
  id: string
  label: string
  type: 'source' | 'staging' | 'cdm'
  parents: string[]
}

export interface ActivityEvent {
  id: string
  timestamp: string
  type: 'pipeline' | 'source' | 'dq' | 'cdm'
  title: string
  description: string
  status: 'success' | 'failed' | 'running' | 'info'
}

export interface DashboardStats {
  total_sources: number
  cdm_models: number
  dq_passing: number
  dq_total: number
  pipeline_runs_today: number
  pipeline_success_today: number
}

// ─── API clients ──────────────────────────────────────────────────────────────

export const sourcesApi = {
  list: (): Promise<DataSource[]> => api.get('/sources').then(r => r.data),
  get: (id: string): Promise<DataSource> => api.get(`/sources/${id}`).then(r => r.data),
  create: (data: SourceCreate): Promise<DataSource> => api.post('/sources', data).then(r => r.data),
  delete: (id: string) => api.delete(`/sources/${id}`),
  sync: (id: string) => api.post(`/sources/${id}/sync`),
  getTables: (id: string): Promise<SourceTable[]> => api.get(`/sources/${id}/tables`).then(r => r.data),
}

export const pipelinesApi = {
  list: (): Promise<Pipeline[]> =>
    api
      .get('/pipelines')
      .then(r => (Array.isArray(r.data) ? r.data.map((pipeline: Pipeline) => normalizePipeline(pipeline)) : [])),
  getRuns: (dagId: string): Promise<PipelineRun[]> =>
    api.get(`/pipelines/${dagId}/runs`).then(r => r.data),
  trigger: (dagId: string, conf: Record<string, unknown> = {}) =>
    api.post(`/pipelines/${dagId}/trigger`, { conf }),
  getSummary: (): Promise<PipelineSummary> => api.get('/pipelines/status/summary').then(r => r.data),
}

export const dqApi = {
  getResults: (): Promise<DQResult[]> => api.get('/dq/results').then(r => r.data),
  getSummary: (): Promise<DQSummary> => api.get('/dq/summary').then(r => r.data),
  getIssues: (): Promise<DQResult[]> => api.get('/dq/issues').then(r => r.data),
}

export const cdmApi = {
  getModels: (): Promise<CDMModel[]> => api.get('/cdm/models').then(r => r.data),
  getModel: (name: string): Promise<CDMModel> => api.get(`/cdm/models/${name}`).then(r => r.data),
  getLineage: (table: string): Promise<LineageNode[]> => api.get(`/cdm/lineage/${table}`).then(r => r.data),
  getStats: (): Promise<CDMStats> => api.get('/cdm/stats').then(r => r.data),
}

export const mockDataApi = {
  getStats: (): Promise<DashboardStats> => mockApi.get('/stats').then(r => r.data),
  getActivity: (): Promise<ActivityEvent[]> => mockApi.get('/activity').then(r => r.data),
}

// ─── Mock fallback data (used when API is unavailable) ────────────────────────

export const MOCK_STATS: DashboardStats = {
  total_sources: 4,
  cdm_models: 7,
  dq_passing: 33,
  dq_total: 36,
  pipeline_runs_today: 12,
  pipeline_success_today: 11,
}

export const MOCK_ACTIVITY: ActivityEvent[] = [
  {
    id: '1',
    timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
    type: 'pipeline',
    title: 'ingest_pos_data completed',
    description: 'Processed 48,231 records from POS system',
    status: 'success',
  },
  {
    id: '2',
    timestamp: new Date(Date.now() - 18 * 60000).toISOString(),
    type: 'dq',
    title: 'DQ check: dim_customers',
    description: '2 tests failed — uniqueness violation on customer_id',
    status: 'failed',
  },
  {
    id: '3',
    timestamp: new Date(Date.now() - 32 * 60000).toISOString(),
    type: 'cdm',
    title: 'dbt run: fact_orders',
    description: 'Rebuilt 3 models, 1,204,871 rows',
    status: 'success',
  },
  {
    id: '4',
    timestamp: new Date(Date.now() - 55 * 60000).toISOString(),
    type: 'source',
    title: 'Source sync: retail_postgres',
    description: 'Schema change detected — new column added to orders',
    status: 'info',
  },
  {
    id: '5',
    timestamp: new Date(Date.now() - 80 * 60000).toISOString(),
    type: 'pipeline',
    title: 'transform_cdm_models completed',
    description: 'All 7 CDM models refreshed successfully',
    status: 'success',
  },
  {
    id: '6',
    timestamp: new Date(Date.now() - 120 * 60000).toISOString(),
    type: 'pipeline',
    title: 'ingest_inventory_data running',
    description: 'Syncing inventory from 3 warehouse locations',
    status: 'running',
  },
]

export const MOCK_PIPELINES: Pipeline[] = [
  {
    dag_id: 'ingest_pos_data',
    description: 'Ingests point-of-sale transaction data from retail_postgres source',
    schedule: '0 */6 * * *',
    is_active: true,
    last_run: {
      run_id: 'run_20240518_060000',
      dag_id: 'ingest_pos_data',
      state: 'success',
      start_date: new Date(Date.now() - 5 * 60000).toISOString(),
      end_date: new Date(Date.now() - 2 * 60000).toISOString(),
      duration: 180,
    },
    next_run: new Date(Date.now() + 3.5 * 3600000).toISOString(),
    tags: ['ingestion', 'pos'],
  },
  {
    dag_id: 'ingest_inventory_data',
    description: 'Syncs inventory levels from warehouse management system',
    schedule: '30 */4 * * *',
    is_active: true,
    last_run: {
      run_id: 'run_20240518_080000',
      dag_id: 'ingest_inventory_data',
      state: 'running',
      start_date: new Date(Date.now() - 12 * 60000).toISOString(),
      end_date: null,
      duration: null,
    },
    next_run: null,
    tags: ['ingestion', 'inventory'],
  },
  {
    dag_id: 'transform_cdm_models',
    description: 'Runs dbt transformations to build all CDM models from staging layer',
    schedule: '0 */2 * * *',
    is_active: true,
    last_run: {
      run_id: 'run_20240518_040000',
      dag_id: 'transform_cdm_models',
      state: 'success',
      start_date: new Date(Date.now() - 55 * 60000).toISOString(),
      end_date: new Date(Date.now() - 40 * 60000).toISOString(),
      duration: 900,
    },
    next_run: new Date(Date.now() + 65 * 60000).toISOString(),
    tags: ['dbt', 'cdm'],
  },
  {
    dag_id: 'run_dq_checks',
    description: 'Executes Great Expectations data quality checks across all CDM models',
    schedule: '15 */2 * * *',
    is_active: true,
    last_run: {
      run_id: 'run_20240518_021500',
      dag_id: 'run_dq_checks',
      state: 'failed',
      start_date: new Date(Date.now() - 90 * 60000).toISOString(),
      end_date: new Date(Date.now() - 85 * 60000).toISOString(),
      duration: 320,
    },
    next_run: new Date(Date.now() + 35 * 60000).toISOString(),
    tags: ['dq', 'quality'],
  },
  {
    dag_id: 'ingest_crm_data',
    description: 'Fetches customer data from CRM REST API',
    schedule: '0 8 * * *',
    is_active: true,
    last_run: {
      run_id: 'run_20240518_080000',
      dag_id: 'ingest_crm_data',
      state: 'success',
      start_date: new Date(Date.now() - 240 * 60000).toISOString(),
      end_date: new Date(Date.now() - 230 * 60000).toISOString(),
      duration: 610,
    },
    next_run: new Date(Date.now() + 16 * 3600000).toISOString(),
    tags: ['ingestion', 'crm'],
  },
  {
    dag_id: 'export_analytics_mart',
    description: 'Exports aggregated analytics data to BI reporting layer',
    schedule: '0 6 * * *',
    is_active: false,
    last_run: null,
    next_run: null,
    tags: ['export', 'analytics'],
  },
]

export const MOCK_SOURCES: DataSource[] = [
  {
    id: '1',
    name: 'retail_postgres',
    type: 'postgres',
    status: 'healthy',
    host: 'postgres',
    port: 5432,
    database: 'retail_db',
    description: 'Primary retail transactional database',
    table_count: 14,
    last_synced: new Date(Date.now() - 25 * 60000).toISOString(),
    created_at: new Date(Date.now() - 30 * 24 * 3600000).toISOString(),
  },
  {
    id: '2',
    name: 'minio_iceberg',
    type: 'iceberg',
    status: 'healthy',
    host: 'minio',
    port: 9000,
    database: 'warehouse',
    description: 'Iceberg data lakehouse on MinIO object storage',
    table_count: 7,
    last_synced: new Date(Date.now() - 45 * 60000).toISOString(),
    created_at: new Date(Date.now() - 25 * 24 * 3600000).toISOString(),
  },
  {
    id: '3',
    name: 'crm_api',
    type: 'api',
    status: 'healthy',
    host: 'api.crm.internal',
    port: 443,
    database: 'crm',
    description: 'REST API integration for customer relationship data',
    table_count: 3,
    last_synced: new Date(Date.now() - 4 * 3600000).toISOString(),
    created_at: new Date(Date.now() - 20 * 24 * 3600000).toISOString(),
  },
  {
    id: '4',
    name: 'inventory_mysql',
    type: 'mysql',
    status: 'error',
    host: 'mysql.warehouse.internal',
    port: 3306,
    database: 'inventory',
    description: 'Legacy inventory management system',
    table_count: 9,
    last_synced: new Date(Date.now() - 8 * 3600000).toISOString(),
    created_at: new Date(Date.now() - 15 * 24 * 3600000).toISOString(),
  },
]

export const MOCK_CDM_MODELS: CDMModel[] = [
  {
    name: 'dim_customers',
    schema: 'cdm',
    materialization: 'table',
    description: 'Customer dimension with SCD Type 2 history',
    row_count: 284_512,
    last_updated: new Date(Date.now() - 35 * 60000).toISOString(),
    tags: ['dimension', 'customer'],
    depends_on: ['stg_customers', 'stg_crm_accounts'],
    columns: [
      { name: 'customer_key', data_type: 'bigint', nullable: false, description: 'Surrogate key', dq_status: 'pass' },
      { name: 'customer_id', data_type: 'varchar(50)', nullable: false, description: 'Natural key from source', dq_status: 'fail' },
      { name: 'full_name', data_type: 'varchar(200)', nullable: true, description: 'Customer full name', dq_status: 'pass' },
      { name: 'email', data_type: 'varchar(254)', nullable: true, description: 'Primary email address', dq_status: 'pass' },
      { name: 'segment', data_type: 'varchar(50)', nullable: true, description: 'Customer segment classification', dq_status: 'pass' },
      { name: 'country_code', data_type: 'char(2)', nullable: true, description: 'ISO 3166-1 alpha-2', dq_status: 'pass' },
      { name: 'valid_from', data_type: 'timestamp', nullable: false, description: 'SCD valid from date', dq_status: 'pass' },
      { name: 'valid_to', data_type: 'timestamp', nullable: true, description: 'SCD valid to date (null = current)', dq_status: 'pass' },
      { name: 'is_current', data_type: 'boolean', nullable: false, description: 'Current record flag', dq_status: 'pass' },
    ],
  },
  {
    name: 'dim_products',
    schema: 'cdm',
    materialization: 'table',
    description: 'Product catalogue dimension',
    row_count: 18_743,
    last_updated: new Date(Date.now() - 35 * 60000).toISOString(),
    tags: ['dimension', 'product'],
    depends_on: ['stg_products'],
    columns: [
      { name: 'product_key', data_type: 'bigint', nullable: false, description: 'Surrogate key', dq_status: 'pass' },
      { name: 'product_id', data_type: 'varchar(50)', nullable: false, description: 'Source product SKU', dq_status: 'pass' },
      { name: 'product_name', data_type: 'varchar(300)', nullable: false, description: 'Product display name', dq_status: 'pass' },
      { name: 'category', data_type: 'varchar(100)', nullable: true, description: 'Top-level category', dq_status: 'pass' },
      { name: 'subcategory', data_type: 'varchar(100)', nullable: true, description: 'Sub-category', dq_status: 'pass' },
      { name: 'brand', data_type: 'varchar(100)', nullable: true, description: 'Product brand', dq_status: 'pass' },
      { name: 'unit_cost', data_type: 'numeric(12,4)', nullable: true, description: 'Cost price', dq_status: 'warn' },
      { name: 'unit_price', data_type: 'numeric(12,4)', nullable: false, description: 'Retail price', dq_status: 'pass' },
    ],
  },
  {
    name: 'dim_stores',
    schema: 'cdm',
    materialization: 'table',
    description: 'Store / location dimension',
    row_count: 312,
    last_updated: new Date(Date.now() - 35 * 60000).toISOString(),
    tags: ['dimension', 'store'],
    depends_on: ['stg_stores'],
    columns: [
      { name: 'store_key', data_type: 'bigint', nullable: false, description: 'Surrogate key', dq_status: 'pass' },
      { name: 'store_id', data_type: 'varchar(20)', nullable: false, description: 'Source store code', dq_status: 'pass' },
      { name: 'store_name', data_type: 'varchar(200)', nullable: false, description: 'Store display name', dq_status: 'pass' },
      { name: 'city', data_type: 'varchar(100)', nullable: true, dq_status: 'pass' },
      { name: 'state', data_type: 'varchar(100)', nullable: true, dq_status: 'pass' },
      { name: 'country_code', data_type: 'char(2)', nullable: true, dq_status: 'pass' },
      { name: 'store_type', data_type: 'varchar(50)', nullable: true, description: 'Physical / online / kiosk', dq_status: 'pass' },
      { name: 'opened_date', data_type: 'date', nullable: true, dq_status: 'pass' },
    ],
  },
  {
    name: 'dim_date',
    schema: 'cdm',
    materialization: 'table',
    description: 'Date dimension (2015–2030)',
    row_count: 5478,
    last_updated: new Date(Date.now() - 48 * 3600000).toISOString(),
    tags: ['dimension', 'time'],
    depends_on: [],
    columns: [
      { name: 'date_key', data_type: 'integer', nullable: false, description: 'YYYYMMDD integer key', dq_status: 'pass' },
      { name: 'full_date', data_type: 'date', nullable: false, dq_status: 'pass' },
      { name: 'year', data_type: 'smallint', nullable: false, dq_status: 'pass' },
      { name: 'quarter', data_type: 'smallint', nullable: false, dq_status: 'pass' },
      { name: 'month', data_type: 'smallint', nullable: false, dq_status: 'pass' },
      { name: 'week', data_type: 'smallint', nullable: false, dq_status: 'pass' },
      { name: 'day_of_week', data_type: 'smallint', nullable: false, dq_status: 'pass' },
      { name: 'is_weekend', data_type: 'boolean', nullable: false, dq_status: 'pass' },
      { name: 'is_holiday', data_type: 'boolean', nullable: false, dq_status: 'pass' },
    ],
  },
  {
    name: 'fact_orders',
    schema: 'cdm',
    materialization: 'incremental',
    description: 'Order line items fact table (grain: one row per order line)',
    row_count: 12_840_291,
    last_updated: new Date(Date.now() - 35 * 60000).toISOString(),
    tags: ['fact', 'orders'],
    depends_on: ['stg_orders', 'stg_order_lines', 'dim_customers', 'dim_products', 'dim_stores', 'dim_date'],
    columns: [
      { name: 'order_line_key', data_type: 'bigint', nullable: false, description: 'Surrogate key', dq_status: 'pass' },
      { name: 'order_id', data_type: 'varchar(50)', nullable: false, dq_status: 'pass' },
      { name: 'customer_key', data_type: 'bigint', nullable: false, description: 'FK → dim_customers', dq_status: 'pass' },
      { name: 'product_key', data_type: 'bigint', nullable: false, description: 'FK → dim_products', dq_status: 'pass' },
      { name: 'store_key', data_type: 'bigint', nullable: false, description: 'FK → dim_stores', dq_status: 'pass' },
      { name: 'date_key', data_type: 'integer', nullable: false, description: 'FK → dim_date', dq_status: 'pass' },
      { name: 'quantity', data_type: 'integer', nullable: false, dq_status: 'pass' },
      { name: 'unit_price', data_type: 'numeric(12,4)', nullable: false, dq_status: 'pass' },
      { name: 'discount_amount', data_type: 'numeric(12,4)', nullable: true, dq_status: 'pass' },
      { name: 'net_amount', data_type: 'numeric(12,4)', nullable: false, dq_status: 'pass' },
      { name: 'tax_amount', data_type: 'numeric(12,4)', nullable: true, dq_status: 'pass' },
      { name: 'order_status', data_type: 'varchar(30)', nullable: false, dq_status: 'pass' },
    ],
  },
  {
    name: 'fact_returns',
    schema: 'cdm',
    materialization: 'incremental',
    description: 'Product returns and refunds fact table',
    row_count: 284_019,
    last_updated: new Date(Date.now() - 35 * 60000).toISOString(),
    tags: ['fact', 'returns'],
    depends_on: ['stg_returns', 'dim_customers', 'dim_products', 'dim_stores', 'dim_date'],
    columns: [
      { name: 'return_key', data_type: 'bigint', nullable: false, dq_status: 'pass' },
      { name: 'return_id', data_type: 'varchar(50)', nullable: false, dq_status: 'pass' },
      { name: 'order_id', data_type: 'varchar(50)', nullable: true, description: 'Original order reference', dq_status: 'pass' },
      { name: 'customer_key', data_type: 'bigint', nullable: false, dq_status: 'pass' },
      { name: 'product_key', data_type: 'bigint', nullable: false, dq_status: 'pass' },
      { name: 'store_key', data_type: 'bigint', nullable: false, dq_status: 'pass' },
      { name: 'date_key', data_type: 'integer', nullable: false, dq_status: 'pass' },
      { name: 'quantity_returned', data_type: 'integer', nullable: false, dq_status: 'pass' },
      { name: 'refund_amount', data_type: 'numeric(12,4)', nullable: false, dq_status: 'pass' },
      { name: 'return_reason', data_type: 'varchar(100)', nullable: true, dq_status: 'pass' },
    ],
  },
  {
    name: 'fact_inventory',
    schema: 'cdm',
    materialization: 'incremental',
    description: 'Daily inventory snapshot per product per store',
    row_count: 5_831_488,
    last_updated: new Date(Date.now() - 120 * 60000).toISOString(),
    tags: ['fact', 'inventory'],
    depends_on: ['stg_inventory', 'dim_products', 'dim_stores', 'dim_date'],
    columns: [
      { name: 'inventory_key', data_type: 'bigint', nullable: false, dq_status: 'pass' },
      { name: 'product_key', data_type: 'bigint', nullable: false, dq_status: 'pass' },
      { name: 'store_key', data_type: 'bigint', nullable: false, dq_status: 'pass' },
      { name: 'date_key', data_type: 'integer', nullable: false, dq_status: 'pass' },
      { name: 'quantity_on_hand', data_type: 'integer', nullable: false, dq_status: 'pass' },
      { name: 'quantity_reserved', data_type: 'integer', nullable: true, dq_status: 'pass' },
      { name: 'reorder_point', data_type: 'integer', nullable: true, dq_status: 'pass' },
      { name: 'days_of_supply', data_type: 'numeric(8,2)', nullable: true, dq_status: 'warn' },
    ],
  },
]

export const MOCK_DQ_RESULTS: DQResult[] = [
  { id: '1', model: 'dim_customers', column_name: 'customer_id', test_type: 'unique', status: 'fail', failures: 142, warn_count: 0, execution_time: 2.3, last_run: new Date(Date.now() - 90 * 60000).toISOString(), message: '142 duplicate customer_id values found' },
  { id: '2', model: 'dim_customers', column_name: 'customer_key', test_type: 'not_null', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.8, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '3', model: 'dim_customers', column_name: 'email', test_type: 'not_null', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.9, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '4', model: 'dim_products', column_name: 'product_key', test_type: 'unique', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.4, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '5', model: 'dim_products', column_name: 'unit_cost', test_type: 'not_null', status: 'warn', failures: 0, warn_count: 28, execution_time: 0.6, last_run: new Date(Date.now() - 90 * 60000).toISOString(), message: '28 null unit_cost values (expected)' },
  { id: '6', model: 'dim_products', column_name: 'unit_price', test_type: 'not_null', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.5, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '7', model: 'fact_orders', column_name: 'customer_key', test_type: 'relationships', status: 'pass', failures: 0, warn_count: 0, execution_time: 4.1, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '8', model: 'fact_orders', column_name: 'product_key', test_type: 'relationships', status: 'pass', failures: 0, warn_count: 0, execution_time: 4.3, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '9', model: 'fact_orders', column_name: 'net_amount', test_type: 'not_null', status: 'pass', failures: 0, warn_count: 0, execution_time: 1.2, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '10', model: 'fact_orders', column_name: 'order_id', test_type: 'not_null', status: 'pass', failures: 0, warn_count: 0, execution_time: 1.1, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '11', model: 'fact_returns', column_name: 'return_id', test_type: 'unique', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.7, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '12', model: 'fact_returns', column_name: 'refund_amount', test_type: 'not_null', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.6, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '13', model: 'fact_inventory', column_name: 'quantity_on_hand', test_type: 'not_null', status: 'pass', failures: 0, warn_count: 0, execution_time: 2.1, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '14', model: 'fact_inventory', column_name: 'days_of_supply', test_type: 'not_null', status: 'warn', failures: 0, warn_count: 1243, execution_time: 2.3, last_run: new Date(Date.now() - 90 * 60000).toISOString(), message: '1,243 null days_of_supply (new stores)' },
  { id: '15', model: 'dim_stores', column_name: 'store_id', test_type: 'unique', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.2, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '16', model: 'dim_stores', column_name: 'store_name', test_type: 'not_null', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.2, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '17', model: 'dim_date', column_name: 'date_key', test_type: 'unique', status: 'pass', failures: 0, warn_count: 0, execution_time: 0.1, last_run: new Date(Date.now() - 90 * 60000).toISOString() },
  { id: '18', model: 'fact_orders', column_name: null, test_type: 'custom', status: 'fail', failures: 37, warn_count: 0, execution_time: 8.4, last_run: new Date(Date.now() - 90 * 60000).toISOString(), message: '37 orders with net_amount < 0 without return reference' },
]
