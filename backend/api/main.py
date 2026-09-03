"""FastAPI app — Phase 1 through 4.

Accepts uploaded files (PDF, image, text) or pasted text, stores files in
Supabase Storage, extracts raw text, performs LLM-based field extraction
with dual-provider fallback, and cross-references against transaction
history and GST rules knowledge base.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.cross_reference import ensure_models_loaded, init_connection_pool
from agent.llm_client import get_llm_client
from db.supabase_client import build_client
from parser.text_extraction import extract_text
from tenancy import (
    TenantCredentials,
    get_store,
    get_tenant,
    resolve_tenant_id,
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: preload the embedding model + DB pool so the first request is fast.

    Loading sentence-transformers on the first user request would otherwise
    stall it for many seconds. Preloading here (in a thread) moves that cost
    to startup.
    """
    import asyncio

    asyncio.get_running_loop().run_in_executor(None, _startup_warmup)
    try:
        yield
    finally:
        pass


def _startup_warmup() -> None:
    """Run blocking warmup (embedding model + DB pool) off the event loop."""
    try:
        init_connection_pool()
        log.info("Warmup: DB connection pool initialized")
    except Exception as e:
        log.warning("Warmup: DB pool init failed: %s", e)

    try:
        ensure_models_loaded()
        log.info("Warmup: embedding model loaded")
    except Exception as e:
        log.warning("Warmup: embedding model load failed: %s", e)


app = FastAPI(title="GST Saathi", version="0.4.0", lifespan=lifespan)

_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:7860",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """Return a clean JSON error instead of a raw 500 with a full traceback."""
    log.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )

BUCKET = "notice-uploads"


def _tenant_creds_from_header(x_tenant_id: str | None) -> TenantCredentials | None:
    """Return the tenant's stored credentials via the X-Tenant-ID header."""
    return get_tenant(x_tenant_id)


class CredentialsRequest(BaseModel):
    """User-supplied credentials for a tenant/session (all optional).

    Stored in-memory only. Never written to disk or returned to clients.
    A tenant can clear credentials by posting all-empty fields (or via DELETE).
    """

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    database_url: str | None = None
    groq_api_key: str | None = None
    groq_model: str | None = None
    google_api_key: str | None = None
    google_model: str | None = None
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None


@app.post("/api/credentials")
async def set_credentials(req: CredentialsRequest, x_tenant_id: str | None = Header(default=None)) -> dict:
    """Store a tenant's own API/DB/Razorpay credentials in memory.

    Every user must supply at least one LLM key and at least one of Supabase /
    Postgres to use this application. Send an empty body to clear the tenant's
    credentials.
    """
    tenant_id = resolve_tenant_id(x_tenant_id)
    creds = TenantCredentials(
        supabase_url=req.supabase_url or None,
        supabase_service_role_key=req.supabase_service_role_key or None,
        database_url=req.database_url or None,
        groq_api_key=req.groq_api_key or None,
        groq_model=req.groq_model or None,
        google_api_key=req.google_api_key or None,
        google_model=req.google_model or None,
        razorpay_key_id=req.razorpay_key_id or None,
        razorpay_key_secret=req.razorpay_key_secret or None,
        paypal_client_id=req.paypal_client_id or None,
        paypal_client_secret=req.paypal_client_secret or None,
    )

    if creds.any_set():
        # Validate that required fields are present.
        missing = creds.validate_required()
        if missing:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Missing required credentials",
                    "missing": missing,
                    "tenant_id": tenant_id,
                },
            )
        get_store().put(tenant_id, creds)
        # Drop any cached per-tenant LLM client so the new keys take effect.
        from agent import llm_client as _llm
        _llm._llm_clients.pop(tenant_id, None)
        _llm._llm_clients.pop("default" if tenant_id == "default" else "", None)
        status = "configured"
        log.info("Credentials stored for tenant '%s'", tenant_id)
    else:
        get_store().clear(tenant_id)
        from agent import llm_client as _llm
        _llm._llm_clients.pop(tenant_id, None)
        status = "cleared"
        log.info("Credentials cleared for tenant '%s'", tenant_id)

    return {"tenant_id": tenant_id, "status": status}


