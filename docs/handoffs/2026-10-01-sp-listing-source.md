# SP 상장 가설 조회 인계

- [개발 기록](../development-records/2026-10-01-sp-listing-source.md), [검색 게이트 판정](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/result.json), [선택 발췌](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/search-snapshot.json)이 진입점이다. 구현 커밋의 main 통합은 감독자 예정.
- 검색 1회에서 SP Plus 보통주·Nasdaq `SP` 연결은 보였으나 상장폐지는 조건부 설명이었다. 보인 8-K의 [정확 URL](https://www.sec.gov/Archives/edgar/data/1059262/000119312524140235/d833024d8k.htm)은 기록만 했고 open/GET 0회다. 제출일·본문·완료 여부를 추정하지 않는다.
- 다른 정확 공식 원문이 완료 사건·증권 class/시장·효력 또는 거래 중단일을 함께 입증할 때 새 scope에서 재개한다. 이전 검색 반복·Yahoo 재요청·자동 재선정/PIT/성과 승격은 하지 않는다.
