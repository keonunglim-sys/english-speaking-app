"""
EBS 오디오어학당 스크립트 저장 도우미

사용법:
  1. 자동 모드 (제목만): python3 fetch_ebs.py
  2. 수동 모드 (스크립트 붙여넣기): python3 fetch_ebs.py --paste
  3. 특정 날짜: python3 fetch_ebs.py 2026-04-14
  4. 특정 날짜 + 붙여넣기: python3 fetch_ebs.py 2026-04-14 --paste

자동 모드: EBS에서 당일 에피소드 제목을 조회하여 source/ 폴더에 저장
수동 모드: EBS 앱/사이트에서 복사한 스크립트를 직접 붙여넣기
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(SCRIPT_DIR, "source")

EBS_AJAX_URL = "https://5dang.ebs.co.kr/auschool/replayAjax"

PROGRAMS = {
    "입트영": {"prodId": "200", "courseId": "BK0KAKC0000000014", "stepId": "01BK0KAKC0000000014"},
    "귀트영": {"prodId": "207", "courseId": "BK0KAKG0000000001", "stepId": "01BK0KAKG0000000001"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://5dang.ebs.co.kr/auschool/sub/replay",
}


def fetch_episode_title(program, date_str):
    """EBS AJAX API에서 당일 에피소드 제목을 가져옵니다."""
    config = PROGRAMS[program]
    date_compact = date_str.replace("-", "")

    data = {
        "prodId": config["prodId"],
        "courseId": config["courseId"],
        "stepId": config["stepId"],
        "lectId": "", "pageNum": "1", "orderby": "NEW",
        "pdfOnly": "", "situ": "",
        "startDate": date_compact, "endDate": date_compact,
        "date": "", "pageSize": "10", "subMenuId": "",
        "prodChrgClsNm": "유료",
    }

    try:
        resp = requests.post(EBS_AJAX_URL, data=data, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        links = soup.find_all("a", href=re.compile(r"lectId="))
        for link in links:
            title = link.get_text(strip=True)
            if title and len(title) > 3:
                return title
    except Exception as e:
        print(f"  조회 실패: {e}")

    return None


def paste_script(program, date_str, title):
    """사용자가 스크립트를 직접 붙여넣도록 합니다."""
    print(f"\n  [{program}] 스크립트를 붙여넣어 주세요.")
    print(f"  (EBS 앱/사이트에서 스크립트를 복사한 후 여기에 붙여넣기)")
    print(f"  (입력 완료 후 빈 줄에서 Ctrl+D 또는 'END' 입력)\n")

    lines = []
    try:
        while True:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
    except EOFError:
        pass

    script = "\n".join(lines).strip()
    if not script:
        print("  (스크립트 없음, 건너뜀)")
        return None

    print(f"  입력 완료! ({len(script)}자)")
    return script


def save_source(program, date_str, title, script=None):
    """source/ 폴더에 소스 파일을 저장합니다."""
    os.makedirs(SOURCE_DIR, exist_ok=True)

    content = f"제목: {title}\n날짜: {date_str}\n\n"
    if script:
        content += f"=== 스크립트 ===\n{script}\n"

    path = os.path.join(SOURCE_DIR, f"{program}_{date_str}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    has_script = "스크립트 포함" if script else "제목만"
    print(f"  저장: {os.path.basename(path)} ({has_script})")
    return path


def main():
    # 인수 파싱
    date_str = None
    paste_mode = "--paste" in sys.argv

    for arg in sys.argv[1:]:
        if arg != "--paste" and re.match(r"\d{4}-\d{2}-\d{2}", arg):
            date_str = arg

    if not date_str:
        now = datetime.now(KST)
        date_str = now.strftime("%Y-%m-%d")

    print("=" * 55)
    print(f"  EBS 스크립트 도우미 - {date_str}")
    if paste_mode:
        print(f"  모드: 수동 (스크립트 붙여넣기)")
    else:
        print(f"  모드: 자동 (제목 조회)")
    print("=" * 55)

    for program in ["입트영", "귀트영"]:
        print(f"\n--- {program} ---")

        # 제목 조회
        title = fetch_episode_title(program, date_str)
        if not title:
            print(f"  {date_str}에 에피소드 없음 (일요일?)")
            continue

        print(f"  제목: {title}")

        # 스크립트 입력 (수동 모드)
        script = None
        if paste_mode:
            script = paste_script(program, date_str, title)

        # 저장
        save_source(program, date_str, title, script)

    print(f"\n{'=' * 55}")
    print("  완료!")
    print(f"\n  다음 단계:")
    print(f"    cd ~/english-speaking-app")
    print(f"    git add source/ && git commit -m 'Add EBS source {date_str}' && git push")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()
