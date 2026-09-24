# 2026-09-24 R1-05 Yahoo long-history bounded receipt

기간 파라미터가 원인인지 확인하기 위해 LIME/MDA에 Yahoo Chart `period1=0` 장기 요청을 각각 한 번씩 수행했다. receipt 경로는 `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/yahoo-long-history-bounded/`이며 manifest SHA-256은 `1718cda518b062d625a1e1a058104cab3f2cc61176a490e68a972ba314af9f8e`이다.

- LIME: 59행, 첫 관측 세션 `2026-07-01`, 마지막 `2026-09-23`, exchange NasdaqGS, `firstTradeDateMilliseconds=null`
- MDA: 135행, 첫 관측 세션 `2026-03-12`, 마지막 `2026-09-23`, exchange NYSE, `firstTradeDateMilliseconds=null`
- raw SHA: LIME `a71df622f096623fba9e798e32020cddde5f3e6455bc8f440450f0af4e93238f`, MDA `2d390678f3972560eb0ab8f844953d67ec9a2902564386ae747cdec84b740493`

기간을 확장해도 시작일은 변하지 않았지만 provider가 상장·최초관측 원인 또는 historical observed_at을 제공하지 않았다. 따라서 짧은 이력이라는 강한 정황은 보존하되 366개 세션을 자동 제외하거나 R1-05/PIT/economic acceptance로 승격하지 않는다.
