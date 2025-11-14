from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Count, QuerySet

from apps.core.utils.s3_uploader import S3Uploader
from apps.recruitments.models import (
    Recruitment,
    RecruitmentAttachment,
    RecruitmentImage,
    Tag,
)
from apps.users.models import User


# 태그 문자열 정리
def _clean_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    return [t.strip() for t in tags if t and t != "undefined"]


# 태그 저장
def _set_recruitment_tags(recruitment: Recruitment, tag_names: list[str]) -> None:
    recruitment.tags.clear()
    for name in tag_names[:5]:
        tag, _ = Tag.objects.get_or_create(name=name)
        recruitment.tags.add(tag)


# 이미지 업로드
def _save_images(recruitment: Recruitment, images: list[Any]) -> None:
    RecruitmentImage.objects.filter(recruitment=recruitment).delete()
    for file in images[:5]:
        url = S3Uploader().upload_file(file, "recruitments/images/")
        RecruitmentImage.objects.create(recruitment=recruitment, img_url=url)


# 첨부파일 업로드
def _save_attachments(recruitment: Recruitment, files: list[Any]) -> None:
    RecruitmentAttachment.objects.filter(recruitment=recruitment).delete()
    for file in files[:3]:
        url = S3Uploader().upload_file(file, "recruitments/attachments/")
        RecruitmentAttachment.objects.create(
            recruitment=recruitment,
            file_name=file.name,
            file_url=url,
        )


# 작성
@transaction.atomic
def create_recruitment(author: User, validated_data: dict[str, Any]) -> Recruitment:
    tags = _clean_tags(validated_data.pop("tags", []))
    images = validated_data.pop("images", [])
    attachments = validated_data.pop("attachments", [])

    # estimated_fee 기본 계산
    if validated_data.get("estimated_fee") is None:
        cnt = validated_data.get("expected_headcount", 1)
        validated_data["estimated_fee"] = cnt * 10000

    recruitment = Recruitment.objects.create(author=author, **validated_data)

    _set_recruitment_tags(recruitment, tags)
    _save_images(recruitment, images)
    _save_attachments(recruitment, attachments)

    return recruitment


# 수정
@transaction.atomic
def update_recruitment(recruitment: Recruitment, validated_data: dict[str, Any]) -> Recruitment:
    tags = validated_data.pop("tags", None)
    new_images = validated_data.pop("images", None)
    new_files = validated_data.pop("attachments", None)

    # 필드 값 업데이트
    for key, value in validated_data.items():
        setattr(recruitment, key, value)
    recruitment.save()

    # 태그 교체
    if tags is not None:
        cleaned = _clean_tags([t.get("name") for t in tags])
        _set_recruitment_tags(recruitment, cleaned)

    # 이미지 교체
    if new_images is not None:
        _save_images(recruitment, new_images)

    # 첨부파일 교체
    if new_files is not None:
        _save_attachments(recruitment, new_files)

    return recruitment


# 조회수 증가
def increase_views(recruitment: Recruitment) -> Recruitment:
    recruitment.views_count += 1
    recruitment.save(update_fields=["views_count"])
    return recruitment


# 추천 공고
def get_recommended_recruitments_for_user(user: User, limit: int = 3) -> QuerySet[Recruitment]:
    if not user.is_authenticated:
        return Recruitment.objects.none()

    return (
        Recruitment.objects.filter(is_closed=False)
        .annotate(bookmark_count=Count("bookmarks"))
        .order_by("-bookmark_count", "-views_count")[:limit]
    )
