from apps.app_notifications.tasks import create_recruitment_applicant_task
from apps.app_notifications import tasks

def recruitment_create():
    data = {"recruitmet_id" : 2,"reciever_id" :1}

    tasks.create_recruitment_applicant_task.delay(data)