@app.delete("/api/credentials")
async def clear_credentials(x_tenant_id: str | None = Header(default=None)) -> dict:
    """Clear stored credentials for a tenant (fall back to global .env)."""
    tenant_id = resolve_tenant_id(x_tenant_id)
    get_store().clear(tenant_id)
    from agent import llm_client as _llm
    _llm._llm_clients.pop(tenant_id, None)
    return {"tenant_id": tenant_id, "status": "cleared"}


class ValidateRequest(BaseModel):
    """Request body for key validation — same shape as CredentialsRequest."""

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    database_url: str | None = None
    groq_api_key: str | None = None
    groq_model: str | None = None
    google_api_key: str | None = None
    google_model: str | None = None
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None


async def _validate_supabase(url: str, key: str) -> dict:
    """Hit Supabase REST API to confirm credentials work."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                f"{url.rstrip('/')}/rest/v1/",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                },
            )
            ok = resp.status_code in (200, 204)
            return {"ok": ok, "error": None if ok else f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


async def _validate_database(database_url: str) -> dict:
    """Quick connect test against the Postgres DATABASE_URL."""
    try:
        import asyncpg

        conn = await asyncpg.connect(database_url, timeout=8)
        await conn.close()
        return {"ok": True, "error": None}
    except ImportError:
        # asyncpg may not be installed — fall back to psycopg
        try:
            import psycopg

            with psycopg.connect(database_url, connect_timeout=8) as conn:
                conn.execute("SELECT 1")
            return {"ok": True, "error": None}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:120]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


async def _validate_groq(api_key: str) -> dict:
    """Make a tiny completion call to Groq to confirm the key works."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen/qwen3.6-27b",
                    "messages": [{"role": "user", "content": "Say hi"}],
                    "max_tokens": 5,
                    "temperature": 0,
                },
            )
            ok = resp.status_code == 200
            err = None
            if not ok:
                body = resp.json()
                err = body.get("error", {}).get("message", f"HTTP {resp.status_code}")
            return {"ok": ok, "error": err[:120] if err else None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


async def _validate_google(api_key: str) -> dict:
    """Make a tiny completion call to Google Gemini to confirm the key works."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": "Say hi"}]}],
                    "generationConfig": {"maxOutputTokens": 5},
                },
            )
            ok = resp.status_code == 200
            err = None
            if not ok:
                body = resp.json()
                err = body.get("error", {}).get("message", f"HTTP {resp.status_code}")
            return {"ok": ok, "error": err[:120] if err else None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


async def _validate_razorpay(key_id: str, key_secret: str) -> dict:
    """Make a lightweight Razorpay API call to confirm credentials work."""
    import httpx
    from base64 import b64encode

    auth = "Basic " + b64encode(f"{key_id}:{key_secret}".encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.razorpay.com/v1/payments",
                headers={"Authorization": auth},
                params={"count": 1, "skip": 0},
            )
            ok = resp.status_code == 200
            err = None
            if not ok:
                body = resp.json()
                err = body.get("error", {}).get("description", f"HTTP {resp.status_code}")
            return {"ok": ok, "error": err[:120] if err else None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


async def _validate_paypal(client_id: str, client_secret: str) -> dict:
    """Exchange PayPal credentials for an OAuth token to confirm they work."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api-m.sandbox.paypal.com/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en_US",
                },
                auth=(client_id, client_secret),
            )
            ok = resp.status_code == 200
            err = None
            if not ok:
                body = resp.json()
                err = body.get("error_description", f"HTTP {resp.status_code}")
            return {"ok": ok, "error": err[:120] if err else None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


@app.post("/api/credentials/validate")
async def validate_credentials(req: ValidateRequest, x_tenant_id: str | None = Header(default=None)) -> dict:
    """Validate user-supplied API keys by making live test calls.

    Runs all validation checks concurrently and returns the result per
    provider so the frontend can show which keys are good and which are not.
    """
    import asyncio

    results: dict[str, dict] = {}

    # Build coroutine list
    checks: list[tuple[str, asyncio.Task]] = []

    if req.groq_api_key:
        checks.append(("groq", asyncio.create_task(_validate_groq(req.groq_api_key))))
    if req.google_api_key:
        checks.append(("google", asyncio.create_task(_validate_google(req.google_api_key))))
    if req.supabase_url and req.supabase_service_role_key:
        checks.append(("supabase", asyncio.create_task(_validate_supabase(req.supabase_url, req.supabase_service_role_key))))
    if req.database_url:
        checks.append(("database", asyncio.create_task(_validate_database(req.database_url))))
    if req.razorpay_key_id and req.razorpay_key_secret:
        checks.append(("razorpay", asyncio.create_task(_validate_razorpay(req.razorpay_key_id, req.razorpay_key_secret))))
    if req.paypal_client_id and req.paypal_client_secret:
        checks.append(("paypal", asyncio.create_task(_validate_paypal(req.paypal_client_id, req.paypal_client_secret))))

    # Await all
    for label, task in checks:
        results[label] = await task

    # Compute overall validity (LLM + at least one DB/payment provider)
    has_valid_llm = results.get("groq", {}).get("ok") or results.get("google", {}).get("ok")
    has_valid_db = results.get("supabase", {}).get("ok") or results.get("database", {}).get("ok")
    has_valid_payment = results.get("razorpay", {}).get("ok") or results.get("paypal", {}).get("ok")

    all_set = has_valid_llm and (has_valid_db or has_valid_payment)

    return {
        "results": results,
        "requirements_met": all_set,
        "llm_ok": has_valid_llm,
        "db_ok": has_valid_db,
        "payment_ok": has_valid_payment,
    }


@app.get("/api/credentials/status")
async def credentials_status(x_tenant_id: str | None = Header(default=None)) -> dict:
    """Report which integrations a tenant has configured (never returns secrets).

    Every user must supply their own keys. This endpoint reports what is set
    and whether the tenant is ready to use the application (requires at least
    an LLM key + at least one of Supabase / Postgres / payment provider).
    """
    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    has_keys = tenant is not None and tenant.any_set()

    if has_keys and tenant is not None:
        llm = get_llm_client(tenant_id)
        return {
            "tenant_id": tenant_id,
            "source": "tenant",
            "ready": not tenant.validate_required(),
            "validation_errors": tenant.validate_required(),
            "supabase": bool(tenant.supabase_url and tenant.supabase_service_role_key),
            "database": bool(tenant.database_url),
            "llm": {
                "groq": bool(tenant.groq_api_key),
                "google": bool(tenant.google_api_key),
                "active": llm.active_provider.value if llm.active_provider else None,
            },
            "razorpay": bool(tenant.razorpay_key_id and tenant.razorpay_key_secret),
            "paypal": bool(tenant.paypal_client_id and tenant.paypal_client_secret),
        }

    return {
        "tenant_id": tenant_id,
        "source": "none",
        "ready": False,
        "validation_errors": ["No credentials provided. Open Settings and add your API keys."],
        "supabase": False,
        "database": False,
        "llm": {"groq": False, "google": False, "active": None},
        "razorpay": False,
        "paypal": False,
    }



class ExtractResponse(BaseModel):
    filename: str | None = None
    size_bytes: int
    content_type: str
    storage_path: str | None = None
    extracted_text: str
    extraction_method: str  # "text", "pdf", "ocr", "pasted"


@app.get("/api/health")
def health() -> dict:
    from razorpay.sync import get_razorpay_status
    from paypal.sync import get_paypal_status

    from agent.llm_client import LLMClient

    llm_client = LLMClient()
    return {
        "status": "ok",
        "mode": "bring_your_own_keys",
        "llm_providers": {
            "active": llm_client.active_provider.value if llm_client.active_provider else None,
            "groq": llm_client._groq_client is not None,
            "google": llm_client._google_client is not None,
        },
        "razorpay": get_razorpay_status(),
        "paypal": get_paypal_status(),
    }


@app.post("/api/upload", response_model=ExtractResponse)
async def upload(
    file: UploadFile = File(...),
) -> ExtractResponse:
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    # 1. Extract text
    extraction_method = _detection_method(content_type)
    try:
        text = extract_text(data, content_type)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})

    # 2. Store in Supabase Storage
    storage_path = _store_file(data, filename, content_type)

    return ExtractResponse(
        filename=filename,
        size_bytes=len(data),
        content_type=content_type,
        storage_path=storage_path,
        extracted_text=text,
        extraction_method=extraction_method,
    )


