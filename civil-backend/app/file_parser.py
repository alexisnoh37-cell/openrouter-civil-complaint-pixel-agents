import io
from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas import ComplaintRequest


COMPLAINT_NO_COLUMNS = ["complaint_no", "complaint_number", "민원신청번호", "신청번호", "접수번호"]
TITLE_COLUMNS = ["title", "subject", "제목", "민원제목", "건명"]
BODY_COLUMNS = ["body", "content", "description", "본문", "내용", "민원내용", "신청내용"]


def _pick_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {column.lower().strip(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _from_table(df: pd.DataFrame, fallback_no: str, fallback_title: str) -> ComplaintRequest:
    if df.empty:
        return ComplaintRequest(
            complaint_no=fallback_no,
            title=fallback_title,
            body="",
        )

    columns = [str(column) for column in df.columns]
    no_col = _pick_column(columns, COMPLAINT_NO_COLUMNS)
    title_col = _pick_column(columns, TITLE_COLUMNS)
    body_col = _pick_column(columns, BODY_COLUMNS)
    row = df.iloc[0]

    complaint_no = _text(row.get(no_col)) if no_col else fallback_no
    title = _text(row.get(title_col)) if title_col else fallback_title

    if body_col:
        body = _text(row.get(body_col))
    else:
        visible_values = [_text(row.get(column)) for column in columns]
        body = "\n".join(value for value in visible_values if value)

    return ComplaintRequest(
        complaint_no=complaint_no or fallback_no,
        title=title or fallback_title,
        body=body,
    )


def _decode_text(content: bytes) -> str:
    for encoding in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _from_plain_text(content: bytes, fallback_no: str, fallback_title: str) -> ComplaintRequest:
    text = _decode_text(content).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else fallback_title
    body = "\n".join(lines[1:]) if len(lines) > 1 else text
    return ComplaintRequest(complaint_no=fallback_no, title=title, body=body)


def parse_complaint_file(filename: str, content: bytes) -> ComplaintRequest:
    """Extract a single complaint from txt/csv/xlsx content for the MVP upload flow."""
    path = Path(filename)
    suffix = path.suffix.lower()
    fallback_no = path.stem or "uploaded-file"
    fallback_title = path.stem or "업로드 민원"

    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(io.BytesIO(content))
        return _from_table(df, fallback_no, fallback_title)

    if suffix == ".csv":
        text = _decode_text(content)
        df = pd.read_csv(io.StringIO(text))
        return _from_table(df, fallback_no, fallback_title)

    if suffix in {".txt", ".md"}:
        return _from_plain_text(content, fallback_no, fallback_title)

    raise ValueError("지원하지 않는 파일 형식입니다. txt, csv, xlsx 파일을 업로드해 주세요.")

