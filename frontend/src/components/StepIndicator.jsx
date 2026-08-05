import './StepIndicator.css'

function StepIndicator({ steps, activeIndex, maxIndex = activeIndex, onStepClick }) {
  return (
    <nav className="step-indicator" aria-label="진행 단계">
      {steps.map((step, idx) => {
        const state =
          idx === activeIndex
            ? 'active'
            : idx < activeIndex
              ? 'done'
              : 'upcoming'
        return (
          <div className="step-indicator__item-wrap" key={step.key}>
            <button
              type="button"
              className={`step-indicator__item step-indicator__item--${state}`}
              onClick={() => onStepClick(idx)}
              disabled={idx > maxIndex}
            >
              <span className="step-indicator__circle">{idx + 1}</span>
              <span className="step-indicator__label">{step.label}</span>
            </button>
            {idx < steps.length - 1 && (
              <span className="step-indicator__chevron" aria-hidden="true">
                &gt;
              </span>
            )}
          </div>
        )
      })}
    </nav>
  )
}

export default StepIndicator
