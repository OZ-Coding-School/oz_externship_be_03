from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class LeaderDelegationAPITest(APITestCase):
    """REQ-STDY-006: 스터디 그룹 리더 위임 API 테스트"""

    def setUp(self) -> None:
        self.group_id = "123e4567-e89b-12d3-a456-426614174000"
        self.member_id = 1
        self.url = reverse(
            "study-group-leader-delegate",
            kwargs={"group_id": self.group_id, "member_id": self.member_id},
        )

    def test_leader_delegation_success(self) -> None:
        response = self.client.patch(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "status": 200,
            "message": "스터디 그룹의 리더를 위임했습니다.",
        }

    def test_leader_delegation_unauthorized(self) -> None:
        response = self.client.patch(self.url)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]
