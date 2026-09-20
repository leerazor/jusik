# KIS stream contract strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: 읽기 전용 KIS research feed state와 protocol ID literal 계약

## 변경

- research feed item 상태를 `pending | connected | stale | rejected | unsupported`로
  좁혔습니다.
- protocol counter의 TR ID를 `H0STCNT0 | HDFSCNT0` typed tuple로 고정했습니다.
- 스트림은 계속 읽기 전용이며 실제 주문·broker execution은 변경하지 않았습니다.

## 검증

- `kis_stream.py` strict mypy — 통과
- Ruff, `git diff --check` — 통과
- KIS stream 테스트 — `17 passed`

## 제한

- 실시간 자료의 PIT/economic readiness나 PAPER/live 승격을 새로 주장하지 않습니다.
