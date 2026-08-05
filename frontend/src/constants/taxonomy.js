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

/**
 * 상황 입력 화면의 "빠른 상황 선택" 칩.
 * icon은 이미지 경로(/icons/*.jpg) 또는 이모지 문자열이다.
 * 클릭 시 텍스트 입력에는 영향을 주지 않고, 하단 "상황 대응 간의 매뉴얼"
 * 카드가 해당 category의 매뉴얼로 전환된다.
 */
export const QUICK_SITUATIONS = [
  {
    key: 'arrest',
    icon: '/icons/arrest.jpg',
    label: '현행범 체포',
    category: 'arrest',
  },
  {
    key: 'voluntary_accompany',
    icon: '/icons/voluntary.jpg',
    label: '임의동행',
    category: 'voluntary_accompany',
  },
  {
    key: 'domestic_violence',
    icon: '/icons/family.jpg',
    label: '가정폭력',
    category: 'field_control',
  },
  {
    key: 'protective',
    icon: '/icons/drunk.jpg',
    label: '주취자 보호',
    category: 'field_control',
  },
]

/**
 * "빠른 상황 선택" 칩 key별 현장 기초 매뉴얼(우선 조치 체크리스트).
 * AI 분석 전, 현장에서 즉시 참고할 수 있는 절차 안내용이며 법적 판단을
 * 대체하지 않는다. 각 항목은 실제 법령상 절차 요건을 간략화한 것이다.
 */
export const FIELD_MANUALS = {
  arrest: {
    title: '현행범 체포 기초 매뉴얼',
    steps: [
      '범죄의 현행성 확인 (지금 범행 중이거나 범행 직후인지)',
      '체포의 필요성 판단 (도주 또는 증거인멸 우려)',
      '미란다 원칙 고지 (피의사실 요지·체포 이유·변호인 선임권·진술거부권)',
      '물리력은 비례의 원칙 범위 내에서 최소한으로 사용',
    ],
  },
  voluntary_accompany: {
    title: '임의동행 기초 매뉴얼',
    steps: [
      '동행 목적과 이유를 명확히 설명하고 동의를 확인',
      '동행 거부 시 강제할 수 없음을 인지 (강제 시 불법체포 소지)',
      '동행 시각·장소를 기록하고 6시간 이내 조사 종료 원칙 준수',
      '언제든지 퇴거할 수 있음을 고지',
    ],
  },
  search_seizure: {
    title: '압수수색/검문검색 기초 매뉴얼',
    steps: [
      '원칙적으로 검사의 청구에 의한 법관의 영장 필요 여부 확인',
      '긴급/현행범 체포 현장 등 영장 없는 예외 요건 충족 여부 확인',
      '압수물 목록을 작성하고 참여인에게 교부',
      '검문검색 시 신분 고지 및 목적·이유 설명',
    ],
  },
  field_control: {
    title: '현장 단속/제지 기초 매뉴얼',
    steps: [
      '위해 분리 및 현장 안전 확보 (당사자·목격자 분리)',
      '구체적 행위와 목격자를 우선 확인',
      '경고 → 제지 → 체포 등 단계적 조치 원칙 준수',
      '보호조치가 필요한 경우 대상자의 안전 확보 우선',
    ],
  },
  admin_sanction: {
    title: '행정처분/영업단속 기초 매뉴얼',
    steps: [
      '단속 근거 법령 및 위반 사실을 구체적으로 확인',
      '단속 대상자에게 위반 사실과 근거를 고지',
      '증거(사진, 진술서 등)를 절차에 따라 확보',
      '행정처분 전 의견제출 기회 등 절차적 권리 안내',
    ],
  },
  obstruction_of_duty: {
    title: '공무집행방해 대응 기초 매뉴얼',
    steps: [
      '집행 중인 직무가 적법한 공무집행인지 먼저 확인',
      '상대방의 폭행·협박 등 방해 행위를 구체적으로 특정',
      '목격자 확보 및 채증(바디캠 등)으로 상황을 기록',
      '독직폭행 논란 방지를 위해 대응 물리력은 최소한으로',
    ],
  },
  liability_risk: {
    title: '국가배상/직권남용 리스크 기초 매뉴얼',
    steps: [
      '직무 범위 내 행위인지, 법령상 근거가 있는지 확인',
      '재량권 행사 시 비례·평등의 원칙 준수 여부 점검',
      '조치의 경과와 판단 근거를 구체적으로 기록',
      '피해 발생 우려가 있다면 즉시 상급자에게 보고',
    ],
  },
}

/** 카테고리에 해당하는 매뉴얼이 없을 때 보여줄 기본 매뉴얼. */
export const DEFAULT_FIELD_MANUAL = {
  title: '현장 대응 기초 매뉴얼',
  steps: [
    '위해 분리 및 안전 확보',
    '구체적 행위와 목격자 확인',
    '취할 조치의 법적 요건 충족 여부 재확인',
    '상황 진행 경과를 시간순으로 기록',
  ],
}
