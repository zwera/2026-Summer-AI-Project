"""최소 유효 목업 데이터셋(fixture).

task 1.2에 따라 ``data.models``의 데이터 모델 타입만 사용해 다음을 만족하는 최소 유효
``MockDataset``을 구성한다.

- ``instanceCautionNotice``를 포함한 ``MockDataset`` 루트와 표시 정책(``MockDisplayPolicies``).
- 8개 경찰_직무_시나리오 각각에 적법 1건 이상·위법 1건 이상의 판례(``CaseRecord``).
- 전체 심급 연결 예시: 현행범체포 시나리오의 1심 판례가 ``relatedInstances``로 항소심
  판례를 가리키고, 항소심 결정에 ``relationToLowerInstance``(유지/변경)를 명시한다.
- 안전 고지, 유사도 경고(HIGH/MEDIUM/LOW), ``정보_없음``·``분류_불가``·``확인 필요``·
  ``확인되지 않음``을 표시 정책 레코드 ID로 갖는 ``MockDisplayPolicies``.

이 모듈은 구조·교차 참조 검증(``DatasetValidator``, task 2.x)을 수행하지 않는다. 여기서
만드는 ``MockDataset``은 검증 전 신뢰되지 않은 데이터일 뿐이다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from domain.enums import LawBasisStatus, LegalityStatus, PoliceScenario
from domain.ids import CaseId, ClaimId, DatasetId, EventId, QueryId, SourceId, StatuteVersionId

from data.models import (
    IMPLEMENTED_COVERAGE_LABEL_TEXT,
    INSTANCE_CAUTION_NOTICE_TEXT,
    LEGAL_SAFETY_NOTICE_TEXT,
    NO_REALTIME_SYNC_LABEL_TEXT,
    TARGET_COVERAGE_LABEL_TEXT,
    ActionJudgment,
    ActorActionEdge,
    AppellateDecision,
    AppellateInformation,
    AppliedStatuteRef,
    CaseRecord,
    CivilStatus,
    ClaimEvidenceLink,
    ClassifiedEvidence,
    CriminalLiabilityRisk,
    DetailedSummarySection,
    DisplayPolicyRecord,
    FactDifference,
    FieldTermExplanation,
    LegalClaimBlock,
    LegalTermExplanationEntry,
    LegalTermMapping,
    MockDataset,
    MockDisplayPolicies,
    PersonalLiabilityRisk,
    QueryFixture,
    QueryMatch,
    QueryVariant,
    RelatedInstanceRef,
    RelationGraph,
    ResponseTemplate,
    ReviewableClaim,
    RiskAssessment,
    ScenarioDefinition,
    SelectionExplanationFixture,
    SelectionReviewFixture,
    SimilarityPreset,
    SimilarityWarningPolicyRecord,
    SourceAnchor,
    SourceAnchorId,
    SourceOwner,
    SourceRecord,
    StatuteRecord,
    StatuteVersion,
    SummaryBundle,
    SummaryLine,
    SummarySectionKey,
    TextBlock,
    VoiceFixture,
    VoiceFixtureId,
)
from data.models_timeline import EventAmbiguity, IssueLink, RecognizedEvent

AS_OF_DATE = "2024-01-01"
"""데이터_기준일. 이 fixture의 모든 현행법_기준 판정 기준일이다."""


def _checksum(text: str) -> str:
    """앵커 체크섬 계산. 검증기(task 2.x)가 대조할 sha256 hex digest를 반환한다."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _judgment_source(source_id: str, case_id: CaseId, title: str, body: str) -> SourceRecord:
    """판례 전문 발췌 ``SourceRecord``를 만들고 전체 본문을 덮는 단일 anchor를 부여한다."""

    anchor = SourceAnchor(
        id=SourceAnchorId(f"{source_id}-anchor-1"),
        start_offset=0,
        end_offset=len(body),
        excerpt_checksum=_checksum(body),
    )
    return SourceRecord(
        id=SourceId(source_id),
        owner=SourceOwner(type="CASE", id=case_id),
        title=title,
        source_kind="JUDGMENT_EXCERPT",
        body=body,
        anchors=(anchor,),
    )


def _statute_fixture() -> Tuple[StatuteRecord, StatuteVersion, SourceRecord]:
    """모든 판례가 공통으로 인용하는 최소 법조문 하나(형법 제125조)를 만든다."""

    body = (
        "제125조(폭행, 가혹행위) 재판, 검찰, 경찰 그 밖에 인신 구속에 관한 직무를 행하는 자 "
        "또는 이를 보조하는 자가 그 직무를 행함에 당하여 형사피의자 또는 기타 사람에 대하여 "
        "폭행 또는 가혹한 행위를 가한 때에는 5년 이하의 징역과 10년 이하의 자격정지에 처한다."
    )
    version_id = StatuteVersionId("statute-version-criminal-act-125")
    source_id = SourceId("source-statute-criminal-act-125")
    anchor = SourceAnchor(
        id=SourceAnchorId(f"{source_id}-anchor-1"),
        start_offset=0,
        end_offset=len(body),
        excerpt_checksum=_checksum(body),
    )
    source = SourceRecord(
        id=source_id,
        owner=SourceOwner(type="STATUTE", id=version_id),
        title="형법 제125조(폭행, 가혹행위)",
        source_kind="STATUTE_TEXT",
        body=body,
        anchors=(anchor,),
    )
    version = StatuteVersion(
        id=version_id,
        statute_id="statute-criminal-act",
        article="제125조",
        text_source_id=source_id,
        revision_date="2020-12-08",
        effective_date="2021-01-01",
        version_label="2020년 개정",
        revision_summary=None,
    )
    record = StatuteRecord(
        id="statute-criminal-act",
        law_name="형법",
        version_ids=(version_id,),
        current_version_id_at_as_of=version_id,
    )
    return record, version, source


