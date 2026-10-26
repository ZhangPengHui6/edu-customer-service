import type {
  ChatMessage,
  HandoffStatus,
  OrderStatus,
  RepairStatus,
  WarrantyStatus,
} from '../api/types'

export function formatMoney(value: string | number | null | undefined): string {
  const amount = Number(value ?? 0)
  if (!Number.isFinite(amount)) return '¥0'
  return `¥${amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return ''
  return new Date(value).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function formatDateTimeLong(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function elapsedText(value: string): string {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000))
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  return `${hours} 小时 ${minutes % 60} 分`
}

export interface SlaInfo {
  text: string
  overdue: boolean
}

export function slaInfo(dueAt: string | null | undefined): SlaInfo {
  if (!dueAt) return { text: '未设置', overdue: false }
  const diff = new Date(dueAt).getTime() - Date.now()
  const minutes = Math.max(0, Math.floor(Math.abs(diff) / 60000))
  const hours = Math.floor(minutes / 60)
  const label = hours > 0 ? `${hours} 小时 ${minutes % 60} 分` : `${minutes} 分钟`
  return diff >= 0
    ? { text: `剩余 ${label}`, overdue: false }
    : { text: `已超时 ${label}`, overdue: true }
}

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  pending: '待付款',
  paid: '待发货',
  shipped: '运输中',
  delivered: '已签收',
  cancelled: '已取消',
  after_sale: '售后中',
}

export const REPAIR_STATUS_LABELS: Record<RepairStatus, string> = {
  created: '已创建',
  received: '已收件',
  diagnosing: '诊断中',
  quoted: '已报价',
  repairing: '维修中',
  completed: '已完成',
  cancelled: '已取消',
}

export const HANDOFF_STATUS_LABELS: Record<HandoffStatus, string> = {
  waiting: '待接入',
  active: '进行中',
  resolved: '已结束',
  closed: '已关闭',
  cancelled: '已取消',
}

export const REPAIR_MODE_LABELS: Record<string, string> = {
  mail_in: '寄修',
  in_store: '到店维修',
  on_site: '上门维修',
}

export const FAULT_TYPE_LABELS: Record<string, string> = {
  screen_flicker: '屏幕闪烁',
  touch_failure: '触控失灵',
  no_power: '无法开机',
  battery: '电池异常',
  speaker: '扬声器异常',
}

export function faultLabel(value: string): string {
  return FAULT_TYPE_LABELS[value] ?? value
}

export function warrantyLabel(status: WarrantyStatus): string {
  if (status === 'in_warranty') return '保修中'
  if (status === 'out_of_warranty') return '已过保'
  return '保修未知'
}

export function warrantyTone(
  status: WarrantyStatus,
): 'green' | 'red' | 'gray' {
  if (status === 'in_warranty') return 'green'
  if (status === 'out_of_warranty') return 'red'
  return 'gray'
}

export function orderTone(status: OrderStatus): 'blue' | 'green' | 'orange' | 'gray' {
  if (status === 'delivered') return 'green'
  if (status === 'shipped' || status === 'paid') return 'blue'
  if (status === 'pending' || status === 'after_sale') return 'orange'
  return 'gray'
}

export function repairTone(status: RepairStatus): 'blue' | 'green' | 'orange' | 'gray' {
  if (status === 'completed') return 'green'
  if (status === 'cancelled') return 'gray'
  if (status === 'created' || status === 'received') return 'orange'
  return 'blue'
}

export function handoffTone(status: HandoffStatus): 'blue' | 'green' | 'orange' | 'gray' {
  if (status === 'active') return 'blue'
  if (status === 'waiting') return 'orange'
  if (status === 'resolved' || status === 'closed') return 'green'
  return 'gray'
}

export function isRepairOpen(status: RepairStatus): boolean {
  return status !== 'completed' && status !== 'cancelled'
}

export function orderStepIndex(status: OrderStatus): number {
  if (status === 'paid') return 0
  if (status === 'shipped' || status === 'after_sale') return 2
  if (status === 'delivered') return 3
  return -1
}

export const ORDER_STEPS = ['已付款', '已发货', '运输中', '已签收']

export function messageText(message: ChatMessage): string {
  const text = message.content?.text
  if (typeof text === 'string' && text.trim()) return text
  if (message.type === 'image') return '[图片]'
  return '[非文本消息]'
}