class PastedRequest(BaseModel):
    text: str


class PastedResponse(BaseModel):
    filename: str
    size_bytes: int
    content_type: str
    extracted_text: str
    extraction_method: str


@app.post("/api/paste", response_model=PastedResponse)
async def paste(req: PastedRequest) -> PastedResponse:
    text = req.text
    content_type = "text/plain"
    filename = f"pasted_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"

    # Store pasted text in Supabase Storage
    storage_path = _store_file(text.encode("utf-8"), filename, content_type)

    return PastedResponse(
        filename=filename,
        size_bytes=len(text.encode("utf-8")),
        content_type=content_type,
        extracted_text=text,
        extraction_method="pasted",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detection_method(content_type: str) -> str:
    ct = content_type.lower().split(";")[0].strip()
    if ct == "text/plain":
        return "text"
    if ct == "application/pdf":
        return "pdf"
    return "ocr"


def _store_file(data: bytes, filename: str, content_type: str, tenant_id: str = "default") -> str:
    """Upload file bytes to Supabase Storage. Returns the storage path."""
    tenant = get_tenant(tenant_id)
    if tenant is not None:
        client = build_client(tenant.supabase_url or None, tenant.supabase_service_role_key or None)
    else:
        client = None
    if client is None:
        return "local-only"

    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    storage_path = f"{date_prefix}/{uuid.uuid4().hex[:12]}.{ext}"

    client.storage.from_(BUCKET).upload(
        path=storage_path,
        file=data,
        file_options={"content-type": content_type},
    )
    return storage_path


# ---------------------------------------------------------------------------
# Phase 2 — Field extraction endpoints
# ---------------------------------------------------------------------------


class ExtractRequest(BaseModel):
    """Request body for the extract endpoint — takes pre-extracted text."""

    text: str


class ExtractAPIResponse(BaseModel):
    """Response from the field extraction endpoint."""

    fields: dict
    confidence: str
    extraction_confidence: str
    missing_fields: list[str]
    provider_used: str


@app.post("/api/extract", response_model=ExtractAPIResponse)
async def extract(req: ExtractRequest, x_tenant_id: str | None = Header(default=None)) -> ExtractAPIResponse:
    """Extract structured fields from notice text using the dual LLM.

    Accepts raw notice text (from a prior upload/paste step) and returns
    structured JSON fields with confidence scoring.
    """
    from agent.extract_fields import extract_notice_fields

    tenant_id = resolve_tenant_id(x_tenant_id)
    result = await extract_notice_fields(req.text, tenant_id=tenant_id)

    return ExtractAPIResponse(
        fields=result.fields.model_dump(exclude={"raw_text"}),
        confidence=result.confidence,
        extraction_confidence=result.extraction_confidence,
        missing_fields=result.missing_fields,
        provider_used=result.provider_used,
    )


@app.post("/api/upload-and-extract", response_model=ExtractAPIResponse)
async def upload_and_extract(
    file: UploadFile = File(...),
    x_tenant_id: str | None = Header(default=None),
) -> ExtractAPIResponse:
    """Upload a file, extract text, then extract structured fields — all in one call.

    Combines Phase 1 (text extraction) + Phase 2 (field extraction).
    """
    from agent.extract_fields import extract_notice_fields

    tenant_id = resolve_tenant_id(x_tenant_id)

    data = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # 1. Extract text (Phase 1)
    try:
        text = extract_text(data, content_type)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    if not text.strip():
        return JSONResponse(status_code=400, content={"detail": "Could not extract any text from the uploaded file."})

    # 2. Store in Supabase Storage
    filename = file.filename or "unknown"
    _store_file(data, filename, content_type, tenant_id)

    # 3. Extract structured fields (Phase 2)
    result = await extract_notice_fields(text, tenant_id=tenant_id)

    return ExtractAPIResponse(
        fields=result.fields.model_dump(exclude={"raw_text"}),
        confidence=result.confidence,
        extraction_confidence=result.extraction_confidence,
        missing_fields=result.missing_fields,
        provider_used=result.provider_used,
    )


class LLMStatusResponse(BaseModel):
    """Status of LLM providers."""

    active_provider: str | None
    groq_configured: bool
    google_configured: bool
    groq_model: str
    google_model: str


@app.get("/api/llm-status", response_model=LLMStatusResponse)
async def llm_status(x_tenant_id: str | None = Header(default=None)) -> LLMStatusResponse:
    """Check which LLM providers are configured and which is active for this tenant."""
    tenant_id = resolve_tenant_id(x_tenant_id)
    try:
        client = get_llm_client(tenant_id)
        return LLMStatusResponse(
            active_provider=client.active_provider.value if client.active_provider else None,
            groq_configured=client._groq_client is not None,
            google_configured=client._google_client is not None,
            groq_model=client._groq_model,
            google_model=client._google_model,
        )
    except RuntimeError:
        return LLMStatusResponse(
            active_provider=None,
            groq_configured=False,
            google_configured=False,
            groq_model="",
            google_model="",
        )


# ---------------------------------------------------------------------------
# Phase 4 — Cross-reference endpoints
# ---------------------------------------------------------------------------


class CrossReferenceRequest(BaseModel):
    """Request body — extracted fields from a notice."""

    notice_type: str
    gstin: str
    tax_period: str
    amount: float
    section_cited: str
    due_date: str


@app.post("/api/cross-reference")
async def cross_reference_endpoint(req: CrossReferenceRequest, x_tenant_id: str | None = Header(default=None)) -> dict:
    """Cross-reference extracted notice fields against transactions + KB.

    Takes structured fields (from /api/extract) and returns:
    - Matching transactions from the same tax period
    - Flagged mismatch transactions
    - Best matching KB entry via pgvector similarity
    - Full audit trail
    """
    from agent.cross_reference import cross_reference
    from agent.models import ExtractedFields

    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    database_url = tenant.database_url if tenant and tenant.database_url else None

    fields = ExtractedFields(
        notice_type=req.notice_type,
        gstin=req.gstin,
        tax_period=req.tax_period,
        amount=req.amount,
        section_cited=req.section_cited,
        due_date=req.due_date,
    )

    result = await cross_reference(fields, database_url)

    return {
        "matched_transactions": [t.model_dump() for t in result.matched_transactions],
        "flagged_transactions": [t.model_dump() for t in result.flagged_transactions],
        "kb_entry": result.kb_entry.model_dump() if result.kb_entry else None,
        "total_transactions_in_period": result.total_transactions_in_period,
        "total_amount_in_period": result.total_amount_in_period,
        "total_tax_in_period": result.total_tax_in_period,
        "audit_log": [a.model_dump() for a in result.audit_log],
    }


class AnalyzeRequest(BaseModel):
    """Request body for the full pipeline — takes raw notice text."""

    text: str


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest, x_tenant_id: str | None = Header(default=None)) -> dict:
    """Full pipeline: extract fields → cross-reference → return everything.

    Combines Phase 2 (field extraction) + Phase 4 (cross-reference) in one call.
    """
    from agent.cross_reference import cross_reference
    from agent.extract_fields import extract_notice_fields

    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    database_url = tenant.database_url if tenant and tenant.database_url else None

    # 1. Extract fields (Phase 2)
    extraction = await extract_notice_fields(req.text, tenant_id=tenant_id)

    # 2. Cross-reference (Phase 4)
    xref = await cross_reference(extraction.fields, database_url)

    return {
        "extraction": {
            "fields": extraction.fields.model_dump(exclude={"raw_text"}),
            "confidence": extraction.confidence,
            "missing_fields": extraction.missing_fields,
            "provider_used": extraction.provider_used,
        },
        "cross_reference": {
            "matched_transactions": [t.model_dump() for t in xref.matched_transactions],
            "flagged_transactions": [t.model_dump() for t in xref.flagged_transactions],
            "kb_entry": xref.kb_entry.model_dump() if xref.kb_entry else None,
            "total_transactions_in_period": xref.total_transactions_in_period,
            "total_amount_in_period": xref.total_amount_in_period,
            "total_tax_in_period": xref.total_tax_in_period,
            "audit_log": [a.model_dump() for a in xref.audit_log],
        },
    }


