"""
한국어 맞춤법/통일성 검사 모델 파인튜닝 (Apple Silicon MPS 버전)

Qwen3-0.6B를 한국어 맞춤법 교정용으로 파인튜닝합니다.

사용법:
    1. 먼저 데이터셋 생성: python build_spelling_dataset.py
    2. 파인튜닝 실행: python finetune_spelling_mps.py
"""

import torch
import json
from pathlib import Path
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import SFTConfig, SFTTrainer
import os

# ============================================
# 설정
# ============================================

MODEL_NAME = "Qwen/Qwen3-0.6B"
DATASET_PATH = "./learning_data/spelling_dataset.json"
OUTPUT_DIR = "./qwen3-spelling-checker"

# 학습 하이퍼파라미터
BATCH_SIZE = 1
GRADIENT_ACCUMULATION_STEPS = 8
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3  # 작은 데이터셋이므로 더 많은 에폭
MAX_SEQ_LENGTH = 512  # 맞춤법 검사는 짧은 문장
WARMUP_RATIO = 0.1

# LoRA 설정
LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.05


def check_mps():
    """MPS 사용 가능 여부 확인"""
    print("=" * 60)
    print("🍎 Apple Silicon MPS 환경 확인")
    print("=" * 60)

    if torch.backends.mps.is_available():
        print("✅ MPS 사용 가능!")
        print(f"   PyTorch 버전: {torch.__version__}")
        return "mps"
    else:
        print("⚠️ MPS 사용 불가, CPU로 진행")
        return "cpu"


def load_dataset_from_json(path: str) -> Dataset:
    """JSON 파일에서 데이터셋 로드"""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # messages 필드만 추출
    messages_list = [item["messages"] for item in data]

    return Dataset.from_dict({"messages": messages_list})


def main():
    device = check_mps()

    # MPS 메모리 관리
    os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

    # ============================================
    # 1. 데이터셋 로드
    # ============================================
    print("\n[1/5] 데이터셋 로딩 중...")

    dataset_path = Path(DATASET_PATH)
    if not dataset_path.exists():
        print(f"❌ 데이터셋을 찾을 수 없습니다: {dataset_path}")
        print("   먼저 실행하세요: python build_spelling_dataset.py")
        return

    dataset = load_dataset_from_json(DATASET_PATH)
    print(f"   로드된 샘플 수: {len(dataset)}개")

    # 데이터 샘플 확인
    print("\n   샘플 데이터:")
    sample = dataset[0]["messages"]
    print(f"   User: {sample[0]['content'][:50]}...")
    print(f"   Assistant: {sample[1]['content'][:50]}...")

    # ============================================
    # 2. 토크나이저 로드
    # ============================================
    print("\n[2/5] 토크나이저 로딩 중...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    print(f"   토크나이저 로드 완료")

    # ============================================
    # 3. 모델 로드
    # ============================================
    print(f"\n[3/5] 모델 로딩 중... (디바이스: {device})")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float32,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )

    model.gradient_checkpointing_enable()
    print(f"   모델 파라미터: {model.num_parameters():,}")

    # ============================================
    # 4. LoRA 설정
    # ============================================
    print("\n[4/5] LoRA 설정 중...")

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
    # 5. 학습 설정
    # ============================================
    print("\n[5/5] 트레이너 설정 중...")

    from transformers import TrainingArguments

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        warmup_ratio=WARMUP_RATIO,
        lr_scheduler_type="cosine",
        max_steps=-1,

        # 로깅
        logging_steps=5,
        logging_dir=f"{OUTPUT_DIR}/logs",

        # 저장
        save_strategy="epoch",
        save_total_limit=2,

        # MPS 최적화
        fp16=False,
        bf16=False,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="adamw_torch",

        # MPS
        use_mps_device=True if device == "mps" else False,
        dataloader_pin_memory=False,

        report_to="none",  # tensorboard 대신 none 사용
        seed=42,
    )

    # 데이터 전처리 함수 (단일 example용)
    def formatting_prompts_func(example):
        messages = example["messages"]
        text = tokenizer.apply_chat_template(messages, tokenize=False)
        return text

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        formatting_func=formatting_prompts_func,
    )

    # ============================================
    # 학습 시작
    # ============================================
    print("\n" + "=" * 60)
    print("🚀 한국어 맞춤법 검사 모델 파인튜닝 시작!")
    print("=" * 60)
    print(f"   디바이스: {device}")
    print(f"   샘플 수: {len(dataset)}")
    print(f"   에폭: {NUM_EPOCHS}")
    print(f"   배치 크기: {BATCH_SIZE} x {GRADIENT_ACCUMULATION_STEPS}")
    print("=" * 60)

    try:
        trainer.train()

        # 모델 저장
        print("\n💾 모델 저장 중...")
        trainer.save_model(f"{OUTPUT_DIR}/final")
        tokenizer.save_pretrained(f"{OUTPUT_DIR}/final")

        print(f"\n✅ 파인튜닝 완료!")
        print(f"   모델 저장 위치: {OUTPUT_DIR}/final")

        # 사용법 안내
        print("\n" + "=" * 60)
        print("📖 모델 사용법")
        print("=" * 60)
        print("""
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

model = AutoPeftModelForCausalLM.from_pretrained("./qwen3-spelling-checker/final")
tokenizer = AutoTokenizer.from_pretrained("./qwen3-spelling-checker/final")

# 맞춤법 검사
text = "스타트 업이 성공할수있도록 지원합니다."
prompt = f"다음 문장의 맞춤법과 용어 통일성을 검사하고 수정해주세요:\\n\\n{text}"

inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=200)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
""")

    except Exception as e:
        print(f"\n❌ 학습 중 오류: {e}")
        print("\n💡 해결 방법:")
        print("   1. MAX_SEQ_LENGTH를 256으로 줄여보세요")
        print("   2. BATCH_SIZE를 1로 유지하세요")
        raise


if __name__ == "__main__":
    main()