@dataclass(frozen=True)
class _ScenarioSpec:
    """경찰_직무_시나리오 하나에 대한 적법·위법 판례 fixture 생성 입력."""

    code: str
    scenario: PoliceScenario
    legal_term: str
    field_expression: str
    lawful_case_number: str
    lawful_court: str
    lawful_date: str
    lawful_action_text: str
    lawful_charge: Optional[str]
    lawful_outcome: str
    lawful_excerpt: str
    unlawful_case_number: str
    unlawful_court: str
    unlawful_date: str
    unlawful_action_text: str
    unlawful_charge: Optional[str]
    unlawful_outcome: str
    unlawful_excerpt: str


_SCENARIO_SPECS: Tuple[_ScenarioSpec, ...] = (
    _ScenarioSpec(
        code="arrest",
        scenario=PoliceScenario.FLAGRANT_OFFENDER_ARREST,
        legal_term="현행범체포",
        field_expression="범행 직후 바로 잡기",
        lawful_case_number="2019고1234",
        lawful_court="서울중앙지방법원",
        lawful_date="2019-05-10",
        lawful_action_text="범행 직후 도주하려는 피고인을 현장에서 체포",
        lawful_charge="폭행",
        lawful_outcome="무죄",
        lawful_excerpt=(
            "피고인은 범행 직후 범죄 장소에서 발견되어 현행범으로 체포되었다. 체포 당시 경찰관은 "
            "체포의 이유와 변호인 선임권을 고지하였다. 법원은 체포 절차가 형사소송법 제211조의 "
            "요건을 충족하여 적법하다고 판단하였다."
        ),
        unlawful_case_number="2020고5678",
        unlawful_court="서울중앙지방법원",
        unlawful_date="2020-08-20",
        unlawful_action_text="범행 종료 후 상당한 시간이 지난 뒤 별건으로 체포",
        unlawful_charge="특수공무집행방해",
        unlawful_outcome="일부 인용",
        unlawful_excerpt=(
            "경찰관은 범행 종료 후 30분이 지난 시점에 피고인을 현행범으로 체포하였으나, 법원은 "
            "시간적·장소적 근접성이 인정되지 않아 현행범 체포의 요건을 충족하지 못하였다고 보아 "
            "체포가 위법하다고 판단하였다."
        ),
    ),
    _ScenarioSpec(
        code="accompany",
        scenario=PoliceScenario.VOLUNTARY_ACCOMPANIMENT,
        legal_term="임의동행",
        field_expression="같이 가자고 부탁해서 데려오기",
        lawful_case_number="2018고910",
        lawful_court="부산지방법원",
        lawful_date="2018-03-15",
        lawful_action_text="동행을 거부할 수 있음을 고지하고 자발적 동의를 받아 지구대로 동행",
        lawful_charge=None,
        lawful_outcome="무죄",
        lawful_excerpt=(
            "경찰관은 피고인에게 동행을 거부할 수 있음과 언제든지 퇴거할 수 있음을 고지한 후 "
            "피고인의 자발적인 동의를 받아 지구대로 동행하였다. 법원은 이러한 동행이 임의동행의 "
            "요건을 충족하여 적법하다고 판단하였다."
        ),
        unlawful_case_number="2018고1122",
        unlawful_court="부산지방법원",
        unlawful_date="2018-11-02",
        unlawful_action_text="동행을 거부할 수 있음을 고지하지 않고 순찰차에 태워 지구대로 이동",
        unlawful_charge="직권남용체포",
        unlawful_outcome="인용",
        unlawful_excerpt=(
            "경찰관은 피고인에게 동행 거부권을 고지하지 않고 사실상 강제로 순찰차에 태워 지구대로 "
            "이동하였다. 법원은 이는 임의동행이 아니라 실질적으로 강제연행에 해당하여 위법하다고 "
            "판단하였다."
        ),
    ),
    _ScenarioSpec(
        code="emergency",
        scenario=PoliceScenario.EMERGENCY_ARREST,
        legal_term="긴급체포",
        field_expression="도망갈 것 같아서 바로 잡기",
        lawful_case_number="2017고3344",
        lawful_court="인천지방법원",
        lawful_date="2017-09-05",
        lawful_action_text="도주 우려가 있어 영장 없이 우선 체포한 뒤 사후 즉시 영장을 청구",
        lawful_charge="강도",
        lawful_outcome="유죄",
        lawful_excerpt=(
            "경찰관은 강도 혐의자가 증거를 인멸하고 도주할 우려가 있다고 판단하여 영장 없이 체포한 "
            "후 48시간 이내에 구속영장을 청구하였다. 법원은 형사소송법 제200조의3의 요건을 충족하여 "
            "긴급체포가 적법하다고 판단하였다."
        ),
        unlawful_case_number="2017고4455",
        unlawful_court="인천지방법원",
        unlawful_date="2017-12-11",
        unlawful_action_text="도주 우려에 대한 구체적 근거 없이 긴급체포",
        unlawful_charge=None,
        unlawful_outcome="각하",
        unlawful_excerpt=(
            "경찰관은 단순 절도 혐의자에 대해 도주나 증거 인멸의 구체적 우려 없이 긴급체포를 "
            "하였다. 법원은 긴급성의 요건을 충족하지 못하였다고 보아 체포가 위법하다고 판단하였다."
        ),
    ),
    _ScenarioSpec(
        code="search",
        scenario=PoliceScenario.SEARCH_AND_SEIZURE,
        legal_term="압수수색",
        field_expression="집 뒤져서 물건 가져오기",
        lawful_case_number="2016고5566",
        lawful_court="대전지방법원",
        lawful_date="2016-04-18",
        lawful_action_text="압수수색영장을 제시하고 영장 기재 범위 내에서 물건을 압수",
        lawful_charge="마약류관리법위반",
        lawful_outcome="유죄",
        lawful_excerpt=(
            "경찰관은 압수수색영장을 피고인에게 제시하고 영장에 기재된 장소와 물건의 범위 내에서 "
            "압수수색을 실시하였다. 법원은 영장주의 원칙을 준수하여 압수수색이 적법하다고 판단하였다."
        ),
        unlawful_case_number="2016고6677",
        unlawful_court="대전지방법원",
        unlawful_date="2016-10-09",
        unlawful_action_text="영장 없이 주거지에 진입하여 물건을 압수",
        unlawful_charge=None,
        unlawful_outcome="일부 인용",
        unlawful_excerpt=(
            "경찰관은 압수수색영장 없이 피고인의 주거지에 진입하여 물건을 압수하였다. 법원은 "
            "긴급성이나 동의 등 예외적 사유가 인정되지 않는다고 보아 압수수색이 위법하다고 판단하고 "
            "압수물의 증거능력을 배제하였다."
        ),
    ),
    _ScenarioSpec(
        code="miranda",
        scenario=PoliceScenario.MIRANDA_WARNING,
        legal_term="미란다 원칙 고지",
        field_expression="체포하면서 권리 알려주기",
        lawful_case_number="2015고7788",
        lawful_court="광주지방법원",
        lawful_date="2015-06-22",
        lawful_action_text="체포 당시 변호인 선임권과 진술거부권을 명확히 고지",
        lawful_charge="폭력행위등처벌에관한법률위반",
        lawful_outcome="유죄",
        lawful_excerpt=(
            "경찰관은 피고인을 체포하면서 체포의 이유, 변호인을 선임할 수 있는 권리 및 진술거부권을 "
            "명확히 고지하였다. 법원은 미란다 원칙에 따른 고지 절차가 적법하게 이루어졌다고 "
            "판단하였다."
        ),
        unlawful_case_number="2015고8899",
        unlawful_court="광주지방법원",
        unlawful_date="2015-09-30",
        unlawful_action_text="체포 이후 조사가 상당히 진행된 뒤에야 진술거부권을 고지",
        unlawful_charge=None,
        unlawful_outcome="일부 인용",
        unlawful_excerpt=(
            "경찰관은 피고인을 체포한 후 조사가 상당히 진행된 이후에야 진술거부권을 고지하였다. "
            "법원은 고지 시점이 지나치게 지연되어 절차가 위법하다고 판단하고 고지 전 진술의 "
            "증거능력을 배제하였다."
        ),
    ),
    _ScenarioSpec(
        code="silence",
        scenario=PoliceScenario.RIGHT_TO_REMAIN_SILENT,
        legal_term="진술거부권",
        field_expression="말하고 싶지 않으면 안 해도 된다고 알려주기",
        lawful_case_number="2014고9900",
        lawful_court="수원지방법원",
        lawful_date="2014-02-14",
        lawful_action_text="피의자 신문 전 진술거부권을 고지하고 이를 조서에 기재",
        lawful_charge="사기",
        lawful_outcome="유죄",
        lawful_excerpt=(
            "경찰관은 피의자 신문을 시작하기 전 진술거부권이 있음을 고지하고 이를 조서에 명확히 "
            "기재하였다. 법원은 진술거부권 고지 절차가 적법하게 준수되었다고 판단하였다."
        ),
        unlawful_case_number="2014고1011",
        unlawful_court="수원지방법원",
        unlawful_date="2014-07-19",
        unlawful_action_text="진술거부권을 고지하지 않고 장시간 신문을 진행",
        unlawful_charge=None,
        unlawful_outcome="인용",
        unlawful_excerpt=(
            "경찰관은 진술거부권을 고지하지 않은 채 피의자를 장시간 신문하였다. 법원은 진술거부권 "
            "미고지로 얻은 진술은 위법수집증거에 해당하여 증거능력이 없다고 판단하였다."
        ),
    ),
    _ScenarioSpec(
        code="domestic",
        scenario=PoliceScenario.DOMESTIC_VIOLENCE_INITIAL_RESPONSE,
        legal_term="가정폭력 초동조치",
        field_expression="집안싸움 신고받고 바로 가서 떼어놓기",
        lawful_case_number="2013고1213",
        lawful_court="제주지방법원",
        lawful_date="2013-01-08",
        lawful_action_text="신고 출동 후 가정폭력행위자와 피해자를 분리하고 긴급임시조치를 신청",
        lawful_charge="가정폭력범죄의처벌등에관한특례법위반",
        lawful_outcome="유죄",
        lawful_excerpt=(
            "경찰관은 가정폭력 신고를 받고 현장에 출동하여 가정폭력행위자와 피해자를 즉시 분리하고 "
            "긴급임시조치를 신청하였다. 법원은 가정폭력범죄의처벌등에관한특례법에 따른 초동조치가 "
            "적법하게 이루어졌다고 판단하였다."
        ),
        unlawful_case_number="2013고1314",
        unlawful_court="제주지방법원",
        unlawful_date="2013-05-27",
        unlawful_action_text="피해자 분리·격리 조치를 취하지 않고 현장을 이탈",
        unlawful_charge=None,
        unlawful_outcome="각하",
        unlawful_excerpt=(
            "경찰관은 가정폭력 신고를 받고 출동하였으나 가정폭력행위자와 피해자를 분리하는 등 "
            "필요한 초동조치를 취하지 않고 현장을 이탈하였다. 법원은 이러한 조치 미이행이 관련 "
            "법령상 요구되는 초동조치 의무를 위반하였다고 판단하였다."
        ),
    ),
    _ScenarioSpec(
        code="dui",
        scenario=PoliceScenario.DUI_CHECKPOINT,
        legal_term="음주단속",
        field_expression="술 마셨는지 숨 불어보라고 확인하기",
        lawful_case_number="2012고1415",
        lawful_court="울산지방법원",
        lawful_date="2012-12-03",
        lawful_action_text="음주감지기 반응 확인 후 정식 음주측정기로 혈중알코올농도를 측정",
        lawful_charge="도로교통법위반(음주운전)",
        lawful_outcome="유죄",
        lawful_excerpt=(
            "경찰관은 음주감지기로 반응을 확인한 후 정식 음주측정기로 혈중알코올농도를 측정하였다. "
            "법원은 도로교통법에서 정한 절차에 따라 음주단속이 적법하게 이루어졌다고 판단하였다."
        ),
        unlawful_case_number="2012고1516",
        unlawful_court="울산지방법원",
        unlawful_date="2012-12-25",
        unlawful_action_text="합리적 의심 없이 무작위로 차량을 세우고 강제로 음주측정을 요구",
        unlawful_charge=None,
        unlawful_outcome="일부 인용",
        unlawful_excerpt=(
            "경찰관은 합리적인 의심 없이 무작위로 차량을 정지시키고 운전자의 동의 없이 강제로 "
            "음주측정을 요구하였다. 법원은 이러한 단속 방식이 적법절차의 요건을 충족하지 못하여 "
            "위법하다고 판단하였다."
        ),
    ),
)


