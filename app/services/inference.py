from pathlib import Path
from functools import lru_cache
from typing import Dict, List
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CLASS_NAMES = [
    "AMD",
    "Diabetic Retinopathy",
    "Glaucoma",
    "Healthy",
    "Retinal Detachment",
    "BRVO",
    "CRVO",
    "RAO",
    "Normal"
]

NUM_CLASSES = len(CLASS_NAMES)

BASE_DIR = Path(__file__).resolve().parents[2]
CHECKPOINT_PATH = BASE_DIR / "checkpoints" / "EfficientNet_best.pth"

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


def build_efficientnet() -> nn.Module:
    model = models.efficientnet_b0(weights=None)

    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features, NUM_CLASSES)
    )

    return model


@lru_cache(maxsize=1)
def load_model() -> nn.Module:
    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(
            f"Checkpoint not found at: {CHECKPOINT_PATH}"
        )

    model = build_efficientnet()
    state_dict = torch.load(CHECKPOINT_PATH, map_location=DEVICE)
    model.load_state_dict(state_dict)
    model.to(DEVICE)
    model.eval()
    return model


def preprocess_image(image: Image.Image) -> torch.Tensor:
    image = image.convert("RGB")
    tensor = transform(image).unsqueeze(0)
    return tensor.to(DEVICE)


def predict_image(image: Image.Image) -> Dict:
    model = load_model()
    image_tensor = preprocess_image(image)

    with torch.no_grad():
        outputs = model(image_tensor)
        probs = torch.softmax(outputs, dim=1)[0]

        confidence, predicted_idx = torch.max(probs, dim=0)
        topk_conf, topk_idx = torch.topk(probs, k=min(3, NUM_CLASSES))

    THRESHOLD = 0.4

    top3 = []
    for idx, conf in zip(topk_idx.tolist(), topk_conf.tolist()):
        if conf >= THRESHOLD:
            top3.append({
                "class_name": CLASS_NAMES[idx],
                "confidence": round(float(conf), 4)
            })

    return {
        "predicted_class": CLASS_NAMES[predicted_idx.item()],
        "confidence": round(float(confidence.item()), 4),
        "top3": top3,
    }
