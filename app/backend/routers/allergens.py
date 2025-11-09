from __future__ import annotations
import os
import json
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, Field

from ..database import get_session  # unused, but keeps pattern consistent

router = APIRouter(prefix="/api/allergens", tags=["allergens"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ALLERGENS_DIR = os.path.join(ASSETS_DIR, "allergens")
META_PATH = os.path.join(ALLERGENS_DIR, "meta.json")
PUBLIC_PREFIX = "/backend-assets/allergens"

os.makedirs(ALLERGENS_DIR, exist_ok=True)


class Allergen(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=128)
    icon_url: str | None = None
    has_icon: bool = False


class AllergenUpsert(BaseModel):
    label: str = Field(..., min_length=1, max_length=128)


def _read_meta() -> Dict[str, Dict[str, Any]]:
    try:
        if not os.path.isfile(META_PATH):
            return {}
        with open(META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_meta(meta: Dict[str, Dict[str, Any]]) -> None:
    tmp = META_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.replace(tmp, META_PATH)


def _icon_path_for(key: str) -> str:
    return os.path.join(ALLERGENS_DIR, f"{key}.png")


def _icon_url_for(key: str) -> str:
    return f"{PUBLIC_PREFIX}/{key}.png"


@router.get("", response_model=List[Allergen])
def list_allergens():
    meta = _read_meta()
    out: List[Allergen] = []
    for key, info in sorted(meta.items(), key=lambda kv: (kv[1].get("order", 9999), kv[1].get("label", kv[0]))):
        p = _icon_path_for(key)
        has_icon = os.path.isfile(p)
        out.append(Allergen(key=key, label=info.get("label") or key, has_icon=has_icon, icon_url=_icon_url_for(key) if has_icon else None))
    return out


@router.put("/{key}", response_model=Allergen)
def upsert_allergen(key: str, payload: AllergenUpsert):
    key = key.strip()
    if not key:
        raise HTTPException(400, "Invalid key")
    if any(ch in key for ch in " /\\:\\t\n"):  # prevent path traversal and spaces
        raise HTTPException(400, "Invalid characters in key")
    meta = _read_meta()
    meta.setdefault(key, {})
    meta[key]["label"] = payload.label.strip() or key
    _write_meta(meta)
    has_icon = os.path.isfile(_icon_path_for(key))
    return Allergen(key=key, label=meta[key]["label"], has_icon=has_icon, icon_url=_icon_url_for(key) if has_icon else None)


@router.post("/{key}/icon", response_model=Allergen)
def upload_icon(key: str, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".png"):
        raise HTTPException(400, "Only PNG files are accepted")
    content = file.file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 2MB)")
    # Basic sig check for PNG
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(400, "Invalid PNG file")
    with open(_icon_path_for(key), "wb") as f:
        f.write(content)
    meta = _read_meta()
    label = meta.get(key, {}).get("label", key)
    return Allergen(key=key, label=label, has_icon=True, icon_url=_icon_url_for(key))


@router.delete("/{key}")
def delete_allergen(key: str):
    meta = _read_meta()
    if key in meta:
        del meta[key]
        _write_meta(meta)
    # Do not delete icon by default to avoid accidental data loss; uncomment if needed
    # try:
    #     os.remove(_icon_path_for(key))
    # except Exception:
    #     pass
    return {"ok": True}
