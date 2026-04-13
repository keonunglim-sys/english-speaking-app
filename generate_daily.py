"""
매일 영어 스피킹 연습 콘텐츠 생성기
- EBS 입트영 + 귀트영 기반
- source/ 폴더의 방송 자료 또는 자동 주제 생성
- Claude API로 학습 콘텐츠 생성
"""

import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MAX_TOKENS, SOURCE_DIR

KST = timezone(timedelta(hours=9))
API_URL = "https://api.anthropic.com/v1/messages"
EBS_AJAX_URL = "https://5dang.ebs.co.kr/auschool/replayAjax"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# EBS 프로그램 설정
EBS_PROGRAMS = {
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


def fetch_ebs_episode_title(program, date_str):
    """EBS AJAX API에서 당일 에피소드 제목을 가져옵니다 (로그인 불필요)."""
    config = EBS_PROGRAMS.get(program)
    if not config:
        return None

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

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://5dang.ebs.co.kr/auschool/sub/replay",
    }

    try:
        resp = requests.post(EBS_AJAX_URL, data=data, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 에피소드 제목 추출 (테이블 행에서)
        links = soup.find_all("a", href=re.compile(r"prodId="))
        for link in links:
            title = link.get_text(strip=True)
            if title and len(title) > 3:
                print(f"  EBS {program} 제목: {title}")
                return title

        print(f"  EBS {program}: {date_str} 에피소드 없음")
        return None
    except Exception as e:
        print(f"  EBS {program} 조회 실패: {e}")
        return None


def load_source_file(program, date_str):
    """source/ 폴더에서 당일 방송 자료를 읽습니다."""
    os.makedirs(SOURCE_DIR, exist_ok=True)

    patterns = [
        os.path.join(SOURCE_DIR, f"{program}_{date_str}.txt"),
        os.path.join(SOURCE_DIR, f"{program}_{date_str}.md"),
        os.path.join(SOURCE_DIR, f"{program}_{date_str}*"),
    ]

    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            path = matches[0]
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                print(f"  소스 파일 발견: {os.path.basename(path)} ({len(content)}자)")
                return content

    print(f"  소스 파일 없음: {program}_{date_str}")
    return None


def generate_content_with_claude(입트영_source, 귀트영_source, date_str,
                                  입트영_title=None, 귀트영_title=None):
    """Claude API로 오늘의 전체 콘텐츠를 생성합니다."""

    # 소스 자료 구성
    입트영_section = ""
    if 입트영_source:
        입트영_section = f"""## 소스 1: 입트영 (입이 트이는 영어) 방송 자료
아래는 오늘 EBS 입트영 방송 내용입니다. 이 자료를 기반으로 학습 콘텐츠를 만들어주세요.
---
{입트영_source[:3000]}
---"""
    elif 입트영_title:
        입트영_section = f"""## 소스 1: 입트영 (입이 트이는 영어)
오늘의 입트영 방송 제목: "{입트영_title}"
스크립트 자료는 없지만, 위 제목을 주제로 입트영 스타일의 에세이를 작성해주세요.
150-200단어 분량으로, 한국인이 소리내어 읽기 좋은 자연스러운 영어로 작성하세요."""
    else:
        입트영_section = """## 소스 1: 입트영 (입이 트이는 영어)
오늘의 입트영 방송 자료가 없습니다.
한국인 직장인에게 유용한 주제로 입트영 스타일의 에세이를 직접 작성해주세요.
비즈니스 또는 일상 주제를 교대로 선택하여 150-200단어 분량으로 작성하세요."""

    귀트영_section = ""
    if 귀트영_source:
        귀트영_section = f"""## 소스 2: 귀트영 (귀가 트이는 영어) 방송 자료
아래는 오늘 EBS 귀트영 방송 내용입니다. 이 자료를 기반으로 학습 콘텐츠를 만들어주세요.
---
{귀트영_source[:3000]}
---"""
    elif 귀트영_title:
        귀트영_section = f"""## 소스 2: 귀트영 (귀가 트이는 영어)
오늘의 귀트영 방송 제목: "{귀트영_title}"
스크립트 자료는 없지만, 위 제목/주제로 귀트영 스타일의 뉴스 텍스트를 작성해주세요.
뉴스 기사 스타일로 100-150단어 분량으로 작성하세요."""
    else:
        귀트영_section = """## 소스 2: 귀트영 (귀가 트이는 영어)
오늘의 귀트영 방송 자료가 없습니다.
최신 영어 뉴스 또는 시사 토픽을 하나 선정하여 귀트영 스타일의 뉴스 텍스트를 작성해주세요.
뉴스 기사 스타일로 100-150단어 분량으로 작성하세요."""

    prompt = f"""당신은 한국인 직장인의 영어 스피킹 실력 향상을 돕는 전문 영어 코치입니다.
EBS 오디오어학당의 '입이 트이는 영어(입트영)'와 '귀가 트이는 영어(귀트영)' 프로그램을 기반으로
오늘의 영어 스피킹 연습 콘텐츠를 생성하세요.

{입트영_section}

{귀트영_section}

## 생성할 콘텐츠 (JSON)

### 1. 입트영 에세이 (ipteunyeong)
- 입트영 스타일: 한국인이 소리내어 읽기 좋은 자연스러운 영어 에세이
- 150-200 단어
- 소스 자료가 있으면 그 내용을 기반으로, 없으면 적절한 주제로 작성
- 에세이의 한국어 요약 (3-4문장)

### 2. 귀트영 뉴스/토픽 (gwitunyeong)
- 귀트영 스타일: 영어 뉴스 기사 또는 시사 토픽
- 100-150 단어
- 소스 자료가 있으면 그 내용을 기반으로, 없으면 최신 시사 주제로 작성
- 한국어 요약 (2-3문장)

### 3. 핵심 표현 (key_expressions) - 8개
- 입트영에서 4개, 귀트영에서 4개
- 각각: 영어 표현, 한국어 뜻, 예문 1개
- 실생활/비즈니스에서 바로 쓸 수 있는 실용 표현

### 4. 오늘의 3문장 (today_sentences)
- 비즈니스 영어 2개 + 일상 영어 1개 (또는 1+2 교대)
- 한국인이 실제로 말할 법한 상황의 문장
- 각각: 영어, 한국어, 카테고리(business/daily), 문법 포인트

### 5. 퀴즈 (quiz) - 6문항
- translation 타입 3개: 한국어 → 영어 번역 (acceptable_keywords 포함)
- fill_in_blank 타입 3개: 핵심 단어 빈칸 + 4지선다

아래 JSON 형식으로만 응답하세요.

{{"ipteunyeong":{{"title":"제목","text":"영어에세이본문","korean_summary":"한국어요약"}},"gwitunyeong":{{"title":"제목","text":"뉴스/토픽본문","korean_summary":"한국어요약"}},"key_expressions":[{{"english":"표현","korean":"뜻","example":"예문","source":"입트영또는귀트영"}}],"today_sentences":[{{"english":"영어문장","korean":"한국어문장","category":"business또는daily","grammar_point":"문법설명"}}],"quiz":[{{"type":"translation","korean":"한국어문장","answer":"영어답","acceptable_keywords":["핵심단어들"],"hint":"힌트"}},{{"type":"fill_in_blank","sentence":"빈칸문장___","answer":"정답","options":["보기1","보기2","보기3","보기4"],"korean":"한국어뜻"}}]}}"""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "{"},
        ],
    }

    print("  Claude API 호출 중...")
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()

    raw_text = "{"
    for block in data.get("content", []):
        if block.get("type") == "text":
            raw_text += block.get("text", "")

    print(f"  응답: stop_reason={data.get('stop_reason')}, length={len(raw_text)}")

    return parse_json_response(raw_text)


