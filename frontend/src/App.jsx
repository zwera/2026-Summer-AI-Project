import { useState } from 'react'
import Header from './components/Header.jsx'
import StepIndicator from './components/StepIndicator.jsx'
import SituationInputStep from './components/SituationInputStep.jsx'
import ClarifyStep from './components/ClarifyStep.jsx'
import ResultStep from './components/ResultStep.jsx'
import './App.css'

const STEPS = [
  { key: 'input', label: '상황 입력' },
  { key: 'clarify', label: '핵심 확인' },
  { key: 'result', label: '근거·보고서' },
]

function App() {
  const [stepIndex, setStepIndex] = useState(0)
  // history: [{role: 'user'|'assistant', content: string}]
  const [history, setHistory] = useState([])
  const [category, setCategory] = useState(null)
  const [situation, setSituation] = useState('')
  const [analysis, setAnalysis] = useState(null)

  function goToStep(key) {
    const idx = STEPS.findIndex((s) => s.key === key)
    if (idx >= 0) setStepIndex(idx)
  }

  function handleReset() {
    setStepIndex(0)
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
        onStepClick={(idx) => {
          // 완료된 단계로만 뒤로가기 허용 (앞으로 건너뛰기는 막음)
          if (idx <= stepIndex) setStepIndex(idx)
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
            onBack={() => goToStep('input')}
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
