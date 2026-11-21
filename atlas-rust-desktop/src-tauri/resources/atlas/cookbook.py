"""Hardware-Aware Model Cookbook for Atlas Chat (Phase 1C — Odysseus integration).

Detects host hardware (CPU, RAM, GPU VRAM) using standard library only, scans
installed .gguf files via model_discovery.py, grades curated open-weight GGUF
recipes by hardware fit, and builds copy-ready llama-swap YAML snippets without
modifying existing configs.
"""
from __future__ import annotations

import ctypes
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

import model_discovery

# Curated open-weight GGUF recipes mapped to Atlas roles (coder, mentor, assist, tasks, vision).
RECIPES: tuple[dict[str, Any], ...] = (
    {
        "id": "qwen3-coder-30b-a3b-q4km",
        "name": "Qwen3-Coder 30B-A3B (MoE)",
        "role": "coder",
        "params": "30B (3B active)",
        "quant": "Q4_K_M",
        "disk_gb": 18.6,
        "vram_gb": 20.5,
        "ram_gb": 22.0,
        "context": 32768,
        "vision": False,
        "file_hint": "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf",
        "repo": "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF",
        "notes": "Fast MoE coding model; near-30B quality at ~3B active token speed.",
    },
    {
        "id": "qwen2.5-coder-14b-q4km",
        "name": "Qwen2.5-Coder 14B Instruct",
        "role": "coder",
        "params": "14B",
        "quant": "Q4_K_M",
        "disk_gb": 9.0,
        "vram_gb": 10.5,
        "ram_gb": 12.0,
        "context": 16384,
        "vision": False,
        "file_hint": "qwen2.5-coder-14b-instruct-q4_k_m.gguf",
        "repo": "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
        "notes": "Sweet spot for 12-16 GB GPUs; strong TypeScript, Python, and Rust refactoring.",
    },
    {
        "id": "qwen2.5-coder-7b-q5km",
        "name": "Qwen2.5-Coder 7B Instruct",
        "role": "coder",
        "params": "7B",
        "quant": "Q5_K_M",
        "disk_gb": 5.4,
        "vram_gb": 6.6,
        "ram_gb": 8.0,
        "context": 16384,
        "vision": False,
        "file_hint": "qwen2.5-coder-7b-instruct-q5_k_m.gguf",
        "repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "notes": "Snappy coding model for 8 GB VRAM laptops or fast local autocomplete.",
    },
    {
        "id": "gemma-3-27b-q4km",
        "name": "Gemma 3 27B Instruct",
        "role": "mentor",
        "params": "27B",
        "quant": "Q4_K_M",
        "disk_gb": 16.5,
        "vram_gb": 19.0,
        "ram_gb": 21.0,
        "context": 16384,
        "vision": True,
        "file_hint": "gemma-3-27b-it-Q4_K_M.gguf",
        "repo": "bartowski/google_gemma-3-27b-it-GGUF",
        "notes": "High-depth architecture review, writing, and vision when paired with mmproj.",
    },
    {
        "id": "gemma-3-12b-q4km",
        "name": "Gemma 3 12B Instruct",
        "role": "mentor",
        "params": "12B",
        "quant": "Q4_K_M",
        "disk_gb": 7.4,
        "vram_gb": 9.0,
        "ram_gb": 11.0,
        "context": 16384,
        "vision": True,
        "file_hint": "gemma-3-12b-it-Q4_K_M.gguf",
        "repo": "bartowski/google_gemma-3-12b-it-GGUF",
        "notes": "Balanced mentor & multimodal model for 10-12 GB VRAM cards.",
    },
    {
        "id": "qwen3-14b-q4km",
        "name": "Qwen3 14B",
        "role": "assist",
        "params": "14B",
        "quant": "Q4_K_M",
        "disk_gb": 9.0,
        "vram_gb": 10.8,
        "ram_gb": 12.5,
        "context": 16384,
        "vision": False,
        "file_hint": "Qwen3-14B-Q4_K_M.gguf",
        "repo": "Qwen/Qwen3-14B-GGUF",
        "notes": "Strong everyday assistant with toggleable thinking mode via llama.cpp --jinja.",
    },
    {
        "id": "qwen3-8b-q4km",
        "name": "Qwen3 8B",
        "role": "assist",
        "params": "8B",
        "quant": "Q4_K_M",
        "disk_gb": 5.0,
        "vram_gb": 6.4,
        "ram_gb": 8.0,
        "context": 16384,
        "vision": False,
        "file_hint": "Qwen3-8B-Q4_K_M.gguf",
        "repo": "Qwen/Qwen3-8B-GGUF",
        "notes": "Dependable general assistant that fits comfortably on 8 GB GPUs or 16 GB laptops.",
    },
    {
        "id": "phi-4-mini-q4km",
        "name": "Phi-4 Mini Instruct 3.8B",
        "role": "tasks",
        "params": "3.8B",
        "quant": "Q4_K_M",
        "disk_gb": 2.5,
        "vram_gb": 3.4,
        "ram_gb": 4.5,
        "context": 16384,
        "vision": False,
        "file_hint": "Phi-4-mini-instruct-Q4_K_M.gguf",
        "repo": "bartowski/microsoft_Phi-4-mini-instruct-GGUF",
        "notes": "Ultra-fast local model for task planning, JSON extraction, and compaction.",
    },
    {
        "id": "llama-3.2-3b-q5km",
        "name": "Llama 3.2 3B Instruct",
        "role": "tasks",
        "params": "3B",
        "quant": "Q5_K_M",
        "disk_gb": 2.3,
        "vram_gb": 3.1,
        "ram_gb": 4.0,
        "context": 8192,
        "vision": False,
        "file_hint": "Llama-3.2-3B-Instruct-Q5_K_M.gguf",
        "repo": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "notes": "Runs smoothly even on CPU-only laptops for quick summaries and chat titles.",
    },
    {
        "id": "qwen2.5-vl-7b-q4km",
        "name": "Qwen2.5-VL 7B Instruct",
        "role": "vision",
        "params": "7B",
        "quant": "Q4_K_M",
        "disk_gb": 5.2,
        "vram_gb": 6.8,
        "ram_gb": 8.5,
        "context": 8192,
        "vision": True,
        "file_hint": "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf",
        "repo": "bartowski/Qwen_Qwen2.5-VL-7B-Instruct-GGUF",
        "notes": "Sharp UI screenshot and document OCR understanding when paired with its mmproj .gguf.",
    },
)


