# 미국 v3 캐시 오프라인 감사 인계

- 작업 `us-v3-offline-cache-audit-20260930`; 기준 `f37d4a3`, 구현 commit 및 main 병합 SHA는 감독자 확정 예정. [개발 기록](../development-records/2026-09-30-us-v3-offline-cache-audit.md)에 방법·제한을 남겼다.
- cache 복사본 139 raw/manifest hash 확인 후 deny-all collector 1회: 가상 Yahoo miss 25개, 실제 외부 요청 0. 기존 v2 miss27 중 이전 실패24 유지, `MET-P-F` 제거, 새 `ICUI` 1개. 이전 검증된 `CFG`·`NOEM`은 재사용했다. diagnostics 누적 종목 101→101의 제거/추가도 같다. 일별 남은 universe 행 수 75~76은 전체 sample100 인수가 아니다.
- `offline-UNTRUSTED-v3.json`은 mock 실패 출력으로 연구 입력 금지. 새 v3 marker는 audit `quarantine/`에 원자 이동했고 `collect-status.ready=false`를 확인했다. 생산 코드·원본 cache·이전 v2 prepared/marker·mandate 불변. audit `result.json`과 `binding.json`에 정확 key 비교·script/result SHA·보호 hash를 보존했다.
- 재개: 같은 Yahoo 24건은 새 근거 없이 재요청하지 않는다. 새 `ICUI` 및 남은 역사 시세·사건별 최초 관측시각의 자료 출처와 비용을 별도 scope로 검토한다. 이전 25 요청 제외/125 사건 관측시각 결손은 이 가상 probe로 해소되지 않았다. 전략·NAV·성과는 자료 gate 이후에만 검토한다.
- Ruff/strict mypy는 단일 audit 스크립트에 통과; 생산 코드와 의존성은 불변이므로 기존 focused pytest 재실행 생략. 독립 review와 main 통합 후 문서·hash 검증은 감독자 예정. 실거래·PAPER·시장 조회·push 없음.