def parse_json_response(text):
    """JSON 파싱 (불완전한 JSON 복구 포함)."""
    stripped = text.strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(stripped[first:last + 1])
        except json.JSONDecodeError:
            pass

    repaired = repair_json(stripped)
    if repaired:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    return None


def repair_json(text):
    """불완전한 JSON의 괄호를 닫아서 복구."""
    if not text.startswith("{"):
        idx = text.find("{")
        if idx == -1:
            return None
        text = text[idx:]

    in_string = False
    escape = False
    brace_depth = 0
    bracket_depth = 0
    last_complete = -1

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and bracket_depth == 0:
                last_complete = i
        elif ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth -= 1

    if last_complete != -1:
        return text[:last_complete + 1]

    if in_string:
        text += '"'
    text = text.rstrip().rstrip(",")
    closing = "]" * max(0, bracket_depth) + "}" * max(0, brace_depth)
    return text + closing


def update_sentences_db(date_str, sentences):
    """누적 문장 DB를 업데이트합니다."""
    db_path = os.path.join(SCRIPT_DIR, "sentences_db.json")

    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as f:
            db = json.load(f)
    else:
        db = {"last_updated": "", "total_sentences": 0, "sentences": []}

    existing_dates = {s["date_added"] for s in db["sentences"]}
    if date_str in existing_dates:
        print(f"  DB: {date_str} 이미 존재, 스킵")
        return

    for i, sent in enumerate(sentences):
        db["sentences"].append({
            "id": f"{date_str}_sent_{i+1:02d}",
            "date_added": date_str,
            "english": sent["english"],
            "korean": sent["korean"],
            "category": sent.get("category", "daily"),
            "grammar_point": sent.get("grammar_point", ""),
        })

    db["last_updated"] = date_str
    db["total_sentences"] = len(db["sentences"])

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"  DB 업데이트: 총 {db['total_sentences']}문장")