@app.post("/api/upload-and-analyze")
async def upload_and_analyze(
    file: UploadFile = File(...),
    x_tenant_id: str | None = Header(default=None),
) -> dict:
    """Upload a file → extract text → extract fields → cross-reference.

    The full end-to-end pipeline in one call (Phase 1 + 2 + 4).
    """
    from agent.cross_reference import cross_reference
    from agent.extract_fields import extract_notice_fields

    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    database_url = tenant.database_url if tenant and tenant.database_url else None

    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    # 1. Extract text (Phase 1)
    try:
        text = extract_text(data, content_type)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    if not text.strip():
        return JSONResponse(status_code=400, content={"detail": "Could not extract any text from the uploaded file."})

    # 2. Store in Supabase Storage
    _store_file(data, filename, content_type, tenant_id)

    # 3. Extract structured fields (Phase 2)
    extraction = await extract_notice_fields(text, tenant_id=tenant_id)

    # 4. Cross-reference (Phase 4)
    xref = await cross_reference(extraction.fields, database_url)

    return {
        "extraction": {
            "fields": extraction.fields.model_dump(exclude={"raw_text"}),
            "confidence": extraction.confidence,
            "missing_fields": extraction.missing_fields,
            "provider_used": extraction.provider_used,
        },
        "cross_reference": {
            "matched_transactions": [t.model_dump() for t in xref.matched_transactions],
            "flagged_transactions": [t.model_dump() for t in xref.flagged_transactions],
            "kb_entry": xref.kb_entry.model_dump() if xref.kb_entry else None,
            "total_transactions_in_period": xref.total_transactions_in_period,
            "total_amount_in_period": xref.total_amount_in_period,
            "total_tax_in_period": xref.total_tax_in_period,
            "audit_log": [a.model_dump() for a in xref.audit_log],
        },
    }


