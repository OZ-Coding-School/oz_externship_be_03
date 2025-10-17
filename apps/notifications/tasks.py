from celery import shared_task
# Todo 정의후 공통 작업들은 상속 구조로 클래스 지정
@shared_task
def create_recruitment_applicant_task(recruitment_id: int, applicant_id: int, receiver_id: int) -> str:
    ...

@shared_task
def create_recruitment_application_approval_task(recruitment_id: int, applicant_id: int, status: str)-> str:
    ...

@shared_task
def create_recruitment_application_rejection_task(recruitment_id: int, applicant_id: int, status: str)-> str:
    ...

@shared_task
def create_studygroup_join_task(study_group_id: int, user_id: int) -> str:
    ...

@shared_task
def create_studygroup_reviewrequest_task(study_group_id: int, group_members_id: int) -> str:
    ...

@shared_task
def create_schedule_upcoming_task(study_group_id: int,group_schedules_id:int, group_members_id: int) -> str:
    ...

@shared_task
def create_schedule_today_task(study_group_id: int,group_schedules_id:int, group_members_id: int) -> str:
    ...

@shared_task
def create_study_record_task(user_id: int, study_notes_id: int) -> str:
    ...



