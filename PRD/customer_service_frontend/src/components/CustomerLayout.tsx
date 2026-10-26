import { Home, Package, Tablet, UserRound } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/app', label: '首页', icon: Home, end: true },
  { to: '/app/orders', label: '订单', icon: Package },
  { to: '/app/devices', label: '设备', icon: Tablet },
  { to: '/app/profile', label: '我的', icon: UserRound },
]

export function CustomerLayout() {
  const { pathname } = useLocation()
  const isChat = pathname.startsWith('/app/chat')
  const hideNav =
    isChat ||
    pathname.startsWith('/app/repairs') ||
    /^\/app\/orders\/[^/]+/.test(pathname)

  return (
    <div className="customer-root">
      <div className="phone-shell">
        <main className={`phone-content ${hideNav ? 'without-nav' : ''} ${isChat ? 'is-chat' : ''}`}>
          <Outlet />
        </main>
        {hideNav ? null : (
          <nav className="bottom-nav">
            {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon size={20} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        )}
      </div>
    </div>
  )
}
