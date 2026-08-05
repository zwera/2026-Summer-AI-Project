"""
Part 2: 직무 시나리오 중심 판례 분류 체계.

기존 법원 분류(형사/민사/행정) 대신 경찰 업무 단계별로 판례를 재분류하기 위한
카테고리 정의와, 판례가 수집된 법률 영역(경범죄/식품/청소년)과의 매핑을 담는다.

현재 수집된 판례는 '경범죄처벌법 위반', '식품위생법 위반', '청소년보호법 위반' 외에
'공무집행방해', '직무유기', '국가배상'(경찰관 직무집행 관련) 판례도 포함한다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class JobCategory:
    key: str
    label: str
    description: str
    keywords: tuple[str, ...]


JOB_CATEGORIES: list[JobCategory] = [
    JobCategory(
        key="field_control",
        label="현장 단속/제지",
        description="주취자·소란·경범죄 등 현장에서 즉시 단속·제지하는 상황",
        keywords=("주취", "소란", "난동", "경범죄", "제지", "단속", "훈방"),
    ),
    JobCategory(
        key="arrest",
        label="체포/현행범체포",
        description="현행범 체포, 긴급체포 등 신체의 자유를 제한하는 조치",
        keywords=("체포", "현행범", "긴급체포", "구속", "연행"),
    ),
    JobCategory(
        key="voluntary_accompany",
        label="임의동행",
        description="동의를 받아 경찰서 등으로 동행하는 조치",
        keywords=("임의동행", "동행", "보호조치"),
    ),
    JobCategory(
        key="search_seizure",
        label="압수수색/검문검색",
        description="물건 압수, 수색, 검문 등 재산·신체에 대한 침익적 조치",
        keywords=("압수", "수색", "검문", "검색", "단속반"),
    ),
    JobCategory(
        key="admin_sanction",
        label="행정처분/영업단속",
        description="식품위생법·청소년보호법 등 영업장 대상 행정처분, 영업정지, 과징금",
        keywords=("영업정지", "행정처분", "과징금", "시정명령", "청소년 출입", "유해업소"),
    ),
    JobCategory(
        key="obstruction_of_duty",
        label="공무집행방해 대응",
        description="상대방의 공무집행방해에 대한 대응 및 정당성 판단",
        keywords=("공무집행방해", "폭행", "협박", "위력"),
    ),
    JobCategory(
        key="liability_risk",
        label="국가배상/직권남용 리스크",
        description="경찰관 조치로 인한 국가배상 청구, 직권남용 여부가 문제되는 사안",
        keywords=("국가배상", "직권남용", "손해배상", "위자료"),
    ),
    JobCategory(
        key="uncategorized",
        label="기타/미분류",
        description="위 카테고리에 명확히 속하지 않는 사안",
        keywords=(),
    ),
]

# 판례가 수집된 법률 영역(폴더명) -> 대표 시나리오 카테고리 (검색 필터 기본값에 사용)
LAW_AREA_DEFAULT_CATEGORY: dict[str, str] = {
    "경범죄": "field_control",
    "식품": "admin_sanction",
    "청소년": "admin_sanction",
    "공무집행방해": "obstruction_of_duty",
    "국가배상": "liability_risk",
    "직무유기": "liability_risk",
}


def category_by_key(key: str) -> JobCategory | None:
    for c in JOB_CATEGORIES:
        if c.key == key:
            return c
    return None


def category_labels() -> list[str]:
    return [c.label for c in JOB_CATEGORIES]
