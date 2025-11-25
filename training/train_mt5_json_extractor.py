import os
import json
from pathlib import Path

import mlflow
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
)

# ==============================
#  Config
# ==============================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "train" / "finetune_io_dataset.jsonl"
# MODEL_NAME = "t5-small" # "t5-11b", "t5-base", "t5-large"
# OUTPUT_DIR = BASE_DIR / "models" / "t5-json-extractor-v2"
MODEL_NAME = "google/flan-t5-base" # "flan-t5-base", "flan-t5-large", "flan-t5-small"
OUTPUT_DIR = BASE_DIR / "models" / "flan-t5-json-extractor-v2"

MAX_INPUT_LENGTH = 512     # mail gövdesi için
MAX_TARGET_LENGTH = 256    # JSON string için

BATCH_SIZE = 2              # GPU yoksa küçük tut paralel eğitim için
NUM_EPOCHS = 8              # epoch sayısı, aynı dataseti kaç kez eğiteceğini belirler
LR = 5e-5                  # learning rate, model ağırlıklarının ne kadar agresif değişeceğini belirler  
SEED = 42                   # random seed, rasgelelik için sabit değer.


def main():
    print(f"Using dataset: {DATA_PATH}")
    assert DATA_PATH.exists(), f"Dataset not found: {DATA_PATH}"

    # ==============================
    #  MLflow ayarları
    # ==============================
    # İstersen önce environment değişkeni ile tracking URI belirle:
    # os.environ["MLFLOW_TRACKING_URI"] = "file://" + str(BASE_DIR / "mlruns")
    mlflow.set_experiment("travel_mail_json_extractor")

    # ==============================
    #  Dataset yükleme (JSONL)
    # ==============================
    raw_dataset = load_dataset(
        "json",
        data_files=str(DATA_PATH),
        split="train",
    )

    # train/validation split
    ds = raw_dataset.train_test_split(test_size=0.15, seed=SEED)
    train_ds = ds["train"]
    val_ds = ds["test"]

    print("Train size:", len(train_ds))
    print("Validation size:", len(val_ds))

    # ==============================
    #  Tokenizer & Model
    # ==============================
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

    # Bazı mT5 tokenizer'larında padding token yok, düzeltelim
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        model.config.pad_token_id = tokenizer.pad_token_id

    # ==============================
    #  Preprocess (tokenization)
    # ==============================

    def preprocess_fn(batch):
        """
        batch["input"]  : e-posta gövdesi
        batch["output"] : JSON string (label)
        """
        inputs = [
            "E-posta içeriği:\n" + x
            for x in batch["input"]
        ]
        targets = batch["output"]

        model_inputs = tokenizer(
            inputs,
            max_length=MAX_INPUT_LENGTH,
            truncation=True,
            padding="max_length",
        )

        with tokenizer.as_target_tokenizer():
            labels = tokenizer(
                targets,
                max_length=MAX_TARGET_LENGTH,
                truncation=True,
                padding="max_length",
            )

        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    tokenized_train = train_ds.map(
        preprocess_fn,
        batched=True,
        remove_columns=train_ds.column_names,
    )
    tokenized_val = val_ds.map(
        preprocess_fn,
        batched=True,
        remove_columns=val_ds.column_names,
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model,
        padding="longest",
    )

    # ==============================
    #  TrainingArguments
    # ==============================
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(OUTPUT_DIR),
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LR,
        predict_with_generate=True,
    )

    # ==============================
    #  Trainer
    # ==============================
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_val,
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    # ==============================
    #  MLflow run içinde eğit
    # ==============================
    with mlflow.start_run(run_name="mt5_json_extractor"):
        # Bazı temel parametreleri loglayalım
        mlflow.log_params(
            {
                "model_name": MODEL_NAME,
                "max_input_length": MAX_INPUT_LENGTH,
                "max_target_length": MAX_TARGET_LENGTH,
                "batch_size": BATCH_SIZE,
                "num_epochs": NUM_EPOCHS,
                "learning_rate": LR,
            }
        )

        trainer.train()

        # En iyi modeli kaydet
        trainer.save_model(str(OUTPUT_DIR))
        tokenizer.save_pretrained(str(OUTPUT_DIR))

        print("Training finished. Model saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
