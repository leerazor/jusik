# 공식 배당 자료 보완 인계

- 2026-10-03, main의 연구 자료 보완. 코드 변경 없음.
- MSFT 공식 12건을 기존 importer로 사본 검증 후 연구 검토 DB에 추가했다. idempotent 검증과 운영 재조회 통과. 전체 eligible 13/111, 제외 98. 당시 원천 완전성·순수익 적격은 미확인.
- 원문/manifest/검증은 `/home/kwl/.local/share/jusik/portfolio-audit/20261003-msft-dividend-review/`에 있다. [작업 기록](../development-records/2026-10-03-msft-dividend-review.md)을 먼저 읽는다.
- SOXL 최근 4건에 공급자 반올림과 공식 금액 차이를 발견했다. 직접 원문 다운로드 403, import 없음. strict 일치 기준과 원본을 보존한다.
- 다음: 공식 연도별 분배 공지 등 대체 원문을 한정 확보하고 배당 현금 금액의 원천 우선순위를 별도 설계한다. 과거 source revision을 수정하거나 현재 문서를 과거 관측 근거로 소급하지 않는다.
- 자동매매·PAPER 승격·현금 원장 적용 없음.
