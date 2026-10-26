import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Plus, Wrench } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import {
  REPAIR_MODE_LABELS,
  REPAIR_STATUS_LABELS,
  faultLabel,
  formatDate,
  isRepairOpen,
  repairTone,
  warrantyLabel,
  warrantyTone,
} from '../../utils/format'
import {
  EmptyBlock,
  ErrorBlock,
  LoadingBlock,
  PageHeader,
  StatusPill,
} from '../../components/ui'

type RepairFilter = 'all' | 'open' | 'done'

const FILTERS: { key: RepairFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'open', label: '进行中' },
  { key: 'done', label: '已结束' },
]

export function RepairsPage() {
  const navigate = useNavigate()
  const { session } = useAuth()
  const token = session?.token ?? ''
  const [filter, setFilter] = useState<RepairFilter>('all')
  const { data, loading, error, reload } = useAsync(
    () => api.repairs(token),
    [token],
  )

  const items = data?.items ?? []
  const filtered = useMemo(() => {
    if (filter === 'all') return items
    if (filter === 'open') return items.filter((item) => isRepairOpen(item.status))
    return items.filter((item) => !isRepairOpen(item.status))
  }, [items, filter])
  const openCount = items.filter((item) => isRepairOpen(item.status)).length

  return (
    <div className="screen page-screen">
      <PageHeader
        title="维修工单"
        subtitle={items.length ? `${openCount} 单进行中` : undefined}
        onBack={() => navigate(-1)}
        action={
          <button
            className="icon-button"
            type="button"
            onClick={() => navigate('/app/chat?intent=repair')}
            aria-label="发起报修"
          >
            <Plus size={20} />
          </button>
        }
      />

      <button
        type="button"
        className="repair-banner"
        onClick={() => navigate('/app/chat?intent=repair')}
      >
        <span className="repair-banner-icon">
          <Wrench size={21} />
        </span>
        <span>
          <strong>设备出现问题？</strong>
          <small>描述故障现象，AI 客服帮您判断并登记报修</small>
        </span>
        <ChevronRight size={17} />
      </button>

      <div className="filter-row">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`filter-chip ${filter === item.key ? 'active' : ''}`}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading && !data ? <LoadingBlock /> : null}
      {error && !data ? <ErrorBlock message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        filtered.length ? (
          <div className="card-list">
            {filtered.map((repair) => (
              <button
                key={repair.repair_no}
                type="button"
                className="repair-card"
                onClick={() => navigate(`/app/repairs/${repair.repair_no}`)}
              >
                <div className="repair-card-head">
                  <span className="repair-no">
                    <Wrench size={14} /> {repair.repair_no}
                  </span>
                  <StatusPill
                    label={repair.status_label ?? REPAIR_STATUS_LABELS[repair.status]}
                    tone={repairTone(repair.status)}
                  />
                </div>
                <strong>{faultLabel(repair.fault_type)}</strong>
                <p>{repair.description}</p>
                <div className="repair-card-meta">
                  <span>SN {repair.device_sn}</span>
                  <span>{REPAIR_MODE_LABELS[repair.mode] ?? repair.mode}</span>
                  {repair.warranty_status ? (
                    <StatusPill
                      label={warrantyLabel(repair.warranty_status)}
                      tone={warrantyTone(repair.warranty_status)}
                    />
                  ) : null}
                </div>
                <div className="repair-card-foot">
                  <small>更新于 {formatDate(repair.updated_at)}</small>
                  <span>
                    查看进度 <ChevronRight size={14} />
                  </span>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <EmptyBlock
            title={items.length ? '该分类下暂无工单' : '暂无维修工单'}
            description={items.length ? undefined : '设备出现故障时，可以随时发起报修'}
            action={
              items.length ? undefined : (
                <button
                  type="button"
                  className="primary-button small"
                  onClick={() => navigate('/app/chat?intent=repair')}
                >
                  发起报修
                </button>
              )
            }
          />
        )
      ) : null}
    </div>
  )
}
