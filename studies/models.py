from django. db import models 
from django.conf import settings


class StudyGroup(models.Model):

    name = models.CharField(max_length=50)
    #제목만 있는 스터디그룹도 존재할수있어서 소개는 blank/null처리했습니다
    description = models.TextField(blank=True, null=True)
    #생성 시각 자동기록 순서대로 정렬되게 만들기위해 
    created_at = models.DateTimeField(auto_now_add=True)   
    #디버깅용도 
    def __str__(self):
        return self.name
    
class StudyNote(models.Model):

    #어느 그룹의 노트인지 FK로 연결, 그룹 삭제 시 노트도 함께 삭제해 그룹삭제되면 내용도 같이사라지게만듬
    #related_name="notes"로 역참조해서  group.notes로 접근 가능
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="notes")
    # 유저 삭제 시 노트도 함께 삭제되게 만들었습니다
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_notes")
    # 노트 제목은 검색/리스트에 쓰이므로 가변 텍스트 CharField, 
    title = models.CharField(max_length=50)
    #본문은 길이 제한이 크지 않으므로 TextField 사용했습니다
    content = models.TextField()
    #요약은 선택필드(blank/null)로 아예 비워도되게하기
    summary = models.TextField(blank=True, null=True)  
    #생성시각 자동기록 처음작성 확인
    created_at = models.DateTimeField(auto_now_add=True)
    #수정시각 자동갱신 변경이력 확인
    updated_at = models.DateTimeField(auto_now=True)

    #기본 정렬을 최신순으로 노출되게
    class Meta:
        ordering = ["-created_at"]
    #관리자가 보기편하게 문자로 작성
    def __str__(self):
        return f"[{self.group.name}] {self.title} by {self.author}"
