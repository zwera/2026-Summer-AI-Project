import './ComparisonView.css'

function PrecedentCard({ p }) {
  return (
    <div className="precedent-card">
      <div className="precedent-card__head">
        <span className="badge badge--blue">{p.similarity}% 유사</span>
        <span className="precedent-card__case-no">{p.case_no}</span>
      </div>
      <p className="precedent-card__title">{p.title}</p>
      <p className="precedent-card__meta">
        {p.court} · {p.date}
      </p>
      <p className="precedent-card__snippet">{p.summary_snippet}</p>
      {p.source_link && (
        <a
          className="precedent-card__link"
          href={p.source_link}
          target="_blank"
          rel="noopener noreferrer"
        >
          📖 판례 원문 보기 ↗
        </a>
      )}
    </div>
  )
}

function ComparisonView({ lawfulExamples = [], unlawfulExamples = [] }) {
  if (lawfulExamples.length === 0 && unlawfulExamples.length === 0) return null

  return (
    <div className="card comparison-view">
      <h2 className="card__title">📊 시나리오 비교</h2>
      <div className="comparison-view__cols">
        <div className="comparison-view__col comparison-view__col--lawful">
          <h3>
            <span className="badge badge--green">적법 사례</span>
          </h3>
          {lawfulExamples.length > 0 ? (
            lawfulExamples.map((p) => <PrecedentCard key={p.id} p={p} />)
          ) : (
            <p className="comparison-view__empty">해당 사례 없음</p>
          )}
        </div>
        <div className="comparison-view__col comparison-view__col--unlawful">
          <h3>
            <span className="badge badge--red">위법 사례</span>
          </h3>
          {unlawfulExamples.length > 0 ? (
            unlawfulExamples.map((p) => <PrecedentCard key={p.id} p={p} />)
          ) : (
            <p className="comparison-view__empty">해당 사례 없음</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default ComparisonView
