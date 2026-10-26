import { useNavigate } from 'react-router-dom'
import {
  ChevronRight,
  Headphones,
  LogOut,
  Package,
  ShieldCheck,
  Tablet,
  Wrench,
} from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import { PageHeader, SectionTitle } from '../../components/ui'

const LINKS = [
  {
    to: '/app/orders',
    label: '我的订单',
    description: '查看订单状态与物流',
    icon: Package,
    tone: 'blue',
  },
  {
    to: '/app/devices',
    label: '我的设备',
    description: '设备绑定、激活与保修',
    icon: Tablet,
    tone: 'green',
  },
  {
    to: '/app/repairs',
    label: '维修工单',
    description: '报修进度与历史记录',
    icon: Wrench,
    tone: 'orange',
  },
]

export function ProfilePage() {
  const navigate = useNavigate()
  const { session, logout } = useAuth()
  const profile = session?.profile

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="screen page-screen profile-screen">
      <PageHeader title="我的" subtitle="家长账号与服务中心" />

      <section className="profile-hero">
        <span className="avatar avatar-lg avatar-navy">{profile?.name.slice(0, 1)}</span>
        <div className="profile-hero-copy">
          <strong>{profile?.name}</strong>
          <span>家长账号 · {profile?.tenant_code}</span>
          <small>演示环境 · 已通过 /auth/demo-token 登录</small>
        </div>
        <ShieldCheck size={22} className="profile-hero-badge" />
      </section>

      <section className="card profile-links">
        {LINKS.map(({ to, label, description, icon: Icon, tone }) => (
          <button key={to} type="button" className="profile-link" onClick={() => navigate(to)}>
            <span className={`quick-icon tone-${tone} small`}>
              <Icon size={18} />
            </span>
            <span className="profile-link-copy">
              <strong>{label}</strong>
              <small>{description}</small>
            </span>
            <ChevronRight size={17} />
          </button>
        ))}
      </section>

      <SectionTitle title="服务与支持" />
      <button
        type="button"
        className="profile-link standalone"
        onClick={() => navigate('/app/chat')}
      >
        <span className="quick-icon tone-navy small">
          <Headphones size={18} />
        </span>
        <span className="profile-link-copy">
          <strong>在线客服</strong>
          <small>AI 优先响应，必要时转人工</small>
        </span>
        <ChevronRight size={17} />
      </button>

      <SectionTitle title="账号信息" />
      <section className="card account-card">
        <dl className="info-list">
          <div>
            <dt>账号角色</dt>
            <dd>家长 / 客户</dd>
          </div>
          <div>
            <dt>所属经销商</dt>
            <dd>{profile?.tenant_code ?? '—'}</dd>
          </div>
          <div>
            <dt>用户标识</dt>
            <dd className="mono">{profile?.user_id.slice(0, 8) ?? '—'}…</dd>
          </div>
        </dl>
      </section>

      <button type="button" className="logout-button" onClick={handleLogout}>
        <LogOut size={16} />
        退出登录 / 切换演示身份
      </button>

      <p className="profile-note">
        当前为演示版本，权限校验已简化；正式接入时替换为统一登录与真实账号体系。
      </p>
    </div>
  )
}
