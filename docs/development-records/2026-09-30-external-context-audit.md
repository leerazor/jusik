# 외부자료 상태 전달 후보 감사

- 상태: 감사 완료, 구현 NO_GO; main 통합 대기
- 기록 시각: 2026-09-30T05:11:09Z
- 작업 slug: `external-context-audit-20260930`
- 기준/통합: `1c98251fd7d529ce9c4bf8fd5818c93ab9b16dde` / 없음 (감독자 확정 예정)
- 범위: 현재 소비 경로의 시점·stale 의미를 검토하고 판단만 보존. 코드·입력·운영 정책 변경 없음.

## 변경과 결정

- [forward 입력](../../backend/jusik/research_forward.py#L755)은 과거 cutoff의 `snapshot_asof`를 쓰고 `external_status=[]`를 둔다. 이를 [store의 현재 집계](../../backend/jusik/research_external_store.py#L315)로 채우면 이후 수집 결과가 과거 실행에 소급돼 미래 정보가 섞인다.
- [portfolio signal](../../backend/jusik/research_portfolio_engine.py#L313)과 [forward FX](../../backend/jusik/research_forward.py#L1354)는 관측값을 소비하며 `external_status`를 사용하지 않는다. [실패 격리·stale 처리](../../backend/jusik/research_external_store.py#L194)는 유지되고 [화면](../../frontend/app/research/portfolio/page.tsx#L113)은 현재 자료 상태와 실행 상태를 구분한다. 재현 가능한 소비자 결함이 없어 기능 추가를 기각했다.
- manifest-integrity guard는 과거 review FAIL에 실행 가능한 finding이 없고, receipt-id discovery는 기존 review 조건이 미해결이며, listing-identity는 자료 대기다. 같은 입력으로 재시도하지 않았다.

## 문서·계약 영향

- 사용자 문서·API·설정·데이터 계약: 변경 없음. 이 기록은 NO_GO 이유와 재개 조건만 남긴다.
- 감사 완료는 프로젝트 개발 전체 완료나 수익성 검증을 뜻하지 않는다.

## 검증

- [초기 상태](../../../../.local/share/jusik/portfolio-audit/20260930-external-context-audit/initial-state.json)와 [결정 기록](../../../../.local/share/jusik/portfolio-audit/20260930-external-context-audit/decision.json)의 상태·판정 및 9개 source/mandate SHA를 확인했다. mandate SHA-256 `2c0b41ef4246c8f9bc0c99f1b4d544364e2350371bf5fa3f4cee2d9ce3e62749`.
- 관련 소비 경로와 상대 링크·`git diff --check`를 확인했다. 테스트·시세 네트워크 요청은 0회이며 코드 변경이 없어 재실행하지 않았다. 도구 설치 관련 조회까지 포함한 네트워크 전체 0회 주장은 하지 않는다.

## 안전·운영 상태

- 초기 관측에서 runner paused, service/timer inactive, 전체 204건(완료 176·차단 9·실패 16·외부 대기 3), READY·running 0. Codex heartbeat는 30분 ACTIVE 유지하며 중복 writer를 막기 위해 기존 systemd runner를 함께 재개하지 않는다. Toss 제외, ECOS 기존 근거 재조회 없음. 실주문·배포·원격 push 없음.
- 프로젝트 `.env`, `backend/.env`, process 범위에서 `API_K_DART`·직접 KOSIS 키 변수 부재를 확인했으나 외부 vault 전체 상태는 모른다. KOSIS 일반 proxy는 키 없이 가능하므로 서비스 전체 불가로 해석하지 않는다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-external-context-audit/`; `initial-state.json` SHA-256 `1ae80ca4fc7fe94c88e581723ee4f26729d07016d8e0377d69567f4d3ce4336b`, `decision.json` SHA-256 `efa2ee5de02fb2e23495409373e44d4331764f5a6c5d59092e311aee118a30c8`.
- 후보 재개: 기록된 9개 파일·mandate 변경, 관측값/cutoff가 있는 재현 가능 소비자 오류, 새 공표·vintage 근거, 실행 가능한 독립 review receipt 또는 새 적격 READY가 생길 때만 검토한다. 다른 독립 READY는 별도로 진행한다.
- 다음 시작: 현재 mandate·등록부와 실제 상태를 확인해 독립 READY가 있으면 진행하고, 이 후보는 위 재개 사건 없이는 재분석하지 않는다.
