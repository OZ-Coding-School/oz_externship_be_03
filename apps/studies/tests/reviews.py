from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.lecture.models.review import RatingEnum
from apps.studies.models.groups import StudyGroup, StudyGroupStatus
from apps.studies.models.reviews import Review

User = get_user_model()


class ReviewModelTestCase(TestCase):
    def setUp(self) -> None:
        # 테스트 사용자 생성
        self.user = User.objects.create(
            email="test@example.com",
            nickname="testuser",
            name="Test User",
            phone_number="010-1234-5678",
            birthday="1990-01-01",
            gender="MALE",
            is_active=True,
        )
        self.user.set_password("testpass123")
        self.user.save()

        # 다른 사용자 생성 (중복 테스트용)
        self.other_user = User.objects.create(
            email="other@example.com",
            nickname="otheruser",
            name="Other User",
            phone_number="010-9876-5432",
            birthday="1990-01-01",
            gender="FEMALE",
            is_active=True,
        )
        self.other_user.set_password("testpass123")
        self.other_user.save()

        # 테스트 스터디 그룹 생성
        self.study_group = StudyGroup.objects.create(
            name="테스트 스터디",
            introduction="테스트용 스터디입니다",
            max_headcount=5,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=30),
            status=StudyGroupStatus.ONGOING,
        )

    def test_review_creation(self) -> None:
        # 리뷰 생성 테스트
        review = Review.objects.create(
            user=self.user,
            study_group=self.study_group,
            star_rating=RatingEnum.FIVE,
            content="정말 좋은 스터디였습니다!",
        )

        self.assertEqual(review.user, self.user)
        self.assertEqual(review.study_group, self.study_group)
        self.assertEqual(review.star_rating, RatingEnum.FIVE)
        self.assertEqual(review.content, "정말 좋은 스터디였습니다!")
        self.assertIsNotNone(review.created_at)
        self.assertIsNotNone(review.updated_at)

    def test_review_default_values(self) -> None:
        # 리뷰 기본값 테스트
        review = Review.objects.create(user=self.user, study_group=self.study_group, content="기본값 테스트")

        # star_rating의 기본값이 RatingEnum.FIVE인지 확인
        self.assertEqual(review.star_rating, RatingEnum.FIVE)

    def test_review_unique_constraint(self) -> None:
        # 중복 방지 테스트
        # 첫 번째 리뷰 생성
        Review.objects.create(
            user=self.user, study_group=self.study_group, star_rating=RatingEnum.FIVE, content="첫 번째 리뷰"
        )

        # 같은 사용자가 같은 스터디에 두 번째 리뷰 생성 시도
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                user=self.user, study_group=self.study_group, star_rating=RatingEnum.THREE, content="두 번째 리뷰"
            )

    def test_review_multiple_users_same_group(self) -> None:
        # 여러 사용자가 같은 그룹에 리뷰작성
        # 첫 번째 사용자 리뷰
        review1 = Review.objects.create(
            user=self.user, study_group=self.study_group, star_rating=RatingEnum.FIVE, content="첫 번째 사용자 리뷰"
        )

        # 두 번째 사용자 리뷰
        review2 = Review.objects.create(
            user=self.other_user,
            study_group=self.study_group,
            star_rating=RatingEnum.FOUR,
            content="두 번째 사용자 리뷰",
        )

        # 두 리뷰가 모두 생성되었는지 확인
        reviews = Review.objects.filter(study_group=self.study_group)
        self.assertEqual(reviews.count(), 2)

        # 각 사용자별로 하나씩 리뷰가 있는지 확인
        user_review = reviews.filter(user=self.user).first()
        other_user_review = reviews.filter(user=self.other_user).first()

        assert user_review is not None
        assert other_user_review is not None

        self.assertIsNotNone(user_review)
        self.assertIsNotNone(other_user_review)
        self.assertEqual(user_review.content, "첫 번째 사용자 리뷰")
        self.assertEqual(other_user_review.content, "두 번째 사용자 리뷰")

    def test_review_content_max_length(self) -> None:
        # 최대 길이(300자) 내용
        long_content = "a" * 300
        review = Review.objects.create(
            user=self.user, study_group=self.study_group, star_rating=RatingEnum.FIVE, content=long_content
        )

        self.assertEqual(len(review.content), 300)
        self.assertEqual(review.content, long_content)

    def test_review_relationships(self) -> None:
        # Review와 다른 모델과의 관계테스트
        review = Review.objects.create(
            user=self.user, study_group=self.study_group, star_rating=RatingEnum.FIVE, content="관계 테스트"
        )

        # User와의 ForeignKey 관계 확인
        self.assertEqual(review.user, self.user)
        self.assertIn(review, self.user.reviews.all())

        # StudyGroup과의 ForeignKey 관계 확인
        self.assertEqual(review.study_group, self.study_group)
        self.assertIn(review, self.study_group.reviews.all())
