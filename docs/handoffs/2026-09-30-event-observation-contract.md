# AOS 사건 관측·배당 회계 계약 인계

- 작업 `event-observation-contract-20260930`, 기준 `86eef58`; 구현 commit과 main 통합 SHA는 감독자 확정 예정. [개발 기록](../development-records/2026-09-30-event-observation-contract.md)에 판정을, [감사 matrix](/home/kwl/.local/share/jusik/portfolio-audit/20260930-event-observation-contract/matrix.json)·[결속 결과](/home/kwl/.local/share/jusik/portfolio-audit/20260930-event-observation-contract/result.json)에 9개 필드 행과 해시를 남겼다.
- 현 `observed_at`은 공급자 관측시각이며 `captured_at`은 별도 수집시각이다. 코드의 aware/max-cutoff/unknown 차단과 과거 공급자 공개 가능성·출처 연결 증명은 구분한다. AOS 배포본의 분 단위 표기를 초 단위 사실이나 Yahoo 관측값으로 채우지 않는다. 과거 우리 시스템 최초 수집 영수증을 무조건 요구하는 새 hard gate도 만들지 않았다.
- 기존 `DividendAction`의 확정 배당 자격·gross accrual/payment 함수는 재사용 후보이나, 현 근사 snapshot은 배당 action을 내보내지 않는다. effective/ex 역할·금액/통화 전달·raw 가격 basis·replay 포지션·사전 비용/FX/세금 정책이 확인될 때만 별도 adapter를 검토한다. entitlement 수량은 검증된 포지션에서 파생한다.
- 자료/PIT/성과 적격은 계속 false. 다음은 125건 재조회가 아니라 AOS 단일 사례의 최소 원천 필드와 date/time precision 표현을 격리 계약으로 검토한다. 생산 코드·준비 자료·원본·mandate·서비스·주문 변경은 없고, 기존 247개 테스트는 반복하지 않았다.
