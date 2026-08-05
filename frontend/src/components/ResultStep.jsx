import { useEffect, useState } from 'react'
import { postAnalysis } from '../api/client.js'
import { categoryLabel } from '../constants/taxonomy.js'
import ConclusionCard from './ConclusionCard.jsx'
import SummaryGrid from './SummaryGrid.jsx'
import RiskBadges from './RiskBadges.jsx'
import ComparisonView from './ComparisonView.jsx'
import FactDiffList from './FactDiffList.jsx'
import Timeline from './Timeline.jsx'
import SelectionPopover from './SelectionPopover.jsx'
import './ResultStep.css'

function ResultStep({ situation, category, analysis, setAnalysis, onRestart }) {
  const [loading, setLoading] = useState(!analysis)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (analysis || !situation) return
    let cancelled = false

    postAnalysis({ situation, category, top_k: 5 })
      .then((res) => {
        if (!cancelled) setAnalysis(res)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [situation])

  function handleCopyReport() {
    if (!analysis) return
    const text = [
      `[사건 개요]\n${analysis.situation}`,
      `[적법성 판단] ${analysis.verdict.verdict}\n${analysis.verdict.reasoning}`,
      `[10줄 요약]\n${analysis.summary.ten_line}`,
    ].join('\n\n')
    navigator.clipboard?.writeText(text)
    alert('보고서 초안이 클립보드에 복사되었습니다.')
  }

  if (loading) {
    return (
      <section className="result-step">
        <div className="card result-step__loading">
          <div className="spinner" aria-hidden="true" />
          <p>판례를 검색하고 적법성을 분석하는 중입니다…</p>
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="result-step">
        <div className="card">
          <p className="situation-step__error">분석 중 오류가 발생했습니다: {error}</p>
          <button type="button" className="btn btn--ghost" onClick={onRestart}>
            처음부터 다시 시작
          </button>
        </div>
      </section>
    )
  }

  if (!analysis) return null

  return (
    <SelectionPopover situation={analysis.situation}>
      <section className="result-step">
        <div className="result-step__topline">
          <span className="badge badge--blue">
            {categoryLabel(analysis.category)}
          </span>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onRestart}>
            새 상황 입력
          </button>
        </div>

        <ConclusionCard verdict={analysis.verdict} summary={analysis.summary} />

        <SummaryGrid
          keyCriteria={analysis.verdict.key_criteria}
          factDiffs={analysis.fact_diffs}
          similarPrecedents={analysis.similar_precedents}
        />

        <RiskBadges badges={analysis.risk_badges} />

        <ComparisonView
          lawfulExamples={analysis.lawful_examples}
          unlawfulExamples={analysis.unlawful_examples}
        />

        <FactDiffList diffs={analysis.fact_diffs} />

        <Timeline events={analysis.timeline} />

        <div className="result-step__action-bar">
          <button type="button" className="btn btn--outline">
            📖 판례 원문 보기
          </button>
          <button type="button" className="btn btn--outline">
            👥 상급자 공유
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={handleCopyReport}
          >
            📄 사건보고서 초안 만들기
          </button>
        </div>
      </section>
    </SelectionPopover>
  )
}

export default ResultStep
