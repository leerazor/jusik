# 등록 종목 배당 검토 상태 표시

- 상태: 구현·백엔드 검증 완료, 프런트 의존성 및 독립 화면 검토 대기
- 기록 시각: 2026-10-03T14:47:09Z
- 작업 slug: `approved-dividend-review-status-20261003`
- 기준/통합: `e0b3d1cc92865455328871b2452032b1aafc131c` / 없음
- 범위: 등록 종목 readiness의 배당 원천 비교 상태만 집계·표시한다. 가격 경로, DB schema, 원천 자료, 성과·주문 경로는 변경하지 않았다.

## 변경과 결정

- `backend/jusik/approved_universe_readiness.py`: 각 배당 이벤트의 최신 revision에 연결된 가장 큰 review sequence 한 행만 상태별로 집계한다. 관측·검토·일치·부분·불일치의 건수 무결성을 검사한다. 최신 상태 오류나 중복행은 배당 원천 전체를 `unavailable`로 닫고 건수를 `null`로 돌려준다. 현재 revision 또는 review가 없으면 그 이벤트는 미검토다.
- 원천에는 market/exchange가 없어 동일 symbol의 다른 등록 identity가 있으면 모든 충돌 행의 배당 건수만 숨긴다. 가격 조회와 `identity_status=not_checked`는 유지한다. 이벤트가 없는 고유 symbol은 원천 사용 가능 시 다섯 건수가 0이다.
- `frontend/app/research/approved-universe/contract.ts`, `editor.tsx`: nullable 0 이상 상태 건수를 계약에 추가하고 관측·검토·일치·부분·불일치·미검토를 표시한다. 결손 또는 불일치는 `조회 불가`로 표시하며 `null`을 0으로 바꾸지 않는다. 일치가 신원·적격·총수익률·성과 검증이 아님을 명시한다.
- `backend/tests/test_approved_universe_readiness.py`: 합성 현재/과거 revision과 복수 review sequence, 합성 TQQQ 13건 불일치, 미검토·0건·원천 실패·알 수 없는 상태·중복 최신행·symbol 충돌 및 API 계약을 검증한다. 실제 TQQQ DB는 읽지 않았다.

## 문서·계약 영향

- 사용자 문서·API 계약: `docs/research.md`의 readiness 응답 필드, 최신 검토 선택, fail-closed, symbol 연계 한계를 갱신했다.
- 운영 문서: 해당 없음. 서비스나 자료 저장 계약을 바꾸지 않았다.

## 검증

- `timeout 30s env PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_approved_universe_readiness.py` — 13개 통과.
- `backend/.venv/bin/ruff check backend/jusik/approved_universe_readiness.py backend/tests/test_approved_universe_readiness.py` 및 `ruff format --check` — 통과.
- `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict backend/jusik/approved_universe_readiness.py backend/tests/test_approved_universe_readiness.py` — 통과.
- 프런트 ESLint·tsc·Next build — 이 워크트리의 `frontend/node_modules`가 없어 로컬 실행 파일 부재(exit 127). 사용자 제한에 따라 네트워크/의존성 설치 없이 보류했다. Next 로컬 가이드도 같은 이유로 열 수 없었다.
- 독립 화면 검토 — supervisor 수행 예정. 이 기록은 화면 검토 PASS 또는 실제 성과 검증을 주장하지 않는다.

## 안전·운영 상태

- 운영 DB·원천·계좌·서비스·주문·성과 실험·네트워크·의존성·원격 push 변경 없음. 테스트 DB는 pytest의 임시 경로에만 생성했다.

## 증거와 재개

- 계획: `/tmp/approved-dividend-status-plan-result.txt`. 실제 자료 확인 없이 합성 테스트만 사용했다.
- 남은 작업: 해당 워크트리의 기존 `frontend/node_modules`가 마련되면 lint/typecheck/build와 fixture 화면 검토를 수행하고 독립 코드 검토 후 supervisor가 통합한다.
- 다음 시작: 변경 diff와 백엔드 검증을 확인한 뒤 프런트 로컬 의존성·화면 검토 가능 여부를 점검한다.

## workflow 평가

- workflow 판단: 도움 됨 — 기존 readiness 조회와 UI 계약만 확장해 새 저장소·API·상태 체계를 만들지 않았다.
- 근거: 기존 endpoint 회귀와 신규 합성 분기 검사를 한 파일에서 확인했다. 프런트 검사는 로컬 의존성 부재로 미확인이다.
- 비용 절감 효과: 비교 자료가 없어 미측정.
