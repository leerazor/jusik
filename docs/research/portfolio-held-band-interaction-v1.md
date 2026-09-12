# 보유 밴드 상호작용 v1

이 문서는 corrected-entry 규칙에서 보유 종목 재배분 밴드 `0.02`와 `0.04`를 비교하는 후속 연구의 실행 기록이다. 미보유 종목의 양수 목표 진입 보정은 두 arm에 공통으로 적용하고, 목표 0 청산·cap 초과·위험 청산은 밴드를 우회한다.

구현과 합성 검증 후 고정 자료의 역사 실행을 승인된 전용 audit 디렉터리에서 정확히 32회 수행했다. 결과는 기술통계로 기록하며 새 승자 판정이나 인과 주장을 하지 않는다.

검증 범위에는 copied engine의 실제 `simulate` 경로에서 보유 상태를 만든 단일 held-position guard와 정확한 `0.02`/`0.04` 경계의 below/equal/above 체결 수량, 미보유·목표 0·cap·risk 경로, Decimal 회계 attribution, 0·음수·누락·중복·비유한 설정 거부가 포함된다. 휴일·UTC·결정 cutoff와 다음 유효 개장 체결은 기존 엔진의 이벤트 순서를 보존하는 방식으로 실행에서 확인한다. 부분 체결·취소·거절 receipt는 현재 연구 모델이 표현하지 않으므로 합성 성공 체결로 만들지 않고 unsupported로 기록한다. 조기 폐장 데이터는 고정 엔진의 시장 시간 모델 범위 밖이므로 지원하지 않는다.

실행 조건은 7개 독립 fold와 continuous를 합치지 않고, 비용 배수 1·2 및 밴드 2%p·4%p를 각 조합으로 한정한다. 대조군은 corrected-entry `*-variant_c{1,2}.json` 16개와 전체 JSON을 exact equality로 비교하고, Decimal reconciliation에만 `1e-6 KRW` 이하 허용오차를 쓴다. 자동 주문, PAPER 설정, GPU, DB, 제품 엔진 변경은 연구 범위가 아니다.

## 실행 결과

정확히 32회(7개 독립 fold와 continuous × 두 비용 × 두 arm)를 실행했다. corrected-entry 2%p control 16개는 저장된 `*-variant_c{1,2}.json` 전체 JSON과 exact equality였고 비교 허용오차는 없었다. Decimal 금액 회계만 `1e-6 KRW`를 허용했으며, 독립 검증의 최대 금액 residual은 `4e-31 KRW`였다. 실행은 `drawdown_limit=0.10`, `symbol_cap=0.20`을 포함한 frozen config를 유지했고 variant engine SHA는 `7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442`였다. 총 거래는 2,347건이다.

