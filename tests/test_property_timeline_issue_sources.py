"""Property 34: 타임라인 쟁점 또는 없음 상태와 출처 유효성 (task 13.6).

유효 목업 출처 registry에서 생성한 쟁점 연결을 타임라인 projection에 적용한다.
쟁점이 없으면 정확히 하나의 ``연결 쟁점 없음`` 상태가, 쟁점이 있으면 모든 쟁점과
사전 연결된 판례·법조문 출처가 누락 없이 유지되어야 한다.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.models_timeline import IssueLink, RecognizedEvent
from data.validated_dataset import ValidatedDataset
from domain.ids import EventId
from domain.timeline import NO_ISSUE_LINKED_LABEL, project_event_issues


def _event_with_issues(issue_links: tuple[IssueLink, ...]) -> RecognizedEvent:
    """Property 입력을 위한 최소 인식 사건을 만든다."""

    return RecognizedEvent(
        id=EventId("timeline-property-event"),
        original_text="타임라인 속성 테스트 사건",
        action="조치",
        original_order=0,
        issue_links=issue_links,
    )


# Feature: police-case-law-ai-bot, Property 34:
# 타임라인 쟁점 또는 없음 상태와 출처 유효성
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_timeline_issues_or_no_issue_and_sources_are_valid(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
) -> None:
    """**Validates: Requirements 11.8, 11.9**

    빈 쟁점 목록은 유일한 없음 상태가 되고, 비어 있지 않은 목록은 원래 순서와
    출처 ID를 보존한다. 모든 표시 출처는 검증된 registry의 판례 또는 법조문
    출처 레코드로 해석된다.
    """

    source_ids = tuple(validated_mock_dataset.sources_by_id)
    issue_count = data.draw(st.integers(min_value=0, max_value=5))
    issue_links = tuple(
        IssueLink(
            issue=f"쟁점 {index}",
            source_ids=tuple(
                data.draw(
                    st.lists(
                        st.sampled_from(source_ids),
                        min_size=1,
                        max_size=4,
                    ),
                    label=f"issue_{index}_source_ids",
                )
            ),
        )
        for index in range(issue_count)
    )

    projection = project_event_issues(_event_with_issues(issue_links))

    if not issue_links:
        assert projection.issues == ()
        assert projection.no_issue_label == NO_ISSUE_LINKED_LABEL
        return

    assert projection.issues == issue_links
    assert projection.no_issue_label is None
    for issue in projection.issues:
        assert issue.source_ids
        for source_id in issue.source_ids:
            source = validated_mock_dataset.sources_by_id.get(source_id)
            assert source is not None
            assert source.owner.type in {"CASE", "STATUTE"}
