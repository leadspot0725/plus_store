import gspread
from google.auth import default
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 구글 시트 연동
def connect_google_sheet(sheet_id, worksheet_name):
    credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets'])
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    return sheet

# 플러스 스토어 연관 키워드 크롤링
def get_related_keywords(keyword):
    url = f"https://search.shopping.naver.com/search/all?query={keyword}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    related_tags = soup.select("span.keywordItem_text__7ZVpD") # 페이지 구조 확인필요
    related_keywords = [tag.get_text().strip() for tag in related]
    return related_keywords

def main():
    SHEET_ID = '1wxvKTda74w3KwyopgYAwAO3cgkShq6itMfS4GCE6Gp0'
    SHEET_NAME = 'Sheet1'

    sheet = connect_google_sheet(sheet_id=SHEET_ID, worksheet_name=SHEET_NAME)
    rows = sheet.get_all_records()

    for idx, row in enumerate(rows, start=2):  # 2행부터 데이터 시작
        keyword = row['키워드']
        if keyword and not row.get('연관키워드'):
            related_keywords = get_related_keywords(keyword)
            # 연관 키워드 열번호 자동 탐지
            header = sheet.row_values(1)
            related_col_idx = header.index('연관키워드') + 1

            sheet.update_cell(idx, related_col_idx, ", ".join(related_keywords))
            sheet.update_cell(idx, 1, idx - 1)  # No 값 업데이트
            sheet.update_cell(idx, 2, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == "__main__":
    main()
