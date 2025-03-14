import os
import gspread
import google.auth
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from datetime import datetime

# ✅ Google Sheets 연동 함수
def connect_google_sheet(sheet_id, worksheet_name):
    service_account_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not service_account_file:
        raise ValueError("❌ GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다.")

    creds = Credentials.from_service_account_file(service_account_file, scopes=[
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    return sheet

# ✅ 최신 CSS 선택자를 적용한 크롤링 함수
def get_related_keywords(keyword):
    url = f"https://search.shopping.naver.com/search/all?query={keyword}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    related = soup.select("span.keywordItem_text__72V9o")  # 최신 선택자 적용
    return [tag.get_text().strip() for tag in related] if related else []

# ✅ Selenium을 활용한 크롤링 (예비용)
def get_related_keywords_selenium(keyword):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    url = f"https://search.shopping.naver.com/search/all?query={keyword}"
    driver.get(url)
    
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    related = soup.select("span.keywordItem_text__72V9o")
    return [tag.get_text().strip() for tag in related] if related else []

# ✅ 실행 함수
def main():
    SHEET_ID = "1wxvKTda74w3KwyopgYAwAO3cgkShq6itMfS4GCE6Gp0"  # Google Sheets ID
    WORKSHEET_NAME = "Sheet1"  # 시트 탭 이름

    try:
        sheet = connect_google_sheet(SHEET_ID, WORKSHEET_NAME)
        rows = sheet.get_all_records()

        for idx, row in enumerate(rows, start=2):  # 첫 번째 행은 헤더
            keyword = row.get("키워드", "").strip()
            if not keyword:
                continue  # 키워드가 비어있다면 건너뜀

            existing_related_keywords = row.get("연관키워드", "").strip()
            if existing_related_keywords:
                continue  # 이미 연관 키워드가 있으면 건너뜀

            try:
                related_keywords = get_related_keywords(keyword)
                if not related_keywords:
                    related_keywords = get_related_keywords_selenium(keyword)  # Backup 크롤링

                if related_keywords:
                    sheet.update_cell(idx, 5, ", ".join(related_keywords))  # 연관 키워드 업데이트
                    sheet.update_cell(idx, 1, idx-1)  # No 값 업데이트
                    sheet.update_cell(idx, 2, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))  # 날짜 업데이트
                    sheet.update_cell(idx, 4, "수집 완료")  # 수집 여부 표시
                    print(f"✅ {keyword} → {related_keywords}")
                else:
                    print(f"⚠️ {keyword}: 연관 키워드를 찾을 수 없음")

            except Exception as e:
                print(f"❌ {keyword} 처리 중 오류 발생: {e}")

    except Exception as e:
        print(f"❌ Google Sheets 연결 실패: {e}")

# ✅ 메인 실행
if __name__ == "__main__":
    main()
