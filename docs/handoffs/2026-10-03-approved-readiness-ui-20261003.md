# 등록 16종목 연구 계속하기

- 2026-10-03 UTC, `/home/kwl/projects/jusik`, main 통합 `262699bcf5ba675b785e247aeeb56a2ded239e35`.
- 사용자 목표: 등록 종목 안에서만 연구하고 한 단계가 끝나면 다음 단계 진행. 자동매매 시작·GitHub Pages 제외. 현재 자료 현황 API/UI 개발은 완료, 비용 차감 수익성 비교는 미완료다.
- [개발 기록](../development-records/2026-10-03-approved-readiness-ui-20261003.md): 가격 기간, 배당 검토 기록, FX 날짜 범위를 표시한다. 종목 신원·PIT·배당 적격·총수익 완전성을 선언하지 않는다. revision 변경 시 이전 현황을 숨긴다.
- 독립 코드/화면 검토 PASS; main focused 8건·Ruff·운영 Next 빌드 PASS. 운영 16종목 HTTP/no-store·인증 401/200·390px 모바일 확인. 전체 TestClient 수명주기 검사는 종료 대기로 미완료.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-approved-readiness-ui/`에 캡처, 검증, manifest. 구현 워크트리와 병합 브랜치 정리 완료. 루트 `HANDOFF.md`는 사용자 소유로 보존했다.
- `jusik-web-stack.service` transient unit 실행 중. 웹 https://hamster-bucket-neatness.ngrok-free.dev/research/approved-universe ; 기존 인증 유지. 재부팅 시에는 이 unit의 자동 시작을 보장하지 않으므로 실제 서비스부터 확인한다.
- 같은 대화 heartbeat `automation` ACTIVE/30분, 현재 thread `01a0fb62-690f-7820-832d-421bad42a6bf`. 컴퓨터와 앱 실행 필요. 변경 없는 상태는 조용히 유지하고 유의미한 결과·실패·사용자 결정만 알린다.
- roadmap 개발 runner pause/dispatch false 및 서비스·timer 정지 유지. 재부팅으로 살아난 과거 93후보 GPU optimizer는 stop/disable했다. read-only prospective monitor는 유지했다. 기존 runner dispatch를 자동 재개하지 않는다.
- MSFT 공식 배당 12건 import 완료: [자료 보완 인계](2026-10-03-msft-dividend-review.md). coverage 적격 13/111, UI 검토 기록 존재 14/111은 서로 다른 수치다. 현금 원장 반영 없음.
- SOXL 공급자 반올림과 공식 금액 차이는 미해결. 기존 strict 조건 완화·revision 덮어쓰기 금지. 2025 연도별 공지는 웹 본문에서 날짜만 보이고 금액 표를 확인하지 못했으며 2024 공지는 timeout. 같은 차단 URL을 반복하지 않는다.
- 다음 순서: (1) 현재 등록 revision과 실행 중 작업 확인, (2) 공식 배당/분할·종목 신원·달력·거래 시점 FX/비용 근거 보완, (3) NAV 독립 검증, (4) 동일 종목·기간·비용의 buy-and-hold 대 사전등록 최대 3개 전략 비교, (5) 미래 관측 검증. 1억원·레버리지20%·MDD20% 등 위임 조건은 최신 `docs/research-mandate.*`를 읽고 유지한다.

재개: 이 인계와 `MEMORY.md`, `docs/research-mandate.md`를 읽고 현재 서비스·등록 목록·진행 writer를 확인한 뒤, 남은 자료 근거에서 실행 가능한 한 단계를 수행하고 다음 단계로 이어간다. 이미 통과한 UI 개발을 반복하지 않는다.
