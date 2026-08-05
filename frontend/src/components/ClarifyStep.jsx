import { useState } from 'react'
import { postChat } from '../api/client.js'
import './ClarifyStep.css'

function ClarifyStep({ history, setHistory, onBack, onSufficient }) {
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const lastAssistant = [...history]
    .reverse()
    .find((turn) => turn.role === 'assistant')

  // 부족한 확인 항목 목록은 마지막 assistant 응답에는 없으므로,
  // ChatResponse 원본을 저장해두지 않고 재요청 시 다시 받는다.
  async function handleSubmit() {
    const trimmed = answer.trim()
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
      setAnswer('')

      if (res.sufficient) {
        onSufficient({
          situationSummary: res.situation_summary || trimmed,
          category: res.category,
        })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="clarify-step">
      <div className="card">
        <div className="clarify-step__header">
          <h2 className="card__title">핵심 확인이 필요합니다</h2>
          <span className="badge badge--orange">근거 충족도: 확인 필요</span>
        </div>

        <div className="clarify-step__thread">
          {history.map((turn, idx) => (
            <div
              key={idx}
              className={`clarify-bubble clarify-bubble--${turn.role}`}
            >
              <span className="clarify-bubble__role">
                {turn.role === 'user' ? '나' : 'AI'}
              </span>
              <p>{turn.content}</p>
            </div>
          ))}
        </div>

        {lastAssistant && (
          <div className="clarify-step__question">
            <strong>Q.</strong> {lastAssistant.content}
          </div>
        )}

        <textarea
          className="clarify-step__answer"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="추가 정보를 입력하세요"
          rows={3}
        />

        {error && <p className="situation-step__error">{error}</p>}

        <div className="clarify-step__actions">
          <button type="button" className="btn btn--ghost" onClick={onBack}>
            ← 상황 다시 입력
          </button>
          <button
            type="button"
            className="btn btn--primary btn--lg"
            onClick={handleSubmit}
            disabled={!answer.trim() || loading}
          >
            {loading ? '확인 중…' : '답변 제출'}
          </button>
        </div>
      </div>
    </section>
  )
}

export default ClarifyStep
