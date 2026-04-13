"""
영어 스피킹 연습 앱 - 설정 파일
"""

import os

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "sk-ant-여기에키입력")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 16000

# 비즈니스 영어 주제 (순환)
ESSAY_TOPICS_BUSINESS = [
    "Handling Difficult Conversations at Work",
    "Presenting Ideas in a Meeting",
    "Writing Professional Emails",
    "Negotiating a Deal",
    "Giving and Receiving Feedback",
    "Networking at a Conference",
    "Leading a Team Meeting",
    "Managing Workplace Conflicts",
    "Discussing Quarterly Results",
    "Preparing for a Job Interview",
    "Delegating Tasks Effectively",
    "Building Rapport with Clients",
    "Explaining a Project Delay",
    "Proposing a New Initiative",
    "Onboarding a New Team Member",
]

# 일상 영어 주제 (순환)
ESSAY_TOPICS_DAILY = [
    "Ordering Food at a Restaurant",
    "Making Plans with Friends",
    "Talking About Weekend Activities",
    "Describing Your Neighborhood",
    "Shopping and Returning Items",
    "Discussing a Movie or TV Show",
    "Traveling and Asking for Directions",
    "Visiting a Doctor",
    "Talking About the Weather",
    "Cooking and Sharing Recipes",
    "Describing Your Daily Routine",
    "Making Small Talk with Neighbors",
    "Talking About Hobbies",
    "Discussing Family and Relationships",
    "Planning a Vacation",
]
