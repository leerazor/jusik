# 등록 종목 자료 현황 화면

- 상태: main 통합·운영 배포·검증 완료
- 작업 slug: `approved-readiness-ui-20261003`
- 기준: `8cac68b`; 병합 직전 main: `c17a55e`; 통합 SHA: `262699bcf5ba675b785e247aeeb56a2ded239e35`
- 범위: 승인 목록별 가격 수집 메타데이터, 배당 검토 기록 수, USD/KRW 관측 날짜의 읽기 전용 API와 화면. 성과 비교와 주문은 연결하지 않음.

## 변경과 결정

- `approved_universe_readiness.py`는 등록 목록을 한 번 읽은 결과를 받아 등록 코드의 가격 메타데이터 열, 현재 이벤트 revision의 배당 검토 건수, USD/KRW의 서로 다른 관측 날짜를 좁은 읽기 전용 SQL로 조회한다. 원천 DB가 없거나 오류이면 수치 `null`과 `unavailable`로 표시하고 오류 원문을 출력하지 않는다. 음수 봉 수는 해당 가격만, 잘못된 환율 날짜나 10,000일 초과는 FX만 조회 불가로 닫는다.
- 가격과 기업행동의 기존 저장 키는 코드만 포함한다. 동일 코드의 시장·거래소 신원이 확인되지 않아 `identity_status=not_checked`로 고정하며 자료 적격을 선언하지 않는다. 여러 DB 조회는 원자적이지 않다.
- 목록 저장으로 revision이 바뀌면 화면은 옛 현황을 숨긴다. 새로고침은 현재 revision과 일치하는 응답만 보여준다. 화면은 목적, 현재 확인 결과의 한계와 다음 검증 행동을 한국어로 설명한다.

## 문서·계약 영향

- API 및 사용자 흐름: `docs/research.md`의 readiness 계약 갱신.
- 기존 `start.sh`로 운영 웹을 배포했다. 거래 설정 변경 없음.

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

## 통합·배포 확인

- 최종 구현 `012acdd`에 독립 코드 검토 PASS. 화면 검토 PASS, 격리 브라우저에서 저장 후 이전 현황 숨김 → 새로고침 후 새 목록 표시를 확인했다. explore/plan/code/review/화면 review 라우팅 사후 검사 모두 PASS.
- main에서 focused pytest 8 passed와 Ruff 통과. `start.sh`의 운영 Next 빌드 통과, API 8000/8001과 웹 3000 정상 시작. 기존 TestClient 수명주기 전체 검사는 미완료이며 전체 suite 통과로 해석하지 않는다.
- `jusik-web-stack.service` 사용자 transient unit으로 실행했다. 이 unit은 현재 로그인 환경에서 실패 시 재시작하며 재부팅 자동 시작 설치는 하지 않았다. 기존 인증 정책 유지, 외부 비인증 401/인증 200 확인. 웹: https://hamster-bucket-neatness.ngrok-free.dev/research/approved-universe
- 운영 readiness: revision 1, 등록 16종목, `comparison_status=not_performed`, `Cache-Control: no-store`, FX 925일(2023-03-13~2026-10-01). 데스크톱과 390px 모바일 렌더링, 가로 넘침 없음.
- 화면의 배당 **검토 기록이 있는 이벤트 14건**과 별도 coverage의 **적격 13건**은 다른 수치다. 부적격 검토 기록도 존재하므로 UI는 적격 수나 순수익 검증으로 표시하지 않는다. 관측 이벤트는 111건이며 전체 수집 완전성은 미확인이다.
- supervisor가 운영 배포를 수행했다. 실제 주문·PAPER 승격·원격 push·GitHub Pages는 수행하지 않았다. 이전의 격리 검증 설명은 구현 담당 단계의 범위다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261003-approved-readiness-ui/manifest.json`; SHA-256 `f97362476168944c74f7c8e0406631e0cbda127ca954b5b4a764a5a7d764668e`. 화면·운영 응답·배포 검증·routing 결과 보존.
- preview 종료와 산출물 보존 후 `/home/kwl/projects/jusik-approved-readiness-ui` 및 병합 브랜치 정리 완료. 사용자 소유 루트 `HANDOFF.md` 보존.
- 후속 작업: [MSFT 배당 검증 기록](2026-10-03-msft-dividend-review.md)과 [재개 지점](../handoffs/2026-10-03-approved-readiness-ui-20261003.md)을 읽고 공식 자료·비용 및 비교 조건 검증을 이어간다. 같은 대화 30분 heartbeat가 활성화되어 있다.
