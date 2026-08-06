import { useState } from 'react'
import Header from './components/Header.jsx'
import StepIndicator from './components/StepIndicator.jsx'
import SituationInputStep from './components/SituationInputStep.jsx'
import ClarifyStep from './components/ClarifyStep.jsx'
import ResultStep from './components/ResultStep.jsx'
import { useFaviconStatus } from './hooks/useFaviconStatus.js'
import './App.css'

const STEPS = [
  { key: 'input', label: '상황 입력' },
  { key: 'clarify', label: '핵심 확인' },
  { key: 'result', label: '근거·보고서' },
]

function App() {
  // 탭 파비콘: 백엔드 서버가 응답하지 않으면 회색조 아이콘으로 전환
  useFaviconStatus()

  const [stepIndex, setStepIndex] = useState(0)
  // 지금까지 도달한 가장 앞선 단계. 이 값 이하 범위에서는 분석 결과를
  // 유지한 채 자유롭게 앞뒤로 이동할 수 있다 (초기화되지 않음).
  const [maxStepIndex, setMaxStepIndex] = useState(0)
  // history: [{role: 'user'|'assistant', content: string}]
  const [history, setHistory] = useState([])
  const [category, setCategory] = useState(null)
  const [situation, setSituation] = useState('')
  const [analysis, setAnalysis] = useState(null)

  function goToStep(key) {
    const idx = STEPS.findIndex((s) => s.key === key)
    if (idx >= 0) {
      setStepIndex(idx)
      setMaxStepIndex((prev) => Math.max(prev, idx))
    }
  }

  // 상황을 완전히 새로 시작할 때만 호출한다: "상황 다시 입력" 버튼을
  // 누르거나 상황 입력 단계 탭으로 돌아갔을 때.
  function handleReset() {
    setStepIndex(0)
    setMaxStepIndex(0)
    setHistory([])
    setCategory(null)
    setSituation('')
    setAnalysis(null)
  }

  return (
    <>
      <Header />
      <StepIndicator
        steps={STEPS}
        activeIndex={stepIndex}
        maxIndex={maxStepIndex}
        onStepClick={(idx) => {
          // 상황 입력 단계로 돌아가는 경우에만 전체 초기화
          if (idx === 0) {
            handleReset()
            return
          }
          // 이미 도달했던 단계라면 기존 데이터(분석 결과 등)를 유지한 채 이동
          if (idx <= maxStepIndex) setStepIndex(idx)
        }}
      />
      <main className="app-main">
        {STEPS[stepIndex].key === 'input' && (
          <SituationInputStep
            history={history}
            setHistory={setHistory}
            onSufficient={({ situationSummary, category: cat }) => {
              // 이전 분석 결과를 반드시 초기화해야 ResultStep이 새 상황으로
              // 재분석을 수행한다 (그대로 두면 이전 결과가 캐시처럼 남아
              // 재요청이 스킵된다).
              setAnalysis(null)
              setSituation(situationSummary)
              setCategory(cat)
              goToStep('result')
            }}
            onNeedsClarify={() => goToStep('clarify')}
          />
        )}

        {STEPS[stepIndex].key === 'clarify' && (
          <ClarifyStep
            history={history}
            setHistory={setHistory}
            onBack={handleReset}
            onSufficient={({ situationSummary, category: cat }) => {
              setAnalysis(null)
              setSituation(situationSummary)
              setCategory(cat)
              goToStep('result')
            }}
          />
        )}

        {STEPS[stepIndex].key === 'result' && (
          <ResultStep
            situation={situation}
            category={category}
            analysis={analysis}
            setAnalysis={setAnalysis}
            onRestart={handleReset}
          />
        )}
      </main>
    </>
  )
}

export default App
