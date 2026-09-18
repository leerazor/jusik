# R1-05 미국 수집 진단

- 상태: 진단 slice 완료; 실제 원인 검증을 포함한 R1-05 전체 acceptance는 차단
- 기록 시각: 2026-09-16 UTC
- 작업 slug: `r1-us-collection-diagnostics`
- 기준/통합: `ef19498632afce9edddac1f5e8aee8e5bbdeff8e` (등록 후 작업 기준 `d9ac948`) / `212f236eafcc9d6930e6f39e0d994ca299db7a30`
- 범위: 미국 Yahoo 수집 결과의 선택적 진단 계약, 심볼별 coverage 대사, 안전한 실패 직렬화와 관련 회귀 검증을 추가했습니다. 기존 membership·사건 cutoff·전략 선택·cache 계약은 유지했습니다.

## 변경과 결정

- `backend/jusik/market_history_approximate.py`에 `CollectionDiagnostics`와 심볼별 `CollectionCoverage` 계약을 추가했습니다. 요청 기간·warmup 시작·고정 reason code·expected/actual/missing/retained/event-excluded 대사를 보존하고, 기존 파일 입력에는 선택 필드로 호환됩니다.
- `backend/jusik/market_data_collector.py`는 parser가 검증한 고유 Yahoo 행만 actual로 집계합니다. identity mismatch는 `CollectorIdentityError`로 구분하며, 명시적이고 시간 순서가 확인된 delisting만 observed_delisting으로 기록합니다. 원래 cutoff를 정하는 split 뒤의 유효한 후속 delisting도 별도 관측으로 보존하고, 장중 모호·미래·상충 자료는 unknown 또는 무원인 상태로 남깁니다. 요청 실패 심볼은 심볼별 `request_excluded`와 aggregate count를 갖고, 알 수 없는 요청 실패는 기존 `unknown` reason과 `request_excluded=true`로 event timing의 `unknown`과 구분합니다. 전체 Yahoo 실패는 모든 심볼의 요청 제외·actual=0·`all_failure` reason을 함께 검증한 typed diagnostics로 `CollectorPartialError`에 첨부합니다.
- `backend/jusik/market_research_cli.py`는 전체 실패 JSON에 구조화 진단만 추가하고 종료 코드 2와 실패 cache 차단을 유지합니다.
- `docs/market-research.md`에 진단 분모·대사·unknown·delisting 정책을 기록했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md` — 선택적 진단 필드와 reason code를 설명했습니다.
- 운영 문서: 해당 없음 — 수집 endpoint·설정·서비스 운영은 바꾸지 않았습니다.
- API·설정·데이터 계약: prepared approximate dataset에 선택적 `collection_diagnostics`를 추가했으며 기존 파일은 계속 읽습니다.

## 검증

- `backend/.venv/bin/python -m pytest -q tests/test_market_data_collector.py tests/test_market_history_approximate.py` — 통과, 155건, 2 warnings.
- `backend/.venv/bin/python -m mypy --config-file pyproject.toml jusik/market_history_approximate.py jusik/market_data_collector.py jusik/market_research_cli.py` — 통과.
- `backend/.venv/bin/ruff check jusik/market_history_approximate.py jusik/market_data_collector.py jusik/market_research_cli.py tests/test_market_data_collector.py` — 통과.
- `backend/.venv/bin/ruff format --diff ...` — 새 변경 hunk는 정리했으며, baseline 원본에도 존재하는 기존 format debt만 남아 있습니다.
- 전체 mypy는 기존 `jusik/research_optimizer.py`의 `torch` import 누락으로 실행 결과가 차단되었고, 변경된 세 source 파일의 strict mypy는 통과했습니다.

## 안전·운영 상태

- 오프라인 합성 transport만 사용했습니다. 네트워크·GPU·PAPER/live·주문·운영 원장·서비스·설정·원격 push 변경은 없습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-05-eae146bd`; Terra 수정 회귀와 fixture bounds는 `validation.json`에 기록했습니다.
- 남은 작업·차단 조건: 실제 공급자 원인 자료는 수집하지 않았으므로 미확인 원인은 unknown/insufficient입니다. 실제 원인 확인을 포함한 R1-05 전체 acceptance는 blocked이며 checkbox는 미체크로 유지합니다. benchmark·미래 관찰 자료를 생성하지 않았고 경제 평가는 not-evaluated입니다. approximate 승격은 없습니다.
- 재개 입력: 해당 심볼·요청 기간·거래소·통화가 고정된 비밀정보 없는 공급자 자료와 명시적인 사건 발생·관측 UTC 시각, 요청 세션 목록이 필요합니다. 자료 확보와 별도 범위 승인 전에는 다른 실패 작업이나 R1-02를 재개하지 않습니다.

## 독립 검토와 main 통합

- Terra가 앞선 split 때문에 뒤의 delisting 진단이 사라지는 문제, 장중 시각의 unknown 누락, 직렬화된 요청 제외 집계 누락을 지적했습니다. 같은 Luna가 수정한 후 전체 실패 상태와 제외 수·reason 사이의 추가 불일치도 보완했습니다. 최종 `dbafd64` 재검토는 PASS입니다. 실패 검토 기록도 audit에 보존했습니다.
- 마지막 `7e23c8c`는 새 조건문 줄바꿈만 수정했습니다. Astra가 AST 동일성을 확인했고, `212f236e`에 병합한 뒤 pytest155·Ruff check·configured strict mypy3 source·diff check가 모두 통과했습니다. 전체 format은 기존 부채 때문에 통과가 아니며, 5개 파일의 format diff 추가/삭제 행이 기준과 정확히 같음을 검증했습니다.
- 재현: 저장소 루트에서 `python3 /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-05-eae146bd/run-integration.py`. 명령·시간·출력은 `integration-verification.json`과 `integrated-*.txt`에 있습니다.
- 검사는 오프라인 CPU·seed0으로 수행했습니다. 신규 transport 시나리오11개와 검증기 회귀를 포함해 테스트12개가 추가됐으며, 최대2심볼·52세션입니다. 검증 실행은900초 한도 안입니다.
- 결과·소스 snapshot·환경 버전·독립 검토·routing 감사·SHA manifest와 audit `HANDOFF.md`를 영구 보관하고40개 증거 파일의 해시를 검증한 후 이번 worktree/branch를 정상 제거했습니다. 기존 루트 `HANDOFF.md`와 다른 차단 작업6개는 보존했습니다.
- 경제 비교 결과를 생성하지 않은 진단 계약 작업이므로 웹 성과 catalog 공개는 해당 없음입니다. 로드맵 checkbox와 단계 상태는 변경하지 않았습니다.
