"""Read an uploaded bill and turn it into something the agent can argue from.

Three things this has to survive, all of which were reaching the browser as an
unreadable "Failed to fetch":

  - Gemini returns 503 "experiencing high demand" fairly often. That is
    transient, so it is retried rather than surfaced.
  - An unreadable or unsupported file makes Gemini answer 400. That is the
    user's problem to fix, so it comes back as a 422 that says which file.
  - Any uncaught exception produced a bare 500, and FastAPI's CORS middleware
    does not attach headers to those - so the browser could not read the error
    and reported a network failure instead. Everything is caught here now.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from google.genai import errors as genai_errors
from google.genai import types

from app.config import settings
from app.models import BillExtraction
from app.security import require_user_id
from app.services import quota
from app.services.ratelimit import limit
from app.services.gemini import GeminiNotConfigured, get_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bills", tags=["bills"])

MAX_BYTES = 20 * 1024 * 1024  # Gemini inline data cap, with room to spare

# A saturated model stays saturated for minutes, so the second attempt goes to
# a different model rather than the same one again. Only the last model in the
# chain is worth waiting between attempts for.
RETRY_DELAY = 2.0

# file.content_type is whatever the browser felt like sending - Chrome reports
# application/octet-stream for a .PDF often enough to matter, and Gemini
# rejects that with a 400 that looks like a bad document.
#
# Everything here is a format Gemini reads directly. Office documents are not:
# a .docx would need converting first, so it is refused with a message that
# says what to do instead rather than failing deep inside the model.
EXTENSION_MIME = {
    # Documents
    "pdf": "application/pdf",
    # Photos of a bill, which is how most people will send one
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "jpe": "image/jpeg",
    "webp": "image/webp",
    "heic": "image/heic",
    "heif": "image/heif",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "avif": "image/avif",
    # Exports and statements people already have as text
    "txt": "text/plain",
    "csv": "text/csv",
    "md": "text/markdown",
    "html": "text/html",
    "htm": "text/html",
    "json": "text/plain",
    "xml": "text/plain",
    "rtf": "text/plain",
}

# Recognised, but not something the model can read - worth naming so the
# message can tell the customer what to do instead of "unsupported".
CONVERT_FIRST = {
    "doc", "docx", "odt", "pages",
    "xls", "xlsx", "ods", "numbers",
    "ppt", "pptx", "key",
}

EXTRACTION_PROMPT = """You are reading a customer's bill so that a negotiator can argue it down.

Extract every field in the schema that the document supports. Be thorough: a field \
left blank is an argument the negotiator cannot make. Read the itemisation carefully - \
equipment rental, service fees, broadcast and regional sports fees, and administrative \
charges are the line items most often waived, so capture each one separately.

Then decide what a phone call about this document should actually try to achieve, and \
say so in call_objective and objective_summary. This matters: not every document is a \
bill to argue down. A receipt for a faulty or unwanted purchase wants a refund. A \
duplicated charge wants disputing. A subscription someone is done with wants \
cancelling. A hospital bill someone cannot pay at once wants a payment plan. Choosing \
'reduce_recurring_rate' for a one-off marketplace purchase would send the agent to ask \
a merchant to lower a price that has already been paid, which is nonsense.

