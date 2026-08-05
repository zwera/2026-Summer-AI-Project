import { useState } from 'react'
import './ConclusionCard.css'

const VERDICT_STYLE = {
  적법: 'green',
  '위법 가능성 있음': 'orange',
  '위법 가능성 높음': 'red',
  '판단 보류': 'gray',
}

function ConclusionCard({ verdict, summary }) {
  const [expanded, setExpanded] = useState(false)
  const style = VERDICT_STYLE[verdict.verdict] || 'gray'

  return (
    <div className={`conclusion-card conclusion-card--${style}`}>
      <div className="conclusion-card__head">
        <span className="conclusion-card__verdict">{verdict.verdict}</span>
        <span className="conclusion-card__disclaimer">
          ⚠ 상급심에서 결론이 달라질 수 있습니다
        </span>
      </div>

      <p className="conclusion-card__three-line">{summary.three_line}</p>

      <button
        type="button"
        className="conclusion-card__toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        {expanded ? '상세 근거 접기 ▲' : '상세 근거 보기 ▼'}
      </button>

      {expanded && (
        <div className="conclusion-card__detail">
          <h3>판단 근거</h3>
          <p>{verdict.reasoning}</p>

          <h3>10줄 요약 (보고서용)</h3>
          <p className="conclusion-card__pre">{summary.ten_line}</p>

          <h3>전문 (법적 다툼 대비)</h3>
          <p className="conclusion-card__pre">{summary.full_text}</p>
        </div>
      )}
    </div>
  )
}

export default ConclusionCard
