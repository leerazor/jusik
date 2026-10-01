# 미국 요청 결손 22종목의 시도별 근거

- 상태: 오프라인 시도 출처 정리 완료, 자료 인수 미완료. 작업 `us-gap-provenance-20261001`, 기준 `bcde06d`. 원래 [요청 제외 25종목](/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-exclusion-pilot-readiness/missing-inputs.json)에서 MET-P-F·GPACW·TNMG를 이 추적 목록에서 제외해 **22종목**을 남겼다. 이 제외는 전체 자료 적격 판정이 아니다.
- [종목별 결과](/home/kwl/.local/share/jusik/portfolio-audit/20261001-us-gap-provenance/result.json)는 9/22 보존 receipt와 9/30 live 호출을 각각 기록한다. 두 시도 모두 404인 19종목: ALB-P-A, BHAC, CVII, DYNX, EBR-B, FFWM, FRBN, GNL-P-E, GS-P-D, HSPT, LCW, NXDT-P-A, PBI-P-B, PELIR, RAPT, RILYM, SP, STGC, XOMAO. AVNS는 **9/22 HTTP 200·timestamp 0개**, **9/30 HTTP 404**다. BERZ·FNGS는 두 시도 HTTP 200이며 9/30 진단은 identity mismatch다. 따라서 추적22의 9/22 상태는 404×19/200×3, 9/30 상태는 404×20/200×2다.
- 이 표는 각 저장 시도의 사실만 말한다. 404의 원인을 상장폐지로 확정하지 않으며, 기존 대안 공급자·symbol search 기록은 이 22종목의 warmup·평가기간 전체 유효 봉을 입증하지 못했다. 다른 공급자가 영원히 제공할 수 없다는 판단이나 유료 자료의 비용·소요시간 견적은 없다.
- 평가기간 2025-09-11..2026-09-11, warmup 시작 2025-08-13. 최신 v5 최종 prepared를 다시 만들지 않았으므로 선정·coverage·성과를 갱신했다고 주장하지 않는다. 재개에는 동일 증권·날짜·가격 기준·기업행동 관측시점에 맞는 독립 원천 근거가 필요하며 재선정은 이 기록의 범위 밖이다.
- 검증: [결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-us-gap-provenance/binding.json)에 원천 4개 SHA, 정확22 목록, 시도별 건수를 고정했다. 네트워크·수집기·금융 실험·코드/캐시/정책 변경 0회. 생산 코드 불변으로 테스트·린트·타입 검사는 재실행하지 않았다. 주문·결제·서비스·push 변경 없음.
- workflow 판단: 같은 응답을 다시 요청하지 않고 날짜가 다른 증거를 분리해 AVNS 상태 혼동을 줄였다.
- 근거: 저장된 25행·27호출에서 22행을 대사했고 새 외부 호출 0회다. 시간·비용 절감 비교치는 미측정이다.
- 다음 조정: 과거 receipt를 최신 상태로 덮어쓰지 않고 시도시각과 함께 인용한다.
