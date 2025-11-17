# 이미지 확장자
ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "tiff",
    "webp",
}

# 첨부 파일 확장자
ALLOWED_ATTACHMENT_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "txt",
    "csv",
    "md",
    "hwp",
}

# 확장자별 MIME 타입 매핑
IMAGE_MIME_BY_EXT = {
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "gif": {"image/gif"},
    "bmp": {"image/bmp", "image/x-ms-bmp"},
    "tiff": {"image/tiff"},
    "webp": {"image/webp"},
}

ATTACHMENT_MIME_BY_EXT = {
    "pdf": {"application/pdf"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "ppt": {"application/vnd.ms-powerpoint"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "txt": {"text/plain"},
    "csv": {"text/csv", "application/csv"},
    "md": {"text/markdown", "text/x-markdown"},
    "hwp": {"application/x-hwp", "application/haansofthwp"},
}
