import './FactDiffList.css'

function FactDiffList({ diffs = [] }) {
  if (diffs.length === 0) return null

  return (
    <div className="card fact-diff-list">
      <h2 className="card__title">🔍 사실관계 비교 (Diff)</h2>
      <table className="fact-diff-list__table">
        <thead>
          <tr>
            <th>항목</th>
            <th>현재 상황</th>
            <th>판례 사실관계</th>
          </tr>
        </thead>
        <tbody>
          {diffs.map((d, idx) => (
            <tr
              key={idx}
              className={d.is_critical ? 'fact-diff-list__row--critical' : ''}
            >
              <td className="fact-diff-list__point">
                {d.is_critical && (
                  <span className="fact-diff-list__warn" title="핵심 차이">
                    ⚠
                  </span>
                )}
                {d.point}
              </td>
              <td>{d.user_situation}</td>
              <td>{d.precedent_fact}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default FactDiffList
