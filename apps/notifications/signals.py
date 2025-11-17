import logging
from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.notifications.tasks import send_to_pubsub
from apps.recruitments.models.application import Application, ApplicationStatus
from apps.studies.models import StudyGroup, StudyNote
from apps.studies.models.groups import GroupMember, StudyGroupStatus

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Application)
def recruitment_apply_created(sender: Any, instance: Application, created: bool, **kwargs: Any) -> None:
    """공고 지원시 알림 생성"""
    if not created:
        return  # 없으면 수정시에도 트리거가 발동됨

    recruitment = instance.recruitment

    notification = Notification.objects.create(
        user_id=recruitment.author_id,
        content=f"공고 '{recruitment.title}'에 새로운 지원자가 지원했습니다.",
        type=Notification.NotificationType.APPLICATION_CREATED,
        back_url_link="https://learn.ozcoding.site/recruit/manage",
    )

    send_to_pubsub.delay(notification.id)


@receiver(post_save, sender=Application)
def application_approved_rejected_created(sender: Any, instance: Application, created: bool, **kwargs: Any) -> None:
    """공고 지원 승인/거절 알림"""
    if not created and instance.status in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED]:
        recruitment = instance.recruitment

        if instance.status == ApplicationStatus.APPROVED:
            notification = Notification.objects.create(
                user_id=instance.user_id,
                content=f"'{recruitment.title}' 구인 공고에 대한 지원내역이 승인되었습니다.",
                type=Notification.NotificationType.APPLICATION_STATUS_APPROVAL,
                back_url_link="https://account.ozcoding.site/mypage/study",
            )
        else:
            notification = Notification.objects.create(
                user_id=instance.user_id,
                content=f"'{recruitment.title}' 구인 공고에 대한 지원내역이 거절되었습니다.",
                type=Notification.NotificationType.APPLICATION_STATUS_REJECTION,
                back_url_link="https://account.ozcoding.site/mypage/study",
            )

        send_to_pubsub.delay(notification.id)


@receiver(post_save, sender=Application)
def study_member_joined_created(sender: Any, instance: Application, created: bool, **kwargs: Any) -> None:
    """스터디 그룹 새 멤버 참여 알림"""
    if not created and instance.status == ApplicationStatus.APPROVED:
        recruitment = instance.recruitment

        if recruitment.study_group:
            study_group = recruitment.study_group
            new_member = instance.user

            # 기존 그룹 멤버들에게 각각 개별 알림 생성 (새 멤버 제외)
            existing_member = GroupMember.objects.filter(study_group=study_group).exclude(user=new_member)

            notifications = [
                Notification(
                    user_id=member.user.id,
                    content=f"{study_group.name}에 {new_member.nickname}님이 참여했습니다. 환영해주세요!",
                    type=Notification.NotificationType.STUDY_MEMBER_JOINED,
                    back_url_link=f"{study_group.uuid}",
                )
                for member in existing_member
            ]

            created_notifications = Notification.objects.bulk_create(notifications)

            for notification in created_notifications:
                send_to_pubsub.delay(notification.id)


@receiver(post_save, sender=StudyGroup)
def study_group_review_created(sender: Any, instance: StudyGroup, created: bool, **kwargs: Any) -> None:
    """스터디 그룹 종료시 후기 작성 알림"""
    if not created and instance.status == StudyGroupStatus.ENDED:
        # 그룹 멤버들 각각 개별 알림 생성( 알림 조회 API를 위해)
        group_members = GroupMember.objects.filter(study_group=instance)

        notifications = [
            Notification(
                user_id=member.user_id,
                content=f"오늘은 {instance.name}의 종료일이에요! 스터디 후기를 기록해주세요!",
                type=Notification.NotificationType.STUDY_REVIEW_REQUEST,
                back_url_link="https://account.ozcoding.site/mypage",
            )
            for member in group_members
        ]

        created_notifications = Notification.objects.bulk_create(notifications)

        for notification in created_notifications:
            send_to_pubsub.delay(notification.id)


@receiver(post_save, sender=StudyNote)
def study_note_created(sender: Any, instance: StudyNote, created: bool, **kwargs: Any) -> None:
    """스터디 기록 작성시 그룹 멤버들에게 알림"""
    if not created:
        return

    study_group = instance.study_group
    author = instance.author

    if study_group and author:
        existing_member = GroupMember.objects.filter(study_group=study_group).exclude(user=author)

        notifications = [
            Notification(
                user_id=member.user.id,
                content=f"{author.nickname}님이 {study_group.name}에 스터디 기록을 작성하셨습니다. 확인해보세요!",
                type=Notification.NotificationType.STUDY_RECORD_CREATED,
                back_url_link=f"https://study.ozcoding.site/study-groups/{study_group.uuid}",
            )
            for member in existing_member
        ]

        created_notifications = Notification.objects.bulk_create(notifications)

        for notification in created_notifications:
            send_to_pubsub.delay(notification.id)
