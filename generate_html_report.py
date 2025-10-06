"""
비트코인 분석 리포트 HTML 생성

이 스크립트는 bitcoin_analysis.py의 분석 기능을 사용하여
HTML 리포트 파일을 생성합니다. 이메일은 전송하지 않습니다.

사용법:
    python generate_html_report.py
"""

from bitcoin_analysis import (
    get_bitcoin_data, 
    calculate_indicators, 
    analyze_market_position,
    format_analysis_result_html
)
from datetime import datetime
import os
import webbrowser
import sys


def generate_html_report(open_browser=True):
    """
    비트코인 분석 리포트 HTML 생성
    
    Args:
        open_browser (bool): 생성 후 브라우저로 열지 여부 (기본값: True)
    """
    print("=" * 70)
    print("비트코인 분석 리포트 HTML 생성")
    print("=" * 70)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 분석 시작...\n")
    
    # 데이터 가져오기
    df = get_bitcoin_data()
    if df is None or df.empty:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [X] 데이터를 가져올 수 없습니다.")
        return None
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [OK] 데이터 로드 완료 ({len(df)}개 봉)")
    
    # 기술적 지표 계산
    df = calculate_indicators(df)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [OK] 기술적 지표 계산 완료")
    
    # 현재 가격
    current_price = df['close'].iloc[-1]
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 현재 비트코인 가격: ${current_price:,.2f}\n")
    
    # 시장 위치 분석
    final_position, indicators, recommendation, score, action, targets, cycle_info, peak_info = analyze_market_position(df)
    
    # 콘솔 출력용 텍스트 (이모지 제거)
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
        print(f"매도 권장: {peak_info['sell_recommendation']}")
    
    # 고점 예측 정보 출력 (매도 신호일 때)
    if 'predicted_peak' in targets:
        print(f"예상 고점: {targets['predicted_peak']}")
        if 'upside_to_peak' in targets:
            print(f"상승 여력: {targets['upside_to_peak']}")
    
    print(f"권장 행동: {action}")
    print("=" * 70 + "\n")
    
    # 현재 날짜/시간
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # HTML 생성
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTML 리포트 생성 중...")
    analysis_html = format_analysis_result_html(
        final_position, indicators, recommendation, 
        current_price, date_str, action, targets, 
        score, cycle_info, peak_info
    )
    
    # HTML 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_filename = f"bitcoin_analysis_{timestamp}.html"
    
    try:
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(analysis_html)
        
        html_path = os.path.abspath(html_filename)
        
        print(f"\n{'=' * 70}")
        print("[OK] HTML 생성 완료!")
        print(f"{'=' * 70}")
        print(f"파일명: {html_filename}")
        print(f"위치: {html_path}")
        
        # 파일 크기 확인
        file_size = os.path.getsize(html_filename)
        if file_size > 1024 * 1024:
            print(f"크기: {file_size / (1024 * 1024):.2f} MB")
        else:
            print(f"크기: {file_size / 1024:.2f} KB")
        print(f"{'=' * 70}\n")
        
        # 브라우저로 열기 (옵션)
        if open_browser:
            print("브라우저를 여는 중...")
            webbrowser.open('file://' + html_path)
            print("\n" + "=" * 70)
            print("브라우저가 열렸습니다!")
            print("=" * 70)
            print("\n[PDF로 저장하는 방법]")
            print("1. 브라우저에서 Ctrl + P (또는 우클릭 > 인쇄)")
            print("2. 대상/프린터: 'PDF로 저장' 또는 'Microsoft Print to PDF' 선택")
            print("3. '저장' 버튼 클릭")
            print("4. 저장 위치와 파일명 지정")
            print("\n이 방법으로 저장하면 한글이 완벽하게 표시됩니다!")
            print("=" * 70)
        
        return html_path
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [X] HTML 저장 실패: {e}")
        return None


if __name__ == "__main__":
    # 명령줄 인자 확인
    open_browser = True
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--no-open":
            # 브라우저로 열지 않음
            open_browser = False
        elif sys.argv[1] == "--help":
            print("""
사용법:
  python generate_html_report.py            # HTML 생성 후 브라우저로 열기 (기본값)
  python generate_html_report.py --no-open  # HTML만 생성 (브라우저 안 열기)
  python generate_html_report.py --help     # 도움말 표시
            """)
            sys.exit(0)
        else:
            print(f"[X] 알 수 없는 옵션: {sys.argv[1]}")
            print("사용법: python generate_html_report.py [--no-open|--help]")
            sys.exit(1)
    
    # HTML 리포트 생성
    result = generate_html_report(open_browser=open_browser)
    
    if result:
        print(f"\n리포트가 성공적으로 생성되었습니다: {result}")
    else:
        print("\n리포트 생성에 실패했습니다.")
        sys.exit(1)

