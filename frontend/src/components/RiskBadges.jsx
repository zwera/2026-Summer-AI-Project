import { RISK_LEVEL_LABELS } from '../constants/taxonomy.js'
import './RiskBadges.css'

const LEVEL_STYLE = {
  low: 'gray',
  medium: 'orange',
  high: 'red',
}

function RiskBadges({ badges = [] }) {
  if (badges.length === 0) return null

  return (
    <div className="card risk-badges">
      <h2 className="card__title">⚖ 리스크 요소</h2>
      <div className="risk-badges__list">
        {badges.map((b, idx) => (
          <div
            key={idx}
            className={`risk-badge risk-badge--${LEVEL_STYLE[b.level] || 'gray'}`}
          >
            <div className="risk-badge__top">
              <span className="risk-badge__type">{b.type}</span>
              <span className={`badge badge--${LEVEL_STYLE[b.level] || 'gray'}`}>
                {RISK_LEVEL_LABELS[b.level] || b.level}
              </span>
            </div>
            <p className="risk-badge__desc">{b.description}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

export default RiskBadges
