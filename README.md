# Jusik

등록한 한국투자증권(KIS)과 키움증권 계좌를 한 화면에서 조회하는 로컬 읽기 전용 현황판입니다. 계좌별 자산 요약과 국내·해외 주식 보유내역을 함께 표시합니다. 프론트엔드는 Next.js App Router, React, TypeScript를 사용하고 백엔드는 Python 3.13과 FastAPI를 사용합니다.

## 로컬 실행

최초 의존성 설치와 계좌 설정을 마쳤다면 저장소 루트에서 다음 명령 하나로 백엔드와 프론트엔드를 함께 실행합니다.

```bash
./start.sh
```

http://localhost:3000 에 접속합니다. 설정된 ngrok 터널이 없으면 함께 실행하고 외부 접속용 HTTPS 주소도 표시합니다. 이미 같은 프론트엔드로 연결된 안전한 터널이 실행 중이면 이를 재사용하며 스크립트가 종료할 때 건드리지 않습니다. `Ctrl+C`로 이 스크립트가 시작한 백엔드, 프론트엔드, ngrok과 각 자식 프로세스를 함께 종료합니다. 한 프로세스가 종료되면 나머지도 종료됩니다. 3000 또는 8000 포트가 이미 사용 중이면 기존 프로세스를 건드리지 않고 실행을 중단합니다. 스크립트는 실행 위치와 관계없이 동작하며 의존성을 자동 설치하지 않습니다.

앱 자체에는 사용자 인증이 없습니다. 외부 접속은 아래의 ngrok basic-auth 정책을 통과해야 하며 두 서버는 loopback에만 바인딩됩니다. 최초 설치 또는 개별 실행은 아래 명령을 사용합니다.

### ngrok 외부 접속 설정

ngrok 계정의 Linux 설치 안내에 따라 WSL에 ngrok을 설치하고 `ngrok config add-authtoken`으로 토큰을 등록합니다. 토큰과 비밀번호는 저장소에 넣지 않습니다. 다음 파일을 `~/.config/ngrok/jusik-policy.yml`에 만들되, 내용은 YAML 문법이 아니라 아래의 정확한 JSON 형식을 사용합니다. 사용자 이름과 긴 비밀번호는 직접 정한 값으로 바꿉니다.

```json
{
  "on_http_request": [
    {
      "actions": [
        {
          "type": "basic-auth",
          "config": {
            "credentials": ["jusik:REPLACE_WITH_RANDOM_PASSWORD"],
            "enforce": true
          }
        }
      ]
    }
  ]
}
```

정책 파일 권한을 제한한 뒤 `./start.sh`를 실행합니다.

```bash
chmod 600 ~/.config/ngrok/jusik-policy.yml
./start.sh
```

스크립트는 정책 파일이 현재 사용자 소유의 일반 파일인지, 권한이 `600`인지, 조건 없는 basic-auth 한 개만 강제하는지 먼저 확인합니다. 실행 중인 ngrok이 있으면 관리 API에서 목적지가 `127.0.0.1:3000` 또는 `localhost:3000`인 공식 HTTPS 주소인지 확인하고, 인증 없는 요청이 리디렉션 없이 `401`과 Basic 인증 요구를 반환할 때만 재사용합니다. 검증에 실패하면 서버를 시작하지 않습니다. 표시된 외부 주소는 PC나 모바일 브라우저에서 열고 정책 파일에 정한 사용자 이름과 비밀번호로 로그인합니다.

백엔드:

```bash
pyenv install -s 3.13.15
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock
backend/.venv/bin/python -m uvicorn jusik.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

프론트엔드:

```bash
nvm install
nvm use
cd frontend
npm ci
npm run dev
```

http://localhost:3000 을 엽니다. 첫 페이지 접속 시 증권사별 접근 토큰을 발급하고 설정한 모든 계좌를 조회합니다. 인증정보와 증권 계좌 식별자는 백엔드에만 두며 API는 화면용 `id`와 `label`만 반환합니다. 주문 endpoint와 주문 호출은 구현하지 않았습니다.

## 한국투자증권 설정

백엔드는 저장소 루트의 `.env.prod`를 명시적으로 불러옵니다. 기존 파일은 보존하세요. 새로 설치할 때는 `.env.example`을 `.env.prod`로 복사한 뒤 로컬에서만 값을 채웁니다. 실제 인증정보와 계좌 식별자는 절대 커밋하지 마세요. 이 현황판은 모의투자 잔고가 아닌 실전 계좌의 **조회 권한**을 사용하므로 `.env.dev`는 불러오지 않습니다. 한국투자증권의 공식 실전 URL만 허용하며, 환경 변수가 파일 값보다 우선합니다.

기존 단일 계좌 변수도 계속 지원합니다.

```dotenv
KIS_APP_KEY=replace_with_app_key
KIS_APP_SECRET=replace_with_app_secret
KIS_CANO=replace_with_account_number
KIS_ACNT_PRDT_CD=replace_with_product_code
```

여러 계좌는 한 줄 JSON 배열로 추가합니다. `id`는 화면에서 쓰는 고정 식별자이고, `label`은 백엔드가 외부에 표시하는 유일한 계좌 이름입니다. 각 항목은 전역 App Key와 App Secret을 상속합니다. 다른 KIS 앱을 사용하는 계좌는 해당 항목에 `app_key`와 `app_secret`을 모두 넣으세요.

```dotenv
KIS_ACCOUNTS=[{"id":"general","label":"일반 계좌","cano":"00000000","acnt_prdt_cd":"01"},{"id":"account_2","label":"두 번째 계좌","cano":"11111111","acnt_prdt_cd":"01","app_key":"replace_with_other_app_key","app_secret":"replace_with_other_app_secret"}]
```

계좌번호는 KIS 8자리 `CANO`와 2자리 상품코드를 사용합니다. 계좌 ID와 증권 계좌 조합은 중복될 수 없습니다. 빈 배열, 잘못된 JSON, 불완전한 인증정보, 중복 계좌는 비밀값을 노출하지 않고 백엔드 시작을 중단합니다.

백엔드는 접근 토큰을 메모리에 보관하고 같은 앱 인증정보를 쓰는 계좌에서는 만료 직전까지 같은 토큰을 재사용합니다. KIS 토큰 발급 제한을 피하려면 백엔드 worker 하나를 계속 실행하세요. 인증 실패 후에는 인증정보 조합별로 1분 동안 재시도를 막습니다. 증권사 요청 제한을 줄이기 위해 잔고 요청 간격은 최소 1초입니다. 포트폴리오 응답은 백엔드에서 30초 동안 캐시하며, 브라우저와 Next.js 데이터 캐시는 끕니다. 30초 안에 새로고침하면 원래 시각이 유지된 같은 스냅샷을 반환합니다.

## 키움증권 설정

키움 계좌는 저장소 루트의 `.env.kiwum`을 별도로 불러옵니다. 이 파일이 없으면 기존 KIS 계좌만 조회합니다. 새 환경에서는 `.env.kiwum.example`을 `.env.kiwum`으로 복사하고 로컬에서만 값을 채우세요. 실제 파일은 Git에서 제외됩니다.

```dotenv
APP_ENV=kiwum
APP_KEY=replace_with_app_key
APP_SECRET=replace_with_app_secret
BASE_URL=https://api.kiwoom.com

# 선택 안전 검증: 두 값을 함께 설정하거나 둘 다 생략합니다.
# CANO=replace_with_8_digit_account_number
# ACNT_PRDT_CD=replace_with_2_digit_product_code
```

`BASE_URL`은 공식 운영 origin 또는 키움에서 안내하는 토큰 URL `https://api.kiwoom.com/oauth2/token`을 사용할 수 있으며, 백엔드는 운영 origin으로 정규화합니다. 모의투자 및 임의 호스트는 받지 않습니다. 현재 설정은 운영 계좌의 읽기 전용 잔고 조회만 지원합니다.