def _summary_line(key: SummarySectionKey, text: Optional[str], evidence: ClaimEvidenceLink) -> SummaryLine:
    return SummaryLine(key=key, text=text, direct_evidence=(evidence,))


def _build_summary_bundle(
    *,
    legality: LegalityStatus,
    charge: Optional[str],
    outcome: str,
    action_text: str,
    excerpt: str,
    legal_term: str,
    field_expression: str,
    evidence: ClaimEvidenceLink,
) -> SummaryBundle:
    """판례 하나의 3줄·10줄·상세 요약과 canonical 값을 채운 ``SummaryBundle``을 만든다."""

    case_overview = action_text
    key_facts = excerpt
    issue = f"{legal_term} 절차의 적법성"
    court_conclusion = f"법원은 해당 경찰 행위를 {legality.value}으로 판단하였다."
    applied_statute_label = "형법 제125조(폭행, 가혹행위)"
    field_point = f"'{field_expression}'은 법적으로 '{legal_term}' 요건 충족 여부로 심사된다."

    three_line = (
        _summary_line("사건 개요", case_overview, evidence),
        _summary_line("법원 결론", court_conclusion, evidence),
        _summary_line("현장 경찰 핵심 포인트", field_point, evidence),
    )
    ten_line = (
        _summary_line("사건 개요", case_overview, evidence),
        _summary_line("주요 사실관계", key_facts, evidence),
        _summary_line("판례 쟁점", issue, evidence),
        _summary_line("법원 결론", court_conclusion, evidence),
        _summary_line("적용 법조문", applied_statute_label, evidence),
        _summary_line("해당 심급 인정 죄명", charge, evidence),
        _summary_line("해당 심급 재판 결과", outcome, evidence),
        _summary_line("현장 경찰 핵심 포인트", field_point, evidence),
        _summary_line("주요 사실관계", key_facts, evidence),
        _summary_line("현장 경찰 핵심 포인트", field_point, evidence),
    )
    detailed = (
        DetailedSummarySection(key="사건 개요", text=case_overview, direct_evidence=(evidence,)),
        DetailedSummarySection(key="주요 사실관계", text=key_facts, direct_evidence=(evidence,)),
        DetailedSummarySection(key="판례 쟁점", text=issue, direct_evidence=(evidence,)),
        DetailedSummarySection(key="법원 결론", text=court_conclusion, direct_evidence=(evidence,)),
        DetailedSummarySection(key="적용 법조문", text=applied_statute_label, direct_evidence=(evidence,)),
        DetailedSummarySection(key="해당 심급 인정 죄명", text=charge, direct_evidence=(evidence,)),
        DetailedSummarySection(key="해당 심급 재판 결과", text=outcome, direct_evidence=(evidence,)),
        DetailedSummarySection(key="현장 경찰 핵심 포인트", text=field_point, direct_evidence=(evidence,)),
    )
    return SummaryBundle(
        canonical_conclusion=court_conclusion,
        canonical_legality_status=legality,
        canonical_instance_charge=charge,
        canonical_instance_outcome=outcome,
        three_line=three_line,
        ten_line=ten_line,
        detailed=detailed,
        field_term_explanations=(
            FieldTermExplanation(
                legal_term=legal_term,
                field_expression=field_expression,
                first_occurrence_block_id="사건 개요",
            ),
        ),
    )


