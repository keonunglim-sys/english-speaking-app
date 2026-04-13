"""
EBS 교재 EPUB 파서
- 입트영/귀트영 월간 교재 EPUB에서 특정 날짜의 콘텐츠를 추출
- 사용법: python3 epub_parser.py <epub_path> [날짜]

EPUB 파일 배치:
  ebooks/입트영_2026-04.epub  (4월호)
  ebooks/귀트영_2026-04.epub  (4월호)
"""

import os
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))


def read_epub(epub_path):
    """EPUB 파일에서 모든 HTML 콘텐츠를 읽습니다."""
    if not os.path.exists(epub_path):
        return []

    chapters = []
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            # OPF 파일에서 읽기 순서 파악
            opf_path = None
            for name in z.namelist():
                if name.endswith(".opf"):
                    opf_path = name
                    break

            html_files = []
            if opf_path:
                # OPF에서 spine 순서대로 읽기
                from xml.etree import ElementTree as ET
                opf_content = z.read(opf_path).decode("utf-8")
                root = ET.fromstring(opf_content)

                ns = {"opf": "http://www.idpf.org/2007/opf"}
                manifest = {}
                for item in root.findall(".//{http://www.idpf.org/2007/opf}item"):
                    item_id = item.get("id", "")
                    href = item.get("href", "")
                    media = item.get("media-type", "")
                    if "html" in media or "xhtml" in media:
                        # href를 OPF 기준 상대경로로 resolve
                        base = os.path.dirname(opf_path)
                        full_path = os.path.join(base, href).replace("\\", "/")
                        manifest[item_id] = full_path

                for itemref in root.findall(".//{http://www.idpf.org/2007/opf}itemref"):
                    idref = itemref.get("idref", "")
                    if idref in manifest:
                        html_files.append(manifest[idref])
            else:
                # OPF 없으면 HTML 파일 정렬
                html_files = sorted(
                    [n for n in z.namelist()
                     if n.endswith((".html", ".xhtml", ".htm"))],
                )

            for html_path in html_files:
                try:
                    content = z.read(html_path).decode("utf-8")
                    soup = BeautifulSoup(content, "html.parser")
                    text = soup.get_text("\n", strip=True)
                    if text and len(text.strip()) > 20:
                        chapters.append({
                            "file": html_path,
                            "html": content,
                            "text": text,
                        })
                except Exception:
                    continue

    except Exception as e:
        print(f"  EPUB 읽기 오류: {e}")

    return chapters


def find_daily_content(chapters, date_str):
    """챕터 목록에서 특정 날짜의 콘텐츠를 찾습니다."""
    if not chapters:
        return None

    # 날짜 패턴들 (교재마다 다를 수 있음)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day = date_obj.day
    month = date_obj.month

    patterns = [
        # "4월 13일", "4/13", "04/13", "April 13", "13일"
        f"{month}월\\s*{day}일",
        f"{month}/{day}",
        f"{month:02d}/{day:02d}",
        f"{month:02d}\\.{day:02d}",
        f"Day\\s*{day}",
        # 요일 + 날짜
        date_obj.strftime("%B %d"),  # "April 13"
        date_obj.strftime("%b %d"),  # "Apr 13"
        date_obj.strftime("%m/%d"),  # "04/13"
    ]

    # 각 챕터에서 날짜 매칭
    best_match = None
    best_score = 0

    for i, ch in enumerate(chapters):
        text = ch["text"]
        score = 0

        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 10

        # 제목 패턴 ("Lesson X", "Unit X", 에피소드 번호)
        if score > 0 and len(text) > 100:
            if score > best_score:
                best_score = score
                best_match = ch

    if best_match:
        return best_match

    # 날짜 매칭 실패 시: 챕터 순서로 추정
    # EBS 월간 교재는 보통 하루에 1-2 챕터
    # 첫 챕터(표지/목차)를 제외하고 날짜 기반 인덱스
    content_chapters = [c for c in chapters if len(c["text"]) > 200]
    if not content_chapters:
        return None

    # 날짜 기반 인덱스 (1일=첫번째 콘텐츠 챕터)
    # 주말 제외 (월~토 방송)
    broadcast_day = 0
    current = datetime(date_obj.year, date_obj.month, 1)
    while current.date() <= date_obj.date():
        if current.weekday() < 6:  # 월~토
            broadcast_day += 1
        current += timedelta(days=1)

    # 입트영은 하루 1챕터, 귀트영도 비슷
    idx = broadcast_day - 1
    if 0 <= idx < len(content_chapters):
        return content_chapters[idx]

    return None


