from __future__ import annotations
import os
import json
from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from ..database import get_session

router = APIRouter(prefix="/api/allergens", tags=["allergens"])

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = (BASE_DIR / "assets" / "allergens").resolve()
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY = ASSETS_DIR / "registry.json"

DEFAULTS: Dict[str, str] = {
    "gluten": "Gluten",
    "crustaces": "Crustacés",
    "oeufs": "Œufs",
    "poisson": "Poisson",
    "arachides": "Arachides",
    "soja": "Soja",
    "lait": "Lait",
    "fruits_a_coque": "Fruits à coque",
    "celeri": "Céleri",
    "moutarde": "Moutarde",
    "sesame": "Sésame",
    "sulfites": "Sulfites",
    "lupin": "Lupin",
    "mollusques": "Mollusques",
}

class Allergen(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=64)
    has_icon: bool | None = None
    icon_url: str | None = None

class UpsertAllergen(BaseModel):
    key: str
    label: str


def _read_registry() -> Dict[str, str]:
    if REGISTRY.exists():
        try:
            with REGISTRY.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
    # initialize registry with defaults on first call
    try:
        with REGISTRY.open("w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return dict(DEFAULTS)


def _write_registry(data: Dict[str, str]) -> None:
    tmp = {str(k): str(v) for k, v in data.items()}
    with REGISTRY.open("w", encoding="utf-8") as f:
        json.dump(tmp, f, ensure_ascii=False, indent=2)


def _icon_path(key: str) -> Path:
    return ASSETS_DIR / f"{key}.png"


def _sanitize_key(key: str) -> str:
    s = key.strip().lower()
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789_-"
    s = ''.join(ch for ch in s if ch in allowed)
    if not s:
        raise HTTPException(400, "Clé invalide")
    return s


@router.get("", response_model=List[Allergen])
def list_allergens():
    reg = _read_registry()
    res: List[Allergen] = []
    for k, label in sorted(reg.items(), key=lambda kv: kv[1].lower()):
        p = _icon_path(k)
        res.append(Allergen(key=k, label=label, has_icon=p.exists(), icon_url=f"/backend-assets/allergens/{k}.png"))
    return res


@router.post("", response_model=Allergen)
def upsert_allergen(payload: UpsertAllergen):
    key = _sanitize_key(payload.key)
    label = payload.label.strip()
    if not label:
        raise HTTPException(400, "Label requis")
    reg = _read_registry()
    reg[key] = label
    _write_registry(reg)
    p = _icon_path(key)
    return Allergen(key=key, label=label, has_icon=p.exists(), icon_url=f"/backend-assets/allergens/{key}.png")


@router.delete("/{key}")
def delete_allergen(key: str):
    k = _sanitize_key(key)
    reg = _read_registry()
    if k in reg:
        del reg[k]
        _write_registry(reg)
    return {"ok": True}


@router.post("/{key}/icon", response_model=Allergen)
def upload_icon(key: str, file: UploadFile = File(...)):
    k = _sanitize_key(key)
    if not file.filename.lower().endswith(".png"):
        raise HTTPException(400, "Le logo doit être un fichier PNG")
    content = file.file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(400, "Fichier trop volumineux (max 2MB)")
    p = _icon_path(k)
    with open(p, "wb") as f:
        f.write(content)
    reg = _read_registry()
    label = reg.get(k, k)
    return Allergen(key=k, label=label, has_icon=True, icon_url=f"/backend-assets/allergens/{k}.png")


@router.delete("/{key}/icon")
def delete_icon(key: str):
    k = _sanitize_key(key)
    p = _icon_path(k)
    if p.exists():
        try:
            os.remove(p)
        except Exception:
            pass
    return {"ok": True}