def _build_liability(*, unlawful: bool, evidence: ClaimEvidenceLink) -> PersonalLiabilityRisk:
    """위험_판정_축을 채운다. 위법 판례는 만장일치 증거로 위험 상태를, 적법 판례는 정보_없음을 갖는다."""

    if unlawful:
        civil_status: CivilStatus = "국가배상_인정"
        return PersonalLiabilityRisk(
            civil=RiskAssessment(
                declared=civil_status,
                evidence=(
                    ClassifiedEvidence(
                        source_id=evidence.source_id,
                        anchor_id=evidence.anchor_id,
                        supports_status=civil_status,
                    ),
                ),
            ),
            criminal=CriminalLiabilityRisk(
                abuse_of_authority=RiskAssessment(
                    declared="해당",
                    evidence=(
                        ClassifiedEvidence(
                            source_id=evidence.source_id,
                            anchor_id=evidence.anchor_id,
                            supports_status="해당",
                        ),
                    ),
                ),
                custodial_violence=RiskAssessment(declared="정보_없음", evidence=()),
            ),
            discipline=RiskAssessment(
                declared="징계_인정",
                evidence=(
                    ClassifiedEvidence(
                        source_id=evidence.source_id,
                        anchor_id=evidence.anchor_id,
                        supports_status="징계_인정",
                    ),
                ),
            ),
        )
    return PersonalLiabilityRisk(
        civil=RiskAssessment(declared="정보_없음", evidence=()),
        criminal=CriminalLiabilityRisk(
            abuse_of_authority=RiskAssessment(declared="정보_없음", evidence=()),
            custodial_violence=RiskAssessment(declared="정보_없음", evidence=()),
        ),
        discipline=RiskAssessment(declared="정보_없음", evidence=()),
    )


