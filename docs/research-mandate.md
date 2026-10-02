# 현재 연구 운용 조건

## 현재 우선 연구 범위

사용자가 직접 등록한 한국·미국 종목만 새 연구의 시작 목록으로 사용한다. 등록 목록은 처음에 비어 있으며 기존 탐색 universe나 운영 universe를 승인된 목록으로 간주하지 않는다. 우선 목표는 같은 종목의 단순 보유와 매수·보유·매도·현금으로 이루어진 낮은 회전율 후보를 비용 차감 기준으로 비교하는 것이다. 등록만으로 시세 자료 적격성, 투자 후보, PAPER 또는 실거래를 승인하지 않는다. 새 연구 절차는 [승인 종목 연구 계획](approved-universe-plan.md)을 따른다.

기존 R0–R7 및 미국 PIT 연구는 과거 근거와 재현을 위한 참조다. 새 사용자 선택 종목 연구의 선행 차단 조건으로 사용하지 않는다. 전용 roadmap runner의 새 dispatch는 이 전환 기간에 비활성화하며 기존 실행 기록과 동결 조건은 유지한다.

현재 `docs/research-mandate.json` 전체 bytes SHA-256은 `ab6d712922b0a148361b3c8170c77cf44f7ef871b2a6878ac51d66447350f904`입니다.

자동 연구는 함께 추적하는 `research-mandate.json`의 실행 범위를 따릅니다. 현재 JSON 전체 bytes SHA-256은 manifest의 `docs/research-mandate.json` 항목과 일치하며, manifest에는 immutable legacy execution identity와 canonical `#governance-object` projection을 별도 항목으로 둡니다. 기존 policy consumer와 과거 replay는 legacy identity를 계속 사용하고, roadmap dispatch는 governance-object projection을 사용합니다. 과거 실험이 고정한 원본과 계약은 해당 실험의 근거로 보존하고 새 조건을 적용했다고 과거 결과를 다시 해석하지 않습니다. 승인된 설계는 [투자 개발 로드맵](investment-development-roadmap.md)의 canonical execution plan과 JSON governance에 동기화되어 있으며, roadmap runner는 전용 scope에서만 dispatch합니다. JSON의 versioned governance는 balanced objective, 비용 차감 primary metrics, diagnostic 분리, `MDD <= 20%` hard filter, 후보 최대 3개와 자동 선택·승격 금지, bounded validation 순서와 별도 live 승인을 고정합니다. 새 연구를 dispatch하기 전 runner는 JSON·Markdown·checksum·roadmap marker·git readiness를 fail-closed로 검증하고, 불일치·누락·미확인은 claim·attempt·launch 전에 차단합니다. 실제 주문·PAPER/live 자동 승격은 계속 금지합니다.

새 미국 연구는 `new_us_research_policy`의 `us-research-symbol-exclusions-v1`을 적용해 `LIME`·`MDA`를 checkpoint seed 전에 제외하고 적격 후보로 빈자리를 채웁니다. 새 수집은 `PRF PERPETUAL` 연속 상품명과 `Wt Exp` 뒤 8자리 날짜가 오는 워런트 명칭 분류와 Yahoo OHLCV 다섯 필드가 모두 null인 날짜의 가격 결손 보존을 포함한 `approx-us-r1-event-timing-v5` 정규화를 기록합니다. 같은 날짜의 사건은 보존하되 관측시각이 없으면 경제 검증은 계속 차단합니다. v2·v3·v4 준비 자료와 해시는 보존합니다. 이전 준비 자료와 strict·근사 전략 입력에서는 원본을 보존한 채 두 심볼의 실행 행만 제외하고, 줄어든 표본과 대체 보충 없음, 제외 사유를 결과에 표시합니다. 신규 pool·자료 계약 해시는 이전 pilot과 v5 final의 혼용을 막고, 기존 raw/cache/result/replay와 immutable legacy execution identity는 그대로 유지합니다. 이전 미국 pilot은 새 final의 정책 계약을 만족하지 않습니다. 이 정책 변경은 R1-05/PIT 완전성·경제 평가 완료를 뜻하지 않습니다.

- 초기 자본은1억원이며 중간 인출은 없습니다. 총 포트폴리오 평가액의 운용 중 최고점(초기 자본 포함) 대비 최대 낙폭 목표는20%입니다. 레버리지 상품 배분은20% 범위에서 연구합니다.
- 불필요한 현금 대기를 줄이고 투자 비중을 높이는 후보를 비교합니다. 현금 비중만 낮추기 위해 낙폭·집중·레버리지 위험을 무시하지 않습니다. 구체적인 투자 비중과 변동성 목표는 사용자 고정값이 아니라 사전등록된 연구 후보입니다.
- 잦은 거래를 원하지 않습니다. 거래 횟수·회전율·비용과 비용 차감 수익률을 함께 평가하고, 실시간 신호 탐지를 매번 주문하는 동작과 구분합니다.
- 신규 ETF의 짧은 이력이 주 연구를 막으면 해당 상품을 제외하고 자료가 충분한 종목으로 먼저 진행합니다. 승인된 확장 범위인 현금·광범위 지수·단기채 ETF 연구는 별도로 계속할 수 있으며, 선택적인 확장 자료 준비를 모든 핵심 실험의 선행 조건으로 만들지 않습니다.
- 과거 lookback은3년이고 투자기간은 정하지 않은 채 계속 운용하는 open-ended 방식입니다. 상장 전 자료를 생성하거나 짧은 이력을3년 실측 자료로 표시하지 않습니다.
- 현재 JSON 실행 범위에서는 우선순위와 암묵적인 가중치를 정하지 않고 실제 순수익·낙폭·거래 횟수·거래/FX 비용을 나란히 확인합니다. 새로 승인된 balanced objective와 비용 차감 `CAGR`·`MDD`·`Sharpe`·`Calmar` primary metrics, `Sortino`·`Profit Factor`·MDD 회복 기간·최대 연속 손실 등 diagnostic metrics, `MDD <= 20%` hard filter 및 후보 최대 3개 규칙은 canonical roadmap 설계이며, JSON/hash 동기화 전에는 기존 실행·재생에 소급 적용하지 않습니다.
- 실거래는 유보합니다. 기존 PAPER10% 계약은 그대로 보존하며 새 연구 후보를 자동으로 승격하지 않습니다.
- 시장 PIT 연구는 한국·미국 각각 원화 1억원의 독립 계좌로 당시 eligible 주식만 매 거래일 재발굴하고, 오늘 후보를 과거 자료로 소급하지 않습니다. 거래량 상위 20·5% 목표·다음 거래일 시가·보유 중 SMA20 2회 청산·원화 기준 20% 낙폭 latch 조건은 JSON의 `historical_discovery_policy`에 고정합니다.
- 무료 근사 자료는 날짜별 표본으로 개인 판단에 참고할 수 있지만 strict PIT 검증·완전한 생존자/상장폐지·배당 자료로 표시하지 않습니다. KRX 공식 일별 GET, Alpha Vantage 상장 상태, Yahoo 과거 일봉, FRED DEXKOUS를 CLI `collect`의 bounded network cache로 수집할 수 있으며 현재 후보를 과거에 소급하지 않습니다. 웹은 준비된 cache만 읽고, 키·자료가 없거나 일부 응답이 실패하면 명시적으로 확인 불가로 남깁니다.
