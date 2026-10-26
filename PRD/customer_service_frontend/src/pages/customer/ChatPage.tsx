import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  Headphones,
  Loader2,
  Send,
  Sparkles,
  Wrench,
  X,
} from 'lucide-react'
import { api } from '../../api/client'
import type {
  ChatMessage,
  ConversationDetail,
  MessageAction,
} from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { usePolling } from '../../hooks/useAsync'
import { formatTime, messageText } from '../../utils/format'
import { ErrorBlock, LoadingBlock } from '../../components/ui'

const SUGGESTIONS = [
  { label: '查我的订单', text: '帮我查一下我最近的订单' },
  { label: '查物流', text: '我最近的订单到哪里了？' },
  { label: '查保修', text: '我的学习机还在保修期内吗？' },
  { label: '申请报修', text: '我想申请设备报修' },
  { label: '转人工', text: '请帮我转人工客服' },
]

function initialDraft(params: URLSearchParams): string {
  const intent = params.get('intent')
  const sn = params.get('sn')
  const orderNo = params.get('order_no')
  const repairNo = params.get('repair_no')
  if (intent === 'repair') {
    return sn ? `我想为设备 ${sn} 申请报修。` : '我想申请设备报修。'
  }
  if (intent === 'order') {
    return orderNo ? `我想咨询订单 ${orderNo} 的物流进度。` : '我想咨询订单。'
  }
  if (intent === 'device') {
    return sn ? `我想查询设备 ${sn} 的保修状态。` : '我想查询设备保修。'
  }
  if (intent === 'repair_progress') {
    return repairNo ? `我想了解维修工单 ${repairNo} 的进度。` : '我想了解维修进度。'
  }
  return ''
}

function contextLabel(params: URLSearchParams): string | null {
  const intent = params.get('intent')
  const sn = params.get('sn')
  const orderNo = params.get('order_no')
  const repairNo = params.get('repair_no')
  if (intent === 'order' && orderNo) return `订单 ${orderNo}`
  if (intent === 'device' && sn) return `设备 ${sn}`
  if (intent === 'repair') return sn ? `报修设备 ${sn}` : '设备报修'
  if (intent === 'repair_progress' && repairNo) return `维修工单 ${repairNo}`
  return intent ? `上下文：${intent}` : null
}

function actionText(action: MessageAction | undefined): string | null {
  if (!action) return null
  if (action.action_type === 'create_repair_ticket') {
    return action.repair_no ? `已创建维修工单 ${action.repair_no}` : '已创建维修工单'
  }
  if (action.action_type === 'cancel_unshipped_order') {
    return action.order_no ? `订单 ${action.order_no} 已取消` : '订单已取消'
  }
  return null
}