# ---------------------------------------------------------------------------
# Phase 5 — Reasoning agent + explanation endpoints
# ---------------------------------------------------------------------------


class ExplainRequest(BaseModel):
    """Request body for explanation generation — takes extracted fields."""

    notice_type: str
    gstin: str
    tax_period: str
    amount: float
    section_cited: str
    due_date: str
    raw_text: str = ""


@app.post("/api/explain")
async def explain(req: ExplainRequest, x_tenant_id: str | None = Header(default=None)) -> dict:
    """Generate a four-part explanation from extracted fields + cross-reference.

    Takes structured fields, runs cross-reference, then calls the reasoning
    LLM to generate the explanation with citations.
    """
    from agent.cross_reference import cross_reference
    from agent.extract_fields import ExtractedFields
    from agent.reasoning import generate_explanation

    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    database_url = tenant.database_url if tenant and tenant.database_url else None

    fields = ExtractedFields(
        notice_type=req.notice_type,
        gstin=req.gstin,
        tax_period=req.tax_period,
        amount=req.amount,
        section_cited=req.section_cited,
        due_date=req.due_date,
        raw_text=req.raw_text,
    )

    # Cross-reference
    xref = await cross_reference(fields, database_url)

    # Generate explanation
    reasoning = await generate_explanation(
        fields=fields,
        xref=xref,
        extraction_confidence="high",
        raw_text=req.raw_text,
        tenant_id=tenant_id,
    )

    return {
        "explanation": reasoning.explanation.model_dump(),
        "overall_confidence": reasoning.overall_confidence,
        "is_low_confidence": reasoning.is_low_confidence,
        "ca_escalation_note": reasoning.ca_escalation_note,
        "provider_used": reasoning.provider_used,
        "audit_log": [a.model_dump() for a in xref.audit_log],
    }


