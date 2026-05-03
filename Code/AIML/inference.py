"""LH4-H - InferenceEngine library.

Loads a chosen trained model per task and runs predictions on a feature
dict. Tasks present in `model_choice` are loaded; tasks absent are
skipped (typical for the LoRa-only `mod` task).
"""
from pathlib import Path

import joblib
import numpy as np
import torch
import torch.nn as nn


# Inlined to avoid re-running training scripts on import.
class MLP(nn.Module):
    def __init__(self, n_features, n_classes, hidden=(64, 32), p=0.3):
        super().__init__()
        layers = []; prev = n_features
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(p)]
            prev = h
        layers.append(nn.Linear(prev, n_classes))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


class CNN1D(nn.Module):
    def __init__(self, n_features, n_classes):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(n_features, 16, kernel_size=3, padding=1), nn.ReLU(),
            nn.Conv1d(16,         32, kernel_size=3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(32, 32), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(32, n_classes),
        )

    def forward(self, x):
        return self.net(x.transpose(1, 2))


class InferenceEngine:
    """Per-task chosen model + per-task scaler/encoder.

    Parameters
    ----------
    model_choice : dict
        task -> 'rf' / 'svm' / 'mlp' / 'cnn'
    artifacts_dir : str | Path
        Directory containing per-task subfolders with preprocessor.pkl
        plus the chosen model's saved file.
    """
    def __init__(self, model_choice, artifacts_dir):
        self.artifacts_dir = Path(artifacts_dir)
        self.choice = dict(model_choice)
        self.models = {}
        self.prep   = {}
        for task, choice in self.choice.items():
            d = self.artifacts_dir / task
            self.prep[task]   = joblib.load(d / "preprocessor.pkl")
            self.models[task] = self._load_one(task, choice, d)

    def _load_one(self, task, choice, d):
        if choice in ("rf", "svm"):
            return {"kind": "sk",
                    "model": joblib.load(d / f"{choice}.pkl")["model"]}
        if choice == "mlp":
            ck = torch.load(d / "mlp.pt", map_location="cpu",
                            weights_only=False)
            m = MLP(ck["n_features"], ck["n_classes"])
            m.load_state_dict(ck["state_dict"]); m.eval()
            return {"kind": "mlp", "model": m}
        if choice == "cnn":
            ck = torch.load(d / "cnn.pt", map_location="cpu",
                            weights_only=False)
            m = CNN1D(ck["n_features"], ck["n_classes"])
            m.load_state_dict(ck["state_dict"]); m.eval()
            return {"kind": "cnn", "model": m, "window": 8}
        raise ValueError(f"Unknown model choice: {choice}")

    def predict(self, feature_dict, sequence_buffer=None):
        out = {}
        for task, bundle in self.models.items():
            pre = self.prep[task]
            cols = pre["feature_cols"]
            try:
                row = np.asarray([feature_dict[c] for c in cols],
                                 dtype=np.float32).reshape(1, -1)
            except KeyError as e:
                raise KeyError(
                    f"Task {task} needs column {e} but feature_dict "
                    f"keys are {sorted(feature_dict)}") from None
            x_scaled = pre["scaler"].transform(row)
            if bundle["kind"] == "sk":
                idx = int(bundle["model"].predict(x_scaled)[0])
                prob = None
                try:
                    prob = float(bundle["model"]
                                 .predict_proba(x_scaled).max())
                except (AttributeError, NotImplementedError):
                    pass
                except Exception:
                    pass
            elif bundle["kind"] == "mlp":
                with torch.no_grad():
                    logits = bundle["model"](torch.from_numpy(x_scaled))
                    probs = torch.softmax(logits, dim=1).numpy()[0]
                    idx = int(probs.argmax())
                    prob = float(probs.max())
            elif bundle["kind"] == "cnn":
                if sequence_buffer is None or task not in sequence_buffer:
                    raise ValueError(
                        f"CNN task {task} needs a sequence_buffer entry")
                seq = np.stack(list(sequence_buffer[task]))
                seq_t = torch.from_numpy(seq[None, :, :]).float()
                with torch.no_grad():
                    logits = bundle["model"](seq_t)
                    probs = torch.softmax(logits, dim=1).numpy()[0]
                    idx = int(probs.argmax())
                    prob = float(probs.max())
            else:
                raise RuntimeError(f"Unhandled bundle kind: {bundle['kind']}")
            label = pre["encoder"].inverse_transform([idx])[0]
            out[task] = {"label": label, "prob": prob,
                         "kind": bundle["kind"]}
        return out
