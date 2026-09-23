"""View classification: what does an MLB center-field broadcast shot look like?

Allowed: frame sampling, image/layout classifier, scene continuity,
crop/layout statistics, lightweight pretrained visual embedding.
Forbidden: pose/skeleton/landmarks, face recognition, jersey OCR,
pitcher identity classifier.

Strategy (pitcher-agnostic):
  primary = CLIP zero-shot over 7 product labels (framing-based prompts,
  no pitcher names). Multi-frame average per shot + softmax confidence.
  fallback = layout-statistics heuristic when CLIP weights unavailable
  (offline). Both backends output the same 7-class contract.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from PIL import Image

from .schemas import VIEW_LABELS

# Framing-based prompts. Deliberately no pitcher names / teams / identity.
PROMPTS: dict[str, list[str]] = {
    "center_field_good": [
        "a wide center field broadcast view of a baseball game, pitcher on the mound seen from behind, full body small in frame",
        "tv broadcast camera behind the pitcher showing the mound, batter and catcher far away",
    ],
    "side_fullbody_acceptable": [
        "a wide side view of a baseball pitcher on the mound, full body visible",
        "baseball pitcher seen from the side during delivery, full body in frame",
    ],
    "closeup_bad": [
        "a close-up of a baseball player's face and upper body",
        "a tight closeup shot of a person, face filling the frame",
    ],
    "batter_bad": [
        "a close view of a baseball batter at home plate holding a bat",
        "baseball hitter in the batter's box, broadcast close view",
    ],
    "field_bad": [
        "baseball fielders spread on the field, wide defensive view",
        "a baseball stadium field view showing outfielders and infield without a close pitcher",
    ],
    "graphic_bad": [
        "a television graphic overlay screen with text and scoreboard, no live play",
        "a broadcast transition screen with large text graphics",
    ],
    "other_bad": [
        "baseball fans and crowd in the stadium stands",
        "a baseball dugout with players sitting inside",
    ],
}


@dataclass
class ViewResult:
    view_class: str
    confidence: float
    scores: dict[str, float]
    backend: str


class CLIPViewClassifier:
    """Zero-shot CLIP classifier (open_clip, ViT-B-32)."""

    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        import open_clip

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained, device=self.device
        )
        self.model.eval()
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.backend = f"clip:{model_name}/{pretrained}"
        with torch.no_grad():
            text_feats = []
            for label in VIEW_LABELS:
                toks = self.tokenizer(PROMPTS[label]).to(self.device)
                feat = self.model.encode_text(toks)
                feat = feat / feat.norm(dim=-1, keepdim=True)
                text_feats.append(feat.mean(dim=0))
            text_feats = torch.stack(text_feats)
            self.text_feats = text_feats / text_feats.norm(dim=-1, keepdim=True)

    def classify(self, frames: list[Image.Image], temperature: float = 50.0) -> ViewResult:
        import torch.nn.functional as F

        if not frames:
            return ViewResult("other_bad", 0.0, {k: 0.0 for k in VIEW_LABELS}, self.backend)
        with torch.no_grad():
            imgs = torch.stack([self.preprocess(f) for f in frames]).to(self.device)
            feat = self.model.encode_image(imgs)
            feat = feat / feat.norm(dim=-1, keepdim=True)
            avg = feat.mean(dim=0)
            avg = avg / avg.norm()
            logits = (avg @ self.text_feats.T) * temperature
            probs = F.softmax(logits, dim=-1).cpu().numpy()
        scores = {k: float(probs[i]) for i, k in enumerate(VIEW_LABELS)}
        best = max(scores, key=lambda k: scores[k])
        return ViewResult(best, scores[best], scores, self.backend)


class HeuristicViewClassifier:
    """Offline fallback using only layout/color statistics.

    Very coarse: green-field ratio + edge density + center brightness.
    Intended to keep the pipeline runnable without network weights;
    accuracy is lower — diagnostics record backend so results stay honest.
    """

    backend = "heuristic_fallback:v1"

    def classify(self, frames: list[Image.Image]) -> ViewResult:
        import cv2

        if not frames:
            return ViewResult("other_bad", 0.0, {k: 0.0 for k in VIEW_LABELS}, self.backend)
        votes: dict[str, float] = {k: 0.0 for k in VIEW_LABELS}
        for img in frames:
            arr = np.asarray(img.resize((256, 144)))
            hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
            green = ((hsv[..., 0] > 35) & (hsv[..., 0] < 85) & (hsv[..., 1] > 40)).mean()
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 80, 160).mean() / 255.0
            # coarse rules
            if green > 0.45 and edges < 0.10:
                votes["center_field_good"] += 1.0
            elif green > 0.35:
                votes["center_field_good"] += 0.6
                votes["field_bad"] += 0.4
            elif edges > 0.18 and green < 0.15:
                votes["graphic_bad"] += 1.0
            elif green < 0.2 and edges > 0.10:
                votes["closeup_bad"] += 0.6
                votes["other_bad"] += 0.4
            else:
                votes["other_bad"] += 1.0
        total = sum(votes.values()) or 1.0
        scores = {k: v / total for k, v in votes.items()}
        best = max(scores, key=lambda k: scores[k])
        return ViewResult(best, scores[best], scores, self.backend)


def load_classifier(prefer_clip: bool = True):
    if prefer_clip:
        try:
            return CLIPViewClassifier()
        except Exception as e:  # offline / no weights -> honest fallback
            print(f"[view] CLIP load failed ({e}), using heuristic fallback")
    return HeuristicViewClassifier()
