from typing import Any, Dict

from rest_framework import serializers, status
from rest_framework.response import Response


class KakaoAuthRequestSerializer(serializers.Serializer[Any]):
    code = serializers.CharField(help_text="카카오 로그인 인가 코드")


class NaverSocialRequestSerializer(serializers.Serializer[Any]):
    code = serializers.CharField(help_text="네이버 로그인 인가 코드")
    state = serializers.CharField(help_text="네이버 로그인 시 필요한 state 값")


class KakaoSocialResponseSerializer(serializers.Serializer[Any]):
    detail = serializers.CharField(help_text="카카오 로그인이 완료되었습니다.", required=True)
    data = serializers.DictField(
        child=serializers.CharField(), help_text="JWT 토큰 데이터", required=True
    )

    @classmethod
    def from_service_result(cls, result: Dict[str, Any]) -> Response:
        data = {
            "detail": result.get("detail", "카카오 로그인이 완료되었습니다."),
            "data": {
                "access_token": result.get("data", {}).get("access"),
            },
        }
        serializer = cls(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class NaverSocialResponseSerializer(serializers.Serializer[Any]):
    detail = serializers.CharField(help_text="네이버 로그인이 완료되었습니다.", required=True)
    data = serializers.DictField(
        child=serializers.CharField(), help_text="JWT 토큰 데이터", required=True
    )

    @classmethod
    def from_service_result(cls, result: Dict[str, Any]) -> Response:
        data = {
            "detail": result.get("detail", "네이버 로그인이 완료되었습니다."),
            "data": {
                "access_token": result.get("data", {}).get("access"),
            },
        }
        serializer = cls(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)