class AnalyzeFullRequest(BaseModel):
    """Request body for the complete pipeline — takes raw notice text."""

    text: str


async def _run_full_pipeline(
    text: str, store: bool = True, tenant_id: str = "default"
) -> dict:
    """Run the complete pipeline: extract → cross-reference → explain → store.

    Shared by /api/analyze-full and /api/upload-and-explain.
    """
    from agent.cross_reference import cross_reference
    from agent.extract_fields import extract_notice_fields
    from agent.reasoning import generate_explanation

    # Resolve this tenant's DB URL (user-supplied; None means skip cross-ref).
    tenant = get_tenant(tenant_id)
    database_url = tenant.database_url if tenant and tenant.database_url else None

    # Phase 2: Extract fields
    extraction = await extract_notice_fields(text, tenant_id=tenant_id)

    # Phase 4: Cross-reference
    xref = await cross_reference(extraction.fields, database_url)

    # Phase 5: Generate explanation
    reasoning = await generate_explanation(
        fields=extraction.fields,
        xref=xref,
        extraction_confidence=extraction.confidence,
        raw_text=text,
        tenant_id=tenant_id,
    )

    # Build audit log (combines xref + reasoning steps)
    full_audit = [a.model_dump() for a in xref.audit_log]
    full_audit.append({
        "step": "reasoning",
        "action": "Generate four-part explanation via LLM",
        "result": f"Generated by {reasoning.provider_used}, confidence: {reasoning.overall_confidence}",
        "details": f"Low confidence: {reasoning.is_low_confidence}",
    })

    result = {
        "extraction": {
            "fields": extraction.fields.model_dump(exclude={"raw_text"}),
            "confidence": extraction.confidence,
            "missing_fields": extraction.missing_fields,
            "provider_used": extraction.provider_used,
        },
        "cross_reference": {
            "matched_transactions": [t.model_dump() for t in xref.matched_transactions],
            "flagged_transactions": [t.model_dump() for t in xref.flagged_transactions],
            "kb_entry": xref.kb_entry.model_dump() if xref.kb_entry else None,
            "total_transactions_in_period": xref.total_transactions_in_period,
            "total_amount_in_period": xref.total_amount_in_period,
            "total_tax_in_period": xref.total_tax_in_period,
        },
        "explanation": {
            "sections": reasoning.explanation.model_dump(),
            "overall_confidence": reasoning.overall_confidence,
            "is_low_confidence": reasoning.is_low_confidence,
            "ca_escalation_note": reasoning.ca_escalation_note,
            "provider_used": reasoning.provider_used,
        },
        "audit_log": full_audit,
    }

    # Store in notices table
    if store:
        _store_notice_record(extraction, xref, reasoning, text, full_audit, tenant_id)

    return result


