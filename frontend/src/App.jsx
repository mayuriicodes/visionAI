import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import DetectionPage from './DetectionPage.jsx'
import ClassificationPage from './ClassificationPage.jsx'
import HistoryPage from './HistoryPage.jsx'

const navigation = [
  { label: 'Overview', path: '/dashboard', icon: 'grid' },
  { label: 'Object detection', path: '/dashboard/detection', icon: 'scan' },
  { label: 'Image classification', path: '/dashboard/xray', icon: 'image' },
  { label: 'History', path: '/dashboard/history', icon: 'clock' },
]

function Icon({ name, size = 20 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
    scan: <><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" /><path d="M8 12h8M12 8v8" /></>,
    image: <><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M5 21v-2a7 7 0 0 1 14 0v2" /></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3" /><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" /></>,
    arrow: <><path d="M7 17 17 7M7 7h10v10" /></>,
    activity: <><path d="M3 12h4l3-8 4 16 3-8h4" /></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
    spark: <><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-2-5.8L4 11l6-2.2L12 3Z" /><path d="m19 14 1 2.5 2 1-2 1-1 2.5-1-2.5-2-1 2-1 1-2.5Z" /></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  }

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name] ?? paths.spark}
    </svg>
  )
}

function Brand({ compact = false }) {
  return (
    <span className={`brand ${compact ? 'brand-compact' : ''}`}>
      <span className="brand-mark"><span /></span>
      <span>vision<span className="brand-accent">ai</span></span>
    </span>
  )
}

