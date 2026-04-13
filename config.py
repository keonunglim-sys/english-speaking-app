"""
영어 스피킹 연습 앱 - 설정 파일
EBS 입트영 + 귀트영 기반 학습
"""

import os

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "sk-ant-여기에키입력")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 16000

# 소스 폴더 (사용자가 당일 방송 자료를 넣는 곳)
SOURCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source")
