import gspread
import google.auth
from google.auth.transport.requests import AuthorizedSession
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from datetime import datetime

# ✅ 구글 시트 연동
def connect_google_sheet(sheet_id, worksheet_name):
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets'])
    gc = gspread.Client(auth=credentials, session=AuthorizedSession(credentials))
    sheet = gc.open_by_key(sheet_id).worksheet(worksheet_name)
    return sheet

# ✅ 연관 키워드 크롤링 함수 (Selenium 사용)
def get_related_keywords(keyword):
    url = f"https://search.shopping.naver.com/search/all?query={keyword}"

    options = Options()
    options.add_argument("--headless")  # 브라우저를 띄우지 않고 실행
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    service = Service("/usr/bin/chromedriver")  # 👉 chromedriver 경로 수정 필요
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # ✅ CSS 선택자를 통한 연관 키워드 크롤링
    related = soup.select("span.keywordItem_text__72V9o")

    # ✅ 크롤링 결과 검증
    if not related:
        print(f"⚠️ Warning: '{keyword}'에 대한 관련 키워드를 찾을 수 없음.")
        return []

    return [tag.get_text().strip() for tag in related]

# ✅ 메인 실행 함수
def main():
    SHEET_ID = '1wxvKTda74w3KwyopgYAwAO3cgkShq6itMfS4GCE6Gp0'
    WORKSHEET_NAME = '시트1'

    sheet = connect_google_sheet(SHEET_ID, WORKSHEET_NAME)
    rows = sheet.get_all_records()

    for idx, row in enumerate(rows, start=2):  # 2행부터 데이터 시작
        keyword = row.get('키워드', '').strip()
        related_keywords = row.get('연관키워드')

        # ✅ 키워드가 존재하고 연관 키워드가 없을 경우만 실행
        if keyword and not related_keywords:
            keywords = get_related_keywords(keyword)

            # ✅ 구글 시트 업데이트
            sheet.update_cell(idx, list(row.keys()).index('연관키워드') + 1, ", ".join(keywords))
            sheet.update_cell(idx, 1, idx - 1)  # No 값 업데이트
            sheet.update_cell(idx, 2, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))  # 시간 업데이트

if __name__ == "__main__":
    main()
