# R2-02 통합 후 전체 회귀 재검증

## 결과

2026-09-24 현재 main(`019ed3e` 포함)에서 backend 전체 pytest를 실행했다.

- `1776 passed, 2 failed, 2 warnings`
- 실패 1: `test_copy_is_exactly_the_guarded_variant` — 현재 portfolio engine variant SHA와 동결 실험 SHA 불일치
- 실패 2: `test_frozen_archive_replay` — immutable timestamp-forensics archive의 `research_market_calendar.py` SHA 불일치

두 실패는 R2-02 변경으로 발생한 런타임 실패가 아니라 기존 고정 provenance와 현재 source drift를 strict fail-closed로 감지한 것이다. archive overwrite, variant hash 갱신, 검증 완화는 하지 않았다.

## 판단

R2-02 비용 진단 통합 후 관련 focused 테스트는 30개 통과했으며 전체 회귀의 기존 provenance 차단 2건은 유지한다. 경제 acceptance와 historical archive replay 승격은 별도 source 재등록 없이는 수행하지 않는다.
