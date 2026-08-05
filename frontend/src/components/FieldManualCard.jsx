import { DEFAULT_FIELD_MANUAL, FIELD_MANUALS } from '../constants/taxonomy.js'
import './FieldManualCard.css'

/**
 * 상황 입력 화면 하단에 표시되는 "현장 판단 요약" 카드.
 * AI 분석 전, 경찰관이 현장에서 즉시 참고할 수 있는 기초 매뉴얼(우선 조치)을
 * 보여준다. 선택된 "빠른 상황 선택" 칩에 맞는 매뉴얼을 보여주고, 선택이 없으면
 * 기본 매뉴얼을 보여준다. 법적 판단을 대체하지 않는다는 점을 명시한다.
 */
function FieldManualCard({ activeKey }) {
  const manual = (activeKey && FIELD_MANUALS[activeKey]) || DEFAULT_FIELD_MANUAL

  return (
    <div className="field-manual-card">
      <div className="field-manual-card__head">
        <h3 className="field-manual-card__title">현장 판단 요약</h3>
        <span className="badge badge--orange">근거 충족도: 확인 필요</span>
      </div>

      <div className="field-manual-card__body">
        <div className="field-manual-card__badge" aria-hidden="true">
          🛡️
          <span>우선 조치</span>
        </div>

        <ol className="field-manual-card__steps">
          {manual.steps.map((step, idx) => (
            <li key={idx}>
              <span className="field-manual-card__num">{idx + 1}</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>

      <p className="field-manual-card__disclaimer">
        ※ {manual.title} · 현장 즉시 참고용 기초 절차이며, 법적 판단은 아래
        &apos;판단 근거 확인&apos; 결과를 따르세요.
      </p>
    </div>
  )
}

export default FieldManualCard
