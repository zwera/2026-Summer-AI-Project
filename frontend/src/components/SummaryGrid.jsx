import './SummaryGrid.css'

function SummaryGrid({ keyCriteria = [], factDiffs = [], similarPrecedents = [] }) {
  const missingFacts = factDiffs.filter((d) => d.is_critical)
  const topPrecedents = similarPrecedents.slice(0, 3)

  return (
    <div className="summary-grid">
      <div className="summary-grid__col summary-grid__col--green">
        <h3>
          <span className="summary-grid__dot">✓</span> 판단 기준
        </h3>
        <ul>
          {keyCriteria.length > 0 ? (
            keyCriteria.map((c, idx) => <li key={idx}>{c}</li>)
          ) : (
            <li className="summary-grid__empty">해당 없음</li>
          )}
        </ul>
      </div>

      <div className="summary-grid__col summary-grid__col--orange">
        <h3>
          <span className="summary-grid__dot">!</span> 부족한 사실
        </h3>
        <ul>
          {missingFacts.length > 0 ? (
            missingFacts.map((d, idx) => <li key={idx}>{d.point}</li>)
          ) : (
            <li className="summary-grid__empty">핵심 누락 사실 없음</li>
          )}
        </ul>
      </div>

      <div className="summary-grid__col summary-grid__col--blue">
        <h3>
          <span className="summary-grid__dot">⚖</span> 관련 근거
        </h3>
        <ul>
          {topPrecedents.length > 0 ? (
            topPrecedents.map((p) => (
              <li key={p.id}>
                {p.case_no} <span className="summary-grid__muted">({p.similarity}%)</span>
              </li>
            ))
          ) : (
            <li className="summary-grid__empty">관련 판례 없음</li>
          )}
        </ul>
      </div>
    </div>
  )
}

export default SummaryGrid
