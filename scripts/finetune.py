# scripts/finetune.py
import json
from pathlib import Path
from typing import List, Tuple
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OUT_DIR = Path("checkpoints/finetuned")
TRAIN = Path("data/train.jsonl")
VALID = Path("data/valid.jsonl")

def load_jsonl(path: Path) -> List[Tuple[str, str]]:
    pairs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            pairs.append((obj["text"], obj["label"]))
    return pairs

def to_examples(pairs):
    return [InputExample(texts=[t, l], label=1.0) for t, l in pairs]

def main():
    train_pairs = load_jsonl(TRAIN) if TRAIN.exists() else []
    valid_pairs = load_jsonl(VALID) if VALID.exists() else []
    if not train_pairs:
        print("no train data")
        return

    model = SentenceTransformer(MODEL_ID)
    train_loader = DataLoader(to_examples(train_pairs), batch_size=16, shuffle=True)
    loss_fn = losses.CosineSimilarityLoss(model)
    model.fit(train_objectives=[(train_loader, loss_fn)], epochs=3, warmup_steps=100, output_path=str(OUT_DIR))
    print("saved ->", OUT_DIR)

if __name__ == "__main__":
    main()