import './Header.css'

function todayLabel() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}.${m}.${d}`
}

function Header() {
  return (
    <header className="app-header">
      <div className="app-header__brand">
        <span className="app-header__badge" aria-hidden="true">
          <img src="/icons/main_icon.jpg" alt="" />
        </span>
        <h1 className="app-header__title">현장 법률 판단 지원</h1>
      </div>
      <div className="app-header__meta">
        <span className="app-header__date">데이터 기준 {todayLabel()}</span>
        <span className="app-header__data-tag">판례 DB 연동</span>
      </div>
    </header>
  )
}

export default Header
