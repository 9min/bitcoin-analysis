import ccxt
import pandas as pd
import numpy as np
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# 설정 정보
EMAIL_ADDRESS = "gm870711@gmail.com"  # 발신자 이메일
EMAIL_PASSWORD = "riqntklboduwdnoz"  # 앱 비밀번호 (Gmail의 경우 앱 비밀번호 필요)
RECIPIENT_EMAIL = "gm0711@kakao.com"  # 수신자 이메일

# Gmail SMTP 서버 설정
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # TLS 포트 사용 (기존 SSL 465 대신)

# 비트코인 데이터 가져오기
def get_bitcoin_data():
    try:
        # Binance API 사용 (다른 거래소도 선택 가능)
        exchange = ccxt.binance()
        
        # 일봉 데이터 가져오기 (최근 250일 데이터)
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1d', limit=250)
        
        # DataFrame으로 변환
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
    except Exception as e:
        print(f"데이터 가져오기 오류: {e}")
        return None

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
    
    # 4. 볼린저 밴드
    bollinger = ta.volatility.BollingerBands(df['close'])
    df['bb_upper'] = bollinger.bollinger_hband()
    df['bb_middle'] = bollinger.bollinger_mavg()
    df['bb_lower'] = bollinger.bollinger_lband()
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    # 5. 스토캐스틱 오실레이터
    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()
    
    return df

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
    
    # 종합 점수 계산
    total_score = rsi_score + macd_score + ma_score + bb_score + stoch_score
    
    # 최종 투자 판단
    if total_score >= 4:
        final_position = "적극매수"
        recommendation = "대부분의 지표가 강한 매수 신호를 보내고 있습니다. 적극매수 구간으로 판단됩니다."
    elif total_score >= 2:
        final_position = "매수"
        recommendation = "여러 지표가 매수 신호를 보내고 있습니다. 매수 구간으로 판단됩니다."
    elif total_score <= -4:
        final_position = "적극매도"
        recommendation = "대부분의 지표가 강한 매도 신호를 보내고 있습니다. 적극매도 구간으로 판단됩니다."
    elif total_score <= -2:
        final_position = "매도"
        recommendation = "여러 지표가 매도 신호를 보내고 있습니다. 매도 구간으로 판단됩니다."
    else:
        final_position = "관망"
        recommendation = "혼합된 신호가 보이거나 중립적인 지표가 많습니다. 관망하며 추세 변화를 지켜보는 것이 좋습니다."
    
    return final_position, indicators, recommendation, total_score

