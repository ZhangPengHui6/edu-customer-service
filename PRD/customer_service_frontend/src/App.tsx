import { useEffect } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import { CustomerLayout } from './components/CustomerLayout'
import { LoginPage } from './pages/LoginPage'
import { ChatPage } from './pages/customer/ChatPage'
import { DevicesPage } from './pages/customer/DevicesPage'
import { HomePage } from './pages/customer/HomePage'
import { OrderDetailPage } from './pages/customer/OrderDetailPage'
import { OrdersPage } from './pages/customer/OrdersPage'
import { ProfilePage } from './pages/customer/ProfilePage'
import { RepairDetailPage } from './pages/customer/RepairDetailPage'
import { RepairsPage } from './pages/customer/RepairsPage'
import { StaffPage } from './pages/staff/StaffPage'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

function Entry() {
  const { session } = useAuth()
  if (!session) return <Navigate to="/login" replace />
  return (
    <Navigate
      to={session.profile.role === 'customer' ? '/app' : '/staff'}
      replace
    />
  )
}

function RequireCustomer() {
  const { session } = useAuth()
  if (!session) return <Navigate to="/login" replace />
  if (session.profile.role !== 'customer') return <Navigate to="/staff" replace />
  return <Outlet />
}

function RequireStaff() {
  const { session } = useAuth()
  if (!session) return <Navigate to="/login" replace />
  if (session.profile.role === 'customer') return <Navigate to="/app" replace />
  return <Outlet />
}

export function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<Entry />} />
        <Route path="/login" element={<LoginPage />} />

        <Route element={<RequireCustomer />}>
          <Route path="/app" element={<CustomerLayout />}>
            <Route index element={<HomePage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="orders/:orderNo" element={<OrderDetailPage />} />
            <Route path="devices" element={<DevicesPage />} />
            <Route path="repairs" element={<RepairsPage />} />
            <Route path="repairs/:repairNo" element={<RepairDetailPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route element={<RequireStaff />}>
          <Route path="/staff" element={<StaffPage />} />
          <Route path="/staff/:handoffId" element={<StaffPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
