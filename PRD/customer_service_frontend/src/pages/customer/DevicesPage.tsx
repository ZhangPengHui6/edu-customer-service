import { useNavigate } from 'react-router-dom'
import { RefreshCw, ShieldCheck, Tablet, Wrench } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, warrantyLabel, warrantyTone } from '../../utils/format'
import {
  EmptyBlock,
  ErrorBlock,
  LoadingBlock,
  PageHeader,
  StatusPill,
} from '../../components/ui'

export function DevicesPage() {
  const navigate = useNavigate()
  const { session } = useAuth()
  const token = session?.token ?? ''
  const { data, loading, error, reload } = useAsync(
    () => api.devices(token),
    [token],
  )
  const items = data?.items ?? []

  return (
    <div className="screen page-screen">
      <PageHeader
        title="我的设备"
        subtitle={items.length ? `已绑定 ${items.length} 台` : undefined}
        action={
          <button
            className="icon-button"
            type="button"
            onClick={() => void reload()}
            aria-label="刷新"
          >
            <RefreshCw size={18} />
          </button>
        }
      />

      {loading && !data ? <LoadingBlock /> : null}
      {error && !data ? <ErrorBlock message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        items.length ? (
          <div className="card-list">
            {items.map((device) => (
              <article className="card device-card" key={device.sn}>
                <header className="device-card-head">
                  <span className="device-avatar">
                    <Tablet size={25} />
                  </span>
                  <div className="device-title">
                    <strong>{device.model}</strong>
                    <small className="mono">SN {device.sn}</small>
                  </div>
                  <StatusPill
                    label={device.warranty_status_label ?? warrantyLabel(device.warranty_status)}
                    tone={warrantyTone(device.warranty_status)}
                  />
                </header>

                <dl className="device-meta">
                  <div>
                    <dt>激活时间</dt>
                    <dd>{formatDate(device.activation_at)}</dd>
                  </div>
                  <div>
                    <dt>固件版本</dt>
                    <dd>{device.firmware_version || '—'}</dd>
                  </div>
                  <div>
                    <dt>保修截止</dt>
                    <dd>{formatDate(device.warranty_end_at)}</dd>
                  </div>
                </dl>

                {device.warranty_status === 'out_of_warranty' ? (
                  <div className="inline-note orange">
                    <ShieldCheck size={15} />
                    该设备已过保修期，维修可能产生费用，客服会先与您确认报价。
                  </div>
                ) : null}

                <div className="device-actions">
                  <button
                    type="button"
                    className="secondary-button small"
                    onClick={() =>
                      navigate(
                        `/app/chat?${new URLSearchParams({ intent: 'device', sn: device.sn }).toString()}`,
                      )
                    }
                  >
                    咨询保修
                  </button>
                  <button
                    type="button"
                    className="primary-button small"
                    onClick={() =>
                      navigate(
                        `/app/chat?${new URLSearchParams({ intent: 'repair', sn: device.sn }).toString()}`,
                      )
                    }
                  >
                    <Wrench size={15} /> 申请报修
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyBlock
            title="还没有绑定设备"
            description="设备绑定时填写的信息需要与订单一致，如有疑问可联系客服"
            action={
              <button
                type="button"
                className="primary-button small"
                onClick={() => navigate('/app/chat')}
              >
                联系客服
              </button>
            }
          />
        )
      ) : null}
    </div>
  )
}