def _build_case(
    *,
    case_id: CaseId,
    scenario: PoliceScenario,
    instance: str,
    court_name: str,
    case_number: str,
    decision_date: str,
    legality: LegalityStatus,
    action_text: str,
    court_finding: str,
    charge: Optional[str],
    outcome: str,
    source: SourceRecord,
    statute_version_id: StatuteVersionId,
    statute_source_id: SourceId,
    legal_term: str,
    field_expression: str,
    fact_differences_by_query: Optional[Dict[QueryId, Tuple[FactDifference, ...]]] = None,
    related_instances: Tuple[RelatedInstanceRef, ...] = (),
    appellate: Optional[AppellateInformation] = None,
    finality: str = "확정",
) -> CaseRecord:
    """``CaseRecord`` 하나를 만드는 공통 빌더. 심급·상급심·위험·요약을 일관되게 채운다."""

    anchor_id = source.anchors[0].id
    evidence = ClaimEvidenceLink(
        source_id=source.id,
        anchor_id=anchor_id,
        purpose="DECISION",
        relation="SUPPORTS",
        coverage="FULL",
    )
    action_judgment = ActionJudgment(
        action_id=f"{case_id}-action-1",
        action_text=action_text,
        court_finding=court_finding,  # type: ignore[arg-type]
        source_ids=(source.id,),
    )
    summaries = _build_summary_bundle(
        legality=legality,
        charge=charge,
        outcome=outcome,
        action_text=action_text,
        excerpt=source.body,
        legal_term=legal_term,
        field_expression=field_expression,
        evidence=evidence,
    )
    liability = _build_liability(unlawful=legality is LegalityStatus.UNLAWFUL, evidence=evidence)
    return CaseRecord(
        id=case_id,
        court_name=court_name,
        instance=instance,  # type: ignore[arg-type]
        case_number=case_number,
        decision_date=decision_date,
        scenario_ids=(scenario,),
        legality_status=legality,
        action_judgments=(action_judgment,),
        source_ids=(source.id,),
        applied_statutes=(
            AppliedStatuteRef(
                citation_label="형법 제125조",
                statute_version_id=statute_version_id,
                source_id=statute_source_id,
            ),
        ),
        expected_law_basis_status=LawBasisStatus.CURRENT_LAW_BASIS,
        summaries=summaries,
        instance_recognized_charge=charge,
        instance_outcome=outcome,
        liability=liability,
        related_instances=related_instances,
        appellate=appellate if appellate is not None else AppellateInformation(state="정보_없음", decisions=()),
        finality=finality,  # type: ignore[arg-type]
        fact_differences_by_query=fact_differences_by_query or {},
    )


def _relation_graph(actor: str, action: str) -> RelationGraph:
    return RelationGraph(
        actors=(actor,),
        actions=(action,),
        times=(),
        negations=(),
        edges=(ActorActionEdge(type="ACTOR_ACTION", actor=actor, action=action),),
    )


def _build_term_mapping(spec: _ScenarioSpec) -> LegalTermMapping:
    # relationGraphBefore/After는 경찰_현장_표현 -> 법률_검색어 "어휘" 변환과는 별개로,
    # 사람·행위 관계 "구조"가 변환 전후 동일하게 보존되는지를 나타낸다(design.md 4.1절
    # 5번, 요구사항 2.5). 어휘 자체의 대응은 field_expression/legal_search_terms가
    # 담당하므로, 이 최소 fixture에서는 두 그래프에 동일한 actor-action 구조(경찰관이
    # spec.legal_term 행위를 수행)를 부여해 정상 변환 시 관계가 보존됨을 표현한다.
    graph = _relation_graph("경찰관", spec.legal_term)
    return LegalTermMapping(
        id=f"term-{spec.code}",
        field_expression=spec.field_expression,
        legal_search_terms=(spec.legal_term,),
        relation_graph_before=graph,
        relation_graph_after=graph,
        unsupported_fragments=(),
    )


def _build_query_fixture(
    spec: _ScenarioSpec,
    lawful_case_id: CaseId,
    unlawful_case_id: CaseId,
    statute_version_id: StatuteVersionId,
    template_id: str,
) -> QueryFixture:
    relation_graph = _relation_graph("경찰관", spec.legal_term)
    raw_example = f"경찰관이 현장에서 {spec.field_expression} 상황입니다."
    variant = QueryVariant(
        id=f"variant-{spec.code}-1",
        raw_example=raw_example,
        normalized_key=raw_example.strip(),
        input_mode="TEXT",
        relation_graph=relation_graph,
    )
    recognized_events = ()
    if spec.code == "arrest":
        recognized_events = (
            RecognizedEvent(
                id=EventId("event-arrest-notice"),
                original_text="14:10 경찰관이 체포 이유와 권리를 고지했다.",
                actor="경찰관",
                action="체포 이유와 권리를 고지",
                explicit_time="2024-01-01T14:10:00",
                resolved_sort_time="2024-01-01T14:10:00",
                original_order=1,
                issue_links=(IssueLink("미란다 원칙 고지", (SourceId("source-arrest-lawful"),)),),
            ),
            RecognizedEvent(
                id=EventId("event-arrest-custody"),
                original_text="14:00 범행 직후 도주하려는 사람을 체포했다.",
                actor="경찰관",
                action="현행범 체포",
                explicit_time="2024-01-01T14:00:00",
                resolved_sort_time="2024-01-01T14:00:00",
                original_order=0,
                issue_links=(IssueLink("현행범체포 요건", (SourceId("source-arrest-lawful"),)),),
            ),
            RecognizedEvent(
                id=EventId("event-arrest-followup"),
                original_text="이후 조치 시점은 확인되지 않았다.",
                actor=None,
                action="후속 조치",
                original_order=2,
                ambiguity=EventAmbiguity(kind="TIME", alternatives=("체포 직후", "고지 후")),
            ),
        )
    return QueryFixture(
        id=QueryId(f"query-{spec.code}"),
        scenario_ids=(spec.scenario,),
        core_fact_set_id=f"corefact-{spec.code}",
        variants=(variant,),
        term_mapping_ids=(f"term-{spec.code}",),
        canonical_relations=relation_graph,
        match=QueryMatch(
            case_ids=(lawful_case_id, unlawful_case_id),
            statute_version_ids=(statute_version_id,),
            response_template_id=template_id,
        ),
        recognized_events=recognized_events,
        fact_values={},
        similarity_by_case={
            lawful_case_id: SimilarityPreset(
                score=90.0,
                search_priority=1,
                tie_order=1,
                similarity_factors=("사실관계 일치",),
                recency_factors=("최근 판례",),
            ),
            unlawful_case_id: SimilarityPreset(
                score=70.0,
                search_priority=2,
                tie_order=1,
                similarity_factors=("사실관계 유사",),
                recency_factors=("최근 판례",),
            ),
        },
    )


