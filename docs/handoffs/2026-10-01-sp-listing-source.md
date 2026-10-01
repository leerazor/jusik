# SP 상장 가설 조회 인계

- [개발 기록](../development-records/2026-10-01-sp-listing-source.md), [전체 검색 결과 재판정](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/result.json), [복구한 원래 도구 응답](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/full-search-response.txt) 및 [출처 결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/full-search-provenance.json)이 진입점이다. 초기 선택 발췌·판정·결속 bytes는 각각 `*-initial.json`으로 보존했다. 구현 커밋의 main 통합은 감독자 예정.
- 원래 검색의 5개 결과 전부에서 SP Plus 보통주·Nasdaq `SP` 연결은 proxy 발췌에만 보이고 상폐는 조건부였다. 보인 8-K의 [정확 URL](https://www.sec.gov/Archives/edgar/data/1059262/000119312524140235/d833024d8k.htm)은 기록만 했고 open/GET 0회다. 해당 발췌가 완료 사실을 보여주지 않았다는 뜻이며 8-K 본문 자체의 제출일·완료 여부를 추정하지 않는다. 복구 중 신규 검색도 0회다.
- 다른 정확 공식 원문이 완료 사건·증권 class/시장·효력 또는 거래 중단일을 함께 입증할 때 새 scope에서 재개한다. 이전 검색 반복·Yahoo 재요청·자동 재선정/PIT/성과 승격은 하지 않는다.
