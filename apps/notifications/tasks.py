from celery import shared_task


# Todo 코드 작성후 공통 작업들은 상속 구조로 클래스 지정
@shared_task
def create_recruitment_applicant_task(recruitment_id: int, receiver_id: int) -> dict[str, object]:
    """
    공고 지원시 공고 작성자에게 보낼 알림 생성 task
    :param recruitment_id: 공고 ID
    :param applicant_id: 지원자 ID
    :param receiver_id: 알림 받을 자 ID
    :return: notification.create()
    """
    mock_recruitment_title = "오즈코딩스쿨 장고 스터디 모집"

    mock_notification_data = {
        "user_id": receiver_id,
        "content": f"공고 #{mock_recruitment_title}에 새로운 지원자가 지원했습니다.",
        "type": "APPLICATION_CREATED",
        "back_url_link": f"/admin/recruitments",
    }
    return mock_notification_data


@shared_task
def create_recruitment_application_approval_task(recruitment_id: int, applicant_id: int, status: str) -> dict[str,object]:
    """
    공고 지원시 공고 지원자에게 보낼 승인 알림 생성 task
    :param recruitment_id: 공고 ID
    :param applicant_id: 지원자 ID
    :param status: approval
    :return: notification.create()
    """
    mock_recruitment_title = "오즈코딩스쿨 장고 스터디 모집"

    mock_notification_data = {
        "user_id": applicant_id,
        "content": f"{mock_recruitment_title} 구인 공고에 대한 지원내역이 승인되었습니다.",
        "type": "APPLICATION_APPROVAL",
        "back_url_link": "/api/v1/applications?status=&cursor=",
    }
    return mock_notification_data

@shared_task
def create_recruitment_application_rejection_task(recruitment_id: int, applicant_id: int, status: str) -> str:
    """
    공고 지원시 공고 지원자에게 보낼 거절 알림 생성 task
    :param recruitment_id: 공고 ID
    :param applicant_id: 지원자 ID
    :param status: rejection
    :return: notification.create()
    """
    mock_recruitment_title = "오즈코딩스쿨 장고 스터디 모집"

    mock_notification_data = {
        "user_id": applicant_id,
        "content": f"{mock_recruitment_title} 구인 공고에 대한 지원내역이 거절되었습니다.",
        "type": "APPLICATION_REJECTION",
        "back_url_link": "/api/v1/applications?status=&cursor=",
    }
    return mock_notification_data


@shared_task
def create_studygroup_join_task(group_members_id: int) -> str:
    """
    지원 승인시 그룹원들에게 새로운 유저가 참여했다는 알림 생성 task
    :param group_members_id : 스터디 그룹원 ID
    :param
    :return: notification.create()
    """
    ...


@shared_task
def create_studygroup_reviewrequest_task(study_group_id: int, group_members_id: int) -> str:
    """
    그룹원들에게 후기 작성 요청하는 알림 생성 task
    :param group_members_id: 스터디 그룹원 ID
    :return: notification.create()
    """
    ...


@shared_task
def create_schedule_upcoming_task(group_schedules_id: int, group_members_id: int) -> str:
    """
    스케줄 참가 인원들에게 보낼 스케줄 예정 알림 생성 task
    :param group_members_id: 스터디 그룹원 ID
    :param group_schedules_id : 그룹 스케줄 ID
    :return: notification.create()
    """
    ...


@shared_task
def create_schedule_today_task(study_group_id: int, group_schedules_id: int) -> str:
    """
    매일 00시 01분부터 배치작업을 통해 모든 스터디 그룹의 스케줄중 당일에 해당하는 스케줄에 대해
    해당 스케줄 참가인원들에게 보낼 스케줄 당일 알림 생성 task
    :param study_group_id: 스터디 그룹 ID
    :param group_schedules_id:그룹 스케줄 ID
    :return: notification.create()
    """
    ...


@shared_task
def create_study_record_task(group_members_id: int, study_notes_id: int) -> str:
    """
    그룹원이 스터디 그룹의 상세페이지에서 스터디 기록 작성시
    다른 그룹원들에게 해당 인원의 기록작성을 알리는 알림 생성 task
    :param group_members_id: 그룹 멤버 ID
    :param study_notes_id: 스터디 기록 ID
    :return: notification.create()
    """
    ...
