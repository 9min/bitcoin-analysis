import os
import ccxt
import pandas as pd
import numpy as np
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# .env 파일 로드 (AWS EC2 등에서 사용)
try:
    from dotenv import load_dotenv
    load_dotenv()  # .env 파일이 있으면 자동 로드
except ImportError:
    pass  # python-dotenv가 없어도 환경 변수는 작동

# 한국 시간대 설정 (UTC+9)
KST = timezone(timedelta(hours=9))

def get_kst_now():
    """현재 한국 시간 반환"""
    return datetime.now(KST)

# 비트코인 반감기 날짜 (과거 및 예정)
HALVING_DATES = {
    "2012-11-28": "1차 반감기",
    "2016-07-09": "2차 반감기", 
    "2020-05-11": "3차 반감기",
    "2024-04-20": "4차 반감기",
    "2028-04-XX": "5차 반감기 (예정)"
}

# 역사적 고점 데이터 (참고용)
HISTORICAL_ATH = {
    "2013-12-04": 1163,    # 1차 사이클 고점
    "2017-12-17": 19783,   # 2차 사이클 고점
    "2021-11-10": 69000,   # 3차 사이클 고점
}

# 설정 정보 (환경 변수에서 가져오기 - 보안)
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")  # 발신자 이메일
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")  # 앱 비밀번호 (Gmail의 경우 앱 비밀번호 필요)
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")  # 수신자 이메일

# Gmail SMTP 서버 설정
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # TLS 포트 사용 (기존 SSL 465 대신)

# 비트코인 데이터 가져오기
def get_bitcoin_data():
    """
    여러 거래소를 시도하여 비트코인 데이터를 가져옵니다.
    Binance가 실패하면 다른 거래소를 시도합니다.
    """
    # 시도할 거래소 목록 (순서대로)
    exchanges_to_try = [
        ('kraken', 'BTC/USD'),      # Kraken (미국/유럽)
        ('coinbase', 'BTC/USD'),    # Coinbase (미국)
        ('bitstamp', 'BTC/USD'),    # Bitstamp (유럽)
        ('binance', 'BTC/USDT'),    # Binance (글로벌, 일부 지역 제한)
    ]
    
    for exchange_name, symbol in exchanges_to_try:
        try:
            print(f"[시도] {exchange_name} 거래소에서 데이터 가져오는 중...")
            
            # 거래소 객체 생성
            exchange_class = getattr(ccxt, exchange_name)
            exchange = exchange_class()
            
            # 일봉 데이터 가져오기 (최근 500일 데이터 - 사이클 분석용)
            ohlcv = exchange.fetch_ohlcv(symbol, '1d', limit=500)
            
            # DataFrame으로 변환
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            print(f"[성공] {exchange_name}에서 데이터를 성공적으로 가져왔습니다.")
            return df
            
        except Exception as e:
            print(f"[실패] {exchange_name}: {str(e)[:100]}")
            continue
    
    # 모든 거래소 시도 실패
    print(f"[오류] 모든 거래소에서 데이터를 가져올 수 없습니다.")
    return None

# 비트코인 4년 주기 분석
def analyze_bitcoin_cycle():
    """현재 비트코인이 4년 주기 중 어디에 위치하는지 분석"""
    current_date = get_kst_now()
    
    # 가장 최근 반감기 찾기
    last_halving = None
    next_halving = None
    
    # naive datetime을 aware datetime으로 변환 (KST 기준)
    halving_dates_sorted = sorted([
        datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=KST) 
        for date in HALVING_DATES.keys() if "XX" not in date
    ])
    
    for halving_date in halving_dates_sorted:
        if halving_date <= current_date:
            last_halving = halving_date
        elif halving_date > current_date and next_halving is None:
            next_halving = halving_date
            break
    
    if last_halving is None:
        return None
    
    # 반감기 이후 경과 일수
    days_since_halving = (current_date - last_halving).days
    
    # 4년 주기에서의 위치 (%)
    cycle_days = 365.25 * 4  # 4년
    cycle_position_pct = (days_since_halving / cycle_days) * 100
    
    # 사이클 단계 판단
    if cycle_position_pct < 15:
        cycle_phase = "축적기 (반감기 직후)"
        phase_score = 2  # 매수 적극 권장
    elif cycle_position_pct < 40:
        cycle_phase = "상승 초기 (강세장 시작)"
        phase_score = 1.5  # 매수 권장
    elif cycle_position_pct < 60:
        cycle_phase = "상승 중기 (강세장 한복판)"
        phase_score = 0.5  # 보유 권장
    elif cycle_position_pct < 75:
        cycle_phase = "상승 후기 (과열 구간)"
        phase_score = -0.5  # 일부 매도 시작
    elif cycle_position_pct < 90:
        cycle_phase = "고점 근접 (분할 매도 구간)"
        phase_score = -1.5  # 분할 매도 적극 권장
    else:
        cycle_phase = "사이클 말기 (약세장 전환)"
        phase_score = -2  # 매도 완료 권장
    
    cycle_info = {
        "last_halving": last_halving,
        "next_halving": next_halving,
        "days_since_halving": days_since_halving,
        "cycle_position_pct": cycle_position_pct,
        "cycle_phase": cycle_phase,
        "phase_score": phase_score
    }
    
    return cycle_info

# 고점 근접도 분석 (과매수 및 과열 신호 종합)
def analyze_peak_proximity(df, indicators):
    """현재 가격이 사이클 고점에 얼마나 가까운지 분석"""
    
    latest = df.iloc[-1]
    current_price = latest['close']
    
    # 1. 역사적 최고가 대비 비율
    max_price_52w = df['high'].tail(365).max()  # 52주 최고가
    max_price_all = df['high'].max()  # 전체 기간 최고가
    
    price_vs_52w_high = (current_price / max_price_52w) * 100
    price_vs_all_high = (current_price / max_price_all) * 100
    
    # 2. RSI 극단값 (70 이상이 지속되는 정도)
    rsi = latest['rsi']
    rsi_readings_above_70 = (df['rsi'].tail(30) > 70).sum()  # 최근 30일 중 RSI 70 이상 일수
    
    # 3. 200일 이평선 대비 괴리율
    ma200 = latest['ma200']
    price_deviation_ma200 = ((current_price - ma200) / ma200) * 100
    
    # 4. 볼린저밴드 위치 지속성
    bb_upper = latest['bb_upper']
    bb_lower = latest['bb_lower']
    bb_position = ((current_price - bb_lower) / (bb_upper - bb_lower)) * 100 if (bb_upper - bb_lower) > 0 else 50
    days_near_bb_upper = (((df['close'].tail(30) - df['bb_lower'].tail(30)) / (df['bb_upper'].tail(30) - df['bb_lower'].tail(30)) * 100) > 80).sum()
    
    # 5. 거래량 폭증 (고점 신호)
    volume_ma = df['volume'].tail(30).mean()
    current_volume = latest['volume']
    volume_surge = (current_volume / volume_ma) if volume_ma > 0 else 1
    
    # 고점 근접 점수 계산 (0~100)
    peak_score = 0
    
    # 가격이 52주 최고가 근처 (20점)
    if price_vs_52w_high > 95:
        peak_score += 20
    elif price_vs_52w_high > 90:
        peak_score += 15
    elif price_vs_52w_high > 85:
        peak_score += 10
    
    # RSI 과열 지속 (20점)
    if rsi > 80:
        peak_score += 20
    elif rsi > 70:
        peak_score += 15
        if rsi_readings_above_70 > 15:  # 최근 30일 중 절반 이상
            peak_score += 5
    
    # 200일선 괴리율 과도 (20점)
    if price_deviation_ma200 > 100:  # 100% 이상 괴리
        peak_score += 20
    elif price_deviation_ma200 > 70:
        peak_score += 15
    elif price_deviation_ma200 > 50:
        peak_score += 10
    
    # 볼린저밴드 상단 장기 체류 (20점)
    if days_near_bb_upper > 20:
        peak_score += 20
    elif days_near_bb_upper > 15:
        peak_score += 15
    elif days_near_bb_upper > 10:
        peak_score += 10
    
    # 거래량 폭증 (20점)
    if volume_surge > 3:  # 평균 대비 3배 이상
        peak_score += 20
    elif volume_surge > 2:
        peak_score += 15
    elif volume_surge > 1.5:
        peak_score += 10
    
    # 공포/탐욕 지수 (추가 보너스)
    fear_greed = latest['fear_greed']
    if fear_greed > 85:
        peak_score += 10
    elif fear_greed > 75:
        peak_score += 5
    
    # 최대값 제한
    peak_score = min(100, peak_score)
    
    # 고점 근접도 판단
    if peak_score >= 80:
        peak_status = "🔴 극도의 과열 (즉시 분할 매도 권장)"
        sell_recommendation = "보유 물량의 80-100% 매도 권장"
    elif peak_score >= 60:
        peak_status = "🟠 심각한 과열 (적극 분할 매도)"
        sell_recommendation = "보유 물량의 50-70% 매도 권장"
    elif peak_score >= 40:
        peak_status = "🟡 과열 구간 (분할 매도 시작)"
        sell_recommendation = "보유 물량의 30-50% 매도 권장"
    elif peak_score >= 20:
        peak_status = "⚪ 상승 지속 (일부 익절 고려)"
        sell_recommendation = "보유 물량의 10-20% 익절 고려"
    else:
        peak_status = "🟢 정상 범위"
        sell_recommendation = "보유 유지"
    
    peak_info = {
        "peak_score": peak_score,
        "peak_status": peak_status,
        "sell_recommendation": sell_recommendation,
        "price_vs_52w_high": price_vs_52w_high,
        "price_deviation_ma200": price_deviation_ma200,
        "rsi_overheating": rsi_readings_above_70,
        "bb_days_near_upper": days_near_bb_upper,
        "volume_surge": volume_surge,
        "details": {
            "52주 최고가 대비": f"{price_vs_52w_high:.1f}%",
            "200일선 괴리율": f"+{price_deviation_ma200:.1f}%",
            "RSI 과열 일수": f"{rsi_readings_above_70}/30일",
            "볼린저 상단 체류": f"{days_near_bb_upper}/30일",
            "거래량 배수": f"{volume_surge:.1f}x"
        }
    }
    
    return peak_info

