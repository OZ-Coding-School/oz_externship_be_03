from rest_framework import status
from rest_framework.exceptions import APIException
from django.utils.translation import gettext_lazy as _

# Conflict 409 Error Custom
class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Conflict data')
    default_code = 'conflict'

    def __init__(self, detail=None, code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
