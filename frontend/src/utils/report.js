import { categoryLabel, RISK_LEVEL_LABELS } from '../constants/taxonomy.js'

/** analysis(AnalysisResponse)를 사건보고서 초안 마크다운 문자열로 변환한다. */
export function buildReportMarkdown(analysis) {
  const lines = []

  lines.push('# 사건보고서 초안')
  lines.push('')
  lines.push(`- 작성일시: ${new Date().toLocaleString('ko-KR')}`)
  lines.push(`- 직무 카테고리: ${categoryLabel(analysis.category)}`)
  lines.push('')

  lines.push('## 1. 사건 개요')
  lines.push('')
  lines.push(analysis.situation || '(내용 없음)')
  lines.push('')

  lines.push('## 2. 적법성 판단')
  lines.push('')
  lines.push(`**결론: ${analysis.verdict.verdict}**`)
  lines.push('')
  lines.push(analysis.verdict.reasoning || '')
  if (analysis.verdict.key_criteria?.length) {
    lines.push('')
    lines.push('판단 기준:')
    for (const c of analysis.verdict.key_criteria) lines.push(`- ${c}`)
  }
  lines.push('')

  lines.push('## 3. 3단계 요약')
  lines.push('')
  lines.push('### 3줄 요약 (현장 즉시 확인용)')
  lines.push('')
  lines.push(analysis.summary.three_line || '')
  lines.push('')
  lines.push('### 10줄 요약 (보고서 작성용)')
  lines.push('')
  lines.push(analysis.summary.ten_line || '')
  lines.push('')
  lines.push('### 전문 (법적 다툼 대비용)')
  lines.push('')
  lines.push(analysis.summary.full_text || '')
  lines.push('')

  if (analysis.risk_badges?.length) {
    lines.push('## 4. 리스크 요소')
    lines.push('')
    lines.push('| 유형 | 수준 | 설명 |')
    lines.push('|---|---|---|')
    for (const b of analysis.risk_badges) {
      const level = RISK_LEVEL_LABELS[b.level] || b.level
      lines.push(`| ${b.type} | ${level} | ${b.description} |`)
    }
    lines.push('')
  }

  if (analysis.lawful_examples?.length || analysis.unlawful_examples?.length) {
    lines.push('## 5. 시나리오 비교')
    lines.push('')
    lines.push('### 적법 사례')
    lines.push('')
    if (analysis.lawful_examples?.length) {
      for (const p of analysis.lawful_examples) lines.push(precedentLine(p))
    } else {
      lines.push('- 해당 사례 없음')
    }
    lines.push('')
    lines.push('### 위법 사례')
    lines.push('')
    if (analysis.unlawful_examples?.length) {
      for (const p of analysis.unlawful_examples) lines.push(precedentLine(p))
    } else {
      lines.push('- 해당 사례 없음')
    }
    lines.push('')
  }

  if (analysis.fact_diffs?.length) {
    lines.push('## 6. 사실관계 비교 (Diff)')
    lines.push('')
    lines.push('| 항목 | 현재 상황 | 판례 사실관계 | 핵심 차이 |')
    lines.push('|---|---|---|---|')
    for (const d of analysis.fact_diffs) {
      lines.push(
        `| ${d.point} | ${escapeCell(d.user_situation)} | ` +
          `${escapeCell(d.precedent_fact)} | ${d.is_critical ? '⚠️' : ''} |`
      )
    }
    lines.push('')
  }

  if (analysis.timeline?.length) {
    lines.push('## 7. 사건 타임라인')
    lines.push('')
    const sorted = [...analysis.timeline].sort((a, b) => a.order - b.order)
    for (const evt of sorted) {
      const issue = evt.legal_issue ? ` (쟁점: ${evt.legal_issue})` : ''
      lines.push(`${evt.order}. **${evt.timestamp_label}** - ${evt.description}${issue}`)
    }
    lines.push('')
  }

  if (analysis.similar_precedents?.length) {
    lines.push('## 8. 참고 판례 전체 목록')
    lines.push('')
    for (const p of analysis.similar_precedents) lines.push(precedentLine(p))
    lines.push('')
  }

  lines.push('---')
  lines.push('')
  lines.push(
    '*본 보고서는 AI가 생성한 초안이며, 실제 보고서 작성 및 법적 판단의 최종 책임은 ' +
      '작성자에게 있습니다. 상급심에서 결론이 달라질 수 있습니다.*'
  )

  return lines.join('\n')
}

function precedentLine(p) {
  const link = p.source_link ? ` — [원문 보기](${p.source_link})` : ''
  return `- [${p.case_no}] ${p.title} (${p.court}, ${p.date}, 유사도 ${p.similarity}%)${link}`
}

function escapeCell(text) {
  return String(text ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ')
}

/** 마크다운 문자열을 .md 파일로 다운로드한다. */
export function downloadMarkdown(filename, content) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
