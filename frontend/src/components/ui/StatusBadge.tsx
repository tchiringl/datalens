import { clsx } from 'clsx'

export type Status = 'success' | 'failed' | 'running' | 'queued' | 'warning' | 'unknown' | 'pass' | 'fail' | 'warn' | 'error'

interface StatusBadgeProps {
  status: Status
  size?: 'sm' | 'md'
}

const CONFIG: Record<Status, { label: string; classes: string; dotClasses: string; animate?: boolean }> = {
  success: {
    label: 'Success',
    classes: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dotClasses: 'bg-emerald-500',
  },
  pass: {
    label: 'Pass',
    classes: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dotClasses: 'bg-emerald-500',
  },
  failed: {
    label: 'Failed',
    classes: 'bg-red-50 text-red-700 border-red-200',
    dotClasses: 'bg-red-500',
  },
  fail: {
    label: 'Fail',
    classes: 'bg-red-50 text-red-700 border-red-200',
    dotClasses: 'bg-red-500',
  },
  error: {
    label: 'Error',
    classes: 'bg-red-50 text-red-700 border-red-200',
    dotClasses: 'bg-red-500',
  },
  running: {
    label: 'Running',
    classes: 'bg-blue-50 text-blue-700 border-blue-200',
    dotClasses: 'bg-blue-500',
    animate: true,
  },
  queued: {
    label: 'Queued',
    classes: 'bg-amber-50 text-amber-700 border-amber-200',
    dotClasses: 'bg-amber-400',
  },
  warning: {
    label: 'Warning',
    classes: 'bg-amber-50 text-amber-700 border-amber-200',
    dotClasses: 'bg-amber-400',
  },
  warn: {
    label: 'Warn',
    classes: 'bg-amber-50 text-amber-700 border-amber-200',
    dotClasses: 'bg-amber-400',
  },
  unknown: {
    label: 'Unknown',
    classes: 'bg-slate-50 text-slate-500 border-slate-200',
    dotClasses: 'bg-slate-400',
  },
}

export function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const cfg = CONFIG[status] ?? CONFIG.unknown

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs',
        cfg.classes
      )}
    >
      <span
        className={clsx(
          'rounded-full',
          size === 'sm' ? 'h-1.5 w-1.5' : 'h-2 w-2',
          cfg.dotClasses,
          cfg.animate && 'animate-pulse'
        )}
      />
      {cfg.label}
    </span>
  )
}
