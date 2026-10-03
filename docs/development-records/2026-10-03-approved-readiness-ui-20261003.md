# 등록 종목 자료 현황 화면

- 상태: 구현·격리 검증 완료, 통합 대기
- 작업 slug: `approved-readiness-ui-20261003`
- 기준: `8ec5057`; 통합 SHA: supervisor 기록 예정
- 범위: 승인 목록별 가격 수집 메타데이터, 배당 검토 기록 수, USD/KRW 관측 날짜의 읽기 전용 API와 화면. 성과 비교와 주문은 연결하지 않음.

## 변경과 결정

- `approved_universe_readiness.py`는 등록 목록을 한 번 읽은 결과를 받아 가격 저장소 `statuses()`의 메타데이터, 현재 이벤트 revision에 대한 좁은 배당 SQL, USD/KRW 날짜 집계 SQL을 읽는다. 원천 DB가 없거나 오류이면 수치 `null`과 `unavailable`로 표시하고 오류 원문을 출력하지 않는다.
- 가격과 기업행동의 기존 저장 키는 코드만 포함한다. 동일 코드의 시장·거래소 신원이 확인되지 않아 `identity_status=not_checked`로 고정하며 자료 적격을 선언하지 않는다. 여러 DB 조회는 원자적이지 않다.
- 독립 코드 검토 후 가격 SQL을 등록 코드의 명시 메타데이터 열로 제한하고 음수 봉 수는 해당 종목 가격만 조회 불가로 닫았다. 환율은 중간 날짜까지 최대 10,001개를 검증해 잘못된 날짜나 상한 초과 시 FX만 조회 불가로 닫았다.
- 목록 저장으로 revision이 바뀌면 화면은 옛 현황을 숨긴다. 새로고침은 현재 revision과 일치하는 응답만 보여준다. 화면은 목적, 현재 확인 결과의 한계와 다음 검증 행동을 한국어로 설명한다.

## 문서·계약 영향

- API 및 사용자 흐름: `docs/research.md`의 readiness 계약 갱신.
- 운영 배포·거래 설정 변경 없음.

## 검증

- `backend/.venv/bin/python -m pytest -q backend/tests/test_approved_universe_readiness.py backend/tests/test_approved_universe.py::test_store_empty_normalization_atomicity_and_stale -o cache_dir=/tmp/readiness-review-fix-pytest` — 8 passed. DB 미존재, 부분/이전 성공 가격, 요청보다 늦은 이력, 최신 배당 revision, 이벤트 0, FX 날짜 중복·잘못된 중간 날짜·상한 초과, 음수 봉 수의 국소 실패, 등록 코드 한정 SQL, DB 오류, 원문 오류 비노출, 바인딩된 API의 revision·순서·no-store를 확인했다.
- `backend/.venv/bin/python -m ruff check --no-cache ...`, `ruff format --check ...`, `mypy ... --follow-imports=silent` — 통과.
- `tsc --noEmit --incremental false`, `npm run lint`, `NEXT_DIST_DIR=.next-build-approved-readiness npm run build` — 통과. Next가 자동 수정한 `tsconfig.json`, `next-env.d.ts`는 원상복구했다.
- 격리 API 8013과 화면 3013 HTTP 200. API는 `Cache-Control: no-store`, `comparison_status=not_performed`; 화면은 현재 수집/기록 없음 혼합 예시를 표시했다. launcher: `/tmp/approved-readiness-private/launch-preview.sh`.
- 전체 기존 `test_api_isolated_from_operations_universe`는 TestClient 수명주기 종료 대기에서 중단했다. 새 endpoint는 격리 HTTP로 별도 확인했다.

## 안전·운영 상태와 재개

- 실제 주문·PAPER·운영 universe·외부 배포·원격 push 없음. 로컬 격리 preview만 사용.
- 다음 단계: 종목 신원, 공식 달력과 배당·분할·환율의 거래 시점 가용성 및 비용을 검증하고 비교 조건을 고정한다.
- 독립 화면 검토가 지적한 비교 주체·평가 기간·전문 용어의 설명을 화면 상단과 가격 행에 반영했다. 실제 참가자 연구가 아닌 agent 화면 검토다.
- workflow 판단: 도움 됨 — 기존 메타데이터/DB를 재사용하고 원문 수집을 반복하지 않았다. 절감 시간과 호출 수는 미측정. 다음 조정: 유지.
