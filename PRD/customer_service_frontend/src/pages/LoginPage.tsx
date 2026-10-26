import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  Headphones,
  Loader2,
  LogOut,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { useAuth } from '../auth/AuthContext'

interface DemoAccount {
  tenantCode: string
  externalId: string
  name: string
  note: string
}

const DEMO_GROUPS: { title: string; icon: typeof UserRound; accounts: DemoAccount[] }[] = [
  {
    title: '家长端 · APP',
    icon: UserRound,
    accounts: [
      {
        tenantCode: 'dlr_north',
        externalId: 'parent_001',
        name: '张伟',
        note: '学习机 X5 / X6 家长',
      },
      {
        tenantCode: 'dlr_north',
        externalId: 'parent_002',
        name: '李娜',
        note: '订单物流与售后咨询',
      },
      {
        tenantCode: 'dlr_south',
        externalId: 'parent_003',
        name: '王强',
        note: '学习机 S3 家长',
      },
    ],
  },
  {
    title: '坐席端 · 工作台',
    icon: Headphones,
    accounts: [
      {
        tenantCode: 'dlr_north',
        externalId: 'agent_001',
        name: '陈晓',
        note: '华北经销商坐席',
      },
      {
        tenantCode: 'dlr_south',
        externalId: 'agent_002',
        name: '刘悦',
        note: '华南经销商坐席',
      },
    ],
  },
]

export function LoginPage() {
  const { session, login, logout } = useAuth()
  const navigate = useNavigate()
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleLogin(account: DemoAccount) {
    const key = `${account.tenantCode}:${account.externalId}`
    setBusyKey(key)
    setError(null)
    try {
      const result = await login(account.tenantCode, account.externalId)
      navigate(result.role === 'customer' ? '/app' : '/staff', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '登录失败')
    } finally {
      setBusyKey(null)
    }
  }

  function enterCurrent() {
    if (!session) return
    navigate(session.profile.role === 'customer' ? '/app' : '/staff', { replace: true })
  }

  return (
    <div className="login-page">
      <div className="login-orbit login-orbit-one" />
      <div className="login-orbit login-orbit-two" />
      <div className="login-card">
        <section className="login-hero">
          <div className="brand-mark">
            <BookOpen size={23} />
          </div>
          <p className="eyebrow">学伴智能客服</p>
          <h1>
            让每一次服务
            <br />
            都有上下文
          </h1>
          <p className="login-lead">
            家长端查订单、物流、设备与报修；坐席端接住 AI 转来的每一个工单。
            演示环境已接通真实后端接口。
          </p>
          <ul className="login-points">
            <li>
              <Sparkles size={16} /> AI 先答，必要时转人工
            </li>
            <li>
              <ShieldCheck size={16} /> 工单、设备、订单同屏可见
            </li>
            <li>
              <Headphones size={16} /> 坐席回复与结单闭环
            </li>
          </ul>
          <span className="login-version">Phase 1 · 演示登录</span>
        </section>

        <section className="login-accounts">
          <div className="login-accounts-head">
            <div>
              <p className="eyebrow">DEMO ACCOUNTS</p>
              <h2>选择演示身份</h2>
            </div>
            {session ? (
              <button className="ghost-button" type="button" onClick={logout}>
                <LogOut size={15} /> 退出
              </button>
            ) : null}
          </div>

          {session ? (
            <div className="current-session">
              <div className="current-session-main">
                <span className="avatar avatar-md avatar-blue">
                  {session.profile.name.slice(0, 1)}
                </span>
                <div>
                  <strong>{session.profile.name}</strong>
                  <span>
                    {session.profile.role === 'customer' ? '家长端' : '坐席端'} ·{' '}
                    {session.profile.tenant_code}
                  </span>
                </div>
              </div>
              <button className="primary-button compact" type="button" onClick={enterCurrent}>
                继续进入 <ArrowRight size={16} />
              </button>
            </div>
          ) : null}

          {error ? <div className="inline-error">{error}</div> : null}

          {DEMO_GROUPS.map((group) => (
            <div className="demo-group" key={group.title}>
              <div className="demo-group-title">
                <group.icon size={15} />
                {group.title}
              </div>
              <div className="demo-account-list">
                {group.accounts.map((account) => {
                  const key = `${account.tenantCode}:${account.externalId}`
                  const busy = busyKey === key
                  return (
                    <button
                      key={key}
                      type="button"
                      className="demo-account"
                      disabled={busyKey !== null}
                      onClick={() => void handleLogin(account)}
                    >
                      <span className="avatar avatar-sm avatar-soft">
                        {account.name.slice(0, 1)}
                      </span>
                      <span className="demo-account-copy">
                        <strong>{account.name}</strong>
                        <small>{account.note}</small>
                      </span>
                      <span className="demo-account-tenant">{account.tenantCode}</span>
                      {busy ? (
                        <Loader2 className="spin" size={16} />
                      ) : (
                        <ArrowRight size={16} />
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
          <p className="login-hint">
            演示环境通过 <code>/api/v1/auth/demo-token</code> 换取 JWT；正式环境替换为统一登录。
          </p>
        </section>
      </div>
    </div>
  )
}
