"""
EBS 오디오어학당 스크립트 다운로더
- 유료 구독 계정으로 로그인하여 당일 입트영/귀트영 스크립트를 가져옵니다
- source/ 폴더에 자동 저장
- 사용법: python3 fetch_ebs.py [날짜(선택, 기본=오늘)]
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

# EBS 로그인 정보 (환경변수 우선)
EBS_ID = os.environ.get("EBS_ID", "keonunglim@gmail.com")
EBS_PW = os.environ.get("EBS_PW", "Xo8090xo!!")

# EBS URLs
LOGIN_URL = "https://www.ebs.co.kr/member/login"
EBS_AJAX_URL = "https://5dang.ebs.co.kr/auschool/replayAjax"
EBS_BASE_URL = "https://5dang.ebs.co.kr"

PROGRAMS = {
    "입트영": {
        "prodId": "200",
        "courseId": "BK0KAKC0000000014",
        "stepId": "01BK0KAKC0000000014",
    },
    "귀트영": {
        "prodId": "207",
        "courseId": "BK0KAKG0000000001",
        "stepId": "01BK0KAKG0000000001",
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def ebs_login(session):
    """EBS 사이트에 로그인합니다."""
    print("  EBS 로그인 중...")

    # 1차: 로그인 페이지 방문 (CSRF 토큰/쿠키 확보)
    session.get("https://www.ebs.co.kr/member/login", headers=HEADERS, timeout=10)

    # 2차: 로그인 POST
    login_data = {
        "userId": EBS_ID,
        "userPw": EBS_PW,
        "target": "",
        "loginType": "normal",
    }

    # EBS 로그인 URL 후보 (사이트 구조에 따라 다를 수 있음)
    login_urls = [
        "https://www.ebs.co.kr/member/loginAction",
        "https://www.ebs.co.kr/member/login",
        "https://sso.ebs.co.kr/login",
    ]

    for url in login_urls:
        try:
            resp = session.post(url, data=login_data, headers=HEADERS,
                                timeout=15, allow_redirects=True)
            # 로그인 성공 여부 확인 (쿠키 기반)
            cookies = session.cookies.get_dict()
            if any(k for k in cookies if "TOKEN" in k.upper() or "SSO" in k.upper()
                   or "SESSION" in k.upper() or "LOGIN" in k.upper()):
                print(f"  로그인 성공 (via {url})")
                return True
        except Exception:
            continue

    # 쿠키만으로 확인이 안 되면, 5dang 접속 시도
    try:
        test = session.get(
            "https://5dang.ebs.co.kr/auschool/sub/replay?prodId=200",
            headers=HEADERS, timeout=10
        )
        if "logout" in test.text.lower() or "로그아웃" in test.text:
            print("  로그인 확인됨")
            return True
    except Exception:
        pass

    print("  로그인 실패 - 스크립트 없이 제목만 사용합니다")
    return False


def fetch_episode_info(session, program, date_str):
    """당일 에피소드 정보(제목, lectId)를 가져옵니다."""
    config = PROGRAMS[program]
    date_compact = date_str.replace("-", "")

    data = {
        "prodId": config["prodId"],
        "courseId": config["courseId"],
        "stepId": config["stepId"],
        "lectId": "",
        "pageNum": "1",
        "orderby": "NEW",
        "pdfOnly": "",
        "situ": "",
        "startDate": date_compact,
        "endDate": date_compact,
        "date": "",
        "pageSize": "10",
        "subMenuId": "",
        "prodChrgClsNm": "유료",
    }

    try:
        resp = session.post(EBS_AJAX_URL, data=data, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        links = soup.find_all("a", href=re.compile(r"lectId="))
        for link in links:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            lect_match = re.search(r"lectId=(\d+)", href)
            if title and lect_match:
                lect_id = lect_match.group(1)
                return {"title": title, "lectId": lect_id}
    except Exception as e:
        print(f"  에피소드 조회 실패: {e}")

    return None


def fetch_script(session, program, episode_info):
    """에피소드 페이지에서 스크립트를 가져옵니다."""
    config = PROGRAMS[program]
    lect_id = episode_info["lectId"]

    # 에피소드 페이지 접속 (스크립트가 페이지에 포함되어 있을 수 있음)
    url = f"{EBS_BASE_URL}/auschool/sub/replay?prodId={config['prodId']}&lectId={lect_id}"

    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 스크립트 영역 탐색
        script_el = soup.find("div", class_="scriptText")
        if script_el:
            text = script_el.get_text("\n", strip=True)
            if text and len(text) > 50:
                return text

        # 대안: script_wrap 영역
        script_wrap = soup.find("div", class_="script_wrap")
        if script_wrap:
            text = script_wrap.get_text("\n", strip=True)
            if text and len(text) > 50:
                return text

        # 대안: 페이지 내 영어 텍스트 블록 추출
        all_text = soup.get_text("\n", strip=True)
        lines = [l.strip() for l in all_text.split("\n") if len(l.strip()) > 20]
        english_blocks = [l for l in lines if re.search(r"[a-zA-Z]{5,}", l)]
        if len(english_blocks) > 5:
            return "\n".join(english_blocks[:30])

        print(f"  스크립트를 찾지 못했습니다 (로그인 또는 구독 필요)")
        return None

    except Exception as e:
        print(f"  스크립트 가져오기 실패: {e}")
        return None


def save_source(program, date_str, title, script=None):
    """source/ 폴더에 소스 파일을 저장합니다."""
    os.makedirs(SOURCE_DIR, exist_ok=True)

    content = f"제목: {title}\n날짜: {date_str}\n\n"
    if script:
        content += f"=== 스크립트 ===\n{script}\n"
    else:
        content += f"(스크립트 없음 - 제목만 제공)\n"

    path = os.path.join(SOURCE_DIR, f"{program}_{date_str}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  저장: {os.path.basename(path)} ({len(content)}자)")
    return path


def main():
    # 날짜 결정
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        now = datetime.now(KST)
        date_str = now.strftime("%Y-%m-%d")

    print("=" * 50)
    print(f"  EBS 스크립트 다운로더 - {date_str}")
    print("=" * 50)

    # 세션 생성 및 로그인
    session = requests.Session()
    logged_in = ebs_login(session)

    for program in ["입트영", "귀트영"]:
        print(f"\n--- {program} ---")

        # 에피소드 정보 조회
        info = fetch_episode_info(session, program, date_str)
        if not info:
            print(f"  {date_str}에 {program} 에피소드가 없습니다")
            continue

        print(f"  제목: {info['title']}")
        print(f"  lectId: {info['lectId']}")

        # 스크립트 가져오기 (로그인된 경우)
        script = None
        if logged_in:
            script = fetch_script(session, program, info)
            if script:
                print(f"  스크립트 수집 완료 ({len(script)}자)")
            else:
                print("  스크립트 수집 실패 (제목만 저장)")

        # 저장
        save_source(program, date_str, info["title"], script)

    print(f"\n{'=' * 50}")
    print("  완료! source/ 폴더를 확인하세요.")
    print("  git add source/ && git commit -m 'Add EBS source' && git push")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
