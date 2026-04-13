"""
동아출판 bookdonga.com EBS 오디오 자료 다운로드 모듈
- 입트영/귀트영 월별 본문 듣기 MP3 파일 URL 제공
- 인증 불필요
"""

import re

import requests
from bs4 import BeautifulSoup

AJAX_LIST_URL = "https://www.bookdonga.com/ebs/extradata_list_ajax.donga"
AJAX_FILES_URL = "https://www.bookdonga.com/common/extradata_file_list_ajax.donga"
DOWNLOAD_BASE = "https://www.bookdonga.com/utility/download.donga"

# brandinfo_seq: 입트영=125, 귀트영=128
PROGRAMS = {
    "입트영": {"brandinfo_seq": "125"},
    "귀트영": {"brandinfo_seq": "128"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.bookdonga.com/ebs/extradata_list.donga",
}


def get_product_seq(program, year):
    """해당 프로그램/연도의 월별 product_seq 목록을 가져옵니다."""
    config = PROGRAMS.get(program)
    if not config:
        return {}

    data = {
        "pagenum": "1",
        "p_serviceyear": str(year),
        "fgorder": "",
        "p_extradatatype": "",
        "p_classtype": "MI",
        "p_brandinfo_seq": config["brandinfo_seq"],
    }

    try:
        resp = requests.post(AJAX_LIST_URL, data=data, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        products = {}
        for item in soup.select(".booklist-item"):
            text = item.get_text()
            month_match = re.search(r"(\d{1,2})월", text)
            if not month_match:
                continue
            month = int(month_match.group(1))

            # product_seq from href or onclick
            item_html = str(item)
            seq_match = re.search(r"product_seq=(\d+)", item_html)
            if seq_match:
                products[month] = seq_match.group(1)

        return products
    except Exception as e:
        print(f"  bookdonga 제품 목록 조회 실패: {e}")
        return {}


def get_audio_files(product_seq):
    """특정 product_seq의 오디오 파일 목록을 가져옵니다."""
    data = {
        "product_seq": product_seq,
        "extradatatype": "DTTPSDP",
        "viewtype": "LAYER",
    }

    try:
        resp = requests.post(AJAX_FILES_URL, data=data, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        files = []
        for btn in soup.select("button[onclick*='downloadFile']"):
            onclick = btn.get("onclick", "")
            # downloadFile('EXTRADATAFILE','listen_flnm','66248','26565')
            m = re.search(
                r"downloadFile\(\s*'[^']*'\s*,\s*'[^']*'\s*,\s*'(\d+)'\s*,\s*'(\d+)'\s*\)",
                onclick,
            )
            if not m:
                continue

            data_seq = m.group(1)
            part_seq = m.group(2)

            # 날짜 추출: 부모 <li>의 텍스트에서 "4월 13일" 패턴
            li = btn.find_parent("li")
            li_text = li.get_text() if li else ""
            day_match = re.search(r"(\d{1,2})월\s*(\d{1,2})일", li_text)

            files.append({
                "data_seq": data_seq,
                "part_seq": part_seq,
                "month": int(day_match.group(1)) if day_match else None,
                "day": int(day_match.group(2)) if day_match else None,
                "is_zip": "전체" in li_text,
            })

        return files
    except Exception as e:
        print(f"  bookdonga 파일 목록 조회 실패: {e}")
        return []


def get_audio_url(data_seq, part_seq):
    """오디오 파일 다운로드 URL을 생성합니다."""
    return (
        f"{DOWNLOAD_BASE}?type=EXTRADATAFILE"
        f"&fieldname=listen_flnm"
        f"&data_seq={data_seq}"
        f"&part_seq={part_seq}"
    )


def get_daily_audio(program, date_str):
    """특정 날짜의 오디오 URL을 가져옵니다.

    Returns:
        dict: {"url": "...", "data_seq": "...", "part_seq": "..."} or None
    """
    from datetime import datetime
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    year = date_obj.year
    month = date_obj.month
    day = date_obj.day

    print(f"  bookdonga {program} {year}년 {month}월 조회...")

    # 1. 월별 product_seq 조회
    products = get_product_seq(program, year)
    if month not in products:
        print(f"  bookdonga: {month}월호 없음")
        return None

    product_seq = products[month]
    print(f"  bookdonga: product_seq={product_seq}")

    # 2. 오디오 파일 목록 조회
    files = get_audio_files(product_seq)
    if not files:
        print(f"  bookdonga: 오디오 파일 없음")
        return None

    # 3. 해당 날짜 파일 찾기
    for f in files:
        if f["day"] == day and (f["month"] is None or f["month"] == month):
            url = get_audio_url(f["data_seq"], f["part_seq"])
            print(f"  bookdonga: 오디오 발견 (data_seq={f['data_seq']})")
            return {
                "url": url,
                "data_seq": f["data_seq"],
                "part_seq": f["part_seq"],
            }

    # 날짜 매칭 실패 시: 순서 기반 추정 (ZIP 제외, 순서대로)
    non_zip = [f for f in files if "ZIP" not in f.get("label", "").upper()
               and "전체" not in f.get("label", "")]
    if non_zip:
        # 방송일 기준 인덱스 계산 (주말 제외)
        from datetime import timedelta
        broadcast_idx = 0
        current = datetime(year, month, 1)
        while current.date() < date_obj.date():
            if current.weekday() < 6:  # 월~토
                broadcast_idx += 1
            current += timedelta(days=1)

        if 0 <= broadcast_idx < len(non_zip):
            f = non_zip[broadcast_idx]
            url = get_audio_url(f["data_seq"], f["part_seq"])
            print(f"  bookdonga: 순서 기반 매칭 (idx={broadcast_idx})")
            return {
                "url": url,
                "data_seq": f["data_seq"],
                "part_seq": f["part_seq"],
            }

    print(f"  bookdonga: {day}일 오디오 찾지 못함")
    return None


if __name__ == "__main__":
    import sys
    from datetime import datetime, timedelta, timezone

    KST = timezone(timedelta(hours=9))
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now(KST).strftime("%Y-%m-%d")

    print(f"날짜: {date_str}\n")
    for prog in ["입트영", "귀트영"]:
        print(f"--- {prog} ---")
        result = get_daily_audio(prog, date_str)
        if result:
            print(f"  URL: {result['url']}")
        print()
