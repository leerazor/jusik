# 선정 후보 설정 동결

- 상태: 완료
- 기록 시각: 2026-10-03T14:23:07Z
- 작업 slug: `selected-candidate-config-freeze-20261003`
- 기준/통합: `613fc1d3edd7611ff9f981d5c52e98c1b263218c` / 커밋 대기 (worktree Git metadata read-only)
- 범위: 선정 후보 설정 JSON과 비교 규약 해석 및 이 작업의 개발 기록만 갱신. MEMORY·등록부와 런타임 코드는 변경하지 않음.

## 변경과 결정

- `docs/research/selected-candidate-config-v1.json`에 두 후보, 연구 대조값, 미해결 입력, 실행 차단 상태를 고정했다. 금액·비율은 십진 문자열이며 source hash는 네 해당 코드 파일에서 직접 확인한 SHA-256이다.
- 비교 규약에 연구값과 사용자 위험 한도의 구분, SMA 적격성과 순수 보유 기준선 차이, `none`과 FX 필요성, episode 10% latch와 lifetime MDD 20% 필터의 분리를 명시했다.
- `results_observed: false`는 이번 새 설정 실행의 상태로 한정한다. 과거 legacy 실행이 없었다는 뜻으로 사용하지 않는다. legacy 엔진의 자체 회계와 raw 회계 core의 중복 계산 위험도 실행 차단 근거로 적었다.

## 문서·계약 영향

- 사용자 문서: 비교 규약에 새 동결 JSON과 의미 해석을 연결했다.
- 운영 문서: 해당 없음. 운영 동작 변경 없음.
- API·설정·데이터 계약: 실행 불가 상태의 연구 설정 문서만 추가. 런타임 import나 validation framework를 추가하지 않았다.

## 검증

- `sha256sum` 대상 네 의미 소스 — 계획에 기재된 네 hash와 모두 일치.
- JSON 파싱 및 구조·후보·위험값·차단 플래그·source hash 점검 — 완료.
- `git diff --check` — 통과.
- 앱 테스트·빌드 — 문서 전용 변경이므로 실행하지 않음.

## 안전·운영 상태

- PAPER/live 주문, 서비스, DB, 데이터, 실험, 외부 배포 및 원격 push 변경 없음.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: JSON의 `semantic_sources_sha256`에 기록.
- 남은 작업·차단 조건: 입력·기간·비용·코드 hash가 동결되고 회계 경계가 해결될 때까지 후보 실행은 금지.
- 다음 시작: 동결 입력과 raw 회계 연결을 검토하고 JSON의 모든 미해결 값이 근거로 결속된 뒤 별도 승인된 구현 경로를 계획한다.
