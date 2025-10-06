"""
GitHub Actions용 HTML 생성 스크립트

이 스크립트는 GitHub Actions에서 실행되어
index.html 파일을 생성합니다.
"""

from bitcoin_analysis import (
    get_bitcoin_data, 
    calculate_indicators, 
    analyze_market_position,
    format_analysis_result_html
)
from datetime import datetime
import sys


def generate_index_html():
    """
    GitHub Pages용 index.html 생성
    """
    print("=" * 70)
    print("비트코인 분석 리포트 생성 (GitHub Pages)")
    print("=" * 70)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 분석 시작...\n")
    
    try:
        # 데이터 가져오기
        df = get_bitcoin_data()
        if df is None or df.empty:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [X] 데이터를 가져올 수 없습니다.")
            sys.exit(1)
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [OK] 데이터 로드 완료 ({len(df)}개 봉)")
        
        # 기술적 지표 계산
        df = calculate_indicators(df)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [OK] 기술적 지표 계산 완료")
        
        # 현재 가격
        current_price = df['close'].iloc[-1]
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 현재 비트코인 가격: ${current_price:,.2f}\n")
        
        # 시장 위치 분석
        final_position, indicators, recommendation, score, action, targets, cycle_info, peak_info = analyze_market_position(df)
        
        # 콘솔 출력
        position_text = final_position.replace("🟢", "").replace("🟡", "").replace("⚪", "").replace("🟠", "").replace("🔴", "").strip()
        
        print("=" * 70)
        print("분석 결과 요약")
        print("=" * 70)
        print(f"투자 판단: {position_text}")
        print(f"종합 점수: {score:.1f}점")
        
        if cycle_info:
            print(f"4년 주기: {cycle_info['cycle_phase']} ({cycle_info['cycle_position_pct']:.1f}%)")
        
        if peak_info:
            print(f"고점 근접도: {peak_info['peak_score']:.0f}/100")
        
        print("=" * 70 + "\n")
        
        # 현재 날짜/시간
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # HTML 생성
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] index.html 생성 중...")
        analysis_html = format_analysis_result_html(
            final_position, indicators, recommendation, 
            current_price, date_str, action, targets, 
            score, cycle_info, peak_info
        )
        
        # index.html로 저장
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(analysis_html)
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [OK] index.html 생성 완료!")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] GitHub Pages에 배포 준비 완료\n")
        
        return True
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [X] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    success = generate_index_html()
    if success:
        print("\n✅ 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        print("\n❌ 실패했습니다.")
        sys.exit(1)