# 기술적 지표 계산
def calculate_indicators(df):
    if df is None or df.empty:
        return None
    
    # 1. RSI (14)
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    
    # 2. MACD
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_histogram'] = macd.macd_diff()
    
    # 3. 이동평균선 (20일, 50일, 200일)
    df['ma20'] = ta.trend.SMAIndicator(df['close'], window=20).sma_indicator()
    df['ma50'] = ta.trend.SMAIndicator(df['close'], window=50).sma_indicator()
    df['ma200'] = ta.trend.SMAIndicator(df['close'], window=200).sma_indicator()
    
    # 4. 지수 이동평균선 (12일, 26일, 50일, 100일) - 중장기 트레이드에 적합
    df['ema12'] = ta.trend.EMAIndicator(df['close'], window=12).ema_indicator()
    df['ema26'] = ta.trend.EMAIndicator(df['close'], window=26).ema_indicator()
    df['ema50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    df['ema100'] = ta.trend.EMAIndicator(df['close'], window=100).ema_indicator()
    
    # 5. 볼린저 밴드
    bollinger = ta.volatility.BollingerBands(df['close'])
    df['bb_upper'] = bollinger.bollinger_hband()
    df['bb_middle'] = bollinger.bollinger_mavg()
    df['bb_lower'] = bollinger.bollinger_lband()
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    # 6. 스토캐스틱 오실레이터
    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()
    
    # 7. ATR (Average True Range) - 변동성 측정
    df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
    
    # 8. OBV (On Balance Volume) - 거래량 기반 지표
    df['obv'] = ta.volume.OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
    df['obv_ma'] = ta.trend.SMAIndicator(df['obv'], window=20).sma_indicator()
    
    # 9. ADX (Average Directional Index) - 추세 강도 측정
    adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['adx'] = adx.adx()
    df['adx_pos'] = adx.adx_pos()
    df['adx_neg'] = adx.adx_neg()
    
    # 10. 일목균형표 (Ichimoku Cloud) - 중장기 트레이드에 매우 유용
    ichimoku = ta.trend.IchimokuIndicator(df['high'], df['low'])
    df['ichimoku_a'] = ichimoku.ichimoku_a()  # 선행스팬A (구름 상단/하단)
    df['ichimoku_b'] = ichimoku.ichimoku_b()  # 선행스팬B (구름 상단/하단)
    df['ichimoku_base'] = ichimoku.ichimoku_base_line()  # 기준선
    df['ichimoku_conversion'] = ichimoku.ichimoku_conversion_line()  # 전환선
    
    # 11. 피보나치 되돌림 레벨 계산 (최근 52주 기준)
    recent_high = df['high'].tail(52).max()
    recent_low = df['low'].tail(52).min()
    diff = recent_high - recent_low
    
    df['fib_236'] = recent_high - 0.236 * diff
    df['fib_382'] = recent_high - 0.382 * diff
    df['fib_500'] = recent_high - 0.500 * diff
    df['fib_618'] = recent_high - 0.618 * diff
    
    # 12. 공포/탐욕 지수 계산 (간이버전 - RSI, 볼린저밴드 위치, 거래량 기반)
    df['fear_greed'] = calculate_fear_greed_index(df)
    
    return df

# 공포/탐욕 지수 계산 (0-100, 0=극단적 공포, 100=극단적 탐욕)
def calculate_fear_greed_index(df):
    fear_greed = pd.Series(index=df.index, dtype=float)
    
    for i in range(len(df)):
        if i < 20:  # 최소 20일 데이터 필요
            fear_greed.iloc[i] = 50
            continue
            
        # RSI 기여도 (30%)
        rsi = df['rsi'].iloc[i]
        rsi_score = rsi if not pd.isna(rsi) else 50
        
        # 볼린저밴드 위치 기여도 (30%)
        bb_upper = df['bb_upper'].iloc[i]
        bb_lower = df['bb_lower'].iloc[i]
        price = df['close'].iloc[i]
        if not pd.isna(bb_upper) and not pd.isna(bb_lower) and bb_upper != bb_lower:
            bb_position = ((price - bb_lower) / (bb_upper - bb_lower)) * 100
        else:
            bb_position = 50
        
        # 거래량 추세 기여도 (20%)
        vol_ma = df['volume'].iloc[max(0, i-20):i].mean()
        current_vol = df['volume'].iloc[i]
        vol_ratio = (current_vol / vol_ma * 50) if vol_ma > 0 else 50
        vol_score = min(100, max(0, vol_ratio))
        
        # 추세 강도 기여도 (20%)
        ma20 = df['ma20'].iloc[i]
        ma50 = df['ma50'].iloc[i]
        if not pd.isna(ma20) and not pd.isna(ma50) and ma50 != 0:
            trend_score = ((ma20 - ma50) / ma50 * 500) + 50
            trend_score = min(100, max(0, trend_score))
        else:
            trend_score = 50
        
        # 종합 점수
        fear_greed.iloc[i] = (rsi_score * 0.3 + bb_position * 0.3 + 
                             vol_score * 0.2 + trend_score * 0.2)
    
    return fear_greed

# 시장 위치 분석
def analyze_market_position(df):
    if df is None or df.empty:
        return "데이터 분석 오류", {}
    
    # 최신 데이터 가져오기
    latest = df.iloc[-1]
    
    # 지표 분석
    indicators = {}
    
    # 1. RSI 분석
    rsi = latest['rsi']
    if rsi > 70:
        rsi_signal = "과매수"
        rsi_score = -2  # 적극매도 방향
    elif rsi > 60:
        rsi_signal = "매수 우세"
        rsi_score = -1  # 매도 방향
    elif rsi < 30:
        rsi_signal = "과매도"
        rsi_score = 2  # 적극매수 방향
    elif rsi < 40:
        rsi_signal = "매도 우세"
        rsi_score = 1  # 매수 방향
    else:
        rsi_signal = "중립"
        rsi_score = 0  # 관망
    
    indicators["RSI"] = {
        "value": f"{rsi:.2f}",
        "signal": rsi_signal,
        "score": rsi_score
    }
    
    # 2. MACD 분석
    macd_val = latest['macd']
    macd_signal = latest['macd_signal']
    macd_hist = latest['macd_histogram']
    
    if macd_val > macd_signal and macd_hist > 0 and macd_hist > df['macd_histogram'].iloc[-2]:
        macd_signal_text = "강한 상승 추세"
        macd_score = 2  # 적극매수 방향
    elif macd_val > macd_signal and macd_hist > 0:
        macd_signal_text = "상승 추세"
        macd_score = 1  # 매수 방향
    elif macd_val < macd_signal and macd_hist < 0 and macd_hist < df['macd_histogram'].iloc[-2]:
        macd_signal_text = "강한 하락 추세"
        macd_score = -2  # 적극매도 방향
    elif macd_val < macd_signal and macd_hist < 0:
        macd_signal_text = "하락 추세"
        macd_score = -1  # 매도 방향
    else:
        macd_signal_text = "추세 전환 가능성"
        macd_score = 0  # 관망
    
    indicators["MACD"] = {
        "value": f"{macd_val:.2f}, 시그널: {macd_signal:.2f}, 히스토그램: {macd_hist:.2f}",
        "signal": macd_signal_text,
        "score": macd_score
    }
    
    # 3. 이동평균선 분석
    price = latest['close']
    ma20 = latest['ma20']
    ma50 = latest['ma50']
    ma200 = latest['ma200']
    
    ma_text = []
    if price > ma20 > ma50 > ma200:
        ma_signal = "강한 상승 추세 (황금 크로스)"
        ma_score = 2  # 적극매수 방향
        ma_text.append("가격 > 20일선 > 50일선 > 200일선 (완전 상승 배열)")
    elif price > ma20 and price > ma50 and price > ma200:
        ma_signal = "상승 추세"
        ma_score = 1  # 매수 방향
        ma_text.append("가격이 모든 이동평균선 위에 위치")
    elif price < ma20 < ma50 < ma200:
        ma_signal = "강한 하락 추세 (데드 크로스)"
        ma_score = -2  # 적극매도 방향
        ma_text.append("가격 < 20일선 < 50일선 < 200일선 (완전 하락 배열)")
    elif price < ma20 and price < ma50 and price < ma200:
        ma_signal = "하락 추세"
        ma_score = -1  # 매도 방향
        ma_text.append("가격이 모든 이동평균선 아래에 위치")
    else:
        ma_signal = "혼합된 추세"
        ma_score = 0  # 관망
        if price > ma200:
            ma_text.append("장기적 상승 추세 유지 (가격 > 200일선)")
        else:
            ma_text.append("장기적 하락 추세 (가격 < 200일선)")
    
    indicators["이동평균선"] = {
        "value": f"가격: {price:.2f}, 20일: {ma20:.2f}, 50일: {ma50:.2f}, 200일: {ma200:.2f}",
        "signal": ma_signal,
        "details": ", ".join(ma_text),
        "score": ma_score
    }
    
    # 4. 볼린저 밴드 분석
    bb_upper = latest['bb_upper']
    bb_middle = latest['bb_middle']
    bb_lower = latest['bb_lower']
    bb_width = latest['bb_width']
    
    # 밴드 내 위치 백분율 (0%: 하단, 50%: 중간, 100%: 상단)
    bb_position = ((price - bb_lower) / (bb_upper - bb_lower)) * 100 if (bb_upper - bb_lower) > 0 else 50
    
    if bb_position > 90:
        bb_signal = "강한 과매수 구간"
        bb_score = -2  # 적극매도 방향
    elif bb_position > 75:
        bb_signal = "과매수 구간 근접"
        bb_score = -1  # 매도 방향
    elif bb_position < 10:
        bb_signal = "강한 과매도 구간"
        bb_score = 2  # 적극매수 방향
    elif bb_position < 25:
        bb_signal = "과매도 구간 근접"
        bb_score = 1  # 매수 방향
    else:
        bb_signal = "중립 구간"
        bb_score = 0  # 관망
    
    indicators["볼린저 밴드"] = {
        "value": f"밴드 위치: {bb_position:.1f}%, 밴드폭: {bb_width:.4f}",
        "signal": bb_signal,
        "details": f"상단: {bb_upper:.2f}, 중간: {bb_middle:.2f}, 하단: {bb_lower:.2f}",
        "score": bb_score
    }
    
    # 5. 스토캐스틱 분석
    stoch_k = latest['stoch_k']
    stoch_d = latest['stoch_d']
    
    if stoch_k > 80 and stoch_d > 80:
        stoch_signal = "강한 과매수 구간"
        stoch_score = -2  # 적극매도 방향
    elif stoch_k > 70 and stoch_d > 70:
        stoch_signal = "과매수 구간"
        stoch_score = -1  # 매도 방향
    elif stoch_k < 20 and stoch_d < 20:
        stoch_signal = "강한 과매도 구간"
        stoch_score = 2  # 적극매수 방향
    elif stoch_k < 30 and stoch_d < 30:
        stoch_signal = "과매도 구간"
        stoch_score = 1  # 매수 방향
    elif stoch_k > stoch_d and stoch_k < 50:
        stoch_signal = "상승 반전 가능성"
        stoch_score = 0.5
    elif stoch_k < stoch_d and stoch_k > 50:
        stoch_signal = "하락 반전 가능성"
        stoch_score = -0.5
    else:
        stoch_signal = "중립 구간"
        stoch_score = 0
    
    indicators["스토캐스틱"] = {
        "value": f"%K: {stoch_k:.2f}, %D: {stoch_d:.2f}",
        "signal": stoch_signal,
        "score": stoch_score
    }
    
    # 6. EMA 추세 분석 (중장기 투자에 중요)
    ema12 = latest['ema12']
    ema26 = latest['ema26']
    ema50 = latest['ema50']
    ema100 = latest['ema100']
    
    ema_text = []
    if price > ema12 > ema26 > ema50 > ema100:
        ema_signal = "강한 상승 추세 (완벽한 정배열)"
        ema_score = 2
        ema_text.append("모든 지수이동평균선이 완벽한 상승 정배열")
    elif price > ema50 and ema50 > ema100:
        ema_signal = "중장기 상승 추세"
        ema_score = 1.5
        ema_text.append("중장기 지수이동평균선 상승 배열")
    elif price < ema12 < ema26 < ema50 < ema100:
        ema_signal = "강한 하락 추세 (완벽한 역배열)"
        ema_score = -2
        ema_text.append("모든 지수이동평균선이 완벽한 하락 역배열")
    elif price < ema50 and ema50 < ema100:
        ema_signal = "중장기 하락 추세"
        ema_score = -1.5
        ema_text.append("중장기 지수이동평균선 하락 배열")
    else:
        ema_signal = "횡보 또는 추세 전환 중"
        ema_score = 0
        ema_text.append("지수이동평균선이 혼재된 상태")
    
    indicators["EMA 추세"] = {
        "value": f"가격: {price:.2f}, 12일: {ema12:.2f}, 26일: {ema26:.2f}, 50일: {ema50:.2f}, 100일: {ema100:.2f}",
        "signal": ema_signal,
        "details": ", ".join(ema_text),
        "score": ema_score
    }
    
    # 7. 거래량 분석 (OBV)
    obv = latest['obv']
    obv_ma = latest['obv_ma']
    obv_prev = df['obv'].iloc[-2]
    
    if obv > obv_ma and obv > obv_prev:
        obv_signal = "강한 매수세 유입"
        obv_score = 1.5
    elif obv > obv_ma:
        obv_signal = "매수세 우세"
        obv_score = 1
    elif obv < obv_ma and obv < obv_prev:
        obv_signal = "강한 매도세 유입"
        obv_score = -1.5
    elif obv < obv_ma:
        obv_signal = "매도세 우세"
        obv_score = -1
    else:
        obv_signal = "거래량 중립"
        obv_score = 0
    
    indicators["거래량(OBV)"] = {
        "value": f"OBV: {obv:,.0f}, OBV MA: {obv_ma:,.0f}",
        "signal": obv_signal,
        "score": obv_score
    }
    
    # 8. 추세 강도 분석 (ADX)
    adx = latest['adx']
    adx_pos = latest['adx_pos']
    adx_neg = latest['adx_neg']
    
    if adx > 50:
        trend_strength = "매우 강한 추세"
    elif adx > 25:
        trend_strength = "강한 추세"
    elif adx > 20:
        trend_strength = "보통 추세"
    else:
        trend_strength = "약한 추세 (횡보)"
    
    if adx > 25 and adx_pos > adx_neg:
        adx_signal = f"{trend_strength} - 상승 방향"
        adx_score = 1.5 if adx > 40 else 1
    elif adx > 25 and adx_neg > adx_pos:
        adx_signal = f"{trend_strength} - 하락 방향"
        adx_score = -1.5 if adx > 40 else -1
    else:
        adx_signal = f"{trend_strength}"
        adx_score = 0
    
    indicators["추세강도(ADX)"] = {
        "value": f"ADX: {adx:.2f}, +DI: {adx_pos:.2f}, -DI: {adx_neg:.2f}",
        "signal": adx_signal,
        "score": adx_score
    }
    
    # 9. 일목균형표 분석 (중장기 투자의 핵심 지표)
    ichimoku_a = latest['ichimoku_a']
    ichimoku_b = latest['ichimoku_b']
    ichimoku_base = latest['ichimoku_base']
    ichimoku_conversion = latest['ichimoku_conversion']
    
    # 구름 위치 판단
    cloud_top = max(ichimoku_a, ichimoku_b) if not pd.isna(ichimoku_a) and not pd.isna(ichimoku_b) else price
    cloud_bottom = min(ichimoku_a, ichimoku_b) if not pd.isna(ichimoku_a) and not pd.isna(ichimoku_b) else price
    
    ichimoku_details = []
    if price > cloud_top:
        ichimoku_signal = "강한 상승 추세 (구름 위)"
        ichimoku_score = 2
        ichimoku_details.append("가격이 구름 위에 위치 - 강세장")
        if ichimoku_conversion > ichimoku_base:
            ichimoku_details.append("전환선이 기준선 위 - 추가 상승 여력")
    elif price > cloud_bottom and price < cloud_top:
        ichimoku_signal = "중립 구간 (구름 안)"
        ichimoku_score = 0
        ichimoku_details.append("가격이 구름 안에 위치 - 방향성 불확실")
    elif price < cloud_bottom:
        ichimoku_signal = "강한 하락 추세 (구름 아래)"
        ichimoku_score = -2
        ichimoku_details.append("가격이 구름 아래 위치 - 약세장")
        if ichimoku_conversion < ichimoku_base:
            ichimoku_details.append("전환선이 기준선 아래 - 추가 하락 가능")
    else:
        ichimoku_signal = "데이터 불충분"
        ichimoku_score = 0
        ichimoku_details.append("일목균형표 계산 중")
    
    indicators["일목균형표"] = {
        "value": f"구름 상단: {cloud_top:.2f}, 구름 하단: {cloud_bottom:.2f}",
        "signal": ichimoku_signal,
        "details": ", ".join(ichimoku_details),
        "score": ichimoku_score
    }
    
    # 10. 변동성 분석 (ATR)
    atr = latest['atr']
    atr_pct = (atr / price * 100) if price > 0 else 0
    
    if atr_pct > 5:
        volatility_signal = "매우 높은 변동성 (주의)"
        volatility_score = -0.5  # 중장기 투자자는 높은 변동성 주의
    elif atr_pct > 3:
        volatility_signal = "높은 변동성"
        volatility_score = -0.25
    elif atr_pct > 1.5:
        volatility_signal = "보통 변동성"
        volatility_score = 0
    else:
        volatility_signal = "낮은 변동성 (안정적)"
        volatility_score = 0.5
    
    indicators["변동성(ATR)"] = {
        "value": f"ATR: {atr:.2f} ({atr_pct:.2f}%)",
        "signal": volatility_signal,
        "score": volatility_score
    }
    
    # 11. 공포/탐욕 지수
    fear_greed = latest['fear_greed']
    
    if fear_greed >= 75:
        fg_signal = "극단적 탐욕 (매도 타이밍 주시)"
        fg_score = -2
    elif fear_greed >= 60:
        fg_signal = "탐욕 (차익실현 고려)"
        fg_score = -1
    elif fear_greed >= 40:
        fg_signal = "중립"
        fg_score = 0
    elif fear_greed >= 25:
        fg_signal = "공포 (매수 기회 포착)"
        fg_score = 1
    else:
        fg_signal = "극단적 공포 (적극 매수 기회)"
        fg_score = 2
    
    indicators["공포/탐욕지수"] = {
        "value": f"{fear_greed:.1f} / 100",
        "signal": fg_signal,
        "score": fg_score
    }
    
    # 12. 피보나치 레벨 분석
    fib_236 = latest['fib_236']
    fib_382 = latest['fib_382']
    fib_500 = latest['fib_500']
    fib_618 = latest['fib_618']
    
    fib_details = []
    if price > fib_236:
        fib_signal = "강세 구간 (23.6% 되돌림 위)"
        fib_score = 1
        fib_details.append("가격이 주요 되돌림 레벨 위에서 지지")
    elif price > fib_382:
        fib_signal = "중립 구간 (38.2% 되돌림 위)"
        fib_score = 0.5
        fib_details.append("38.2% 레벨에서 지지")
    elif price > fib_500:
        fib_signal = "약세 전환 구간 (50% 되돌림 위)"
        fib_score = 0
        fib_details.append("50% 되돌림 레벨 근처")
    elif price > fib_618:
        fib_signal = "약세 구간 (61.8% 되돌림 위)"
        fib_score = -0.5
        fib_details.append("61.8% 황금 되돌림 레벨 근처")
    else:
        fib_signal = "깊은 되돌림 구간 (매수 기회)"
        fib_score = 1
        fib_details.append("깊은 되돌림 - 반등 시 매수 기회")
    
    indicators["피보나치"] = {
        "value": f"23.6%: ${fib_236:.2f}, 38.2%: ${fib_382:.2f}, 50%: ${fib_500:.2f}, 61.8%: ${fib_618:.2f}",
        "signal": fib_signal,
        "details": ", ".join(fib_details),
        "score": fib_score
    }
    
    # 4년 주기 분석
    cycle_info = analyze_bitcoin_cycle()
    if cycle_info:
        indicators["4년 주기"] = {
            "value": f"{cycle_info['cycle_position_pct']:.1f}% 경과 ({cycle_info['days_since_halving']}일)",
            "signal": cycle_info['cycle_phase'],
            "score": cycle_info['phase_score'],
            "details": f"최근 반감기: {cycle_info['last_halving'].strftime('%Y-%m-%d')}"
        }
    
    # 고점 근접도 분석
    peak_info = analyze_peak_proximity(df, indicators)
    if peak_info:
        indicators["고점 근접도"] = {
            "value": f"{peak_info['peak_score']:.0f}/100점",
            "signal": peak_info['peak_status'],
            "score": -(peak_info['peak_score'] / 20),  # 0~100 -> 0~-5 점수로 변환 (고점 = 매도 신호)
            "details": f"52주고가: {peak_info['details']['52주 최고가 대비']}, 200일선: {peak_info['details']['200일선 괴리율']}"
        }
    
    # 종합 점수 계산 (가중치 적용)
    base_score = (
        rsi_score * 0.8 +           # RSI
        macd_score * 1.0 +          # MACD (중요)
        ma_score * 1.2 +            # 이동평균선 (매우 중요)
        bb_score * 0.8 +            # 볼린저밴드
        stoch_score * 0.6 +         # 스토캐스틱
        ema_score * 1.2 +           # EMA (중장기 투자에 중요)
        obv_score * 1.0 +           # 거래량
        adx_score * 0.8 +           # 추세 강도
        ichimoku_score * 1.5 +      # 일목균형표 (중장기 투자에 매우 중요)
        volatility_score * 0.5 +    # 변동성
        fg_score * 1.0 +            # 공포/탐욕 지수
        fib_score * 0.6             # 피보나치
    )
    
    # 사이클 및 고점 근접도 반영
    cycle_score = cycle_info['phase_score'] * 0.5 if cycle_info else 0  # 사이클 점수 가중치 낮춤 (2.0 → 0.5)
    peak_penalty = -(peak_info['peak_score'] / 10) if peak_info else 0  # 고점 근접 시 큰 감점
    
    total_score = base_score + cycle_score + peak_penalty
    
    # 점수 범위 정보 (참고용)
    # 최저: -15점 (모든 지표 극단적 매도)
    # 최고: +25점 (모든 지표 극단적 매수)
    # 중립: 0점 (지표들이 혼재)
    
    # 고점 근접 시 강제 매도 신호 (최우선 판단)
    # 고점 근접도가 매우 높으면 다른 지표와 무관하게 매도 권장
    if peak_info and peak_info['peak_score'] >= 80:
        final_position = "🔴 적극 매도 (고점 경고!)"
        position_category = "STRONG_SELL"
        recommendation = f"⚠️ 고점 근접도 {peak_info['peak_score']:.0f}점! 역사적으로 이런 과열 신호는 곧 조정이 옵니다. {peak_info['sell_recommendation']}"
        action = "즉시 분할 매도 시작 (보유 물량의 80-100%)"
    elif peak_info and peak_info['peak_score'] >= 60:
        final_position = "🔴 매도 (과열 경고)"
        position_category = "SELL"
        recommendation = f"⚠️ 고점 근접도 {peak_info['peak_score']:.0f}점! 심각한 과열 구간입니다. {peak_info['sell_recommendation']}"
        action = "적극 분할 매도 (보유 물량의 50-70%)"
    elif peak_info and peak_info['peak_score'] >= 40:
        # 고점 근접 시 매도 신호 강화
        if total_score > 0:  # 원래 매수 신호였어도
            final_position = "🟠 분할 매도 시작"
            position_category = "WEAK_SELL"
            recommendation = f"고점 근접도 {peak_info['peak_score']:.0f}점! 과열 구간 진입. {peak_info['sell_recommendation']}"
            action = "분할 매도 시작 (보유 물량의 30-50%)"
        else:
            final_position = "🟠 약한 매도"
            position_category = "WEAK_SELL"
            recommendation = f"고점 근접도 {peak_info['peak_score']:.0f}점! 과열 신호 감지. {peak_info['sell_recommendation']}"
            action = "분할 매도로 리스크 축소"
    # 일반적인 판단 (고점 근접도가 낮을 때)
    elif total_score >= 10:
        final_position = "🟢 적극 매수 (강력 추천)"
        position_category = "STRONG_BUY"
        recommendation = "대부분의 지표가 매우 강한 매수 신호를 보내고 있습니다. 중장기적으로 상승 추세가 명확하며, 적극적인 매수 진입을 권장합니다."
        action = "분할 매수 또는 일괄 매수 진행"
    elif total_score >= 6:
        final_position = "🟢 매수 (추천)"
        position_category = "BUY"
        recommendation = "다수의 지표가 매수 신호를 보내고 있습니다. 상승 추세가 형성되고 있으며, 매수 진입을 고려할 시점입니다."
        action = "분할 매수로 포지션 구축"
    elif total_score >= 3:
        final_position = "🟡 약한 매수 (신중)"
        position_category = "WEAK_BUY"
        recommendation = "일부 지표가 매수 신호를 보내고 있으나 확신이 부족합니다. 소량 매수 후 추가 신호 확인을 권장합니다."
        action = "소량 매수 후 관망, 추가 상승 시 증액"
    elif total_score >= 1:
        final_position = "⚪ 중립-매수 편향"
        position_category = "NEUTRAL_BUY"
        recommendation = "매수 신호가 약하게 감지됩니다. 명확한 추세 확인 후 진입하는 것이 안전합니다."
        action = "관망 우선, 강한 매수 신호 포착 시 진입"
    elif total_score >= -1:
        final_position = "⚪ 중립 (관망)"
        position_category = "NEUTRAL"
        recommendation = "혼합된 신호가 나타나고 있으며 방향성이 불확실합니다. 명확한 추세가 나타날 때까지 관망을 권장합니다."
        action = "현재 포지션 유지, 신규 진입 보류"
    elif total_score >= -3:
        final_position = "⚪ 중립-매도 편향"
        position_category = "NEUTRAL_SELL"
        recommendation = "매도 신호가 약하게 감지됩니다. 보유 중이라면 일부 차익실현을 고려할 수 있습니다."
        action = "일부 차익실현 고려, 손절매 라인 점검"
    elif total_score >= -6:
        final_position = "🟠 약한 매도"
        position_category = "WEAK_SELL"
        recommendation = "일부 지표가 매도 신호를 보내고 있습니다. 보유 중이라면 일부 매도를 고려하고, 신규 진입은 피해야 합니다."
        action = "분할 매도로 리스크 축소, 신규 매수 금지"
    elif total_score >= -10:
        final_position = "🔴 매도 (권장)"
        position_category = "SELL"
        recommendation = "다수의 지표가 매도 신호를 보내고 있습니다. 하락 추세가 형성되고 있으며, 보유 자산 매도를 권장합니다."
        action = "보유 중이라면 분할 매도 진행"
    else:
        final_position = "🔴 적극 매도 (강력 권장)"
        position_category = "STRONG_SELL"
        recommendation = "대부분의 지표가 매우 강한 매도 신호를 보내고 있습니다. 중장기적으로 하락 추세가 명확하며, 즉시 매도를 권장합니다."
        action = "보유 중이라면 즉시 매도, 추가 하락 대비"
    
    # 목표가 및 손절가 계산
    targets = calculate_price_targets(df, latest, position_category)
    
    return final_position, indicators, recommendation, total_score, action, targets, cycle_info, peak_info

# 고점 예측 함수 (각종 지표 기반)
def predict_peak_price(df, latest):
    """
    여러 기술 지표를 종합하여 예상 고점을 계산
    """
    price = latest['close']
    bb_upper = latest['bb_upper']
    
    # 1. 볼린저 밴드 확장 예측
    bb_width = latest['bb_upper'] - latest['bb_lower']
    bb_predicted_peak = bb_upper + (bb_width * 0.3)  # 밴드 폭의 30% 추가 상승 여력
    
    # 2. 52주 최고가 기반 예측
    high_52w = df['high'].tail(365).max()
    if price > high_52w * 0.95:  # 현재가가 52주 고점 근처라면
        peak_from_52w = high_52w * 1.05  # 5% 돌파 여력
    else:
        peak_from_52w = high_52w * 1.02  # 2% 돌파 여력
    
    # 3. 최근 추세선 연장 예측
    recent_highs = df['high'].tail(30)
    if len(recent_highs) >= 10:
        # 최근 30일 고점들의 상승 추세
        recent_max = recent_highs.max()
        # 현재가가 고점에 얼마나 가까운지에 따라
        price_to_recent_high = (price / recent_max) * 100
        if price_to_recent_high > 98:  # 고점 매우 근접
            trend_peak = recent_max * 1.15  # 돌파 시 15% 상승
        elif price_to_recent_high > 95:  # 고점 근접
            trend_peak = recent_max * 1.12  # 12% 상승
        else:
            trend_peak = recent_max * 1.08  # 8% 상승
    else:
        trend_peak = price * 1.12
    
    # 4. ATR 기반 변동성 예측
    atr = latest['atr']
    volatility_peak = price + (atr * 4)  # ATR의 4배 상승 여력 (3→4배로 증가)
    
    # 5. 200일 이동평균선 대비 과열도
    ma200 = latest['ma200']
    price_to_ma200 = (price / ma200 - 1) * 100
    
    if price_to_ma200 > 80:  # 극단적 괴리
        ma200_peak = price * 1.05  # 매우 제한적
    elif price_to_ma200 > 50:  # 심각한 괴리
        ma200_peak = price * 1.12  # 제한적 상승
    elif price_to_ma200 > 30:  # 높은 괴리
        ma200_peak = price * 1.20
    elif price_to_ma200 > 15:  # 보통 괴리
        ma200_peak = price * 1.30
    else:  # 낮은 괴리
        ma200_peak = price * 1.40  # 충분한 상승 여력
    
    # 6. RSI 기반 과열도 조정 (완화)
    rsi = latest['rsi']
    if rsi > 85:
        rsi_multiplier = 0.85  # 극단적 과열만 크게 하향
    elif rsi > 75:
        rsi_multiplier = 0.95  # 과열 구간 약간 하향
    elif rsi > 65:
        rsi_multiplier = 1.0   # 정상
    elif rsi > 50:
        rsi_multiplier = 1.05  # 약간 상향
    else:
        rsi_multiplier = 1.15  # RSI 여유 있으면 상향 조정
    
    # 모든 예측값의 가중 평균
    predicted_peak = (
        bb_predicted_peak * 0.20 +     # 볼린저 비중 축소
        peak_from_52w * 0.25 +         # 52주 고점 비중 증가
        trend_peak * 0.25 +            # 추세 비중 증가
        volatility_peak * 0.15 +       # 변동성 유지
        ma200_peak * 0.15              # 200일선 비중 축소 (너무 높게 나옴)
    ) * rsi_multiplier
    
    # 현실성 체크: 현재가의 최소 +5%, 최대 +80%
    min_peak = price * 1.05
    max_peak = price * 1.80
    predicted_peak = max(min_peak, min(predicted_peak, max_peak))
    
    return {
        'predicted_peak': predicted_peak,
        'bb_peak': bb_predicted_peak,
        'high_52w_peak': peak_from_52w,
        'trend_peak': trend_peak,
        'volatility_peak': volatility_peak,
        'ma200_peak': ma200_peak,
        'confidence': 'high' if rsi < 70 and price_to_ma200 < 30 else 'medium' if rsi < 80 else 'low'
    }

# 목표가 및 손절가 계산
def calculate_price_targets(df, latest, position_category):
    price = latest['close']
    atr = latest['atr']
    bb_upper = latest['bb_upper']
    bb_lower = latest['bb_lower']
    ma200 = latest['ma200']
    fib_236 = latest['fib_236']
    fib_618 = latest['fib_618']
    
    targets = {}
    
    if position_category in ["STRONG_BUY", "BUY"]:
        # 강력 매수 시나리오 - 공격적 목표가
        targets["entry_zone"] = f"${price * 0.97:.2f} - ${price * 1.03:.2f}"
        targets["target_1"] = f"${price * 1.15:.2f} (1차 목표 +15%)"
        targets["target_2"] = f"${price * 1.30:.2f} (2차 목표 +30%)"
        targets["target_3"] = f"${price * 1.50:.2f} (3차 목표 +50%)"
        targets["target_4"] = f"${price * 2.00:.2f} (최종 목표 +100%)"
        targets["stop_loss"] = f"${max(bb_lower, price * 0.88, ma200 * 0.95):.2f} (손절 -12%)"
        targets["risk_reward"] = "1:4.2 (고수익 전략)"
        
    elif position_category in ["WEAK_BUY", "NEUTRAL_BUY"]:
        # 약한 매수 시나리오 - 중간 공격적
        targets["entry_zone"] = f"${price * 0.97:.2f} - ${price * 1.03:.2f}"
        targets["target_1"] = f"${price * 1.10:.2f} (1차 목표 +10%)"
        targets["target_2"] = f"${price * 1.20:.2f} (2차 목표 +20%)"
        targets["target_3"] = f"${price * 1.35:.2f} (3차 목표 +35%)"
        targets["stop_loss"] = f"${max(bb_lower, price * 0.90, ma200 * 0.97):.2f} (손절 -10%)"
        targets["risk_reward"] = "1:3.5 (균형 전략)"
        
    elif position_category in ["STRONG_SELL", "SELL"]:
        # 강력 매도 시나리오 - 고점 예측 기반 분할 매도
        peak_prediction = predict_peak_price(df, latest)
        predicted_peak = peak_prediction['predicted_peak']
        confidence = peak_prediction['confidence']
        
        # 예상 고점 기준 분할 매도 구간 설정
        targets["predicted_peak"] = f"${predicted_peak:.2f} (예상 고점 - {confidence} 신뢰도)"
        targets["exit_stage_1"] = f"${price:.2f} (즉시 30% 매도 - 현재가)"
        targets["exit_stage_2"] = f"${(predicted_peak * 0.85):.2f} (추가 30% 매도 - 예상고점 85%)"
        targets["exit_stage_3"] = f"${(predicted_peak * 0.95):.2f} (추가 30% 매도 - 예상고점 95%)"
        targets["exit_stage_4"] = f"${predicted_peak:.2f} (최종 10% 매도 - 예상고점 도달)"
        
        # 기술 지표별 예상 고점 상세
        targets["indicator_peaks"] = (
            f"볼린저: ${peak_prediction['bb_peak']:.0f} | "
            f"52주고점: ${peak_prediction['high_52w_peak']:.0f} | "
            f"추세: ${peak_prediction['trend_peak']:.0f} | "
            f"변동성: ${peak_prediction['volatility_peak']:.0f}"
        )
        
        # 현재가 대비 예상 고점까지 상승 여력
        upside_potential = ((predicted_peak / price - 1) * 100)
        targets["upside_to_peak"] = f"+{upside_potential:.1f}% (현재가 → 예상 고점)"
        
        # 지지선 (하락 시)
        targets["support_1"] = f"${max(bb_lower, price * 0.88):.2f} (1차 지지선)"
        targets["support_2"] = f"${price * 0.80:.2f} (2차 지지선)"
        targets["support_3"] = f"${price * 0.70:.2f} (3차 지지선)"
        targets["reentry_zone"] = f"${min(fib_618, price * 0.70):.2f} 근처 (재진입 고려)"
        
    elif position_category in ["WEAK_SELL", "NEUTRAL_SELL"]:
        # 약한 매도 시나리오 - 고점 예측 기반
        peak_prediction = predict_peak_price(df, latest)
        predicted_peak = peak_prediction['predicted_peak']
        confidence = peak_prediction['confidence']
        
        # 예상 고점 기준 보수적 분할 매도
        targets["predicted_peak"] = f"${predicted_peak:.2f} (예상 고점 - {confidence} 신뢰도)"
        targets["exit_stage_1"] = f"${(predicted_peak * 0.90):.2f} (1차 매도 20% - 예상고점 90%)"
        targets["exit_stage_2"] = f"${(predicted_peak * 0.95):.2f} (2차 매도 30% - 예상고점 95%)"
        targets["exit_stage_3"] = f"${predicted_peak:.2f} (3차 매도 30% - 예상고점 도달)"
        targets["exit_stage_4"] = f"${(predicted_peak * 1.03):.2f} (최종 20% - 예상고점 초과 시)"
        
        # 상승 여력
        upside_potential = ((predicted_peak / price - 1) * 100)
        targets["upside_to_peak"] = f"+{upside_potential:.1f}% (현재가 → 예상 고점)"
        
        # 지지선
        targets["support_1"] = f"${max(bb_lower, price * 0.92):.2f} (1차 지지선)"
        targets["support_2"] = f"${price * 0.85:.2f} (2차 지지선)"
        targets["support_3"] = f"${price * 0.78:.2f} (3차 지지선)"
        targets["reentry_zone"] = f"${min(fib_618, price * 0.80):.2f} 근처 (재진입 고려)"
        
    else:
        # 중립 시나리오
        targets["current_range"] = f"${bb_lower:.2f} - ${bb_upper:.2f}"
        targets["watch_level_up"] = f"${bb_upper:.2f} 돌파 시 매수 신호"
        targets["watch_level_down"] = f"${bb_lower:.2f} 이탈 시 매도 신호"
        targets["key_support"] = f"${ma200:.2f} (200일 이평선)"
    
    return targets

# 지표 점수에 따른 색상 반환
def get_indicator_color(score):
    if score > 1:
        return "#1B5E20"  # 매우 긍정적
    elif score > 0:
        return "#4CAF50"  # 긍정적
    elif score < -1:
        return "#B71C1C"  # 매우 부정적
    elif score < 0:
        return "#F44336"  # 부정적
    else:
        return "#757575"  # 중립

# 간단한 지표 HTML 생성
def create_indicator_html(title, data, color):
    return f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 20px; border: 1px solid #f0f0f0; border-radius: 6px; overflow: hidden;">
                                    <tr>
                                        <td style="padding: 12px 15px; background-color: #f5f5f5; font-weight: bold; font-size: 16px; border-bottom: 1px solid #f0f0f0;">
                                            {title}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 15px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td width="70%" style="font-size: 14px; color: #555555; padding: 5px 0;">
                                                        현재 수치: <span style="font-family: 'Courier New', monospace; font-weight: bold;">{data.get('value', 'N/A')}</span>
                                                    </td>
                                                    <td width="30%" style="font-size: 14px; text-align: right; font-weight: bold; color: {color};">
                                                        {data.get('signal', 'N/A')}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
    """

# 상세 정보가 있는 지표 HTML 생성
def create_indicator_html_with_details(title, data, color):
    return f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 20px; border: 1px solid #f0f0f0; border-radius: 6px; overflow: hidden;">
                                    <tr>
                                        <td style="padding: 12px 15px; background-color: #f5f5f5; font-weight: bold; font-size: 16px; border-bottom: 1px solid #f0f0f0;">
                                            {title}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 15px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td style="font-size: 14px; color: #555555; padding: 5px 0;">
                                                        <span style="font-family: 'Courier New', monospace; font-weight: bold;">{data.get('value', 'N/A')}</span>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 14px; font-weight: bold; color: {color}; padding: 5px 0;">
                                                        {data.get('signal', 'N/A')}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 12px; color: #777777; padding: 5px 0; font-style: italic;">
                                                        {data.get('details', '')}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
    """

# HTML 이메일 형식으로 결과 포맷팅
def format_analysis_result_html(final_position, indicators, recommendation, price, date_str, action, targets, total_score, cycle_info, peak_info):
    # 색상 결정 (이모지 포함 문자열 처리)
    if "적극 매수" in final_position and "강력" in final_position:
        position_color = "#0D5E20"  # 매우 진한 녹색
    elif "매수" in final_position and "추천" in final_position:
        position_color = "#1B5E20"  # 진한 녹색
    elif "약한 매수" in final_position:
        position_color = "#4CAF50"  # 녹색
    elif "중립-매수" in final_position:
        position_color = "#7CB342"  # 연한 녹색
    elif "중립" in final_position and "매도" not in final_position and "매수" not in final_position:
        position_color = "#9E9E9E"  # 회색
    elif "중립-매도" in final_position:
        position_color = "#FF9800"  # 주황색
    elif "약한 매도" in final_position:
        position_color = "#FF5722"  # 진한 주황색
    elif "매도" in final_position and "권장" in final_position:
        position_color = "#F44336"  # 빨간색
    elif "적극 매도" in final_position:
        position_color = "#B71C1C"  # 매우 진한 빨간색
    else:
        position_color = "#757575"  # 기본 회색
    
    html = f"""
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"/>
        <title>비트코인 분석 리포트</title>
        <style type="text/css">
            /* 프린트 전용 스타일 */
            @media print {{
                /* 페이지 설정 */
                @page {{
                    size: A4;
                    margin: 1cm;
                }}
                
                /* 기본 스타일 */
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Malgun Gothic', '맑은 고딕', sans-serif;
                    font-size: 10pt;
                    line-height: 1.4;
                    color: #000;
                    background: #fff !important;
                }}
                
                /* 배경색 제거 */
                * {{
                    background: transparent !important;
                    box-shadow: none !important;
                }}
                
                /* 컨테이너 */
                table {{
                    width: 100% !important;
                    max-width: 100% !important;
                    border-collapse: collapse;
                }}
                
                /* 헤더 스타일 */
                .print-header {{
                    background: #0052cc !important;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                    color: #000 !important;
                    padding: 15px !important;
                    border: 2px solid #000 !important;
                    page-break-after: avoid;
                }}
                
                .print-header h1 {{
                    color: #000 !important;
                    font-size: 18pt !important;
                    margin: 0 !important;
                }}
                
                .print-header p {{
                    color: #333 !important;
                    font-size: 9pt !important;
                }}
                
                /* 가격 정보 */
                .price-box {{
                    border: 2px solid #000 !important;
                    padding: 10px !important;
                    text-align: center;
                    page-break-inside: avoid;
                }}
                
                .price-box p {{
                    font-size: 24pt !important;
                    font-weight: bold !important;
                    color: #000 !important;
                }}
                
                /* 투자 판단 박스 */
                .judgment-box {{
                    border: 3px solid #000 !important;
                    padding: 15px !important;
                    text-align: center;
                    margin: 10px 0 !important;
                    page-break-inside: avoid;
                }}
                
                .judgment-box p {{
                    font-size: 16pt !important;
                    font-weight: bold !important;
                    color: #000 !important;
                }}
                
                /* 섹션 제목 */
                h2 {{
                    font-size: 14pt !important;
                    color: #000 !important;
                    border-bottom: 2px solid #000 !important;
                    padding-bottom: 5px !important;
                    margin: 15px 0 10px 0 !important;
                    page-break-after: avoid;
                }}
                
                /* 표 스타일 */
                .data-table {{
                    border: 1px solid #000 !important;
                    margin: 10px 0 !important;
                    page-break-inside: avoid;
                }}
                
                .data-table td {{
                    border: 1px solid #666 !important;
                    padding: 8px !important;
                    font-size: 9pt !important;
                    color: #000 !important;
                }}
                
                .table-header {{
                    background: #ddd !important;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                    font-weight: bold !important;
                }}
                
                /* 4년 주기 및 고점 근접도 박스 */
                .warning-box {{
                    border: 2px solid #000 !important;
                    padding: 10px !important;
                    margin: 10px 0 !important;
                    page-break-inside: avoid;
                }}
                
                /* 경고 박스 */
                .alert-box {{
                    border: 3px double #000 !important;
                    padding: 10px !important;
                    margin: 10px 0 !important;
                    page-break-inside: avoid;
                }}
                
                /* 지표 카드 */
                .indicator-card {{
                    border: 1px solid #666 !important;
                    padding: 8px !important;
                    margin: 5px 0 !important;
                    page-break-inside: avoid;
                }}
                
                /* 유의사항 박스 */
                .notice-box {{
                    border: 1px dashed #666 !important;
                    padding: 10px !important;
                    margin: 15px 0 !important;
                    page-break-inside: avoid;
                }}
                
                .notice-box ul {{
                    margin: 5px 0 !important;
                    padding-left: 20px !important;
                }}
                
                .notice-box li {{
                    font-size: 8pt !important;
                    line-height: 1.4 !important;
                    color: #333 !important;
                }}
                
                /* 푸터 */
                .footer {{
                    border-top: 1px solid #000 !important;
                    padding: 10px !important;
                    text-align: center;
                    font-size: 8pt !important;
                    color: #666 !important;
                    page-break-before: avoid;
                }}
                
                /* 페이지 브레이크 제어 */
                .no-break {{
                    page-break-inside: avoid;
                }}
                
                .page-break {{
                    page-break-before: always;
                }}
                
                /* 불필요한 요소 숨김 */
                .no-print {{
                    display: none !important;
                }}
                
                /* 링크 URL 표시 */
                a[href]:after {{
                    content: none !important;
                }}
            }}
            
            /* 화면 표시용 스타일 */
            @media screen {{
                .print-only {{
                    display: none;
                }}
            }}
            
            /* 모바일 최적화 */
            @media screen and (max-width: 640px) {{
                /* 테이블을 100% 너비로 */
                .email-container {{
                    width: 100% !important;
                    min-width: 100% !important;
                }}
                
                /* 패딩 축소 */
                .mobile-padding {{
                    padding: 15px !important;
                }}
                
                .mobile-padding-small {{
                    padding: 10px !important;
                }}
                
                /* 폰트 크기 조정 */
                .mobile-text-large {{
                    font-size: 28px !important;
                }}
                
                .mobile-text-medium {{
                    font-size: 18px !important;
                }}
                
                .mobile-text-small {{
                    font-size: 12px !important;
                }}
                
                /* 가격 표시 */
                .mobile-price {{
                    font-size: 28px !important;
                }}
                
                /* 헤더 */
                .mobile-header {{
                    padding: 20px 15px !important;
                }}
                
                /* 두 열을 한 열로 */
                .mobile-full-width {{
                    width: 100% !important;
                    display: block !important;
                }}
            }}
        </style>
    </head>
    <body style="margin:0; padding:0; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', sans-serif;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f7f7f7;">
            <tr>
                <td class="mobile-padding-small" style="padding: 20px 0;">
                    <!-- 컨테이너 -->
                    <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" class="email-container" style="border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); max-width: 600px;">
                        <!-- 헤더 -->
                        <tr>
                            <td align="center" class="print-header mobile-header" style="padding: 30px 30px 20px 30px; background-color: #0052cc; border-radius: 8px 8px 0 0;">
                                <h1 class="mobile-text-medium" style="color: #ffffff; font-size: 24px; margin: 0 0 10px 0;">📈 비트코인(BTC) 중장기 투자 분석</h1>
                                <p class="mobile-text-small" style="color: #ffffff; opacity: 0.9; margin: 5px 0; font-size: 14px;">14개 핵심 지표 종합 분석 리포트</p>
                                <p class="mobile-text-small" style="color: #ffffff; opacity: 0.8; margin: 5px 0; font-size: 12px;">{date_str}</p>
                                <p class="mobile-text-small" style="color: #ffffff; opacity: 0.7; margin: 8px 0 0 0; font-size: 11px; background-color: rgba(255,255,255,0.1); padding: 6px 12px; border-radius: 15px; display: inline-block;">
                                    🔄 매일 오전 9시 (KST) 자동 업데이트
                                </p>
                            </td>
                        </tr>
                        
                        <!-- 가격 정보 -->
                        <tr>
                            <td style="padding: 0;">
                                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td align="center" class="price-box no-break mobile-padding" style="padding: 25px 30px; background: linear-gradient(135deg, #f5f9ff 0%, #ecf4ff 100%);">
                                            <p class="mobile-text-small" style="margin: 0; font-size: 14px; color: #0052cc; font-weight: bold;">분석 시점 가격</p>
                                            <p class="mobile-price" style="margin: 10px 0 0 0; font-size: 36px; font-weight: bold; color: #0d2a53;">
                                                ${price:,.2f}
                                            </p>
                                            <p class="mobile-text-small" style="margin: 8px 0 0 0; font-size: 11px; color: #666666; opacity: 0.8;">
                                                (데이터 수집: {date_str})
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- 투자 판단 -->
                        <tr>
                            <td style="padding: 0;">
                                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td align="center" class="mobile-padding" style="padding: 25px 30px; background-color: #ffffff; border-bottom: 1px solid #f0f0f0;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="90%" class="email-container">
                                                <tr>
                                                    <td align="center" class="judgment-box no-break mobile-padding-small" style="padding: 20px; border-radius: 12px; background-color: {position_color}; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                                                        <p class="mobile-text-medium" style="margin: 0; font-size: 26px; font-weight: bold; color: #ffffff;">
                                                            {final_position}
                                                        </p>
                                                        <p class="mobile-text-small" style="margin: 10px 0 0 0; font-size: 14px; color: #ffffff; opacity: 0.9;">
                                                            종합 점수: {total_score:.1f}점
                                                        </p>
                                                        <p class="mobile-text-small" style="margin: 5px 0 0 0; font-size: 11px; color: #ffffff; opacity: 0.75;">
                                                            (범위: -15점~+25점 | 중립: 0점 | 매수: +6점 이상 | 매도: -3점 이하)
                                                        </p>
                                                    </td>
                                                </tr>
                                            </table>
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top: 20px;">
                                                <tr>
                                                    <td class="mobile-padding-small" style="padding: 15px; background-color: #f9f9f9; border-left: 4px solid {position_color}; border-radius: 4px;">
                                                        <p class="mobile-text-small" style="margin: 0; font-size: 14px; line-height: 1.6; color: #333333;">
                                                            <strong>💡 투자 판단:</strong> {recommendation}
                                                        </p>
                                                    </td>
                                                </tr>
                                            </table>
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top: 15px;">
                                                <tr>
                                                    <td class="mobile-padding-small" style="padding: 15px; background-color: #E3F2FD; border-left: 4px solid #2196F3; border-radius: 4px;">
                                                        <p class="mobile-text-small" style="margin: 0; font-size: 14px; line-height: 1.6; color: #333333;">
                                                            <strong>🎯 권장 행동:</strong> {action}
                                                        </p>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- 핵심 분석: 고점 근접도 (메인) + 4년 주기 (참고) -->
                        <tr class="page-break">
                            <td class="mobile-padding" style="padding: 25px 30px; background-color: #ffffff;">
                                <h2 class="mobile-text-medium" style="color: #D32F2F; font-size: 24px; margin: 0 0 25px 0; padding-bottom: 12px; border-bottom: 3px solid #F44336;">
                                    📊 핵심 분석: 고점 근접도 (12개 지표 종합)
                                </h2>
    """
    
    # 고점 근접도 정보 (메인 - 먼저 표시)
    if peak_info:
        peak_score = peak_info['peak_score']
        if peak_score >= 80:
            peak_bg_color = "#FFEBEE"
            peak_border_color = "#B71C1C"
        elif peak_score >= 60:
            peak_bg_color = "#FFF3E0"
            peak_border_color = "#E65100"
        elif peak_score >= 40:
            peak_bg_color = "#FFF9C4"
            peak_border_color = "#F57F17"
        else:
            peak_bg_color = "#E8F5E9"
            peak_border_color = "#2E7D32"
        
        html += f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" class="alert-box no-break" style="margin-bottom: 20px; background-color: {peak_bg_color}; border-radius: 8px; border: 3px solid {peak_border_color};">
                                    <tr>
                                        <td style="padding: 20px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td style="font-size: 18px; font-weight: bold; color: {peak_border_color}; padding-bottom: 10px;">
                                                        ⚠️ 고점 근접도: {peak_score:.0f}/100점
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 16px; font-weight: bold; color: {peak_border_color}; padding: 10px 0;">
                                                        {peak_info['peak_status']}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 15px; color: #333333; padding: 10px 0; background-color: rgba(255,255,255,0.7); border-radius: 6px; padding: 15px;">
                                                        <strong>🎯 매도 권장사항:</strong> {peak_info['sell_recommendation']}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 15px;">
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tr>
                                                                <td style="font-size: 13px; color: #666666; padding: 3px 0;">
                                                                    📈 {peak_info['details']['52주 최고가 대비']}
                                                                </td>
                                                            </tr>
                                                            <tr>
                                                                <td style="font-size: 13px; color: #666666; padding: 3px 0;">
                                                                    📊 {peak_info['details']['200일선 괴리율']}
                                                                </td>
                                                            </tr>
                                                            <tr>
                                                                <td style="font-size: 13px; color: #666666; padding: 3px 0;">
                                                                    🔥 RSI 과열: {peak_info['details']['RSI 과열 일수']}
                                                                </td>
                                                            </tr>
                                                            <tr>
                                                                <td style="font-size: 13px; color: #666666; padding: 3px 0;">
                                                                    📍 볼린저 상단: {peak_info['details']['볼린저 상단 체류']}
                                                                </td>
                                                            </tr>
                                                            <tr>
                                                                <td style="font-size: 13px; color: #666666; padding: 3px 0;">
                                                                    💹 거래량: {peak_info['details']['거래량 배수']}
                                                                </td>
                                                            </tr>
                                                        </table>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
        """
    
    # 4년 주기 정보 (보조 정보 - 나중에 간략하게 표시)
    if cycle_info:
        cycle_color = "#757575" if cycle_info['phase_score'] > 0 else "#9E9E9E"
        days_since = cycle_info['days_since_halving']
        cycle_pct = cycle_info['cycle_position_pct']
        
        html += f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 15px; background-color: #F5F5F5; border-radius: 6px; border-left: 3px solid {cycle_color};">
                                    <tr>
                                        <td style="padding: 12px 15px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td style="font-size: 13px; font-weight: bold; color: #555555; padding-bottom: 8px;">
                                                        🔄 4년 주기 참고: {cycle_info['cycle_phase']}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 12px; color: #777777; padding: 2px 0;">
                                                        최근 반감기 {cycle_info['last_halving'].strftime('%Y.%m.%d')} ({days_since}일 경과) | 진행률 {cycle_pct:.1f}%
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 8px 0 0 0;">
                                                        <div style="width: 100%; height: 20px; background-color: #E0E0E0; border-radius: 10px; overflow: hidden;">
                                                            <div style="width: {min(100, cycle_pct):.1f}%; height: 100%; background: linear-gradient(90deg, #9E9E9E 0%, #757575 100%); display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; color: #ffffff; font-weight: bold; font-size: 10px;">
                                                                {cycle_pct:.1f}%
                                                            </div>
                                                        </div>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- 가격 목표 및 전략 -->
                        <tr>
                            <td class="mobile-padding" style="padding: 25px 30px; background-color: #f9f9f9;">
                                <h2 class="mobile-text-medium" style="color: #333333; font-size: 20px; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #e0e0e0;">
                                    📊 가격 목표 및 전략
                                </h2>
    """
    
    # 가격 목표 표시
    for key, value in targets.items():
        key_display = key.replace("_", " ").title()
        key_emoji = "🎯" if "target" in key else "🛡️" if "stop" in key else "📍" if "entry" in key or "exit" in key else "📉" if "support" in key else "👀" if "watch" in key else "🔄" if "reentry" in key else "📊"
        
        html += f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 12px;">
                                    <tr>
                                        <td style="padding: 12px 15px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td width="40%" style="font-size: 13px; color: #666666; font-weight: 600;">
                                                        {key_emoji} {key_display.replace("_", " ")}
                                                    </td>
                                                    <td width="60%" style="font-size: 14px; color: #333333; font-weight: bold; text-align: right;">
                                                        {value}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
        """
    
    html += """
                            </td>
                        </tr>
                        
                        <!-- 지표 분석 -->
                        <tr>
                            <td class="mobile-padding" style="padding: 25px 30px;">
                                <h2 class="mobile-text-medium" style="color: #333333; font-size: 20px; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0;">
                                    지표별 분석
                                </h2>
    """
    
    # RSI 지표
    rsi_data = indicators.get("RSI", {})
    if rsi_data:
        rsi_score = rsi_data.get('score', 0)
        rsi_color = "#757575"  # 기본 회색
        if rsi_score > 1:
            rsi_color = "#1B5E20"  # 매우 긍정적
        elif rsi_score > 0:
            rsi_color = "#4CAF50"  # 긍정적
        elif rsi_score < -1:
            rsi_color = "#B71C1C"  # 매우 부정적
        elif rsi_score < 0:
            rsi_color = "#F44336"  # 부정적
            
        html += f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 20px; border: 1px solid #f0f0f0; border-radius: 6px; overflow: hidden;">
                                    <tr>
                                        <td style="padding: 12px 15px; background-color: #f5f5f5; font-weight: bold; font-size: 16px; border-bottom: 1px solid #f0f0f0;">
                                            RSI (상대강도지수)
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 15px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td width="70%" style="font-size: 14px; color: #555555; padding: 5px 0;">
                                                        현재 수치: <span style="font-family: 'Courier New', monospace; font-weight: bold;">{rsi_data.get('value', 'N/A')}</span>
                                                    </td>
                                                    <td width="30%" style="font-size: 14px; text-align: right; font-weight: bold; color: {rsi_color};">
                                                        {rsi_data.get('signal', 'N/A')}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
        """
    
    # MACD 지표
    macd_data = indicators.get("MACD", {})
    if macd_data:
        macd_score = macd_data.get('score', 0)
        macd_color = "#757575"  # 기본 회색
        if macd_score > 1:
            macd_color = "#1B5E20"  # 매우 긍정적
        elif macd_score > 0:
            macd_color = "#4CAF50"  # 긍정적
        elif macd_score < -1:
            macd_color = "#B71C1C"  # 매우 부정적
        elif macd_score < 0:
            macd_color = "#F44336"  # 부정적
            
        html += f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 20px; border: 1px solid #f0f0f0; border-radius: 6px; overflow: hidden;">
                                    <tr>
                                        <td style="padding: 12px 15px; background-color: #f5f5f5; font-weight: bold; font-size: 16px; border-bottom: 1px solid #f0f0f0;">
                                            MACD (이동평균수렴확산지수)
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 15px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td width="70%" style="font-size: 14px; color: #555555; padding: 5px 0;">
                                                        현재 수치: <span style="font-family: 'Courier New', monospace; font-weight: bold;">{macd_data.get('value', 'N/A')}</span>
                                                    </td>
                                                    <td width="30%" style="font-size: 14px; text-align: right; font-weight: bold; color: {macd_color};">
                                                        {macd_data.get('signal', 'N/A')}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
        """
    
    # 이동평균선 지표
    ma_data = indicators.get("이동평균선", {})
    if ma_data:
        ma_score = ma_data.get('score', 0)
        ma_color = "#757575"  # 기본 회색
        if ma_score > 1:
            ma_color = "#1B5E20"  # 매우 긍정적
        elif ma_score > 0:
            ma_color = "#4CAF50"  # 긍정적
        elif ma_score < -1:
            ma_color = "#B71C1C"  # 매우 부정적
        elif ma_score < 0:
            ma_color = "#F44336"  # 부정적
            
        html += f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 20px; border: 1px solid #f0f0f0; border-radius: 6px; overflow: hidden;">
                                    <tr>
                                        <td style="padding: 12px 15px; background-color: #f5f5f5; font-weight: bold; font-size: 16px; border-bottom: 1px solid #f0f0f0;">
                                            이동평균선
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 15px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td style="font-size: 14px; color: #555555; padding: 5px 0;">
                                                        <span style="font-family: 'Courier New', monospace; font-weight: bold;">{ma_data.get('value', 'N/A')}</span>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 14px; font-weight: bold; color: {ma_color}; padding: 5px 0;">
                                                        {ma_data.get('signal', 'N/A')}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 12px; color: #777777; padding: 5px 0; font-style: italic;">
                                                        {ma_data.get('details', '')}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
        """
    
    # 볼린저 밴드 지표
    bb_data = indicators.get("볼린저 밴드", {})
    if bb_data:
        bb_score = bb_data.get('score', 0)
        bb_color = "#757575"  # 기본 회색
        if bb_score > 1:
            bb_color = "#1B5E20"  # 매우 긍정적
        elif bb_score > 0:
            bb_color = "#4CAF50"  # 긍정적
        elif bb_score < -1:
            bb_color = "#B71C1C"  # 매우 부정적
        elif bb_score < 0:
            bb_color = "#F44336"  # 부정적
            
        html += f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 20px; border: 1px solid #f0f0f0; border-radius: 6px; overflow: hidden;">
                                    <tr>
                                        <td style="padding: 12px 15px; background-color: #f5f5f5; font-weight: bold; font-size: 16px; border-bottom: 1px solid #f0f0f0;">
                                            볼린저 밴드
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 15px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td style="font-size: 14px; color: #555555; padding: 5px 0;">
                                                        <span style="font-family: 'Courier New', monospace; font-weight: bold;">{bb_data.get('value', 'N/A')}</span>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 14px; font-weight: bold; color: {bb_color}; padding: 5px 0;">
                                                        {bb_data.get('signal', 'N/A')}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="font-size: 12px; color: #777777; padding: 5px 0; font-style: italic;">
                                                        {bb_data.get('details', '')}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
        """
    
    # 스토캐스틱 지표
    stoch_data = indicators.get("스토캐스틱", {})
    if stoch_data:
        stoch_score = stoch_data.get('score', 0)
        stoch_color = "#757575"  # 기본 회색
        if stoch_score > 1:
            stoch_color = "#1B5E20"  # 매우 긍정적
        elif stoch_score > 0:
            stoch_color = "#4CAF50"  # 긍정적
        elif stoch_score < -1:
            stoch_color = "#B71C1C"  # 매우 부정적
        elif stoch_score < 0:
            stoch_color = "#F44336"  # 부정적
            
        html += f"""
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 20px; border: 1px solid #f0f0f0; border-radius: 6px; overflow: hidden;">
                                    <tr>
                                        <td style="padding: 12px 15px; background-color: #f5f5f5; font-weight: bold; font-size: 16px; border-bottom: 1px solid #f0f0f0;">
                                            스토캐스틱 오실레이터
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 15px;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                <tr>
                                                    <td width="70%" style="font-size: 14px; color: #555555; padding: 5px 0;">
                                                        현재 수치: <span style="font-family: 'Courier New', monospace; font-weight: bold;">{stoch_data.get('value', 'N/A')}</span>
                                                    </td>
                                                    <td width="30%" style="font-size: 14px; text-align: right; font-weight: bold; color: {stoch_color};">
                                                        {stoch_data.get('signal', 'N/A')}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
        """
    
    # 새로운 지표들 추가
    
    # EMA 추세 지표
    ema_data = indicators.get("EMA 추세", {})
    if ema_data:
        ema_score = ema_data.get('score', 0)
        ema_color = get_indicator_color(ema_score)
        html += create_indicator_html("EMA 추세 (지수이동평균)", ema_data, ema_color)
    
    # 거래량(OBV) 지표
    obv_data = indicators.get("거래량(OBV)", {})
    if obv_data:
        obv_score = obv_data.get('score', 0)
        obv_color = get_indicator_color(obv_score)
        html += create_indicator_html("거래량 분석 (OBV)", obv_data, obv_color)
    
    # 추세강도(ADX) 지표
    adx_data = indicators.get("추세강도(ADX)", {})
    if adx_data:
        adx_score = adx_data.get('score', 0)
        adx_color = get_indicator_color(adx_score)
        html += create_indicator_html("추세 강도 (ADX)", adx_data, adx_color)
    
    # 일목균형표 지표
    ichimoku_data = indicators.get("일목균형표", {})
    if ichimoku_data:
        ichimoku_score = ichimoku_data.get('score', 0)
        ichimoku_color = get_indicator_color(ichimoku_score)
        html += create_indicator_html_with_details("일목균형표 (Ichimoku Cloud)", ichimoku_data, ichimoku_color)
    
    # 변동성(ATR) 지표
    atr_data = indicators.get("변동성(ATR)", {})
    if atr_data:
        atr_score = atr_data.get('score', 0)
        atr_color = get_indicator_color(atr_score)
        html += create_indicator_html("변동성 (ATR)", atr_data, atr_color)
    
    # 공포/탐욕 지수
    fg_data = indicators.get("공포/탐욕지수", {})
    if fg_data:
        fg_score = fg_data.get('score', 0)
        fg_color = get_indicator_color(fg_score)
        html += create_indicator_html("공포/탐욕 지수", fg_data, fg_color)
    
    # 피보나치 레벨
    fib_data = indicators.get("피보나치", {})
    if fib_data:
        fib_score = fib_data.get('score', 0)
        fib_color = get_indicator_color(fib_score)
        html += create_indicator_html_with_details("피보나치 되돌림", fib_data, fib_color)
    
    # 투자자 유의사항 및 푸터
    html += f"""
                                <!-- 투자자 유의사항 -->
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" class="notice-box no-break" style="margin-top: 10px; background-color: #FFFDE7; border-radius: 6px; border-left: 3px solid #FFC107;">
                                    <tr>
                                        <td style="padding: 15px;">
                                            <h3 style="margin: 0 0 10px 0; color: #555555; font-size: 16px;">⚠️ 중장기 투자자를 위한 유의사항</h3>
                                            <ul style="margin: 0; padding-left: 20px; color: #555555; font-size: 13px; line-height: 1.6;">
                                                <li><strong>기술적 분석은 참고 자료:</strong> 모든 투자 판단의 결과는 본인 책임이며, 이 분석은 참고용으로만 활용하세요.</li>
                                                <li><strong>중장기 관점 유지:</strong> 일일 변동성에 흔들리지 말고, 주요 추세와 지지/저항선을 중심으로 판단하세요.</li>
                                                <li><strong>분할 매수/매도 전략:</strong> 한 번에 전량 매수/매도하지 말고, 여러 차례 나누어 진행하세요.</li>
                                                <li><strong>손절매 라인 준수:</strong> 손실을 제한하기 위해 사전에 정한 손절매 라인을 반드시 지키세요.</li>
                                                <li><strong>강한 추세의 특징:</strong> 과매수/과매도 구간이 장기간 유지될 수 있으므로, 추세의 방향성을 함께 고려하세요.</li>
                                                <li><strong>리스크 관리:</strong> 투자금은 손실을 감당할 수 있는 범위 내에서만 운용하세요.</li>
                                            </ul>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- 푸터 -->
                        <tr>
                            <td class="footer" style="padding: 20px 30px; background-color: #f5f5f5; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #777777; border-top: 1px solid #eeeeee;">
                                <p style="margin: 0;">© 9min 비트코인 기술적 분석 리포트</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    return html

# 이메일 전송 함수
def send_email(analysis_html):
    try:
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 이메일 전송 시작...")
        
        # 이메일 기본 설정
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'📊 비트코인 중장기 투자 분석 리포트 ({get_kst_now().strftime("%Y-%m-%d")})'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL
        
        # 일반 텍스트 버전 추가 (스팸 필터 우회에 도움)
        text_content = "비트코인 기술적 분석 리포트입니다. HTML을 지원하는 이메일 클라이언트에서 확인해주세요."
        part1 = MIMEText(text_content, 'plain')
        msg.attach(part1)
        
        # HTML 내용 추가
        part2 = MIMEText(analysis_html, 'html')
        msg.attach(part2)
        
        # 이메일 서버 연결 및 전송
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(0)  # 디버그 정보 출력 비활성화
        
        server.starttls()  # TLS 연결 시작
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 이메일 전송 완료: {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 이메일 인증 오류")
        return False
    except smtplib.SMTPException as e:
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] SMTP 오류")
        return False
    except Exception as e:
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 이메일 전송 실패")
        return False

# 메인 분석 및 이메일 전송 함수
def analyze_and_send():
    print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 비트코인 분석 시작...")
    
    # 데이터 가져오기
    df = get_bitcoin_data()
    if df is None or df.empty:
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 데이터를 가져올 수 없습니다.")
        return
    
    # 기술적 지표 계산
    df = calculate_indicators(df)
    
    # 현재 가격
    current_price = df['close'].iloc[-1]
    
    # 시장 위치 분석
    final_position, indicators, recommendation, score, action, targets, cycle_info, peak_info = analyze_market_position(df)
    
    # 현재 날짜/시간 (한국 시간)
    date_str = get_kst_now().strftime("%Y-%m-%d %H:%M:%S KST")
    
    # 분석 결과 HTML 형식으로 포맷팅
    analysis_html = format_analysis_result_html(final_position, indicators, recommendation, current_price, date_str, action, targets, score, cycle_info, peak_info)
    
    # 콘솔 출력용 텍스트 (이모지 제거)
    position_text = final_position.replace("🟢", "").replace("🟡", "").replace("⚪", "").replace("🟠", "").replace("🔴", "").strip()
    
    print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 비트코인 분석 완료")
    print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 투자 판단: {position_text} (점수: {score:.1f})")
    if cycle_info:
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 4년 주기: {cycle_info['cycle_phase']} ({cycle_info['cycle_position_pct']:.1f}%)")
    if peak_info:
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 고점 근접도: {peak_info['peak_score']:.0f}/100 - {peak_info['sell_recommendation']}")
    
    # 고점 예측 정보 출력 (매도 신호일 때)
    if 'predicted_peak' in targets:
        print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 예상 고점: {targets['predicted_peak']}")
        if 'upside_to_peak' in targets:
            print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 상승 여력: {targets['upside_to_peak']}")
    
    print(f"[{get_kst_now().strftime('%Y-%m-%d %H:%M:%S')}] 권장 행동: {action}")
    
    # 이메일 전송
    send_email(analysis_html)

if __name__ == "__main__":
    # 비트코인 분석 및 이메일 전송 실행
    analyze_and_send()