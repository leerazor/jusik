# 외부 readiness trust-boundary 우선 결정 준비

- 상태: 완료 (권고 문서 준비; 사용자 결정 전 trust-boundary 구현·적용은 PENDING)
- 기록 시각: 2026-09-28T05:01:12Z
- 작업 slug: `trust-boundary-priority-decision-v1`
- 기준/통합: `e2c2bbcd228c96db3be4b1e65a940a8096098ab1` / 설계 문서 `bfe477b81bbe7a5736428be0e5eea83b0e5d57df` (local `main` fast-forward)
- 범위: 사용자가 요청한 한 개의 우선 trust-boundary 결정과 권고를 짧게 정리하고 나머지 설계 결정을 분리했습니다. trust 구현은 하지 않았습니다.

## 변경과 결정

- [trust-boundary 결정안](../development-runner-readiness-trust-boundary.md)은 실행 actor와 독립 hash/trust-root의 owner·control channel을 하나의 우선 사용자 결정으로 묶습니다. 권고는 producer/validator와 분리된 trust-root owner와 별도 run controller를 두는 역할 분리입니다. 보호된 저장소 manifest + 별도 controller와 별도 host/attestation service를 대안으로 비교하고 각각의 보안 한계와 운영 부담을 남겼습니다.
- 실행·receipt attestation 형식과 원자 publication, v1 bridge, hash/key 갱신·철회·freshness 및 과거 receipt 처리, 실패·복구, scheduler 연결은 별도 사용자 승인 대상입니다. 우선 역할 선택만으로 이 후속 범위를 승인하지 않습니다.
- 현재 실제 owner·ACL·독립 channel은 확인되지 않았습니다. 과거 collector source hash는 null이고 v1은 실행 actor가 receipt를 만들었다는 증명을 제공하지 않습니다. 실제 owner와 control 경계가 지정·검증되기 전까지 publisher, attestation, pin, scheduler binding과 readiness 연결은 계속 `PENDING`입니다.
- 임시 신뢰 정책은 추가하지 않았고 mandate, 자료 수용 기준, 투자 기준, OOS gate는 변경하지 않았습니다.

## 문서·계약 영향

- 사용자/운영 문서: 기존 준비용 trust-boundary 문서만 한 결정과 후속 항목 중심으로 압축했습니다.
- API·설정·데이터 계약: 변경 없음.

## 검증

- `git diff --check e2c2bbcd228c96db3be4b1e65a940a8096098ab1..bfe477b81bbe7a5736428be0e5eea83b0e5d57df` — 통과.
- 독립 `role.review` — 우선 결정 한 건, 권고·대안·후속 승인 분리, PENDING 유지 및 scope 보존 확인; material finding 없음.
- `role.explore/gpt-6-luna`, `role.plan/gpt-6-sol`, `role.code_small/gpt-6-luna`, `role.review/gpt-6-sol`의 model-routing resolve/check와 preflight 및 `check_routing.py post` — 모두 PASS.
- 문서 전용 변경이라 코드 테스트, lint, type check는 실행하지 않았습니다.

## 안전·운영 상태

- publisher, scheduler, trust-root, key/hash pin 코드 및 외부 producer 자료는 수정하지 않았습니다. 비용·credential·시장자료·PAPER/live·주문·외부 서비스 설정·remote는 사용하거나 변경하지 않았습니다.
- 수동 문서 통합 절차에 따라 개발 runner를 일시 pause했습니다. 최종 정리 때 이전 상태로 복구합니다. 사용자 소유 루트 `HANDOFF.md`는 계속 보존합니다.

## 증거와 재개

- 남은 결정: 실제 독립 trust-root owner, 실행 controller, 양쪽 권한·독립 배포/통신 경로의 지정과 입증. 이 결정은 사용자 승인이 필요합니다.
- 다음 시작: 해당 결정이 승인되고 실제 control boundary 증거가 준비되면 그 범위만 별도 scope review합니다. 승인 전에는 implementation을 시작하지 않습니다.