Rules:
- Never invent a value. If something genuinely is not on the document, leave it out.
- current_rate is the recurring monthly charge. amount_due is the total on this \
statement. They are often different; do not conflate them.
- Use the document's own currency and report it in `currency`.
- Set document_type and is_negotiable honestly. A shop or marketplace receipt for a \
one-off purchase is a 'retail_receipt' and is NOT negotiable, no matter how large the \
total - but it may still justify a refund or dispute call, so set call_objective \
accordingly rather than giving up on it.
- objective_summary should name the specific thing to ask for and the reason this \
document supports it, in one sentence a customer would recognise as their own situation.
- Put anything else worth raising on the call - an expiring promotion, a recent price \
rise, a late fee, a long tenure, a charge that appears twice - into `notes`."""


def _mime_for(file: UploadFile) -> str:
    extension = (file.filename or "").rsplit(".", 1)[-1].lower()
    if extension in EXTENSION_MIME:
        return EXTENSION_MIME[extension]

    if extension in CONVERT_FIRST:
        raise HTTPException(
            status_code=422,
            detail=(
                "convert_first: that's an office document. Export it as a PDF, or "
                "send a photo or screenshot of the bill."
            ),
        )

    declared = (file.content_type or "").lower()
    if (
        declared.startswith("image/")
        or declared.startswith("text/")
        or declared == "application/pdf"
    ):
        return declared

    raise HTTPException(
        status_code=422,
        detail="unsupported_file_type: upload a PDF, a photo, or a screenshot of the bill",
    )


@router.post("/ingest", response_model=BillExtraction)
async def ingest_bill(
    file: UploadFile, user_id: str = Depends(require_user_id)
) -> BillExtraction:
    """Extract the bill's details via Gemini multimodal.

    Gemini is used here rather than AssemblyAI's LLM Gateway because this is
    genuinely multimodal - a photo or PDF - and the Gateway's chat completions
    are text only.
    """
    # Every call here spends Gemini quota.
    limit(f"ingest:{user_id}", max_calls=20, per_seconds=300)

    # Validate the upload before anything else: a .docx is the caller's mistake
    # whether or not the server happens to be configured, and telling them
    # "service unavailable" for it sends them chasing the wrong problem.
    mime_type = _mime_for(file)

    # Refuse on the declared size before reading a byte. Checking after
    # file.read() meant a request could spool an unbounded amount to disk
    # first, and only then be told it was too large.
    declared = file.size if file.size is not None else 0
    if declared > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large: 20MB maximum")

    # A declared size can lie, so the read is bounded as well: one byte past
    # the cap is enough to know.
    data = await file.read(MAX_BYTES + 1)

    if not data:
        raise HTTPException(status_code=422, detail="empty_file")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large: 20MB maximum")

    try:
        client = get_client()
    except GeminiNotConfigured as exc:
        raise HTTPException(status_code=503, detail="gemini_not_configured") from exc

    # The free plan's allowance is spent here, because a bill is the unit of
    # work a customer thinks in and everything downstream - the negotiation and
    # its calls - follows from one. Counted after the upload has been checked,
    # so a file that was never going to work does not cost an allowance, and
    # before the model is called, so it gates the spend rather than reporting
    # it afterwards.
    charged = await quota.consume_bill(user_id)

    chain = settings.gemini_model_chain
    response = None
    last_error: Exception | None = None

    for index, model in enumerate(chain):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=data, mime_type=mime_type),
                    EXTRACTION_PROMPT,
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": BillExtraction,
                },
            )
            if index:
                logger.info("Extraction fell back to %s", model)
            break

        except genai_errors.ServerError as exc:
            # "This model is currently experiencing high demand" can persist for
            # minutes, so move to the next model instead of asking the same one
            # again - that retry loop is exactly how extraction kept failing.
            last_error = exc
            logger.warning("%s unavailable, trying the next model: %s", model, exc)

        except genai_errors.ClientError as exc:
            status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if status in (404, 429):
                # Not available to this key, or its quota is spent. Another
                # model may well be fine.
                last_error = exc
                logger.warning("%s unusable (%s), trying the next model", model, status)
                continue
            # A 400 is the document, not the model - every model will reject it.
            logger.info("Gemini rejected the upload %r: %s", file.filename, exc)
            if charged:
                await quota.refund_bill(user_id)
            raise HTTPException(
                status_code=422,
                detail="unreadable_document: the file couldn't be read as a bill",
            ) from exc

        # One short pause before the final model, in case the whole region is
        # briefly busy rather than one model being saturated.
        if index == len(chain) - 2:
            await asyncio.sleep(RETRY_DELAY)

    # From here on, every exit that is not a successful extraction hands the
    # allowance back. A free account has five bills a month, and losing one to
    # a busy model or a malformed response would be charging someone a fifth of
    # their month for our failure.
    if response is None:
        logger.error("Every extraction model failed for %r: %s", file.filename, last_error)
        if charged:
            await quota.refund_bill(user_id)
        raise HTTPException(
            status_code=503,
            detail="extraction_busy: every extraction model is busy, try again shortly",
        )

    if not response.text:
        if charged:
            await quota.refund_bill(user_id)
        raise HTTPException(status_code=502, detail="empty_extraction_response")

    try:
        return BillExtraction.model_validate_json(response.text)
    except ValueError as exc:
        logger.error("Extraction did not match the schema: %s", exc)
        if charged:
            await quota.refund_bill(user_id)
        raise HTTPException(status_code=502, detail="malformed_extraction") from exc
