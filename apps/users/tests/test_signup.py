from __future__ import annotations

from contextlib import ExitStack
from datetime import date, datetime
from typing import Any, Dict, Mapping, Optional, Tuple, cast
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import Role
from apps.users.serializers.user_signup_serializers import SignupPayload
from apps.users.services.user_signup_service import (
    DefaultSignupService,
    _extract_msgs,
    active_from_status,
    flags_from_role,
    role_from_flags,
    status_from_active,
)
from apps.users.views.user_signup_views import UserSignupView

User = get_user_model()


# ---------------------------------------------------------------------
# 더미 유저 객체 (서비스 리턴용)
# ---------------------------------------------------------------------
class DummyUser:
    id: int
    email: str
    nickname: str
    name: str
    phone_number: str
    birthday: date
    gender: str
    role: str
    is_active: bool
    created_at: datetime

    def __init__(self, **kwargs: Any) -> None:
        self.id = int(kwargs.get("id", 1))
        self.email = str(kwargs.get("email", "john@example.com"))
        self.nickname = str(kwargs.get("nickname", "johnny"))
        self.name = str(kwargs.get("name", "John Doe"))
        self.phone_number = str(kwargs.get("phone_number", "01012345678"))
        self.birthday = cast(date, kwargs.get("birthday", date(1990, 1, 1)))
        self.gender = str(kwargs.get("gender", "M"))
        self.role = str(kwargs.get("role", "user"))
        self.is_active = bool(kwargs.get("is_active", True))
        self.created_at = cast(datetime, kwargs.get("created_at", datetime(2024, 1, 1, 0, 0, 0)))


# ---------------------------------------------------------------------
# 권한 패치 유틸: has_permission에서 request.*_verify_claims 주입
# ---------------------------------------------------------------------
def make_permission_patches(email_sub: Optional[str], phone_sub: Optional[str]) -> Tuple[Any, Any]:
    from apps.users import permissions as P  # 로컬 임포트(테스트 격리)

    def _email_has_perm(self: Any, request: Any, view: Any) -> bool:
        setattr(request, "email_verify_claims", {"sub": email_sub} if email_sub is not None else None)
        return True

    def _phone_has_perm(self: Any, request: Any, view: Any) -> bool:
        setattr(request, "phone_verify_claims", {"sub": phone_sub} if phone_sub is not None else None)
        return True

    p1 = mock.patch.object(P.EmailVerifiedPermission, "has_permission", new=_email_has_perm)
    p2 = mock.patch.object(P.PhoneVerifiedPermission, "has_permission", new=_phone_has_perm)
    return p1, p2


# ---------------------------------------------------------------------
# 더미 서비스
# ---------------------------------------------------------------------
class FakeSignupServiceOK:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def sign_up(self, payload: Dict[str, Any]) -> DummyUser:
        return DummyUser(
            id=1,
            email=payload["email"],
            nickname=payload["nickname"],
            name=payload["name"],
            phone_number=payload["phone_number"],
            birthday=payload["birthday"],
            gender=payload["gender"],
            role=payload.get("role", "user"),
            is_active=True,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )


class FakeSignupServiceRaisesDRF400:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def sign_up(self, payload: Dict[str, Any]) -> DummyUser:
        raise DRFValidationError({"email": ["이미 사용 중입니다."]})


