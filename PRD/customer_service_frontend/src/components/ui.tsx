import type { ReactNode } from 'react'
import {
  AlertCircle,
  ChevronLeft,
  Inbox,
  Loader2,
  RefreshCw,
} from 'lucide-react'

export type Tone = 'blue' | 'green' | 'orange' | 'red' | 'gray' | 'navy'

export function StatusPill({
  label,
  tone = 'gray',
}: {
  label: string
  tone?: Tone
}) {
  return <span className={`status-pill tone-${tone}`}>{label}</span>
}

export function PriorityDot({ priority }: { priority: string }) {
  const tone = priority === 'P0' ? 'red' : priority === 'P1' ? 'orange' : 'blue'
  return (
    <span className={`priority priority-${tone}`}>
      <i />
      {priority}
    </span>
  )
}

export function Avatar({
  name,
  size = 'md',
  tone = 'blue',
}: {
  name: string
  size?: 'sm' | 'md' | 'lg'
  tone?: 'blue' | 'green' | 'navy'
}) {
  return (
    <span className={`avatar avatar-${size} avatar-${tone}`}>
      {name.slice(0, 1)}
    </span>
  )
}

export function PageHeader({
  title,
  subtitle,
  onBack,
  action,
}: {
  title: string
  subtitle?: string
  onBack?: () => void
  action?: ReactNode
}) {
  return (
    <header className="page-header">
      {onBack ? (
        <button className="icon-button" type="button" onClick={onBack} aria-label="返回">
          <ChevronLeft size={21} />
        </button>
      ) : (
        <span className="header-spacer" />
      )}
      <div className="page-header-title">
        <strong>{title}</strong>
        {subtitle ? <small>{subtitle}</small> : null}
      </div>
      <div className="page-header-action">{action}</div>
    </header>
  )
}

export function SectionTitle({
  title,
  action,
}: {
  title: string
  action?: ReactNode
}) {
  return (
    <div className="section-title">
      <h2>{title}</h2>
      {action}
    </div>
  )
}

export function LoadingBlock({ label = '加载中…' }: { label?: string }) {
  return (
    <div className="state-block">
      <Loader2 className="spin" size={22} />
      <span>{label}</span>
    </div>
  )
}

export function ErrorBlock({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div className="state-block state-error">
      <AlertCircle size={22} />
      <span>{message}</span>
      {onRetry ? (
        <button className="text-button" type="button" onClick={onRetry}>
          <RefreshCw size={14} /> 重试
        </button>
      ) : null}
    </div>
  )
}

export function EmptyBlock({
  title = '暂无内容',
  description,
  action,
}: {
  title?: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="state-block state-empty">
      <Inbox size={24} />
      <strong>{title}</strong>
      {description ? <span>{description}</span> : null}
      {action}
    </div>
  )
}
