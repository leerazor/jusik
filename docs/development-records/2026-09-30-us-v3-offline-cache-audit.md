# 미국 v3 캐시 오프라인 감사

- 상태: 자료 요청 범위 진단 완료, 독립 검토·main 통합 대기. 데이터 인수·성과 검증은 미완료
- 기록 시각: 2026-09-30T07:13:09Z
- 작업 slug: `us-v3-offline-cache-audit-20260930`
- 기준/통합: `f37d4a3b8499296cf7a240c36eb07112c8c9cbd7` / 감독자 확정 예정
- 범위: 미국 2025-09-11~2026-09-11, warmup 20세션, sample100, v3 수집 경로를 기존 cache 복사본에서 deny-all로 1회 검사. 생산 코드·mandate·원본 자료 변경 없음.

## 실행과 결과

- 기존 cache의 manifest/raw만 새 audit의 `cache-copy`로 복사했다. 139개 raw의 hash를 복사본에서 1회 검증했고 총 4,990,768 bytes, manifest SHA `95e6bea955905e44b661f485ed0e0fe18f6b8722a86f99e1b0616d3c072d41ba`는 probe 전후 같다. baseline의 보호 파일 7개 SHA도 실행 전후 일치한다. 완료 marker는 복사하지 않았다.
- `httpx.MockTransport`가 모든 cache miss를 거부했다. 가상 거부 25건은 전부 Yahoo GET·동일 기간·옵션의 정확한 cache key로 고정했고, 비Yahoo miss·키 오류·초과 예산은 완료 실패로 처리했다. 실제 시장 요청 0건, 가상 거부 상한 300, collector 예산 300, timeout 60초, 별도 재시도 0이다.
- 기존 v2 miss 27개와 새 v3 miss 25개의 정확 key 비교: 이전 실패 24개는 그대로, `MET-P-F` 요청은 사라지고 `ICUI`가 새 key로 들어왔다. 이전에 검증·저장된 `CFG`·`NOEM` 두 응답은 cache에서 재사용했다. 이전 diagnostics 누적 101종목과 새 101종목의 차이도 `MET-P-F` 제거·`ICUI` 추가다. 이는 누적 진단 목록 비교이며 checkpoint 전체 listing 재구성이나 100종목 자료 완전성 판정이 아니다. 일별 실제 universe 행 수는 양쪽 모두 75~76 범위다.
- Mock 실패에도 생성된 v3 출력은 `offline-UNTRUSTED-v3.json`(SHA `39b87099703c1603bcf242cf5b85c74ae4b4a6ac0eae1878f7d9a2e0f6753ac8`)으로 격리했다. v3 완료 marker는 같은 audit의 `quarantine/`으로 원자 이동했고, 실제 `collect-status` 재조회는 exit 2·`ready=false`였다. `research_input=false`, `performance_eligible=false`, v3 데이터 적격은 미평가다.

## 검증과 안전

- 단일 audit 스크립트 `audit_v3_cache.py`는 Ruff check/format과 strict mypy 통과. `result.json`·`binding.json`에 script SHA `43923c0253c1999ab87af019dda118726d7a93cee1e0ccc2b9beab99124ea64c`, result SHA `d567253f74aaad0c738dca9c0e0ad1a06f1e144c537194bd31d5f0aa89d2175a`를 결속했다. 결과 불변식·marker 격리·원본 hash·최종 audit 크기 16.8 MB(<100 MiB 사전·사후 점검 기준, hard limit 아님)를 확인했다.
- 기존 생산 코드 hash와 통합 후 focused 247개 통과 근거는 [이전 개발 기록](2026-09-30-us-preferred-classification.md)에 있다. 이번 변경은 문서·audit 산출물뿐이므로 pytest를 반복하지 않았다. `.env` 값은 설정 loader에서만 읽었고 복사·출력하지 않았다. 실거래·PAPER·전략·NAV·OOS·push·결제·서비스 상태 변경은 없다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-v3-offline-cache-audit/` (`baseline.json`, `audit_v3_cache.py`, `result.json`, `binding.json`, 격리된 출력/marker). 비교 원본은 이전 자료 준비 audit의 `frozen-misses.json`, `live-attempts.json`, `missing-inputs.json`이다.
- 가상 실패는 실제 공급자 응답이나 자료 적격 증거가 아니다. 같은 Yahoo 요청 24건은 새 원본 근거 없이 재시도하지 않는다. 새 `ICUI` 요청과 사건별 역사 관측시각·상장/가격 결손은 별도 scope에서 비용·접근을 검토해야 한다. 기존 25 요청 제외·125 사건 관측시각 결손이 해결되었다고 해석하지 않는다.