def _build_response_template(
    spec: _ScenarioSpec,
    template_id: str,
    lawful_source: SourceRecord,
    unlawful_source: SourceRecord,
) -> ResponseTemplate:
    lawful_anchor = lawful_source.anchors[0].id
    unlawful_anchor = unlawful_source.anchors[0].id
    return ResponseTemplate(
        id=template_id,
        blocks=(
            TextBlock(type="TEXT", text=f"[{spec.legal_term}] 관련 목업 응답입니다."),
            LegalClaimBlock(
                type="LEGAL_CLAIM",
                claim_id=ClaimId(f"claim-{spec.code}-lawful"),
                text=f"적법 판례: {spec.lawful_action_text}",
                citation_links=(
                    ClaimEvidenceLink(
                        source_id=lawful_source.id,
                        anchor_id=lawful_anchor,
                        purpose="DECISION",
                        relation="SUPPORTS",
                        coverage="FULL",
                    ),
                ),
            ),
            LegalClaimBlock(
                type="LEGAL_CLAIM",
                claim_id=ClaimId(f"claim-{spec.code}-unlawful"),
                text=f"위법 판례: {spec.unlawful_action_text}",
                citation_links=(
                    ClaimEvidenceLink(
                        source_id=unlawful_source.id,
                        anchor_id=unlawful_anchor,
                        purpose="DECISION",
                        relation="SUPPORTS",
                        coverage="FULL",
                    ),
                ),
            ),
        ),
    )


def _build_selection_review_fixture(
    spec: _ScenarioSpec,
    template_id: str,
    lawful_source: SourceRecord,
    unlawful_source: SourceRecord,
) -> SelectionReviewFixture:
    lawful_anchor = lawful_source.anchors[0].id
    unlawful_anchor = unlawful_source.anchors[0].id
    lawful_claim_id = ClaimId(f"claim-{spec.code}-lawful")
    unlawful_claim_id = ClaimId(f"claim-{spec.code}-unlawful")
    explanation_text = f"'{spec.legal_term}'은 현장 표현 '{spec.field_expression}'에 대응하는 법률 용어입니다."
    return SelectionReviewFixture(
        response_template_id=template_id,
        claims=(
            ReviewableClaim(
                id=lawful_claim_id,
                text=f"적법 판례: {spec.lawful_action_text}",
                document_order=1,
                evidence=(
                    ClaimEvidenceLink(
                        source_id=lawful_source.id,
                        anchor_id=lawful_anchor,
                        purpose="DECISION",
                        relation="SUPPORTS",
                        coverage="FULL",
                    ),
                ),
            ),
            ReviewableClaim(
                id=unlawful_claim_id,
                text=f"위법 판례: {spec.unlawful_action_text}",
                document_order=2,
                evidence=(
                    ClaimEvidenceLink(
                        source_id=unlawful_source.id,
                        anchor_id=unlawful_anchor,
                        purpose="DECISION",
                        relation="SUPPORTS",
                        coverage="FULL",
                    ),
                ),
            ),
        ),
        explanations=(
            SelectionExplanationFixture(
                claim_id=lawful_claim_id,
                legal_terms=(LegalTermExplanationEntry(term=spec.legal_term, explanation=explanation_text),),
                issues=(),
                additional_information_needed=(),
                context=None,
            ),
            SelectionExplanationFixture(
                claim_id=unlawful_claim_id,
                legal_terms=(LegalTermExplanationEntry(term=spec.legal_term, explanation=explanation_text),),
                issues=(),
                additional_information_needed=(),
                context=None,
            ),
        ),
    )


