from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL_DIR = r"C:\python_scripts\travel-mail-llm\models\mt5-json-extractor"

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_DIR)

def predict_json(mail_body: str) -> str:
    prompt = "E-posta içeriği:\n" + mail_body
    inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=256)
    outputs = model.generate(**inputs, max_length=256)
    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return text

sample = """
Merhaba,
2-5 Aralık tarihleri arasında Berlin için uçak ve otel rica ederiz.
2 kişi ekonomi sınıfı, THY olabilir.
"""

def main():
    print(predict_json(sample))

if __name__ == "__main__":
    main()