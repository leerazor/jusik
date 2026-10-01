# SP 상장 이력 SEC 원천 조회 게이트

- 상태: 공식 원문 진입 전 차단, 상장폐지 가설 미확정. 작업 `sp-listing-source-20261001`, 기준 `6e6a0a5`. 생산 코드·정책·캐시·기존 원본 불변.
- 처음 보존한 [선택 발췌](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/search-snapshot-initial.json)는 전체 응답이 아니었다. 독립 검토 후 [원래 검색 도구의 전체 렌더링 응답](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/full-search-response.txt) 5개 결과를 세션 로그에서 복구해 [호출·응답 결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/full-search-provenance.json)과 SHA로 보존했다. 검색 결과는 SEC 원문 본문이나 HTML bytes가 아니다. [확정 proxy URL](https://www.sec.gov/Archives/edgar/data/1059262/000119312524005660/d152391ddefm14a.htm)의 결과는 SP Plus 보통주와 Nasdaq `SP`를 연결하지만 합병·상폐는 조건부 또는 예정 표현이다.
- 결과에 보인 미사용 [8-K URL](https://www.sec.gov/Archives/edgar/data/1059262/000119312524140235/d833024d8k.htm)의 제목은 `8-K`였으며 정확한 제출일은 해당 발췌에 없었다. 보이는 도입부는 SP Plus·Metropolis 합병계약을 설명하지만 거래 완료·상장폐지·거래 중단 날짜와 `SP` 기호를 함께 확인해 주지 않는다. URL을 열지 않았으므로 본문에 그런 근거가 없다는 주장은 하지 않는다.
- [전체 결과 재판정](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/result.json): proxy 2개는 조건형, 계약 전시 1개는 합병 합의, 8-K의 보이는 발췌는 계약 도입부, 투표 표 1개는 채택안이다. 다섯 결과 어디에도 완료 사건과 `SP` 증권 identity가 함께 보이지 않아 사전 게이트 미충족. 원문 open/GET 0회, 복구 과정의 검색·Yahoo 요청·재시도 0회. 합병 완료 여부·효력/거래 중단일, Alpha/Yahoo 증권 identity 연결, 과거 선정·PIT·관측시각·coverage·성과 적격은 모두 미확인이다. 404만으로 상장폐지 원인을 추론하지 않는다.
- 검증: [결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/binding.json)에 scope·계획·초기 증거·전체 검색 응답·판정 SHA를 기록했고 보호 파일 4개 SHA 일치와 문서 링크를 확인했다. 원문이 없으므로 HTML byte hash·HTTP 상태를 만들지 않았다. 생산 코드 불변으로 pytest·Ruff·mypy·build는 재실행하지 않았다. 주문·금융 실험·추가 결제·서비스·push 변경 없음.
- 재개: 완료된 거래와 `SP` 증권 class/시장, 효력 또는 거래 중단일을 직접 연결할 공식 원문의 **정확 URL**과 새 한정 범위가 생길 때만 확인한다. 동일 검색과 조건부 proxy를 반복하지 않는다.
- workflow 판단: 검색 전 게이트로 불충분한 결과에서 원문 요청을 중지했다.
- 근거: 실제 검색 1회·원문 0회; 시간·비용 절감 비교치는 미측정이다.
- 다음 조정: 완료 사건과 증권 identity를 함께 보여 주는 새 URL 근거가 없으면 가설을 미해결로 유지한다.
