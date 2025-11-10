from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Type, cast

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.lecture.models.review import RatingEnum
from apps.studies.models.groups import GroupMember, StudyGroup, StudyGroupStatus
from apps.studies.models.reviews import Review

if TYPE_CHECKING:
    from apps.users.models.user import User
else:
    # Runtime only; for mypy we import concrete type in TYPE_CHECKING above
    from django.contrib.auth.base_user import (
        AbstractBaseUser as User,  # type: ignore[assignment]
    )

UserModel: Type[User] = get_user_model()


class _BaseFixtures(TestCase):
    user: ClassVar[User]
    other_user: ClassVar[User]
    study_group: ClassVar[StudyGroup]
    client: APIClient

    # 공통 셋업
    @classmethod
    def setUpTestData(cls) -> None:
        # 사용자 1
        cls.user = UserModel.objects.create(
            email="test@example.com",
            nickname="testuser",
            name="Test User",
            phone_number="010-1234-5678",
            birthday="1990-01-01",
            gender="M",
            is_active=True,
        )
        cls.user.set_password("pw1234")
        cls.user.save()

        cls.other_user = UserModel.objects.create(
            email="other@example.com",
            nickname="otheruser",
            name="Other User",
            phone_number="010-1111-2222",
            birthday="1990-01-01",
            gender="F",
            is_active=True,
        )
        cls.other_user.set_password("pw1234")
        cls.other_user.save()

        cls.study_group = StudyGroup.objects.create(
            name="테스트 스터디",
            introduction="테스트용 스터디입니다",
            max_headcount=5,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=30),
            status=StudyGroupStatus.ONGOING,
        )

    def setUp(self) -> None:
        self.client = APIClient()


# 모델테스트
class ReviewModelsTests(_BaseFixtures):
    def test_review_creation(self) -> None:  # 리뷰 정상 생성 확인
        review = Review.objects.create(
            user=cast(Any, self.user),
            study_group=self.study_group,
            star_rating=RatingEnum.FIVE,
            content="정말 좋은 스터디였습니다",
        )
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.study_group, self.study_group)
        self.assertEqual(review.content, "정말 좋은 스터디였습니다")
        self.assertIsNotNone(review.created_at)
        self.assertIsNotNone(review.updated_at)

    def test_review_default_values(self) -> None:  # star_rating 기본값 FIVE로 되어있는지
        review = Review.objects.create(user=cast(Any, self.user), study_group=self.study_group, content="기본값 테스트")
        self.assertEqual(review.star_rating, RatingEnum.FIVE)

    def test_review_unique_constraint(self) -> None:  # 같은 user+group 중복 리뷰 DB 제약
        Review.objects.create(
            user=self.user,
            study_group=self.study_group,
            star_rating=RatingEnum.FIVE,
            content="첫 번째 리뷰",
        )
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                user=self.user,
                study_group=self.study_group,
                star_rating=RatingEnum.THREE,
                content="두 번째 리뷰",
            )

    def test_review_multiple_users_same_group(self) -> None:  # 다른 유저들은 같은 그룹에 각각 리뷰 가능한지
        Review.objects.create(
            user=self.user,
            study_group=self.study_group,
            star_rating=RatingEnum.FIVE,
            content="첫 번째 사용자 리뷰",
        )
        Review.objects.create(
            user=self.other_user,
            study_group=self.study_group,
            star_rating=RatingEnum.FOUR,
            content="두 번째 사용자 리뷰",
        )
        reviews = Review.objects.filter(study_group=self.study_group)
        self.assertEqual(reviews.count(), 2)

        user_review = reviews.filter(user=self.user).first()
        other_user_review = reviews.filter(user=self.other_user).first()

        assert user_review is not None, "user_review should not be None"
        assert other_user_review is not None, "other_user_review should not be None"

        self.assertIsNotNone(user_review)
        self.assertIsNotNone(other_user_review)
        self.assertEqual(user_review.content, "첫 번째 사용자 리뷰")
        self.assertEqual(other_user_review.content, "두 번째 사용자 리뷰")

    def test_review_content_max_length(self) -> None:  # content가 300자까지 허용되는지
        long_content = "a" * 300
        review = Review.objects.create(
            user=cast(Any, self.user),
            study_group=self.study_group,
            star_rating=RatingEnum.FIVE,
            content=long_content,
        )
        self.assertEqual(len(review.content), 300)

    def test_review_relationships(self) -> None:  # User/StudyGroup 역참조 관계 정상동작 확인
        review = Review.objects.create(
            user=cast(Any, self.user), study_group=self.study_group, star_rating=RatingEnum.FIVE, content="관계 테스트"
        )
        self.assertEqual(review.study_group, self.study_group)
        self.assertIn(review, self.study_group.reviews.all())
        self.assertEqual(review.study_group, self.study_group)
        self.assertIn(review, self.study_group.reviews.all())


# API 테스트


