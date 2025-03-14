import time
import gspread
import requests
from bs4 import BeautifulSoup
import google.auth
from google.auth.transport.requests import AuthorizedSession
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
from datetime import datetime

# ✅ 크롬드라이버 자동 설치 및 설정
def get_driver():
    chromedriver_autoinstaller.install()  # 최신 버전의 ChromeDriver 자동 설치
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # GUI 없이 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# ✅ 네이버 쇼핑에서 연관 키워드 가져오기
def get_related_keywords(keyword):
    url = f"https://search.shopping.naver.com/search/all?query={keyword}"
    driver = get_driver()
    driver.get(url)
    time.sleep(3)  # 페이지 로딩 대기

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()  # 크롬드라이버 종료

    related = soup.select("span.keywordItem_text__72V9o")
    return [tag.text.strip() for tag in related]

# ✅ 구글 시트 연동
def connect_google_sheet(sheet_id, worksheet_name):
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets'])
    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(sheet_id).worksheet(worksheet_name)
    return sheet

# ✅ 메인 실행 함수
def main():
    SHEET_ID = "1wxvKTda74w3KwyopgYAwAO3cgkShq6itMfS4GCE6Gp0"  # 시트 ID
    WORKSHEET_NAME = "시트1"  # 시트 탭 이름

    sheet = connect_google_sheet(SHEET_ID, WORKSHEET_NAME)
    rows = sheet.get_all_records()

    for idx, row in enumerate(rows, start=2):  # 첫 번째 행은 헤더
        keyword = row.get('키워드')
        collected = row.get('수집여부')

        if keyword and not collected:  # 이미 수집된 키워드는 건너뛰기
            related_keywords = get_related_keywords(keyw