function AuthPage({ mode, navigate }) {
  const isSignup = mode === 'signup'
  const [values, setValues] = useState({ name: '', email: '', password: '', confirmPassword: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function update(event) {
    setValues((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (isSignup && values.password !== values.confirmPassword) {
      setError('Your passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      if (isSignup) {
        await api.register({ name: values.name, email: values.email, password: values.password })
      } else {
        await api.login({ email: values.email, password: values.password })
      }
      navigate('/dashboard')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-story">
        <div className="auth-story-inner">
          <a className="brand-link" href="/" onClick={(event) => { event.preventDefault(); navigate('/login') }}>
            <Brand />
          </a>
          <div className="story-content">
            <div className="eyebrow"><span className="eyebrow-dot" /> GENERAL-PURPOSE IMAGE ANALYSIS</div>
            <h1>Clarity for every<br /><span>image.</span></h1>
            <p>A focused workspace for computer vision. Detect objects and classify everyday images in one thoughtful, secure space.</p>
            <div className="story-visual" aria-hidden="true">
              <div className="visual-orbit orbit-one" />
              <div className="visual-orbit orbit-two" />
              <div className="visual-glow" />
              <div className="visual-cross"><span /><i /></div>
              <div className="visual-caption"><span className="caption-pulse" /> VISION SYSTEM <b>READY</b></div>
              <div className="visual-coordinates">34° 03' 08.4" N<br />118° 14' 37.2" W</div>
            </div>
          </div>
          <div className="auth-footer"><span>© 2026 VisionAI</span><span>Secure workspace <Icon name="shield" size={15} /></span></div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-mobile-brand"><Brand /></div>
        <div className="auth-form-wrap">
          <div className="auth-form-heading">
            <p className="form-kicker">{isSignup ? 'GET STARTED' : 'WELCOME BACK'}</p>
            <h2>{isSignup ? 'Create your account' : 'Sign in to your account'}</h2>
            <p>{isSignup ? 'Your workspace for clearer insights starts here.' : 'Enter your details to access your workspace.'}</p>
          </div>
          <form className="auth-form" onSubmit={submit}>
            {isSignup && (
              <label className="field">
                <span>Full name</span>
                <input autoComplete="name" name="name" onChange={update} placeholder="e.g. Alex Morgan" required value={values.name} />
              </label>
            )}
            <label className="field">
              <span>Email address</span>
              <input autoComplete="email" name="email" onChange={update} placeholder="you@organization.com" required type="email" value={values.email} />
            </label>
            <label className="field">
              <span>Password</span>
              <input autoComplete={isSignup ? 'new-password' : 'current-password'} minLength={isSignup ? 8 : undefined} name="password" onChange={update} placeholder={isSignup ? 'At least 8 characters' : 'Enter your password'} required type="password" value={values.password} />
            </label>
            {isSignup && (
              <label className="field">
                <span>Confirm password</span>
                <input autoComplete="new-password" minLength={8} name="confirmPassword" onChange={update} placeholder="Re-enter your password" required type="password" value={values.confirmPassword} />
              </label>
            )}
            {error && <div className="form-error" role="alert">{error}</div>}
            <button className="button button-primary auth-submit" disabled={submitting} type="submit">
              {submitting ? 'Please wait…' : isSignup ? 'Create account' : 'Sign in'}
              {!submitting && <span className="button-arrow"><Icon name="arrow" size={17} /></span>}
            </button>
          </form>
          <p className="auth-switch">
            {isSignup ? 'Already have an account?' : 'New to VisionAI?'}{' '}
            <a href={isSignup ? '/login' : '/signup'} onClick={(event) => { event.preventDefault(); navigate(isSignup ? '/login' : '/signup') }}>
              {isSignup ? 'Sign in' : 'Create an account'}
            </a>
          </p>
          <p className="privacy-note"><Icon name="shield" size={15} /> Your account is protected with secure, encrypted authentication.</p>
        </div>
      </section>
    </main>
  )
}

function Sidebar({ path, user, navigate, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const link = (to) => (event) => {
    event.preventDefault()
    navigate(to)
    setMenuOpen(false)
  }

  return (
    <>
      <button aria-label="Toggle navigation" className="mobile-menu-toggle" onClick={() => setMenuOpen((open) => !open)} type="button"><Icon name="menu" /></button>
      {menuOpen && <button aria-label="Close navigation" className="sidebar-backdrop" onClick={() => setMenuOpen(false)} type="button" />}
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <a className="sidebar-brand" href="/dashboard" onClick={link('/dashboard')}><Brand /></a>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map((item) => (
            <a aria-current={path === item.path ? 'page' : undefined} className={`nav-link ${path === item.path ? 'nav-active' : ''}`} href={item.path} key={item.path} onClick={link(item.path)}>
              <Icon name={item.icon} size={19} /><span>{item.label}</span>
              {item.path === '/dashboard' && <span className="nav-indicator" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="workspace-status"><span className="status-light" /><span><b>Workspace active</b><small>Private and secure</small></span></div>
          <div className="sidebar-divider" />
          <a className={`profile-link ${path === '/dashboard/profile' ? 'nav-active' : ''}`} href="/dashboard/profile" onClick={link('/dashboard/profile')}>
            <span className="avatar">{user.name.trim().charAt(0).toUpperCase()}</span>
            <span className="profile-copy"><b>{user.name}</b><small>{user.email}</small></span>
            <span className="profile-menu-dot">···</span>
          </a>
          <button className="logout-button" onClick={onLogout} type="button"><Icon name="logout" size={17} /> Sign out</button>
        </div>
      </aside>
    </>
  )
}

function StatCard({ title, value, detail, icon, accent, period = 'ALL TIME' }) {
  return (
    <article className="stat-card">
      <div className="stat-top"><span className={`stat-icon ${accent}`}><Icon name={icon} size={20} /></span><span className="stat-period">{period}</span></div>
      <p className="stat-title">{title}</p>
      <div className="stat-bottom"><span className="stat-value">{value.toLocaleString()}</span><span className="stat-detail">{detail}</span></div>
    </article>
  )
}

function formatActivity(activity) {
  const date = new Date(activity.created_at)
  return {
    date: Number.isNaN(date.getTime()) ? activity.created_at : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date),
  }
}

function Overview({ dashboard, user, navigate }) {
  return (
    <>
      <div className="page-heading">
        <div><p className="page-kicker">YOUR WORKSPACE</p><h1>Good to see you, {user.name.split(' ')[0]}<span className="greeting-dot">.</span></h1><p className="page-subtitle">Here’s an overview of your imaging activity.</p></div>
        <div className="date-chip"><span className="date-chip-dot" /> YOUR PERSONAL WORKSPACE</div>
      </div>
      <section aria-label="Analysis totals" className="stats-grid">
        <StatCard title="Object detection runs" value={dashboard.total_object_detection_runs} detail="saved analyses" icon="scan" accent="cyan" />
        <StatCard title="Image classifications" value={dashboard.total_image_classifications} detail="saved analyses" icon="image" accent="purple" />
        <StatCard title="Images processed" value={dashboard.total_images_processed} detail="tracked source images" icon="grid" accent="blue" />
        <StatCard title="Recent activity" value={dashboard.recent_activity_count} detail="latest results" icon="clock" accent="green" period="LATEST" />
      </section>
      <section className="dashboard-lower">
        <article className="panel activity-panel">
          <div className="panel-heading"><div><p className="section-eyebrow">YOUR WORKSPACE</p><h2>Recent activity</h2></div><span className="activity-count">{dashboard.recent_activity_count} {dashboard.recent_activity_count === 1 ? 'event' : 'events'}</span></div>
          {dashboard.recent_results.length ? (
            <div className="activity-list">
              {dashboard.recent_results.map((activity) => {
                const formatted = formatActivity(activity)
                const isDetection = activity.type === 'detection'
                return (
                  <div className="activity-item" key={`${activity.type}-${activity.result_id}`}>
                    <span className={`activity-icon ${isDetection ? 'activity-cyan' : 'activity-purple'}`}>
                      <Icon name={isDetection ? 'scan' : 'image'} size={17} />
                    </span>
                    <span className="activity-copy">
                      <b>{isDetection ? 'Object detection' : 'Image classification'}</b>
                      <small title={`${activity.original_filename} · ${activity.summary}`}>{activity.original_filename} · {activity.summary}</small>
                    </span>
                    <time dateTime={activity.created_at}>{formatted.date}</time>
                    <button
                      aria-label={`View ${isDetection ? 'detection' : 'classification'} result for ${activity.original_filename}`}
                      className="activity-result-link"
                      onClick={() => navigate(`/dashboard/history?type=${activity.type}&id=${activity.result_id}`)}
                      type="button"
                    >
                      View result <Icon name="arrow" size={14} />
                    </button>
                  </div>
                )
              })}
            </div>
          ) : <div className="empty-activity"><span className="empty-symbol"><Icon name="activity" size={23} /></span><b>No activity yet</b><span>Your completed analyses will appear here.</span></div>}
        </article>
        <article className="panel quick-panel">
          <div className="panel-heading"><div><p className="section-eyebrow">GET STARTED</p><h2>Analysis tools</h2></div><span className="panel-spark"><Icon name="spark" size={18} /></span></div>
          <button className="tool-link" onClick={() => navigate('/dashboard/detection')} type="button"><span className="tool-icon tool-cyan"><Icon name="scan" /></span><span><b>Object detection</b><small>Explore image analysis</small></span><Icon name="arrow" size={17} /></button>
          <button className="tool-link" onClick={() => navigate('/dashboard/xray')} type="button"><span className="tool-icon tool-purple"><Icon name="image" /></span><span><b>Image classification</b><small>Rank common image categories</small></span><Icon name="arrow" size={17} /></button>
          <div className="tools-note"><Icon name="shield" size={16} /><span>Model predictions are estimates and are not guaranteed.</span></div>
        </article>
      </section>
      <footer className="dashboard-footer"><span>VISIONAI <i>·</i> COMPUTER VISION WORKSPACE</span><span>All activity is private to your account</span></footer>
    </>
  )
}

function Profile({ user }) {
  return <><div className="page-heading"><div><p className="page-kicker">ACCOUNT</p><h1>Your profile</h1><p className="page-subtitle">Manage your VisionAI workspace identity.</p></div></div><section className="panel profile-panel"><span className="profile-avatar-large">{user.name.trim().charAt(0).toUpperCase()}</span><div><p className="section-eyebrow">PROFILE DETAILS</p><h2>{user.name}</h2><p>{user.email}</p><span className="profile-secure"><Icon name="shield" size={15} /> Secure account</span></div></section></>
}

function Dashboard({ path, user, dashboard, navigate, onLogout }) {
  return (
    <div className="app-shell">
      <Sidebar path={path} user={user} navigate={navigate} onLogout={onLogout} />
      <main className="main-content">
        <header className="topbar"><div className="breadcrumb"><span>Workspace</span><i>/</i><b>{path === '/dashboard' ? 'Overview' : path.endsWith('/profile') ? 'Profile' : path.endsWith('/history') ? 'History' : path.endsWith('/xray') ? 'Image classification' : 'Object detection'}</b></div><div className="topbar-user"><span className="online-indicator" /> All systems operational <span className="topbar-avatar">{user.name.trim().charAt(0).toUpperCase()}</span></div></header>
        <div className="dashboard-content">
          {path === '/dashboard' && dashboard && <Overview dashboard={dashboard} user={user} navigate={navigate} />}
          {path === '/dashboard/detection' && <DetectionPage />}
          {path === '/dashboard/profile' && <Profile user={user} />}
          {path === '/dashboard/history' && <HistoryPage />}
          {path === '/dashboard/xray' && <ClassificationPage />}
        </div>
      </main>
    </div>
  )
}

function App() {
  const [path, setPath] = useState(window.location.pathname)
  const [user, setUser] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [loadedKey, setLoadedKey] = useState('')
  const [loadError, setLoadError] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const requestKey = `${path}:${retryCount}`
  const loading = path.startsWith('/dashboard') && loadedKey !== requestKey
  const currentLoadError = loadError?.key === requestKey ? loadError.message : ''

  const navigate = useCallback((nextPath) => {
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, '', nextPath)
    }
    setPath(nextPath)
  }, [])

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    if (!path.startsWith('/dashboard')) {
      return undefined
    }

    let active = true
    async function loadProtectedPage() {
      try {
        const currentUser = await api.me()
        const workspace = path === '/dashboard' ? await api.dashboard() : null
        if (active) {
          setUser(currentUser)
          setDashboard(workspace)
          setLoadError(null)
          setLoadedKey(requestKey)
        }
      } catch (error) {
        if (!active) return
        if (error instanceof Error && error.status === 401) {
          navigate('/login')
          return
        }
        setLoadError({
          key: requestKey,
          message: error instanceof Error ? error.message : 'Unable to load your workspace.',
        })
        setLoadedKey(requestKey)
      }
    }
    void loadProtectedPage()
    return () => { active = false }
  }, [path, navigate, requestKey])

  async function logout() {
    try {
      await api.logout()
      setUser(null)
      setDashboard(null)
      navigate('/login')
    } catch (error) {
      setLoadError({
        key: requestKey,
        message: error instanceof Error ? error.message : 'Unable to sign out.',
      })
    }
  }

  if (path === '/' || path === '/signup' || path === '/login') {
    return <AuthPage mode={path === '/signup' ? 'signup' : 'login'} navigate={navigate} />
  }

  if (!path.startsWith('/dashboard')) {
    navigate('/login')
    return null
  }
  if (loading) return <main className="loading-screen"><Brand /><span className="loading-ring" /><p>Opening your secure workspace…</p></main>
  if (currentLoadError) return <main className="loading-screen"><Brand /><p className="load-error">{currentLoadError}</p><button className="button button-primary" onClick={() => setRetryCount((count) => count + 1)} type="button">Try again</button></main>
  if (!user) return <main className="loading-screen"><Brand /><span className="loading-ring" /><p>Redirecting to sign in…</p></main>

  const normalizedPath = path.split('?')[0]
  return <Dashboard path={normalizedPath} user={user} dashboard={dashboard} navigate={navigate} onLogout={logout} />
}

export default App
