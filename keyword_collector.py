import os
import time
import logging
import urllib.parse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import gspread
import requests
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# CSS 선택자 설정 (유지보수를 위해 한 곳에 모음)
SELECTORS = {
    "related_keywords": "span.keywordItem_text__72V9o",  # 현재 선택자
    "related_keywords_alt": ".relatedTags_relation_tag__M4DGR span",  # 대체 선택자
}

# 로깅 설정
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("keyword_collector.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger()

# Google Sheets 연동 함수
def connect_google_sheet(sheet_id, worksheet_name):
    logger = logging.getLogger()
    service_account_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not service_account_file:
        logger.error("❌ GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
        raise ValueError("❌ GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다.")

    try:
        creds = Credentials.from_service_account_file(service_account_file, scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
        logger.info(f"✅ Google Sheet '{worksheet_name}' 연결 성공")
        return sheet
    except Exception as e:
        logger.error(f"❌ Google Sheet 연결 실패: {e}")
        raise

# 일반 요청을 사용한 크롤링 함수
def get_related_keywords(keyword):
    logger = logging.getLogger()
    # URL 인코딩 추가
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://search.shopping.naver.com/search/all?query={encoded_keyword}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"}
    
    # 요청 전송 및 예외 처리
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # HTTP 오류 검사
    except requests.exceptions.RequestException as e:
        logger.warning(f"요청 실패: {e}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # 여러 선택자 시도
    related = []
    for selector in [SELECTORS["related_keywords"], SELECTORS["related_keywords_alt"]]:
        related = soup.select(selector)
        if related:
            logger.info(f"✅ 선택자 '{selector}'로 {len(related)}개 키워드 찾음")
            break
    
    result = [tag.get_text().strip() for tag in related] if related else []
    if not result:
        logger.warning(f"⚠️ {keyword}: 일반 요청으로 연관 키워드를 찾을 수 없음")
    return result

# Selenium을 활용한 크롤링 (예비용)
def get_related_keywords_selenium(keyword):
    logger = logging.getLogger()
    logger.info(f"🔄 {keyword}: Selenium 크롤링 시작")
    
    # URL 인코딩
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://search.shopping.naver.com/search/all?query={encoded_keyword}"
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(20)
        
        driver.get(url)
        # 페이지 로딩 대기
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        
        # 여러 선택자 시도
        related = []
        for selector in [SELECTORS["related_keywords"], SELECTORS["related_keywords_alt"]]:
            related = soup.select(selector)
            if related:
                logger.info(f"✅ Selenium으로 선택자 '{selector}'에서 {len(related)}개 키워드 찾음")
                break
                
        result = [tag.get_text().strip() for tag in related] if related else []
        if not result:
            logger.warning(f"⚠️ {keyword}: Selenium으로도 연관 키워드를 찾을 수 없음")
        return result
        
    except Exception as e:
        logger.error(f"❌ Selenium 크롤링 중 오류: {e}")
        return []

# 재시도 로직이 포함된 크롤링 함수
def get_related_keywords_with_retry(keyword, max_retries=3):
    logger = logging.getLogger()
    logger.info(f"🔍 '{keyword}' 연관 키워드 수집 시작")
    
    for attempt in range(max_retries):
        try:
            # 일반 요청 시도
            keywords = get_related_keywords(keyword)
            if keywords:
                return keywords
            
            # 일반 요청 실패 시 Selenium으로 시도
            logger.info(f"일반 요청 실패, Selenium 사용 시도 중 ({attempt+1}/{max_retries})")
            keywords = get_related_keywords_selenium(keyword)
            if keywords:
                return keywords
                
        except Exception as e:
            logger.error(f"시도 {attempt+1}/{max_retries} 실패: {e}")
        
        if attempt < max_retries - 1:
            wait_time = 2 * (attempt + 1)  # 점진적 대기 시간 증가
            logger.info(f"⏱️ {wait_time}초 후 재시도...")
            time.sleep(wait_time)
    
    logger.error(f"❌ '{keyword}' 연관 키워드 수집 실패 (최대 시도 횟수 초과)")
    return []

# 배치 처리 함수
def process_keyword_batch(batch_items, sheet):
    logger = logging.getLogger()
    results = {"success": 0, "fail": 0}
    
    for idx, keyword in batch_items:
        try:
            related_keywords = get_related_keywords_with_retry(keyword)
            
            if related_keywords:
                # 연관 키워드 업데이트
                sheet.update_cell(idx, 5, ", ".join(related_keywords))  # 연관 키워드 업데이트
                sheet.update_cell(idx, 1, idx-1)  # No 값 업데이트
                sheet.update_cell(idx, 2, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))  # 날짜 업데이트
                sheet.update_cell(idx, 4, "수집 완료")  # 수집 여부 표시
                logger.info(f"✅ '{keyword}' 연관 키워드 수집 및 업데이트 완료 ({len(related_keywords)}개)")
                results["success"] += 1
            else:
                sheet.update_cell(idx, 4, "수집 실패")  # 수집 실패 표시
                logger.warning(f"⚠️ '{keyword}' 연관 키워드를 찾을 수 없음")
                results["fail"] += 1
                
        except Exception as e:
            logger.error(f"❌ '{keyword}' 처리 중 오류 발생: {e}")
            try:
                sheet.update_cell(idx, 4, "오류 발생")
            except:
                pass
            results["fail"] += 1
            
    return results

# 실행 함수
def main():
    logger = setup_logging()
    logger.info("🚀 키워드 수집기 실행 시작")
    
    # 스프레드시트 설정
    SHEET_ID = "1wxvKTda74w3KwyopgYAwAO3cgkShq6itMfS4GCE6Gp0"  # Google Sheets ID
    WORKSHEET_NAME = "Sheet1"  # 시트 탭 이름
    
    total_stats = {"processed": 0, "success": 0, "fail": 0}
    
    try:
        sheet = connect_google_sheet(SHEET_ID, WORKSHEET_NAME)
        rows = sheet.get_all_records()
        logger.info(f"📊 총 {len(rows)}개 행 로드됨")
        
        # 처리할 키워드 필터링
        keywords_to_process = []
        for idx, row in enumerate(rows, start=2):  # 첫 번째 행은 헤더
            keyword = row.get("키워드", "").strip()
            existing_related_keywords = row.get("연관키워드", "").strip()
            
            if not keyword:
                logger.debug(f"행 {idx}: 키워드 없음, 건너뜀")
                continue
                
            if existing_related_keywords:
                logger.debug(f"행 {idx}: '{keyword}' 이미 연관 키워드 있음, 건너뜀")
                continue
                
            keywords_to_process.append((idx, keyword))
            
        logger.info(f"🔍 처리할 키워드 {len(keywords_to_process)}개 발견")
        
        if not keywords_to_process:
            logger.info("✅ 처리할 키워드가 없습니다. 프로그램 종료")
            return
            
        # 배치 처리
        batch_size = 5  # 한 번에 처리할 키워드 수
        total_batches = (len(keywords_to_process) + batch_size - 1) // batch_size
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            
            for i in range(0, len(keywords_to_process), batch_size):
                batch = keywords_to_process[i:i+batch_size]
                logger.info(f"📦 배치 {i//batch_size + 1}/{total_batches} 처리 시작 ({len(batch)}개 키워드)")
                future = executor.submit(process_keyword_batch, batch, sheet)
                futures.append(future)
                
                # API 제한 방지를 위한 간격 두기
                if i + batch_size < len(keywords_to_process):
                    time.sleep(2)
            
            # 결과 수집
            for future in futures:
                result = future.result()
                total_stats["success"] += result["success"]
                total_stats["fail"] += result["fail"]
                total_stats["processed"] += result["success"] + result["fail"]
        
        logger.info(f"✅ 작업 완료: 총 {total_stats['processed']}개 처리, 성공: {total_stats['success']}, 실패: {total_stats['fail']}")
        
    except Exception as e:
        logger.error(f"❌ 실행 중 오류 발생: {e}")
        raise

# 메인 실행
if __name__ == "__main__":
    main()
