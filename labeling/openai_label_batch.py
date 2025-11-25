
import os
import json
import logging
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from pydantic import ValidationError

from .schema import EmailRequest
from .cleaning import html_to_text, anonymize_text, choose_best_segment

from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)

RAW_PATH = Path("data/train/raw_emails.jsonl")
OUT_PATH = Path("data/train/labeled_emails.jsonl")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

COMPANY_DOMAIN = "julesverne.com.tr"
MAIL_GROUPS = ["booking", "jvnobet", "karadeniz", "denizbank", "tvekip1", "tvekip2", "tvekip3", "tvekip4"]

RE_PREFIXES = ("re:", "fw:", "fwd:", "ynt:", "cev:", "cevap:", "yanıt:")

PROMPT_TEMPLATE = """
Aşağıda bir uçuş / otel / transfer talebi e-postası var.

Bu e-postadan aşağıdaki JSON şemasına UYGUN bir çıktı üret.

Genel şema:

{
  "requests": [
    {
      "type": "flight" | "hotel" | "transfer",
      "flight": FlightRequest veya null,
      "hotel": HotelRequest veya null,
      "transfer": TransferRequest veya null
    }
  ]
}

Her request için:
- type = "flight" ise: flight doldur, hotel ve transfer = null
- type = "hotel" ise: hotel doldur, flight ve transfer = null
- type = "transfer" ise: transfer doldur, flight ve hotel = null

Aşağıda her tip için kullanılacak alanlar detaylı olarak verilmiştir.

--------------------
DateSpec (tüm tarihler için)
--------------------
JSON alan adı: DateSpec
Yapı:

{
  "type": "exact" | "range" | "after" | "before" | "unspecified",
  "exact": "YYYY-MM-DD" veya null,
  "from": "YYYY-MM-DD" veya null,
  "to": "YYYY-MM-DD" veya null,
  "text": "kullanıcının serbest metni" veya null
}

Örnekler:
- Kullanıcı net bir tarih veriyorsa: 5 Ocak 2026
  → { "type": "exact", "exact": "2026-01-05", "from": null, "to": null, "text": null }

- "5-7 Ocak arası" diyorsa:
  → { "type": "range", "exact": null, "from": "2026-01-05", "to": "2026-01-07", "text": null }

- "Ocak içinde bir gün" diyorsa:
  → { "type": "unspecified", "exact": null, "from": null, "to": null, "text": "ocak içinde bir gün" }

--------------------
TimeSpec (tüm saatler için)
--------------------
JSON alan adı: TimeSpec
Yapı:

{
  "type": "exact" | "range" | "after" | "before" | "unspecified",
  "exact": "HH:MM" veya null,
  "from": "HH:MM" veya null,
  "to": "HH:MM" veya null,
  "text": "kullanıcının serbest metni" veya null
}

Örnekler:
- "Saat 15:30" diyorsa:
  → { "type": "exact", "exact": "15:30", "from": null, "to": null, "text": null }

- "Öğleden sonra" veya "akşam 5'ten sonra" diyorsa:
  → { "type": "unspecified", "exact": null, "from": null, "to": null, "text": "öğleden sonra" }

--------------------
FlightRequest
--------------------
JSON alan adı: flight
Yapı:

{
  "trip_type": "one_way" | "round_trip" | "multi_city",
  "pnr": string veya null,
  "airline_preference": string veya null,   // THY, Pegasus vb.
  "cabin": "ECONOMY" | "BUSINESS" | "FIRST" | "PREMIUM_ECONOMY" veya null,
  "legs": [ Leg, ... ],
  "pax": {
    "adult": int,
    "child": int,
    "infant": int
  },
  "baggage": {
    "hand": int,
    "hold": int
  },
  "currency": string veya null,     // TRY, EUR, USD...
  "budget_total": number veya null,
  "notes": string veya null,
  "po_number": müşterinin satın yada talep numarası varsa string yoksa null
}

Leg yapısı:

{
  "from": string veya null,    // Şehir veya havaalanı (örn: "IST", "SAW", "Istanbul")
  "to": string veya null,      // Şehir veya havaalanı
  "date": DateSpec,
  "time": TimeSpec
}

Örnek tek yön uçuş:

{
  "type": "flight",
  "flight": {
    "trip_type": "one_way",
    "pnr": null,
    "airline_preference": "THY",
    "cabin": "ECONOMY",
    "legs": [
      {
        "from": "IST",
        "to": "BER",
        "date": { ... DateSpec ... },
        "time": { ... TimeSpec ... }
      }
    ],
    "pax": { "adult": 1, "child": 0, "infant": 0 },
    "baggage": { "hand": 1, "hold": 0 },
    "currency": "EUR",
    "budget_total": null,
    "notes": "mümkünse direkt uçuş",
    "po_number": "DNZ12345"
  },
  "hotel": null,
  "transfer": null
}

--------------------
HotelRequest
--------------------
JSON alan adı: hotel
Yapı:

{
  "city": string veya null,
  "area": string veya null,            // semt/bölge
  "date": {
    "check_in": DateSpec,
    "check_out": DateSpec
  },
  "nights": int veya null,
  "rooms": int veya null,
  "pax": {
    "adult": int,
    "child": int
  },
  "purpose": "business" | "leisure" | "mixed" veya null,
  "theme": "city_center" | "sea_side" | "ski" | "conference" veya null,
  "hotel_class": int veya null,        // 3, 4, 5
  "budget_total": number veya null,
  "currency": string veya null,
  "notes": string veya null,
  "po_number": müşterinin satın yada talep numarası varsa string yoksa null
}

--------------------
TransferRequest
--------------------
JSON alan adı: transfer
Yapı:

{
  "direction": "arrival" | "departure" | "roundtrip" | "other" veya null,
  "from": string veya null,
  "to": string veya null,
  "date": DateSpec,
  "time": TimeSpec,
  "pax": {
    "adult": int,
    "child": int,
    "infant": int
  },
  "luggage_pieces": int veya null,
  "notes": string veya null,
  "po_number": müşterinin satın yada talep numarası varsa string yoksa null
}

--------------------
Kurallar (çok önemli)
--------------------

1. JSON DIŞINDA hiçbir şey yazma. Açıklama, yorum, metin KULLANMA.
2. Bilmediğin veya mailde açık yazmayan alanları UYDURMA → o alanı null yap.
3. Listeler boş olabilir (örn: legs: []), ama alan ADLARI her zaman şemadaki gibi olmalıdır.
4. "from" ve "to" alanları JSON içinde tam olarak "from" ve "to" olarak yazılmalıdır (from_ kullanma).
5. Eğer mailde hem uçak hem otel hem de transfer isteniyorsa, "requests" listesinde birden fazla obje kullan:
   - Bir flight request,
   - Bir hotel request,
   - Bir transfer request.
6. Sadece aşağıdaki gibi açık kelimeler geçiyorsa transfer isteği oluştur:
    "transfer", "şoförlü araç", "karşılama", "karşılanma", "şuttle", "shuttle", "servis", "özel araç", "pickup", "drop-off", "ground transfer"
7. Eğer cümlede “uçak”, “uçuş”, “flight” kelimeleri geçiyor ve güzergah “şehir ↔ havaalanı” olsa bile, bunu uçuş isteği olarak yorumla, transfer oluşturma.
8. Transfer isteği, açıkça karayolu / araçla ulaşım için olmalı. Sadece “uçak saatleri rica edebilir miyiz” deniyorsa, bu uçuş talebidir, transfer değildir.

E-posta içeriği:
---
{body}
---
"""