class ReviewCreateAPITests(_BaseFixtures):
    def setUp(self) -> None:
        self.client = APIClient()

    def _url(self, group: StudyGroup) -> str:
        return reverse("studies:group-reviews", kwargs={"group_uuid": str(group.uuid)})

    # 인증 사용자 + 정상 입력 → 201 생성(본문 없음) 확인
    def test_create_review_201(self) -> None:
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            self._url(self.study_group),
            {"star_rating": 5, "content": "좋아요"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)

        obj = Review.objects.get(user_id=self.user.pk, study_group=self.study_group)
        self.assertEqual(obj.star_rating, RatingEnum.FIVE)

    # 이미 작성한 사용자/그룹 조합으로 재요청 → 409 충돌
    def test_create_review_duplicate_409(self) -> None:
        self.client.force_authenticate(user=self.user)
        Review.objects.create(
            user=self.user,
            study_group=self.study_group,
            star_rating=RatingEnum.FIVE,
            content="기존",
        )
        res = self.client.post(
            self._url(self.study_group),
            {"star_rating": 4, "content": "중복"},
            format="json",
        )
        self.assertEqual(res.status_code, 409)

    # content 공백만 보냄 → 422 검증 실패
    def test_create_review_blank_content_422(self) -> None:
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            self._url(self.study_group),
            {"star_rating": 3, "content": ""},
            format="json",
        )
        self.assertEqual(res.status_code, 422)

    # 미인증 상태로 요청 → 401 또는 403
    def test_create_review_unauthenticated(self) -> None:
        res = self.client.post(
            self._url(self.study_group),
            {"star_rating": 5, "content": "로그인 필요"},
            format="json",
        )
        self.assertIn(res.status_code, (401, 403))

    # 존재하지 않는 group_id로 요청 → 404
    def test_create_review_group_not_found_404(self) -> None:
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            reverse("studies:group-reviews", kwargs={"group_uuid": "00000000-0000-0000-0000-000000000999"}),
            {"star_rating": 5, "content": "없음"},
            format="json",
        )
        self.assertEqual(res.status_code, 404)


# 2)API 리뷰생성
class ReviewListAPITests(_BaseFixtures):
    def _url(self, group: StudyGroup) -> str:
        return reverse("studies:group-reviews", kwargs={"group_uuid": str(group.uuid)})

    def _add_member(self, group: StudyGroup, user: User) -> None:
        GroupMember.objects.create(study_group=group, user=user)

    def _create_review(
        self,
        *,
        group: StudyGroup,
        author: User,
        rating: RatingEnum,
        content: str,
        created_at: Optional[datetime] = None,
    ) -> Review:
        r = Review.objects.create(
            user=author,
            study_group=group,
            star_rating=rating,
            content=content,
        )
        if created_at is not None:
            Review.objects.filter(pk=r.pk).update(created_at=created_at, updated_at=created_at)
            r.refresh_from_db()
        return r

    def test_unauthenticated_returns_401(self) -> None:  # 비로그인 접근 401 반환
        res = self.client.get(self._url(self.study_group))
        self.assertEqual(res.status_code, 401)

    def test_forbidden_if_not_member_returns_403(self) -> None:  # 로그인했지만 그룹멤버가 아니면 403반환
        self.client.force_authenticate(user=self.user)
        res = self.client.get(self._url(self.study_group))
        self.assertEqual(res.status_code, 403)
        self.assertIn("detail", res.data)

    def test_group_not_found_404(self) -> None:  # 존재하지 않는 group_id 호출 404 반환
        self.client.force_authenticate(user=self.user)
        res = self.client.get(
            reverse("studies:group-reviews", kwargs={"group_uuid": "00000000-0000-0000-0000-000000000999"})
        )
        self.assertEqual(res.status_code, 404)


class ReviewUpdateAPITests(_BaseFixtures):
    def setUp(self) -> None:
        self.client = APIClient()
        # 내가 쓴 리뷰 하나 만들어 두기
        self.my_review = Review.objects.create(
            user=self.user,
            study_group=self.study_group,
            star_rating=RatingEnum.FIVE,
            content="원본 내용",
        )
        GroupMember.objects.create(study_group=self.study_group, user=self.user)

    def _url(self, group: StudyGroup, review: Review) -> str:
        return reverse(
            "studies:group-review-detail",
            kwargs={"group_uuid": str(group.uuid), "review_uuid": str(review.uuid)},
        )

    def test_update_my_review_200(self) -> None:
        """내가 쓴 리뷰를 내가 수정하면 200"""
        self.client.force_authenticate(user=self.user)
        res = self.client.patch(
            self._url(self.study_group, self.my_review),
            {"content": "수정한 내용", "star_rating": 4},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.my_review.refresh_from_db()
        self.assertEqual(self.my_review.content, "수정한 내용")
        self.assertEqual(self.my_review.star_rating, RatingEnum.FOUR)

    def test_update_unauthenticated_401(self) -> None:
        """비로그인은 401"""
        res = self.client.patch(
            self._url(self.study_group, self.my_review),
            {"content": "수정 불가"},
            format="json",
        )
        self.assertIn(res.status_code, (401, 403))

    def test_update_other_users_review_403(self) -> None:
        """다른 사람이 쓴 리뷰는 403"""
        other_review = Review.objects.create(
            user=self.other_user,
            study_group=self.study_group,
            star_rating=RatingEnum.THREE,
            content="남의 리뷰",
        )
        GroupMember.objects.create(study_group=self.study_group, user=self.other_user)

        self.client.force_authenticate(user=self.user)
        res = self.client.patch(
            self._url(self.study_group, other_review),
            {"content": "훔쳐서 수정"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_update_not_found_group_404(self) -> None:
        """그룹 uuid가 존재하지 않으면 404"""
        self.client.force_authenticate(user=self.user)
        res = self.client.patch(
            reverse(
                "studies:group-review-detail",
                kwargs={
                    "group_uuid": "00000000-0000-0000-0000-000000000999",
                    "review_uuid": str(self.my_review.uuid),
                },
            ),
            {"content": "아무거나"},
            format="json",
        )
        self.assertEqual(res.status_code, 404)

    def test_update_not_found_review_404(self) -> None:
        """그룹은 맞는데 리뷰 uuid가 없으면 404"""
        self.client.force_authenticate(user=self.user)
        res = self.client.patch(
            reverse(
                "studies:group-review-detail",
                kwargs={
                    "group_uuid": str(self.study_group.uuid),
                    "review_uuid": "00000000-0000-0000-0000-000000000999",
                },
            ),
            {"content": "아무거나"},
            format="json",
        )
        self.assertEqual(res.status_code, 404)
