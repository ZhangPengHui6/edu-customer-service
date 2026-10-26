import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertCircle,
  BookOpen,
  Clock3,
  Headphones,
  Inbox,
  Loader2,
  LogOut,
  MessageSquare,
  Package,
  Phone,
  RefreshCw,
  Send,
  Sparkles,
  Tablet,
  Wrench,
  X,
} from 'lucide-react'
import { api } from '../../api/client'
import type { ChatMessage, Handoff, StaffHandoffContext } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { usePolling } from '../../hooks/useAsync'
import {
  HANDOFF_STATUS_LABELS,
  ORDER_STATUS_LABELS,
  REPAIR_MODE_LABELS,
  REPAIR_STATUS_LABELS,
  elapsedText,
  faultLabel,
  formatDate,
  formatMoney,
  formatTime,
  handoffTone,
  messageText,
  orderTone,
  repairTone,
  slaInfo,
  warrantyLabel,
  warrantyTone,
} from '../../utils/format'
import { PriorityDot, StatusPill } from '../../components/ui'

type QueueFilter = 'all' | 'waiting' | 'active'
type ContextTab = 'overview' | 'orders' | 'devices' | 'repairs'

const QUICK_REPLIES = [
  '稍后给您回电',
  '已为您登记，请保持电话畅通',
  '我正在帮您核实，请稍等',
  '已提交售后处理，请留意进度',
]

function mergeHandoff(previous: Handoff, next: Handoff): Handoff {
  return {
    ...previous,
    ...next,
    customer_name: next.customer_name ?? previous.customer_name,
    customer_phone_masked:
      next.customer_phone_masked ?? previous.customer_phone_masked,
    sla_due_at: next.sla_due_at ?? previous.sla_due_at,
  }
}

