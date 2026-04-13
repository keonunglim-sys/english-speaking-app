"""
매일 영어 스피킹 연습 콘텐츠 생성기
- Living Life QT 본문 수집
- Claude API로 에세이, 핵심표현, 문장, 퀴즈 생성
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    ESSAY_TOPICS_BUSINESS,
    ESSAY_TOPICS_DAILY,
    MAX_TOKENS,
)

KST = timezone(timedelta(hours=9))
API_URL = "https://api.anthropic.com/v1/messages"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def fetch_qt_content(date_str):
    """두란노 Living Life QT 본문을 가져옵니다."""
    url = f"https://www.duranno.com/livinglife/qt/reload_default1.asp?OD={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print(f"  QT 수집: {url}")

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 제목과 성경 구절 추출
        title = ""
        bible_ref = ""

        title_el = soup.find("strong", class_="qt_tit")
        if title_el:
            title = title_el.get_text(strip=True)

        ref_el = soup.find("p", class_="qt_day")
        if ref_el:
            bible_ref = ref_el.get_text(strip=True)

        # 본문 추출 (여러 시도)
        scripture = ""
        reflection = ""
        prayer = ""

        # 성경 본문
        content_divs = soup.find_all("div", class_="bible_text")
        if content_divs:
            scripture = "\n".join(d.get_text(strip=True) for d in content_divs)

        # 묵상 내용
        devotion_divs = soup.find_all("div", class_="devotion_text")
        if devotion_divs:
            reflection = "\n\n".join(d.get_text("\n", strip=True) for d in devotion_divs)

        # 대안: 전체 텍스트에서 추출
        if not scripture and not reflection:
            all_text = soup.get_text("\n", strip=True)
            # 의미있는 영어 텍스트 블록 추출
            lines = [l.strip() for l in all_text.split("\n") if len(l.strip()) > 20]
            english_lines = [l for l in lines if re.search(r"[a-zA-Z]{3,}", l)]
            if english_lines:
                mid = len(english_lines) // 2
                scripture = "\n".join(english_lines[:mid])
                reflection = "\n".join(english_lines[mid:])

        # 기도문
        prayer_el = soup.find("div", class_="prayer_text")
        if prayer_el:
            prayer = prayer_el.get_text(strip=True)

        if not scripture and not reflection:
            # 최종 대안: 전체 HTML에서 영어 문장 추출
            text = soup.get_text(" ", strip=True)
            sentences = re.findall(r"[A-Z][^.!?]*[.!?]", text)
            if sentences:
                scripture = " ".join(sentences[:5])
                reflection = " ".join(sentences[5:15])
                prayer = " ".join(sentences[-3:]) if len(sentences) > 15 else ""

        result = {
            "title": title or "Daily Devotion",
            "bible_ref": bible_ref,
            "scripture_text": scripture[:3000],
            "reflection": reflection[:3000],
            "prayer": prayer[:1000],
        }
        print(f"  QT 수집 완료: {result['title']} ({result['bible_ref']})")
        return result

    except Exception as e:
        print(f"  QT 수집 실패: {e}")
        return {
            "title": "Daily Devotion",
            "bible_ref": "",
            "scripture_text": "",
            "reflection": "",
            "prayer": "",
        }


def get_today_topic(date_str):
    """날짜 기반으로 오늘의 에세이 주제를 결정합니다 (비즈니스/일상 교대)."""
    day_num = int(date_str.replace("-", "")) % (len(ESSAY_TOPICS_BUSINESS) + len(ESSAY_TOPICS_DAILY))

    if day_num % 2 == 0:
        idx = (day_num // 2) % len(ESSAY_TOPICS_BUSINESS)
        return ESSAY_TOPICS_BUSINESS[idx], "business"
    else:
        idx = (day_num // 2) % len(ESSAY_TOPICS_DAILY)
        return ESSAY_TOPICS_DAILY[idx], "daily"


def generate_content_with_claude(qt_data, essay_topic, essay_category, date_str):
    """Claude API로 오늘의 전체 콘텐츠를 생성합니다."""

    qt_text = f"""Title: {qt_data['title']}
Bible Reference: {qt_data['bible_ref']}
Scripture: {qt_data['scripture_text'][:1500]}
Reflection: {qt_data['reflection'][:1500]}
Prayer: {qt_data['prayer'][:500]}"""

    category_label = "비즈니스" if essay_category == "business" else "일상"

    prompt = f"""당신은 한국인 직장인의 영어 스피킹 실력 향상을 돕는 전문 영어 코치입니다.

