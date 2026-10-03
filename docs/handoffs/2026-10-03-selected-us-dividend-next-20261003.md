# 등록 미국 배당 보완 인계

- 갱신 2026-10-03T14:05:59.919587+00:00; [기록](../development-records/2026-10-03-selected-us-dividend-next-20261003.md).
- NVDA3건 기존SEC원문은 금액/기준일/지급일만명시. 과거record/ex-date병기정정, 독립PASS후partial3 실제reviewDB반영. eligible24/111유지/원장반영0.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-selected-nvda-partial/`의pins/상태/독립검토부터확인. 같은원문재조회불필요. NasdaqNVDA배당API1회curl92/HTTP000실패,동일조회반복금지.
- 다음배당재개조건은 사건별ex-date를직접명시한새공식원천. 그전에는partial을matched/eligible로바꾸지않는다. GOOGL10건은미검증.
- 독립된원주가후속: ARM/GEV 공식거래개시본문2건을추가확보해 선행51/188세션대조,별도독립검토완료. 등록16/rev1과현재연구조건유지.

- 2026-10-03T21:00Z heartbeat 보완: GOOGL의 사건별 ex-date 공식 대체 근거를 abc.xyz/Nasdaq 공개 검색으로 한정 탐색했으나 적격 원문은 확보하지 못했다. 검색 snippet/다른종목 결과/일반 배당정책은 근거로 채택하지 않았다. 검색어 Alphabet dividend ex dividend date(abc.xyz), GOOGL cash dividend June 2024 ex(nasdaq.com) 및 abc.xyz 연도별 ex-dividend 검색은 새로운 단서 없이 반복하지 않는다. DB·수익률·준비 상태 변경0, 별도audit 미생성. 새 사건별 공식 배당락일 문서가 재개조건이다.
