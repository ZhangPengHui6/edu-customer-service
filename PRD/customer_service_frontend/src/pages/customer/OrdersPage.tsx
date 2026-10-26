import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, RefreshCw, Tablet } from 'lucide-react'
import { api } from '../../api/client'
import type { OrderStatus } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import { ORDER_STATUS_LABELS, formatDate, formatMoney, orderTone } from '../../utils/format'
import {
  EmptyBlock,
  ErrorBlock,
  LoadingBlock,
  PageHeader,
  StatusPill,
} from '../../components/ui'

const FILTERS: { key: OrderStatus | 'all'; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待付款' },
  { key: 'paid', label: '待发货' },
  { key: 'shipped', label: '运输中' },
  { key: 'delivered', label: '已签收' },
  { key: 'after_sale', label: '售后中' },
  { key: 'cancelled', label: '已取消' },
]

export function OrdersPage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const token = session?.token ?? ''
  const [filter, setFilter] = useState<OrderStatus | 'all'>('all')
  const { data, loading, error, reload } = useAsync(
    () => api.orders(token),
    [token],
  )

  const items = data?.items ?? []
  const filtered = useMemo(
    () => (filter === 'all' ? items : items.filter((order) => order.status === filter)),
    [items, filter],
  )

  return (
    <div className="screen page-screen">
      <PageHeader
        title="我的订单"
        subtitle={items.length ? `共 ${items.length} 笔订单` : undefined}
        action={
          <button className="icon-button" type="button" onClick={() => void reload()} aria-label="刷新">
            <RefreshCw size={18} />
          </button>
        }
      />

      <div className="filter-row filter-grid">
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
          <div className="card-list order-list">
            {filtered.map((order) => (
              <button
                key={order.order_no}
                type="button"
                className="order-card"
                onClick={() => navigate(`/app/orders/${order.order_no}`)}
              >
                <div className="order-card-head">
                  <span className="order-no">{order.order_no}</span>
                  <StatusPill
                    label={order.status_label ?? ORDER_STATUS_LABELS[order.status]}
                    tone={orderTone(order.status)}
                  />
                </div>
                <div className="order-card-main">
                  <span className="order-thumb">
                    <Tablet size={22} />
                  </span>
                  <div className="order-main-copy">
                    <strong>
                      {order.items.map((item) => item.product_name).join('、') || '学习机订单'}
                    </strong>
                    <small>
                      {formatDate(order.created_at)} · 共{' '}
                      {order.items.reduce((sum, item) => sum + item.quantity, 0)} 件
                    </small>
                  </div>
                  <span className="order-amount">{formatMoney(order.total_amount)}</span>
                </div>
                <div className="order-card-foot">
                  <span>查看订单详情</span>
                  <ChevronRight size={15} />
                </div>
              </button>
            ))}
          </div>
        ) : (
          <EmptyBlock
            title={filter === 'all' ? '暂无订单' : '该状态下没有订单'}
            description={filter === 'all' ? '下单后可以在这里查看物流和售后进度' : undefined}
          />
        )
      ) : null}
    </div>
  )
}