| period | arm | cost | return% | MDD% | trades | turnover% | tx KRW | FX KRW | unheld | skip | complete |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| fold_1 | control | 1 | 0.2334 | 4.7287 | 35 | 75.4836 | 150951.8818 | 54439.2122 | 20 | 7 | True |
| fold_1 | control | 2 | 0.0812 | 4.7687 | 35 | 74.5543 | 298156.2811 | 108041.4240 | 20 | 7 | True |
| fold_1 | variant | 1 | 0.2334 | 4.7287 | 35 | 75.4836 | 150951.8818 | 54439.2122 | 20 | 7 | True |
| fold_1 | variant | 2 | 0.0812 | 4.7687 | 35 | 74.5543 | 298156.2811 | 108041.4240 | 20 | 7 | True |
| fold_2 | control | 1 | 2.5103 | 2.1105 | 45 | 47.5758 | 95134.1721 | 34279.5713 | 18 | 25 | True |
| fold_2 | control | 2 | 2.1892 | 1.9753 | 46 | 46.7526 | 186941.9262 | 67107.8020 | 18 | 25 | True |
| fold_2 | variant | 1 | 2.5103 | 2.1105 | 45 | 47.5758 | 95134.1721 | 34279.5713 | 18 | 25 | True |
| fold_2 | variant | 2 | 2.1892 | 1.9753 | 46 | 46.7526 | 186941.9262 | 67107.8020 | 18 | 25 | True |
| fold_3 | control | 1 | -2.0879 | 5.2437 | 25 | 92.6972 | 185378.1070 | 33657.2951 | 19 | 0 | True |
| fold_3 | control | 2 | -2.3172 | 5.3237 | 25 | 92.4140 | 369591.1772 | 67170.2731 | 19 | 0 | True |
| fold_3 | variant | 1 | -2.0879 | 5.2437 | 25 | 92.6972 | 185378.1070 | 33657.2951 | 19 | 0 | True |
| fold_3 | variant | 2 | -2.3172 | 5.3237 | 25 | 92.4140 | 369591.1772 | 67170.2731 | 19 | 0 | True |
| fold_4 | control | 1 | 4.9912 | 1.7182 | 48 | 50.0969 | 100170.6523 | 37429.0815 | 18 | 25 | True |
| fold_4 | control | 2 | 4.7789 | 1.7242 | 48 | 49.5379 | 198060.3351 | 73881.0209 | 18 | 25 | True |
| fold_4 | variant | 1 | 4.5745 | 1.5195 | 47 | 45.1556 | 90294.0524 | 32481.7715 | 18 | 28 | True |
| fold_4 | variant | 2 | 4.4251 | 1.5246 | 47 | 44.8745 | 179429.8743 | 64531.4333 | 18 | 28 | True |
| fold_5 | control | 1 | 6.6800 | 2.3431 | 55 | 111.4727 | 222933.3208 | 78510.0252 | 24 | 15 | True |
| fold_5 | control | 2 | 6.2868 | 2.4560 | 56 | 111.5470 | 446139.3880 | 157223.8410 | 24 | 15 | True |
| fold_5 | variant | 1 | 6.7417 | 2.3205 | 55 | 95.5614 | 191110.1884 | 73131.3653 | 24 | 20 | True |
| fold_5 | variant | 2 | 6.3476 | 2.2854 | 55 | 95.4318 | 381677.5997 | 146007.3168 | 24 | 20 | True |
| fold_6 | control | 1 | 6.9757 | 4.2422 | 36 | 82.9442 | 165874.4630 | 59660.1871 | 18 | 10 | True |
| fold_6 | control | 2 | 6.7307 | 4.2868 | 37 | 82.9239 | 331639.7390 | 119367.4114 | 18 | 10 | True |
| fold_6 | variant | 1 | 6.9757 | 4.2422 | 36 | 82.9442 | 165874.4630 | 59660.1871 | 18 | 10 | True |
| fold_6 | variant | 2 | 6.7307 | 4.2868 | 37 | 82.9239 | 331639.7390 | 119367.4114 | 18 | 10 | True |
| fold_7 | control | 1 | -0.0162 | 4.5297 | 33 | 68.6840 | 137348.4492 | 53255.0834 | 15 | 7 | True |
| fold_7 | control | 2 | -0.2185 | 4.6339 | 33 | 68.4441 | 273698.2594 | 106162.0750 | 15 | 7 | True |
| fold_7 | variant | 1 | 0.5502 | 4.2436 | 33 | 64.0348 | 128050.3194 | 48557.2820 | 15 | 8 | True |
| fold_7 | variant | 2 | 0.3626 | 4.3087 | 33 | 63.4872 | 253872.7029 | 96149.1984 | 15 | 8 | True |
| continuous | control | 1 | 27.8639 | 7.2249 | 308 | 569.5922 | 1139200.9819 | 404656.8003 | 102 | 143 | True |
| continuous | control | 2 | 26.2100 | 7.2911 | 313 | 561.1744 | 2244770.0127 | 794764.3899 | 101 | 143 | True |
| continuous | variant | 1 | 28.9165 | 6.2378 | 305 | 539.7579 | 1079533.2835 | 386221.5987 | 102 | 157 | True |
| continuous | variant | 2 | 27.0271 | 6.2325 | 310 | 527.3905 | 2109636.6668 | 751239.7981 | 101 | 157 | True |

각 period/cost pair의 variant−control 차이는 다음과 같다. fold를 합성하거나 continuous와 합산하지 않았다.

| period | cost | return Δ pp | MDD Δ pp | trades Δ |
|---|---:|---:|---:|---:|
| fold_1 | 1/2 | 0 / 0 | 0 / 0 | 0 / 0 |
| fold_2 | 1/2 | 0 / 0 | 0 / 0 | 0 / 0 |
| fold_3 | 1/2 | 0 / 0 | 0 / 0 | 0 / 0 |
| fold_4 | 1/2 | -0.416655 / -0.353816 | -0.198757 / -0.199531 | -1 / -1 |
| fold_5 | 1/2 | +0.061654 / +0.060810 | -0.022575 / -0.170615 | 0 / -1 |
| fold_6 | 1/2 | 0 / 0 | 0 / 0 | 0 / 0 |
| fold_7 | 1/2 | +0.566346 / +0.581156 | -0.286080 / -0.325215 | 0 / 0 |
| continuous | 1/2 | +1.052528 / +0.817125 | -0.987155 / -1.058593 | -3 / -3 |

fold 단순 수익률 차이의 중앙값은 비용 1배와 2배 모두 `0 pp`이다. 비용 1배 worst fold MDD는 control/variant 각각 `5.243656%`/`5.243656%`, 비용 2배는 `5.323653%`/`5.323653%`다. 각 비용에서 양수 return 차이는 2개 fold, 음수 차이는 1개 fold, 0 차이는 4개 fold였다. 양수 return 차이는 fold 5·7, 음수 return 차이는 fold 4, 동일한 차이는 fold 1·2·3·6에서 나타났다. 이는 기술통계이며 승자 기준이나 인과 효과가 아니다. 수익률·MDD·비용·turnover 중 일부가 개선되어도 정책 승격, retuning, PAPER 또는 실거래 설정으로 이어지지 않는다.

