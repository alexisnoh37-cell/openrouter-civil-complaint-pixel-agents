import json
from typing import AsyncGenerator

from fastapi import FastAPI, File, Form, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.file_parser import parse_complaint_file
from app.orchestrator import process_complaint, stream_process_complaint
from app.schemas import ComplaintRequest, ProcessResponse


app = FastAPI(title="Civil Complaint Agent MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process", response_model=ProcessResponse)
async def process(complaint: ComplaintRequest) -> ProcessResponse:
    return await process_complaint(complaint)


async def complaint_from_upload(
    file: UploadFile,
    complaint_no: str | None = None,
    title: str | None = None,
    body: str | None = None,
) -> ComplaintRequest:
    content = await file.read()
    parsed = parse_complaint_file(file.filename or "complaint.txt", content)
    return ComplaintRequest(
        complaint_no=complaint_no or parsed.complaint_no,
        title=title or parsed.title,
        body=body or parsed.body,
    )


@app.post("/process/file", response_model=ProcessResponse)
async def process_file(
    file: UploadFile = File(...),
    complaint_no: str | None = Form(None),
    title: str | None = Form(None),
    body: str | None = Form(None),
) -> ProcessResponse:
    complaint = await complaint_from_upload(file, complaint_no, title, body)
    return await process_complaint(complaint)


def sse_line(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def sse_generator(complaint: ComplaintRequest) -> AsyncGenerator[str, None]:
    async for event in stream_process_complaint(complaint):
        yield sse_line(event.model_dump(exclude_none=True))


@app.get("/process/stream")
async def process_stream_get(
    complaint_no: str = Query(...),
    title: str = Query(...),
    body: str = Query(...),
) -> StreamingResponse:
    complaint = ComplaintRequest(complaint_no=complaint_no, title=title, body=body)
    return StreamingResponse(sse_generator(complaint), media_type="text/event-stream")


@app.post("/process/stream")
async def process_stream_post(complaint: ComplaintRequest) -> StreamingResponse:
    return StreamingResponse(sse_generator(complaint), media_type="text/event-stream")


@app.post("/process/file/stream")
async def process_file_stream(
    file: UploadFile = File(...),
    complaint_no: str | None = Form(None),
    title: str | None = Form(None),
    body: str | None = Form(None),
) -> StreamingResponse:
    complaint = await complaint_from_upload(file, complaint_no, title, body)
    return StreamingResponse(sse_generator(complaint), media_type="text/event-stream")
