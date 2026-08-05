import { useState } from 'react'
import { postChat } from '../api/client.js'
import { QUICK_SITUATIONS } from '../constants/taxonomy.js'
import './SituationInputStep.css'

const MAX_LEN = 500

function SituationInputStep({
  history,
  setHistory,
  onSufficient,
  onNeedsClarify,
}) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function applyQuickTemplate(template) {
    setText((prev) => (prev ? `${prev} ${template}` : template))
  }

  async function handleSubmit() {
    const trimmed = text.trim()
    if (!trimmed || loading) return
    setError(null)
    setLoading(true)
    const nextHistory = [...history, { role: 'user', content: trimmed }]
    setHistory(nextHistory)

    try {
      const res = await postChat(nextHistory)
      const withAssistant = [
        ...nextHistory,
        {
          role: 'assistant',
          content: res.sufficient
            ? res.situation_summary || '상황 확인이 완료되었습니다.'
            : res.follow_up_question || '추가 확인이 필요합니다.',
        },
      ]
      setHistory(withAssistant)

      if (res.sufficient) {
        onSufficient({
          situationSummary: res.situation_summary || trimmed,
          category: res.category,
        })
      } else {
        onNeedsClarify()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="situation-step">
      <div className="card">
        <h2 className="card__title">현재 상황을 입력하세요</h2>
        <div className="situation-step__textarea-wrap">
          <textarea
            className="situation-step__textarea"
            value={text}
            maxLength={MAX_LEN}
            placeholder="예) 주취자가 편의점 앞에서 행인을 밀치고 욕설하며 귀가를 거부합니다."
            onChange={(e) => setText(e.target.value)}
            rows={4}
          />
          <span className="situation-step__counter">
            {text.length} / {MAX_LEN}
          </span>
        </div>

        <p className="situation-step__section-label">빠른 상황 선택</p>
        <div className="situation-step__quick-grid">
          {QUICK_SITUATIONS.map((q) => (
            <button
              key={q.key}
              type="button"
              className="quick-chip"
              onClick={() => applyQuickTemplate(q.template)}
            >
              <span className="quick-chip__icon" aria-hidden="true">
                {q.icon}
              </span>
              {q.label}
            </button>
          ))}
        </div>

        <div className="situation-step__actions">
          <button
            type="button"
            className="btn btn--primary btn--lg"
            onClick={handleSubmit}
            disabled={!text.trim() || loading}
          >
            {loading ? '분석 중…' : '🔍 판단 근거 확인'}
          </button>
          <button
            type="button"
            className="btn btn--outline btn--lg"
            disabled
            title="음성 입력은 준비 중입니다"
          >
            🎤 음성으로 입력
          </button>
        </div>

        {error && <p className="situation-step__error">{error}</p>}

        <p className="situation-step__privacy">
          🔒 개인정보(이름·주민번호·연락처·주소 등) 입력 금지
        </p>
      </div>
    </section>
  )
}

export default SituationInputStep
