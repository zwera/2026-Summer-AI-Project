import { useState } from 'react'
import './Timeline.css'

function Timeline({ events = [] }) {
  const [copiedOrder, setCopiedOrder] = useState(null)

  if (events.length === 0) return null

  const sorted = [...events].sort((a, b) => a.order - b.order)

  function handleCopy(evt) {
    const text = `${evt.timestamp_label} - ${evt.description}${
      evt.legal_issue ? ` (쟁점: ${evt.legal_issue})` : ''
    }`
    navigator.clipboard?.writeText(text)
    setCopiedOrder(evt.order)
    setTimeout(() => setCopiedOrder(null), 1500)
  }

  return (
    <div className="card timeline">
      <h2 className="card__title">🕐 사건 타임라인</h2>
      <ol className="timeline__list">
        {sorted.map((evt) => (
          <li key={evt.order} className="timeline__item">
            <div className="timeline__marker" aria-hidden="true" />
            <div className="timeline__body">
              <div className="timeline__row">
                <span className="timeline__label">{evt.timestamp_label}</span>
                <button
                  type="button"
                  className="timeline__copy"
                  onClick={() => handleCopy(evt)}
                >
                  {copiedOrder === evt.order ? '복사됨 ✓' : '복사'}
                </button>
              </div>
              <p className="timeline__desc">{evt.description}</p>
              {evt.legal_issue && (
                <span className="badge badge--orange timeline__issue">
                  쟁점: {evt.legal_issue}
                </span>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default Timeline