토큰 발급 후 `ka00001`로 토큰에 연결된 계좌번호가 올바른 10자리인지 먼저 확인합니다. 키움 토큰은 연결된 단일 계좌의 잔고만 조회합니다. `CANO` 8자리와 `ACNT_PRDT_CD` 2자리는 선택 안전 검증값이며, 설정하려면 두 값을 함께 입력해야 합니다. 명시한 조합이 토큰 계좌와 일치할 때만 잔고를 조회합니다. 두 값을 생략해도 발견한 계좌번호는 저장하거나 응답에 포함하지 않습니다. 키움의 지정단말기 인증 오류가 발생하면 키움 REST API 이용 등록 및 지정단말기 설정을 확인하세요.

키움은 국내 계좌의 총 평가금액, 평가손익, 예수금, 추정예탁자산을 제공합니다. 추정예탁자산은 앱의 통합 순자산에 포함하지 않고 키움 계좌 카드에 별도로 표시합니다. 미국 주식은 거래소와 종목 필터를 생략한 전체 잔고 조회가 성공했을 때 미국 시장 결과에 포함합니다.

## 타 증권사 계좌

이 앱은 한국투자증권과 키움증권 계좌를 조회합니다. `KIS_ACCOUNTS`에 메리츠증권이나 신한투자증권 계좌를 넣어도 조회할 수 없습니다. 각 증권사의 App Key와 App Secret은 해당 증권사 API 호출에만 사용됩니다.

토스처럼 여러 금융회사의 정보를 한 화면에 모으는 서비스는 KIS 다계좌 설정과 다른 문제입니다. 각 증권사의 공식 조회 API를 개별 연동하거나, 사용자 동의를 받아 표준 API로 금융정보를 전송하는 마이데이터 사업 구조가 필요합니다. 금융위원회는 여러 금융회사의 개인신용정보를 수집해 사용자에게 제공하는 마이데이터 서비스를 허가 대상으로 설명합니다. 개인 로컬 앱에 KIS 키만 추가해서 같은 기능을 만들 수는 없습니다.

- 한국투자증권 계좌 여러 개: 현재 `KIS_ACCOUNTS`에 직접 등록합니다.
- 키움증권 계좌: `.env.kiwum`의 인증정보에 연결된 단일 계좌를 조회합니다.
- 메리츠·신한 등 다른 증권사: 증권사별 공식 조회 API의 제공 범위, 이용 조건, 사용자 인증 방식을 각각 확인한 뒤 별도 adapter를 구현해야 합니다.
- 토스 수준 통합: 마이데이터 또는 제휴 서비스의 법적·보안·운영 요건을 먼저 결정해야 합니다.

## 조회 범위와 의미

