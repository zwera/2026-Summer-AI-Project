import { useRef, useState } from 'react'
import { postFactCheck } from '../api/client.js'
import './SelectionPopover.css'

/**
 * 자식 영역 내에서 텍스트를 드래그 선택하면 '재검토(Fact-Check)' / '자세히 설명'
 * 버튼이 담긴 팝오버를 보여주는 컨테이너.
 */
function SelectionPopover({ situation, children }) {
  const containerRef = useRef(null)
  const [popover, setPopover] = useState(null) // {x, y, text}
  const [result, setResult] = useState(null) // {mode, text, answer} | {mode, text, loading} | {mode, text, error}

  function handleMouseUp() {
    const selection = window.getSelection()
    const text = selection ? selection.toString().trim() : ''

    if (!text || !containerRef.current) {
      setPopover(null)
      return
    }

    const range = selection.getRangeAt(0)
    if (!containerRef.current.contains(range.commonAncestorContainer)) {
      setPopover(null)
      return
    }

    const rect = range.getBoundingClientRect()
    const containerRect = containerRef.current.getBoundingClientRect()
    setPopover({
      x: rect.left - containerRect.left + rect.width / 2,
      y: rect.top - containerRect.top,
      text,
    })
  }

  async function handleAction(mode) {
    const selectedText = popover.text
    setPopover(null)
    setResult({ mode, text: selectedText, loading: true })

    try {
      const res = await postFactCheck({
        situation,
        selected_text: selectedText,
        mode,
      })
      setResult({ mode, text: selectedText, answer: res.result })
    } catch (err) {
      setResult({ mode, text: selectedText, error: err.message })
    }
  }

  return (
    <div
      className="selection-popover-root"
      ref={containerRef}
      onMouseUp={handleMouseUp}
    >
      {children}

      {popover && (
        <div
          className="selection-popover"
          style={{ left: popover.x, top: popover.y }}
        >
          <button type="button" onClick={() => handleAction('fact_check')}>
            🔎 재검토
          </button>
          <button type="button" onClick={() => handleAction('explain')}>
            💡 자세히 설명
          </button>
        </div>
      )}

      {result && (
        <div className="selection-result-overlay" onClick={() => setResult(null)}>
          <div
            className="selection-result"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="selection-result__head">
              <strong>
                {result.mode === 'fact_check' ? '🔎 재검토 결과' : '💡 자세히 설명'}
              </strong>
              <button
                type="button"
                className="selection-result__close"
                onClick={() => setResult(null)}
              >
                ✕
              </button>
            </div>
            <p className="selection-result__quote">&ldquo;{result.text}&rdquo;</p>
            {result.loading && <p className="selection-result__loading">확인 중…</p>}
            {result.error && (
              <p className="situation-step__error">{result.error}</p>
            )}
            {result.answer && (
              <p className="selection-result__answer">{result.answer}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default SelectionPopover
