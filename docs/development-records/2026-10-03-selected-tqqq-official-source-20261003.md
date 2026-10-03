# TQQQ 공식 분배금과 공급자 금액 충돌 확인

- 상태: 원천 대조·독립 검토 보완 후 불일치13건 반영 완료. 실제 회계 입력 적격화는 미완료.
- 기록: 2026-10-03T14:30:13.283558+00:00; 작업 `selected-tqqq-official-source-20261003`; 기준 main613fc1d.
- [공식 상품 페이지](https://www.proshares.com/our-etfs/leveraged-and-inverse/tqqq)에 직접 연결된 공개 distributionsummary API의2023~2026년 원문을 각1회 보존했다. 관측 사건13건의 ExDate/RecordDate/PayableDate 및 Dividend/CashDividendPerShare를 exact Decimal로 대조했다. 예정 분배일 일반표로 사건을 추정하지 않았다.
- 13건 모두 공급자 금액과 다르다. 예:2026-09-23 공식API0.156012 대 공급자0.156. 과거 주당금액에2025분할이 반영된 기준은 미확인이다. 반올림 양상과 맞는다는 산술은 공급자의 처리방식 증명이 아니다.
- 독립 검토 P2: USD가 공식원문에 직접 명시되지 않아 원문 확인 사실로 넣을 수 없었다. 수정manifest에서13건 모두 currency와 comparable_share_basis를 생략했다. 새 사본 import13 모두mismatched, currency전부missing을 확인한 뒤 조건부 검토 승인 범위 안에서 현재reviewDB에 반영했다.
- 정확한 최신revision/content를 실제반영 직전에 재확인했다. 원래 공급자 금액은 변경0, 원장/NAV/성과 연결0. eligible24/111 유지, coverageSHA `88b7b28028d713c5a77ed2ae0ead36b62b337efd79b883c858778de4aaded1d1`.
- 2025-11-20 분할2:1은 이미matched 검토가 있었다. 공지1회 재조회는 중복이었다고 기록하고 추가review/import하지 않았다. 다음에는 문서 검색뿐 아니라 현재사건 검토/원천 목록을 조회 전에 먼저 확인한다. 이번원문 GET6회 중 유효한 새상품/API근거5회, 중복분할1회.
- 검증: 원문/13pins/정확한금액·날짜 독립 대조, 사본 수정검증, 실제 import13. readiness API는 여전히 comparison_status=not_performed, 등록16/rev1. reviewed건수는적격건수와다르다. 코드 변경이 없어 앱테스트는 재실행하지 않았다.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-selected-tqqq-source/`; manifestSHA `943bb11c90a2226196d82a3d4a24226342ece9ab8721449495145ff884009e50`. 최초draft/교정manifest/원문/DB백업/검토/실제상태 보존.
- 재개 조건: 지급통화와 당시 주당 기준을 직접 뒷받침하는 추가근거 및 공급자 정밀도 충돌을 보존하는 인수계약이 필요하다. 허용오차를 넓히거나 공식현재API값을과거원주당금액으로간주하지 않는다. 같은원문재조회불필요.
- 주문/PAPER/live/서비스/권한정책/등록목록/원격push 변경0.
- workflow 판단: 도움 됨 —13건의 미확인 상태를 구체적인금액충돌로 좁히고 통화가정유입을차단했다. 부담: 기존분할근거1회중복조회; 다음조정은DB검토확인우선. 시간절감미측정.
