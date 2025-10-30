# apps/chat/exceptions.py

from rest_framework.exceptions import APIException


class ChatMessageNotFoundException(APIException):
    status_code = 404
    default_detail = "메시지를 찾을 수 없습니다."
    default_code = "MESSAGE_NOT_FOUND"


class ChatMessageNotSenderException(APIException):
    status_code = 403
    default_detail = "메시지 발신자만 수정할 수 있습니다."
    default_code = "NOT_MESSAGE_SENDER"
