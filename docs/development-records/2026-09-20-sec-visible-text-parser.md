# SEC HTML visible-text candidate parser

- 상태: 완료·operator review gate 유지
- 기록 시각: 2026-09-20T08:00:00Z
- 작업 slug: `sec-visible-text-parser-20260920`
- 기준/통합: `75fea53` / 다음 통합 커밋
- 범위: SEC filing candidate parser가 HTML 태그·script/style/head 메타데이터를 후보 문맥으로 오인하지 않도록 visible-text parser를 추가했습니다. action facts, operator verification, ledger 적용은 변경하지 않았습니다.

## 변경과 결정

- 표준 library `HTMLParser(convert_charrefs=True)`로 bounded UTF-8 filing body의 보이는 텍스트만 추출합니다.
- `script`, `style`, `head`, `title` 내용은 제외합니다.
- 기존 candidate kind 탐지와 SHA/source identity는 유지하고, parser는 여전히 dividend/split의 금액·날짜·권리수량을 추론하지 않습니다.
- malformed HTML은 parser가 허용하는 범위에서 읽되, invalid UTF-8은 기존처럼 fail-closed합니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_research_sec_evidence.py -q` — `15 passed`
- SEC/action/public catalog bundle — `49 passed`
- `ruff check` — 통과
- `mypy --strict backend/jusik/research_sec_evidence.py` — 통과
- `git diff --check` — 통과
- 기존 event-near 원문 52건 read-only 재파싱 — 기존 candidate kind과 변경 0건; priority catalog 재생성은 필요하지 않음을 확인했습니다.

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·network collection·remote push·Windows 종료 없음.
- SEC review form은 여전히 operator facts 입력 전 `ready=false`, 자동 ledger `false`입니다.
- runner paused, service inactive, timer disabled 상태를 유지합니다.

## 재개 조건

- visible snippets는 검토 보조일 뿐입니다. operator가 원문에서 event type, amount/ratio, ex/effective/payment/record 경계와 share basis를 확인한 뒤에만 form validator를 재실행합니다.
