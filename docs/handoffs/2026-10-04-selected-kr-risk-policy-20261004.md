# 선정 KR 위험 정책 인계

- 완료: 구현8efee89 → 독립P2 2건 → 동일소유자cf1c8ac수정 → 독립PASS → main7cc20002cb43bfae1256b581c3871f419db16fd1.
- 검증: main268검사/Ruff/strict mypy PASS, 독립Fraction 4사례의 청산·회복·재진입/현금/수량/NAV/고점/순서반전 PASS. 기존11개/KRsequence전체출력 보존, 위험없는정책은configSHA만변경.
- 범위: 실제planner 두고정방법→동일 raw원장, episode10%청산·28일대기·주간2회확인·다음4주재진입. lifetime고점/MDD20 및과거한도위반 보존. 비용연쇄cap재평가·첫공통개장 선택 수정.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-kr-risk-policy/`, manifest7597cdc43ca614c155af3e853c57809605d26460642892bc4824fefd8721cd4a. 실패한초기probe의확인횟수2개정확일치 가정은최초2회/준비시각검사로정정; 이후 주간유효확인기록은허용한다.
- 다음: selected-kr-comparison-20261004 읽기전용조사결과→계획→같은구현자/checkout 재사용. 기존 회계/지표를 재작성하지 않는 동일입력 합성 비교연결. 실자료수익률 공개는원천인수전금지.
- 등록16/rev1·초기1억원·레버리지20%·MDD20% 유지. 실제READYcohort/성과/OOS 미검증, 자동매매·실주문·PAPER/live·원격push 없음. rootHANDOFF보존.
