import type {
  AcceptHandoffResponse,
  AuthProfile,
  ChatMessage,
  Conversation,
  ConversationDetail,
  DemoTokenResponse,
  Device,
  HandoffList,
  MessageList,
  Order,
  OrderDetail,
  Repair,
  RepairDetail,
  StaffHandoffContext,
  StaffMessageResponse,
} from './types'

function defaultApiBase(): string {
  // 手机/平板通过局域网地址打开时，API 也要指向同一台开发机，
  // 否则浏览器会去请求设备自己的 127.0.0.1。
  if (typeof window === 'undefined') return 'http://127.0.0.1:8010'
  const host = window.location.hostname
  if (!host || host === 'localhost' || host === '127.0.0.1') {
    return 'http://127.0.0.1:8010'
  }
  return `http://${host}:8010`
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || defaultApiBase()).replace(
  /\/$/,
  '',
)

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST'
  token?: string | null
  body?: unknown
  params?: Record<string, string | number | undefined>
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`)
  for (const [key, value] of Object.entries(options.params ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value))
  }

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.token) headers.Authorization = `Bearer ${options.token}`
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(url, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, `无法连接客服服务（${BASE_URL}），请确认后端已启动`)
  }

  if (!response.ok) {
    let detail = `请求失败（${response.status}）`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === 'string') detail = payload.detail
      else if (payload.detail) detail = JSON.stringify(payload.detail)
    } catch {
      // keep the generic message
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  demoToken(tenantCode: string, externalId: string): Promise<DemoTokenResponse> {
    return request('/api/v1/auth/demo-token', {
      method: 'POST',
      body: { tenant_code: tenantCode, external_id: externalId },
    })
  },

  currentConversation(token: string, channel = 'app'): Promise<Conversation> {
    return request('/api/v1/conversations/current', {
      token,
      params: { channel },
    })
  },

  conversationDetail(token: string, conversationId: string): Promise<ConversationDetail> {
    return request(`/api/v1/conversations/${conversationId}`, { token })
  },

  messages(token: string, conversationId: string, limit = 100): Promise<MessageList> {
    return request(`/api/v1/conversations/${conversationId}/messages`, {
      token,
      params: { limit },
    })
  },

  sendMessage(token: string, conversationId: string, text: string) {
    return request<{
      conversation_id: string
      mode: Conversation['mode']
      is_processing: boolean
      message: ChatMessage
      input_revision?: number | null
    }>(`/api/v1/conversations/${conversationId}/messages`, {
      method: 'POST',
      token,
      body: {
        message_id: crypto.randomUUID(),
        type: 'text',
        content: { text },
      },
    })
  },

  orders(token: string): Promise<{ items: Order[] }> {
    return request('/api/v1/me/orders', { token })
  },

  order(token: string, orderNo: string): Promise<OrderDetail> {
    return request(`/api/v1/me/orders/${encodeURIComponent(orderNo)}`, { token })
  },

  devices(token: string): Promise<{ items: Device[] }> {
    return request('/api/v1/me/devices', { token })
  },

  repairs(token: string): Promise<{ items: Repair[] }> {
    return request('/api/v1/me/repairs', { token })
  },

  repair(token: string, repairNo: string): Promise<RepairDetail> {
    return request(`/api/v1/me/repairs/${encodeURIComponent(repairNo)}`, { token })
  },

  handoffs(token: string): Promise<HandoffList> {
    return request('/api/v1/staff/handoffs', {
      token,
      params: { status: 'waiting,active', limit: 50 },
    })
  },

  handoffMessages(token: string, conversationId: string): Promise<MessageList> {
    return request(`/api/v1/conversations/${conversationId}/messages`, {
      token,
      params: { limit: 100 },
    })
  },

  acceptHandoff(token: string, handoffId: string): Promise<AcceptHandoffResponse> {
    return request(`/api/v1/staff/handoffs/${handoffId}/accept`, {
      method: 'POST',
      token,
    })
  },

  resolveHandoff(
    token: string,
    handoffId: string,
    closeReason = 'resolved',
    note = '坐席结束会话',
  ): Promise<AcceptHandoffResponse> {
    return request(`/api/v1/staff/handoffs/${handoffId}/resolve`, {
      method: 'POST',
      token,
      body: { close_reason: closeReason, note },
    })
  },

  sendStaffMessage(
    token: string,
    handoffId: string,
    text: string,
  ): Promise<StaffMessageResponse> {
    return request(`/api/v1/staff/handoffs/${handoffId}/messages`, {
      method: 'POST',
      token,
      body: { client_message_id: crypto.randomUUID(), text },
    })
  },

  handoffContext(token: string, handoffId: string): Promise<StaffHandoffContext> {
    return request(`/api/v1/staff/handoffs/${handoffId}/context`, { token })
  },
}

export type { AuthProfile }
