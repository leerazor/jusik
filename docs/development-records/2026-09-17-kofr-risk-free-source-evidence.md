# KOFR 원천 증거 수집

- 상태: 차단
- 기록 시각: 2026-09-17T00:00:00Z
- 작업 slug: `kofr-risk-free-source-evidence`
- 기준/통합: `efbf82cf0e8d9d7de31a4d8daa7df0231ce73400` / 없음 (endpoint validation 실패)
- 범위: 공식 KOFR 원문을 한 번만 bounded하게 수집하는 표준 라이브러리 collector,
  XML parser/verifier, 불변 audit 산출물과 focused fake-transport 테스트를 추가했다.
  readiness, metrics, policy, strategy, runner, API와 적용 근거는 변경하지 않았다.

## 변경과 결정

- endpoint·task·action·언어·canonical 날짜는 코드 상수와 request XML에 고정했다.
- 실제 관측된 KSD 응답 계약은 root `<vector result="N">`와 N개의 sibling
  `<data><result>...</result></data>`이다. wrapper root, `RECORD_COUNT`, 한 data
  아래 다중 result는 legacy/변조 shape로 거부한다.
- Decimal projection은 유효숫자·조정 지수·출력 길이를 bounded하게 검사하고
  tuple 기반으로 정규화해 ambient precision의 반올림과 exponent expansion을 막는다.
  audit 파일은 `O_NOFOLLOW` descriptor-relative read/write로 symlink escape를
  차단하며, transport 전에 audit parent 전체를 preflight한다. verifier는 request
  원문·hash와 namespace 없는 정확한 XML tag/attribute/text shape도 대조한다.
- XML MIME/UTF-8, DTD/entity, 응답 크기·깊이·행·필드, 선언 행수, 날짜 범위·중복,
  유한 Decimal, `PUBN_DTTM` raw 형식을 fail-closed로 검증한다.
- request와 attempt를 네트워크 전에 배타적으로 만들고, raw는 SHA-256 경로에
  저장한다. tracked evidence JSON은 전체 원문 행과 projection, raw SHA/size,
  제한사항을 포함하며 오프라인에서 원문과 재검증한다.

## 문서·계약 영향

- 사용자 문서: `docs/market-performance-metrics.md`에 source evidence와 적용
  근거를 혼동하지 않는 계약을 추가했다.
- 운영 문서: 해당 없음. 운영 서비스·DB·설정은 변경하지 않았다.
- API·설정·데이터 계약: 신규 source evidence schema만 추가했으며 readiness 누락
  code와 blocked 상태를 보존했다.

## 검증

- `python -m pytest tests/test_kofr_source_evidence.py -q` — 실행 불가: 작업 트리의
  backend `.venv`와 pytest가 없다(패키지 설치하지 않음).
- `python -m py_compile jusik/kofr_source_evidence.py tests/test_kofr_source_evidence.py`
  — 통과.
- 표준 라이브러리 fake test harness — 위협·원문 고정·Decimal bounds·symlink·request
  hash·정확한 XML shape 포함 전체 함수 통과.
- 차단 후보 hardening commits: `2eef27c`, `3d6c7b3`.
- 추가 경계 수정은 transport 전 symlink parent 거부와 namespace/text-tail 회귀를
  포함한다.
- 실제 공식 수집 — production CLI를 정확히 1회 실행했으나 당시 parser 계약이
  `RECORD_COUNT` wrapper를 잘못 가정해 `invalid_record_count`로 차단했다. 실제
  관측 shape로 parser를 수리했지만 재요청은 금지되어 end-to-end 성공은 입증하지
  않았다. 후속 semantic 실패에서는 bounded HTTP 200 raw와 `failure.json`을 먼저
  보존하도록 수집 흐름을 보완했다.

## 안전·운영 상태

- 테스트는 fake transport만 사용하며 실제 주문·PAPER/live·서비스·운영 DB·원격
  push를 수행하지 않는다. 공식 수집은 canonical audit 경로에서 단 한 번만 한다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-kofr-risk-free-source-evidence`;
  실패 시도에서 `attempt.json`과 `request.xml`만 생성됐다.
- 남은 작업·차단 조건: pytest/Ruff/mypy는 전용 환경이 제공되면 재실행해야 한다.
  공식 응답 계약 검증 실패로 성공 artifact와 commit을 만들지 않았다. audit에는
  배타적 attempt와 request만 남아 있으며, 같은 경로의 재요청은 금지된다.
- 다음 시작: 감독자가 공식 응답의 실제 vector/count 계약을 별도 승인·계획한 뒤,
  새 audit attempt에서 parser 계약을 조정하고 단일 수집을 다시 수행한다.
