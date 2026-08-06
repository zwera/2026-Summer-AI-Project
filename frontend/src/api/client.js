/**
 * 백엔드 API 클라이언트.
 * 별도 axios 의존성 없이 fetch로 구현한다.
 */
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method || 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const errBody = await res.json()
      detail = errBody.detail ? JSON.stringify(errBody.detail) : detail
    } catch {
      // 응답 본문이 JSON이 아닌 경우 statusText 그대로 사용
    }
    throw new Error(`API 요청 실패 (${res.status}): ${detail}`)
  }

  return res.json()
}

/**
 * 백엔드 헬스체크. 사이트(백엔드 서버)가 정상 동작 중인지 확인하는 용도로,
 * 실패해도 request()처럼 에러를 던지지 않고 boolean으로 결과를 돌려준다
 * (탭 아이콘 상태 표시처럼 실패해도 화면이 멈추면 안 되는 곳에서 사용).
 */
export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { method: 'GET' })
    return res.ok
  } catch {
    return false
  }
}

/** Part 1: 대화형 절차 보완. history: [{role, content}] */
export function postChat(history) {
  return request('/api/chat', { body: { history } })
}

/** Part 1+2: 판례 검색(RAG). */
export function postSearch({ query, category, top_k = 5 }) {
  return request('/api/search', { body: { query, category, top_k } })
}

/** Part 3: 적법성 분석 (요약/리스크/타임라인/비교 등 전체). */
export function postAnalysis({ situation, category, top_k = 5 }) {
  return request('/api/analysis', { body: { situation, category, top_k } })
}

/** Part 3: 텍스트 드래그 재검토/자세히 설명. */
export function postFactCheck({ situation, selected_text, mode }) {
  return request('/api/analysis/fact-check', {
    body: { situation, selected_text, mode },
  })
}
