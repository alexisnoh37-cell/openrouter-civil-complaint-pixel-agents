from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT_DIR / "data" / "similar_cases.xlsx"


def _pick_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {column.lower().strip(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]
    return None


def search_similar_cases(title: str, body: str, top_k: int = 3) -> dict[str, Any]:
    """Search local Excel examples with TF-IDF. Missing or malformed files return empty results."""
    if not DATA_FILE.exists():
        return {
            "similar_cases": [],
            "recommended_answer_pattern": "유사민원 파일이 없어 추천 답변 패턴을 생성하지 않았습니다.",
        }

    try:
        df = pd.read_excel(DATA_FILE)
    except Exception as exc:
        return {
            "similar_cases": [],
            "recommended_answer_pattern": f"유사민원 파일을 읽지 못했습니다: {exc}",
        }

    if df.empty:
        return {
            "similar_cases": [],
            "recommended_answer_pattern": "유사민원 데이터가 비어 있습니다.",
        }

    columns = [str(column) for column in df.columns]
    title_col = _pick_column(columns, ["title", "제목", "민원제목"])
    body_col = _pick_column(columns, ["body", "본문", "민원내용", "내용"])
    answer_col = _pick_column(columns, ["answer", "답변", "처리결과", "답변내용"])
    category_col = _pick_column(columns, ["category", "분류", "유형"])

    if not title_col and not body_col:
        return {
            "similar_cases": [],
            "recommended_answer_pattern": "제목 또는 본문 컬럼을 찾지 못했습니다.",
        }

    def row_text(row: pd.Series) -> str:
        parts = []
        if title_col:
            parts.append(str(row.get(title_col, "")))
        if body_col:
            parts.append(str(row.get(body_col, "")))
        return " ".join(parts)

    corpus = [row_text(row) for _, row in df.iterrows()]
    query = f"{title} {body}"

    try:
        vectorizer = TfidfVectorizer()
        matrix = vectorizer.fit_transform(corpus + [query])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    except Exception as exc:
        return {
            "similar_cases": [],
            "recommended_answer_pattern": f"유사도 계산에 실패했습니다: {exc}",
        }

    ranked_indices = scores.argsort()[::-1][:top_k]
    similar_cases = []
    answer_samples = []

    for index in ranked_indices:
        score = float(scores[index])
        if score <= 0:
            continue
        row = df.iloc[int(index)]
        answer = str(row.get(answer_col, "")) if answer_col else ""
        if answer:
            answer_samples.append(answer)
        similar_cases.append(
            {
                "score": round(score, 4),
                "title": str(row.get(title_col, "")) if title_col else "",
                "body": str(row.get(body_col, "")) if body_col else "",
                "category": str(row.get(category_col, "")) if category_col else "",
                "answer": answer,
            }
        )

    recommended = (
        " / ".join(answer_samples[:2])
        if answer_samples
        else "유사도가 높은 기존 답변 패턴을 찾지 못했습니다."
    )
    return {"similar_cases": similar_cases, "recommended_answer_pattern": recommended}

