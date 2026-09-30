# ICUI 단일 시세 결손 진단

- 상태: 허용된 단일 원문 조회·진단·독립 검토·main 통합 완료. 전체 미국 자료 인수·성과 검증은 미완료
- 기록 시각: 2026-09-30T07:45:09.236273+00:00
- 작업 slug: `us-icui-bounded-gap-20260930`
- 기준/통합: `59eeac7dce8bb80f8f65b4d497a8e3880c19abe5` / `ff5eb6ebd7bfa5c62481f6ee1a9dfd66915dc0a7`
- 범위: 기존 v3 오프라인 감사에서 새로 확인된 ICUI 정확 cache key 1건(2025-08-13~2026-09-11). 생산 코드·mandate·기존 자료 변경 없음.

## 실행과 증거

- source cache의 manifest/raw 139개만 새 audit로 복사·hash 검증했다. 이전 prepared·UNTRUSTED 출력·완료 marker는 복사하지 않았다. scope의 보호 원본 9개 SHA는 전후 일치하고, 새 cache에 marker는 0개다.
- `fetch_icui.py`가 네트워크 시도 전에 `attempt-sentinel.json`을 원자 생성한다. `HttpFetcher.get`의 기존 cache/validator 경로를 사용하며 전용 client가 ICUI의 HTTPS GET·host/path·중복 없는 5개 query 값만 허용한다. TLS 검증, redirect·transport retry 없음, 요청 timeout 30초·전체 60초, Content-Length 선거부와 streaming 10 MiB hard cap을 적용했다. 같은 key 재실행은 sentinel과 새 audit preflight가 차단한다.
- 실제 GET 1회, HTTP 200, 원문 30,776 bytes. `parse_yahoo_chart`의 ICUI·NAS·USD·OHLCV 검증을 통과해 기존 cache 계약으로 원문 1건만 저장했다(139→140). body/cache SHA-256 `235e3d73e29b98a6ae6ebbbc88f3a4ca31d4280fff96bd317b4663ffdc1bc417`. 다른 24개 실패 key의 요청은 없다.
- 거래소 달력의 예상 272세션과 ICUI 일봉 272세션이 정확히 일치하며 날짜 결손·범위 밖 세션이 각각 0이다. 이 원문에는 배당·분할 event가 0건이므로 이 종목의 occurrence/observed 시각 결손도 0이다. 다른 종목의 사건 125행이나 전체 sample100 결손 해소를 뜻하지 않는다.
- `result.json`은 `diagnostic_only=true`, `research_input=false`, `performance_eligible=false`다. 준비 dataset·완료 marker·전략·NAV·비용 성과·주문은 생성/실행하지 않았다. audit 전체 크기 약 5.13 MB는 100 MiB 사전·사후 점검 기준 이내다(저장소 hard limit 아님).

## 검증·재개

- 단일 script Ruff check/format·strict mypy 통과 후 1회 실행했다. `binding.json`에 script SHA `6697b76e01ccdcc1c617c8f8774638c323ab82fd0eef417af0a338b5536224ef`, result SHA `08194d7f5cba483839e3a92316c7b56dccacc17e642dd1e70bb69860700602d9`, scope/attempt SHA를 결속했다. 결과·cache entry·원본 hash·marker 0·시도 1 불변식을 확인했다. 코드 변경이 없어 기존 focused pytest 247개는 반복하지 않았다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-icui-bounded-gap/` (`scope.json`, `attempt-sentinel.json`, `fetch_icui.py`, `result.json`, `binding.json`, `cache-copy/`). 입력은 이전 [v3 오프라인 감사](2026-09-30-us-v3-offline-cache-audit.md)의 새 key다.
- 다음은 남은 24개 동일 실패 요청을 반복하지 않고 사건별 역사 관측시각 근거를 별도 scope로 검토한다. 감독자 보존 `next-source-scope-input.json`·`next-source-scope-review.json`은 AOS 1건 후속 범위의 출발점이다. Yahoo fetch 시각을 과거 event 관측시각으로 대체하지 않는다.

## 통합·문서 영향

- 구현 `00a7cb2f455d7a0b232db5380af4e0225f98c59b`, 독립 review PASS(단일 원문 진단 한정), main 통합 `ff5eb6ebd7bfa5c62481f6ee1a9dfd66915dc0a7`. `review-final.json`, `integration.json`, `routing-code.json`, `routing-review.json`에 결과와 모델 실행 근거를 보존했다.
- main 전체 backend tree가 scope 기준과 같으며, 원본9 hash·script/scope/result/sentinel 결속·marker0·실제요청1의 통합 검증 PASS. 기존 247 tests와 reviewer의 140 raw hash 검사 근거를 재사용했고 추가 조회·수집 실행은 없었다.
- 기능·API·설정·데이터 계약 변경이 없어 별도 기능 문서 수정은 필요 없다. 작업 등록부·MEMORY 진입점·인계를 갱신했다. `environment.json`과 audit 결과를 보존한 뒤 깨끗한 작업 워크트리·브랜치를 정리했다. 사용자 루트 `HANDOFF.md`는 보존했고 runner는 paused/inactive를 유지했다. 결제·권한·자격증명·원격 push 변경 없음.
- 후속 자료의 캐시 출발점은 이 audit의 `cache-copy/` 140개이며 manifest SHA `2584c27430262169a88154fccd4a598c2cd012b57ed6861975da67e3ebed322e`다. ICUI를 재조회하거나 오래된 139개 cache만 재사용해 결손으로 되돌리지 않는다.
- 독립 읽기 조사로 기존 사건125개는 배당115·분할10, 37심볼 모두 observed_at 결손임을 분류했다. 다음 AOS 배당1건은 raw 금액·날짜·해시를 고정한 뒤 공식 발행사/SEC 검색1회·원문열람2회 이내의 별도 scope로 검토한다. 날짜만 제공되면 정밀 시각을 만들지 않는다. 아직 실행하지 않았다.