class _APIExc(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = {"non_field_errors": ["절차 미완료"]}


class FakeSignupServiceRaises422:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def sign_up(self, payload: Dict[str, Any]) -> DummyUser:
        raise _APIExc()


class _APIConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = {"email": ["이미 사용 중입니다."]}


class FakeSignupServiceRaises409:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def sign_up(self, payload: Dict[str, Any]) -> DummyUser:
        raise _APIConflict()


class _APIServer(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = {"non_field_errors": ["서버 오류"]}


class FakeSignupServiceRaises500:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def sign_up(self, payload: Dict[str, Any]) -> DummyUser:
        raise _APIServer()


# ---------------------------------------------------------------------
# 공통 페이로드 (뷰 테스트용)
# ---------------------------------------------------------------------
def valid_payload() -> Dict[str, Any]:
    return {
        "email": "john@example.com",
        "password": "Passw0rd!",
        "nickname": "johnny",
        "name": "John Doe",
        "phone_number": "01012345678",
        "birthday": "1990-01-01",
        "gender": "M",
        "role": "user",
    }


# ---------------------------------------------------------------------
# 회원가입 뷰 테스트
# ---------------------------------------------------------------------
class SignupViewTests(IsolatedRedisTestClient):
    url: str
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        users = [
            User(
                email=f"dup{i}@example.com",
                nickname=f"dup{i}",
                name="Dup User",
                phone_number=f"0100000{i:04d}",
                birthday=date(1990, 1, 1),
                is_active=True,
            )
            for i in range(1, 51)
        ]
        User.objects.bulk_create(users)

    def setUp(self) -> None:
        super().setUp()
        self.url = reverse("users:signup")

    def test_signup_success_201(self) -> None:
        p1, p2 = make_permission_patches(email_sub="john@example.com", phone_sub="01012345678")
        with ExitStack() as stack:
            stack.enter_context(p1)
            stack.enter_context(p2)
            stack.enter_context(mock.patch.object(UserSignupView, "SERVICE_CLASS", new=FakeSignupServiceOK))

            resp: Response = self.client.post(self.url, data=valid_payload(), format="json")
            body: Dict[str, Any] = cast(Dict[str, Any], resp.data)

            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
            self.assertEqual(body.get("detail"), "회원가입에 성공하였습니다.")

    def test_serializer_invalid_400(self) -> None:
        p1, p2 = make_permission_patches(email_sub="john@example.com", phone_sub="01012345678")
        with ExitStack() as stack:
            stack.enter_context(p1)
            stack.enter_context(p2)
            stack.enter_context(mock.patch.object(UserSignupView, "SERVICE_CLASS", new=FakeSignupServiceOK))

            bad: Dict[str, Any] = valid_payload()
            bad.pop("email")

            resp: Response = self.client.post(self.url, data=bad, format="json")
            body: Dict[str, Any] = cast(Dict[str, Any], resp.data)

            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(body.get("error"), "email: 이 필드는 필수 항목입니다.")

    def test_email_claim_mismatch_400(self) -> None:
        p1, p2 = make_permission_patches(email_sub="mismatch@example.com", phone_sub="01012345678")
        with ExitStack() as stack:
            stack.enter_context(p1)
            stack.enter_context(p2)
            stack.enter_context(mock.patch.object(UserSignupView, "SERVICE_CLASS", new=FakeSignupServiceOK))

            resp: Response = self.client.post(self.url, data=valid_payload(), format="json")
            body: Dict[str, Any] = cast(Dict[str, Any], resp.data)

            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("error", body)
            msg: str = body["error"]
            self.assertIn("인증된 이메일과 불일치합니다.", msg)
            self.assertIn("email", msg)

    def test_phone_claim_mismatch_400(self) -> None:
        p1, p2 = make_permission_patches(email_sub="john@example.com", phone_sub="01000000000")
        with ExitStack() as stack:
            stack.enter_context(p1)
            stack.enter_context(p2)
            stack.enter_context(mock.patch.object(UserSignupView, "SERVICE_CLASS", new=FakeSignupServiceOK))

            resp: Response = self.client.post(self.url, data=valid_payload(), format="json")
            body: Dict[str, Any] = cast(Dict[str, Any], resp.data)

            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("error", body)
            msg: str = body["error"]
            self.assertIn("인증된 휴대폰과 불일치합니다.", msg)
            self.assertIn("phone_number", msg)

    def test_service_raises_drf_validation_400(self) -> None:
        p1, p2 = make_permission_patches(email_sub="john@example.com", phone_sub="01012345678")
        with ExitStack() as stack:
            stack.enter_context(p1)
            stack.enter_context(p2)
            stack.enter_context(mock.patch.object(UserSignupView, "SERVICE_CLASS", new=FakeSignupServiceRaisesDRF400))

            resp: Response = self.client.post(self.url, data=valid_payload(), format="json")
            body: Dict[str, Any] = cast(Dict[str, Any], resp.data)

            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(body.get("error"), "email: 이미 사용 중입니다.")

    def test_service_raises_422(self) -> None:
        p1, p2 = make_permission_patches(email_sub="john@example.com", phone_sub="01012345678")
        with ExitStack() as stack:
            stack.enter_context(p1)
            stack.enter_context(p2)
            stack.enter_context(mock.patch.object(UserSignupView, "SERVICE_CLASS", new=FakeSignupServiceRaises422))

            resp: Response = self.client.post(self.url, data=valid_payload(), format="json")
            body: Dict[str, Any] = cast(Dict[str, Any], resp.data)
            self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
            self.assertEqual(body.get("error"), "절차 미완료")

    def test_service_raises_409(self) -> None:
        p1, p2 = make_permission_patches(email_sub="john@example.com", phone_sub="01012345678")
        with ExitStack() as stack:
            stack.enter_context(p1)
            stack.enter_context(p2)
            stack.enter_context(mock.patch.object(UserSignupView, "SERVICE_CLASS", new=FakeSignupServiceRaises409))

            resp: Response = self.client.post(self.url, data=valid_payload(), format="json")
            body: Dict[str, Any] = cast(Dict[str, Any], resp.data)

            self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(body.get("error"), "email: 이미 사용 중입니다.")

    def test_service_raises_500(self) -> None:
        p1, p2 = make_permission_patches(email_sub="john@example.com", phone_sub="01012345678")
        with ExitStack() as stack:
            stack.enter_context(p1)
            stack.enter_context(p2)
            stack.enter_context(mock.patch.object(UserSignupView, "SERVICE_CLASS", new=FakeSignupServiceRaises500))

            resp: Response = self.client.post(self.url, data=valid_payload(), format="json")
            body: Dict[str, Any] = cast(Dict[str, Any], resp.data)
            self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertEqual(body.get("error"), "서버 오류")


# ---------------------------------------------------------------------
# 회원가입 서비스 테스트
# ---------------------------------------------------------------------
class SignupServiceTests(IsolatedRedisTestClient):
    @staticmethod
    def payload_base(**overrides: Any) -> SignupPayload:
        base: Dict[str, Any] = {
            "email": "john@example.com",
            "password": "Passw0rd!",
            "nickname": "johnny",
            "name": "John Doe",
            "phone_number": "01012345678",
            "birthday": date(1990, 1, 1),
            "gender": "M",
            "role": Role.USER,
        }
        base.update(overrides)
        return cast(SignupPayload, base)

    def test_role_flag_roundtrip(self) -> None:
        self.assertEqual(role_from_flags(is_staff=False, is_superuser=False), Role.USER.value)
        self.assertEqual(role_from_flags(is_staff=True, is_superuser=False), Role.STAFF.value)
        self.assertEqual(role_from_flags(is_staff=True, is_superuser=True), Role.ADMIN.value)

        self.assertEqual(flags_from_role(Role.USER.value), {"is_staff": False, "is_superuser": False})
        self.assertEqual(flags_from_role(Role.STAFF.value), {"is_staff": True, "is_superuser": False})
        self.assertEqual(flags_from_role(Role.ADMIN.value), {"is_staff": True, "is_superuser": True})

        self.assertEqual(status_from_active(True), "active")
        self.assertEqual(status_from_active(False), "inactive")
        self.assertTrue(active_from_status("active"))
        self.assertFalse(active_from_status("inactive"))

    def test_sign_up_success_user_role(self) -> None:
        svc = DefaultSignupService()

        with (
            mock.patch("apps.users.services.user_signup_service.User.objects.create_user") as create_user,
            mock.patch("apps.users.services.user_signup_service.validate_nickname") as v_nick,
            mock.patch("apps.users.services.user_signup_service.validate_name") as v_name,
            mock.patch("apps.users.services.user_signup_service.validate_korean_phone") as v_phone,
            mock.patch("apps.users.services.user_signup_service.validate_birthday") as v_birth,
        ):

            class DU:
                def __init__(self) -> None:
                    self.email = "john@example.com"
                    self.nickname = "johnny"
                    self.name = "John Doe"
                    self.phone_number = "01012345678"
                    self.birthday = date(1990, 1, 1)
                    self.gender = "M"
                    self.is_staff = False
                    self.is_superuser = False
                    self.is_active = True

            create_user.return_value = DU()

            payload = self.payload_base(role=Role.USER)
            user = svc.sign_up(payload)

            self.assertEqual(user.email, "john@example.com")
            self.assertEqual(user.nickname, "johnny")

            v_nick.assert_called_once_with(payload["nickname"])
            v_name.assert_called_once_with(payload["name"])
            v_phone.assert_called_once_with(payload["phone_number"])
            v_birth.assert_called_once_with(payload["birthday"])

            _, kwargs = create_user.call_args
            self.assertEqual(
                kwargs,
                {
                    "email": "john@example.com",
                    "password": "Passw0rd!",
                    "nickname": "johnny",
                    "name": "John Doe",
                    "phone_number": "01012345678",
                    "birthday": date(1990, 1, 1),
                    "gender": "M",
                    "is_staff": False,
                    "is_superuser": False,
                    "is_active": True,
                },
            )

    def test_sign_up_success_staff_admin_role_and_str(self) -> None:
        svc = DefaultSignupService()

        with (
            mock.patch("apps.users.services.user_signup_service.User.objects.create_user") as create_user,
            mock.patch("apps.users.services.user_signup_service.validate_nickname"),
            mock.patch("apps.users.services.user_signup_service.validate_name"),
            mock.patch("apps.users.services.user_signup_service.validate_korean_phone"),
            mock.patch("apps.users.services.user_signup_service.validate_birthday"),
        ):

            class DU1:
                def __init__(self) -> None:
                    self.email = "john@example.com"
                    self.nickname = "johnny"
                    self.name = "John Doe"
                    self.phone_number = "01012345678"
                    self.birthday = date(1990, 1, 1)
                    self.gender = "M"
                    self.is_staff = True
                    self.is_superuser = False
                    self.is_active = True

            create_user.return_value = DU1()
            svc.sign_up(self.payload_base(role=Role.STAFF))
            _, kw_staff = create_user.call_args
            self.assertTrue(kw_staff["is_staff"])
            self.assertFalse(kw_staff["is_superuser"])

            class DU2:
                def __init__(self) -> None:
                    self.email = "john@example.com"
                    self.nickname = "johnny"
                    self.name = "John Doe"
                    self.phone_number = "01012345678"
                    self.birthday = date(1990, 1, 1)
                    self.gender = "M"
                    self.is_staff = True
                    self.is_superuser = True
                    self.is_active = True

            create_user.return_value = DU2()
            svc.sign_up(self.payload_base(role="admin"))
            _, kw_admin = create_user.call_args
            self.assertTrue(kw_admin["is_staff"])
            self.assertTrue(kw_admin["is_superuser"])

    def test_sign_up_accepts_birthday_str_and_calls_validator(self) -> None:
        svc = DefaultSignupService()

        with (
            mock.patch("apps.users.services.user_signup_service.User.objects.create_user") as create_user,
            mock.patch("apps.users.services.user_signup_service.validate_birthday") as v_birth,
            mock.patch("apps.users.services.user_signup_service.validate_nickname"),
            mock.patch("apps.users.services.user_signup_service.validate_name"),
            mock.patch("apps.users.services.user_signup_service.validate_korean_phone"),
        ):

            class DU:
                def __init__(self) -> None:
                    self.email = "john@example.com"
                    self.nickname = "johnny"
                    self.name = "John Doe"
                    self.phone_number = "01012345678"
                    self.birthday = date(1990, 1, 1)
                    self.gender = "M"
                    self.is_staff = False
                    self.is_superuser = False
                    self.is_active = True

            create_user.return_value = DU()

            payload = self.payload_base(birthday="1990-01-01")
            svc.sign_up(payload)

            v_birth.assert_called_once_with("1990-01-01")

    def test_sign_up_validation_aggregates_field_errors(self) -> None:
        svc = DefaultSignupService()

        with (
            mock.patch("apps.users.services.user_signup_service.validate_nickname") as v_nick,
            mock.patch("apps.users.services.user_signup_service.validate_name") as v_name,
            mock.patch("apps.users.services.user_signup_service.validate_korean_phone") as v_phone,
            mock.patch("apps.users.services.user_signup_service.validate_birthday") as v_birth,
        ):
            v_nick.side_effect = ValidationError("닉네임 형식 오류")
            v_name.side_effect = ValidationError("이름 형식 오류")
            v_phone.side_effect = ValidationError("휴대폰 형식 오류")
            v_birth.side_effect = ValidationError("생년월일 형식 오류")

            with self.assertRaises(ValidationError) as ei:
                svc.sign_up(self.payload_base())

            err = ei.exception
            self.assertIsInstance(err.detail, dict)
            d = cast(Dict[str, Any], err.detail)
            self.assertTrue(d.keys() >= {"nickname", "name", "phone_number", "birthday"})
            self.assertTrue(any("닉네임" in str(x) for x in d["nickname"]))
            self.assertTrue(any("이름" in str(x) for x in d["name"]))
            self.assertTrue(any("휴대폰" in str(x) for x in d["phone_number"]))
            self.assertTrue(any("생년월일" in str(x) for x in d["birthday"]))

            with mock.patch("apps.users.services.user_signup_service.User.objects.create_user") as create_user_2:
                v_nick.side_effect = ValidationError("닉네임 형식 오류")
                with self.assertRaises(ValidationError):
                    svc.sign_up(self.payload_base())
                create_user_2.assert_not_called()

    def test_sign_up_integrity_error_mapping_to_409(self) -> None:
        svc = DefaultSignupService()

        cases = [
            ("duplicate key value violates unique constraint users_email_key", "email"),
            ("... unique constraint users_phone_number_key ...", "phone_number"),
            ("... duplicate key on users_nickname_key ...", "nickname"),
            ("some unknown unique violation", "non_field_errors"),
        ]

        for msg, expected_field in cases:
            with (
                mock.patch("apps.users.services.user_signup_service.User.objects.create_user") as create_user,
                mock.patch("apps.users.services.user_signup_service.validate_nickname"),
                mock.patch("apps.users.services.user_signup_service.validate_name"),
                mock.patch("apps.users.services.user_signup_service.validate_korean_phone"),
                mock.patch("apps.users.services.user_signup_service.validate_birthday"),
            ):
                create_user.side_effect = IntegrityError(msg)

                with self.assertRaises(APIException) as ei:
                    svc.sign_up(self.payload_base())

                exc = ei.exception
                self.assertEqual(getattr(exc, "status_code", None), 409)
                self.assertIsInstance(exc.detail, dict)
                d = cast(Mapping[str, Any], exc.detail)
                self.assertIn(expected_field, d)

    # ---------------------------------------------------------------------
    # _extract_msgs 유틸 테스트
    # ---------------------------------------------------------------------

    def test__extract_msgs_with_detail_dict_mixed(self) -> None:
        # detail이 dict 형태 (list + 단일 문자열 혼합)
        exc = DRFValidationError(
            detail={
                "email": ["이미 사용 중입니다.", "형식이 올바르지 않습니다."],
                "name": "필수 입력값입니다.",
            }
        )
        msgs = _extract_msgs(exc)
        self.assertEqual(len(msgs), 3)
        self.assertIn("이미 사용 중입니다.", msgs)
        self.assertIn("형식이 올바르지 않습니다.", msgs)
        self.assertIn("필수 입력값입니다.", msgs)

    def test__extract_msgs_with_detail_dict_all_lists(self) -> None:
        exc = DRFValidationError(
            detail={
                "nickname": ["사용 불가 문자 포함"],
                "phone_number": ["형식 오류", "이미 사용 중"],
            }
        )
        msgs = _extract_msgs(exc)
        self.assertEqual(len(msgs), 3)
        self.assertEqual(set(msgs), {"사용 불가 문자 포함", "형식 오류", "이미 사용 중"})

    def test__extract_msgs_detail_scalar(self) -> None:
        # detail이 문자열일 때 (if detail is not None 분기)
        exc = DRFValidationError("단일 에러 메시지")
        msgs = _extract_msgs(exc)
        self.assertEqual(msgs, ["단일 에러 메시지"])

    def test__extract_msgs_message_dict(self) -> None:
        # message_dict 속성을 가진 ValidationError (dict 형태)
        exc = DjangoValidationError({"field1": ["msg1", "msg2"], "field2": "msg3"})
        msgs = _extract_msgs(exc)
        self.assertEqual(len(msgs), 3)
        self.assertIn("msg1", msgs)
        self.assertIn("msg2", msgs)
        self.assertIn("msg3", msgs)

    def test__extract_msgs_messages_list(self) -> None:
        # messages 속성이 list인 경우
        exc = DjangoValidationError(["a", "b", "c"])
        msgs = _extract_msgs(exc)
        self.assertEqual(msgs, ["a", "b", "c"])

    def test__extract_msgs_fallback_str(self) -> None:
        # 위 조건에 모두 해당하지 않을 때 (fallback: str(exc))
        class WeirdExc(Exception):
            pass

        exc = WeirdExc("fallback here")
        msgs = _extract_msgs(exc)
        self.assertEqual(msgs, ["fallback here"])
