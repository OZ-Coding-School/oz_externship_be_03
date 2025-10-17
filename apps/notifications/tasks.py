from celery import shared_task

@shared_task(serializer='json')
def create_recruitment_applicant_task():
    ...

@shared_task(serializer='json')
def create_recruitment_application_approval_task():
    ...

@shared_task(serializer='json')
def create_recruitment_application_rejection_task():
    ...

@shared_task(serializer='json')
def create_studygroup_join_task():
    ...

@shared_task(serializer='json')
def create_studygroup_reviewrequest_task():
    ...

@shared_task(serializer='json')
def create_schedule_upcoming_task():
    ...

@shared_task(serializer='json')
def create_schedule_today_task():
    ...

@shared_task(serializer='json')
def create_study_record_task():
    ...



