export type Role = 'customer' | 'agent' | 'admin'

export interface AuthProfile {
  user_id: string
  tenant_id: string
  tenant_code: string
  tenant_type: string
  role: Role
  name: string
}

export interface DemoTokenResponse extends AuthProfile {
  access_token: string
  expires_in: number
}

export type OrderStatus =
  | 'pending'
  | 'paid'
  | 'shipped'
  | 'delivered'
  | 'cancelled'
  | 'after_sale'

export interface OrderItem {
  product_name: string
  product_model: string
  quantity: number
  amount: string
}

export interface Order {
  order_no: string
  status: OrderStatus
  status_label?: string | null
  total_amount: string
  created_at: string
  shipped_at?: string | null
  delivered_at?: string | null
  cancelled_at?: string | null
  items: OrderItem[]
}

export interface LogisticsEvent {
  status: string
  description: string
  occurred_at: string
}

export interface OrderDetail extends Order {
  recipient_masked?: string | null
  address_masked?: string | null
  logistics: LogisticsEvent[]
}

export type WarrantyStatus = 'in_warranty' | 'out_of_warranty' | 'unknown'

export interface Device {
  sn: string
  model: string
  activation_at?: string | null
  firmware_version?: string | null
  status: string
  warranty_type?: string | null
  warranty_start_at?: string | null
  warranty_end_at?: string | null
  warranty_status: WarrantyStatus
  warranty_status_label?: string | null
}

export type RepairStatus =
  | 'created'
  | 'received'
  | 'diagnosing'
  | 'quoted'
  | 'repairing'
  | 'completed'
  | 'cancelled'

export interface Repair {
  repair_no: string
  device_sn: string
  fault_type: string
  description: string
  status: RepairStatus
  status_label?: string | null
  mode: 'mail_in' | 'in_store' | 'on_site'
  warranty_status?: WarrantyStatus | null
  warranty_status_label?: string | null
  quote_amount?: string | null
  created_at: string
  updated_at: string
  closed_at?: string | null
}

export interface RepairEvent {
  from_status?: string | null
  to_status: string
  note?: string | null
  created_at: string
}

export interface RepairDetail extends Repair {
  events: RepairEvent[]
}

export type ConversationMode = 'AI' | 'QUEUED' | 'HUMAN' | 'REPAIR' | 'CLOSED'

export interface Conversation {
  id: string
  mode: ConversationMode
  is_processing: boolean
  channel: string
  started_at: string
  last_active_at: string
}

export interface MessageAction {
  action_type: string
  order_no?: string
  repair_no?: string
  status?: string
}

export interface MessageContent {
  text?: string
  reply_type?: string
  action?: MessageAction
  [key: string]: unknown
}

export interface ChatMessage {
  sequence: number
  message_id: string
  conversation_id: string
  role: 'customer' | 'ai' | 'agent' | 'system'
  type: 'text' | 'image' | 'object'
  content: MessageContent
  created_at: string
}

export interface MessageList {
  messages: ChatMessage[]
  next_after_sequence?: number | null
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[]
}

export type HandoffStatus =
  | 'waiting'
  | 'active'
  | 'resolved'
  | 'closed'
  | 'cancelled'

export type Priority = 'P0' | 'P1' | 'P2'

export interface Handoff {
  id: string
  conversation_id: string
  user_id: string
  summary: string
  status: HandoffStatus
  priority: Priority
  assigned_agent_id?: string | null
  created_at: string
  accepted_at?: string | null
  resolved_at?: string | null
  sla_due_at?: string | null
  customer_name?: string | null
  customer_phone_masked?: string | null
}

export interface StaffCustomer {
  id: string
  name: string
  phone_masked?: string | null
}

export interface StaffCustomerStats {
  orders: number
  devices: number
  repairs: number
}

export interface StaffHandoffContext {
  customer: StaffCustomer
  stats: StaffCustomerStats
  orders: Order[]
  devices: Device[]
  repairs: Repair[]
}

export interface HandoffList {
  items: Handoff[]
}

export interface AcceptHandoffResponse {
  handoff: Handoff
  conversation_mode: ConversationMode
}

export interface StaffMessageResponse {
  conversation_id: string
  message_id: string
  sequence: number
  created_at: string
}