def build_mock_dataset() -> MockDataset:
    """최소 유효 ``MockDataset``을 생성한다.

    8개 경찰_직무_시나리오 각각에 적법 1건·위법 1건의 ``CaseRecord``를 포함하고,
    현행범체포 시나리오의 1심 적법 판례에는 항소심 판례로의 ``relatedInstances`` 연결과
    ``relationToLowerInstance``를 명시한 상급심_정보를 추가한다.
    """

    statute_record, statute_version, statute_source = _statute_fixture()

    cases: list[CaseRecord] = []
    sources: list[SourceRecord] = [statute_source]
    queries: list[QueryFixture] = []
    term_mappings: list[LegalTermMapping] = []
    response_templates: list[ResponseTemplate] = []
    review_fixtures: list[SelectionReviewFixture] = []

    for spec in _SCENARIO_SPECS:
        lawful_case_id = CaseId(f"case-{spec.code}-lawful")
        unlawful_case_id = CaseId(f"case-{spec.code}-unlawful")

        lawful_source = _judgment_source(
            f"source-{spec.code}-lawful",
            lawful_case_id,
            f"{spec.lawful_court} {spec.lawful_case_number} 판결 발췌",
            spec.lawful_excerpt,
        )
        unlawful_source = _judgment_source(
            f"source-{spec.code}-unlawful",
            unlawful_case_id,
            f"{spec.unlawful_court} {spec.unlawful_case_number} 판결 발췌",
            spec.unlawful_excerpt,
        )
        sources.extend((lawful_source, unlawful_source))

        fact_differences: Dict[QueryId, Tuple[FactDifference, ...]] = {}
        related_instances: Tuple[RelatedInstanceRef, ...] = ()
        appellate: Optional[AppellateInformation] = None
        lawful_finality = "확정"

        if spec.code == "arrest":
            # 전체 심급 연결 예시: 현행범체포 1심 적법 판례 -> 항소심 판례.
            appeal_case_id = CaseId("case-arrest-appeal")
            appeal_source = _judgment_source(
                "source-arrest-appeal",
                appeal_case_id,
                "서울고등법원 2019노5678 판결 발췌",
                (
                    "서울고등법원은 원심의 현행범체포 절차가 형사소송법 제211조 요건을 충족한다고 "
                    "보아 검사의 항소를 기각하고 원심의 무죄 판단을 그대로 유지하였다."
                ),
            )
            sources.append(appeal_source)

            related_instances = (
                RelatedInstanceRef(case_id=appeal_case_id, instance="항소심", relation="상급심"),
            )
            appellate = AppellateInformation(
                state="PRESENT",
                decisions=(
                    AppellateDecision(
                        case_number="2019노5678",
                        instance="항소심",
                        court_name="서울고등법원",
                        decision_date="2020-01-15",
                        outcome="항소기각(원심 유지)",
                        relation_to_lower_instance="유지",
                        source_ids=(appeal_source.id,),
                    ),
                ),
            )
            lawful_finality = "미확정"

            fact_differences = {
                QueryId(f"query-{spec.code}"): (
                    FactDifference(
                        id=f"factdiff-{spec.code}-1",
                        dimension="체포 시점",
                        user_fact="범행 직후 바로 체포",
                        case_fact="범행 종료 후 30분이 지난 뒤 체포",
                        conclusion_impact="체포 시점의 시간적 근접성이 현행범체포 적법성을 좌우할 수 있음",
                        could_change_conclusion=True,
                        display_priority=1,
                        source_ids=(unlawful_source.id,),
                    ),
                )
            }

        lawful_case = _build_case(
            case_id=lawful_case_id,
            scenario=spec.scenario,
            instance="1심",
            court_name=spec.lawful_court,
            case_number=spec.lawful_case_number,
            decision_date=spec.lawful_date,
            legality=LegalityStatus.LAWFUL,
            action_text=spec.lawful_action_text,
            court_finding="LAWFUL",
            charge=spec.lawful_charge,
            outcome=spec.lawful_outcome,
            source=lawful_source,
            statute_version_id=statute_version.id,
            statute_source_id=statute_source.id,
            legal_term=spec.legal_term,
            field_expression=spec.field_expression,
            fact_differences_by_query=fact_differences,
            related_instances=related_instances,
            appellate=appellate,
            finality=lawful_finality,
        )
        unlawful_case = _build_case(
            case_id=unlawful_case_id,
            scenario=spec.scenario,
            instance="1심",
            court_name=spec.unlawful_court,
            case_number=spec.unlawful_case_number,
            decision_date=spec.unlawful_date,
            legality=LegalityStatus.UNLAWFUL,
            action_text=spec.unlawful_action_text,
            court_finding="PROBLEM",
            charge=spec.unlawful_charge,
            outcome=spec.unlawful_outcome,
            source=unlawful_source,
            statute_version_id=statute_version.id,
            statute_source_id=statute_source.id,
            legal_term=spec.legal_term,
            field_expression=spec.field_expression,
            fact_differences_by_query=(
                {QueryId(f"query-{spec.code}"): fact_differences[QueryId(f"query-{spec.code}")]}
                if fact_differences
                else None
            ),
            finality="확정",
        )
        cases.extend((lawful_case, unlawful_case))

        if spec.code == "arrest":
            appeal_case = _build_case(
                case_id=CaseId("case-arrest-appeal"),
                scenario=spec.scenario,
                instance="항소심",
                court_name="서울고등법원",
                case_number="2019노5678",
                decision_date="2020-01-15",
                legality=LegalityStatus.LAWFUL,
                action_text="원심의 현행범체포 절차 적법성 판단을 그대로 유지",
                court_finding="LAWFUL",
                charge=spec.lawful_charge,
                outcome="항소기각(원심 유지)",
                source=[s for s in sources if s.id == SourceId("source-arrest-appeal")][0],
                statute_version_id=statute_version.id,
                statute_source_id=statute_source.id,
                legal_term=spec.legal_term,
                field_expression=spec.field_expression,
                related_instances=(
                    RelatedInstanceRef(case_id=lawful_case_id, instance="1심", relation="하급심"),
                ),
                finality="확정",
            )
            cases.append(appeal_case)

        term_mappings.append(_build_term_mapping(spec))

        template_id = f"template-{spec.code}"
        queries.append(
            _build_query_fixture(spec, lawful_case_id, unlawful_case_id, statute_version.id, template_id)
        )
        response_templates.append(
            _build_response_template(spec, template_id, lawful_source, unlawful_source)
        )
        review_fixtures.append(
            _build_selection_review_fixture(spec, template_id, lawful_source, unlawful_source)
        )

    voice_fixtures = (
        VoiceFixture(
            id=VoiceFixtureId("voice-arrest-success"),
            label="현행범체포 상황 설명(성공)",
            failure=False,
            recognized_text="경찰관이 현장에서 범행 직후 바로 잡기 상황입니다.",
            query_id=QueryId("query-arrest"),
        ),
        VoiceFixture(
            id=VoiceFixtureId("voice-unrecognized"),
            label="인식 실패 시연",
            failure=True,
            recognized_text=None,
            query_id=None,
        ),
    )

    scenarios = tuple(
        ScenarioDefinition(id=spec.scenario, label=spec.scenario.value) for spec in _SCENARIO_SPECS
    )

    display_policies = MockDisplayPolicies(
        notices=(
            DisplayPolicyRecord(
                id="notice-legal-safety",
                kind="NOTICE",
                key="LEGAL_SAFETY_NOTICE",
                text=LEGAL_SAFETY_NOTICE_TEXT,
                summary_label="목업 시연 안내",
                full_text=LEGAL_SAFETY_NOTICE_TEXT,
            ),
            DisplayPolicyRecord(
                id="notice-instance-caution",
                kind="NOTICE",
                key="INSTANCE_CAUTION_NOTICE",
                text=INSTANCE_CAUTION_NOTICE_TEXT,
            ),
            DisplayPolicyRecord(
                id="notice-no-realtime-sync",
                kind="NOTICE",
                key="NO_REALTIME_SYNC",
                text=NO_REALTIME_SYNC_LABEL_TEXT,
            ),
        ),
        placeholders=(
            DisplayPolicyRecord(id="placeholder-no-information", kind="PLACEHOLDER", key="정보_없음", text="정보_없음"),
            DisplayPolicyRecord(id="placeholder-unclassifiable", kind="PLACEHOLDER", key="분류_불가", text="분류_불가"),
            DisplayPolicyRecord(
                id="placeholder-confirmation-needed",
                kind="PLACEHOLDER",
                key="확인 필요",
                text="확인 필요",
            ),
            DisplayPolicyRecord(
                id="placeholder-not-confirmed",
                kind="PLACEHOLDER",
                key="확인되지 않음",
                text="확인되지 않음",
            ),
            DisplayPolicyRecord(
                id="placeholder-no-evidence-information",
                kind="PLACEHOLDER",
                key="근거 정보 없음",
                text="근거 정보 없음",
            ),
        ),
        status_labels=(
            DisplayPolicyRecord(id="status-old-law-basis", kind="STATUS_LABEL", key="구법_기준", text="구법 기준"),
            DisplayPolicyRecord(
                id="status-law-basis-indeterminate",
                kind="STATUS_LABEL",
                key="법령_상태_판별불가",
                text="법령 상태 판별 불가",
            ),
            DisplayPolicyRecord(
                id="status-unsupported-query",
                kind="STATUS_LABEL",
                key="UNSUPPORTED_QUERY",
                text="목업에서 지원하지 않는 질의",
            ),
            DisplayPolicyRecord(
                id="status-interpretation-check-needed",
                kind="STATUS_LABEL",
                key="INTERPRETATION_CHECK_NEEDED",
                text="해석 확인 필요",
            ),
            DisplayPolicyRecord(id="status-no-match", kind="STATUS_LABEL", key="NO_MATCH", text="일치하는 목업 자료 없음"),
            DisplayPolicyRecord(
                id="status-source-data-error",
                kind="STATUS_LABEL",
                key="SOURCE_DATA_ERROR",
                text="출처 데이터 오류",
            ),
            DisplayPolicyRecord(
                id="status-similarity-data-error",
                kind="STATUS_LABEL",
                key="SIMILARITY_DATA_ERROR",
                text="유사도 데이터 오류",
            ),
            DisplayPolicyRecord(
                id="status-case-data-inconsistency",
                kind="STATUS_LABEL",
                key="CASE_DATA_INCONSISTENCY",
                text="판례 데이터 불일치",
            ),
            DisplayPolicyRecord(
                id="status-mock-data-insufficient",
                kind="STATUS_LABEL",
                key="MOCK_DATA_INSUFFICIENT",
                text="목업 데이터 부족",
            ),
            DisplayPolicyRecord(
                id="status-explanation-not-found",
                kind="STATUS_LABEL",
                key="EXPLANATION_NOT_FOUND",
                text="목업 자료에서 확인할 수 없음",
            ),
            DisplayPolicyRecord(
                id="status-selection-pending",
                kind="STATUS_LABEL",
                key="SELECTION_PENDING",
                text="선택 대기",
            ),
        ),
        similarity_warnings=(
            SimilarityWarningPolicyRecord(
                id="similarity-warning-high",
                kind="SIMILARITY_WARNING",
                key="HIGH",
                min_inclusive=80,
                max_inclusive=100,
                text="높은 유사도 — 핵심 차이 확인 필요",
            ),
            SimilarityWarningPolicyRecord(
                id="similarity-warning-medium",
                kind="SIMILARITY_WARNING",
                key="MEDIUM",
                min_inclusive=50,
                max_exclusive=80,
                text="중간 유사도 — 직접 적용 전 사실관계 재검토 필요",
            ),
            SimilarityWarningPolicyRecord(
                id="similarity-warning-low",
                kind="SIMILARITY_WARNING",
                key="LOW",
                min_inclusive=0,
                max_exclusive=50,
                text="낮은 유사도 — 결론 근거로 사용 금지",
            ),
        ),
    )

    return MockDataset(
        schema_version="1.0.0",
        dataset_id=DatasetId("dataset-police-case-law-ai-bot-mock-v1"),
        dataset_version="0.1.0",
        normalization_version="v1",
        as_of_date=AS_OF_DATE,
        target_coverage_label=TARGET_COVERAGE_LABEL_TEXT,
        implemented_coverage_label=IMPLEMENTED_COVERAGE_LABEL_TEXT,
        legal_safety_notice=LEGAL_SAFETY_NOTICE_TEXT,
        instance_caution_notice=INSTANCE_CAUTION_NOTICE_TEXT,
        no_realtime_sync_label=NO_REALTIME_SYNC_LABEL_TEXT,
        scenarios=scenarios,
        queries=tuple(queries),
        term_mappings=tuple(term_mappings),
        cases=tuple(cases),
        statutes=(statute_record,),
        statute_versions=(statute_version,),
        sources=tuple(sources),
        response_templates=tuple(response_templates),
        review_fixtures=tuple(review_fixtures),
        voice_fixtures=voice_fixtures,
        display_policies=display_policies,
    )


MOCK_DATASET: MockDataset = build_mock_dataset()
"""모듈 임포트 시 즉시 구성되는 최소 유효 목업 데이터셋 인스턴스."""
