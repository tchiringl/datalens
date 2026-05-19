import { clsx } from 'clsx'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface KPICardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ComponentType<{ className?: string }>
  iconBg?: string
  iconColor?: string
  trend?: { value: number; label: string; positive: boolean }
}

export function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconBg = 'bg-blue-50',
  iconColor = 'text-blue-600',
  trend,
}: KPICardProps) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div className={clsx('rounded-xl p-3', iconBg)}>
          <Icon className={clsx('h-5 w-5', iconColor)} />
        </div>
        {trend && (
          <div
            className={clsx(
              'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
              trend.positive
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-red-50 text-red-600'
            )}
          >
            {trend.positive ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {trend.value}%
          </div>
        )}
      </div>

      <div>
        <p className="text-2xl font-bold text-slate-900 leading-none">{value}</p>
        <p className="mt-1 text-sm font-medium text-slate-500">{title}</p>
        {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        {trend && (
          <p className="mt-1 text-xs text-slate-400">{trend.label}</p>
        )}
      </div>
    </div>
  )
}
