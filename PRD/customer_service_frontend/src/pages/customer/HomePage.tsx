import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  ChevronRight,
  Headphones,
  MessageCircle,
  Package,
  ShieldCheck,
  Tablet,
  Truck,
  Wrench,
} from 'lucide-react'
import { api } from '../../api/client'
import type { Device, Order, Repair } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import {
  faultLabel,
  isRepairOpen,
  orderTone,
  repairTone,
  warrantyLabel,
  warrantyTone,
  formatDate,
  formatMoney,
  ORDER_STATUS_LABELS,
  REPAIR_STATUS_LABELS,
} from '../../utils/format'
import { EmptyBlock, ErrorBlock, LoadingBlock, SectionTitle, StatusPill } from '../../components/ui'

interface HomeData {
  orders: Order[]
  devices: Device[]
  repairs: Repair[]
  mode: string
}

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

export function HomePage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const token = session?.token ?? ''
  const name = session?.profile.name ?? '家长'

  const { data, loading, error, reload } = useAsync<HomeData>(async () => {
    const [orders, devices, repairs, conversation] = await Promise.all([
      api.orders(token),
      api.devices(token),
      api.repairs(token),
      api.currentConversation(token),
    ])
    return {
      orders: orders.items,
      devices: devices.items,
      repairs: repairs.items,
      mode: conversation.mode,
    }
  }, [token])

  const latestOrder = data?.orders[0] ?? null
  const openRepairs = useMemo(
    () => (data?.repairs ?? []).filter((repair) => isRepairOpen(repair.status)),
    [data],
  )
  const activeRepair = openRepairs[0] ?? null
  const shippingOrder = data?.orders.find((order) => order.status === 'shipped') ?? null

  const mode = data?.mode ?? 'AI'
  const serviceCopy = (() => {
    if (mode === 'QUEUED') {
      return {
        title: '正在为您转接人工',
        text: '已进入人工队列，请稍候，接入后可直接在这里沟通。',
        cta: '查看排队进度',
      }
    }
    if (mode === 'HUMAN') {
      return {
        title: '人工客服正在服务',
        text: '坐席已接入，您可以继续补充问题或上传相关信息。',
        cta: '继续会话',
      }
    }
    if (mode === 'REPAIR') {
      return {
        title: '报修流程进行中',
        text: '正在收集设备与故障信息，确认后会生成维修工单。',
        cta: '继续报修',
      }
    }
    if (mode === 'CLOSED') {
      return {
        title: '本次会话已结束',
        text: '如需帮助，可以随时开启一段新的咨询。',
        cta: '重新咨询',
      }
    }
    return {
      title: 'AI 客服在线，随时解答',
      text: '订单、物流、保修、报修，一句话就能查。',
      cta: '开始咨询',
    }
  })()

  function openChat(params?: Record<string, string>) {
    const query = params ? `?${new URLSearchParams(params).toString()}` : ''
    navigate(`/app/chat${query}`)
  }

  if (loading && !data) return <LoadingBlock label="正在加载首页…" />
  if (error && !data) return <ErrorBlock message={error} onRetry={() => void reload()} />

  return (
    <div className="screen home-screen">
      <header className="home-head">
        <div>
          <p className="eyebrow">{greeting()}，欢迎回来</p>
          <h1>{name}，今天想了解什么？</h1>
        </div>
        <button
          type="button"
          className="avatar avatar-md avatar-blue avatar-button"
          onClick={() => navigate('/app/profile')}
          aria-label="个人中心"
        >
          {name.slice(0, 1)}
        </button>
      </header>

      <section className={`service-card mode-${mode.toLowerCase()}`}>
        <Headphones className="service-watermark" size={116} aria-hidden />
        <div className="service-status">
          <span className="live-dot" />
          {mode === 'HUMAN' ? '人工坐席在线' : mode === 'QUEUED' ? '排队中' : 'AI 客服 · 7×24'}
        </div>
        <h2>{serviceCopy.title}</h2>
        <p>{serviceCopy.text}</p>
        <button type="button" className="service-cta" onClick={() => openChat()}>
          {serviceCopy.cta}
          <ArrowRight size={16} />
        </button>
      </section>

      <div className="quick-grid">
        <button
          type="button"
          className="quick-item"
          onClick={() => navigate('/app/orders')}
        >
          <span className="quick-icon tone-blue">
            <Package size={20} />
          </span>
          <strong>查订单</strong>
          <small>{data?.orders.length ?? 0} 笔订单</small>
        </button>
        <button
          type="button"
          className="quick-item"
          onClick={() =>
            shippingOrder
              ? navigate(`/app/orders/${shippingOrder.order_no}`)
              : navigate('/app/orders')
          }
        >
          <span className="quick-icon tone-green">
            <Truck size={20} />
          </span>
          <strong>查物流</strong>
          <small>{shippingOrder ? '有包裹在途' : '查看订单进度'}</small>
        </button>
        <button
          type="button"
          className="quick-item"
          onClick={() => openChat({ intent: 'repair' })}
        >
          <span className="quick-icon tone-orange">
            <Wrench size={20} />
          </span>
          <strong>设备报修</strong>
          <small>{openRepairs.length ? `${openRepairs.length} 单处理中` : '智能受理'}</small>
        </button>
        <button
          type="button"
          className="quick-item"
          onClick={() => navigate('/app/devices')}
        >
          <span className="quick-icon tone-navy">
            <ShieldCheck size={20} />
          </span>
          <strong>保修查询</strong>
          <small>{data?.devices.length ?? 0} 台设备</small>
        </button>
      </div>

      <section className="home-section">
        <SectionTitle
          title="我的设备"
          action={
            <button
              type="button"
              className="link-button"
              onClick={() => navigate('/app/devices')}
            >
              全部 <ChevronRight size={14} />
            </button>
          }
        />
        {data?.devices.length ? (
          <div className="device-scroll">
            {data.devices.slice(0, 3).map((device) => (
              <button
                key={device.sn}
                type="button"
                className="device-mini"
                onClick={() => navigate('/app/devices')}
              >
                <span className="device-mini-icon">
                  <Tablet size={22} />
                </span>
                <div className="device-mini-body">
                  <strong>{device.model}</strong>
                  <small>SN {device.sn}</small>
                </div>
                <StatusPill
                  label={warrantyLabel(device.warranty_status)}
                  tone={warrantyTone(device.warranty_status)}
                />
              </button>
            ))}
          </div>
        ) : (
          <EmptyBlock title="还没有绑定设备" description="购买学习机后会自动出现在这里" />
        )}
      </section>

      <section className="home-section">
        <SectionTitle
          title="最近订单"
          action={
            <button
              type="button"
              className="link-button"
              onClick={() => navigate('/app/orders')}
            >
              全部 <ChevronRight size={14} />
            </button>
          }
        />
        {latestOrder ? (
          <button
            type="button"
            className="order-card compact"
            onClick={() => navigate(`/app/orders/${latestOrder.order_no}`)}
          >
            <div className="order-card-head">
              <span className="order-no">{latestOrder.order_no}</span>
              <StatusPill
                label={latestOrder.status_label ?? ORDER_STATUS_LABELS[latestOrder.status]}
                tone={orderTone(latestOrder.status)}
              />
            </div>
            <div className="order-card-main">
              <span className="order-thumb">
                <Tablet size={21} />
              </span>
              <div className="order-main-copy">
                <strong>
                  {latestOrder.items.map((item) => item.product_name).join('、') || '学习机订单'}
                </strong>
                <small>
                  {formatDate(latestOrder.created_at)} · 共{' '}
                  {latestOrder.items.reduce((sum, item) => sum + item.quantity, 0)} 件
                </small>
              </div>
              <span className="order-amount">{formatMoney(latestOrder.total_amount)}</span>
            </div>
          </button>
        ) : (
          <EmptyBlock title="暂无订单" />
        )}
      </section>

      <section className="home-section last">
        <SectionTitle
          title="售后服务"
          action={
            <button
              type="button"
              className="link-button"
              onClick={() => navigate('/app/repairs')}
            >
              维修记录 <ChevronRight size={14} />
            </button>
          }
        />
        {activeRepair ? (
          <button
            type="button"
            className="repair-card"
            onClick={() => navigate(`/app/repairs/${activeRepair.repair_no}`)}
          >
            <div className="repair-card-head">
              <span className="repair-no">
                <Wrench size={14} /> {activeRepair.repair_no}
              </span>
              <StatusPill
                label={REPAIR_STATUS_LABELS[activeRepair.status]}
                tone={repairTone(activeRepair.status)}
              />
            </div>
            <strong>{faultLabel(activeRepair.fault_type)}</strong>
            <p>{activeRepair.description}</p>
            <small>
              设备 SN {activeRepair.device_sn} · 更新于 {formatDate(activeRepair.updated_at)}
            </small>
          </button>
        ) : (
          <button
            type="button"
            className="support-strip"
            onClick={() => openChat({ intent: 'repair' })}
          >
            <span className="support-strip-icon">
              <MessageCircle size={19} />
            </span>
            <span>
              <strong>设备遇到问题？</strong>
              <small>告诉 AI 客服，帮你判断并登记报修</small>
            </span>
            <ChevronRight size={17} />
          </button>
        )}
      </section>
    </div>
  )
}