def build_body_text(msg: Dict[str, Any]) -> str:
    body = (msg.get("body") or {})
    content_type = body.get("contentType", "html")
    content = body.get("content", "") or ""

    # 1) HTML ise düz metne çevir
    if content_type.lower() == "html":
        plain = html_to_text(content)
    else:
        plain = content

    # 2) Thread içinden en anlamlı mail segmentini seç
    best_segment = choose_best_segment(plain)

    # 3) Maskele
    # best_segment = anonymize_text(best_segment)

    return best_segment


def call_openai(body_text: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = PROMPT_TEMPLATE.replace("{body}", body_text)

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are an assistant that extracts structured travel requests (flight, hotel, transfer) as JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    content = resp.choices[0].message.content
    return content


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if not RAW_PATH.exists():
        logger.error("Raw emails file not found: %s", RAW_PATH)
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUT_PATH.open("a", encoding="utf-8") as out_f:
        with RAW_PATH.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()

                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping invalid JSON line")
                    continue

                mail_id = msg.get("id")
                subject = msg.get("subject")
                subject_lower = subject.lower()
                recv = msg.get("receivedDateTime")

                if subject_lower.startswith(RE_PREFIXES):
                    logger.info("Skipping mail %s (%d): reply/forward subject '%s'", mail_id, idx, subject)
                    continue                

                to_addrs = [(r.get("address") or "").lower() for r in msg.get("to", [])]
                has_target_group = any(
                    addr.endswith(f"@{COMPANY_DOMAIN}") and any(group in addr for group in MAIL_GROUPS)
                    for addr in to_addrs
                )

                if not has_target_group:
                    logger.info("Skipping mail %s (%d): not sent to target groups", mail_id, idx)
                    continue

                body_text = build_body_text(msg)

                if len(body_text) < 40:
                    logger.info("Skipping mail %s (%d): body too short after block selection", mail_id, idx)
                    continue

                logger.info("Labeling mail %s (%d): %s", mail_id, idx, subject)

                try:
                    raw_json_str = call_openai(body_text)
                    parsed = json.loads(raw_json_str)
                except Exception as e:
                    logger.exception("OpenAI or JSON parse error for mail %s: %s", mail_id, e)
                    record = {
                        "mail_id": mail_id,
                        "subject": subject,
                        "receivedDateTime": recv,
                        "text": body_text,
                        "label": None,
                        "review_needed": True,
                        "error": str(e),
                    }
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    continue

                try:
                    EmailRequest.model_validate(parsed)
                    review_needed = False
                    error_msg = None
                except ValidationError as ve:
                    logger.warning("Validation error for mail %s: %s", mail_id, ve)
                    review_needed = True
                    error_msg = str(ve)

                record = {
                    "mail_id": mail_id,
                    "subject": subject,
                    "receivedDateTime": recv,
                    "text": body_text,
                    "label": parsed,
                    "review_needed": review_needed,
                    "error": error_msg,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info("Labeled emails written to %s", OUT_PATH)

if __name__ == "__main__":
    main()
