# Travel Email Intent & JSON Extractor – Proje Dokümantasyonu

Projeyi bu linkten deneyebilirsiniz -> https://travel-mail-llm-melih.streamlit.app/

## 1. Bu projeyi neden yaptım?

MICE / kurumsal seyahat tarafında gerçek hayat şöyle işliyor:

- Müşteri talepleri ağırlıklı **e‑posta ile** geliyor.
- Format yok: kimi iki satır yazıyor, kimi Excel yapıştırıyor, kimi mobilden forward’lıyor.
- Aynı mailde hem **uçak**, hem **otel**, hem **transfer** isteği olabiliyor.
- Bu mailleri her seferinde insan gözüyle okuyup yorumlamak zaman kaybı.

Benim amacım:

- Müşteri mailini okuyup:
  - Bu mailde **uçak mı istenmiş, otel mi, transfer mi**, hepsini tespit eden,
  - Uçuş için tarih, rota, kişi sayısı, kabin, havayolu tercihi… gibi alanları
  - Otel için şehir, tarih aralığı, kişi sayısı, amaç vs.
  - Transfer için yön, tarih, kişi sayısı…
- Bütün bunları **tek bir standart JSON şemasına** çıkaran,
- Mümkünse **lokalde koşan**, kuruma özel bir LLM modeli geliştirmekti.

Kısaca:  
“Mail okuyan, talebi anlayan ve operasyona hazır JSON üreten bir seyahat asistanı” yapmak istedim.

---

## 2. Veriyi nasıl topladım?

### 2.1. Dağıtım grubu gerçeği

Başta sanıyordum ki talepler bir shared mailbox’a düşüyor.  
Sonra ortaya çıktı ki bunların çoğu **distribution group**:

- `locktonbilet@...`, `dfdstalep@...` gibi adresler aslında mailbox değil,
- Sadece içindeki üyelere mail forward eden gruplar.

Graph API ile bu gruplardan direkt mail çekemediğim için şu yolu izledim:

1. Bu gruplarda en çok mail alan temsilcileri tespit ettim.
2. O temsilcilerin Outlook’unda özel bir klasör açtım: **TrainMails**
3. İlgili mailleri (uçak/otel/transfer içerikleri) bu klasöre topladım.

Böylece eğitim verisini okuyabileceğim **gerçek bir mailbox klasörüm** oluştu.

---

### 2.2. Microsoft Graph API ile mail çekme

Bunun için `email_ingestion` modülünü yazdım:

- `email_ingestion/graph_client.py`
  - Microsoft Identity üzerinden **client credential** ile access token alıyor
  - Belirlenen mailbox ve klasörden (`GRAPH_USER_MAIL` + `TrainMails`) mailleri çekiyor
  - `subject`, `receivedDateTime`, `from`, `to` ve temizlenmiş gövdeyi alıyor

- `email_ingestion/fetch_training_batch.py`
  - Konfigürasyonu `.env` içinden okuyor (tenant id, client id, secret, mail vs.)
  - GraphClient ile maksimum X adet maili çekiyor
  - Sonuçları **append modunda** `data/train/raw_emails.jsonl` dosyasına yazıyor

Bu sayede, gerektiği zaman yeni training maillerini kolayca ekleyebiliyorum.

---

## 3. Mailleri temizleme & normalleştirme

Gövde tarafında ciddi gürültü var:

- Forward chain’ler, “Original Message” blokları,
- Uzun legal disclaimer’lar,
- Mail imzaları (isim, ünvan, adres, telefon),
- HTML kalıntıları, unicode çöpleri (zero-width vb.).

Bunları çözmek için:

1. **Plain text’e dönüştürme**  
   - HTML gövdeleri text’e çevirdim.
   - Gereksiz boşlukları, tekrarlayan satırları temizledim.

2. **Spam / legal bloklarını ayıklama**  
   - “Bu e-posta iletisi…”, “Bu mesaj ve ekleri gizlidir…”, “Hizmete özel | Restricted” gibi kalıplar için  
     bir keyword listesi oluşturdum.
   - Bu keyword’leri barındıran blokları tail’den kırparak attım.

