import { useNavigate, useParams } from 'react-router-dom'
import {
  CalendarDays,
  Headphones,
  ShieldCheck,
  Tablet,
  Wrench,
} from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import {
  REPAIR_MODE_LABELS,
  REPAIR_STATUS_LABELS,
  faultLabel,
  formatDateTimeLong,
  formatMoney,
  repairTone,
  warrantyLabel,
  warrantyTone,
} from '../../utils/format'
import {
  ErrorBlock,
  LoadingBlock,
  PageHeader,
  StatusPill,
} from '../../components/ui'

export function RepairDetailPage() {
  const { repairNo = '' } = useParams()
  const navigate = useNavigate()
  const { session } = useAuth()
  const token = session?.token ?? ''
  const { data, loading, error, reload } = useAsync(
    () => api.repair(token, repairNo),
    [token, repairNo],
  )

  if (loading && !data) return <LoadingBlock label="正在加载维修工单…" />
  if (error && !data) {
    return (
      <div className="screen page-screen">
        <PageHeader title="维修详情" onBack={() => navigate(-1)} />
        <ErrorBlock message={error} onRetry={() => void reload()} />
      </div>
    )
  }
  if (!data) return null

  const events = [...data.events].reverse()

  return (
    <div className="screen page-screen detail-screen">
      <PageHeader
        title="维修详情"
        subtitle={data.repair_no}
        onBack={() => navigate(-1)}
      />

      <section className={`detail-hero repair-hero status-${data.status}`}>
        <div className="detail-hero-top">
          <div>
            <span className="detail-hero-label">当前进度</span>
            <h2>{data.status_label ?? REPAIR_STATUS_LABELS[data.status]}</h2>
          </div>
          <StatusPill
            label={data.status_label ?? REPAIR_STATUS_LABELS[data.status]}
            tone={repairTone(data.status)}
          />
        </div>
        <p>{faultLabel(data.fault_type)}</p>
        <div className="detail-hero-meta">
          <span>设备 SN {data.device_sn}</span>
          <span>{REPAIR_MODE_LABELS[data.mode] ?? data.mode}</span>
        </div>
      </section>

      {data.warranty_status === 'out_of_warranty' && data.quote_amount ? (
        <div className="quote-strip">
          <span>维修报价</span>
          <strong>{formatMoney(data.quote_amount)}</strong>
        </div>
      ) : null}

      <section className="card detail-card">
        <div className="card-heading">
          <Wrench size={17} />
          <h3>故障描述</h3>
        </div>
        <p className="detail-paragraph">{data.description}</p>
      </section>

      <section className="card detail-card">
        <div className="card-heading">
          <CalendarDays size={17} />
          <h3>处理进度</h3>
        </div>
        {events.length ? (
          <ol className="timeline">
            {events.map((event, index) => (
              <li key={`${event.created_at}-${index}`} className={index === 0 ? 'current' : ''}>
                <span className="timeline-dot" />
                <div className="timeline-body">
                  <strong>
                    {REPAIR_STATUS_LABELS[
                      event.to_status as keyof typeof REPAIR_STATUS_LABELS
                    ] ?? event.to_status}
                  </strong>
                  {event.note ? <p>{event.note}</p> : null}
                  <small>{formatDateTimeLong(event.created_at)}</small>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted-line">暂无处理记录。</p>
        )}
      </section>

      <section className="card detail-card">
        <div className="card-heading">
          <Tablet size={17} />
          <h3>工单信息</h3>
        </div>
        <dl className="info-list">
          <div>
            <dt>设备序列号</dt>
            <dd className="mono">{data.device_sn}</dd>
          </div>
          <div>
            <dt>维修方式</dt>
            <dd>{REPAIR_MODE_LABELS[data.mode] ?? data.mode}</dd>
          </div>
          <div>
            <dt>保修状态</dt>
            <dd>
              {data.warranty_status ? (
                <StatusPill
                  label={
                    data.warranty_status_label ?? warrantyLabel(data.warranty_status)
                  }
                  tone={warrantyTone(data.warranty_status)}
                />
              ) : (
                '—'
              )}
            </dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{formatDateTimeLong(data.created_at)}</dd>
          </div>
          <div>
            <dt>最近更新</dt>
            <dd>{formatDateTimeLong(data.updated_at)}</dd>
          </div>
          {data.closed_at ? (
            <div>
              <dt>完成时间</dt>
              <dd>{formatDateTimeLong(data.closed_at)}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <div className="detail-note">
        <ShieldCheck size={15} />
        维修进度由服务网点更新，如需补充信息可直接联系客服。
      </div>

      <div className="sticky-actions">
        <button
          type="button"
          className="secondary-button"
          onClick={() => navigate('/app/repairs')}
        >
          全部工单
        </button>
        <button
          type="button"
          className="primary-button"
          onClick={() =>
            navigate(
              `/app/chat?${new URLSearchParams({ intent: 'repair_progress', repair_no: data.repair_no }).toString()}`,
            )
          }
        >
          <Headphones size={16} /> 咨询进度
        </button>
      </div>
    </div>
  )
}