def _detect_ram_gb() -> float:
    # Linux /proc/meminfo
    if os.path.isfile("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024 * 1024), 1)
        except (OSError, ValueError):
            pass

    # Windows GlobalMemoryStatusEx via ctypes (no subprocess needed)
    if os.name == "nt":
        try:
            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            st = _MemStatus()
            st.dwLength = ctypes.sizeof(_MemStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return round(st.ullTotalPhys / (1024**3), 1)
        except Exception:
            pass

    # POSIX sysconf fallback
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if pages > 0 and page_size > 0:
                return round((pages * page_size) / (1024**3), 1)
        except (ValueError, OSError):
            pass

    return 16.0


def _detect_gpus() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"capture_output": True, "text": True, "timeout": 4}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            **kwargs,
        ).stdout
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                try:
                    vram_gb = round(float(parts[1]) / 1024.0, 1)
                except ValueError:
                    vram_gb = 0.0
                gpus.append({"name": parts[0], "vram_gb": vram_gb, "vendor": "NVIDIA"})
    except Exception:
        pass
    return gpus


def detect_hardware(vram_override_gb: float | None = None, ram_override_gb: float | None = None) -> dict[str, Any]:
    """Return host hardware profile (or simulated budget when overrides are given)."""
    ram_gb = round(float(ram_override_gb), 1) if ram_override_gb is not None else _detect_ram_gb()
    gpus = _detect_gpus() if vram_override_gb is None else [{"name": "Simulated GPU", "vram_gb": round(float(vram_override_gb), 1), "vendor": "Simulated"}]
    max_vram = max((float(g.get("vram_gb") or 0.0) for g in gpus), default=0.0)
    total_vram = round(sum(float(g.get("vram_gb") or 0.0) for g in gpus), 1)
    return {
        "os": platform.system() or os.name,
        "cpu_cores": os.cpu_count() or 4,
        "ram_gb": max(1.0, ram_gb),
        "gpus": gpus,
        "vram_gb": round(max_vram, 1),
        "total_vram_gb": total_vram,
        "simulated": vram_override_gb is not None or ram_override_gb is not None,
    }


