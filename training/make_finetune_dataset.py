import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
LABELED_PATH = BASE_DIR / "data" / "train" / "labeled_emails.jsonl"

OUT_IO_PATH = BASE_DIR / "data" / "train" / "finetune_io_dataset.jsonl"
OUT_CHAT_PATH = BASE_DIR / "data" / "train" / "finetune_chat_dataset.jsonl"

def main():
    print(f"Labeled file: {LABELED_PATH}")
    assert LABELED_PATH.exists(), f"Labeled file not found: {LABELED_PATH}"

    records = []
    with LABELED_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"Loaded {len(records)} labeled records")

    # 1) Basit input/output dataset
    with OUT_IO_PATH.open("w", encoding="utf-8") as fo:
        count = 0
        for r in records:
            text = (r.get("text") or "").strip()
            label = r.get("label") or {}
            if not text or not label:
                continue
            instruction = (
                "Aşağıda bir seyahat talebi e-postasının gövdesi var. "
                "Bu metinden sadece geçerli JSON formatında flight/hotel/transfer "
                "taleplerini çıkar. JSON dışında hiçbir şey yazma."
            )
            obj = {
                "input": instruction + "\n\nE-posta gövdesi:\n" + text,
                "output": json.dumps(label, ensure_ascii=False),
            }
            fo.write(json.dumps(obj, ensure_ascii=False) + "\n")
            count += 1

    print(f"Wrote {count} examples to {OUT_IO_PATH}")

    # 2) Chat-style dataset (istersen ileride kullanırız)
    SYSTEM_PROMPT = (
        "Sen kurumsal seyahat taleplerini anlayan bir asistansın. "
        "Görevin, verilen e-posta gövdesinden uçuş / otel / transfer "
        "taleplerini standart JSON şemasına uygun olarak çıkarmaktır. "
        "Sadece geçerli JSON döndür."
    )

    with OUT_CHAT_PATH.open("w", encoding="utf-8") as fo:
        count_chat = 0
        for r in records:
            text = (r.get("text") or "").strip()
            label = r.get("label") or {}
            if not text or not label:
                continue

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Aşağıdaki e-posta gövdesinden seyahat taleplerini JSON formatında çıkar:\n\n"
                        + text
                    ),
                },
                {
                    "role": "assistant",
                    "content": json.dumps(label, ensure_ascii=False),
                },
            ]
            fo.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
            count_chat += 1

    print(f"Wrote {count_chat} examples to {OUT_CHAT_PATH}")


if __name__ == "__main__":
    main()