3. **İmza / iletişim bilgisi bloklarını temizleme**  
   - Tipik imza pattern’leri: isim, ünvan, şirket adı, adres, telefon
   - Bunlara benzer blokları gövdeden çıkardım.

4. **En anlamlı bloğu seçme (best block scoring)**  
   Tek bir mail gövdesi içinde:
   - Birden fazla segment olabiliyor (ör. asıl talep + altta forward edilmiş eski yazışma).
   - Her segmenti skorlayıp (tarih/strateji, seyahat kelimeleri, long text vs.)
   - **en anlamlı segmenti** “text” alanına aldım.

Sonuç:  
Modeli eğitirken kullandığım “text”, büyük ölçüde **müşteri talebini anlatan net gövde**.

Bu temizlenmiş içerik sonrasında label’lama ve eğitimde kullanıldı.

---

## 4. Labeling: OpenAI’dan nasıl faydalandım?

Burada iki farklı adımı birbirinden ayırdım:

1. **Label üretimi** (OpenAI ile)
2. **Model eğitimi** (tamamen kendi tarafımda, local)

### 4.1. Neden OpenAI ile label’ladım?

- 2000+ maili **elle etiketlemek gerçekçi değil**.
- Bana gereken şey, belli sayıda (200–300 gibi) kaliteli, JSON formatında etiketli örnek.
- OpenAI’ı burada “akıllı etiketçi” gibi kullandım:
  - Her mail gövdesini OpenAI’a gönderdim,
  - Uçak / otel / transfer isteklerini belirli JSON şemasına göre çıkarmasını istedim,
  - Sonuçları kontrol edilebilir bir jsonl dosyasına yazdım.

OpenAI burada **sadece** training datası hazırlamak için kullanıldı.  
Eğitilen modelin kendisi %100 lokal.

### 4.2. Labeling pipeline

- `labeling/openai_label_batch.py`
  - `raw_emails.jsonl` içindeki mailleri okuyor
  - Temizlenmiş gövdeyi, tasarladığım JSON şema açıklamasıyla beraber OpenAI Chat API’ye gönderiyor
  - OpenAI’nin döndürdüğü JSON’u Pydantic ile validate ediyor
  - Valid olanları `labeled_emails.jsonl` dosyasına **append** ediyor
  - Parse edilemeyenleri veya hatalı gelenleri `review_needed=true` işaretliyor

Label kaydı örneği:

- `text` → Temizlenmiş mail içeriği
- `label` → `{"requests": [... flight/hotel/transfer objeleri ...]}`

Bu aşamanın sonunda **200+ sağlam etiketli kayıt** elde ettim.

---

## 5. Model seçimi: T5-small’dan Flan-T5-base’e giden yol

İlk denememi **T5-small** ile yaptım:

- MODEL: `t5-small`
- Avantaj: Hafif, hızlı
- Dezavantaj: Küçük model + karmaşık JSON şeması + küçük dataset

Sonuç:

- Model “uçak / otel / transfer” kavramlarını bir miktar öğrendi,
- Ama **JSON formatını çok sık bozdu**:
  - Fazladan stringler,
  - Eksik tırnak / köşeli parantez,
  - Çıktının başına eski prompt cümlelerini kusma,
  - Çok uzun ve tekrar eden alanlar.

Ben de şu sonuca vardım:

> “Bu problem, salt encoder-decoder kapasitesinden çok,  
> instruction anlayışı ve JSON formatına disiplin gerektiriyor.  
> Yani biraz daha akıllı bir model ailesine geçmem lazım.”

### 5.1. Neden Flan-T5 ailesine geçtim?

**Flan-T5** (özellikle flan-t5-base):

- Zaten **instruction-tuned**:
  - “Sadece JSON döndür”
  - “Açıklama yazma”
  gibi komutları plain T5’e göre çok daha iyi kavrıyor.
- Çok dilli senaryolarda (TR/EN karışık mail) oldukça başarılı.
- Model ailesi yine T5 tabanlı → Kod tarafında mimariyi kökten değiştirmem gerekmiyor.
- `flan-t5-base` boyut / performans açısından **sweet spot**:
  - `small`’dan çok daha yetenekli,
  - `large`a göre çok daha makul eğitim süresi ve kaynak tüketimi.