def main():
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    day_names_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    day_of_week = day_names_ko[now.weekday()]

    print("=" * 60)
    print("  EBS 영어 스피킹 연습 콘텐츠 생성기")
    print(f"  {date_str} ({day_of_week})")
    print("=" * 60)

    # 1. EBS 에피소드 제목 조회 (로그인 불필요)
    print("\n[1/4] EBS 에피소드 조회")
    입트영_title = fetch_ebs_episode_title("입트영", date_str)
    귀트영_title = fetch_ebs_episode_title("귀트영", date_str)

    # 2. 소스 파일 확인 (사용자가 직접 넣은 스크립트)
    print("\n[2/4] 소스 자료 확인")
    입트영_source = load_source_file("입트영", date_str)
    귀트영_source = load_source_file("귀트영", date_str)

    has_source = bool(입트영_source or 귀트영_source)
    if has_source:
        print("  → 소스 자료 기반으로 콘텐츠 생성")
    elif 입트영_title or 귀트영_title:
        print("  → EBS 제목 기반으로 콘텐츠 생성")
    else:
        print("  → 소스 없음, Claude가 자체 주제로 생성")

    # 3. Claude API로 콘텐츠 생성
    print("\n[3/4] 콘텐츠 생성")
    content = generate_content_with_claude(
        입트영_source, 귀트영_source, date_str,
        입트영_title, 귀트영_title
    )

    if not content:
        print("  콘텐츠 생성 실패!")
        sys.exit(1)

    print("  콘텐츠 생성 완료!")

    # 3. 데이터 조합
    daily_data = {
        "date": date_str,
        "day_of_week": day_of_week,
        "has_source": has_source,
        "ipteunyeong": content.get("ipteunyeong", {}),
        "gwitunyeong": content.get("gwitunyeong", {}),
        "key_expressions": content.get("key_expressions", []),
        "today_sentences": content.get("today_sentences", []),
        "quiz": content.get("quiz", []),
    }

    # 4. JSON 저장
    daily_dir = os.path.join(SCRIPT_DIR, "daily")
    os.makedirs(daily_dir, exist_ok=True)

    daily_path = os.path.join(daily_dir, f"{date_str}.json")
    with open(daily_path, "w", encoding="utf-8") as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)
    print(f"\n[4/4] 저장 완료: {daily_path}")

    # 5. 누적 DB 업데이트
    sentences = content.get("today_sentences", [])
    if sentences:
        update_sentences_db(date_str, sentences)

    print(f"\n{'=' * 60}")
    print("  완료!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
