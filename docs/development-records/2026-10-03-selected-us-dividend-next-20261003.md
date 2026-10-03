# NVIDIA 기존 공식 배당 근거 재검토

- 상태: 원문 정정·부분 검토3건 반영 완료, 배당락일 결손으로 적격화 미완료.
- 기록 2026-10-03T14:05:59.919587+00:00; 작업 `selected-us-dividend-next-20261003`; 기준main276bf03.
- 기존SEC q2fy26pr/q3fy26pr/q4fy26pr 원문과 해시를 재사용했다. 과거후보/기록은 record date를ex-date와 병기했으나 원문에는 ex-dividend가 없다. 2026-09-20 개발 기록을 정정하고, 원본 candidate manifest/원문 bytes는 보존했다.
- 원문3건에서 주당USD0.01, 기준일2025-09-11/2025-12-04/2026-03-11, 예정지급일2025-10-02/2025-12-26/2026-04-01만 확인했다. 새review에서 ex_dividend_date를 생략했고, captured_at은 현재 cache재확인시각임을 locator에 명시했다.
- fresh SQLite onlinebackup의 exactlatest revision3건을 고정했다. trialDB import3/partial3, 독립review PASS 후 같은revision이최신인지 다시 확인하고 운영reviewDB에 partial3반영했다. source파일 경로만 영구audit로 이동했고 원문해시는 동일하다.
- 전체 eligible는 전후24/111로 그대로다. coverageSHA는 `1800dee72e91518fe771d60640229207045019c5529ec6594510bb4cd49205ba`. 원장·공식입력freeze·NAV·수익률에 연결하지 않았다.
- 보완조회: 공개 Nasdaq NVDA배당API 신규1회가curl92 HTTP2 INTERNAL_ERROR/HTTP000으로 실패했다. 응답사실추가0,재시도0. 같은URL 재조회하지 않는다.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-selected-nvda-partial/`; manifestSHA `e342a6d33d3f075faed3bbc2e1072564c10014418e0dfe41e8578c1879920f01`. 이전DB백업/정확한pins/원문/검토입력/독립결과/반영상태 보존.
- 사용자/운영문서: 이전 issuer기록 정정. application코드·정책·투자기준 변경없어 pytest미수행; 원문·DB결과 독립대조 수행. 등록목록·서비스·주문·PAPER/live·remote push 변경0.
- 재개조건: 사건별배당락일을 직접 명시하는 새로운 공식원천이 확보될 때 기존partial에 새검토를 추가한다. record date에서추정하지 않는다. GOOGL도 같은 원칙으로 기존미검증10건 보완 대상이다.
- workflow 판단: 도움 됨 — 저장요약을원문과재대조하여3건의 잘못된적격화를 막았다. 시간/비용절감 미측정; 이후source탐색은일반요약보다원문필드확인우선.