def _store_notice_record(extraction, xref, reasoning, raw_text, audit_log, tenant_id="default"):
    """Store the processed notice in the notices table for audit."""
    tenant = get_tenant(tenant_id)
    if tenant is not None:
        client = build_client(tenant.supabase_url or None, tenant.supabase_service_role_key or None)
    else:
        client = None
    if client is None:
        log.warning("Supabase not configured for this tenant — skipping notice storage")
        return

    try:
        f = extraction.fields
        client.table("notices").insert({
            "notice_type": f.notice_type or "Unknown",
            "gstin": f.gstin or "Unknown",
            "tax_period": f.tax_period or "Unknown",
            "amount": f.amount if f.amount is not None else 0,
            "section_cited": f.section_cited or "Unknown",
            "due_date": f.due_date or "Not specified",
            "extraction_confidence": extraction.confidence,
            "explanation_json": reasoning.explanation.model_dump(),
            "overall_confidence": reasoning.overall_confidence,
            "is_low_confidence": reasoning.is_low_confidence,
            "provider_used": reasoning.provider_used,
            "extraction_provider": extraction.provider_used,
            "matched_txn_count": xref.total_transactions_in_period,
            "flagged_txn_count": len(xref.flagged_transactions),
            "kb_entry_section": xref.kb_entry.section if xref.kb_entry else None,
            "audit_log": audit_log,
            "raw_text": raw_text[:5000],
        }).execute()
        log.info("Notice stored in notices table")
    except Exception as e:
        log.warning("Failed to store notice record: %s", e)


@app.post("/api/analyze-full")
async def analyze_full(req: AnalyzeFullRequest, x_tenant_id: str | None = Header(default=None)) -> dict:
    """Complete pipeline: text → extract → cross-reference → explain → store.

    Phase 2 + 4 + 5 in one call. Stores audit log in notices table.
    """
    tenant_id = resolve_tenant_id(x_tenant_id)
    return await _run_full_pipeline(req.text, store=True, tenant_id=tenant_id)


@app.post("/api/upload-and-explain")
async def upload_and_explain(
    file: UploadFile = File(...),
    x_tenant_id: str | None = Header(default=None),
) -> dict:
    """Upload a file → full pipeline: text extraction → fields → cross-ref → explain.

    The complete end-to-end pipeline (Phase 1 + 2 + 4 + 5).
    """
    tenant_id = resolve_tenant_id(x_tenant_id)

    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    # Phase 1: Extract text
    try:
        text = extract_text(data, content_type)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    if not text.strip():
        return JSONResponse(status_code=400, content={"detail": "Could not extract any text from the uploaded file."})

    # Store in Supabase Storage
    _store_file(data, filename, content_type, tenant_id)

    # Run full pipeline (Phase 2 + 4 + 5)
    return await _run_full_pipeline(text, store=True, tenant_id=tenant_id)


