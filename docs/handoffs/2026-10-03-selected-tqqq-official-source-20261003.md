# TQQQ 공식 원천 인계

- 갱신 2026-10-03T14:30:13.283558+00:00; [기록](../development-records/2026-10-03-selected-tqqq-official-source-20261003.md), audit20261003-selected-tqqq-source의 manifest943bb11c와status부터확인.
- ProShares공식API13사건 금액/배당락일/기준일/지급일을 확보했으나 공급자금액13건모두불일치. USD직접근거와과거주당기준은미확인. 교정manifest는해당두필드없음. 독립조건충족후mismatched13 실제반영,eligible24/111그대로.
- 원문·과거vendor값·기존matched분할검토보존. split공지중복1회외추가반영없음. 같은API와분할페이지재조회금지. 원주가·NAV·성과입력으로자동연결하지않는다.
- 다음은 충돌을유지하는정확한공식입력경로 검토와화면의검토결과표시확인. 새readinessAPI는reviewed count만제공하므로 matched/partial/mismatched가어떻게보이는지 별도explore진행.
