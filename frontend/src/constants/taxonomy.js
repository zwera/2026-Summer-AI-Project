/**
 * app/taxonomy.py의 JOB_CATEGORIES와 동일한 라벨 매핑.
 * 백엔드가 category key(예: field_control)를 그대로 다루므로
 * 프론트엔드에서는 사용자에게 보여줄 라벨만 관리한다.
 */
export const JOB_CATEGORY_LABELS = {
  field_control: '현장 단속/제지',
  arrest: '체포/현행범체포',
  voluntary_accompany: '임의동행',
  search_seizure: '압수수색/검문검색',
  admin_sanction: '행정처분/영업단속',
  obstruction_of_duty: '공무집행방해 대응',
  liability_risk: '국가배상/직권남용 리스크',
  uncategorized: '기타/미분류',
}

export function categoryLabel(key) {
  return JOB_CATEGORY_LABELS[key] || key || '미분류'
}

export const RISK_LEVEL_LABELS = {
  low: '낮음',
  medium: '보통',
  high: '높음',
}

/** 상황 입력 화면의 "빠른 상황 선택" 칩. icon은 이모지로 간단히 표현. */
export const QUICK_SITUATIONS = [
  {
    key: 'arrest',
    icon: '🚨',
    label: '현행범 체포',
    template: '현장에서 범행을 목격하여 현행범으로 체포하려고 합니다.',
    category: 'arrest',
  },
  {
    key: 'voluntary_accompany',
    icon: '🚶',
    label: '임의동행',
    template: '조사를 위해 임의동행을 요청하는 상황입니다.',
    category: 'voluntary_accompany',
  },
  {
    key: 'domestic_violence',
    icon: '🏠',
    label: '가정폭력',
    template: '가정폭력 신고를 받고 현장에 출동했습니다.',
    category: 'field_control',
  },
  {
    key: 'protective',
    icon: '💚',
    label: '주취자 보호',
    template: '술에 취한 사람을 보호조치하려는 상황입니다.',
    category: 'field_control',
  },
]
