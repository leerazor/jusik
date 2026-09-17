# Market research mandate digest repair

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `market-research-mandate-digest-repair`
- 기준/통합: `c6d2bf9a2f01fa470fe9783a04dcc10133d690d9` / 구현 커밋 참조
- 범위: 합법적인 후속 `docs/market-research.md` 문서 갱신으로 생긴 digest drift만 매니페스트에서 수정하고, 거버넌스 정책·문서 내용·runner 상태는 보존했습니다.

## 변경과 결정

- `docs/market-research.md`의 tracked bytes SHA-256이 매니페스트의 기존 `b3c8a67ee853aa16eb072ea029b4307ec102f7aba24b59ef4ac958f8e5523c75`와 달랐고, 현재 값 `2e9f329a13d8f9ea58ec5064400f27e25cfd01b267063bf35f182d302332ea7e`로 해당 한 줄만 갱신했습니다.
- manifest 변경 이후 유효한 다른 네 항목, legacy execution identity, governance projection, mandate marker와 roadmap `policy_version`을 대조했습니다.
- drift 원인은 manifest 갱신 뒤의 정상적인 문서 변경입니다. `977c0dd`(frozen NAV metrics), `a6f8d05`(US event timing invariance), `a47b1a8`(unknown US membership gaps)가 `docs/market-research.md`만 후속 변경했으며, `git log`와 diff로 내용 변조나 정책 identity 변경이 아님을 확인했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md` 내용은 변경하지 않았습니다.
- 운영 문서: 해당 없음. runner 운영 상태 설명은 보존했습니다.
- API·설정·데이터 계약: 해당 없음. checksum manifest 한 항목만 정정했습니다.

## 검증

- 기준 상태에서 governance/roadmap 관련 pytest를 재현한 결과 digest drift로 5개가 실패했습니다. 핵심 disabled/not-ready 회귀 3건은 `test_disabled_governance_blocks_run_resume_and_cli_without_state_mutation` 및 두 dirty governance swap 테스트입니다.
- `validate_mandate(Path('.'))` — 통과; JSON digest `9643a23000674c9461e3f102511b395817a01deb90b480c4c67738fd17ef54c0`, policy `investment-roadmap-governance-v1`, `dispatch_enabled=false`.
- `validate_dispatch_gate(Path('.'))` — `investment roadmap governance is disabled`로 fail-closed.
- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m pytest backend/tests/test_research_mandate_governance.py backend/tests/test_development_runner_roadmap.py -q` — 34 passed.
- 세 핵심 회귀 테스트 직접 실행 — 3 passed; state mutation assertion 모두 통과.
- 인접 runner/research 테스트 — 163 passed, 2 기존 deprecation warnings.
- service/timer read-only 확인 — service `inactive`, timer `inactive`·`disabled`.
- 실행하지 않은 검사: 실제 runner resume/dispatch, 외부 수집, PAPER/live, 주문, 운영 DB/config 변경, remote push.

## 안전·운영 상태

- runner는 계속 disabled/not-ready fail-closed 상태이며 service/timer를 enable·resume하지 않았습니다. 실제 주문·PAPER/live·DB·서비스·remote는 변경하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: `docs/market-research-mandate.sha256`; hash: 위 old/new digest와 validator 결과.
- 남은 작업·차단 조건: 없음. 자동 연구는 기존 운영자 승인 게이트가 해제될 때까지 비활성입니다.
- 다음 시작: 운영자가 별도 승인하기 전까지 runner를 enable/resume하지 않습니다.
