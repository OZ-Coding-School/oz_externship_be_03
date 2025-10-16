from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.response import Response
from .models import StudyNote, StudyGroup
from .serializers import StudyNoteSerializer, StudyNoteCreateSerializer

#StudyNote 목록보기get새로 작성하기post 둘다보기용도
class StudyNoteListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/studies/notes/?group_id=3
    POST /api/v1/studies/notes/?group_id=3
    """
    #로그인한 사용자만 가능하게 만듬
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        #URL 쿼리에서 group_id(그룹 번호)를 가져옴
        group_id = self.request.query_params.get("group_id")
        if not group_id:
            #group_id가 없으면 에러를 발생시킴
            raise NotFound("group_id 쿼리 파라미터가 필요합니다.")
        #해당 그룹의 노트들만 필터링하게함 
        return StudyNote.objects.filter(group_id=group_id)
    #요청이 post인지 get인지에 따라 사용할 시리얼라이저를 다르게 
    def get_serializer_class(self):
        #post일 땐 제목/내용만 받는 간단한 시리얼라이저 사용
        if self.request.method == "POST":
            return StudyNoteCreateSerializer
        #get일 땐 전체 정보를 보여주는 시리얼라이저 사용
        return StudyNoteSerializer

    def perform_create(self, serializer):
        #쿼리에서 group_id 가져오기 없으면 에러뜨게 뜨게만들었으
        group_id = self.request.query_params.get("group_id")
        if not group_id:
            raise NotFound("group_id 쿼리 파라미터가 필요합니다.")

        try:
            group = StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            raise NotFound("해당 스터디 그룹을 찾을 수 없습니다.")
        #노트를 저장할 때 작성자랑 그룹 함께 저장
        note = serializer.save(author=self.request.user, group=group)
        
        #요약비면 임시문장뜨게하기
        if not note.summary:
            note.summary = f"{note.title}에 대한 자동 요약입니다."
            note.save()

#StudyNote 하나만 보기get이랑 수정하기patch 담당
class StudyNoteDetailView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/studies/notes/{note_id}/ 
    PATCH /api/v1/studies/notes/{note_id}/
    """
    #로그인한 유저만 가능하게
    permission_classes = [permissions.IsAuthenticated]
    #사용할 시리얼라이저
    serializer_class = StudyNoteSerializer
    #url에서 note_id값 가져올떄이름
    lookup_url_kwarg = "note_id"
    #어떤데이터 수정조회할지 선택
    def get_queryset(self):
        return StudyNote.objects.all() #전체중에서 찾기 

    #patch요청시 수정되는부분
    def perform_update(self, serializer):
        note = self.get_object()
        #수정할거만 가져오고 작성자가아니면 수정불가능하게
        if note.author != self.request.user:
            raise PermissionDenied("작성자만 수정할 수 있습니다.")
        updated_note = serializer.save()

        updated_note.summary = f"{updated_note.title}의 내용이 수정되었습니다."
        updated_note.save()
