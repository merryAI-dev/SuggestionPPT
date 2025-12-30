"""
Fine-tune Qwen3-0.6B on open-r1/codeforces-cots dataset
Apple Silicon MPS 버전 (Mac M1/M2/M3/M4/M5 지원)

사용법:
    python finetune_qwen3_mps.py
"""

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import SFTConfig, SFTTrainer
import os

# ============================================
# 설정
# ============================================

MODEL_NAME = "Qwen/Qwen3-0.6B"
DATASET_NAME = "open-r1/codeforces-cots"
DATASET_SUBSET = "solutions_py"  # Python 버전 (더 작음)
OUTPUT_DIR = "./qwen3-0.6b-codeforces-mps"

# 학습 하이퍼파라미터 (메모리 효율적으로 조정)
BATCH_SIZE = 1  # MPS에서는 작게
GRADIENT_ACCUMULATION_STEPS = 16  # 누적으로 보완
LEARNING_RATE = 2e-4
NUM_EPOCHS = 1
MAX_SEQ_LENGTH = 1024  # 메모리 절약
WARMUP_RATIO = 0.03
MAX_SAMPLES = 1000  # 테스트용으로 샘플 제한 (전체 학습시 None)

# LoRA 설정
LORA_R = 8  # 더 작은 rank로 메모리 절약
LORA_ALPHA = 16
LORA_DROPOUT = 0.05


def check_mps_availability():
    """MPS 사용 가능 여부 확인"""
    print("=" * 60)
    print("🍎 Apple Silicon MPS 환경 확인")
    print("=" * 60)

    if not torch.backends.mps.is_available():
        if not torch.backends.mps.is_built():
            print("❌ PyTorch가 MPS 지원 없이 빌드되었습니다.")
            print("   다음 명령으로 재설치하세요:")
            print("   pip install --upgrade torch torchvision torchaudio")
        else:
            print("❌ MPS 디바이스를 찾을 수 없습니다.")
        return False

    print("✅ MPS 사용 가능!")
    print(f"   PyTorch 버전: {torch.__version__}")

    # 간단한 MPS 테스트
    try:
        x = torch.ones(1, device="mps")
        print(f"   MPS 테스트: 성공")
    except Exception as e:
        print(f"   MPS 테스트 실패: {e}")
        return False

    return True


def main():
    # MPS 확인
    if not check_mps_availability():
        print("\n⚠️ MPS를 사용할 수 없어 CPU로 진행합니다 (매우 느림)")
        device = "cpu"
    else:
        device = "mps"

    # 환경 변수 설정 (MPS 메모리 관리)
    os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

    # ============================================
    # 1. 데이터셋 로드
    # ============================================
    print("\n[1/5] 데이터셋 로딩 중...")

    dataset = load_dataset(DATASET_NAME, DATASET_SUBSET, split="train")
    print(f"전체 데이터: {len(dataset)} 샘플")

    # 샘플 제한 (테스트용)
    if MAX_SAMPLES and len(dataset) > MAX_SAMPLES:
        dataset = dataset.select(range(MAX_SAMPLES))
        print(f"테스트용 샘플 제한: {len(dataset)} 샘플")

    print(f"데이터 컬럼: {dataset.column_names}")

    # ============================================
    # 2. 토크나이저 로드
    # ============================================
    print("\n[2/5] 토크나이저 로딩 중...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    print(f"토크나이저 로드 완료. 어휘 크기: {tokenizer.vocab_size}")

    # ============================================
    # 3. 모델 로드 (MPS/CPU)
    # ============================================
    print(f"\n[3/5] 모델 로딩 중... (디바이스: {device})")

    # MPS에서는 float32 사용 권장 (bfloat16 지원 제한적)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float32,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )

    # 그래디언트 체크포인팅 활성화 (메모리 절약)
    model.gradient_checkpointing_enable()

    print(f"모델 로드 완료: {MODEL_NAME}")
    print(f"모델 파라미터: {model.num_parameters():,}")

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

        # 로깅
        logging_steps=10,
        logging_dir=f"{OUTPUT_DIR}/logs",

        # 저장
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,

        # MPS 최적화
        fp16=False,  # MPS는 fp16 불안정
        bf16=False,  # MPS는 bf16 미지원
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="adamw_torch",  # MPS 호환 옵티마이저

        # 데이터셋
        dataset_text_field="messages",
        packing=False,

        # MPS 사용
        use_mps_device=True if device == "mps" else False,

        # 기타
        dataloader_pin_memory=False,  # MPS에서는 비활성화
        report_to="tensorboard",
        seed=42,
    )

    # ============================================
    # 6. 학습 시작
    # ============================================
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    print("\n" + "=" * 60)
    print("🚀 학습 시작!")
    print(f"   디바이스: {device}")
    print(f"   배치 크기: {BATCH_SIZE} x {GRADIENT_ACCUMULATION_STEPS} = {BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")
    print(f"   최대 시퀀스 길이: {MAX_SEQ_LENGTH}")
    print(f"   샘플 수: {len(dataset)}")
    print("=" * 60)
    print("\n⚠️ MPS 학습은 CUDA보다 느립니다. 커피 한 잔 하고 오세요 ☕")

    try:
        trainer.train()

        # 모델 저장
        print("\n" + "=" * 60)
        print("💾 모델 저장 중...")
        print("=" * 60)

        trainer.save_model(f"{OUTPUT_DIR}/final")
        tokenizer.save_pretrained(f"{OUTPUT_DIR}/final")

        print(f"\n✅ 학습 완료! 모델 저장 위치: {OUTPUT_DIR}/final")

    except Exception as e:
        print(f"\n❌ 학습 중 오류 발생: {e}")
        print("\n💡 해결 방법:")
        print("   1. MAX_SEQ_LENGTH를 512로 줄여보세요")
        print("   2. BATCH_SIZE를 1로 유지하세요")
        print("   3. MAX_SAMPLES를 500으로 줄여보세요")
        raise


if __name__ == "__main__":
    main()