Bu yüzden final model olarak **`google/flan-t5-base`**’i seçtim.

`flan-t5-large`’ı da denedim:
- `model.safetensors` ~3.3 GB,
- Eğitim süresi CPU’da 7+ saatlere gidiyordu,
- Bu proje için maliyeti getirisine göre fazla bulup  
  **flan-t5-base’e geri döndüm**.

---

## 6. Fine-tuning: Dataset ve eğitim scriptleri

### 6.1. Fine-tune dataset hazırlama

`training/make_finetune_dataset.py`:

- Girdi: `data/train/labeled_emails.jsonl`
- Çıkış:
  - `data/train/finetune_io_dataset.jsonl`
  - (isteğe bağlı) `finetune_chat_dataset.jsonl`

`finetune_io_dataset.jsonl` formatı:

```json
{"input": "<instruction + e-posta gövdesi>", "output": "{... JSON ...}"}
```

Örneğin:

```python
instruction = (
    "Aşağıda bir seyahat talebi e-postasının gövdesi var. "
    "Bu metinden sadece geçerli JSON formatında flight/hotel/transfer "
    "taleplerini çıkar. JSON dışında hiçbir şey yazma."
)

obj = {
    "input": instruction + "

E-posta gövdesi:
" + text,
    "output": json.dumps(label, ensure_ascii=False),
}
```

Burada kritik nokta şu:

- **Eğitimde kullandığım input pattern’i ile inference’ta kullandığım prompt birebir aynı.**

Bu, Flan-T5’in instruction kapasitesini tam kullanmamı sağladı.

---

### 6.2. Eğitim scripti: `training/train_mt5_json_extractor.py`

Bu script aslında T5 için yazılmıştı, ben modeli Flan’a çevirdim:

```python
MODEL_NAME = "google/flan-t5-base"
OUTPUT_DIR = BASE_DIR / "models" / "flan-t5-json-extractor-v1"

MAX_INPUT_LENGTH = 512
MAX_TARGET_LENGTH = 256

BATCH_SIZE = 1              # CPU için dengeli
NUM_EPOCHS = 5
LR = 5e-5                   # Instruction-tuned model için konservatif LR
SEED = 42
```

Pipeline:

1. `finetune_io_dataset.jsonl` dosyasını okuyor
2. Train / validation split yapıyor (örneğin %80 / %20)
3. Tokenizer & modeli yüklüyor:
   ```python
   tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
   model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
   ```
4. Dataset’i token’lıyor:
   - `input` → encoder
   - `output` → decoder hedefi
5. `Seq2SeqTrainer` ile eğitiyor:
   - Loss fonksiyonu: cross-entropy
   - Değerlendirme: eval loss (JSON doğruluğu ana metrik)

Eğitim sonunda:

```text
Training finished. Model saved to: models/flan-t5-json-extractor-v1
```

Bu klasörde:

- `config.json`
- `tokenizer.json` / `spiece.model`
- `model.safetensors`
- `generation_config.json`

gibi Hugging Face formatında tüm dosyalar oluşuyor.

---

## 7. Inference & Streamlit demo

Modeli insan gibi test etmek için basit bir **Streamlit arayüzü** yazdım.

### 7.1. Prompt

Streamlit tarafındaki `run_inference` fonksiyonu, eğitimdeki pattern’i aynen kullanıyor:

```python
instruction = (
    "Aşağıda bir seyahat talebi e-postasının gövdesi var. "
    "Bu metinden sadece geçerli JSON formatında flight/hotel/transfer "
    "taleplerini çıkar. JSON dışında hiçbir şey yazma."
)

prompt = instruction + "

E-posta gövdesi:
" + mail_body.strip()
```

### 7.2. Model çağrısı

