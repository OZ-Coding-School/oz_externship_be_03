from __future__ import annotations

import textwrap
import logging
import re
from typing import ClassVar

from django.conf import settings
from django.utils import timezone
from google import genai

from apps.studies.models.notes import StudyNote

logger = logging.getLogger(__name__)


class StudyNoteService:
    """
    스터디 노트 관련 비즈니스 로직
    - Gemini API 호출로 AI 요약 생성
    """

    MODEL_NAME = ClassVar[str] = "gemini-2.5-flash"

    _CLIENT: ClassVar[genai.Client] = genai.Client(api_key=settings.GEMINI_API_KEY)

    # 템플릿 문자열을 클래스 변수로 정의하여 summarize 메서드를 간결화
    # note.content는 f-string 내에서 직접 삽입하지 않고, 나중에 .format()이나 치환 함수로 사용예정
    # textwrap.dedent() : 문자열 좌측 들여쓰기 제거
    SUMMARY_PROMPT_TEMPLATE: ClassVar[str] = textwrap.dedent(
        """
        ### **역할:** 당신은 사용자의 학습 기록을 분석하고 요약하는 AI 분석가입니다.
        주어진 학습 내용 원문을 분석하여, 아래에 정의된 **정확한 형식**과 **지침**에 따라 요약 보고서를 한국어로 작성하십시오.

        ---

        ### **입력 데이터**
        - **날짜 (`date_str`):** {date_str}
        - **사용자 이름 (`author_name`):** {author_name}
        - **학습 내용 원문 (`note.content`):**
        {note_content}

        ---

        ### **출력 형식 및 지침**
        **반드시** 아래 형식만을 사용하여 응답을 생성해야 하며, 내용 원문은 출력에 **포함하지 않습니다**.

        ### {date_str} {author_name}님의 학습 기록 요약입니다.

        ## 학습 내용 요약
        * 핵심 내용을 간결한 **줄글로** 3~5줄 분량으로 요약합니다.

        ## 학습한 키워드
        * 원문에서 추출한 핵심 키워드를 **5개 내외**로 작성하며, 쉼표(,)로 구분하지 않고 줄 바꿈하여 작성합니다. (예: 키워드1\n키워드2...)

        ## 추가로 학습하면 좋을 내용 추천
        * 현재 학습 내용과 직접적으로 연관된 추가 학습 주제나 개념을 **2~3가지** 제안합니다. 제안은 간결하고 구체적이어야 합니다.

        ---
        """
    ).strip()


    @classmethod
    def summarize(cls, note: StudyNote) -> str:
        """Gemini API를 호출해 학습 내용 요약을 생성"""
        content =  (note.content or "").strip()

        if len(content) < 10 or len(re.findall(r"\w+",content)) < 5: # 10자 미만 내용 or 5개 단어 이하
            summary = (
                "### 자동요약이 생략되었습니다.\n\n"
                "입력된 내용이 너무 짧거나 불충분하여 생성할 요약이 없습니다"
            )
            note.ai_summary = summary
            note.save(update_fields = [ "ai_summary"])
            return summary

        # author의 데이터 수집, 선언
        date_str = timezone.localtime(note.created_at).strftime("%Y년 %m월 %d일 %A")
        author_name = note.author.nickname

        prompt = cls.SUMMARY_PROMPT_TEMPLATE.format(
            date_str=date_str,
            author_name=author_name,
            note_content=content,
        )

        # 토큰절약로직
        max_output_tokens = min(768, max(128, len(content) // 2))

        try:
            response = cls._CLIENT.models.generate_content(
                model=cls.MODEL_NAME,
                contents=prompt,
                config={
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_output_tokens": max_output_tokens,
                },
            )

            ai_summary = response.text.strip()

        except Exception as e:
            logger.error("요약 생성 실패: %s", e, exc_info=True)
            ai_summary = (
                "### 요약 오류 \n\n"
                "AI 요약 생성 중 오류 발생. 잠시 후 다시 시도하세요"
            )

        note.ai_summary = ai_summary
        note.save(update_fields = ["ai_summary"])
        return ai_summary