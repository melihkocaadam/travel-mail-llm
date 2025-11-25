# training/train_t5_slots.py

from pathlib import Path

import mlflow
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
)


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "train" / "finetune_slots_dataset.jsonl"

MODEL_NAME = "t5-small"
OUTPUT_DIR = BASE_DIR / "models" / "t5-slots-extractor"

MAX_INPUT_LENGTH = 256
MAX_TARGET_LENGTH = 256

BATCH_SIZE = 1
NUM_EPOCHS = 10
LR = 1e-4
SEED = 42


def main():
    assert DATA_PATH.exists(), f"Dataset not found: {DATA_PATH}"

    print(f"Using dataset: {DATA_PATH}")

    raw_ds = load_dataset("json", data_files=str(DATA_PATH))["train"]
    print("Total examples:", len(raw_ds))

    # train/val split
    ds = raw_ds.train_test_split(test_size=0.15, seed=SEED)
    train_ds = ds["train"]
    val_ds = ds["test"]

    print("Train size:", len(train_ds))
    print("Validation size:", len(val_ds))

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        model.config.pad_token_id = tokenizer.pad_token_id

    def preprocess(batch):
        # input: e-posta metni
        model_inputs = tokenizer(
            batch["input"],
            max_length=MAX_INPUT_LENGTH,
            truncation=True,
        )

        # target: slot formatı
        with tokenizer.as_target_tokenizer():
            labels = tokenizer(
                batch["target"],
                max_length=MAX_TARGET_LENGTH,
                truncation=True,
            )

        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    train_ds_tokenized = train_ds.map(preprocess, batched=True)
    val_ds_tokenized = val_ds.map(preprocess, batched=True)

    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

    training_args = Seq2SeqTrainingArguments(
        output_dir=str(OUTPUT_DIR),
        overwrite_output_dir=True,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        learning_rate=LR,
        weight_decay=0.01,
        predict_with_generate=True,
        generation_max_length=MAX_TARGET_LENGTH,
        save_total_limit=2,
        seed=SEED,
    )

    mlflow.set_experiment("t5-slots-extractor")

    with mlflow.start_run():
        mlflow.log_params(
            {
                "model_name": MODEL_NAME,
                "max_input_len": MAX_INPUT_LENGTH,
                "max_target_len": MAX_TARGET_LENGTH,
                "batch_size": BATCH_SIZE,
                "num_epochs": NUM_EPOCHS,
                "learning_rate": LR,
            }
        )

        trainer = Seq2SeqTrainer(
            model=model,
            args=training_args,
            train_dataset=train_ds_tokenized,
            eval_dataset=val_ds_tokenized,
            tokenizer=tokenizer,
            data_collator=data_collator,
        )

        trainer.train()
        trainer.save_model(OUTPUT_DIR)
        tokenizer.save_pretrained(OUTPUT_DIR)

        print(f"Training finished. Model saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