## 검증과 보존

사전 실행 검증은 baseline 관련 61개와 새 범위 10개 테스트를 포함해 71개가 통과했고, target Ruff와 strict mypy도 통과했다. 실제 실행은 exact control 16개, variant 16개로 제한했다. 독립 verifier는 2,347개 거래의 raw price/FX/cash/next-open 순서와 회계를 재구성해 통과했고, 저장 corrected artifact 일치 검증은 control 16개와 실행 결과 중 동일한 8개를 확인했다. 실제 시장 조기 폐장은 고정 엔진이 표현하지 않아 unsupported이고, partial/cancelled/rejected receipt도 연구 모델에서 성공 체결로 표현하지 않았다. feature cutoff는 baseline의 known-close, `_as_of_external`, volatility causal 테스트로 확인했고, next-open 순서는 저장 결과에 대한 독립 raw-open 검증에서 strict `decision_at < execution_at`으로 확인했다.

주요 audit 산출물은 [`experiment/results.json`](../../../../.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74/experiment/results.json), [`experiment/preregistration.json`](../../../../.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74/experiment/preregistration.json), [`experiment/hash-manifest.json`](../../../../.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74/experiment/hash-manifest.json)과 독립 검증 JSON이다. SHA-256은 각각 `6c20c79552964182d52e5a9ce8571747ddf97a21a9c7b5c46b2dc827e167479b`, `fa5065df2ae70d024656209b0a33b755071c1441ecfa3406db99973fda49277e`, `bba3822f08a648462c8a2634c9402b545c833ad854bcb924fac96adb75d366a2`다. 독립 review 결과 JSON SHA-256은 `ab15ff8980dce5f34c968064068023b9364d13aad9460a416255517f82bdab0d`다.

남은 한계는 후향 재사용 자료, point-in-time 정확성 미인증, 배당·분배금과 생존·상장 편향, 원천 자료의 시각·완전성, 조기 폐장 및 broker receipt 표현 부재다. 고정 시장시간은 New York local 16:00(겨울 UTC 21:00)으로 처리되므로 실제 조기 폐장은 지원하지 않는다. 이번 결과는 정책 승격이나 자동 주문 적합성을 의미하지 않는다.

runner 사전 검증의 original-versus-variant 선택 오류, tuple JSON key, eager hash fallback, precision 28 회계 false failure는 historical run 전에 수정했다. 실행 후에는 저장된 32개 결과만 사용해 독립 verifier의 next-open 비교를 engine의 strict `decision_at < execution_at` 의미로 조정하고 local-price exact 검증을 보강했으며, historical 재실행은 하지 않았다. 이 과정의 durable 기록은 `preflight-intercepted-result.json`, `review-second-probes.json`, `preflight-accounting-failure.json`, `independent-verification.json`이다. historical execution failure는 0건이다. review 결과 SHA-256은 `ab15ff8980dce5f34c968064068023b9364d13aad9460a416255517f82bdab0d`로 보존했다.

## 단일 successor scope

`portfolio-session-calendar-stress-v1`을 다음 successor로 기록한다. 근거는 [`successor-scope.json`](../../../../.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74/successor-scope.json)이며 SHA-256은 `1cef7a651ae9f1f0c4812ff778b4d38691a7194b316e545cb40495de7a9799d1`이다. 범위는 정확히 새 파일 3개로 한정한다: `backend/jusik/research_portfolio_session_calendar_stress.py`, `backend/tests/test_research_portfolio_session_calendar_stress.py`, `docs/research/portfolio-session-calendar-stress-v1.md`. `backend/jusik/data/market_sessions_2023_2026.json`을 기존 loader로 읽고 SHA-256 `ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8`을 요구한다. product engine, DB, PAPER, 주문, remote fetch, runner, GPU와 historical rerun은 범위에서 제외한다.

synthetic-only 검증은 NYSE 2026-07-03 holiday, 2026-11-27/12-24 13:00 New York local(18:00 UTC) early close, winter 16:00 local(21:00 UTC), DST, KRX offset와 unknown session 거부, completed-session cutoff와 next-open 실행, Decimal cash/FX/split/rounding reconciliation을 포함한다. calendar/hash/cutoff/next-open/accounting 검증이 하나라도 실패하면 중단한다. 이 successor는 point-in-time 정확성이나 조기 폐장에 대한 현재 실험의 결론을 소급해서 보완하지 않으며, 별도 승인 없이는 historical execution을 수행하지 않는다.

## 통합 검증 기록

최종 통합 커밋은 `7486b2c9ac51edff0d36a68dbcb48293a47d32ab`이다. 통합 후 pytest 71개, strict mypy 84개 source file, Ruff check와 format, `git diff --check`를 통과했다. frontend 변경은 없어 frontend build는 해당 없음이다. 실행 로그는 durable audit의 `integration-pytest.log`, `integration-mypy.log`, `integration-ruff.log`, `integration-format.log`에 보존했다.
