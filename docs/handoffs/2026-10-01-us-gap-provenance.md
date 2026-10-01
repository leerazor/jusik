# 미국 22종목 결손 시도 출처 인계

- [개발 기록](../development-records/2026-10-01-us-gap-provenance.md), [정확22종목·시도별 JSON](/home/kwl/.local/share/jusik/portfolio-audit/20261001-us-gap-provenance/result.json), [결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-us-gap-provenance/binding.json)이 진입점이다. 구현 커밋의 main 통합은 감독자 예정.
- 9/22 추적22: 404×19, AVNS 200이지만 timestamp 0개, BERZ/FNGS 200. 9/30 추적22: 404×20에 AVNS 포함, BERZ/FNGS 200 identity mismatch. 두 시도의 상태는 서로 대체하지 않는다. MET-P-F·GPACW·TNMG는 원래25의 이 추적 목록에서 제외했지만 최신 v5 최종 prepared는 재실행하지 않았다.
- 평가 2025-09-11..2026-09-11 및 warmup 2025-08-13에 같은 증권·날짜·가격 기준·기업행동 시점이 맞는 근거가 필요하다. 기존 대안 확인은 전체 유효 봉을 입증하지 못했고 다른 공급자의 영구 불가나 유료 비용은 미확인이다. 새 원천·명시 견적 없이 동일 실패 요청, 재선정, NAV·성과 계산을 반복하지 않는다.

- 구현 `7af5628`, main `652c59ab03350a1e96a2b1eddda7925a1059fa75`; 독립 검토와 원천·문서 결속 PASS, backend 불변. audit `integration.json`·`review.json`·`cleanup.json` 참조. 후속 SP 공식 원천의 조건부 검색 범위는 별도 작업이며 이번 결과에 포함하지 않는다.