export function ChatPage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const token = session?.token ?? ''
  const context = contextLabel(params)
  const [draft, setDraft] = useState(() => initialDraft(params))
  const [conversation, setConversation] = useState<ConversationDetail | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [liveError, setLiveError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [slowReply, setSlowReply] = useState(false)
  const [retryKey, setRetryKey] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const current = await api.currentConversation(token)
        const detail = await api.conversationDetail(token, current.id)
        if (cancelled) return
        setConversation(detail)
        setMessages(detail.messages)
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : '无法加载会话')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, retryKey])

  const conversationId = conversation?.id

  const refresh = useCallback(async () => {
    if (!conversationId) return
    try {
      const detail = await api.conversationDetail(token, conversationId)
      setConversation(detail)
      setMessages(detail.messages)
      setLiveError(null)
    } catch (cause) {
      setLiveError(cause instanceof Error ? cause.message : '消息刷新失败')
    }
  }, [token, conversationId])

  usePolling(() => refresh(), 2500, Boolean(conversationId))

  useEffect(() => {
    if (!conversation?.is_processing || conversation.mode !== 'AI') {
      setSlowReply(false)
      return
    }
    const timer = window.setTimeout(() => setSlowReply(true), 45000)
    return () => window.clearTimeout(timer)
  }, [conversation?.is_processing, conversation?.mode])

  const lastSequence = messages.length ? messages[messages.length - 1].sequence : 0
  useLayoutEffect(() => {
    const element = listRef.current
    if (element) element.scrollTop = element.scrollHeight
  }, [lastSequence, conversation?.is_processing, loading])

  async function submit(text: string) {
    const content = text.trim()
    if (!content || !conversation || sending || conversation.mode === 'CLOSED') {
      return
    }
    setSending(true)
    setSendError(null)
    try {
      const result = await api.sendMessage(token, conversation.id, content)
      setDraft('')
      setMessages((previous) =>
        previous.some((item) => item.message_id === result.message.message_id)
          ? previous
          : [...previous, result.message],
      )
      setConversation((previous) =>
        previous
          ? { ...previous, mode: result.mode, is_processing: result.is_processing }
          : previous,
      )
      if (params.get('intent')) {
        setParams({}, { replace: true })
      }
    } catch (cause) {
      setSendError(cause instanceof Error ? cause.message : '发送失败')
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  function dismissContext() {
    setParams({}, { replace: true })
  }

  const customerMessageCount = messages.filter(
    (message) => message.role === 'customer',
  ).length
  const statusText = (() => {
    if (!conversation) return '连接中'
    if (conversation.mode === 'QUEUED') return '正在排队等待人工'
    if (conversation.mode === 'HUMAN') return '人工客服服务中'
    if (conversation.mode === 'REPAIR') return '报修处理中'
    if (conversation.mode === 'CLOSED') return '会话已结束'
    return conversation.is_processing ? 'AI 正在思考' : 'AI 客服在线'
  })()

  if (loading) {
    return (
      <div className="chat-screen">
        <LoadingBlock label="正在连接客服…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="chat-screen">
        <header className="chat-header">
          <button className="icon-button" type="button" onClick={() => navigate(-1)} aria-label="返回">
            <ArrowLeft size={20} />
          </button>
          <div className="chat-header-title">
            <strong>在线客服</strong>
          </div>
          <span className="header-spacer" />
        </header>
        <ErrorBlock message={error} onRetry={() => setRetryKey((value) => value + 1)} />
      </div>
    )
  }

  if (!conversation) return null

  const closed = conversation.mode === 'CLOSED'

  return (
    <div className="chat-screen">
      <header className="chat-header">
        <button className="icon-button" type="button" onClick={() => navigate('/app')} aria-label="返回">
          <ArrowLeft size={20} />
        </button>
        <div className="chat-header-title">
          <strong>学伴客服</strong>
          <span className={`chat-status mode-${conversation.mode.toLowerCase()}`}>
            <i />
            {statusText}
          </span>
        </div>
        <button
          type="button"
          className="chat-human-button"
          disabled={conversation.mode !== 'AI' || sending}
          onClick={() => void submit('请帮我转人工客服')}
        >
          <Headphones size={14} />
          人工
        </button>
      </header>

      {conversation.mode === 'QUEUED' ? (
        <div className="chat-banner queue">
          <Loader2 className="spin" size={15} />
          已为您转接人工客服，正在排队，请稍候…
        </div>
      ) : null}
      {conversation.mode === 'HUMAN' ? (
        <div className="chat-banner human">
          <Headphones size={15} />
          人工客服已接入，AI 暂停自动回复。
        </div>
      ) : null}
      {liveError ? <div className="chat-banner warn">{liveError}</div> : null}
      {slowReply ? (
        <div className="chat-banner warn">
          AI 回复较慢，如情况紧急可点击右上角「人工」转接客服。
        </div>
      ) : null}

      <div className="chat-messages" ref={listRef}>
        {context ? (
          <div className="chat-context-chip">
            <Sparkles size={14} />
            <span>正在咨询：{context}</span>
            <button type="button" onClick={dismissContext} aria-label="清除上下文">
              <X size={14} />
            </button>
          </div>
        ) : null}

        <div className="chat-day">今天</div>

        {messages.length === 0 ? (
          <div className="chat-row left">
            <span className="chat-avatar ai">
              <Sparkles size={16} />
            </span>
            <div className="chat-bubble-wrap">
              <span className="chat-author">AI 客服</span>
              <div className="chat-bubble">
                您好，我是学伴智能客服。可以帮您查订单、物流和保修进度，也能协助登记报修。请问有什么可以帮您？
              </div>
            </div>
          </div>
        ) : null}

        {messages.map((message) => {
          if (message.role === 'system') {
            return (
              <div className="chat-system" key={message.message_id}>
                {messageText(message)}
              </div>
            )
          }
          const mine = message.role === 'customer'
          const isAgent = message.role === 'agent'
          const action = actionText(message.content.action)
          return (
            <div
              className={`chat-row ${mine ? 'right' : 'left'}`}
              key={message.message_id}
            >
              {!mine ? (
                <span className={`chat-avatar ${isAgent ? 'agent' : 'ai'}`}>
                  {isAgent ? <Headphones size={15} /> : <Sparkles size={16} />}
                </span>
              ) : null}
              <div className="chat-bubble-wrap">
                {!mine ? (
                  <span className="chat-author">{isAgent ? '人工客服' : 'AI 客服'}</span>
                ) : null}
                <div className={`chat-bubble ${mine ? 'mine' : ''}`}>
                  {messageText(message)}
                </div>
                {action ? (
                  <div className="chat-action">
                    <Wrench size={13} /> {action}
                  </div>
                ) : null}
                <span className="chat-time">{formatTime(message.created_at)}</span>
              </div>
            </div>
          )
        })}

        {conversation.is_processing && conversation.mode === 'AI' ? (
          <div className="chat-row left">
            <span className="chat-avatar ai">
              <Sparkles size={16} />
            </span>
            <div className="chat-bubble-wrap">
              <div className="chat-bubble typing">
                <i />
                <i />
                <i />
              </div>
            </div>
          </div>
        ) : null}

        {!messages.length && customerMessageCount === 0 ? (
          <div className="chat-suggestions">
            {SUGGESTIONS.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => void submit(item.text)}
              >
                {item.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {sendError ? <div className="composer-error">{sendError}</div> : null}

      {closed ? (
        <div className="chat-closed">
          <span>本次会话已结束</span>
          <button
            type="button"
            className="primary-button small"
            onClick={() => setRetryKey((value) => value + 1)}
          >
            开始新会话
          </button>
        </div>
      ) : (
        <div className="chat-composer">
          <textarea
            ref={inputRef}
            value={draft}
            rows={1}
            maxLength={4000}
            placeholder={
              conversation.mode === 'QUEUED'
                ? '可先留言，接入后客服会看到…'
                : conversation.mode === 'HUMAN'
                  ? '回复人工客服…'
                  : '描述您的问题…'
            }
            onChange={(event) => {
              setDraft(event.target.value)
              event.target.style.height = 'auto'
              event.target.style.height = `${Math.min(event.target.scrollHeight, 96)}px`
            }}
            onKeyDown={(event) => {
              if (
                event.key === 'Enter' &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault()
                void submit(draft)
              }
            }}
          />
          <button
            type="button"
            className="chat-send"
            disabled={!draft.trim() || sending}
            onClick={() => void submit(draft)}
            aria-label="发送"
          >
            {sending ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
          </button>
        </div>
      )}
    </div>
  )
}
