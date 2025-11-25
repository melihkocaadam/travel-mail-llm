import json
from pathlib import Path

import streamlit as st
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


# ==============================
#  Config
# ==============================

BASE_DIR = Path(__file__).resolve().parent
# MODEL_DIR = BASE_DIR / "models" / "mt5-json-extractor"  # hafif model
# MODEL_DIR = BASE_DIR / "models" / "flan-t5-json-extractor-v2"  # ağır model
MODEL_DIR = "melihkocaadam/flan-t5-json-extractor-v2"  # HF modeli

MAX_INPUT_LENGTH = 256
MAX_OUTPUT_LENGTH = 256


@st.cache_resource
def load_model_and_tokenizer():
    if isinstance(MODEL_DIR, Path) and not MODEL_DIR.exists():
        raise RuntimeError(f"Model klasörü bulunamadı: {MODEL_DIR}")
    elif isinstance(MODEL_DIR, str):
        st.info(f"Huggingface Hub'dan model indiriliyor: {MODEL_DIR} (ilk seferde biraz zaman alabilir)")

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForSeq2SeqLM.from_pretrained(str(MODEL_DIR))

    # padding ayarı (gerekirse)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        model.config.pad_token_id = tokenizer.pad_token_id

    return tokenizer, model


def run_inference(mail_body: str) -> str:
    tokenizer, model = load_model_and_tokenizer()

    instruction = (
        "Aşağıda bir seyahat talebi e-postasının gövdesi var. "
        "Bu metinden sadece geçerli JSON formatında flight/hotel/transfer "
        "taleplerini çıkar. JSON dışında hiçbir şey yazma."
    )

    prompt = instruction + "\n\nE-posta gövdesi:\n" + mail_body.strip()

    inputs = tokenizer(
        [prompt],
        return_tensors="pt",
        truncation=True,
        max_length=MAX_INPUT_LENGTH,
    )

    outputs = model.generate(
        **inputs,
        max_length=MAX_OUTPUT_LENGTH,
        num_beams=4,
        early_stopping=True,
    )

    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return text

def try_parse_json(text: str):
    try:
        return json.loads(text.strip()), None
    except Exception as e:
        return None, str(e)
    
# ==============================
#  Streamlit UI
# ==============================

st.set_page_config(page_title="Travel Mail LLM Demo", layout="wide")

st.title("✈️ Travel Mail LLM – Demo")
st.markdown(
    """
Bu ekran, **e-posta ile gelen uçuş / otel / transfer taleplerini** çıkaran
fine-tune ettiğimiz modeli test etmek için hazırlandı.

Sol tarafa, müşteri maili gibi bir metin yaz → **Model JSON çıktı üretsin.**
"""
)

with st.sidebar:
    st.header("Ayarlar")
    st.write(f"Model klasörü: `{MODEL_DIR}`")
    st.write(f"Maks. input uzunluğu: {MAX_INPUT_LENGTH}")
    st.write(f"Maks. output uzunluğu: {MAX_OUTPUT_LENGTH}")

    st.markdown("---")
    st.caption("Not: Bu demo sadece lokal olarak çalışmaktadır.")

st.subheader("1) E-posta içeriği")

default_example = """\
Merhaba,

1 aralık  7 aralık tarihleri arasında istanbul'dan paris'e uçacağım. 2 kişilik rezervasyon olsun.
ayrıca havalimanına yakın bir otel rezervasyonu da yapılmalı.
PO numarası MLH6346232 olarak girilsin lütfen.

Teşekkürler.
"""

mail_text = st.text_area(
    "Müşterinin gönderdiği e-posta gövdesini buraya yazın / yapıştırın:",
    value=default_example,
    height=260,
)

col1, col2 = st.columns([1, 3])

with col1:
    run_button = st.button("📤 Çözümle", type="primary")

with col2:
    st.write("")

st.subheader("2) Model Çıktısı")

if run_button:
    if not mail_text.strip():
        st.warning("Lütfen önce bir e-posta metni gir.")
    else:
        with st.spinner("Model çalışıyor, JSON çıkarılıyor..."):
            raw_output = run_inference(mail_text)

        st.markdown("**Ham model çıktısı (string):**")
        st.code(raw_output, language="json")

        parsed, err = try_parse_json(raw_output)
        if parsed is not None:
            st.markdown("**Parse edilmiş JSON (güzel formatlanmış):**")
            st.json(parsed)
        else:
            st.error("JSON parse edilemedi:")
            st.code(err)
else:
    st.info("Sol taraftaki metni düzenleyip **📤 Çözümle** butonuna basabilirsin.")
