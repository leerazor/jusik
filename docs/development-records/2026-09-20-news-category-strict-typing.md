# News category strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: RSS/news parser의 category literal 계약

## 변경

- news category를 `NewsCategory` literal alias로 정의하고 RSS parser와 source parser
  catalog에 공유했습니다.
- 허용되지 않은 category가 `NewsItem` 모델로 전달되지 않도록 정적·runtime 계약을
  강화했습니다.
- 뉴스 원문 수집, assessment 문구, 투자 비중·주문 동작은 변경하지 않았습니다.

## 검증

- `news.py` strict mypy — 통과
- Ruff, `git diff --check` — 통과
- market news 테스트 — `9 passed`

## 제한

- 뉴스는 참고 자료이며 전략 성과·PAPER/live 승인·경제 acceptance 근거로 사용하지 않습니다.