def extract_lesson_content(chapter):
    """챕터에서 학습 콘텐츠를 구조화합니다."""
    if not chapter:
        return None

    text = chapter["text"]
    html = chapter["html"]
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "title": "",
        "script": "",
        "expressions": [],
        "full_text": text[:5000],
    }

    # 제목 추출 (첫 번째 h1/h2/h3 또는 큰 텍스트)
    for tag in ["h1", "h2", "h3", "strong"]:
        el = soup.find(tag)
        if el:
            title_text = el.get_text(strip=True)
            if title_text and len(title_text) > 3:
                result["title"] = title_text
                break

    if not result["title"]:
        lines = text.split("\n")
        for line in lines[:5]:
            line = line.strip()
            if line and 5 < len(line) < 100:
                result["title"] = line
                break

    # 영어 텍스트 블록 추출 (스크립트/본문)
    lines = text.split("\n")
    english_blocks = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        words = line.split()
        eng_words = [w for w in words if re.match(r"^[a-zA-Z'\"]", w)]
        if len(eng_words) >= 3 and len(eng_words) / max(len(words), 1) > 0.3:
            english_blocks.append(line)

    if english_blocks:
        result["script"] = "\n".join(english_blocks)

    return result


def find_epub_for_date(ebooks_dir, program, date_str):
    """ebooks/ 폴더에서 해당 날짜의 EPUB 파일을 찾습니다."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    year_month = date_obj.strftime("%Y-%m")

    # 파일명 패턴: 입트영_2026-04.epub, 입이 트이는 영어_2026년 4월.epub 등
    patterns = [
        f"{program}_{year_month}",
        f"{program}_{date_obj.year}-{date_obj.month:02d}",
        f"{program}_{date_obj.year}_{date_obj.month:02d}",
        f"{program}*{date_obj.year}*{date_obj.month:02d}",
        f"{program}*{date_obj.month}월",
    ]

    import glob
    for pattern in patterns:
        for ext in [".epub", ".EPUB"]:
            matches = glob.glob(os.path.join(ebooks_dir, pattern + ext))
            if matches:
                return matches[0]

    # 패턴 매칭 실패 시: 폴더 내 모든 EPUB 검색
    all_epubs = glob.glob(os.path.join(ebooks_dir, f"*{program}*.epub"))
    if not all_epubs:
        all_epubs = glob.glob(os.path.join(ebooks_dir, "*.epub"))

    for epub_path in all_epubs:
        fname = os.path.basename(epub_path).lower()
        if program.lower() in fname or program[0] in fname:
            return epub_path

    return None


def get_content_from_epub(ebooks_dir, program, date_str):
    """EPUB 교재에서 특정 날짜의 학습 콘텐츠를 추출합니다."""
    epub_path = find_epub_for_date(ebooks_dir, program, date_str)
    if not epub_path:
        return None

    print(f"  EPUB: {os.path.basename(epub_path)}")

    chapters = read_epub(epub_path)
    if not chapters:
        print(f"  EPUB 읽기 실패")
        return None

    print(f"  챕터 {len(chapters)}개 로드")

    chapter = find_daily_content(chapters, date_str)
    if not chapter:
        print(f"  {date_str} 해당 콘텐츠를 찾지 못함")
        return None

    content = extract_lesson_content(chapter)
    if content:
        print(f"  제목: {content['title']}")
        print(f"  본문: {len(content['full_text'])}자")

    return content


# YES24 앱 EPUB 경로
YES24_EBOOK_DIR = os.path.expanduser(
    "~/Library/Containers/com.yes24.macEBook/Data/Documents/YES24eBook/content"
)


def scan_yes24_for_ebs():
    """YES24 앱에서 EBS 교재를 찾습니다."""
    if not os.path.exists(YES24_EBOOK_DIR):
        return {}

    results = {}
    for fname in os.listdir(YES24_EBOOK_DIR):
        if not fname.endswith(".epub"):
            continue
        path = os.path.join(YES24_EBOOK_DIR, fname)
        try:
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if name.endswith(".opf"):
                        from xml.etree import ElementTree as ET
                        opf = ET.fromstring(z.read(name))
                        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
                        title_el = opf.find(".//dc:title", ns)
                        title = title_el.text if title_el is not None else ""
                        if any(k in title for k in ["입이 트이는", "귀가 트이는",
                                                      "입트영", "귀트영"]):
                            results[fname] = title
                        break
        except Exception:
            continue

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 epub_parser.py <epub_path> [날짜]")
        print("\nYES24 앱 EBS 교재 검색...")
        found = scan_yes24_for_ebs()
        if found:
            for fname, title in found.items():
                print(f"  {fname}: {title}")
        else:
            print("  EBS 교재를 찾지 못했습니다.")
            print("  YES24 앱에서 입트영/귀트영 교재를 다운로드해주세요.")
        sys.exit(0)

    epub_path = sys.argv[1]
    date_str = sys.argv[2] if len(sys.argv) > 2 else datetime.now(KST).strftime("%Y-%m-%d")

    print(f"EPUB: {epub_path}")
    print(f"날짜: {date_str}")

    chapters = read_epub(epub_path)
    print(f"챕터: {len(chapters)}개")

    if chapters:
        ch = find_daily_content(chapters, date_str)
        if ch:
            content = extract_lesson_content(ch)
            print(f"\n제목: {content['title']}")
            print(f"스크립트:\n{content['script'][:500]}")
        else:
            print("해당 날짜 콘텐츠를 찾지 못했습니다.")
            print("\n챕터 목록:")
            for i, c in enumerate(chapters[:20]):
                first_line = c["text"].split("\n")[0][:60]
                print(f"  {i+1}. [{c['file']}] {first_line}")
