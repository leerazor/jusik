# Yahoo 가격 기준 공식 도움말 확인

- 상태: 본문 접근 차단. 작업 `yahoo-price-basis-source-20260930`, 작업 기준 `c21cc55`. 생산 코드·원본 캐시·정책 변경 없음.
- 고정 검색어를 1회 사용해 공식 Yahoo Help의 [Adjusted close 문서](https://in.help.yahoo.com/kb/adjusted-close-sln28256.html)를 선택하고 [URL을 먼저 고정](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/selected-url.json)했다. [검색 발췌](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/search-snapshot.md)는 선택 항목 일부이며 공식 문서 본문 증거가 아니다.
- 해당 URL의 본문 open 1회는 도구에서 429로 실패했다. [open 반환](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/open-snapshot.md)에는 렌더링 본문이 없으며 원본 HTML byte hash도 아니다. 재시도·대체 URL 검색은 하지 않았다.
- [판정](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/result.json): 공식 문서의 Close/Adj Close 조정 규칙을 본문으로 검증하지 못했고, 해당 일반 규칙과 Yahoo chart JSON `quote`/`adjclose` 필드의 연결도 확인하지 못했다. [이전 TNMG 대사](2026-09-30-berz-security-source.md)의 `price_basis=unknown` 및 회계 raw-basis 차단 유지. 검색 발췌나 가격 변동으로 TNMG 원문을 승격하지 않는다.
- 검증: 보호 파일 6개 SHA 전후 일치; 검색 1회·본문 open 1회·추가 검색/재시도/가격 요청/collector/회계·NAV/금융 실험 0회. 증거 및 문서 SHA와 링크는 [verification](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/verification.json)에 결속했다. 생산 코드 불변으로 pytest·Ruff·mypy·build를 실행하지 않았다. 주문·추가 결제·서비스·push 변경 없음.
- 재개: 새로 제한한 범위에서 공식 본문에 실제 접근할 수 있고, chart JSON 필드의 역사적 가격 기준에 적용되는 명시 근거가 있을 때만 판단한다. 동일한 429 요청을 즉시 반복하지 않는다.
- workflow 판단: 고정 검색·선택 URL·1회 open 상한으로 접근 차단을 명확히 했다.
- 근거: 검색 1회와 실패한 본문 open 1회; 시간·호출 절감 비교치는 미측정이다.
- 다음 조정: 본문 확보 없이 일반 도움말 검색 결과를 데이터 계약으로 사용하지 않는다.