아래 두 가지 소스를 바탕으로 오늘의 영어 스피킹 연습 콘텐츠를 생성하세요.

## 소스 1: Living Life QT (오늘의 묵상)
{qt_text}

## 소스 2: 오늘의 에세이 주제
주제: {essay_topic} (카테고리: {category_label})

## 생성할 콘텐츠

### 1. 에세이 (essay)
- EBS 입이트이는영어(입트영) 스타일로 작성
- 150-200 단어
- 한국인 직장인이 소리내어 읽기 좋은 자연스러운 영어
- 주제: {essay_topic}
- 에세이의 한국어 요약도 포함 (3-4문장)

### 2. 핵심 표현 (key_expressions) - 8개
- QT 본문에서 4개, 에세이에서 4개
- 각각: 영어 표현, 한국어 뜻, 예문 1개
- 실생활이나 비즈니스에서 바로 쓸 수 있는 실용적 표현 위주

### 3. 오늘의 3문장 (today_sentences)
- 비즈니스 영어 2개 + 일상 영어 1개 (또는 1+2 교대)
- 한국인이 실제로 말할 법한 상황의 문장
- 각각: 영어, 한국어, 카테고리(business/daily), 문법 포인트

### 4. 퀴즈 (quiz) - 6문항
- translation 타입 3개: 한국어 문장을 주고 영어로 번역 (acceptable_keywords 포함)
- fill_in_blank 타입 3개: 핵심 단어 빈칸 + 4지선다 보기

아래 JSON 형식으로만 응답하세요.

{{"essay":{{"title":"제목","category":"{essay_category}","text":"영어에세이본문","korean_summary":"한국어요약"}},"key_expressions":[{{"english":"표현","korean":"한국어뜻","example":"예문","source":"qt또는essay"}}],"today_sentences":[{{"english":"영어문장","korean":"한국어문장","category":"business또는daily","grammar_point":"문법설명"}}],"quiz":[{{"type":"translation","korean":"한국어문장","answer":"영어답","acceptable_keywords":["핵심단어들"],"hint":"힌트"}},{{"type":"fill_in_blank","sentence":"빈칸문장___","answer":"정답","options":["보기1","보기2","보기3","보기4"],"korean":"한국어뜻"}}]}}"""

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

    # 직접 파싱
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # ```json 블록 추출
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # { ~ } 추출
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(stripped[first:last + 1])
        except json.JSONDecodeError:
            pass

    # 불완전 JSON 복구
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

    # 닫는 괄호 추가
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

    # 오늘 날짜의 문장이 이미 있으면 스킵
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
    print(f"  영어 스피킹 연습 콘텐츠 생성기")
    print(f"  {date_str} ({day_of_week})")
    print("=" * 60)

    # 1. QT 수집
    print("\n[1/3] Living Life QT 수집")
    qt_data = fetch_qt_content(date_str)

    # 2. 에세이 주제 결정
    essay_topic, essay_category = get_today_topic(date_str)
    print(f"\n[2/3] 콘텐츠 생성 (에세이 주제: {essay_topic})")

    # 3. Claude API로 콘텐츠 생성
    content = generate_content_with_claude(qt_data, essay_topic, essay_category, date_str)

    if not content:
        print("  콘텐츠 생성 실패!")
        sys.exit(1)

    print(f"  콘텐츠 생성 완료!")

    # 4. 데이터 조합
    daily_data = {
        "date": date_str,
        "day_of_week": day_of_week,
        "qt": qt_data,
        "essay": content.get("essay", {}),
        "key_expressions": content.get("key_expressions", []),
        "today_sentences": content.get("today_sentences", []),
        "quiz": content.get("quiz", []),
    }

    # 5. JSON 저장
    daily_dir = os.path.join(SCRIPT_DIR, "daily")
    os.makedirs(daily_dir, exist_ok=True)

    daily_path = os.path.join(daily_dir, f"{date_str}.json")
    with open(daily_path, "w", encoding="utf-8") as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)
    print(f"\n[3/3] 저장 완료: {daily_path}")

    # 6. 누적 DB 업데이트
    sentences = content.get("today_sentences", [])
    if sentences:
        update_sentences_db(date_str, sentences)

    print(f"\n{'=' * 60}")
    print(f"  완료!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
