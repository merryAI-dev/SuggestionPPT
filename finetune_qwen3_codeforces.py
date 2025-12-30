"""
Fine-tune Qwen3-0.6B on open-r1/codeforces-cots dataset
Using SFTTrainer from TRL with LoRA for efficient training
"""

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTConfig, SFTTrainer

# ============================================
# Configuration
# ============================================

MODEL_NAME = "Qwen/Qwen3-0.6B"
DATASET_NAME = "open-r1/codeforces-cots"
DATASET_SUBSET = "solutions"  # Options: solutions, solutions_w_editorials, solutions_py, etc.
OUTPUT_DIR = "./qwen3-0.6b-codeforces-finetuned"

# Training hyperparameters
BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 8  # Effective batch size = 2 * 8 = 16
LEARNING_RATE = 2e-4
NUM_EPOCHS = 1
MAX_SEQ_LENGTH = 2048
WARMUP_RATIO = 0.03

# LoRA configuration
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05

# Use 4-bit quantization for memory efficiency (optional)
USE_4BIT = True


def main():
    print("=" * 60)
    print("Fine-tuning Qwen3-0.6B on CodeForces-CoTs Dataset")
    print("=" * 60)

    # ============================================
    # 1. Load Dataset
    # ============================================
    print("\n[1/5] Loading dataset...")

    dataset = load_dataset(DATASET_NAME, DATASET_SUBSET, split="train")
    print(f"Dataset loaded: {len(dataset)} examples")
    print(f"Dataset columns: {dataset.column_names}")

    # The dataset has a 'messages' column ready for SFT
    # Sample format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    print(f"\nSample data structure:")
    print(f"Keys: {dataset[0].keys()}")

    # ============================================
    # 2. Load Tokenizer
    # ============================================
    print("\n[2/5] Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)

    # Ensure padding token is set
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tokenizer.padding_side = "right"  # Required for training

    print(f"Tokenizer loaded. Vocab size: {tokenizer.vocab_size}")

    # ============================================
    # 3. Load Model with Quantization (optional)
    # ============================================
    print("\n[3/5] Loading model...")

    if USE_4BIT:
        # 4-bit quantization config for memory efficiency
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

        # Prepare model for k-bit training
        model = prepare_model_for_kbit_training(model)
        print("Model loaded with 4-bit quantization")
    else:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )
        print("Model loaded in bfloat16")

    # ============================================
    # 4. Configure LoRA
    # ============================================
    print("\n[4/5] Configuring LoRA...")

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ============================================
    # 5. Configure Training
    # ============================================
    print("\n[5/5] Setting up trainer...")

    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        warmup_ratio=WARMUP_RATIO,
        lr_scheduler_type="cosine",
        max_seq_length=MAX_SEQ_LENGTH,

        # Logging
        logging_steps=10,
        logging_dir=f"{OUTPUT_DIR}/logs",

        # Saving
        save_strategy="steps",
        save_steps=500,
        save_total_limit=3,

        # Optimization
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit" if USE_4BIT else "adamw_torch",

        # Dataset
        dataset_text_field="messages",  # The codeforces-cots dataset has 'messages' column
        packing=False,  # Disable packing for reasoning traces (they can be long)

        # Misc
        report_to="tensorboard",
        seed=42,
    )

    # ============================================
    # 6. Initialize Trainer and Train
    # ============================================
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    print("\n" + "=" * 60)
    print("Starting training...")
    print("=" * 60)

    # Train!
    trainer.train()

    # ============================================
    # 7. Save Final Model
    # ============================================
    print("\n" + "=" * 60)
    print("Saving model...")
    print("=" * 60)

    # Save the LoRA adapter
    trainer.save_model(f"{OUTPUT_DIR}/final")
    tokenizer.save_pretrained(f"{OUTPUT_DIR}/final")

    print(f"\nTraining complete! Model saved to: {OUTPUT_DIR}/final")
    print("\nTo load the fine-tuned model:")
    print(f"""
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

model = AutoPeftModelForCausalLM.from_pretrained("{OUTPUT_DIR}/final")
tokenizer = AutoTokenizer.from_pretrained("{OUTPUT_DIR}/final")

# Or merge LoRA weights into base model:
merged_model = model.merge_and_unload()
merged_model.save_pretrained("{OUTPUT_DIR}/merged")
""")


if __name__ == "__main__":
    main()
