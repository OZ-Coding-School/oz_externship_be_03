from rest_framework.pagination import PageNumberPagination


class StudyGroupPagination(PageNumberPagination):
    page_size = 9
