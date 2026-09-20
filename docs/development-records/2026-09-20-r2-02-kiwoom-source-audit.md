# R2-02 Kiwoom 비용 원천 audit

- 상태: 공식 표기 일부 확인·비용 계약과 경제 평가는 미완료
- 공식 현재 페이지: Kiwoom 안내는 국내주식 거래 수수료를 KRX `0.015%`, NXT
  `0.0145%`로 표기하고, 증권거래비용·기타 비용이 추가될 수 있다고 명시합니다.
  URL: https://www.kiwoom.com/e/m/home/event/VEvent20260068View
- 해외주식 보조 자료: Kiwoom 교육 PDF는 미국 온라인 `0.25%`, 오프라인 `0.50%` 및
  당시 SEC fee 표기를 포함하지만, 문서 심사기간이 2024-05-21~2025-05-20으로
  현재 계약의 유효기간 증거가 아닙니다.
  URL: https://www.kiwoom.com/inv/resources/inv/assets/images/biz/invest/edu/matr/OSTK67-TXBK.pdf
- 계좌 확인 경로: Kiwoom 해외주식 거래내역 화면은 종목별 거래수량·정산금액·인지세·
  수수료를 계좌별로 조회할 수 있다고 안내하지만, 해당 계좌의 실제 거래내역은 제공되지
  않았습니다. URL: https://download.kiwoom.com/htsw_help/kiwoom_fx/2110.html
- 판정: 현재 `fee_rate`·`sell_tax_rate`에 시장·상품·계좌·거래일·우대기간·세목을
  결속하지 못했습니다. 공식 표기를 기존 modeled rate로 치환하거나 미국 SEC fee를
  broker 고객비용으로 추정하지 않으며, R2-02와 경제 성과 승격은 유지합니다.
- 다음 입력: 사용할 broker/계좌의 당시 fee schedule 또는 거래명세 원장(민감정보 제거),
  국내 시장 board·상품과 미국 거래일의 적용 세목·유효기간을 별도 contract로 고정해야 합니다.