```python
inputs = tokenizer(
    [prompt],
    return_tensors="pt",
    truncation=True,
    max_length=MAX_INPUT_LENGTH,
)

outputs = model.generate(
    **inputs,
    max_length=MAX_OUTPUT_LENGTH,   # 256
    num_beams=4,
    early_stopping=True,
)

text = tokenizer.decode(outputs[0], skip_special_tokens=True)
```

Buradaki hedef:

- Flan-T5-base’e “sadece JSON yaz” dediğim için,
- `text` çıktısı büyük oranda **direkt `json.loads` yapılabilir** hale geliyor.

### 7.3. JSON parse

İlk denemede basit tuttum:

```python
def try_parse_json(text: str):
    import json
    try:
        return json.loads(text.strip()), None
    except Exception as e:
        return None, str(e)
```

Flan-T5-base ile bu yaklaşım, T5-small’a göre ciddi oranda daha başarılı.  
Gerektiğinde fallback olarak “ilk `{` ile son `}` arasını alıp parse etme” gibi robustifier’lar da eklenebilir.

---

## 8. Kurulum & Çalıştırma

### 8.1. Ortam kurulumu

```bash
git clone <repo-url>
cd travel-mail-llm

python -m venv .venv
.\.venv\Scriptsctivate   # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

### 8.2. .env dosyası

Proje kökünde bir `.env` dosyası oluşturuyorum:

```env
GRAPH_TENANT_ID=...
GRAPH_CLIENT_ID=...
GRAPH_CLIENT_SECRET=...
GRAPH_USER_MAIL=melih.ko@...

OPENAI_API_KEY=sk-...   # sadece labeling sırasında kullanılıyor
```

### 8.3. Eğitim verisini toplama

Outlook tarafında `TrainMails` klasörüne mailleri topladıktan sonra:

```bash
python -m email_ingestion.fetch_training_batch
```

Bu komut:

- Graph API ile mailleri çekiyor,
- `data/train/raw_emails.jsonl` dosyasına append ediyor.

### 8.4. Labeling

```bash
python -m labeling.openai_label_batch
```

- OpenAI ile her maili şemaya göre JSON’a çeviriyor,
- `data/train/labeled_emails.jsonl` dosyasına append ediyor.

### 8.5. Fine-tune dataset üretimi

```bash
python -m training.make_finetune_dataset
```

- `data/train/finetune_io_dataset.jsonl` oluşturuluyor.

### 8.6. Model eğitimi (Flan-T5-base)

```bash
python -m training.train_mt5_json_extractor
```

Eğitim sonunda model burada:

```text
models/flan-t5-json-extractor-v1/
```

### 8.7. Streamlit demo

```bash
streamlit run streamlit_app/app.py
```

Arayüz:

1. Birinci kutuya müşteri mailini yapıştırıyorum.
2. “Model çıktısı” alanında ham string’i görüyorum.
3. “JSON parse sonucu” alanında, parse edilmiş ve pretty-print edilmiş `requests` yapısını görüyorum.

---

## 9. Sonuç & öğrenilenler

Bu proje boyunca:

- Sadece model eğitimi değil, **uçtan uca bir LLM ürününün tüm yaşam döngüsünü** deneyimledim:
  - Veri toplama (Graph API, dağıtım grubu workaround’u),
  - Veri temizleme (imza, legal, forward zinciri),
  - Labeling stratejisi (OpenAI ile semi-otomatik etiketleme),
  - Pydantic ile şema validasyonu,
  - T5-small ile ilk deneme ve yaşanan JSON format sorunları,
  - Flan-T5-base’e geçiş kararı (instruction tuning avantajı),
  - Eğitim parametrelerinin pratikte ayarlanması (seq length, batch, epoch, LR),
  - Streamlit ile pratik demo hazırlama.

En önemlisi:

- Tamamen **kuruma özel**,  
- Local ortamda koşabilen,  
- E‑posta → JSON seyahat talep çıkarımı yapan  
bir model ortaya çıkmış oldu.

Bunu bitirme projesi olarak sunarken:

> “Sadece model eğitmedim; veri toplama, temizleme, etiketleme, eğitim ve inference’ı kapsayan tüm pipeline’ı tasarladım.”

diyebileceğim gayet somut bir işim var artık.
