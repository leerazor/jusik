# 2026-09-17 development delivery policy

- 상태: 완료
- 기준: `9da77dc`
- 범위: runtime, research planner, investment-roadmap planner/generated prompt와 지속 개발 runner 운영 문서에 delivery policy를 명시했다.

## 변경과 결정

agent가 임의로 만든 unit regression fixture 개수나 일반 focused test 호출 횟수는 과학적 실험 cap이 아니므로 기술 slice를 영구 중단시키지 않는다. 감독자가 승인한 prospective replacement는 focused 파일과 runtime/artifact budget을 사용한다. 역사적 위반은 보존하며 소급 승인하지 않는다.

연구 표본·기간·가정·seed·실험 횟수, 금융 자료·계산 예산과 사용자 명시 한도는 계속 엄격하다. 현재 tracked 문서는 오래된 agent 생성 task test-count 제한보다 우선한다. 기술 slice 완료는 전체 금융·자료 acceptance와 구분하고 identity/hash/review 검증은 유지한다. 소유 environment/cache의 일상적 repair는 새 사용자 승인 없이 수행할 수 있다.

## 검증

- 변경된 runner 모듈의 Ruff, format, configured strict mypy와 기존 세 runner test files의 pytest를 worktree 전용 venv에서 실행했다.
- 실제 Codex, 서비스, 네트워크 자료 수집, 거래 주문은 실행하지 않는다.

## 통합과 운영

- 기록 시각: 2026-09-17T00:23:03.114594+00:00; 작업 slug: `development-delivery-policy`.
- 통합: `6ebfabefbefd2d8f91f1e217c1129bbcd4010a3b`; worker/main pytest95개, Ruff check/format, strict mypy PASS. 독립 검토 중요 지적 없음.
- 사용자 UI/API·투자 조건·상태 schema 변경 없음. 운영 문서는 `docs/development-runner.md`를 갱신했습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-delivery-recovery`; policy-worker·policy-source·policy-integration.json 참조. 소스/환경/증거 보관 후 전용 worktree/branch를 정상 제거했습니다.
- runner는 수동 통합 중 paused/service inactive였으며 기록 커밋 후 R1-04 재개 증거를 activation.json에 저장합니다. 실주문/PAPER 활성화/원격 push 없음.
