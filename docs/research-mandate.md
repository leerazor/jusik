# 현재 연구 운용 조건

자동 연구는 함께 추적하는 `research-mandate.json`의 실행 범위를 따릅니다. 현재 JSON 전체 bytes SHA-256은 `9643a23000674c9461e3f102511b395817a01deb90b480c4c67738fd17ef54c0`이며, manifest에는 immutable legacy execution identity와 canonical `#governance-object` projection을 별도 항목으로 둡니다. 기존 policy consumer와 과거 replay는 legacy identity를 계속 사용하고, roadmap dispatch는 governance-object projection을 사용합니다. 과거 실험이 고정한 원본과 계약은 해당 실험의 근거로 보존하고 새 조건을 적용했다고 과거 결과를 다시 해석하지 않습니다. 새 설계는 [투자 개발 로드맵](investment-development-roadmap.md)의 canonical execution plan에서 별도로 승인되며, 이 문서만으로 dispatch가 기술적으로 차단되지는 않습니다. 현재 runner paused·service inactive·timer inactive/disabled 운영 게이트를 유지합니다. JSON의 versioned governance는 balanced objective, 비용 차감 primary metrics, diagnostic 분리, `MDD <= 20%` hard filter, 후보 최대 3개와 자동 선택·승격 금지, bounded validation 순서와 별도 live 승인을 고정합니다. 새 연구를 dispatch하기 전 운영자는 governance와 문서의 SHA-256을 검증해야 하며, dispatcher는 investment-roadmap scope에서만 이를 fail-closed로 적용합니다. 그 전에는 operator가 enable/resume하지 않습니다. 불일치·누락·미확인은 dispatch 차단 사유입니다.

- 초기 자본은1억원이며 중간 인출은 없습니다. 총 포트폴리오 평가액의 운용 중 최고점(초기 자본 포함) 대비 최대 낙폭 목표는20%입니다. 레버리지 상품 배분은20% 범위에서 연구합니다.
- 불필요한 현금 대기를 줄이고 투자 비중을 높이는 후보를 비교합니다. 현금 비중만 낮추기 위해 낙폭·집중·레버리지 위험을 무시하지 않습니다. 구체적인 투자 비중과 변동성 목표는 사용자 고정값이 아니라 사전등록된 연구 후보입니다.
- 잦은 거래를 원하지 않습니다. 거래 횟수·회전율·비용과 비용 차감 수익률을 함께 평가하고, 실시간 신호 탐지를 매번 주문하는 동작과 구분합니다.
- 신규 ETF의 짧은 이력이 주 연구를 막으면 해당 상품을 제외하고 자료가 충분한 종목으로 먼저 진행합니다. 승인된 확장 범위인 현금·광범위 지수·단기채 ETF 연구는 별도로 계속할 수 있으며, 선택적인 확장 자료 준비를 모든 핵심 실험의 선행 조건으로 만들지 않습니다.
- 과거 lookback은3년이고 투자기간은 정하지 않은 채 계속 운용하는 open-ended 방식입니다. 상장 전 자료를 생성하거나 짧은 이력을3년 실측 자료로 표시하지 않습니다.
- 현재 JSON 실행 범위에서는 우선순위와 암묵적인 가중치를 정하지 않고 실제 순수익·낙폭·거래 횟수·거래/FX 비용을 나란히 확인합니다. 새로 승인된 balanced objective와 비용 차감 `CAGR`·`MDD`·`Sharpe`·`Calmar` primary metrics, `MDD <= 20%` hard filter 및 후보 최대 3개 규칙은 canonical roadmap 설계이며, JSON/hash 동기화 전에는 기존 실행·재생에 소급 적용하지 않습니다.
- 실거래는 유보합니다. 기존 PAPER10% 계약은 그대로 보존하며 새 연구 후보를 자동으로 승격하지 않습니다.
- 시장 PIT 연구는 한국·미국 각각 원화 1억원의 독립 계좌로 당시 eligible 주식만 매 거래일 재발굴하고, 오늘 후보를 과거 자료로 소급하지 않습니다. 거래량 상위 20·5% 목표·다음 거래일 시가·보유 중 SMA20 2회 청산·원화 기준 20% 낙폭 latch 조건은 JSON의 `historical_discovery_policy`에 고정합니다.
- 무료 근사 자료는 날짜별 표본으로 개인 판단에 참고할 수 있지만 strict PIT 검증·완전한 생존자/상장폐지·배당 자료로 표시하지 않습니다. KRX 공식 일별 GET, Alpha Vantage 상장 상태, Yahoo 과거 일봉, FRED DEXKOUS를 CLI `collect`의 bounded network cache로 수집할 수 있으며 현재 후보를 과거에 소급하지 않습니다. 웹은 준비된 cache만 읽고, 키·자료가 없거나 일부 응답이 실패하면 명시적으로 확인 불가로 남깁니다.
