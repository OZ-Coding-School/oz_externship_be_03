from __future__ import annotations

import logging
import re
import textwrap
from typing import ClassVar

from django.conf import settings
from django.utils import timezone
from google import genai
from google.genai.types import GenerateContentConfig

from apps.studies.models.notes import StudyNote

logger = logging.getLogger(__name__)


class StudyNoteAIService:
    """
    스터디 노트 관련 비즈니스 로직
    - Google 공식 SDK (`google-genai`)를 이용하여 Gemini 모델을 직접 호출
    - RESTful HTTP 요청 대신 SDK 클라이언트를 생성 및 재사용하여 효율적 요청 처리
    - 학습 노트의 내용을 프롬프트에 맞춰 AI 요약문으로 정제하고, 결과를 DB에 저장
    """

    MODEL_NAME: ClassVar[str] = settings.GEMINI_MODEL_NAME
    _CLIENT: ClassVar[genai.Client]

    if getattr(settings, "GEMINI_API_KEY", None):
        _CLIENT = genai.Client(api_key=settings.GEMINI_API_KEY)
    else:
        # CI나 테스트 환경에서는 MockClient 사용
        import unittest.mock as mock

        _CLIENT = mock.MagicMock(name="MockGeminiClient")

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
    def _validate_summary(cls, text: str) -> bool:
        """요약 결과의 품질을 간단히 점검"""
        if not text or len(text.split()) < 10:
            return False
        if any(err in text for err in ["요약 오류", "생략", "불충분", "오류 발생", "실패"]):
            return False
        return True

    @classmethod
    def _self_check_summary(cls, draft: str, content: str) -> str:
        """1차 요약 결과가 불완전할 경우 2차 self-prompt로 수정"""
        refine_prompt = textwrap.dedent(
            f"""
        아래는 AI가 생성한 1차 요약 결과입니다.  
        만약 요약이 불완전하거나 요약문 형식이 어긋난 경우,  
        학습 내용을 기반으로 동일한 형식으로 다시 작성하십시오.
        ---

        [원문]
        {content}

        [1차 요약 결과]
        {draft}

        ---
        **출력 형식은 기존 요약 템플릿과 동일하게 유지하십시오.**
        """
        )

        try:
            res = cls._CLIENT.models.generate_content(
                model=cls.MODEL_NAME,
                contents=refine_prompt,
                config=GenerateContentConfig(
                    temperature=0.5,
                    top_p=0.9,
                    max_output_tokens=768,
                ),
            )
            return (res.text or "").strip()
        except Exception as e:
            logger.error("2차 self-refine 실패: %s", e, exc_info=True)
            return draft

    @staticmethod
    def _save_summary(note: StudyNote, text: str) -> str:
        note.ai_summary = text
        note.save(update_fields=["ai_summary"])
        return text

    @classmethod
    def summarize(cls, note: StudyNote) -> str:
        """Gemini API를 호출해 학습 내용 요약을 생성"""
        content = (note.content or "").strip()

        if len(content) < 10 or len(re.findall(r"\w+", content)) < 5:
            return cls._save_summary(
                note, "### 자동요약이 생략되었습니다.\n\n입력된 내용이 너무 짧거나 불충분하여 생성할 요약이 없습니다"
            )

        # author의 데이터 수집, 선언
        date_str = timezone.localtime(note.created_at).strftime("%Y년 %m월 %d일 %A")
        author_name = note.author.nickname

        prompt = cls.SUMMARY_PROMPT_TEMPLATE.format(
            date_str=date_str,
            author_name=author_name,
            note_content=content,
        )

        # 토큰절약로직
        max_output_tokens = max(128, min(768, len(content) // 2))

        try:
            response = cls._CLIENT.models.generate_content(
                model=cls.MODEL_NAME,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.7,
                    top_p=0.9,
                    max_output_tokens=max_output_tokens,
                ),
            )
            ai_summary = (response.text or "").strip()

            # 1차 요약 결과가 불완전하면 self-refine 발동
            if not cls._validate_summary(ai_summary):
                ai_summary = cls._self_check_summary(ai_summary, content)

            return cls._save_summary(note, ai_summary)

        except Exception as e:
            # %s 자리에 오는 값을(e) str()로 변환시켜주고 필요할 때에만 작동되는 지연 평가방식 가볍고 기능적이라고함
            logger.error("AI요약 생성 실패: %s", e, exc_info=True)
            return cls._save_summary(note, "### AI요약 오류:\n\nAI 요약 생성 중 오류 발생. 잠시 후 다시 시도하세요")