# HTML 이메일 형식으로 결과 포맷팅
def format_analysis_result_html(final_position, indicators, recommendation, price, date_str):
    position_colors = {
        "적극매수": "#1B5E20",  # 진한 녹색
        "매수": "#4CAF50",      # 녹색
        "관망": "#FFC107",      # 노란색
        "매도": "#F44336",      # 빨간색
        "적극매도": "#B71C1C"   # 진한 빨간색
    }
    
    position_color = position_colors.get(final_position, "#757575")
    
    # 표시할 심볼 결정
    position_symbol = "↑↑"  # 기본값
    if final_position == "적극매수":
        position_symbol = "↑↑"
    elif final_position == "매수":
        position_symbol = "↑"
    elif final_position == "관망":
        position_symbol = "↔"
    elif final_position == "매도":
        position_symbol = "↓"
    elif final_position == "적극매도":
        position_symbol = "↓↓"
    
    html = f"""
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>비트코인 분석 리포트</title>
    </head>
    <body style="margin:0; padding:0; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', sans-serif;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f7f7f7;">
            <tr>
                <td style="padding: 20px 0;">
                    <!-- 컨테이너 -->
                    <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                        <!-- 헤더 -->
                        <tr>
                            <td align="center" style="padding: 30px 30px 20px 30px; background-color: #0052cc; border-radius: 8px 8px 0 0;">
                                <h1 style="color: #ffffff; font-size: 24px; margin: 0 0 10px 0;">비트코인(BTC) 기술적 분석 리포트</h1>
                                <p style="color: #ffffff; opacity: 0.8; margin: 5px 0;">{date_str}</p>
                            </td>
                        </tr>
                        
                        <!-- 가격 정보 -->
                        <tr>
                            <td style="padding: 0;">
                                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td align="center" style="padding: 25px 30px; background: linear-gradient(135deg, #f5f9ff 0%, #ecf4ff 100%);">
                                            <p style="margin: 0; font-size: 14px; color: #0052cc; font-weight: bold;">현재 가격</p>
                                            <p style="margin: 10px 0 0 0; font-size: 36px; font-weight: bold; color: #0d2a53;">
                                                ${price:,.2f}
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
                                        <td align="center" style="padding: 25px 30px; background-color: #ffffff; border-bottom: 1px solid #f0f0f0;">
                                            <table border="0" cellpadding="0" cellspacing="0" width="80%">
                                                <tr>
                                                    <td align="center" style="padding: 15px; border-radius: 50px; background-color: {position_color};">
                                                        <p style="margin: 0; font-size: 22px; font-weight: bold; color: #ffffff;">
                                                            {position_symbol} {final_position} {position_symbol}
                                                        </p>
                                                    </td>
                                                </tr>
                                            </table>
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top: 20px;">
                                                <tr>
                                                    <td style="padding: 15px; background-color: #f9f9f9; border-left: 4px solid {position_color}; border-radius: 4px;">
                                                        <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #333333;">
                                                            <strong>투자 판단 요약:</strong> {recommendation}
                                                        </p>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- 지표 분석 -->
                        <tr>
                            <td style="padding: 25px 30px;">
                                <h2 style="color: #333333; font-size: 20px; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0;">
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
    
    # 투자자 유의사항 및 푸터
    html += f"""
                                <!-- 투자자 유의사항 -->
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top: 10px; background-color: #FFFDE7; border-radius: 6px; border-left: 3px solid #FFC107;">
                                    <tr>
                                        <td style="padding: 15px;">
                                            <h3 style="margin: 0 0 10px 0; color: #555555; font-size: 16px;">투자자 유의사항</h3>
                                            <ul style="margin: 0; padding-left: 20px; color: #555555; font-size: 13px; line-height: 1.6;">
                                                <li>모든 기술적 분석은 참고용이며, 투자의 결과는 본인 책임임을 명심하세요.</li>
                                                <li>과매수/과매도 구간이 반드시 즉각적인 가격 반전을 의미하지는 않습니다.</li>
                                                <li>강한 추세에서는 지표가 과매수/과매도 상태로 장기간 유지될 수 있습니다.</li>
                                                <li>투자금은 감당할 수 있는 범위 내에서 운용하세요.</li>
                                            </ul>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- 푸터 -->
                        <tr>
                            <td style="padding: 20px 30px; background-color: #f5f5f5; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #777777; border-top: 1px solid #eeeeee;">
                                <p style="margin: 0;">© 2024 비트코인 기술적 분석 리포트</p>
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
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 이메일 전송 시작...")
        
        # 이메일 기본 설정
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'비트코인 일일 기술적 분석 리포트 ({datetime.now().strftime("%Y-%m-%d")})'
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
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 이메일 전송 완료: {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 이메일 인증 오류")
        return False
    except smtplib.SMTPException as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SMTP 오류")
        return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 이메일 전송 실패")
        return False

# 메인 분석 및 이메일 전송 함수
def analyze_and_send():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 비트코인 분석 시작...")
    
    # 데이터 가져오기
    df = get_bitcoin_data()
    if df is None or df.empty:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 데이터를 가져올 수 없습니다.")
        return
    
    # 기술적 지표 계산
    df = calculate_indicators(df)
    
    # 현재 가격
    current_price = df['close'].iloc[-1]
    
    # 시장 위치 분석
    final_position, indicators, recommendation, score = analyze_market_position(df)
    
    # 현재 날짜/시간
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 분석 결과 HTML 형식으로 포맷팅
    analysis_html = format_analysis_result_html(final_position, indicators, recommendation, current_price, date_str)
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 비트코인 분석 완료")
    
    # 이메일 전송
    send_email(analysis_html)

if __name__ == "__main__":
    # 비트코인 분석 및 이메일 전송 실행
    analyze_and_send()