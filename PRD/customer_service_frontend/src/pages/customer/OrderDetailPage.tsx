import { useNavigate, useParams } from 'react-router-dom'
import {
  Headphones,
  MapPin,
  PackageCheck,
  ShieldCheck,
  Tablet,
  Truck,
} from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import {
  ORDER_STATUS_LABELS,
  ORDER_STEPS,
  formatDateTime,
  formatDateTimeLong,
  formatMoney,
  orderStepIndex,
  orderTone,
} from '../../utils/format'
import {
  ErrorBlock,
  LoadingBlock,
  PageHeader,
  StatusPill,
} from '../../components/ui'

export function OrderDetailPage() {
  const { orderNo = '' } = useParams()
  const navigate = useNavigate()
  const { session } = useAuth()
  const token = session?.token ?? ''
  const { data, loading, error, reload } = useAsync(
    () => api.order(token, orderNo),
    [token, orderNo],
  )

  const stepIndex = data ? orderStepIndex(data.status) : -1
  const logistics = data ? [...data.logistics].reverse() : []

  if (loading && !data) return <LoadingBlock label="正在加载订单…" />
  if (error && !data) {
    return (
      <div className="screen page-screen">
        <PageHeader title="订单详情" onBack={() => navigate(-1)} />
        <ErrorBlock message={error} onRetry={() => void reload()} />
      </div>
    )
  }
  if (!data) return null

  return (
    <div className="screen page-screen detail-screen">
      <PageHeader
        title="订单详情"
        subtitle={data.order_no}
        onBack={() => navigate(-1)}
      />

      <section
        className={`detail-hero ${data.status === 'cancelled' ? 'is-cancelled' : ''}`}
      >
        <div className="detail-hero-top">
          <div>
            <span className="detail-hero-label">订单状态</span>
            <h2>{data.status_label ?? ORDER_STATUS_LABELS[data.status]}</h2>
          </div>
          <StatusPill
            label={data.status_label ?? ORDER_STATUS_LABELS[data.status]}
            tone={orderTone(data.status)}
          />
        </div>
        <div className="detail-hero-meta">
          <span>下单时间 {formatDateTimeLong(data.created_at)}</span>
          <span className="detail-hero-amount">{formatMoney(data.total_amount)}</span>
        </div>
      </section>

      {data.status === 'cancelled' ? (
        <div className="notice-strip">
          订单已取消
          {data.cancelled_at ? ` · ${formatDateTimeLong(data.cancelled_at)}` : ''}
          ，退款将按原支付方式退回。
        </div>
      ) : data.status === 'pending' ? (
        <div className="notice-strip">订单待付款，如需帮助可联系客服。</div>
      ) : (
        <div className="order-steps card">
          <div className="steps-track">
            {ORDER_STEPS.map((step, index) => {
              const done = index <= stepIndex
              return (
                <div className={`step ${done ? 'done' : ''}`} key={step}>
                  <span className="step-dot">
                    {index === 3 && done ? <PackageCheck size={13} /> : null}
                  </span>
                  <small>{step}</small>
                </div>
              )
            })}
          </div>
          {data.shipped_at ? (
            <p className="steps-caption">发货时间 {formatDateTime(data.shipped_at)}</p>
          ) : null}
        </div>
      )}

      <section className="card detail-card">
        <div className="card-heading">
          <Tablet size={17} />
          <h3>商品信息</h3>
        </div>
        <div className="detail-items">
          {data.items.map((item, index) => (
            <div className="detail-item" key={`${item.product_model}-${index}`}>
              <span className="order-thumb large">
                <Tablet size={24} />
              </span>
              <div>
                <strong>{item.product_name}</strong>
                <small>
                  {item.product_model} · × {item.quantity}
                </small>
              </div>
              <span>{formatMoney(item.amount)}</span>
            </div>
          ))}
        </div>
        <div className="detail-total">
          <span>实付金额</span>
          <strong>{formatMoney(data.total_amount)}</strong>
        </div>
      </section>

      <section className="card detail-card">
        <div className="card-heading">
          <Truck size={17} />
          <h3>物流信息</h3>
        </div>
        {logistics.length ? (
          <ol className="timeline">
            {logistics.map((event, index) => (
              <li key={`${event.occurred_at}-${index}`} className={index === 0 ? 'current' : ''}>
                <span className="timeline-dot" />
                <div className="timeline-body">
                  <strong>{event.description}</strong>
                  <small>{formatDateTimeLong(event.occurred_at)}</small>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted-line">暂无物流轨迹，发货后会在这里更新。</p>
        )}
      </section>

      <section className="card detail-card">
        <div className="card-heading">
          <MapPin size={17} />
          <h3>收货信息</h3>
        </div>
        <dl className="info-list">
          <div>
            <dt>收货人</dt>
            <dd>{data.recipient_masked || '—'}</dd>
          </div>
          <div>
            <dt>收货地址</dt>
            <dd>{data.address_masked || '—'}</dd>
          </div>
          <div>
            <dt>订单编号</dt>
            <dd className="mono">{data.order_no}</dd>
          </div>
        </dl>
      </section>

      <div className="detail-note">
        <ShieldCheck size={15} />
        保修权益与设备绑定可在「我的设备」查看。
      </div>

      <div className="sticky-actions">
        <button
          type="button"
          className="secondary-button"
          onClick={() => navigate('/app/devices')}
        >
          <ShieldCheck size={16} /> 我的设备
        </button>
        <button
          type="button"
          className="primary-button"
          onClick={() =>
            navigate(
              `/app/chat?${new URLSearchParams({ intent: 'order', order_no: data.order_no }).toString()}`,
            )
          }
        >
          <Headphones size={16} /> 联系客服
        </button>
      </div>
    </div>
  )
}
