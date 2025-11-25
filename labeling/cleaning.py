# labeling/cleaning.py

import re
import unicodedata
from typing import List
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
PHONE_RE = re.compile(r"(?<![0-9A-Za-z])\+?\d[\d \-]{7,}\d(?![0-9A-Za-z])")
PNR_RE   = re.compile(r"\b[A-Z0-9]{5,7}\b")

TRAVEL_KEYWORDS = [
    "uçuş", "ucus", "bilet", "rezervasyon", "otel",
    "konaklama", "transfer", "uçak", "ucak",
    "gidiş", "gidis", "dönüş", "donus",
    "tek yön", "tek yon", "gidiş-dönüş", "gidis-donus",
    "check-in", "check in", "check-out", "check out",
    "giriş", "çıkış",
    "thy", "pegasus", "sunexpress", "tk ", " pc ", " xq ",
    "flight", "hotel", "booking", "reservation",
    "telep", "request", "boarding", "pnr", "voucher",
]

LEGAL_KEYWORDS = [
    "gizlidir", "gizliliği", "hukuken", "yasal", "sorumlu değildir",
    "yetkili alıcı", "yanlışlıkla", "lütfen siliniz",
    "bu e-posta ve ekleri", "bu eposta ve ekleri",
    "bu elektronik posta", "işbu e-posta", "işbu eposta", "isbu e-posta", "isbu eposta",
    "gönderilen kişilere özel olup",
    "sadece göndericisi tarafindan almasi",
    "sadece göndericisi tarafından alması",
    "posta sorumluluk red",
    "confidential", "confidentiality", "disclaimer",
    "if you are not the intended recipient",
    "please delete this e-mail", "please delete this email",
    "consider the environment", "before printing this email",
]


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = normalize_whitespace_and_invisible(text)
    return text.strip()


def anonymize_text(text: str) -> str:
    if not text:
        return ""
    text = EMAIL_RE.sub("EMAIL_MASKED", text)
    text = PHONE_RE.sub("PHONE_MASKED", text)
    text = PNR_RE.sub("PNR_MASKED", text)
    return text


def split_segments(full_text: str) -> List[str]:
    """
    Thread içinden tek tek "mail" bloklarını çıkar.
    Marker'lar: -----Original Message-----, From:, Gönderen:, Kimden: vs.
    """
    if not full_text:
        return []

    t = full_text.replace("\r\n", "\n")
    lower = t.lower()

    markers = [
        "-----original message-----",
        "----- özgün ileti -----",
        "-----özgün ileti-----",
        "\nfrom:",
        "\ngönderen:",
        "\nkimden:",
    ]

    indices = [0]

    for m in markers:
        start = 0
        while True:
            idx = lower.find(m, start)
            if idx == -1:
                break
            indices.append(idx)
            start = idx + len(m)

    indices = sorted(set(i for i in indices if 0 <= i < len(t)))

    segments: List[str] = []
    for i, start in enumerate(indices):
        end = indices[i + 1] if i + 1 < len(indices) else len(t)
        seg = t[start:end].strip()
        if seg:
            segments.append(seg)

    # marker hiç bulunamadıysa tek segment olsun
    if not segments and full_text.strip():
        return [full_text.strip()]

    return segments


def trim_legal_tail(segment: str) -> str:
    """
    Bir mail segmentinin SONUNDAKİ legal / disclaimer bloklarını kes.
    (Talep üstte, legal altta olduğu için.)
    """
    if not segment:
        return ""

    lower = segment.lower()
    cut_pos = len(segment)

    for kw in LEGAL_KEYWORDS:
        idx = lower.find(kw.lower())
        if idx != -1 and idx < cut_pos:
            cut_pos = idx

    # Gövdeden önce anlamlı kısım varsa kes
    if 50 < cut_pos < len(segment):
        return segment[:cut_pos].strip()
    return segment.strip()


def score_segment(segment: str) -> float:
    """
    Tüm bir mail segmenti için talep skoru:
    + travel keyword
    - legal keyword
    - çok kısaysa ceza
    """
    lower = segment.lower()
    travel_hits = sum(1 for kw in TRAVEL_KEYWORDS if kw in lower)
    legal_hits  = sum(1 for kw in LEGAL_KEYWORDS  if kw in lower)

    length = len(segment)
    length_penalty = 1.0 if length < 40 else 0.0

    return travel_hits - 0.7 * legal_hits - length_penalty


def choose_best_segment(full_text: str) -> str:
    """
    1) Thread'i mail segmentlerine böler
    2) Her segmenti skorlar
    3) En yüksek skorlu mail segmentini seçer
    4) O segmentin sonundaki legal kuyruğu keser
    """
    segments = split_segments(full_text)
    if not segments:
        return ""

    best_score = None
    best_seg = ""

    for seg in segments:
        s = score_segment(seg)
        if best_score is None or s > best_score:
            best_score = s
            best_seg = seg

    best_seg = trim_legal_tail(best_seg)
    return best_seg.strip()

def normalize_whitespace_and_invisible(text: str) -> str:
    """
    Zero-width space vb. görünmeyen unicode karakterleri ve
    saçma whitespace'leri temizler.
    """
    if not text:
        return ""

    # Bazı mailer'lar non-breaking space (u00A0) basıyor; normal boşluğa çevir
    text = text.replace("\u00A0", " ")

    # Unicode "format" kategorisindeki karakterleri (Cf) sil
    # (zero-width space, zero-width joiner vs.)
    text = "".join(
        ch for ch in text
        if unicodedata.category(ch) != "Cf"
    )

    # Satır sonlarını normalize et
    text = text.replace("\r\n", "\n")

    # Aynı satırdaki fazla boşlukları sıkıştır
    text = re.sub(r"[ \t]+", " ", text)

    # Birden fazla boş satırı tek boş satıra indir
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()