export function StaffPage() {
  const { session, logout } = useAuth()
  const navigate = useNavigate()
  const { handoffId } = useParams<{ handoffId: string }>()
  const token = session?.token ?? ''
  const [handoffs, setHandoffs] = useState<Handoff[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [selectedSnapshot, setSelectedSnapshot] = useState<Handoff | null>(null)
  const [filter, setFilter] = useState<QueueFilter>('all')
  const [context, setContext] = useState<StaffHandoffContext | null>(null)
  const [contextLoading, setContextLoading] = useState(false)
  const [contextError, setContextError] = useState<string | null>(null)
  const [contextTab, setContextTab] = useState<ContextTab>('overview')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [accepting, setAccepting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [showResolve, setShowResolve] = useState(false)
  const [resolveNote, setResolveNote] = useState('')
  const [resolving, setResolving] = useState(false)
  const [resolveError, setResolveError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const loadHandoffs = useCallback(
    async (silent = false) => {
      if (!silent) setListLoading(true)
      try {
        const result = await api.handoffs(token)
        setHandoffs(result.items)
        setListError(null)
      } catch (cause) {
        setListError(cause instanceof Error ? cause.message : '队列加载失败')
      } finally {
        if (!silent) setListLoading(false)
      }
    },
    [token],
  )

  useEffect(() => {
    void loadHandoffs()
  }, [loadHandoffs])

  usePolling(() => loadHandoffs(true), 5000, true)

  const listMatch = handoffs.find((item) => item.id === handoffId) ?? null

  useEffect(() => {
    if (listMatch) setSelectedSnapshot(listMatch)
  }, [listMatch])

  useEffect(() => {
    if (!handoffId && handoffs.length) {
      navigate(`/staff/${handoffs[0].id}`, { replace: true })
    }
  }, [handoffId, handoffs, navigate])

  const selected =
    listMatch ?? (selectedSnapshot?.id === handoffId ? selectedSnapshot : null)
  const activeConversationId = selected?.conversation_id ?? null

  useEffect(() => {
    setDraft('')
    setActionError(null)
    setShowResolve(false)
    setResolveNote('')
    setResolveError(null)
    setContextTab('overview')
  }, [handoffId])

  const loadContext = useCallback(async () => {
    if (!handoffId) {
      setContext(null)
      return
    }
    setContextLoading(true)
    setContextError(null)
    try {
      const result = await api.handoffContext(token, handoffId)
      setContext(result)
    } catch (cause) {
      setContextError(cause instanceof Error ? cause.message : '客户资料加载失败')
    } finally {
      setContextLoading(false)
    }
  }, [token, handoffId])

  useEffect(() => {
    setContext(null)
    void loadContext()
  }, [loadContext])

  const loadMessages = useCallback(
    async (silent = false) => {
      if (!activeConversationId) return
      if (!silent) setMessagesLoading(true)
      try {
        const result = await api.handoffMessages(token, activeConversationId)
        setMessages(result.messages)
        setMessagesError(null)
      } catch (cause) {
        setMessagesError(cause instanceof Error ? cause.message : '消息加载失败')
      } finally {
        if (!silent) setMessagesLoading(false)
      }
    },
    [token, activeConversationId],
  )

  useEffect(() => {
    setMessages([])
    if (!activeConversationId) {
      setMessagesLoading(false)
      return
    }
    void loadMessages()
  }, [activeConversationId, loadMessages])

  usePolling(() => loadMessages(true), 3000, Boolean(activeConversationId))

  const lastSequence = messages.length ? messages[messages.length - 1].sequence : 0
  useLayoutEffect(() => {
    const element = listRef.current
    if (element) element.scrollTop = element.scrollHeight
  }, [lastSequence, selected?.id])

  const waitingCount = handoffs.filter((item) => item.status === 'waiting').length
  const activeCount = handoffs.filter((item) => item.status === 'active').length

  const filteredHandoffs = useMemo(
    () =>
      filter === 'all'
        ? handoffs
        : handoffs.filter((item) => item.status === filter),
    [handoffs, filter],
  )

  async function handleAccept() {
    if (!selected || accepting || selected.status !== 'waiting') return
    setAccepting(true)
    setActionError(null)
    try {
      const result = await api.acceptHandoff(token, selected.id)
      setSelectedSnapshot((previous) =>
        previous ? mergeHandoff(previous, result.handoff) : result.handoff,
      )
      setHandoffs((previous) =>
        previous.map((item) =>
          item.id === result.handoff.id ? mergeHandoff(item, result.handoff) : item,
        ),
      )
      await loadMessages(true)
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : '接入失败')
    } finally {
      setAccepting(false)
    }
  }

  async function sendReply(text?: string) {
    const content = (text ?? draft).trim()
    if (!selected || selected.status !== 'active' || !content || sending) return
    setSending(true)
    setActionError(null)
    try {
      await api.sendStaffMessage(token, selected.id, content)
      setDraft('')
      await loadMessages(true)
      inputRef.current?.focus()
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : '发送失败')
    } finally {
      setSending(false)
    }
  }

  async function handleResolve() {
    if (!selected || resolving) return
    setResolving(true)
    setResolveError(null)
    try {
      const result = await api.resolveHandoff(
        token,
        selected.id,
        'resolved',
        resolveNote.trim() || '坐席结束会话',
      )
      setSelectedSnapshot((previous) =>
        previous ? mergeHandoff(previous, result.handoff) : result.handoff,
      )
      setHandoffs((previous) =>
        previous.filter((item) => item.id !== result.handoff.id),
      )
      setShowResolve(false)
      setDraft('')
      await loadMessages(true)
    } catch (cause) {
      setResolveError(cause instanceof Error ? cause.message : '结束会话失败')
    } finally {
      setResolving(false)
    }
  }

  function signOut() {
    logout()
    navigate('/login', { replace: true })
  }

  function renderContextBody() {
    if (contextLoading && !context) {
      return (
        <div className="ctx-state">
          <Loader2 className="spin" size={18} />
          加载客户资料…
        </div>
      )
    }
    if (contextError && !context) {
      return (
        <div className="ctx-state error">
          <AlertCircle size={18} />
          {contextError}
          <button type="button" className="text-button" onClick={() => void loadContext()}>
            重试
          </button>
        </div>
      )
    }
    if (!context) return null

    if (contextTab === 'orders') {
      return context.orders.length ? (
        <div className="ctx-list">
          {context.orders.map((order) => (
            <div className="ctx-item" key={order.order_no}>
              <div>
                <strong>{order.order_no}</strong>
                <small>{formatDate(order.created_at)}</small>
              </div>
              <StatusPill
                label={order.status_label ?? ORDER_STATUS_LABELS[order.status]}
                tone={orderTone(order.status)}
              />
              <span>{formatMoney(order.total_amount)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="ctx-empty">暂无订单</p>
      )
    }

    if (contextTab === 'devices') {
      return context.devices.length ? (
        <div className="ctx-list">
          {context.devices.map((device) => (
            <div className="ctx-item device" key={device.sn}>
              <div>
                <strong>{device.model}</strong>
                <small className="mono">SN {device.sn}</small>
              </div>
              <StatusPill
                label={device.warranty_status_label ?? warrantyLabel(device.warranty_status)}
                tone={warrantyTone(device.warranty_status)}
              />
            </div>
          ))}
        </div>
      ) : (
        <p className="ctx-empty">暂无绑定设备</p>
      )
    }

    if (contextTab === 'repairs') {
      return context.repairs.length ? (
        <div className="ctx-list">
          {context.repairs.map((repair) => (
            <div className="ctx-item repair" key={repair.repair_no}>
              <div>
                <strong>{faultLabel(repair.fault_type)}</strong>
                <small>
                  {repair.repair_no} · {REPAIR_MODE_LABELS[repair.mode] ?? repair.mode}
                </small>
              </div>
              <StatusPill
                label={repair.status_label ?? REPAIR_STATUS_LABELS[repair.status]}
                tone={repairTone(repair.status)}
              />
            </div>
          ))}
        </div>
      ) : (
        <p className="ctx-empty">暂无维修工单</p>
      )
    }

    const latestOrder = context.orders[0]
    const latestRepair = context.repairs[0]
    return (
      <div className="ctx-overview">
        <div className="ctx-stats">
          <div>
            <strong>{context.stats.orders}</strong>
            <span>订单</span>
          </div>
          <div>
            <strong>{context.stats.devices}</strong>
            <span>设备</span>
          </div>
          <div>
            <strong>{context.stats.repairs}</strong>
            <span>维修</span>
          </div>
        </div>
        <div className="ctx-section">
          <h4>最近订单</h4>
          {latestOrder ? (
            <div className="ctx-mini">
              <div>
                <strong>{latestOrder.order_no}</strong>
                <small>
                  {latestOrder.items.map((item) => item.product_name).join('、')}
                </small>
              </div>
              <StatusPill
                label={latestOrder.status_label ?? ORDER_STATUS_LABELS[latestOrder.status]}
                tone={orderTone(latestOrder.status)}
              />
            </div>
          ) : (
            <p className="ctx-empty">暂无订单</p>
          )}
        </div>
        <div className="ctx-section">
          <h4>最近维修</h4>
          {latestRepair ? (
            <div className="ctx-mini">
              <div>
                <strong>{faultLabel(latestRepair.fault_type)}</strong>
                <small>{latestRepair.repair_no}</small>
              </div>
              <StatusPill
                label={
                  latestRepair.status_label ??
                  REPAIR_STATUS_LABELS[latestRepair.status]
                }
                tone={repairTone(latestRepair.status)}
              />
            </div>
          ) : (
            <p className="ctx-empty">暂无维修记录</p>
          )}
        </div>
        <div className="ctx-section">
          <h4>联系信息</h4>
          <div className="ctx-contact">
            <Phone size={14} />
            {context.customer.phone_masked ?? '未提供手机号'}
          </div>
        </div>
      </div>
    )
  }

  const customerName = selected?.customer_name ?? context?.customer.name ?? '客户'

  return (
    <div className="staff-root">
      <aside className="staff-sidebar">
        <div className="staff-brand">
          <span className="brand-mark small">
            <BookOpen size={18} />
          </span>
          <div>
            <strong>学伴服务台</strong>
            <small>Customer Service</small>
          </div>
        </div>

        <nav className="staff-nav">
          <span className="staff-nav-label">服务</span>
          <button type="button" className="staff-nav-item active">
            <Headphones size={17} />
            工单队列
            <span className="staff-nav-badge">{waitingCount}</span>
          </button>
        </nav>

        <div className="staff-tip">
          <Sparkles size={15} />
          <p>AI 已完成常见问题拦截，这里只显示需要人工跟进的会话。</p>
        </div>

        <div className="staff-sidebar-spacer" />

        <div className="staff-agent">
          <span className="avatar avatar-sm avatar-green">
            {session?.profile.name.slice(0, 1)}
          </span>
          <div>
            <strong>{session?.profile.name}</strong>
            <small>
              <i className="online-dot" /> {session?.profile.tenant_code} · 在线
            </small>
          </div>
          <button
            type="button"
            className="icon-button light"
            onClick={signOut}
            aria-label="退出登录"
            title="退出登录"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <div className="staff-main">
        <header className="staff-topbar">
          <div>
            <h1>服务队列</h1>
            <p>
              {new Date()
                .toLocaleDateString('zh-CN', {
                  month: 'long',
                  day: 'numeric',
                  weekday: 'long',
                })
                .replace('日', '日 ')}
              · 待接入 {waitingCount} · 进行中 {activeCount}
            </p>
          </div>
          <div className="staff-topbar-right">
            <span className="live-chip">
              <i /> 自动刷新
            </span>
            <span className="staff-top-avatar">
              {session?.profile.name.slice(0, 1)}
            </span>
          </div>
        </header>

        <div className="staff-board">
          <section className="queue-panel">
            <div className="queue-head">
              <h2>待处理会话</h2>
              <span>{handoffs.length}</span>
            </div>
            <div className="queue-tabs">
              {(
                [
                  ['all', '全部', handoffs.length],
                  ['waiting', '待接入', waitingCount],
                  ['active', '进行中', activeCount],
                ] as const
              ).map(([key, label, count]) => (
                <button
                  key={key}
                  type="button"
                  className={filter === key ? 'active' : ''}
                  onClick={() => setFilter(key)}
                >
                  {label} {count}
                </button>
              ))}
            </div>

            <div className="queue-list">
              {listLoading && !handoffs.length ? (
                <div className="queue-state">
                  <Loader2 className="spin" size={18} /> 正在加载队列…
                </div>
              ) : null}
              {listError && !handoffs.length ? (
                <div className="queue-state error">
                  <AlertCircle size={17} />
                  {listError}
                  <button type="button" className="text-button" onClick={() => void loadHandoffs()}>
                    重试
                  </button>
                </div>
              ) : null}
              {!listLoading && !listError && filteredHandoffs.length === 0 ? (
                <div className="queue-state empty">
                  <Inbox size={22} />
                  暂无{filter === 'all' ? '' : filter === 'waiting' ? '待接入' : '进行中'}会话
                </div>
              ) : null}
              {filteredHandoffs.map((item) => {
                const sla = slaInfo(item.sla_due_at)
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`queue-item ${item.id === handoffId ? 'active' : ''}`}
                    onClick={() => navigate(`/staff/${item.id}`)}
                  >
                    <div className="queue-item-top">
                      <PriorityDot priority={item.priority} />
                      <span className="queue-time">
                        <Clock3 size={12} />
                        {item.status === 'waiting'
                          ? elapsedText(item.created_at)
                          : elapsedText(item.accepted_at ?? item.created_at)}
                      </span>
                      <StatusPill
                        label={HANDOFF_STATUS_LABELS[item.status]}
                        tone={handoffTone(item.status)}
                      />
                    </div>
                    <div className="queue-customer">
                      <span className="avatar avatar-xs avatar-blue">
                        {(item.customer_name ?? '客').slice(0, 1)}
                      </span>
                      <strong>{item.customer_name ?? '匿名客户'}</strong>
                      {item.customer_phone_masked ? (
                        <small>{item.customer_phone_masked}</small>
                      ) : null}
                    </div>
                    <p>{item.summary}</p>
                    <div className={`queue-sla ${sla.overdue ? 'overdue' : ''}`}>
                      {sla.text}
                    </div>
                  </button>
                )
              })}
            </div>
          </section>

          <section className="workspace">
            {!selected ? (
              <div className="workspace-empty">
                <MessageSquare size={28} />
                <strong>选择一个会话</strong>
                <span>从左侧队列选择待接入或进行中的会话，查看客户上下文并回复。</span>
              </div>
            ) : (
              <>
                <header className="ws-head">
                  <div className="ws-customer">
                    <span className="avatar avatar-md avatar-blue">
                      {customerName.slice(0, 1)}
                    </span>
                    <div>
                      <strong>{customerName}</strong>
                      <span>
                        {selected.customer_phone_masked ?? context?.customer.phone_masked ?? '未提供手机号'}
                      </span>
                    </div>
                    <PriorityDot priority={selected.priority} />
                  </div>
                  <div className="ws-actions">
                    {selected.status === 'active' ? (
                      <button
                        type="button"
                        className="ghost-button danger"
                        onClick={() => setShowResolve(true)}
                      >
                        结束会话
                      </button>
                    ) : null}
                    <StatusPill
                      label={HANDOFF_STATUS_LABELS[selected.status]}
                      tone={handoffTone(selected.status)}
                    />
                  </div>
                </header>

                <div className="ws-summary">
                  <Sparkles size={15} />
                  <div>
                    <strong>AI 转接摘要</strong>
                    <p>{selected.summary}</p>
                  </div>
                  {selected.status === 'waiting' || selected.status === 'active' ? (
                    <span
                      className={`ws-sla ${slaInfo(selected.sla_due_at).overdue ? 'overdue' : ''}`}
                    >
                      {slaInfo(selected.sla_due_at).text}
                    </span>
                  ) : (
                    <span className="ws-sla">已结束</span>
                  )}
                </div>

                {actionError ? (
                  <div className="ws-error">
                    <AlertCircle size={15} />
                    {actionError}
                    <button type="button" onClick={() => setActionError(null)} aria-label="关闭">
                      <X size={14} />
                    </button>
                  </div>
                ) : null}

                <div className="ws-messages" ref={listRef}>
                  {messagesLoading && !messages.length ? (
                    <div className="queue-state">
                      <Loader2 className="spin" size={18} /> 正在加载消息…
                    </div>
                  ) : null}
                  {messagesError && !messages.length ? (
                    <div className="queue-state error">
                      <AlertCircle size={17} />
                      {messagesError}
                      <button type="button" className="text-button" onClick={() => void loadMessages()}>
                        重试
                      </button>
                    </div>
                  ) : null}
                  {!messagesLoading && !messages.length ? (
                    <div className="ws-no-message">暂无消息记录</div>
                  ) : null}

                  {messages.map((message) => {
                    if (message.role === 'system') {
                      return (
                        <div className="ws-system" key={message.message_id}>
                          {messageText(message)}
                        </div>
                      )
                    }
                    const mine = message.role === 'agent'
                    const isAi = message.role === 'ai'
                    return (
                      <div
                        className={`ws-msg-row ${mine ? 'mine' : ''}`}
                        key={message.message_id}
                      >
                        {!mine ? (
                          <span className={`ws-msg-avatar ${isAi ? 'ai' : ''}`}>
                            {isAi ? (
                              <Sparkles size={14} />
                            ) : (
                              customerName.slice(0, 1)
                            )}
                          </span>
                        ) : null}
                        <div className="ws-msg-wrap">
                          <span className="ws-msg-author">
                            {mine ? '我' : isAi ? 'AI 客服' : customerName}
                          </span>
                          <div className="ws-bubble">{messageText(message)}</div>
                          <time>{formatTime(message.created_at)}</time>
                        </div>
                      </div>
                    )
                  })}
                </div>

                {selected.status === 'waiting' ? (
                  <div className="ws-accept-box">
                    <div>
                      <strong>接入后即可与客户对话</strong>
                      <span>接入后 AI 自动回复暂停，客户消息将直接转给你。</span>
                    </div>
                    <button
                      type="button"
                      className="primary-button"
                      disabled={accepting}
                      onClick={() => void handleAccept()}
                    >
                      {accepting ? <Loader2 className="spin" size={16} /> : <Headphones size={16} />}
                      接入会话
                    </button>
                  </div>
                ) : selected.status === 'active' ? (
                  <div className="ws-composer">
                    <div className="quick-replies">
                      {QUICK_REPLIES.map((reply) => (
                        <button
                          key={reply}
                          type="button"
                          onClick={() => {
                            setDraft(reply)
                            inputRef.current?.focus()
                          }}
                        >
                          {reply}
                        </button>
                      ))}
                    </div>
                    <div className="ws-composer-box">
                      <textarea
                        ref={inputRef}
                        rows={2}
                        maxLength={4000}
                        value={draft}
                        placeholder="回复客户…（Enter 发送，Shift + Enter 换行）"
                        onChange={(event) => setDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (
                            event.key === 'Enter' &&
                            !event.shiftKey &&
                            !event.nativeEvent.isComposing
                          ) {
                            event.preventDefault()
                            void sendReply()
                          }
                        }}
                      />
                      <button
                        type="button"
                        className="primary-button send"
                        disabled={!draft.trim() || sending}
                        onClick={() => void sendReply()}
                      >
                        {sending ? (
                          <Loader2 className="spin" size={16} />
                        ) : (
                          <Send size={16} />
                        )}
                        发送
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="ws-closed-box">
                    会话已结束，如需继续服务，请让客户重新发起咨询。
                  </div>
                )}

                {showResolve ? (
                  <div className="modal-backdrop">
                    <div className="modal-card">
                      <div className="modal-head">
                        <div>
                          <h3>结束本次服务</h3>
                          <p>结束后会话将关闭，客户需要重新发起咨询。</p>
                        </div>
                        <button
                          type="button"
                          className="icon-button"
                          onClick={() => setShowResolve(false)}
                          aria-label="关闭"
                        >
                          <X size={18} />
                        </button>
                      </div>
                      <label className="field">
                        <span>服务小结（可选）</span>
                        <textarea
                          rows={3}
                          maxLength={1000}
                          value={resolveNote}
                          placeholder="例如：已与客户确认物流异常，补偿方案已同步。"
                          onChange={(event) => setResolveNote(event.target.value)}
                        />
                      </label>
                      {resolveError ? (
                        <div className="inline-error">{resolveError}</div>
                      ) : null}
                      <div className="modal-actions">
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => setShowResolve(false)}
                        >
                          取消
                        </button>
                        <button
                          type="button"
                          className="primary-button"
                          disabled={resolving}
                          onClick={() => void handleResolve()}
                        >
                          {resolving ? <Loader2 className="spin" size={16} /> : null}
                          确认结束
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </section>

          <aside className="context-panel">
            <header className="ctx-head">
              <h2>客户信息</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => void loadContext()}
                disabled={!handoffId}
                aria-label="刷新客户资料"
              >
                <RefreshCw size={15} className={contextLoading ? 'spin' : ''} />
              </button>
            </header>

            {context ? (
              <>
                <div className="ctx-profile">
                  <span className="avatar avatar-md avatar-blue">
                    {context.customer.name.slice(0, 1)}
                  </span>
                  <div>
                    <strong>{context.customer.name}</strong>
                    <span>
                      <Phone size={12} /> {context.customer.phone_masked ?? '未提供手机号'}
                    </span>
                  </div>
                </div>
                <nav className="ctx-tabs">
                  {(
                    [
                      ['overview', '概览'],
                      ['orders', `订单 ${context.stats.orders}`],
                      ['devices', `设备 ${context.stats.devices}`],
                      ['repairs', `维修 ${context.stats.repairs}`],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      className={contextTab === key ? 'active' : ''}
                      onClick={() => setContextTab(key)}
                    >
                      {label}
                    </button>
                  ))}
                </nav>
              </>
            ) : null}

            <div className="ctx-body">{renderContextBody()}</div>

            <footer className="ctx-foot">
              <span>
                <Package size={15} /> 订单
              </span>
              <span>
                <Tablet size={15} /> 设备
              </span>
              <span>
                <Wrench size={15} /> 维修
              </span>
            </footer>
          </aside>
        </div>
      </div>
    </div>
  )
}