@app.get("/api/notices")
async def list_notices(limit: int = 20, x_tenant_id: str | None = Header(default=None)) -> dict:
    """List recently processed notices from the audit log."""
    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    if tenant is not None:
        client = build_client(tenant.supabase_url or None, tenant.supabase_service_role_key or None)
    else:
        client = None
    if client is None:
        return {"notices": [], "count": 0}

    result = (
        client.table("notices")
        .select("id, notice_type, gstin, tax_period, amount, overall_confidence, "
                "is_low_confidence, matched_txn_count, flagged_txn_count, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"notices": result.data, "count": len(result.data)}


# ---------------------------------------------------------------------------
# Phase 6 — Razorpay Test Mode integration
# ---------------------------------------------------------------------------


class RazorpaySyncRequest(BaseModel):
    """Request body for Razorpay sync."""

    count: int = 100
    from_timestamp: int | None = None
    to_timestamp: int | None = None


@app.post("/api/razorpay/sync")
async def razorpay_sync(
    req: RazorpaySyncRequest | None = None,
    x_tenant_id: str | None = Header(default=None),
) -> dict:
    """Sync transactions from Razorpay Test Mode API into the transactions table.

    Pulls real payment data from Razorpay Test Mode and upserts it into
    Supabase. After sync, the cross-reference logic can use this real data
    alongside synthetic data.

    Uses the tenant's Razorpay/DB credentials if provided, else .env.
    """
    from razorpay.sync import sync_transactions

    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    key_id = tenant.razorpay_key_id if tenant else None
    key_secret = tenant.razorpay_key_secret if tenant else None
    database_url = tenant.database_url if tenant and tenant.database_url else None

    kwargs = {}
    if req is not None:
        if req.count:
            kwargs["count"] = req.count
        if req.from_timestamp:
            kwargs["from_timestamp"] = req.from_timestamp
        if req.to_timestamp:
            kwargs["to_timestamp"] = req.to_timestamp

    return sync_transactions(
        **kwargs, key_id=key_id, key_secret=key_secret, database_url=database_url
    )


@app.get("/api/razorpay/status")
async def razorpay_status(x_tenant_id: str | None = Header(default=None)) -> dict:
    """Check Razorpay configuration and mode (test vs live)."""
    from razorpay.sync import get_razorpay_status

    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    key_id = tenant.razorpay_key_id if tenant else None
    key_secret = tenant.razorpay_key_secret if tenant else None
    return get_razorpay_status(key_id, key_secret)


# ---------------------------------------------------------------------------
# Phase 6b — PayPal Reporting API integration
# ---------------------------------------------------------------------------


class PayPalSyncRequest(BaseModel):
    """Request body for PayPal sync."""

    count: int = 100
    start_date: str | None = None
    end_date: str | None = None
    sandbox: bool = True


@app.post("/api/paypal/sync")
async def paypal_sync(
    req: PayPalSyncRequest | None = None,
    x_tenant_id: str | None = Header(default=None),
) -> dict:
    """Sync transactions from the PayPal Reporting API into transactions table.

    Pulls real payment data from PayPal (Transaction Search) and upserts it
    into Supabase. After sync, the cross-reference logic can use this real data
    alongside synthetic and Razorpay data.

    Uses the tenant's PayPal/DB credentials if provided, else .env.
    """
    from paypal.sync import sync_transactions

    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    client_id = tenant.paypal_client_id if tenant else None
    client_secret = tenant.paypal_client_secret if tenant else None
    database_url = tenant.database_url if tenant and tenant.database_url else None

    kwargs = {}
    if req is not None:
        if req.count:
            kwargs["count"] = req.count
        if req.start_date:
            kwargs["start_date"] = req.start_date
        if req.end_date:
            kwargs["end_date"] = req.end_date
        kwargs["sandbox"] = req.sandbox

    return sync_transactions(
        **kwargs, client_id=client_id, client_secret=client_secret,
        database_url=database_url,
    )


@app.get("/api/paypal/status")
async def paypal_status(x_tenant_id: str | None = Header(default=None)) -> dict:
    """Check PayPal configuration and mode (sandbox vs live)."""
    from paypal.sync import get_paypal_status

    tenant_id = resolve_tenant_id(x_tenant_id)
    tenant = get_tenant(tenant_id)
    client_id = tenant.paypal_client_id if tenant else None
    client_secret = tenant.paypal_client_secret if tenant else None
    return get_paypal_status(client_id, client_secret)
