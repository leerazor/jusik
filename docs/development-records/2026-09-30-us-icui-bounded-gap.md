# ICUI 단일 시세 결손 진단

- 상태: 허용된 단일 원문 조회·진단 완료, 독립 검토·main 통합 대기. 전체 미국 자료 인수·성과 검증은 미완료
- 작업 slug: `us-icui-bounded-gap-20260930`
- 기준/통합: `59eeac7dce8bb80f8f65b4d497a8e3880c19abe5` / 감독자 확정 예정
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
