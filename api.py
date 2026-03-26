import base64
import os
import re
import time
from contextlib import suppress
from io import BytesIO
from uuid import uuid4

from loguru import logger
import markdownify
import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

app = FastAPI(title="Chandra OCR API", version="0.1.0")

BBOX_SCALE = 1000



OCR_LAYOUT_PROMPT = """ You are an OCR engine that extracts text and layout information from images. extract from the image"""


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = uuid4().hex[:8]
    client_host = request.client.host if request.client else "unknown"
    started_at = time.perf_counter()

    logger.info(
        "[{request_id}] Incoming {method} {path} from {client_host}",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_host=client_host,
    )

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "[{request_id}] Failed {method} {path} after {elapsed_ms:.2f} ms",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            elapsed_ms=elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "[{request_id}] Completed {method} {path} with {status_code} in {elapsed_ms:.2f} ms",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=elapsed_ms,
    )
    return response


def image_bytes_to_data_url(image_bytes: bytes) -> tuple[str, tuple[int, int]]:
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as error:
        raise HTTPException(
            status_code=400, detail=f"Invalid image file: {error}"
        ) from error

    width, height = image.size
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}", (width, height)


def build_payload(model: str, data_url: str, prompt: str, max_tokens: int) -> dict:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }


def call_chandra(api_base: str, payload: dict, timeout: int) -> str:
    try:
        response = requests.post(
            f"{api_base.rstrip('/')}/chat/completions",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        logger.info("Chandra upstream responded with status {data}", data=data)

        return data["choices"][0]["message"]["content"]
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502, detail=f"Chandra API request failed: {error}"
        ) from error
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(
            status_code=502, detail=f"Unexpected Chandra response format: {error}"
        ) from error


def parse_chunks(html: str, image_size: tuple[int, int]) -> list[dict]:
    """Parse Chandra's HTML output into chunks with pixel-coordinate bounding boxes."""
    width, height = image_size
    chunks = []
    pattern = re.compile(
        r'<div\s+[^>]*?data-bbox="([^"]*)"[^>]*?data-label="([^"]*)"[^>]*?>(.*?)</div>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        bbox_str, label, content = match.group(1), match.group(2), match.group(3)
        try:
            x0, y0, x1, y1 = (int(v) for v in bbox_str.split())
            bbox_px = [
                round(x0 * width / BBOX_SCALE),
                round(y0 * height / BBOX_SCALE),
                round(x1 * width / BBOX_SCALE),
                round(y1 * height / BBOX_SCALE),
            ]
        except (ValueError, TypeError):
            bbox_px = None
        chunks.append(
            {
                "bbox": bbox_px,
                "label": label,
                "content": content.strip(),
            }
        )
    return chunks


def html_to_markdown(html: str) -> str:
    """Convert Chandra's HTML output to markdown."""
    return markdownify.markdownify(html, heading_style="ATX", strip=["div"]).strip()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ocr/image")
async def ocr_image(
    file: UploadFile = File(...),
    max_tokens: int = Form(12384),
    model: str = Form("chandra"),
) -> JSONResponse:
    """Extract OCR with markdown output, bounding boxes, and layout labels in a single call."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    api_base = os.getenv("CHANDRA_API_BASE", "http://192.168.9.1:8000/v1")
    timeout = int(os.getenv("CHANDRA_TIMEOUT", "600"))

    logger.info(
        "OCR request received for filename={filename} content_type={content_type} size_bytes={size_bytes} model={model} max_tokens={max_tokens}",
        filename=file.filename or "unknown",
        content_type=file.content_type,
        size_bytes=len(image_bytes),
        model=model,
        max_tokens=max_tokens,
    )

    data_url, image_size = image_bytes_to_data_url(image_bytes)
    payload = build_payload(
        model=model, data_url=data_url, prompt=OCR_LAYOUT_PROMPT, max_tokens=max_tokens
    )
    raw_html = call_chandra(api_base=api_base, payload=payload, timeout=timeout)
    chunks = parse_chunks(raw_html, image_size)
    markdown = html_to_markdown(raw_html)

    logger.info(
        "OCR completed for filename={filename} with {chunk_count} chunk(s) at image_size={image_size}",
        filename=file.filename or "unknown",
        chunk_count=len(chunks),
        image_size=image_size,
    )

    with suppress(Exception):
        await file.close()

    return JSONResponse(
        {
            "filename": file.filename,
            "model": model,
            "api_base": api_base,
            "image_size": {"width": image_size[0], "height": image_size[1]},
            "markdown": markdown,
            "raw_html": raw_html,
            "chunks": chunks,
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8080, reload=False)
