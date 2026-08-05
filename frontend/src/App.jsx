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