def grade_recipe(recipe: dict[str, Any], hardware: dict[str, Any]) -> dict[str, Any]:
    """Compute hardware fit verdict and recommended llama-server flags for one recipe."""
    vram = float(hardware.get("total_vram_gb") or hardware.get("vram_gb") or 0.0)
    ram = float(hardware.get("ram_gb") or 0.0)
    req_vram = float(recipe["vram_gb"])
    req_ram = float(recipe["ram_gb"])

    # Keep ~1.2 GB VRAM headroom and ~25% OS RAM headroom
    usable_vram = max(0.0, vram - 1.0)
    usable_ram = max(0.0, ram * 0.78)

    if vram > 0 and usable_vram >= req_vram:
        fit = "gpu_fit"
        fit_label = "Fits in GPU VRAM"
        ngl = 99
        rank = 3
    elif vram >= 4.0 and (usable_vram + usable_ram) >= req_ram and usable_vram >= req_vram * 0.45:
        fit = "hybrid_fit"
        fit_label = "Hybrid GPU + RAM"
        ngl = max(8, min(60, int(round(40 * (usable_vram / max(req_vram, 0.1))))))
        rank = 2
    elif usable_ram >= req_ram:
        fit = "cpu_fit"
        fit_label = "CPU-Only (System RAM)"
        ngl = 0
        rank = 1
    else:
        fit = "too_large"
        fit_label = "Exceeds Hardware"
        ngl = 0
        rank = 0

    return {
        **recipe,
        "fit": fit,
        "fit_label": fit_label,
        "fit_rank": rank,
        "recommended_ngl": ngl,
        "recommended_ctx": recipe["context"] if rank >= 2 else min(8192, recipe["context"]),
    }


def scan_installed(runtime_dir: str, data_dir: str) -> list[dict[str, Any]]:
    """Scan local model directories for already-installed .gguf files."""
    try:
        dirs = model_discovery.search_dirs(runtime_dir, data_dir, [])
        found = model_discovery.find_models(dirs)
        return [
            {
                "name": Path(p).name,
                "path": str(p),
                "size_gb": round(size / (1024**3), 2),
                "has_mmproj": model_discovery.find_mmproj(p) is not None,
            }
            for p, size in found
        ]
    except Exception:
        return []


def build_yaml_snippet(selected: list[dict[str, Any]], models_dir: str = "{models}") -> str:
    """Render a copy-ready llama-swap YAML block for the recommended role stack."""
    base = str(models_dir or "{models}").replace("\\", "/").rstrip("/")
    lines = [
        "# Atlas Cookbook snippet — paste into your llama-swap config.yaml",
        "healthCheckTimeout: 300",
        "",
        "models:",
    ]
    for r in selected:
        role = r["role"]
        path = f"{base}/{r['file_hint']}"
        ngl = r.get("recommended_ngl", 99)
        ctx = r.get("recommended_ctx", r["context"])
        lines += [
            f'  "{role}":',
            "    cmd: >",
            "      llama-server --port ${PORT}",
            f"      -m {path}",
            f"      -ngl {ngl} -c {ctx} -fa on -np 1 --jinja",
            "    ttl: 900",
            "",
        ]
    return "\n".join(lines).strip() + "\n"


def cookbook_payload(
    runtime_dir: str,
    data_dir: str,
    *,
    role_filter: str = "",
    vram_override_gb: float | None = None,
    ram_override_gb: float | None = None,
) -> dict[str, Any]:
    """Build the full Hardware-Aware Cookbook payload for GET /api/cookbook & POST /api/cookbook/recommend."""
    hardware = detect_hardware(vram_override_gb=vram_override_gb, ram_override_gb=ram_override_gb)
    installed = scan_installed(runtime_dir, data_dir)
    installed_low = [i["name"].lower() for i in installed]

    graded = []
    for rec in RECIPES:
        item = grade_recipe(rec, hardware)
        hint_tokens = [t for t in rec["id"].replace(".", "-").split("-") if len(t) >= 3][:3]
        item["installed"] = any(all(tok in name for tok in hint_tokens[:2]) for name in installed_low)
        graded.append(item)

    # Best fit recommendation per core Atlas role
    recommended_stack: list[dict[str, Any]] = []
    for role in ("coder", "mentor", "assist", "tasks"):
        candidates = [r for r in graded if r["role"] == role]
        candidates.sort(key=lambda r: (-r["fit_rank"], -r["disk_gb"] if r["fit_rank"] >= 2 else r["disk_gb"]))
        if candidates:
            recommended_stack.append(candidates[0])

    role_clean = str(role_filter or "").strip().lower()
    visible = [r for r in graded if not role_clean or role_clean == "all" or r["role"] == role_clean]
    visible.sort(key=lambda r: (-r["fit_rank"], r["role"], -r["disk_gb"]))

    return {
        "hardware": hardware,
        "installed": installed,
        "recipes": visible,
        "recommended_stack": recommended_stack,
        "yaml_snippet": build_yaml_snippet(recommended_stack),
    }
