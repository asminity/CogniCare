import json
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from pypdf import PdfReader

from app.core.config import Settings


class PolicyExtractionError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


@dataclass
class ExtractedRule:
    rule_type: str
    service_name: str
    value: dict[str, Any]
    in_network: bool
    requires_authorization: bool
    coverage_percent: int
    copay_cents: int
    notes: str
    source_page: int
    source_text: str
    confidence: float


@dataclass
class ExtractionResult:
    rules: list[ExtractedRule]
    pages: int
    method: str
    warning: str | None = None


def _extract_pages(pdf_bytes: bytes) -> tuple[list[str], bool]:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise PolicyExtractionError("text_extraction", f"The PDF could not be read: {exc}") from exc

    if any(page for page in pages):
        return pages, False

    try:
        import fitz
        import pytesseract
        from PIL import Image

        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            pages.append(pytesseract.image_to_string(image).strip())
    except Exception as exc:
        raise PolicyExtractionError("ocr", "The PDF has no selectable text and OCR is unavailable. Install Tesseract OCR to process scanned policies.") from exc

    if not any(pages):
        raise PolicyExtractionError("ocr", "No text could be extracted from the PDF, including through OCR.")
    return pages, True


def _section_name(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "policy provision")
    return re.sub(r"[^A-Za-z0-9 /-]", "", first_line)[:100] or "policy provision"


def _money_cents(text: str) -> int:
    match = re.search(r"\$\s*([\d,]+(?:\.\d{1,2})?)", text)
    if not match:
        return 0
    return round(float(match.group(1).replace(",", "")) * 100)


def _percentage(text: str) -> int:
    match = re.search(r"(\d{1,3})\s*%", text)
    return int(match.group(1)) if match else 0


def _rule_type(text: str) -> str | None:
    lowered = text.lower()
    terms = [
        ("exclusion", ("excluded", "exclusion", "not covered")),
        ("waiting_period", ("waiting period", "wait ")),
        ("room_limit", ("room limit", "daily room", "room and board")),
        ("copay", ("co-pay", "copay", "co-pay")),
        ("deductible", ("deductible",)),
        ("sub_limit", ("sub-limit", "sublimit", "sub limit")),
        ("network", ("in-network", "out-of-network", "network restriction", "network")),
        ("authorization", ("prior authorization", "preauthorization", "authorization required")),
        ("emergency", ("emergency", "urgent care")),
        ("procedure_restriction", ("procedure", "medical necessity", "referral required")),
        ("coverage", ("covered", "coverage", "benefit")),
    ]
    return next((rule_type for rule_type, matches in terms if any(match in lowered for match in matches)), None)


def _heuristic_rules(pages: list[str]) -> list[ExtractedRule]:
    rules: list[ExtractedRule] = []
    seen: set[tuple[str, str]] = set()
    for page_number, page_text in enumerate(pages, start=1):
        for raw_line in page_text.splitlines():
            line = " ".join(raw_line.split())
            rule_type = _rule_type(line)
            if not rule_type or len(line) < 12:
                continue
            key = (rule_type, line.lower())
            if key in seen:
                continue
            seen.add(key)
            lowered = line.lower()
            rules.append(ExtractedRule(
                rule_type=rule_type,
                service_name=_section_name(page_text),
                value={"text": line, "percentage": _percentage(line), "amount_cents": _money_cents(line)},
                in_network="out-of-network" not in lowered,
                requires_authorization=rule_type == "authorization" or "authorization" in lowered,
                coverage_percent=_percentage(line) if rule_type in {"coverage", "copay", "network", "emergency"} else 0,
                copay_cents=_money_cents(line) if rule_type == "copay" else 0,
                notes=line,
                source_page=page_number,
                source_text=line,
                confidence=0.72,
            ))
    return rules


def _llm_rules(pages: list[str], settings: Settings) -> list[ExtractedRule]:
    from openai import OpenAI

    prompt = """Extract insurance policy provisions into JSON. Return an object with a 'rules' array. Each rule must have rule_type, service_name, value, in_network, requires_authorization, coverage_percent, copay_cents, notes, source_page, source_text, and confidence. Use only the supplied text, preserve exact source text, use page numbers supplied, and include coverage, exclusions, waiting periods, room limits, co-pay, deductible, sub-limits, network restrictions, authorization, emergency coverage, and procedure restrictions when present. Confidence is a number from 0 to 1.\n\n"""
    prompt += "\n\n".join(f"PAGE {number}:\n{text}" for number, text in enumerate(pages, start=1))
    response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    return [ExtractedRule(**rule) for rule in payload.get("rules", [])]


def extract_policy_rules(pdf_bytes: bytes, settings: Settings) -> ExtractionResult:
    pages, used_ocr = _extract_pages(pdf_bytes)
    warning = None
    method = "ocr + heuristic extraction" if used_ocr else "heuristic extraction"
    if settings.openai_api_key:
        try:
            rules = _llm_rules(pages, settings)
            method = "ocr + OpenAI extraction" if used_ocr else "OpenAI extraction"
        except Exception as exc:
            rules = _heuristic_rules(pages)
            warning = f"LLM extraction failed; heuristic extraction was used: {exc}"
    else:
        rules = _heuristic_rules(pages)
    if not rules:
        raise PolicyExtractionError("information_extraction", "Text was extracted, but no recognizable policy rules were found.")
    return ExtractionResult(rules=rules, pages=len(pages), method=method, warning=warning)