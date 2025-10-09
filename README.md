# 📊 비트코인 분석 리포트 (Bitcoin Analysis Report)

실시간 비트코인 기술적 분석을 제공하는 자동화된 리포트 시스템입니다.
14개 핵심 지표를 분석하여 투자 판단을 돕습니다.

## 🌐 실시간 리포트 보기

**GitHub Pages:** https://9min.github.io/bitcoin-analysis/

> 매 시간마다 자동으로 업데이트됩니다!

## ✨ 주요 기능

### 📈 14개 기술적 지표 분석
- **모멘텀 지표**: RSI, MACD, 스토캐스틱
- **추세 지표**: 이동평균선, EMA, 일목균형표, ADX
- **변동성 지표**: 볼린저밴드, ATR
- **거래량 지표**: OBV
- **심리 지표**: 공포/탐욕 지수
- **특별 분석**: 피보나치, 4년 주기, 고점 근접도

### 🎯 제공 정보
- 현재 비트코인 가격 (실시간)
- 투자 판단 (매수/매도/중립)
- 종합 점수 (-15점 ~ +25점)
- 가격 목표 및 전략
- 권장 행동

### 워크플로우
1. 비트코인 데이터 수집 (Binance API)
2. 14개 기술 지표 계산
3. 투자 분석 수행
4. HTML 리포트 생성
5. GitHub Pages 자동 배포

## 📁 프로젝트 구조

```
bitcoin-analysis/
├── bitcoin_analysis.py          # 핵심 분석 엔진
├── generate_html_report.py      # 로컬용 HTML 생성
├── generate_for_github.py       # GitHub Actions용 생성
├── requirements.txt             # Python 의존성
├── .github/
│   └── workflows/
│       └── deploy.yml          # 자동 배포 워크플로우
└── README.md
```

## 🛠️ 기술 스택

- **언어**: Python 3.11+
- **데이터**: Binance API (ccxt)
- **분석**: pandas, numpy, ta
- **배포**: GitHub Actions + GitHub Pages
- **자동화**: Cron (매일 자동 실행)

## 📊 분석 방법론

### 종합 점수 계산
각 지표별 가중치를 적용하여 종합 점수 산출:
- 이동평균선 (1.2)
- EMA (1.2)
- 일목균형표 (1.5)
- MACD (1.0)
- RSI (0.8)
- 기타 지표들...

### 투자 판단 기준
- **적극 매수**: +10점 이상
- **매수**: +6점 이상
- **중립**: -1 ~ +1점
- **매도**: -6점 이하
- **적극 매도**: -10점 이하

### 업데이트 주기 변경
`.github/workflows/deploy.yml` 파일의 cron 수정:
```yaml
# 매 시간마다 (현재)
- cron: '0 * * * *'

# 매일 오전 9시로 변경하려면
- cron: '0 0 * * *'

# 하루 2번 (오전 9시, 오후 9시)
- cron: '0 0,12 * * *'
```

## 📄 라이선스

MIT License

## ⚠️ 면책 조항

이 분석은 참고용이며 투자 권유가 아닙니다.
모든 투자 결정은 본인의 책임입니다.

---

Made with ❤️ by 9min