- `KIS_ACCOUNTS`에 명시한 모든 계좌 또는 기존 `KIS_CANO` 단일 계좌를 조회합니다. KIS는 고객의 모든 계좌를 자동 발견하는 API를 제공하지 않습니다.
- `.env.kiwum`이 있으면 토큰에 연결된 키움 계좌 한 개를 추가로 조회합니다. 선택 검증값을 설정한 경우 토큰 계좌와 일치하지 않으면 잔고 API를 호출하지 않습니다.
- KIS 투자계좌 자산현황에서 받은 원화 순자산, 총 평가금액, 예수금, 미실현 손익, 해외주식 평가금액을 표시합니다. 지원하지 않거나 없는 요약 필드는 0으로 바꾸지 않고 사용할 수 없음으로 남깁니다.
- 국내주식과 미국(NASD 실전 조회는 미국 거래소 포함)·홍콩·상하이·선전·일본·하노이·호치민 해외주식을 조회합니다.
- 잔고 API 스냅샷이며 실시간 시세가 아닙니다. 특히 장 마감 중 가격은 지연될 수 있습니다. 조회 완료 시각은 내부에서 UTC로 저장하고 한국 시각으로 보여 주며 거래소 시세 시각과 다릅니다.
- 보유 수량, 평균 매입가, 현재가, 매입금액, 평가금액, 미실현 손익, 계산 수익률을 표시합니다.
- 통합 원화 순자산은 계좌별로 확인된 `nass_tot_amt`의 합계입니다. 주식 평가금액을 다시 더하지 않습니다. 부분 합계와 사용할 수 없는 합계는 화면에 명확히 표시합니다.
- 원화·달러·홍콩달러·위안·엔·베트남동 주식 합계를 분리합니다. 자체 환전과 여러 통화의 총합은 제공하지 않습니다. 채권, 선물·옵션, 연금 전용 포지션, 실현 손익은 이번 버전 범위 밖입니다.
- 백엔드는 `Decimal`로 계산하고 금융값은 문자열로 API를 통과합니다. 수익률은 소수 둘째 자리에서 반올림합니다. 표시용 가격 정밀도는 부동소수점 계산 없이 잘라 냅니다. 매입금액이 0이면 수익률은 정의되지 않아 대시로 표시합니다.
- 한 시장을 포함하려면 모든 연속 조회 페이지가 성공해야 합니다. 완전히 같은 중복 포지션은 제거하고, 서로 충돌하는 중복 포지션은 해당 시장 조회를 실패 처리해 이중 합산을 막습니다. 수량이 0인 포지션은 제외합니다.
- 키움 국내 잔고는 동일 종목의 현금·신용 보유분을 합산하고 평균매입가를 수량 가중 계산합니다. 미국 잔고 수량은 주문가능수량이 아닌 `poss_qty`를 사용합니다.
- 계좌와 시장 조회 실패를 명확히 표시합니다. 성공한 계좌와 시장 결과는 계속 표시합니다. 주식 합계는 성공한 시장 조회만 포함하고, 순자산 합계는 검증된 원화 순자산이 있는 계좌만 포함합니다. 필수 보유 필드가 없거나 잘못되면 0으로 바꾸지 않고 검증에 실패합니다.
- 데이터베이스와 수익률 추이 차트는 없습니다. 날짜별 스냅샷을 저장해야 하기 때문입니다.

## 검사

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy jusik
cd ../frontend
npm run lint
npm run typecheck
npm run build
```

테스트는 모의 증권사 응답만 사용하며 주문을 내지 않습니다. 설정 검증, 계좌 일치 확인, 토큰 재사용, 부분·전체 실패, 잔고 0, `Decimal` 정밀도, 음수·누락 값, 페이지 조회, 시간대 경계, 캐시 합치기, 오류 정보 가리기를 검증합니다. 부분 체결과 취소·거절 주문은 이 앱이 처리하지 않으며 증권사가 반영한 최종 보유내역을 조회합니다.

## GitHub

remote가 없으면 README나 license 없이 빈 비공개 GitHub 저장소를 만듭니다. 그 뒤 `git remote add origin https://github.com/YOUR_USERNAME/jusik.git`로 URL을 설정합니다. Git을 아직 초기화하지 않았다면 먼저 `git init -b main`을 실행합니다.

커밋 전 `git status --short`, `git check-ignore .env.prod .env.dev`를 실행하고 `git diff --cached`를 확인합니다. 프로젝트 코드와 자리표시자 설정만 stage 합니다. 첫 커밋은 `git push -u origin main`으로 push 합니다. 무시된 환경 파일을 강제로 추가하지 마세요. 이 설정은 커밋·원격 저장소 생성·push를 자동으로 하지 않습니다.

## API 참고 자료

- [KIS 국내주식 잔고조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py)
- [KIS 투자계좌 자산현황조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py)
- [KIS 해외주식 잔고조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py)
- [KIS Open API 서비스](https://apiportal.koreainvestment.com/apiservice)
- [키움 REST API 공식 명세](https://github.com/Kiwoom-Securities/Kiwoom-REST-API)
- [금융위원회 마이데이터 허가 안내](https://www.fsc.go.kr/po010105/74324)
- [금융결제원 오픈뱅킹 서비스](https://openapi.kftc.or.kr/service/openBanking)
- [Next.js 설치](https://nextjs.org/docs/app/getting-started/installation)
