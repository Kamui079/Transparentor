import os
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
import gc
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser, simpledialog
from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageFont, ImageEnhance, ImageFilter
try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None
from tkinterdnd2 import TkinterDnD, DND_FILES
import math
import re
import sys
import traceback
import io
import json
import hashlib
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
import ctypes

APP_NAME = "Transparentor"
APP_VERSION = "1.1.0"
WINDOWS_APP_USER_MODEL_ID = f"Transparentor.Desktop.{APP_VERSION}"
PROJECT_FORMAT_VERSION = 4
FUSION_AI_MODEL = "fusion-best"
DEFAULT_AI_MODEL = FUSION_AI_MODEL
APP_ICON_CANDIDATES = (
    "transparentoricon.ico",
    "Transparentor.ico",
    "transparentor.ico",
)

AI_MODEL_INFO = {
    FUSION_AI_MODEL: {
        "label": "Fusion · Best Overall",
        "components": ("birefnet-massive", "isnet-general-use"),
        "size": 972666916 + 178648008,
    },
    "isnet-general-use": {
        "label": "ISNet · Glow & Fine Effects",
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
        "md5": "fc16ebd8b0c10d971d3513d564d01e29",
        "size": 178648008,
    },
    "birefnet-massive": {
        "label": "BiRefNet · Clean Shapes & Chroma",
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-massive-TR_DIS5K_TR_TEs-epoch_420.onnx",
        "md5": "33e726a2136a3d59eb0fdf613e31e3e9",
        "size": 972666916,
    },
}

PROJECT_IMAGE_KEYS = (
    "ai_mask",
    "composite_mask",
    "refinement_mask",
    "refinement_mask_swirls",
    "local_mask",
)

COMPOSITION_LAYER_DEFAULTS = {
    "rotation": 0.0,
    "opacity": 1.0,
    "brightness": 1.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "blur": 0.0,
    "shadow_enabled": False,
    "shadow_opacity": 0.45,
    "shadow_blur": 18.0,
    "shadow_x": 14.0,
    "shadow_y": 14.0,
    "flip_x": False,
    "flip_y": False,
}

IMAGE_OPEN_FILETYPES = [
    ("Supported images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),
    ("WebP images", "*.webp"),
    ("PNG images", "*.png"),
    ("JPEG images", "*.jpg *.jpeg"),
    ("All files", "*.*"),
]
TRANSPARENT_EXPORT_FORMATS = ("PNG", "WEBP")
DEFAULT_AI_DURATION_ESTIMATES = {
    FUSION_AI_MODEL: 47.0,
    "birefnet-massive": 34.0,
    "isnet-general-use": 9.0,
}

# Modern dark creative-tool palette. The interface intentionally uses one
# dominant accent and reserves semantic colors for status and destructive work.
THEME_BG_MAIN = "#0B0E14"
THEME_BG_SURFACE = "#141922"
THEME_BG_ELEVATED = "#1B2230"
THEME_BG_INPUT = "#0F131B"
THEME_COLOR_BORDER = "#293244"
THEME_COLOR_BORDER_STRONG = "#39455A"
THEME_COLOR_TEXT = "#E8ECF4"
THEME_COLOR_MUTED = "#8C97A9"
THEME_COLOR_ACCENT = "#6C8CFF"
THEME_COLOR_ACCENT_HOVER = "#86A0FF"
THEME_COLOR_SUCCESS = "#45D6A4"
THEME_COLOR_DANGER = "#FF6B7A"
THEME_COLOR_WARNING = "#F5C96A"


def _get_tools_dir():
    return Path(__file__).resolve().parent


def _get_app_icon_path():
    tools_dir = _get_tools_dir()
    for icon_name in APP_ICON_CANDIDATES:
        icon_path = tools_dir / icon_name
        if icon_path.exists():
            return icon_path
    return None


def _set_windows_app_identity(shell32=None):
    """Prevent source launches from inheriting pythonw.exe's taskbar identity."""
    if sys.platform != "win32":
        return False
    try:
        shell32 = shell32 or ctypes.windll.shell32
        result = shell32.SetCurrentProcessExplicitAppUserModelID(
            WINDOWS_APP_USER_MODEL_ID
        )
        return int(result) == 0
    except Exception:
        return False


def _build_brand_mark_image(icon_path, size=36):
    """Render the application icon as a crisp rounded header brand mark."""
    icon_path = Path(icon_path)
    size = max(12, int(size))
    with Image.open(icon_path) as icon_file:
        if (
            getattr(icon_file, "format", None) == "ICO"
            and hasattr(icon_file, "ico")
        ):
            available_sizes = icon_file.ico.sizes()
            source = icon_file.ico.getimage(max(available_sizes)).convert("RGBA")
        else:
            source = icon_file.convert("RGBA")

    inset = 1
    inner_size = size - inset * 2
    source = ImageOps.fit(
        source,
        (inner_size, inner_size),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    rounded_mask = Image.new("L", (inner_size, inner_size), 0)
    ImageDraw.Draw(rounded_mask).rounded_rectangle(
        (0, 0, inner_size - 1, inner_size - 1),
        radius=max(3, round(inner_size * 0.20)),
        fill=255,
    )

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(result).rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=max(4, round(size * 0.22)),
        fill=(145, 167, 255, 210),
    )
    result.paste(source, (inset, inset), rounded_mask)
    return result


def _apply_dark_mode_titlebar(window):
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


def _apply_window_identity(window, title: str):
    try:
        window.title(title)
    except Exception:
        pass

    try:
        window.iconname(APP_NAME)
    except Exception:
        pass

    _apply_dark_mode_titlebar(window)

    icon_path = _get_app_icon_path()
    if icon_path is None:
        return

    try:
        window.iconbitmap(default=str(icon_path))
    except Exception:
        pass

    try:
        with Image.open(icon_path) as icon_image:
            icon_photo = ImageTk.PhotoImage(icon_image.copy())
        window.iconphoto(True, icon_photo)
        setattr(window, "_transparentor_icon_photo", icon_photo)
    except Exception:
        pass


def _center_window(window, width, height):
    try:
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


def _model_cache_path(model_name):
    configured_dir = os.environ.get("U2NET_HOME")
    if configured_dir:
        model_dir = Path(os.path.expanduser(configured_dir))
    else:
        data_home = os.environ.get("XDG_DATA_HOME", "~")
        model_dir = Path(os.path.expanduser(data_home)) / ".u2net"
    return model_dir / f"{model_name}.onnx"


def _ai_component_models(model_name):
    info = AI_MODEL_INFO.get(model_name, {})
    return tuple(info.get("components", (model_name,)))


def _uses_dark_background_recovery(model_name):
    """ISNet-backed modes recover glow on uniform dark artwork."""
    return model_name in ("isnet-general-use", FUSION_AI_MODEL)


def _ai_refinement_policy(model_name):
    """Return whether refinement is user-controlled or fixed by the mode."""
    if model_name.startswith("birefnet"):
        return "pure"
    if model_name == FUSION_AI_MODEL:
        return "adaptive"
    return "user"


def _missing_ai_model_bytes(model_name):
    return sum(
        AI_MODEL_INFO[component]["size"]
        for component in _ai_component_models(model_name)
        if not _model_is_cached(component)
    )


def _model_is_cached(model_name):
    components = _ai_component_models(model_name)
    if components != (model_name,):
        return all(_model_is_cached(component) for component in components)
    info = AI_MODEL_INFO[model_name]
    model_path = _model_cache_path(model_name)
    try:
        return model_path.is_file() and model_path.stat().st_size == info["size"]
    except OSError:
        return False


def _download_ai_model(model_name, status_callback=None, progress_callback=None):
    """Download and verify one model. Intended to run on a worker thread."""
    components = _ai_component_models(model_name)
    if components != (model_name,):
        missing = [
            component
            for component in components
            if not _model_is_cached(component)
        ]
        if not missing:
            if progress_callback:
                progress_callback(100.0)
            return tuple(_model_cache_path(component) for component in components)

        total_bytes = sum(AI_MODEL_INFO[component]["size"] for component in missing)
        completed_bytes = 0
        for index, component in enumerate(missing, start=1):
            component_size = AI_MODEL_INFO[component]["size"]

            def mapped_progress(percent, base=completed_bytes, size=component_size):
                if progress_callback:
                    progress_callback(
                        (base + size * float(percent) / 100.0)
                        * 100.0
                        / max(1, total_bytes)
                    )

            if status_callback:
                status_callback(
                    f"Fusion model {index} of {len(missing)}: "
                    f"{AI_MODEL_INFO[component]['label']}"
                )
            _download_ai_model(
                component,
                status_callback=status_callback,
                progress_callback=mapped_progress,
            )
            completed_bytes += component_size

        if progress_callback:
            progress_callback(100.0)
        return tuple(_model_cache_path(component) for component in components)

    info = AI_MODEL_INFO[model_name]
    model_path = _model_cache_path(model_name)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = model_path.with_suffix(model_path.suffix + ".download")

    def report_status(message):
        if status_callback:
            status_callback(message)

    def report_progress(percent):
        if progress_callback:
            progress_callback(max(0.0, min(100.0, float(percent))))

    try:
        report_status(f"Downloading {info['label']}...")
        request = urllib.request.Request(
            info["url"],
            headers={"User-Agent": f"{APP_NAME}/{APP_VERSION} (Windows)"},
        )
        md5_hash = hashlib.md5()
        downloaded = 0
        with urllib.request.urlopen(request) as response, open(temp_path, "wb") as output:
            total_size = int(response.info().get("Content-Length", 0)) or info["size"]
            while True:
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                md5_hash.update(chunk)
                downloaded += len(chunk)
                report_progress(downloaded * 100.0 / max(1, total_size))

        if downloaded != info["size"]:
            raise RuntimeError(
                f"Downloaded file has the wrong size ({downloaded:,} bytes; expected {info['size']:,})."
            )
        if md5_hash.hexdigest().lower() != info["md5"].lower():
            raise RuntimeError("Downloaded model failed its integrity check.")

        os.replace(temp_path, model_path)
        report_progress(100)
        report_status(f"{info['label']} download complete.")
        return model_path
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _smoothstep(values, low, high):
    import numpy as np

    scaled = np.clip(
        (values - float(low)) / max(float(high) - float(low), 1e-6),
        0.0,
        1.0,
    )
    return scaled * scaled * (3.0 - 2.0 * scaled)


def _classify_uniform_background(rgb):
    """Classify solid or luminance-gradient screens from the image perimeter."""
    import numpy as np

    rgb = np.asarray(rgb, dtype=np.float32)
    height, width = rgb.shape[:2]
    corners = np.stack(
        (
            rgb[0, 0],
            rgb[0, width - 1],
            rgb[height - 1, 0],
            rgb[height - 1, width - 1],
        ),
        axis=0,
    )
    background = np.median(corners, axis=0)
    corner_std = float(np.std(corners, axis=0).max())
    is_uniform = corner_std < 15.0

    # A studio/key background can have a strong brightness gradient, haze, or
    # compression noise while retaining nearly identical chromaticity around
    # the full perimeter. Corner RGB variance alone calls those images
    # "complex". Measure normalized cool-channel dominance across a border band
    # so gradient green/blue/cyan screens still enter the screen-aware path.
    border_width = max(2, round(min(height, width) * 0.025))
    border_pixels = np.concatenate(
        (
            rgb[:border_width].reshape(-1, 3),
            rgb[-border_width:].reshape(-1, 3),
            rgb[border_width:-border_width, :border_width].reshape(-1, 3),
            rgb[border_width:-border_width, -border_width:].reshape(-1, 3),
        ),
        axis=0,
    )
    border_sum = np.maximum(
        np.sum(border_pixels, axis=1, keepdims=True),
        1.0,
    )
    border_norm = border_pixels / border_sum
    border_brightest = np.max(border_pixels, axis=1)
    border_darkest = np.min(border_pixels, axis=1)
    border_saturation = (
        border_brightest - border_darkest
    ) / np.maximum(border_brightest, 1.0)
    border_cool_dominance = (
        np.maximum(border_norm[:, 1], border_norm[:, 2])
        - border_norm[:, 0]
    )
    border_screen_pixels = (
        (border_brightest >= 60.0)
        & (border_saturation >= 0.55)
        & (border_cool_dominance >= 0.30)
    )
    border_screen_fraction = float(np.mean(border_screen_pixels))
    border_chromaticity_std = float(
        np.std(border_norm, axis=0).max()
    )
    is_gradient_chroma = bool(
        not is_uniform
        and border_screen_fraction >= 0.92
        and border_chromaticity_std <= 0.08
    )

    brightest = float(np.max(background))
    darkest = float(np.min(background))
    saturation = (
        (brightest - darkest) / max(brightest, 1.0)
        if brightest > 0.0
        else 0.0
    )
    luma = float(
        0.2126 * background[0]
        + 0.7152 * background[1]
        + 0.0722 * background[2]
    )

    # Chroma recovery was developed for luminous green/blue/cyan screens. A
    # minimum brightness is essential: near-black navy artwork can be highly
    # saturated numerically but is not a chroma screen.
    cool_screen = (
        max(float(background[1]), float(background[2]))
        >= float(background[0]) + 24.0
    )
    is_chroma_screen = bool(
        (is_uniform or is_gradient_chroma)
        and brightest >= 80.0
        and saturation >= 0.35
        and cool_screen
    )
    is_dark_uniform = bool(
        is_uniform
        and luma <= 45.0
        and brightest <= 72.0
    )
    if is_chroma_screen:
        kind = "chroma"
    elif is_dark_uniform:
        kind = "dark"
    elif is_uniform:
        kind = "uniform"
    else:
        kind = "complex"

    return {
        "kind": kind,
        "background": background,
        "corner_std": corner_std,
        "border_screen_fraction": border_screen_fraction,
        "border_chromaticity_std": border_chromaticity_std,
        "is_gradient_chroma": is_gradient_chroma,
        "is_uniform": is_uniform,
        "is_chroma_screen": is_chroma_screen,
        "is_dark_uniform": is_dark_uniform,
        "luma": luma,
        "saturation": saturation,
    }


def _refine_gradient_chroma_alpha(rgb, alpha, key_idx):
    """Suppress a luminance-gradient key screen without hardening translucency."""
    import numpy as np

    rgb = np.asarray(rgb, dtype=np.float32)
    alpha = np.clip(np.asarray(alpha, dtype=np.float32), 0.0, 1.0)
    height, width = alpha.shape
    other_indices = [channel for channel in range(3) if channel != key_idx]

    key_value = rgb[:, :, key_idx]
    strongest_other = np.maximum(
        rgb[:, :, other_indices[0]],
        rgb[:, :, other_indices[1]],
    )
    # This ratio is insensitive to illumination. Dark and bright samples of the
    # same screen receive approximately the same score, while cyan glass, white
    # highlights, and purple particles retain the model's original alpha.
    key_dominance = (
        key_value - strongest_other
    ) / np.maximum(key_value, np.float32(1.0))

    border_width = max(2, round(min(height, width) * 0.025))
    border_dominance = np.concatenate(
        (
            key_dominance[:border_width].reshape(-1),
            key_dominance[-border_width:].reshape(-1),
            key_dominance[
                border_width:-border_width,
                :border_width,
            ].reshape(-1),
            key_dominance[
                border_width:-border_width,
                -border_width:,
            ].reshape(-1),
        )
    )
    screen_samples = border_dominance[border_dominance > 0.10]
    screen_dominance = (
        float(np.median(screen_samples))
        if screen_samples.size
        else 0.75
    )

    # Background samples vary because of JPEG noise, haze, and bokeh. Treat
    # pixels retaining at least 65% of the perimeter's key dominance as screen,
    # then ease continuously toward foreground. Squaring the key matte removes
    # green veiling while retaining genuinely translucent cyan structures.
    cleanup_reference = max(screen_dominance * 0.65, 0.20)
    key_alpha = np.clip(
        1.0 - key_dominance / cleanup_reference,
        0.0,
        1.0,
    )
    key_alpha *= key_alpha
    refined_alpha = np.minimum(alpha, key_alpha)
    refined_alpha = np.where(
        refined_alpha < (1.0 / 255.0),
        0.0,
        refined_alpha,
    )
    return (
        refined_alpha.astype(np.float32),
        key_alpha.astype(np.float32),
    )


def _reconstruct_gradient_chroma_foreground(
    rgb,
    alpha,
    key_idx,
    strength=0.55,
):
    """Estimate clean foreground RGB after a translucent gradient-screen key."""
    import numpy as np

    rgb = np.asarray(rgb, dtype=np.float32)
    alpha = np.clip(np.asarray(alpha, dtype=np.float32), 0.0, 1.0)
    height, width = alpha.shape
    other_indices = [channel for channel in range(3) if channel != key_idx]
    key_value = rgb[:, :, key_idx]
    strongest_other = np.maximum(
        rgb[:, :, other_indices[0]],
        rgb[:, :, other_indices[1]],
    )

    border_width = max(2, round(min(height, width) * 0.025))
    border_rgb = np.concatenate(
        (
            rgb[:border_width].reshape(-1, 3),
            rgb[-border_width:].reshape(-1, 3),
            rgb[
                border_width:-border_width,
                :border_width,
            ].reshape(-1, 3),
            rgb[
                border_width:-border_width,
                -border_width:,
            ].reshape(-1, 3),
        )
    )
    border_key = border_rgb[:, key_idx]
    border_other = np.maximum(
        border_rgb[:, other_indices[0]],
        border_rgb[:, other_indices[1]],
    )
    screen_samples = (
        (border_key > 20.0)
        & ((border_key - border_other) / np.maximum(border_key, 1.0) > 0.30)
    )
    if not np.any(screen_samples):
        return rgb.copy()

    # The perimeter provides screen channel ratios while the local key-channel
    # brightness supplies the illumination gradient. Solve C=aF+(1-a)B with a
    # neutral/cool foreground key estimate, then blend conservatively to avoid
    # amplification at very low alpha.
    screen_ratios = np.median(
        border_rgb[screen_samples]
        / np.maximum(border_key[screen_samples, None], 1.0),
        axis=0,
    ).astype(np.float32)
    inverse_alpha = 1.0 - alpha
    foreground_key = np.where(
        inverse_alpha > 0.02,
        strongest_other,
        key_value,
    )
    background_key = (
        key_value - alpha * foreground_key
    ) / np.maximum(inverse_alpha, 0.02)
    background_key = np.clip(background_key, 0.0, 255.0)
    estimated_background = (
        background_key[:, :, None]
        * screen_ratios[None, None, :]
    )
    estimated_foreground = (
        rgb
        - inverse_alpha[:, :, None] * estimated_background
    ) / np.maximum(alpha[:, :, None], 0.04)
    estimated_foreground = np.clip(
        estimated_foreground,
        0.0,
        255.0,
    )

    stable_alpha = _smoothstep(alpha, 0.02, 0.20)
    blend = stable_alpha[:, :, None] * float(strength)
    return (
        rgb * (1.0 - blend)
        + estimated_foreground * blend
    ).astype(np.float32)


def _fuse_ai_mask_arrays(rgb, birefnet_alpha, isnet_alpha, profile=None):
    """Keep BiRefNet structure while admitting credible ISNet-only fine detail."""
    import cv2
    import numpy as np

    rgb = np.asarray(rgb, dtype=np.float32)
    heavy = np.clip(np.asarray(birefnet_alpha, dtype=np.float32), 0.0, 1.0)
    light = np.clip(np.asarray(isnet_alpha, dtype=np.float32), 0.0, 1.0)
    if heavy.shape != light.shape or heavy.shape != rgb.shape[:2]:
        raise ValueError("Fusion masks and source image must have matching dimensions.")

    profile = profile or _classify_uniform_background(rgb)
    background = np.asarray(profile["background"], dtype=np.float32)
    color_distance = np.sqrt(
        np.sum((rgb - background[None, None, :]) ** 2, axis=2)
    )

    if profile["kind"] == "dark":
        color_evidence = _smoothstep(color_distance, 5.0, 48.0)
        minimum_light_alpha = 0.025
    elif profile["kind"] == "chroma":
        color_evidence = _smoothstep(color_distance, 28.0, 105.0)
        minimum_light_alpha = 0.045
    else:
        color_evidence = _smoothstep(color_distance, 18.0, 82.0)
        minimum_light_alpha = 0.08

    light_advantage = np.clip(light - heavy, 0.0, 1.0)
    candidate = (
        (light_advantage > 0.012)
        & (light > minimum_light_alpha)
        & (color_evidence > 0.04)
    )

    # Remove isolated model noise, while allowing a single genuinely bright,
    # confident sparkle to survive.
    labels_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        candidate.astype(np.uint8),
        connectivity=8,
    )
    credible_components = np.zeros_like(candidate, dtype=bool)
    for label in range(1, labels_count):
        component = labels == label
        area = int(stats[label, cv2.CC_STAT_AREA])
        peak_alpha = float(np.max(light[component]))
        peak_color = float(np.max(color_evidence[component]))
        if area >= 2 or (peak_alpha >= 0.28 and peak_color >= 0.72):
            credible_components[component] = True

    heavy_support = (heavy > 0.12).astype(np.uint8)
    distance_from_heavy = cv2.distanceTransform(
        1 - heavy_support,
        cv2.DIST_L2,
        5,
    )
    light_confidence = _smoothstep(light, minimum_light_alpha, 0.60)

    if profile["kind"] == "dark":
        # ISNet owns the boundary on dark luminous artwork: its partial alpha
        # preserves glow and detached particles that BiRefNet tends to harden
        # or suppress. BiRefNet may strengthen only pixels safely inside an
        # already-supported ISNet shape, never its outer glow.
        light_support = (light > 0.10).astype(np.uint8)
        light_interior_distance = cv2.distanceTransform(
            light_support,
            cv2.DIST_L2,
            5,
        )
        interior_weight = (
            _smoothstep(light_interior_distance, 2.0, 7.0)
            * _smoothstep(light, 0.20, 0.82)
        )
        heavy_advantage = np.clip(heavy - light, 0.0, 1.0)
        return np.clip(light + heavy_advantage * interior_weight, 0.0, 1.0)
    elif profile["kind"] == "chroma":
        # Near a BiRefNet silhouette, prefer its cleaner screen separation.
        # Detached, strongly non-screen particles may still come from ISNet.
        detached_weight = _smoothstep(distance_from_heavy, 2.0, 9.0)
        reliability = (
            color_evidence
            * (0.18 + 0.82 * detached_weight)
            * (0.30 + 0.70 * light_confidence)
        )
    else:
        detached_weight = _smoothstep(distance_from_heavy, 1.5, 7.0)
        reliability = (
            color_evidence
            * (0.25 + 0.75 * detached_weight)
            * light_confidence
        )

    reliability = np.where(credible_components, reliability, 0.0)
    fused = heavy + light_advantage * np.clip(reliability, 0.0, 1.0)
    return np.clip(fused, 0.0, 1.0)


def _fuse_ai_masks(image, birefnet_mask, isnet_mask):
    import numpy as np

    source_rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    if birefnet_mask.size != image.size:
        birefnet_mask = birefnet_mask.resize(
            image.size,
            Image.Resampling.BILINEAR,
        )
    if isnet_mask.size != image.size:
        isnet_mask = isnet_mask.resize(
            image.size,
            Image.Resampling.BILINEAR,
        )
    heavy = np.asarray(birefnet_mask.convert("L"), dtype=np.float32) / 255.0
    light = np.asarray(isnet_mask.convert("L"), dtype=np.float32) / 255.0
    fused = _fuse_ai_mask_arrays(source_rgb, heavy, light)
    return Image.fromarray(
        np.clip(np.round(fused * 255.0), 0, 255).astype(np.uint8),
        "L",
    )


def _image_to_png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _read_archived_image(archive, asset_path):
    with archive.open(asset_path) as image_file:
        return Image.open(io.BytesIO(image_file.read())).copy()


def _export_extension(format_name):
    normalized = str(format_name or "PNG").strip().upper()
    return ".webp" if normalized == "WEBP" else ".png"


def _save_transparent_image(image, path, format_name=None):
    """Save an RGBA-capable still image while preserving transparency."""
    selected = str(format_name or "").strip().upper()
    if not selected:
        extension = Path(path).suffix.lower()
        selected = "WEBP" if extension == ".webp" else "PNG"

    rgba = image.convert("RGBA")
    if selected == "WEBP":
        rgba.save(
            path,
            format="WEBP",
            lossless=True,
            quality=100,
            method=6,
            exact=True,
        )
    else:
        rgba.save(path, format="PNG")


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported project value: {type(value).__name__}")


def _serialize_project_action(action, action_index, archive):
    serialized = {}
    for key, value in action.items():
        if key in PROJECT_IMAGE_KEYS and isinstance(value, Image.Image):
            asset_path = f"assets/actions/{action_index:04d}_{key}.png"
            archive.writestr(asset_path, _image_to_png_bytes(value))
            serialized[key] = {"$image": asset_path}
        else:
            serialized[key] = _json_safe(value)
    return serialized


def _deserialize_project_action(action, archive=None):
    restored = dict(action)
    for key in PROJECT_IMAGE_KEYS:
        value = restored.get(key)
        if isinstance(value, dict) and "$image" in value:
            if archive is None:
                raise ValueError(f"Project image asset for '{key}' is unavailable.")
            with archive.open(value["$image"]) as image_file:
                restored[key] = Image.open(io.BytesIO(image_file.read())).copy()

    for key in ("color", "old", "new", "target", "box"):
        if key in restored and restored[key] is not None:
            restored[key] = tuple(restored[key])
    for key in ("points", "edge_coords"):
        if key in restored and restored[key] is not None:
            restored[key] = [tuple(point) for point in restored[key]]
    return restored


def _get_crash_log_dir():
    base_dir = os.environ.get("LOCALAPPDATA")
    if base_dir:
        log_dir = Path(base_dir) / APP_NAME / "logs"
    else:
        log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _get_ai_timing_path():
    base_dir = os.environ.get("LOCALAPPDATA")
    if base_dir:
        data_dir = Path(base_dir) / APP_NAME
    else:
        data_dir = Path(__file__).resolve().parent
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "ai_timing.json"


def _load_ai_duration_estimates():
    estimates = dict(DEFAULT_AI_DURATION_ESTIMATES)
    try:
        payload = json.loads(_get_ai_timing_path().read_text(encoding="utf-8"))
        for model_name in estimates:
            value = float(payload.get(model_name, estimates[model_name]))
            if math.isfinite(value) and value > 0:
                estimates[model_name] = max(1.0, min(1800.0, value))
    except Exception:
        pass
    return estimates


def _save_ai_duration_estimates(estimates):
    try:
        path = _get_ai_timing_path()
        temp_path = path.with_suffix(".tmp")
        payload = {
            model_name: round(float(value), 3)
            for model_name, value in estimates.items()
            if math.isfinite(float(value)) and float(value) > 0
        }
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp_path, path)
    except Exception:
        pass


def _write_crash_log(exc_type, exc_value, exc_tb, context: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = _get_crash_log_dir() / f"crash_{timestamp}.log"
    lines = [
        f"Application: {APP_NAME}",
        f"Context: {context}",
        f"Timestamp: {datetime.now().isoformat()}",
        f"Python: {sys.version}",
        f"Executable: {sys.executable}",
        f"Working Directory: {os.getcwd()}",
        "",
        "Traceback:",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    ]
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path


def _show_fatal_error_dialog(title: str, message: str):
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
        return
    except Exception:
        pass

    dialog_root = None
    try:
        dialog_root = tk.Tk()
        _apply_window_identity(dialog_root, APP_NAME)
        dialog_root.withdraw()
        messagebox.showerror(title, message, parent=dialog_root)
    except Exception:
        pass
    finally:
        if dialog_root is not None:
            try:
                dialog_root.destroy()
            except Exception:
                pass


def _handle_fatal_exception(exc_type, exc_value, exc_tb, context: str):
    try:
        log_path = _write_crash_log(exc_type, exc_value, exc_tb, context)
        message = (
            f"{APP_NAME} hit an unrecoverable error.\n\n"
            f"Context: {context}\n\n"
            f"A crash log was written to:\n{log_path}"
        )
    except Exception:
        message = f"{APP_NAME} hit an unrecoverable error and could not write a crash log."
    _show_fatal_error_dialog(APP_NAME, message)


def _draw_preview_panel_badge(draw, x: int, y: int, text: str):
    font = ImageFont.load_default()
    text_box = draw.textbbox((0, 0), text, font=font)
    text_w = text_box[2] - text_box[0]
    text_h = text_box[3] - text_box[1]
    pad_x = 8
    pad_y = 5
    box = (
        x,
        y,
        x + text_w + pad_x * 2,
        y + text_h + pad_y * 2,
    )
    draw.rectangle(box, fill=(20, 20, 20, 210), outline=(218, 218, 218, 180), width=1)
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=(245, 245, 245, 255))


def _render_glass_card(width, height, bg_color=THEME_BG_SURFACE, border_color=THEME_COLOR_BORDER, accent_color=THEME_COLOR_ACCENT, corner_radius=10):
    scale = 2
    w = max(1, width * scale)
    h = max(1, height * scale)
    r = corner_radius * scale
    
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    def parse_hex(hex_str):
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        
    bg_rgb = parse_hex(bg_color)
    border_rgb = parse_hex(border_color)
    # A restrained elevated card: soft shadow, opaque surface, one crisp border,
    # and a faint top highlight. This reads much cleaner than the old gloss.
    inset = 2 * scale
    draw.rounded_rectangle(
        [inset, inset + scale, w - inset, h - inset],
        radius=max(1, r - scale),
        fill=(0, 0, 0, 72),
    )
    draw.rounded_rectangle(
        [inset, inset, w - inset, h - inset - scale],
        radius=max(1, r - scale),
        fill=bg_rgb + (255,),
        outline=border_rgb + (255,),
        width=scale,
    )
    draw.line(
        [(inset + r, inset + scale), (w - inset - r, inset + scale)],
        fill=(255, 255, 255, 16),
        width=scale,
    )

    return img.resize((width, height), Image.Resampling.LANCZOS)


def _draw_button_icon(draw, icon_name, w, h, scale, color):
    if isinstance(color, str):
        color = color.lstrip('#')
        color = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    color_rgba = color + (255,)
    soft_rgba = color + (110,)
    cx = w // 2
    cy = h // 2
    u = scale
    stroke = max(3, int(round(1.7 * scale)))
    fine = max(2, int(round(1.15 * scale)))

    def line(points, width=stroke, fill=color_rgba, joint="curve"):
        draw.line(points, fill=fill, width=width, joint=joint)

    def rr(box, radius=4 * u, width=stroke, fill=None, outline=color_rgba):
        draw.rounded_rectangle(
            box,
            radius=radius,
            fill=fill,
            outline=outline,
            width=width,
        )

    if icon_name == "image":
        rr((cx - 11*u, cy - 9*u, cx + 11*u, cy + 9*u), radius=3*u)
        draw.ellipse(
            (cx + 3*u, cy - 5*u, cx + 7*u, cy - u),
            outline=color_rgba,
            width=fine,
        )
        line([
            (cx - 8*u, cy + 5*u),
            (cx - 2*u, cy - u),
            (cx + 2*u, cy + 3*u),
            (cx + 5*u, cy),
            (cx + 9*u, cy + 5*u),
        ], width=fine)

    elif icon_name == "clipboard":
        rr((cx - 9*u, cy - 8*u, cx + 9*u, cy + 11*u), radius=3*u)
        rr(
            (cx - 5*u, cy - 11*u, cx + 5*u, cy - 5*u),
            radius=2*u,
            width=fine,
            fill=THEME_BG_ELEVATED,
        )
        for offset, length in ((-2, 11), (3, 11), (8, 7)):
            line(
                [(cx - 5*u, cy + offset*u), (cx + (length - 5)*u, cy + offset*u)],
                width=fine,
            )

    elif icon_name == "save":
        line([(cx, cy - 11*u), (cx, cy + 4*u)])
        line([(cx - 6*u, cy - 2*u), (cx, cy + 4*u), (cx + 6*u, cy - 2*u)])
        line([
            (cx - 10*u, cy + 4*u),
            (cx - 10*u, cy + 10*u),
            (cx + 10*u, cy + 10*u),
            (cx + 10*u, cy + 4*u),
        ])
        line([(cx - 6*u, cy + 7*u), (cx + 6*u, cy + 7*u)], width=fine, fill=soft_rgba)

    elif icon_name == "folder":
        rr((cx - 11*u, cy - 7*u, cx + 11*u, cy + 9*u), radius=3*u)
        line([
            (cx - 10*u, cy - 7*u),
            (cx - 10*u, cy - 10*u),
            (cx - 2*u, cy - 10*u),
            (cx + 2*u, cy - 7*u),
        ], width=fine)
        line([(cx - 8*u, cy - 2*u), (cx + 8*u, cy - 2*u)], width=fine, fill=soft_rgba)

    elif icon_name == "project":
        rr((cx - 10*u, cy - 11*u, cx + 10*u, cy + 11*u), radius=3*u)
        for offset in (-5, 1, 7):
            draw.ellipse(
                (cx - 6*u, cy + (offset-1)*u, cx - 4*u, cy + (offset+1)*u),
                fill=color_rgba,
            )
            line(
                [(cx - 1*u, cy + offset*u), (cx + 6*u, cy + offset*u)],
                width=fine,
            )

    elif icon_name == "undo":
        draw.arc(
            (cx - 8*u, cy - 8*u, cx + 11*u, cy + 10*u),
            205,
            515,
            fill=color_rgba,
            width=stroke,
        )
        draw.polygon(
            [(cx - 11*u, cy - 2*u), (cx - 3*u, cy - 8*u), (cx - 3*u, cy + 3*u)],
            fill=color_rgba,
        )

    elif icon_name == "redo":
        draw.arc(
            (cx - 11*u, cy - 8*u, cx + 8*u, cy + 10*u),
            25,
            335,
            fill=color_rgba,
            width=stroke,
        )
        draw.polygon(
            [(cx + 11*u, cy - 2*u), (cx + 3*u, cy - 8*u), (cx + 3*u, cy + 3*u)],
            fill=color_rgba,
        )

    elif icon_name == "crop":
        line([(cx - 9*u, cy - 12*u), (cx - 9*u, cy + 7*u), (cx + 10*u, cy + 7*u)])
        line([(cx - 12*u, cy - 7*u), (cx + 7*u, cy - 7*u), (cx + 7*u, cy + 12*u)])
        draw.ellipse(
            (cx + 5*u, cy + 5*u, cx + 9*u, cy + 9*u),
            fill=color_rgba,
        )

    elif icon_name == "lasso":
        points = [
            (cx - 9*u, cy + 3*u),
            (cx - 11*u, cy - 4*u),
            (cx - 5*u, cy - 10*u),
            (cx + 5*u, cy - 9*u),
            (cx + 11*u, cy - 3*u),
            (cx + 8*u, cy + 5*u),
            (cx, cy + 8*u),
            (cx - 7*u, cy + 6*u),
            (cx - 9*u, cy + 3*u),
        ]
        line(points, width=stroke)
        line([(cx + 7*u, cy + 5*u), (cx + 11*u, cy + 11*u)], width=fine)
        draw.ellipse(
            (cx + 8*u, cy + 8*u, cx + 12*u, cy + 12*u),
            outline=color_rgba,
            width=fine,
        )

    elif icon_name == "clear":
        draw.polygon(
            [
                (cx - 10*u, cy + 4*u),
                (cx + 2*u, cy - 9*u),
                (cx + 10*u, cy - u),
                (cx - 2*u, cy + 11*u),
            ],
            outline=color_rgba,
            fill=None,
        )
        line([(cx - 5*u, cy - u), (cx + 3*u, cy + 7*u)], width=fine)
        line([(cx - 2*u, cy + 11*u), (cx + 10*u, cy + 11*u)], width=fine)

    elif icon_name == "discard":
        line([(cx - 10*u, cy - 7*u), (cx + 10*u, cy - 7*u)])
        line([(cx - 4*u, cy - 10*u), (cx + 4*u, cy - 10*u)], width=fine)
        rr((cx - 8*u, cy - 4*u, cx + 8*u, cy + 11*u), radius=3*u)
        line([(cx - 3*u, cy), (cx - 3*u, cy + 7*u)], width=fine)
        line([(cx + 3*u, cy), (cx + 3*u, cy + 7*u)], width=fine)

    elif icon_name == "help":
        draw.ellipse(
            (cx - 11*u, cy - 11*u, cx + 11*u, cy + 11*u),
            outline=color_rgba,
            width=stroke,
        )
        try:
            help_font = ImageFont.truetype("segoeuib.ttf", 16*u)
        except Exception:
            help_font = ImageFont.load_default()
        draw.text(
            (cx, cy - u),
            "?",
            fill=color_rgba,
            font=help_font,
            anchor="mm",
        )


def _render_glossy_button(width, height, state="normal", base_color=THEME_BG_ELEVATED, accent_color=THEME_COLOR_ACCENT, corner_radius=8, icon_name=None):
    scale = 2
    w = max(1, width * scale)
    h = max(1, height * scale)
    r = corner_radius * scale
    
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    def parse_hex(hex_str):
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        
    base_rgb = parse_hex(base_color)
    accent_rgb = parse_hex(accent_color)
    
    if state == "normal":
        fill_rgb = base_rgb
        border_rgb = parse_hex(THEME_COLOR_BORDER)
        icon_color = THEME_COLOR_TEXT
    elif state == "hover":
        fill_rgb = tuple(min(255, c + 12) for c in base_rgb)
        border_rgb = accent_rgb
        icon_color = THEME_COLOR_ACCENT_HOVER
    else:
        fill_rgb = tuple(max(0, c - 8) for c in base_rgb)
        border_rgb = accent_rgb
        icon_color = THEME_COLOR_ACCENT

    inset = scale
    draw.rounded_rectangle(
        [inset, inset, w - inset, h - inset],
        radius=r,
        fill=fill_rgb + (255,),
        outline=border_rgb + (255,),
        width=scale,
    )

    if icon_name:
        _draw_button_icon(draw, icon_name, w, h, scale, icon_color)

    return img.resize((width, height), Image.Resampling.LANCZOS)


class GlassPanel(tk.Canvas):
    def __init__(self, master=None, text="", style=None, border_color=None, accent_color=None, bullet_color=None, **kwargs):
        parent_bg = THEME_BG_MAIN
        if master is not None and hasattr(master, "cget"):
            try:
                parent_bg = master.cget("bg")
            except Exception:
                pass
        kwargs.setdefault("bg", parent_bg)
        super().__init__(master, highlightthickness=0, bd=0, **kwargs)
        self.text = text
        self.border_color = border_color or THEME_COLOR_BORDER
        self.accent_color = accent_color or THEME_COLOR_ACCENT
        
        if text and not bullet_color:
            clean_text = text.strip().lower()
            if "remove" in clean_text:
                self.bullet_color = THEME_COLOR_ACCENT
            elif "gif" in clean_text or "filmstrip" in clean_text:
                self.bullet_color = THEME_COLOR_ACCENT
            elif "replace" in clean_text:
                self.bullet_color = THEME_COLOR_ACCENT
            elif "protect" in clean_text or "lasso" in clean_text:
                self.bullet_color = THEME_COLOR_WARNING
            elif "cleanup" in clean_text or "blend" in clean_text:
                self.bullet_color = THEME_COLOR_SUCCESS
            elif "rule" in clean_text:
                self.bullet_color = THEME_COLOR_ACCENT
            elif "slicer" in clean_text:
                self.bullet_color = THEME_COLOR_ACCENT
            elif "preset" in clean_text:
                self.bullet_color = THEME_COLOR_ACCENT
            elif "name" in clean_text:
                self.bullet_color = THEME_COLOR_ACCENT
            else:
                self.bullet_color = THEME_COLOR_ACCENT
        else:
            self.bullet_color = bullet_color or THEME_COLOR_ACCENT
            
        self.bg_image = None
        self.bg_photo = None
        self.bg_image_id = None
        
        self.bind("<Configure>", self.on_configure)
        
        if self.text:
            self.header_frame = tk.Frame(self, bg=THEME_BG_SURFACE)
            self.header_frame.pack(fill=tk.X, padx=14, pady=(13, 6), anchor="nw")
            
            self.bullet_canvas = tk.Canvas(self.header_frame, width=4, height=18, bg=THEME_BG_SURFACE, highlightthickness=0)
            self.bullet_canvas.pack(side=tk.LEFT, padx=(0, 9))
            
            bc = self.bullet_color
            self.bullet_canvas.create_rectangle(0, 1, 3, 17, fill=bc, outline=bc)
            
            self.title_label = tk.Label(
                self.header_frame,
                text=self.text.strip(),
                fg=THEME_COLOR_TEXT,
                bg=THEME_BG_SURFACE,
                font=('Segoe UI Semibold', 10),
            )
            self.title_label.pack(side=tk.LEFT)
 
    def on_configure(self, event):
        w = event.width
        h = event.height
        if w < 5 or h < 5:
            return
        
        img = _render_glass_card(w, h, bg_color=THEME_BG_SURFACE, border_color=self.border_color, accent_color=self.accent_color)
        self.bg_photo = ImageTk.PhotoImage(img)
        
        if self.bg_image_id is None:
            self.bg_image_id = self.create_image(0, 0, image=self.bg_photo, anchor="nw")
        else:
            self.itemconfig(self.bg_image_id, image=self.bg_photo)
            
        self.tag_lower(self.bg_image_id)


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.show_tip, add="+")
        self.widget.bind("<Leave>", self.hide_tip, add="+")
        self.widget.bind("<Button-1>", self.hide_tip, add="+")

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        self.id = self.widget.after(500, self.display_tip)

    def display_tip(self):
        try:
            if not self.widget.winfo_exists():
                return
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.withdraw()  # Hide immediately to prevent flashing in the top-left
            tw.wm_overrideredirect(True)
            
            bg = THEME_BG_SURFACE
            fg = THEME_COLOR_TEXT
            border = THEME_COLOR_BORDER
            
            frame = tk.Frame(tw, bg=border, padx=1, pady=1)
            frame.pack(fill=tk.BOTH, expand=True)
            
            inner = tk.Frame(frame, bg=bg, padx=6, pady=4)
            inner.pack(fill=tk.BOTH, expand=True)
            
            label = tk.Label(inner, text=self.text, fg=fg, bg=bg, font=('Segoe UI', 9), justify=tk.LEFT)
            label.pack()
            
            # Force layout updates on both the parent widget and the tooltip to get correct dimensions
            self.widget.update_idletasks()
            tw.update_idletasks()
            
            widget_x = self.widget.winfo_rootx()
            widget_y = self.widget.winfo_rooty()
            widget_w = self.widget.winfo_width()
            widget_h = self.widget.winfo_height()
            
            req_w = tw.winfo_reqwidth()
            req_h = tw.winfo_reqheight()
            
            if widget_x < 150:
                x = widget_x + widget_w + 8
                y = widget_y + (widget_h - req_h) // 2
            else:
                x = widget_x + (widget_w - req_w) // 2
                y = widget_y + widget_h + 6
                
            tw.wm_geometry(f"+{x}+{y}")
            tw.deiconify()  # Reveal the window now that it is positioned correctly
            tw.attributes("-topmost", True)
        except Exception:
            pass

    def hide_tip(self, event=None):
        try:
            if self.id:
                self.widget.after_cancel(self.id)
                self.id = None
        except Exception:
            pass
        try:
            if self.tip_window:
                self.tip_window.destroy()
                self.tip_window = None
        except Exception:
            pass


class CustomButton(tk.Button):
    def __init__(self, master=None, **kwargs):
        style = kwargs.pop("style", "Action.TButton")
        text = kwargs.get("text", "")
        explicit_icon = kwargs.pop("icon", kwargs.pop("icon_name", None))
        
        emoji_to_icon = {
            "🖼️": "image", "📋": "clipboard", "💾": "save", "🗑️": "discard", "📂": "folder",
            "🗄️": "project", "↩️": "undo", "↪️": "redo", "✂️": "crop",
            "⚬": "lasso", "❌": "clear", "❓": "help"
        }
        icon_name = explicit_icon or emoji_to_icon.get(text)
        self.icon_name = icon_name
        
        tooltip_text = kwargs.pop("tooltip", None)
        if not tooltip_text and icon_name:
            friendly_names = {
                "image": "Open Image",
                "clipboard": "Paste from Clipboard",
                "save": "Save / Export Image",
                "folder": "Load Project",
                "project": "Save Project",
                "undo": "Undo",
                "redo": "Redo",
                "crop": "Crop Tool",
                "lasso": "Lasso Selection Tool",
                "clear": "Clear Selection",
                "help": "Help Guide"
            }
            tooltip_text = friendly_names.get(icon_name, icon_name.capitalize())
        
        self.style_map = {
            'Action.TButton': (THEME_BG_ELEVATED, THEME_COLOR_ACCENT),
            'ToolbarBlue.TButton': (THEME_BG_ELEVATED, THEME_COLOR_ACCENT),
            'Success.TButton': (THEME_COLOR_ACCENT, THEME_COLOR_ACCENT_HOVER),
            'ToolbarTeal.TButton': (THEME_BG_ELEVATED, THEME_COLOR_SUCCESS),
            'Danger.TButton': ("#362029", THEME_COLOR_DANGER),
            'ToolbarRed.TButton': (THEME_BG_ELEVATED, THEME_COLOR_DANGER),
            'ToolbarYellow.TButton': (THEME_BG_ELEVATED, THEME_COLOR_WARNING),
            'ToolbarGrey.TButton': (THEME_BG_ELEVATED, THEME_COLOR_BORDER_STRONG),
            'Toolbar.TButton': (THEME_BG_ELEVATED, THEME_COLOR_BORDER_STRONG),
        }
        
        base_color, accent_color = self.style_map.get(style, (THEME_BG_MAIN, THEME_COLOR_BORDER))
        self.current_style = style
        self.base_color = base_color
        self.accent_color = accent_color
        self.uses_image = bool(icon_name)
        
        custom_w = kwargs.pop("custom_w", None)
        custom_h = kwargs.pop("custom_h", None)

        if custom_w is not None and custom_h is not None:
            w = custom_w
            h = custom_h
            font_config = ('Segoe UI Semibold', 10)
        elif icon_name:
            w = 42
            h = 42
            font_config = ('Segoe UI', 13)
            kwargs["text"] = ""
        else:
            w = max(96, len(text) * 7 + 28)
            h = 34
            font_config = ('Segoe UI Semibold', 9)
            
        self.w = w
        self.h = h

        parent_bg = THEME_BG_SURFACE
        if master is not None and hasattr(master, "cget"):
            try:
                # GlassPanel paints its elevated surface as a background image,
                # while the underlying Canvas still reports the page color.
                # Using that reported color creates a square halo around rounded
                # icon tiles. Match the visible card surface instead.
                if isinstance(master, GlassPanel):
                    parent_bg = THEME_BG_SURFACE
                else:
                    parent_bg = master.cget("bg")
            except Exception:
                pass

        common = {
            "relief": "flat",
            "bd": 0,
            "highlightthickness": 0,
            "compound": "center",
            "cursor": "hand2",
            "font": font_config,
        }

        if self.uses_image:
            self._build_icon_images()
            common.update({
                "image": self.normal_photo,
                "bg": parent_bg,
                "activebackground": parent_bg,
                "fg": THEME_COLOR_TEXT,
                "activeforeground": accent_color,
            })
        else:
            text_fg = "#FFFFFF" if style == "Success.TButton" else THEME_COLOR_TEXT
            common.update({
                "bg": base_color,
                "activebackground": self._shift_color(base_color, -8),
                "fg": text_fg,
                "activeforeground": "#FFFFFF",
                "padx": 14,
                "pady": 7,
            })

        kwargs.update(common)
        
        super().__init__(master, **kwargs)
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        
        if tooltip_text:
            ToolTip(self, tooltip_text)

    @staticmethod
    def _shift_color(color, amount):
        value = color.lstrip("#")
        rgb = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
        rgb = [max(0, min(255, channel + amount)) for channel in rgb]
        return "#" + "".join(f"{channel:02X}" for channel in rgb)

    def _build_icon_images(self):
        normal_img = _render_glossy_button(
            self.w, self.h, "normal", self.base_color, self.accent_color, icon_name=self.icon_name
        )
        hover_img = _render_glossy_button(
            self.w, self.h, "hover", self.base_color, self.accent_color, icon_name=self.icon_name
        )
        pressed_img = _render_glossy_button(
            self.w, self.h, "pressed", self.base_color, self.accent_color, icon_name=self.icon_name
        )
        self.normal_photo = ImageTk.PhotoImage(normal_img)
        self.hover_photo = ImageTk.PhotoImage(hover_img)
        self.pressed_photo = ImageTk.PhotoImage(pressed_img)

    def change_style(self, style):
        base_color, accent_color = self.style_map.get(style, (THEME_BG_MAIN, THEME_COLOR_BORDER))
        self.current_style = style
        self.base_color = base_color
        self.accent_color = accent_color
        if self.uses_image:
            self._build_icon_images()
            if self.cget("state") != "disabled":
                super().configure(image=self.normal_photo)
        else:
            text_fg = "#FFFFFF" if style == "Success.TButton" else THEME_COLOR_TEXT
            super().configure(
                bg=base_color,
                activebackground=self._shift_color(base_color, -8),
                fg=text_fg,
            )

    def configure(self, cnf=None, **kw):
        style = kw.pop("style", None)
        if style is not None:
            self.change_style(style)
        if cnf is not None:
            style = cnf.pop("style", None)
            if style is not None:
                self.change_style(style)
        super().configure(cnf, **kw)

    def config(self, cnf=None, **kw):
        self.configure(cnf, **kw)

    def on_enter(self, e):
        if self.cget("state") != "disabled":
            if self.uses_image:
                super().configure(image=self.hover_photo, fg=self.accent_color)
            else:
                super().configure(bg=self._shift_color(self.base_color, 12))
 
    def on_leave(self, e):
        if self.cget("state") != "disabled":
            if self.uses_image:
                super().configure(image=self.normal_photo, fg=THEME_COLOR_TEXT)
            else:
                super().configure(bg=self.base_color)
 
    def on_press(self, e):
        if self.cget("state") != "disabled":
            if self.uses_image:
                super().configure(image=self.pressed_photo, fg=self.accent_color)
            else:
                super().configure(bg=self._shift_color(self.base_color, -8))
 
    def on_release(self, e):
        if self.cget("state") != "disabled":
            if self.uses_image:
                super().configure(image=self.hover_photo, fg=self.accent_color)
            else:
                super().configure(bg=self._shift_color(self.base_color, 12))
            
    def state(self, statespec):
        if "disabled" in statespec:
            self.config(state="disabled")
        elif "!disabled" in statespec:
            self.config(state="normal")


# Apply Module Overrides
ttk.Button = CustomButton
ttk.LabelFrame = GlassPanel


class TransparentorApp:
    def __init__(self, root):
        self.root = root
        # Every AI job runs inside this process. Track those jobs and expose a
        # single shutdown signal so closing the app cannot leave work running.
        self._shutdown_event = threading.Event()
        self._worker_threads = set()
        self._worker_threads_lock = threading.Lock()
        self._cleanup_complete = False
        self.ai_progress_value = 0.0
        self.ai_progress_target = 0.0
        self.ai_progress_active = False
        self.ai_progress_stage = "Ready"
        self.ai_progress_stage_started = None
        self.ai_progress_stage_start = 0.0
        self.ai_progress_stage_end = 0.0
        self.ai_progress_stage_expected = None
        self.ai_progress_task_started = None
        self.ai_progress_item_expected = None
        self.ai_progress_queue_remaining = 0
        self.ai_progress_after_id = None
        self.ai_progress_shimmer = 0.0
        self.ai_progress_reset_after_id = None
        self.ai_inference_started = None
        self.ai_duration_estimates = _load_ai_duration_estimates()
        _apply_window_identity(self.root, APP_NAME)
        _center_window(self.root, 1440, 900)
        self.root.minsize(1180, 720)

        # Modern dark creative-tool theme
        self.BG_MAIN = THEME_BG_MAIN
        self.BG_SURFACE = THEME_BG_SURFACE
        self.BG_ELEVATED = THEME_BG_ELEVATED
        self.BG_INPUT = THEME_BG_INPUT
        self.COLOR_BORDER = THEME_COLOR_BORDER
        self.COLOR_BORDER_STRONG = THEME_COLOR_BORDER_STRONG
        self.COLOR_TEXT = THEME_COLOR_TEXT
        self.COLOR_MUTED = THEME_COLOR_MUTED
        self.COLOR_ACCENT = THEME_COLOR_ACCENT
        self.COLOR_ACCENT_HOVER = THEME_COLOR_ACCENT_HOVER
        self.COLOR_SUCCESS = THEME_COLOR_SUCCESS
        self.COLOR_DANGER = THEME_COLOR_DANGER
        self.COLOR_WARNING = THEME_COLOR_WARNING

        # Compatibility aliases for existing drawing and editor code
        self.PS1_GREY = self.BG_MAIN
        self.PS1_GREY_DK = self.COLOR_BORDER
        self.PS1_GREY_LT = self.BG_INPUT
        self.PS1_INK = self.COLOR_TEXT
        self.PS1_BLUE = self.COLOR_ACCENT
        self.PS1_TEAL = self.COLOR_SUCCESS
        self.PS1_YELLOW = self.COLOR_WARNING
        self.PS1_RED = self.COLOR_DANGER

        self.root.configure(bg=self.BG_MAIN)

        # Style setup
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Global Option Database defaults for non-ttk widgets and listbox dropdowns
        self.root.option_add('*TCombobox*Listbox.background', self.BG_INPUT)
        self.root.option_add('*TCombobox*Listbox.foreground', self.COLOR_TEXT)
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.COLOR_ACCENT)
        self.root.option_add('*TCombobox*Listbox.selectForeground', self.BG_SURFACE)
        self.root.option_add('*Listbox.background', self.BG_INPUT)
        self.root.option_add('*Listbox.foreground', self.COLOR_TEXT)
        self.root.option_add('*Listbox.selectBackground', self.COLOR_ACCENT)
        self.root.option_add('*Listbox.selectForeground', self.BG_SURFACE)

        # Configure typography and shared widget surfaces
        font_family = 'Segoe UI'
        self.style.configure('.', font=(font_family, 10), background=self.BG_MAIN, foreground=self.COLOR_TEXT)

        self.style.configure('TFrame', background=self.BG_SURFACE)
        self.style.configure('Main.TFrame', background=self.BG_MAIN)
        self.style.configure('Elevated.TFrame', background=self.BG_ELEVATED)
        self.style.configure('Toolbar.TFrame', background=self.BG_MAIN)

        self.style.configure('TLabel', background=self.BG_SURFACE, foreground=self.COLOR_TEXT, font=(font_family, 10))
        self.style.configure('Muted.TLabel', background=self.BG_SURFACE, foreground=self.COLOR_MUTED, font=(font_family, 9))
        self.style.configure('Eyebrow.TLabel', background=self.BG_SURFACE, foreground=self.COLOR_ACCENT, font=('Segoe UI Semibold', 8))
        self.style.configure('TCheckbutton', background=self.BG_SURFACE, foreground=self.COLOR_TEXT, font=(font_family, 9), focuscolor="", bordercolor=self.COLOR_BORDER, lightcolor=self.COLOR_BORDER, darkcolor=self.COLOR_BORDER)
        self.style.map('TCheckbutton', foreground=[('disabled', self.COLOR_MUTED)], background=[('active', self.BG_SURFACE)])
        self.style.configure('TRadiobutton', background=self.BG_SURFACE, foreground=self.COLOR_TEXT, font=(font_family, 9), focuscolor="", bordercolor=self.COLOR_BORDER, lightcolor=self.COLOR_BORDER, darkcolor=self.COLOR_BORDER)
        self.style.map('TRadiobutton', foreground=[('disabled', self.COLOR_MUTED)], background=[('active', self.BG_SURFACE)])

        self.style.configure('Header.TLabel', background=self.BG_MAIN, foreground=self.COLOR_TEXT, font=(font_family, 9))
        self.style.configure('HeaderMuted.TLabel', background=self.BG_MAIN, foreground=self.COLOR_MUTED, font=(font_family, 8))
        self.style.configure('Brand.TLabel', background=self.BG_MAIN, foreground=self.COLOR_TEXT, font=('Segoe UI Semibold', 13))
        self.style.configure('Header.TCheckbutton', background=self.BG_MAIN, foreground=self.COLOR_TEXT, font=(font_family, 9), focuscolor="", bordercolor=self.COLOR_BORDER, lightcolor=self.COLOR_BORDER, darkcolor=self.COLOR_BORDER)
        self.style.map('Header.TCheckbutton', background=[('active', self.BG_MAIN)], foreground=[('disabled', self.COLOR_MUTED)])

        self.style.configure('Horizontal.TScale', background=self.BG_SURFACE, troughcolor=self.BG_INPUT, slidercolor=self.COLOR_ACCENT, borderwidth=0, thickness=6)
        self.style.configure('TEntry', fieldbackground=self.BG_INPUT, foreground=self.COLOR_TEXT, insertcolor=self.COLOR_TEXT, bordercolor=self.COLOR_BORDER, lightcolor=self.COLOR_BORDER, darkcolor=self.COLOR_BORDER, padding=(8, 6))
        self.style.configure('TCombobox', fieldbackground=self.BG_INPUT, foreground=self.COLOR_TEXT, selectbackground=self.COLOR_ACCENT, selectforeground="#FFFFFF", bordercolor=self.COLOR_BORDER, lightcolor=self.COLOR_BORDER, darkcolor=self.COLOR_BORDER, arrowcolor=self.COLOR_MUTED, padding=(7, 5))
        self.style.map('TCombobox',
            fieldbackground=[('readonly', self.BG_INPUT)],
            background=[('readonly', self.BG_INPUT)],
            foreground=[('readonly', self.COLOR_TEXT)],
            arrowcolor=[('readonly', self.COLOR_MUTED), ('active', self.COLOR_TEXT)],
            bordercolor=[('focus', self.COLOR_ACCENT), ('readonly', self.COLOR_BORDER)]
        )
        self.style.configure('TSpinbox', fieldbackground=self.BG_INPUT, foreground=self.COLOR_TEXT, selectbackground=self.COLOR_ACCENT, selectforeground="#FFFFFF", bordercolor=self.COLOR_BORDER, lightcolor=self.COLOR_BORDER, darkcolor=self.COLOR_BORDER, arrowcolor=self.COLOR_MUTED, padding=(6, 4))
        self.style.configure('TSeparator', background=self.COLOR_BORDER)

        self.style.configure('TScrollbar', background=self.BG_ELEVATED, troughcolor=self.BG_MAIN, bordercolor=self.BG_MAIN, arrowcolor=self.COLOR_MUTED)
        self.style.map('TScrollbar',
            background=[('pressed', self.COLOR_ACCENT), ('active', self.COLOR_BORDER_STRONG)],
        )
        
        self.style.configure('TProgressbar', thickness=6, troughcolor=self.BG_INPUT, bordercolor=self.BG_INPUT, background=self.COLOR_ACCENT)

        self.style.configure(
            'TNotebook',
            background=self.BG_MAIN,
            borderwidth=0,
            padding=0,
            bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_BORDER,
            darkcolor=self.COLOR_BORDER,
        )
        self.style.configure(
            'TNotebook.Tab',
            background=self.BG_MAIN,
            foreground=self.COLOR_MUTED,
            padding=(16, 10),
            font=('Segoe UI Semibold', 9),
            borderwidth=1,
            bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_BORDER,
            darkcolor=self.COLOR_BORDER,
            focuscolor=self.BG_MAIN,
        )
        self.style.map('TNotebook.Tab',
            background=[('selected', self.BG_SURFACE), ('active', self.BG_ELEVATED)],
            foreground=[('selected', self.COLOR_ACCENT), ('active', self.COLOR_TEXT)],
            bordercolor=[('selected', self.COLOR_BORDER_STRONG), ('active', self.COLOR_BORDER_STRONG)],
            lightcolor=[('selected', self.COLOR_BORDER_STRONG), ('active', self.COLOR_BORDER_STRONG)],
            darkcolor=[('selected', self.COLOR_BORDER_STRONG), ('active', self.COLOR_BORDER_STRONG)],
        )
        self.style.configure('TabContent.TFrame', background=self.BG_MAIN)
        self.style.configure('NamesInner.TFrame', background=self.BG_INPUT)
        self.style.configure('NamesLabel.TLabel', background=self.BG_INPUT, foreground=self.COLOR_TEXT)

        self.original_img = None
        self.edited_img = None
        self.actions = []
        self.redo_actions = []
        self.history = []            # list of past edited_img snapshots
        self.future_history = []     # list of undone snapshots for redo
        self.rules = []
        self.current_preview_rule = None
        self.swap_old_color = None
        self.color_swap_color = None
        self.blend_color = None
        self.blend_strength = tk.DoubleVar(value=50)
        self.last_blend_index = None
        self.edge_blend_mode = tk.StringVar(value="transparent")  # default edge blend to transparency
        self.mode = 'picker'
        self.brush_size = 24
        self.mode_var = tk.StringVar(value="picker")
        self.brush_var = tk.IntVar(value=24)
        self.hex_var = tk.StringVar(value="#000000")
        self.side_by_side = tk.BooleanVar(value=False)
        self.tol_var = tk.DoubleVar(value=20)
        self.tol_var.trace_add("write", self.on_tol_change)
        self.soft_var = tk.DoubleVar(value=0.0)
        self.soft_var.trace_add("write", self.on_tol_change)
        self.contiguous_var = tk.BooleanVar(value=True)
        self.contiguous_var.trace_add("write", self.on_tol_change)
        self.clean_holes_var = tk.BooleanVar(value=True)
        self.clean_holes_var.trace_add("write", self.on_tol_change)
        self.zoom_fit = True
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.pan_start = None
        # Multi-image composition state. Layers are stored bottom-to-top and
        # retain their original RGBA pixels so transforms remain non-destructive.
        self.is_composition_active = False
        self.composition_layers = []
        self.composition_selected_index = None
        self.composition_canvas_size = None
        self.composition_history = []
        self.composition_future_history = []
        self.composition_drag_state = None
        self.composition_drag_history_pushed = False
        self.composition_layer_refs = []
        self.composition_x_var = tk.IntVar(value=0)
        self.composition_y_var = tk.IntVar(value=0)
        self.composition_scale_var = tk.DoubleVar(value=100.0)
        self.composition_rotation_var = tk.DoubleVar(value=0.0)
        self.composition_opacity_var = tk.DoubleVar(value=100.0)
        self.composition_brightness_var = tk.DoubleVar(value=100.0)
        self.composition_contrast_var = tk.DoubleVar(value=100.0)
        self.composition_saturation_var = tk.DoubleVar(value=100.0)
        self.composition_blur_var = tk.DoubleVar(value=0.0)
        self.composition_shadow_enabled_var = tk.BooleanVar(value=False)
        self.composition_shadow_opacity_var = tk.DoubleVar(value=45.0)
        self.composition_shadow_blur_var = tk.DoubleVar(value=18.0)
        self.composition_shadow_x_var = tk.IntVar(value=14)
        self.composition_shadow_y_var = tk.IntVar(value=14)
        self.composition_preview_after_id = None
        self.composition_preview_cache = {}
        self.composition_effect_cache = {}
        self.composition_controls_syncing = False
        self.composition_control_history_pushed = False
        self.composition_control_commit_after_id = None

        # Batch processing owns a temporary main-canvas preview while it runs.
        self.batch_files_list = []
        self.batch_preview_active = False
        self.batch_preview_image = None
        self.batch_preview_index = None
        self.batch_preview_status = ""
        self.batch_item_statuses = []
        self.batch_filmstrip_refs = []
        self.batch_thumbnail_cache = {}
        # Multi-file drops in Edit use the same filmstrip surface, but retain
        # their results in memory instead of opening the Compose workspace.
        self.edit_queue_active = False
        self.edit_queue_running = False
        self.edit_queue_results = {}
        self.edit_queue_errors = {}
        self.crop_start = None
        self.crop_rect = None
        self.resize_width_var = tk.IntVar(value=0)
        self.resize_height_var = tk.IntVar(value=0)
        self.resize_percent_var = tk.DoubleVar(value=100.0)
        self.resize_lock_aspect_var = tk.BooleanVar(value=True)
        self.resize_quality_var = tk.StringVar(value="Lanczos (Best)")
        self.resize_current_size_var = tk.StringVar(value="No image loaded")
        self.crop_x_var = tk.IntVar(value=0)
        self.crop_y_var = tk.IntVar(value=0)
        self.crop_width_var = tk.IntVar(value=0)
        self.crop_height_var = tk.IntVar(value=0)
        self._crop_resize_syncing = False
        self.lasso_mode = False
        self.lasso_points = []
        self.lasso_line = None
        self.protected_mask = set()
        self.protected_overlay = None
        self.hex_var = tk.StringVar(value="#000000")
        self.preview_after_id = None
        self.brush_replace_color = None
        self._last_applied_action_count = 0
        self.ai_sessions = {}
        self.ai_model_var = tk.StringVar(value=DEFAULT_AI_MODEL)
        self._ai_model_display_to_value = {
            AI_MODEL_INFO[FUSION_AI_MODEL]["label"]: FUSION_AI_MODEL,
            AI_MODEL_INFO["birefnet-massive"]["label"]: "birefnet-massive",
            AI_MODEL_INFO["isnet-general-use"]["label"]: "isnet-general-use",
        }
        self._ai_model_value_to_display = {
            value: label for label, value in self._ai_model_display_to_value.items()
        }
        self.ai_model_display_var = tk.StringVar(
            value=self._ai_model_value_to_display[self.ai_model_var.get()]
        )
        self.force_ai_only_var = tk.BooleanVar(value=False)
        self._last_ai_model = self.ai_model_var.get()
        self._isnet_force_ai_pref = False
        self.replace_color_var = tk.StringVar(value="")
        self.auto_remove_on_click = tk.BooleanVar(value=False)

        # PNG -> GIF mode state
        self.png_gif_mode = tk.BooleanVar(value=False)
        self.gif_frame_paths = []
        self.gif_src_images = []
        self.gif_aligned_rgba = []
        self.gif_frame_omitted = []
        self.gif_history = []
        self.gif_future_history = []
        self.gif_preview_index = 0
        self.gif_playing = False
        self.gif_play_after_id = None
        self.gif_preview_after_id = None
        self._gif_frame_list_syncing = False
        self.gif_thumb_refs = []
        self.gif_filmstrip_menu = None
        self.gif_drag_index = None
        self.gif_drag_target_index = None
        self.gif_drag_start_x = 0
        self.gif_drag_start_y = 0
        self.gif_dragging = False
        self._gif_syncing_scrub = False
        self.help_window = None
        self.photo = None
        self.photo_size = None
        self.active_brush_action = None
        self.active_brush_rule_index = None
        self.last_brush_point = None
        self.cursor_canvas_pos = None
        self.live_preview_after_id = None
        self.canvas_image_item = None
        self.live_brush_preview_img = None
        self.live_brush_preview_key = None
        self.live_brush_preview_scale = None
        self.brush_cursor_ring = None
        self.brush_cursor_ring_outer = None
        self.brush_cursor_crosshair_h = None
        self.brush_cursor_crosshair_v = None
        self.brush_cursor_label = None
        self.brush_cursor_label_shadow = None
        self._slicer_font_cache = {}

        # PNG -> GIF settings (live UI-controlled)
        # VFX usually align best by center/centroid (not foot-planting).
        self.gif_duration_ms = tk.IntVar(value=80)
        self.gif_anchor = tk.StringVar(value="center")
        self.gif_alpha_threshold = tk.IntVar(value=1)
        self.gif_padding = tk.IntVar(value=0)
        self.gif_preview_checker = tk.BooleanVar(value=True)
        self.gif_frame_export_format = tk.StringVar(value="PNG")
        self.gif_template_box = None
        self.gif_aligned_template_box = None
        self.gif_template_frame_idx = None

        # Presets
        self.gif_preset = tk.StringVar(value="VFX")
        self._gif_applying_preset = False

        # Slicer state
        self.editor_image_path = None
        self.slicer_image = None  # PIL Image loaded for slicing
        self.slicer_image_path = None
        self.slicer_cols = tk.IntVar(value=3)
        self.slicer_rows = tk.IntVar(value=2)
        self.slicer_scale = tk.DoubleVar(value=1.0)
        self.slicer_crop_square = tk.BooleanVar(value=True)
        self.slicer_crop_center_content = tk.BooleanVar(value=True)
        self.slicer_square_trim_x = tk.IntVar(value=0)
        self.slicer_square_trim_y = tk.IntVar(value=0)
        self.slicer_output_size = tk.StringVar(value="Original")
        self.slicer_export_format = tk.StringVar(value="PNG")
        self.slicer_preview_grid = True
        self.slicer_names = []  # List of name entries for each slice

        # Additional grid adjustment (padding/margins)
        self.slicer_margin_x = tk.IntVar(value=0)
        self.slicer_margin_y = tk.IntVar(value=0)
        self.slicer_padding_x = tk.IntVar(value=0)
        self.slicer_padding_y = tk.IntVar(value=0)
        self.slicer_expand_w = tk.IntVar(value=0)
        self.slicer_expand_h = tk.IntVar(value=0)
        self.slicer_use_manual = tk.BooleanVar(value=False)
        self.slicer_boxes = []
        self.slicer_trim_transparency = tk.BooleanVar(value=False)
        self.slicer_trim_threshold = tk.IntVar(value=10)
        self.slicer_batch_images = []
        self.slicer_batch_active_idx = 0
        self.slicer_history = []
        self.slicer_future_history = []

        # Tab state flags
        self.is_slicer_active = False

        # Preview background selection
        self.preview_bg_var = tk.StringVar(value="Checker (Dark)")
        self.preview_custom_bg = None

        self.setup_ui()
        self._apply_dark_widget_theme()
        
        self.project_dirty = False
        self.current_project_path = None

        # Bind keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.open_image())
        self.root.bind('<Control-O>', lambda e: self.open_image())
        self.root.bind('<Control-s>', lambda e: self.save_image())
        self.root.bind('<Control-S>', lambda e: self.save_image())
        self.root.bind('<F1>', lambda e: self.open_help_window())
        self.root.bind('<Control-b>', lambda e: self.open_batch_bg_removal_window())
        self.root.bind('<Control-B>', lambda e: self.open_batch_bg_removal_window())

        # Configure menu bar
        self._create_menu_bar()

        # Canvas resize binding to redraw welcome screen dynamically
        self.canvas.bind("<Configure>", lambda e: self.update_preview(), add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_closing)

        # Clipboard paste (Ctrl+V)
        try:
            self.root.bind_all("<Control-v>", self._on_paste_shortcut, add="+")
            self.root.bind_all("<Control-V>", self._on_paste_shortcut, add="+")
        except Exception:
            pass

        # Thread lock for AI session creation
        self.ai_session_lock = threading.Lock()

        # Pre-initialize default AI model in a background thread to make the first run instant
        self._start_worker(self._pre_initialize_ai, "ai-preload")

        self.update_preview()

    def setup_ui(self):
        # Compact application header: product identity, engine state, and
        # context controls share one calm horizontal surface.
        self.header_canvas = tk.Canvas(
            self.root,
            height=70,
            bg=self.BG_MAIN,
            highlightthickness=0,
            bd=0,
        )
        self.header_canvas.pack(fill=tk.X, padx=0, pady=(0, 2))
        self.header_canvas.bind("<Configure>", lambda _e: self._draw_header_bands())

        toolbar = ttk.Frame(self.header_canvas, style='Main.TFrame')
        self._toolbar_window = self.header_canvas.create_window(14, 9, anchor="nw", window=toolbar)

        def add_sep(parent):
            ttk.Separator(parent, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=7)

        left_group = ttk.Frame(toolbar, style='Main.TFrame')
        left_group.pack(side=tk.LEFT, pady=2)

        brand_mark = tk.Canvas(
            left_group,
            width=36,
            height=36,
            bg=self.BG_MAIN,
            highlightthickness=0,
            bd=0,
        )
        brand_mark.pack(side=tk.LEFT, padx=(0, 10))
        try:
            brand_icon_path = _get_app_icon_path()
            if brand_icon_path is None:
                raise FileNotFoundError("Application icon asset was not found.")
            brand_icon = _build_brand_mark_image(brand_icon_path, 36)
            self._brand_mark_photo = ImageTk.PhotoImage(brand_icon)
            brand_mark.create_image(
                18,
                18,
                image=self._brand_mark_photo,
            )
        except Exception:
            brand_mark.create_oval(
                2,
                2,
                34,
                34,
                fill=self.COLOR_ACCENT,
                outline="#91A7FF",
                width=1,
            )
            brand_mark.create_text(
                18,
                18,
                text="T",
                fill="#FFFFFF",
                font=('Segoe UI Semibold', 15),
            )

        brand_copy = ttk.Frame(left_group, style='Main.TFrame')
        brand_copy.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(brand_copy, text="Transparentor", style='Brand.TLabel').pack(anchor="w")
        ttk.Label(brand_copy, text="LOCAL IMAGE STUDIO", style='HeaderMuted.TLabel').pack(anchor="w")

        add_sep(left_group)

        self.ai_indicator = tk.Canvas(left_group, width=10, height=10, bg=self.BG_MAIN, highlightthickness=0)
        self.ai_indicator.pack(side=tk.LEFT, padx=(2, 7))
        self.ai_indicator_circle = self.ai_indicator.create_oval(2, 2, 8, 8, fill=self.COLOR_SUCCESS, outline=self.COLOR_SUCCESS)
        
        status_copy = ttk.Frame(left_group, style='Main.TFrame')
        status_copy.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(status_copy, text="AI ENGINE", style='HeaderMuted.TLabel').pack(anchor="w")
        self.ai_status_label = ttk.Label(
            status_copy,
            text="READY",
            width=24,
            anchor="w",
            font=('Segoe UI Semibold', 9),
            foreground=self.COLOR_TEXT,
            style='Header.TLabel',
        )
        self.ai_status_label.pack(anchor="w")
        
        self.ai_progress = tk.Canvas(
            left_group,
            width=190,
            height=34,
            bg=self.BG_MAIN,
            highlightthickness=0,
            bd=0,
        )
        self.ai_progress.pack(side=tk.LEFT, padx=(0, 8))
        self.ai_progress.bind("<Configure>", lambda _e: self._draw_ai_progress())
        self._draw_ai_progress()

        right_group = ttk.Frame(toolbar, style='Main.TFrame')
        right_group.pack(side=tk.RIGHT, pady=4)

        self.compare_check = ttk.Checkbutton(
            right_group,
            text="Compare",
            variable=self.side_by_side,
            command=self.update_preview,
            style='Header.TCheckbutton',
        )
        self.compare_check.pack(side=tk.LEFT, padx=(0, 14))

        # Background Selector
        bg_group = ttk.Frame(right_group, style='Main.TFrame')
        bg_group.pack(side=tk.LEFT, padx=(0, 14))
        ttk.Label(bg_group, text="Preview", style='HeaderMuted.TLabel').pack(side=tk.LEFT, padx=(0, 6))
        self.bg_combo = ttk.Combobox(
            bg_group,
            textvariable=self.preview_bg_var,
            values=["Checker (Dark)", "Checker (Light)", "Solid Dark", "Solid Light", "Chroma Green", "Custom Color..."],
            state="readonly",
            width=13,
        )
        self.bg_combo.pack(side=tk.LEFT)
        self.bg_combo.bind("<<ComboboxSelected>>", self._on_bg_combo_changed)

        mode_group = ttk.Frame(right_group, style='Main.TFrame')
        mode_group.pack(side=tk.LEFT)
        ttk.Label(mode_group, text="Tool", style='HeaderMuted.TLabel').pack(side=tk.LEFT, padx=(0, 6))

        # Compact mode selector (saves a lot of header space vs radio cluster)
        self._mode_display_to_value = {
            "Picker": "picker",
            "Eraser": "erase",
            "Replace": "replace_single",
        }
        self._mode_value_to_display = {v: k for k, v in self._mode_display_to_value.items()}
        self.mode_display_var = tk.StringVar(value=self._mode_value_to_display.get(self.mode_var.get(), "Picker"))
        self.mode_combo = ttk.Combobox(
            mode_group,
            textvariable=self.mode_display_var,
            values=list(self._mode_display_to_value.keys()),
            state="readonly",
            width=9,
        )
        self.mode_combo.pack(side=tk.LEFT)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_combo_changed)

        add_sep(right_group)

        brush_group = ttk.Frame(right_group, style='Main.TFrame')
        brush_group.pack(side=tk.LEFT)
        ttk.Label(brush_group, text="Brush", style='HeaderMuted.TLabel').pack(side=tk.LEFT, padx=(0, 6))

        # Compact brush size selector
        self.brush_spin = ttk.Spinbox(
            brush_group,
            from_=1,
            to=99,
            textvariable=self.brush_var,
            width=3,
            command=self._on_brush_changed,
        )
        self.brush_spin.pack(side=tk.LEFT)
        ttk.Label(brush_group, text="px", style='Header.TLabel').pack(side=tk.LEFT, padx=(4, 0))
        self.brush_var.trace_add("write", lambda *_: self._on_brush_changed())

        self.replace_color_label = ttk.Label(right_group, textvariable=self.replace_color_var, style='Header.TLabel')
        self.replace_color_label.pack(side=tk.LEFT, padx=(12, 0))

        self.replace_color_swatch = tk.Canvas(
            right_group,
            width=14,
            height=14,
            highlightthickness=1,
            highlightbackground=self.PS1_GREY_DK,
            bd=0,
            bg=self.BG_MAIN,
        )
        self.replace_color_swatch.pack(side=tk.LEFT, padx=(6, 0))
        self.replace_color_swatch_rect = self.replace_color_swatch.create_rectangle(
            1,
            1,
            13,
            13,
            fill=self.PS1_GREY_DK,
            outline=self.PS1_GREY_DK,
        )

        self.replace_color_clear_btn = ttk.Button(
            right_group,
            text="Clear",
            style='ToolbarGrey.TButton',
            command=self._clear_replace_color,
        )
        self.replace_color_clear_btn.pack(side=tk.LEFT, padx=(6, 0))
        self._update_replace_color_label()

        # Main Layout Restructuring Container
        self.main_container = ttk.Frame(self.root, style='Main.TFrame')
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Focused tool rail with consistent line icons and tooltip labels.
        self.tool_sidebar = GlassPanel(self.main_container, width=62)
        self.tool_sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 4), pady=8)
        self.tool_sidebar.pack_propagate(False)

        rail_pad = {"side": tk.TOP, "padx": 8, "pady": 4}

        btn_open = ttk.Button(self.tool_sidebar, text="", icon="image", style='ToolbarBlue.TButton', command=self.open_image)
        btn_open.pack(**rail_pad)
        ToolTip(btn_open, "Open/Import Image (Ctrl+O)")

        btn_paste = ttk.Button(self.tool_sidebar, text="", icon="clipboard", style='ToolbarGrey.TButton', command=self.paste_image_from_clipboard)
        btn_paste.pack(**rail_pad)
        ToolTip(btn_paste, "Paste Image from Clipboard (Ctrl+V)")

        btn_save = ttk.Button(self.tool_sidebar, text="", icon="save", style='ToolbarGrey.TButton', command=self.save_image)
        btn_save.pack(**rail_pad)
        ToolTip(btn_save, "Save/Export Output Image (Ctrl+S)")

        btn_discard = ttk.Button(self.tool_sidebar, text="", icon="discard", style='ToolbarRed.TButton', command=self.discard_image)
        btn_discard.pack(**rail_pad)
        ToolTip(btn_discard, "Discard Current Image / Reset Editor")

        ttk.Separator(self.tool_sidebar, orient='horizontal').pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)

        btn_load_proj = ttk.Button(self.tool_sidebar, text="", icon="folder", style='ToolbarGrey.TButton', command=self.load_project)
        btn_load_proj.pack(**rail_pad)
        ToolTip(btn_load_proj, "Load Project File")

        btn_save_proj = ttk.Button(self.tool_sidebar, text="", icon="project", style='ToolbarGrey.TButton', command=self.save_project)
        btn_save_proj.pack(**rail_pad)
        ToolTip(btn_save_proj, "Save Project File")

        ttk.Separator(self.tool_sidebar, orient='horizontal').pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)

        btn_undo = ttk.Button(self.tool_sidebar, text="", icon="undo", style='ToolbarGrey.TButton', command=self.undo)
        btn_undo.pack(**rail_pad)
        ToolTip(btn_undo, "Undo Last Action (Ctrl+Z)")

        btn_redo = ttk.Button(self.tool_sidebar, text="", icon="redo", style='ToolbarGrey.TButton', command=self.redo)
        btn_redo.pack(**rail_pad)
        ToolTip(btn_redo, "Redo Last Action (Ctrl+Y)")

        ttk.Separator(self.tool_sidebar, orient='horizontal').pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)

        btn_crop = ttk.Button(self.tool_sidebar, text="", icon="crop", style='ToolbarGrey.TButton', command=self.start_crop)
        btn_crop.pack(**rail_pad)
        ToolTip(btn_crop, "Crop Image Tool")

        btn_lasso = ttk.Button(self.tool_sidebar, text="", icon="lasso", style='ToolbarGrey.TButton', command=self.start_lasso_mode)
        btn_lasso.pack(**rail_pad)
        ToolTip(btn_lasso, "Lasso Selection Tool (Shift+Click)")

        btn_clear_sel = ttk.Button(self.tool_sidebar, text="", icon="clear", style='ToolbarRed.TButton', command=self.clear_lasso_selection)
        btn_clear_sel.pack(**rail_pad)
        ToolTip(btn_clear_sel, "Clear Lasso Selection (Escape)")

        ttk.Separator(self.tool_sidebar, orient='horizontal').pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)

        btn_help = ttk.Button(self.tool_sidebar, text="", icon="help", style='ToolbarGrey.TButton', command=self.open_help_window)
        btn_help.pack(**rail_pad)
        ToolTip(btn_help, "Open Help & Keyboard Shortcuts (F1)")

        # Center Canvas Container
        self.canvas_container = ttk.Frame(self.main_container, style='Main.TFrame')
        self.canvas_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=8)

        # Bottom Filmstrip Timeline Container (starts hidden, packed on tab change)
        self.bottom_filmstrip_frame = GlassPanel(self.canvas_container, text="Filmstrip", bullet_color=self.COLOR_ACCENT)

        # Batch queue filmstrip. It is separate from the animation timeline so
        # batch work can take over the main preview without changing tabs.
        self.batch_filmstrip_frame = GlassPanel(
            self.canvas_container,
            text="AI Queue",
            bullet_color=self.COLOR_SUCCESS,
        )
        self.batch_filmstrip_status_var = tk.StringVar(value="Ready")
        ttk.Label(
            self.batch_filmstrip_frame,
            textvariable=self.batch_filmstrip_status_var,
            style="Muted.TLabel",
        ).pack(anchor="w", padx=12, pady=(2, 2))
        self.batch_filmstrip_canvas = tk.Canvas(
            self.batch_filmstrip_frame,
            height=100,
            bg=self.BG_INPUT,
            highlightthickness=1,
            highlightbackground=self.COLOR_BORDER,
            bd=0,
        )
        self.batch_filmstrip_canvas.pack(fill=tk.X, expand=True, padx=8, pady=(0, 4))
        self.batch_filmstrip_scrollbar = ttk.Scrollbar(
            self.batch_filmstrip_frame,
            orient="horizontal",
            command=self.batch_filmstrip_canvas.xview,
        )
        self.batch_filmstrip_scrollbar.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.batch_filmstrip_canvas.configure(xscrollcommand=self.batch_filmstrip_scrollbar.set)
        self.batch_filmstrip_canvas.bind("<Configure>", lambda _e: self._render_batch_filmstrip())
        self.batch_filmstrip_canvas.bind("<Button-1>", self.on_batch_filmstrip_click)

        # Right Inspector Panel (holds settings Notebook)
        # We name this variable 'left' for backwards compatibility
        left = ttk.Frame(self.main_container, style='Main.TFrame', width=370)
        left.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 10), pady=8)
        left.pack_propagate(False)

        # Scrollable left panel for smaller windows
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        left.grid_columnconfigure(1, minsize=12)

        self.left_scroll_canvas = tk.Canvas(left, highlightthickness=0, bd=0, bg=self.PS1_GREY)
        self.left_scroll_canvas.grid(row=0, column=0, sticky="nsew")
        self.left_scrollbar = tk.Canvas(
            left,
            width=12,
            bg=self.PS1_GREY,
            highlightthickness=1,
            highlightbackground=self.PS1_GREY_DK,
            bd=0,
        )
        self.left_scrollbar.grid(row=0, column=1, sticky="ns")
        self.left_scroll_canvas.configure(yscrollcommand=self._on_left_scroll)

        self._left_scroll_thumb = None
        self._left_scroll_dragging = False
        self._left_scroll_drag_offset = 0
        self._left_scroll_range = (0, 0)

        self.left_scrollbar.bind("<Button-1>", self._on_left_scroll_click)
        self.left_scrollbar.bind("<B1-Motion>", self._on_left_scroll_drag)
        self.left_scrollbar.bind("<ButtonRelease-1>", self._on_left_scroll_release)

        self.left_scroll_frame = ttk.Frame(self.left_scroll_canvas, style='Main.TFrame')
        self.left_scroll_window = self.left_scroll_canvas.create_window(
            (0, 0),
            window=self.left_scroll_frame,
            anchor="nw",
        )

        def _on_left_frame_configure(_event=None):
            self.left_scroll_canvas.configure(scrollregion=self.left_scroll_canvas.bbox("all"))
            self._update_left_scrollbar()

        def _on_left_canvas_configure(event=None):
            if event is None:
                return
            self.left_scroll_canvas.itemconfigure(self.left_scroll_window, width=event.width)
            self._update_left_scrollbar()

        self.left_scroll_frame.bind("<Configure>", _on_left_frame_configure)
        self.left_scroll_canvas.bind("<Configure>", _on_left_canvas_configure)

        def _on_left_mousewheel(event):
            # Pass Slicer shortcuts (Ctrl/Shift + Scroll) to the main handler
            # 0x1=Shift, 0x4=Ctrl (on Windows/standard tk state)
            is_ctrl = (event.state & 0x4) != 0
            is_shift = (event.state & 0x1) != 0
            
            if is_ctrl or is_shift:
                if hasattr(self, 'on_mouse_wheel'):
                    # Explicitly pass detected state
                    self.on_mouse_wheel(event, force_ctrl=is_ctrl, force_shift=is_shift)
                    return "break"

            if self.left_scroll_canvas.winfo_height() <= 0:
                return
            self.left_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.left_scroll_canvas.bind("<MouseWheel>", _on_left_mousewheel)

        # Left panel uses tabs: Edit tools vs PNG→GIF tools vs Slicer
        self.left_notebook = ttk.Notebook(self.left_scroll_frame)
        self.left_notebook.pack(fill=tk.BOTH, expand=True)
        self.edit_tab = ttk.Frame(self.left_notebook, style='TabContent.TFrame')
        self.compose_tab = ttk.Frame(self.left_notebook, style='TabContent.TFrame')
        self.gif_tab = ttk.Frame(self.left_notebook, style='TabContent.TFrame')
        self.slicer_tab = ttk.Frame(self.left_notebook, style='TabContent.TFrame')
        self.left_notebook.add(self.edit_tab, text="Edit")
        self.left_notebook.add(self.compose_tab, text="Compose")
        self.left_notebook.add(self.gif_tab, text="Animate")
        self.left_notebook.add(self.slicer_tab, text="Slice")
        self.left_notebook.bind("<<NotebookTabChanged>>", self.on_left_tab_changed)
        self._setup_composition_tab()

        # AI removal is the primary workflow, so it receives the clearest card
        # and the only full-strength call-to-action in the inspector.
        ai_group = ttk.LabelFrame(self.edit_tab, text="Background Removal", style='Card.TLabelframe')
        ai_group.pack(fill=tk.X, pady=(10, 8), padx=2)

        ttk.Label(ai_group, text="LOCAL  •  ON-DEVICE", style='Eyebrow.TLabel').pack(
            anchor="w", padx=14, pady=(4, 2)
        )
        ttk.Label(
            ai_group,
            text="Create a clean transparent cutout with a local AI model.",
            style='Muted.TLabel',
            wraplength=300,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 10))

        model_row = ttk.Frame(ai_group)
        model_row.pack(fill=tk.X, padx=14, pady=(0, 4))
        
        ttk.Label(model_row, text="Model").pack(side=tk.LEFT, padx=(0, 10))
        
        self.model_combo = ttk.Combobox(
            model_row,
            textvariable=self.ai_model_display_var,
            values=list(self._ai_model_display_to_value.keys()),
            state="readonly",
            style='TCombobox'
        )
        self.model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_ai_model_display_changed)

        self.ai_model_hint = ttk.Label(
            ai_group,
            text="Combines clean structure with glow and fine-detail recovery",
            style='Muted.TLabel',
            wraplength=300,
            justify="left",
        )
        self.ai_model_hint.pack(anchor="w", padx=14, pady=(2, 8))

        ai_opts_row = ttk.Frame(ai_group)
        ai_opts_row.pack(fill=tk.X, padx=14, pady=(2, 0))
        self.force_ai_only_cb = ttk.Checkbutton(
            ai_opts_row,
            text="Pure AI mask",
            variable=self.force_ai_only_var,
            style='TCheckbutton'
        )
        self.force_ai_only_cb.pack(side=tk.LEFT)
        ToolTip(self.force_ai_only_cb, "Bypass manual color-key controls and use AI-guided refinement. Fusion and BiRefNet manage this automatically.")
        self.ai_model_var.trace_add("write", self._on_ai_model_changed)
        self._sync_force_ai_checkbox()


        self.ai_btn = ttk.Button(
            ai_group,
            text="Remove Background",
            style='Success.TButton',
            command=self.run_ai_remove
        )
        self.ai_btn.pack(fill=tk.X, padx=14, pady=(12, 8))

        refine_row = ttk.Frame(ai_group)
        refine_row.pack(fill=tk.X, padx=14, pady=(0, 12))
        
        self.refine_tool_btn = ttk.Button(
            refine_row,
            text="Select Region",
            style='Action.TButton',
            command=self.toggle_ai_refine_box_mode
        )
        self.refine_tool_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        
        self.cleanup_btn = ttk.Button(
            refine_row,
            text="Refine Selection",
            style='Action.TButton',
            state=tk.DISABLED,
            command=self.run_local_ai_cleanup
        )
        self.cleanup_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        # Collapsible drawer for advanced settings
        self.adv_header = ttk.Button(
            self.edit_tab,
            text="Advanced Color Keyer",
            style='ToolbarGrey.TButton',
            command=self.toggle_advanced_drawer
        )
        self.adv_header.pack(fill=tk.X, padx=2, pady=(2, 6))

        self.adv_drawer = ttk.Frame(self.edit_tab, style='TabContent.TFrame')
        # adv_drawer is not packed by default (collapsed)

        ctrl = ttk.LabelFrame(self.adv_drawer, text="Manual Color Key", style='Card.TLabelframe')
        ctrl.pack(fill=tk.X, pady=5)

        ttk.Label(ctrl, text="Pick a background color, tune the edge, then save the rule.", style='Muted.TLabel', wraplength=300).pack(anchor="w", padx=14, pady=(4, 4))

        color_row = ttk.Frame(ctrl)
        color_row.pack(pady=8)
        self.color_canvas = tk.Canvas(
            color_row,
            width=60,
            height=60,
            bg=self.PS1_GREY_LT,
            highlightthickness=2,
            highlightbackground=self.PS1_GREY_DK,
        )
        self.color_canvas.pack(side=tk.LEFT)
        self.color_canvas.create_rectangle(8, 8, 52, 52, fill="#000000", outline=self.PS1_GREY_DK, width=2)

        ttk.Entry(color_row, textvariable=self.hex_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(color_row, text="Pick", style='Action.TButton', command=self.choose_color).pack(side=tk.LEFT)
        ttk.Button(color_row, text="Save Rule", style='Action.TButton', command=self.add_rule).pack(side=tk.LEFT, padx=5)

        ttk.Label(ctrl, text="Tolerance:").pack(anchor="w")
        ttk.Scale(ctrl, from_=0, to=100, variable=self.tol_var).pack(fill=tk.X, pady=5)

        tol_frame = ttk.Frame(ctrl)
        tol_frame.pack()
        ttk.Label(tol_frame, text="Manual:").pack(side=tk.LEFT)
        ttk.Entry(tol_frame, textvariable=self.tol_var, width=5).pack(side=tk.LEFT)

        ttk.Label(ctrl, text="Softness (Feathering):").pack(anchor="w", pady=(5, 0))
        ttk.Scale(ctrl, from_=0, to=100, variable=self.soft_var).pack(fill=tk.X, pady=5)

        soft_frame = ttk.Frame(ctrl)
        soft_frame.pack()
        ttk.Label(soft_frame, text="Manual:").pack(side=tk.LEFT)
        ttk.Entry(soft_frame, textvariable=self.soft_var, width=5).pack(side=tk.LEFT)

        options_row = ttk.Frame(ctrl)
        options_row.pack(fill=tk.X, padx=4, pady=(5, 2))
        ttk.Checkbutton(options_row, text="Contiguous", variable=self.contiguous_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(options_row, text="Clean Holes", variable=self.clean_holes_var).pack(side=tk.LEFT)

        auto_row = ttk.Frame(ctrl)
        auto_row.pack(fill=tk.X, padx=4, pady=(2, 6))
        ttk.Checkbutton(auto_row, text="Auto-remove on click", variable=self.auto_remove_on_click).pack(side=tk.LEFT)
        ttk.Button(auto_row, text="Replace All", style='Action.TButton', command=self.replace_all_color).pack(side=tk.RIGHT)

        ttk.Separator(self.edit_tab, orient='horizontal').pack(fill=tk.X, pady=5)

        # Exact crop and resize controls. These commit into the same action
        # stack as canvas edits, so they support undo, redo, and project files.
        size_frame = ttk.LabelFrame(self.edit_tab, text="Crop & Resize", style='Card.TLabelframe')
        size_frame.pack(fill=tk.X, pady=8, padx=2)
        ttk.Label(
            size_frame,
            textvariable=self.resize_current_size_var,
            style='Eyebrow.TLabel',
        ).pack(anchor="w", padx=14, pady=(4, 2))
        ttk.Label(
            size_frame,
            text="Set an exact output size, scale proportionally, or crop by coordinates.",
            style='Muted.TLabel',
            wraplength=300,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 8))

        pixel_row = ttk.Frame(size_frame)
        pixel_row.pack(fill=tk.X, padx=14, pady=(0, 5))
        ttk.Label(pixel_row, text="Pixels").pack(side=tk.LEFT, padx=(0, 8))
        self.resize_width_entry = ttk.Entry(pixel_row, textvariable=self.resize_width_var, width=7)
        self.resize_width_entry.pack(side=tk.LEFT)
        ttk.Label(pixel_row, text="×").pack(side=tk.LEFT, padx=5)
        self.resize_height_entry = ttk.Entry(pixel_row, textvariable=self.resize_height_var, width=7)
        self.resize_height_entry.pack(side=tk.LEFT)
        ttk.Label(pixel_row, text="px", style='Muted.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        self.resize_width_entry.bind("<FocusOut>", lambda _e: self._on_resize_dimension_changed("width"))
        self.resize_height_entry.bind("<FocusOut>", lambda _e: self._on_resize_dimension_changed("height"))
        self.resize_width_entry.bind("<Return>", lambda _e: self._on_resize_dimension_changed("width"))
        self.resize_height_entry.bind("<Return>", lambda _e: self._on_resize_dimension_changed("height"))

        pixel_options = ttk.Frame(size_frame)
        pixel_options.pack(fill=tk.X, padx=14, pady=(0, 6))
        ttk.Checkbutton(
            pixel_options,
            text="Lock aspect ratio",
            variable=self.resize_lock_aspect_var,
        ).pack(side=tk.LEFT)
        ttk.Button(
            pixel_options,
            text="Apply Size",
            style='Action.TButton',
            command=self.apply_pixel_resize,
        ).pack(side=tk.RIGHT)

        percent_row = ttk.Frame(size_frame)
        percent_row.pack(fill=tk.X, padx=14, pady=(0, 6))
        ttk.Label(percent_row, text="Scale").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Spinbox(
            percent_row,
            from_=1,
            to=1000,
            increment=1,
            textvariable=self.resize_percent_var,
            width=7,
        ).pack(side=tk.LEFT)
        ttk.Label(percent_row, text="%", style='Muted.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(
            percent_row,
            text="Apply Scale",
            style='Action.TButton',
            command=self.apply_percent_resize,
        ).pack(side=tk.RIGHT)

        quality_row = ttk.Frame(size_frame)
        quality_row.pack(fill=tk.X, padx=14, pady=(0, 10))
        ttk.Label(quality_row, text="Quality").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Combobox(
            quality_row,
            textvariable=self.resize_quality_var,
            values=("Lanczos (Best)", "Bicubic", "Bilinear", "Nearest (Pixel Art)"),
            state="readonly",
            width=20,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Separator(size_frame, orient='horizontal').pack(fill=tk.X, padx=14, pady=(0, 8))
        crop_grid = ttk.Frame(size_frame)
        crop_grid.pack(fill=tk.X, padx=14, pady=(0, 6))
        for column in range(4):
            crop_grid.grid_columnconfigure(column, weight=1)
        for column, (label, variable) in enumerate((
            ("X", self.crop_x_var),
            ("Y", self.crop_y_var),
            ("W", self.crop_width_var),
            ("H", self.crop_height_var),
        )):
            field = ttk.Frame(crop_grid)
            field.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 3, 0))
            ttk.Label(field, text=label, style='Muted.TLabel').pack(anchor="w")
            ttk.Entry(field, textvariable=variable, width=6).pack(fill=tk.X)

        crop_actions = ttk.Frame(size_frame)
        crop_actions.pack(fill=tk.X, padx=14, pady=(0, 12))
        ttk.Button(
            crop_actions,
            text="Drag Crop",
            style='ToolbarGrey.TButton',
            command=self.start_crop,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(
            crop_actions,
            text="Apply Exact Crop",
            style='Action.TButton',
            command=self.apply_exact_crop,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        ttk.Separator(self.edit_tab, orient='horizontal').pack(fill=tk.X, pady=5)

        # ===== PNG -> GIF mode panel (in its own tab) =====
        self.gif_frame = ttk.LabelFrame(self.gif_tab, text="Animation", style='Card.TLabelframe')
        self.gif_frame.pack(fill=tk.X, pady=10, padx=2)

        preset_row = ttk.Frame(self.gif_frame)
        preset_row.pack(fill=tk.X, pady=4)
        ttk.Label(preset_row, text="Preset:").pack(side=tk.LEFT)
        self.gif_preset_combo = ttk.Combobox(
            preset_row,
            textvariable=self.gif_preset,
            state="readonly",
            values=["VFX", "Character"],
            width=10,
        )
        self.gif_preset_combo.pack(side=tk.LEFT, padx=6)
        self.gif_preset_combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_gif_preset(self.gif_preset.get()))

        gif_btn_row = ttk.Frame(self.gif_frame)
        gif_btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(gif_btn_row, text="Load Frames", style='Action.TButton', command=self.gif_load_frames).pack(side=tk.LEFT, padx=2)
        ttk.Button(gif_btn_row, text="Clear", style='Danger.TButton', command=self.gif_clear_frames).pack(side=tk.LEFT, padx=2)

        gif_info_row = ttk.Frame(self.gif_frame)
        gif_info_row.pack(fill=tk.X, pady=(2, 4))
        self.gif_frame_summary_label = ttk.Label(gif_info_row, text="No frames loaded")
        self.gif_frame_summary_label.pack(side=tk.LEFT)
        self.gif_current_label = ttk.Label(gif_info_row, text="Frame 0 / 0")
        self.gif_current_label.pack(side=tk.RIGHT)

        gif_nav_row = ttk.Frame(self.gif_frame)
        gif_nav_row.pack(fill=tk.X, pady=(0, 4))
        self.gif_prev_btn = ttk.Button(gif_nav_row, text="Prev Frame", style='ToolbarGrey.TButton', command=lambda: self.gif_step_frame(-1), state=tk.DISABLED)
        self.gif_prev_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.gif_next_btn = ttk.Button(gif_nav_row, text="Next Frame", style='ToolbarGrey.TButton', command=lambda: self.gif_step_frame(1), state=tk.DISABLED)
        self.gif_next_btn.pack(side=tk.LEFT)

        # Filmstrip title inside the bottom timeline
        ttk.Label(self.bottom_filmstrip_frame, text="Drag frames left/right to reorder, right-click for actions", font=('Segoe UI', 9)).pack(anchor="w", padx=12, pady=(2, 2))
        gif_list_row = ttk.Frame(self.bottom_filmstrip_frame)
        gif_list_row.pack(fill=tk.X, pady=(0, 4), padx=8)
        self.gif_filmstrip_canvas = tk.Canvas(
            gif_list_row,
            height=92,
            bg=self.PS1_GREY_LT,
            highlightthickness=1,
            highlightbackground=self.PS1_GREY_DK,
            relief="flat",
            cursor="hand2",
        )
        self.gif_filmstrip_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.gif_filmstrip_scrollbar = ttk.Scrollbar(gif_list_row, orient="horizontal", command=self.gif_filmstrip_canvas.xview)
        self.gif_filmstrip_scrollbar.pack(side=tk.TOP, fill=tk.X)
        self.gif_filmstrip_canvas.configure(xscrollcommand=self.gif_filmstrip_scrollbar.set)
        self.gif_filmstrip_canvas.bind("<Button-1>", self.on_gif_filmstrip_press)
        self.gif_filmstrip_canvas.bind("<Button-3>", self.on_gif_filmstrip_context_menu)
        self.gif_filmstrip_canvas.bind("<B1-Motion>", self.on_gif_filmstrip_drag)
        self.gif_filmstrip_canvas.bind("<ButtonRelease-1>", self.on_gif_filmstrip_release)
        self.gif_filmstrip_canvas.bind("<Configure>", lambda _e: self._render_gif_filmstrip())
        self.gif_selected_name_label = ttk.Label(self.gif_frame, text="Selected file: -", justify="left", wraplength=220)
        self.gif_selected_name_label.pack(fill=tk.X, pady=(0, 4))

        gif_opt = ttk.Frame(self.gif_frame)
        gif_opt.pack(fill=tk.X, pady=4)
        ttk.Label(gif_opt, text="Anchor:").pack(side=tk.LEFT)
        self.gif_anchor_combo = ttk.Combobox(
            gif_opt,
            textvariable=self.gif_anchor,
            state="readonly",
            values=[
                "bottom-center",
                "center",
                "top-center",
                "top-left",
                "bottom-left",
                "top-right",
                "bottom-right",
                "centroid",
                "template",
            ],
            width=14,
        )
        self.gif_anchor_combo.pack(side=tk.LEFT, padx=6)
        self.gif_anchor_combo.bind("<<ComboboxSelected>>", lambda _e: self.schedule_gif_preview_update())

        self.gif_template_btn = ttk.Button(
            gif_opt,
            text="Set Anchor Box",
            style='ToolbarGrey.TButton',
            command=self.start_gif_template_mode,
        )
        self.gif_template_btn.pack(side=tk.LEFT, padx=2)

        gif_row2 = ttk.Frame(self.gif_frame)
        gif_row2.pack(fill=tk.X, pady=4)
        ttk.Label(gif_row2, text="Duration (ms):").pack(side=tk.LEFT)
        self.gif_duration_spin = tk.Spinbox(gif_row2, from_=1, to=60000, textvariable=self.gif_duration_ms, width=6, command=self.on_gif_setting_changed)
        self.gif_duration_spin.pack(side=tk.LEFT, padx=6)
        self.gif_duration_ms.trace_add("write", lambda *_: self.on_gif_setting_changed())

        gif_row3 = ttk.Frame(self.gif_frame)
        gif_row3.pack(fill=tk.X, pady=4)
        ttk.Label(gif_row3, text="Alpha thresh:").pack(side=tk.LEFT)
        self.gif_alpha_spin = tk.Spinbox(gif_row3, from_=0, to=255, textvariable=self.gif_alpha_threshold, width=4, command=self.on_gif_setting_changed)
        self.gif_alpha_spin.pack(side=tk.LEFT, padx=6)
        ttk.Label(gif_row3, text="Padding:").pack(side=tk.LEFT)
        self.gif_padding_spin = tk.Spinbox(gif_row3, from_=0, to=4096, textvariable=self.gif_padding, width=4, command=self.on_gif_setting_changed)
        self.gif_padding_spin.pack(side=tk.LEFT, padx=6)
        self.gif_alpha_threshold.trace_add("write", lambda *_: self.on_gif_setting_changed())
        self.gif_padding.trace_add("write", lambda *_: self.on_gif_setting_changed())

        ttk.Checkbutton(self.gif_frame, text="Checker preview", variable=self.gif_preview_checker, command=self.update_preview).pack(anchor="w", pady=2)

        gif_play_row = ttk.Frame(self.gif_frame)
        gif_play_row.pack(fill=tk.X, pady=6)
        self.gif_play_btn = ttk.Button(gif_play_row, text="Play", style='Success.TButton', command=self.gif_toggle_play)
        self.gif_play_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(gif_play_row, text="Save GIF", style='Toolbar.TButton', command=self.gif_save).pack(side=tk.LEFT, padx=6)
        ttk.Button(gif_play_row, text="Export Frames", style='ToolbarGrey.TButton', command=self.gif_export_frames).pack(side=tk.LEFT, padx=2)
        self.gif_frame_format_combo = ttk.Combobox(
            gif_play_row,
            textvariable=self.gif_frame_export_format,
            values=TRANSPARENT_EXPORT_FORMATS,
            state="readonly",
            width=6,
        )
        self.gif_frame_format_combo.pack(side=tk.LEFT, padx=(4, 0))

        self.gif_scrub = ttk.Scale(self.gif_frame, from_=0, to=0, orient="horizontal", command=self.on_gif_scrub)
        self.gif_scrub.pack(fill=tk.X, pady=4)

        # Color Swap section
        swap_frame = ttk.LabelFrame(self.edit_tab, text="Color Replace", style='Card.TLabelframe')
        swap_frame.pack(fill=tk.X, pady=8, padx=2)
        ttk.Label(swap_frame, text="Replace one sampled color across the image.", style='Muted.TLabel').pack(anchor="w", padx=14, pady=(4, 6))
        swap_actions = ttk.Frame(swap_frame)
        swap_actions.pack(fill=tk.X, padx=14, pady=(0, 12))
        ttk.Button(swap_actions, text="Choose Color", style='Action.TButton', command=self.choose_swap_color_ui).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(swap_actions, text="Pick from Image", style='Action.TButton', command=self.pick_swap_color_ui).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        ttk.Separator(self.edit_tab, orient='horizontal').pack(fill=tk.X, pady=5)

        # Selection section
        sel_frame = ttk.LabelFrame(self.edit_tab, text="Protected Area", style='Card.TLabelframe')
        sel_frame.pack(fill=tk.X, pady=8, padx=2)
        ttk.Label(sel_frame, text="Shield selected pixels from compatible edits.", style='Muted.TLabel').pack(anchor="w", padx=14, pady=(4, 6))
        sel_row = ttk.Frame(sel_frame)
        sel_row.pack(fill=tk.X, padx=14, pady=(0, 12))
        ttk.Button(sel_row, text="Start Lasso", style='Action.TButton', command=self.start_lasso_mode).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(sel_row, text="Clear", style='ToolbarGrey.TButton', command=self.clear_lasso_selection).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Edge processing section
        blend_frame = ttk.LabelFrame(self.edit_tab, text="Edge Finish", style='Card.TLabelframe')
        blend_frame.pack(fill=tk.X, pady=8, padx=2)
        finish_actions = ttk.Frame(blend_frame)
        finish_actions.pack(fill=tk.X, padx=14, pady=(4, 8))
        ttk.Button(finish_actions, text="Blend Edge", style='Action.TButton', command=self.run_edge_blend).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(finish_actions, text="Anti-Alias", style='Action.TButton', command=self.run_edge_smooth).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        mode_row = ttk.Frame(blend_frame)
        mode_row.pack(pady=2, fill=tk.X)
        ttk.Radiobutton(mode_row, text="To Color", value="color", variable=self.edge_blend_mode).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(mode_row, text="To Transparent", value="transparent", variable=self.edge_blend_mode).pack(side=tk.LEFT, padx=2)

        ttk.Label(blend_frame, text="Edge Strength:").pack(anchor="w")
        ttk.Scale(blend_frame, from_=0, to=100, variable=self.blend_strength,
    					command=self.on_blend_strength_change).pack(fill=tk.X, pady=5)

        ttk.Separator(self.edit_tab, orient='horizontal').pack(fill=tk.X, pady=5)

        rf = ttk.LabelFrame(self.edit_tab, text="Edit Stack", style='Card.TLabelframe')
        rf.pack(fill=tk.BOTH, expand=True, padx=2, pady=(4, 8))
        self.rules_list = tk.Listbox(rf)
        self.rules_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        rules_btns = ttk.Frame(rf)
        rules_btns.pack(pady=5)
        ttk.Button(rules_btns, text="Remove", style='Danger.TButton', command=self.remove_rule).pack(side=tk.LEFT, padx=4)
        ttk.Button(rules_btns, text="Clear All", style='ToolbarGrey.TButton', command=self.clear_rules).pack(side=tk.LEFT, padx=4)

        # ===== SLICER TAB =====
        self._setup_slicer_tab()

        self._setup_bg_dots()
        self.canvas = tk.Canvas(self.canvas_container, bg=self.PS1_GREY_LT, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _setup_composition_tab(self):
        intro = ttk.LabelFrame(
            self.compose_tab,
            text="Layered Composition",
            style="Card.TLabelframe",
        )
        intro.pack(fill=tk.X, pady=(10, 8), padx=2)
        ttk.Label(
            intro,
            text="Arrange multiple images on one transparent canvas. Drag a selected layer to move it; drag its lower-right handle to scale.",
            style="Muted.TLabel",
            wraplength=310,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(6, 10))
        add_row = ttk.Frame(intro)
        add_row.pack(fill=tk.X, padx=14, pady=(0, 12))
        ttk.Button(
            add_row,
            text="Add Images",
            style="Success.TButton",
            command=self.composition_add_images_dialog,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(
            add_row,
            text="Paste",
            style="Action.TButton",
            command=self.paste_image_from_clipboard,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        layers_group = ttk.LabelFrame(
            self.compose_tab,
            text="Layers",
            style="Card.TLabelframe",
        )
        layers_group.pack(fill=tk.X, pady=8, padx=2)
        ttk.Label(
            layers_group,
            text="Top of this list = front of the composition.",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=14, pady=(4, 6))
        list_row = ttk.Frame(layers_group)
        list_row.pack(fill=tk.X, padx=14)
        self.composition_layer_listbox = tk.Listbox(
            list_row,
            height=5,
            exportselection=False,
            bg=self.BG_INPUT,
            fg=self.COLOR_TEXT,
            selectbackground=self.COLOR_ACCENT,
            selectforeground="#FFFFFF",
            highlightthickness=1,
            highlightbackground=self.COLOR_BORDER,
            bd=0,
        )
        self.composition_layer_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        layer_scroll = ttk.Scrollbar(
            list_row,
            orient="vertical",
            command=self.composition_layer_listbox.yview,
        )
        layer_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.composition_layer_listbox.configure(yscrollcommand=layer_scroll.set)
        self.composition_layer_listbox.bind(
            "<<ListboxSelect>>",
            self._on_composition_list_selection,
        )

        layer_actions = ttk.Frame(layers_group)
        layer_actions.pack(fill=tk.X, padx=14, pady=(8, 6))
        ttk.Button(
            layer_actions,
            text="Duplicate",
            style="ToolbarGrey.TButton",
            command=self.composition_duplicate_selected,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ttk.Button(
            layer_actions,
            text="Show / Hide",
            style="ToolbarGrey.TButton",
            command=self.composition_toggle_selected_visibility,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        ttk.Button(
            layer_actions,
            text="Delete",
            style="Danger.TButton",
            command=self.composition_delete_selected,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        arrange_group = ttk.LabelFrame(
            self.compose_tab,
            text="Arrange",
            style="Card.TLabelframe",
        )
        arrange_group.pack(fill=tk.X, pady=8, padx=2)
        arrange_top = ttk.Frame(arrange_group)
        arrange_top.pack(fill=tk.X, padx=14, pady=(6, 3))
        ttk.Button(
            arrange_top,
            text="Bring Forward",
            style="Action.TButton",
            command=lambda: self.composition_reorder_selected("forward"),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ttk.Button(
            arrange_top,
            text="Bring to Front",
            style="Action.TButton",
            command=lambda: self.composition_reorder_selected("front"),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
        arrange_bottom = ttk.Frame(arrange_group)
        arrange_bottom.pack(fill=tk.X, padx=14, pady=(3, 10))
        ttk.Button(
            arrange_bottom,
            text="Send Backward",
            style="ToolbarGrey.TButton",
            command=lambda: self.composition_reorder_selected("backward"),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ttk.Button(
            arrange_bottom,
            text="Send to Back",
            style="ToolbarGrey.TButton",
            command=lambda: self.composition_reorder_selected("back"),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        transform_group = ttk.LabelFrame(
            self.compose_tab,
            text="Transform Selected Layer",
            style="Card.TLabelframe",
        )
        transform_group.pack(fill=tk.X, pady=8, padx=2)
        position_row = ttk.Frame(transform_group)
        position_row.pack(fill=tk.X, padx=14, pady=(6, 4))
        ttk.Label(position_row, text="Position  X").pack(side=tk.LEFT)
        self.composition_x_spin = ttk.Spinbox(
            position_row,
            from_=-100000,
            to=100000,
            textvariable=self.composition_x_var,
            width=7,
        )
        self.composition_x_spin.pack(side=tk.LEFT, padx=(4, 10))
        ttk.Label(position_row, text="Y").pack(side=tk.LEFT)
        self.composition_y_spin = ttk.Spinbox(
            position_row,
            from_=-100000,
            to=100000,
            textvariable=self.composition_y_var,
            width=7,
        )
        self.composition_y_spin.pack(side=tk.LEFT, padx=(4, 10))

        scale_row = ttk.Frame(transform_group)
        scale_row.pack(fill=tk.X, padx=14, pady=4)
        ttk.Label(scale_row, text="Scale", width=10).pack(side=tk.LEFT)
        self.composition_scale_slider = ttk.Scale(
            scale_row,
            from_=2,
            to=400,
            variable=self.composition_scale_var,
            command=self._on_composition_adjustment_live,
        )
        self.composition_scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.composition_scale_spin = ttk.Spinbox(
            scale_row,
            from_=2,
            to=2000,
            increment=1,
            textvariable=self.composition_scale_var,
            width=6,
        )
        self.composition_scale_spin.pack(side=tk.LEFT)
        ttk.Label(scale_row, text="%").pack(side=tk.LEFT, padx=(3, 0))

        rotation_row = ttk.Frame(transform_group)
        rotation_row.pack(fill=tk.X, padx=14, pady=4)
        ttk.Label(rotation_row, text="Rotation", width=10).pack(side=tk.LEFT)
        ttk.Button(
            rotation_row,
            text="↶ 90°",
            style="ToolbarGrey.TButton",
            command=lambda: self.composition_rotate_selected(-90),
        ).pack(side=tk.LEFT, padx=(0, 4))
        self.composition_rotation_spin = ttk.Spinbox(
            rotation_row,
            from_=-3600,
            to=3600,
            increment=1,
            textvariable=self.composition_rotation_var,
            width=7,
        )
        self.composition_rotation_spin.pack(side=tk.LEFT, padx=4)
        ttk.Label(rotation_row, text="°").pack(side=tk.LEFT)
        ttk.Button(
            rotation_row,
            text="90° ↷",
            style="ToolbarGrey.TButton",
            command=lambda: self.composition_rotate_selected(90),
        ).pack(side=tk.LEFT, padx=(4, 0))

        for widget in (
            self.composition_x_spin,
            self.composition_y_spin,
            self.composition_scale_spin,
            self.composition_rotation_spin,
        ):
            widget.bind("<Return>", self.composition_apply_all_controls)
            widget.bind("<FocusOut>", self.composition_apply_all_controls)

        transform_actions = ttk.Frame(transform_group)
        transform_actions.pack(fill=tk.X, padx=14, pady=(4, 10))
        ttk.Button(
            transform_actions,
            text="Apply",
            style="Success.TButton",
            command=self.composition_apply_all_controls,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ttk.Button(
            transform_actions,
            text="Fit to Canvas",
            style="Action.TButton",
            command=self.composition_fit_selected,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        ttk.Button(
            transform_actions,
            text="Reset",
            style="ToolbarGrey.TButton",
            command=self.composition_reset_selected,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        flip_row = ttk.Frame(transform_group)
        flip_row.pack(fill=tk.X, padx=14, pady=(0, 10))
        ttk.Button(
            flip_row,
            text="Flip Horizontal",
            style="ToolbarGrey.TButton",
            command=lambda: self.composition_flip_selected("horizontal"),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ttk.Button(
            flip_row,
            text="Flip Vertical",
            style="ToolbarGrey.TButton",
            command=lambda: self.composition_flip_selected("vertical"),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        appearance_group = ttk.LabelFrame(
            self.compose_tab,
            text="Selected Layer Appearance",
            style="Card.TLabelframe",
        )
        appearance_group.pack(fill=tk.X, pady=8, padx=2)
        ttk.Label(
            appearance_group,
            text="Adjust only the selected image; other layers remain unchanged.",
            style="Muted.TLabel",
            wraplength=310,
        ).pack(anchor="w", padx=14, pady=(5, 6))

        self.composition_adjustment_sliders = [self.composition_scale_slider]

        def add_adjustment_slider(parent, label, variable, minimum, maximum, suffix="%"):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, padx=14, pady=3)
            ttk.Label(row, text=label, width=10).pack(side=tk.LEFT)
            slider = ttk.Scale(
                row,
                from_=minimum,
                to=maximum,
                variable=variable,
                command=self._on_composition_adjustment_live,
            )
            slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
            value_label = ttk.Label(row, textvariable=variable, width=5, anchor="e")
            value_label.pack(side=tk.LEFT)
            if suffix:
                ttk.Label(row, text=suffix, width=2).pack(side=tk.LEFT)
            self.composition_adjustment_sliders.append(slider)
            return slider

        add_adjustment_slider(
            appearance_group,
            "Opacity",
            self.composition_opacity_var,
            0,
            100,
        )
        add_adjustment_slider(
            appearance_group,
            "Brightness",
            self.composition_brightness_var,
            0,
            200,
        )
        add_adjustment_slider(
            appearance_group,
            "Contrast",
            self.composition_contrast_var,
            0,
            200,
        )
        add_adjustment_slider(
            appearance_group,
            "Saturation",
            self.composition_saturation_var,
            0,
            200,
        )
        add_adjustment_slider(
            appearance_group,
            "Blur",
            self.composition_blur_var,
            0,
            20,
            "px",
        )
        ttk.Button(
            appearance_group,
            text="Reset Appearance",
            style="ToolbarGrey.TButton",
            command=self.composition_reset_appearance,
        ).pack(fill=tk.X, padx=14, pady=(7, 10))

        shadow_group = ttk.LabelFrame(
            self.compose_tab,
            text="Drop Shadow",
            style="Card.TLabelframe",
        )
        shadow_group.pack(fill=tk.X, pady=8, padx=2)
        ttk.Checkbutton(
            shadow_group,
            text="Enable shadow",
            variable=self.composition_shadow_enabled_var,
            command=self.composition_apply_all_controls,
        ).pack(anchor="w", padx=14, pady=(6, 4))
        add_adjustment_slider(
            shadow_group,
            "Opacity",
            self.composition_shadow_opacity_var,
            0,
            100,
        )
        add_adjustment_slider(
            shadow_group,
            "Softness",
            self.composition_shadow_blur_var,
            0,
            50,
            "px",
        )
        shadow_offset_row = ttk.Frame(shadow_group)
        shadow_offset_row.pack(fill=tk.X, padx=14, pady=(4, 10))
        ttk.Label(shadow_offset_row, text="Offset  X").pack(side=tk.LEFT)
        self.composition_shadow_x_spin = ttk.Spinbox(
            shadow_offset_row,
            from_=-500,
            to=500,
            textvariable=self.composition_shadow_x_var,
            width=7,
        )
        self.composition_shadow_x_spin.pack(side=tk.LEFT, padx=(4, 10))
        ttk.Label(shadow_offset_row, text="Y").pack(side=tk.LEFT)
        self.composition_shadow_y_spin = ttk.Spinbox(
            shadow_offset_row,
            from_=-500,
            to=500,
            textvariable=self.composition_shadow_y_var,
            width=7,
        )
        self.composition_shadow_y_spin.pack(side=tk.LEFT, padx=(4, 0))
        for widget in (
            self.composition_shadow_x_spin,
            self.composition_shadow_y_spin,
        ):
            widget.bind("<Return>", self.composition_apply_all_controls)
            widget.bind("<FocusOut>", self.composition_apply_all_controls)

        for slider in self.composition_adjustment_sliders:
            slider.bind("<ButtonPress-1>", self._composition_begin_control_change, add="+")
            slider.bind("<ButtonRelease-1>", self._composition_finish_control_change, add="+")

        ttk.Button(
            self.compose_tab,
            text="Flatten Copy to Edit",
            style="Success.TButton",
            command=self.composition_flatten_to_editor,
        ).pack(fill=tk.X, padx=2, pady=(8, 12))

    def _draw_header_bands(self):
        if not hasattr(self, "header_canvas") or self.header_canvas is None:
            return

        w = max(1, int(self.header_canvas.winfo_width()))
        h = max(1, int(self.header_canvas.winfo_height()))

        self.header_canvas.delete("bg_img")

        scale = 2
        sw = w * scale
        sh = h * scale
        
        img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        def parse_hex(hex_str):
            hex_str = hex_str.lstrip('#')
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        
        bg_rgb = parse_hex(self.BG_MAIN)
        border_rgb = parse_hex(self.COLOR_BORDER)
        accent_rgb = parse_hex(self.COLOR_ACCENT)
        
        draw.rectangle([0, 0, sw, sh], fill=bg_rgb + (255,))
        draw.rectangle([0, sh - 2 * scale, sw, sh], fill=border_rgb + (255,))
        draw.rectangle([0, sh - 2 * scale, int(sw * 0.24), sh], fill=accent_rgb + (255,))
        
        img = img.resize((w, h), Image.Resampling.LANCZOS)
        
        self.header_bg_photo = ImageTk.PhotoImage(img)
        self.header_canvas.create_image(0, 0, image=self.header_bg_photo, anchor="nw", tags="bg_img")
        self.header_canvas.tag_lower("bg_img")

        try:
            if hasattr(self, "_toolbar_window") and self._toolbar_window is not None:
                self.header_canvas.itemconfigure(self._toolbar_window, width=max(1, w - 28))
        except Exception:
            pass

    def _apply_dark_widget_theme(self):
        # Apply the same visual language to legacy tk widgets that cannot use
        # ttk style definitions.
        try:
            if hasattr(self, "canvas") and self.canvas is not None:
                self.canvas.configure(bg=self.BG_INPUT)
        except Exception:
            pass

        # Common listboxes in the app (e.g., selection lists)
        for attr in [
            "rules_list",
        ]:
            lb = getattr(self, attr, None)
            if lb is None:
                continue
            try:
                lb.configure(
                    bg=self.BG_INPUT,
                    fg=self.COLOR_TEXT,
                    selectbackground=self.COLOR_ACCENT,
                    selectforeground="white",
                    highlightthickness=1,
                    highlightbackground=self.COLOR_BORDER,
                    relief="flat",
                )
            except Exception:
                pass

        def theme_tree(parent):
            try:
                children = parent.winfo_children()
            except Exception:
                return
            for child in children:
                try:
                    if isinstance(child, tk.Spinbox):
                        child.configure(
                            bg=self.BG_INPUT,
                            fg=self.COLOR_TEXT,
                            insertbackground=self.COLOR_TEXT,
                            buttonbackground=self.BG_ELEVATED,
                            relief="flat",
                            bd=0,
                            highlightthickness=1,
                            highlightbackground=self.COLOR_BORDER,
                            highlightcolor=self.COLOR_ACCENT,
                        )
                    elif isinstance(child, tk.Entry):
                        child.configure(
                            bg=self.BG_INPUT,
                            fg=self.COLOR_TEXT,
                            insertbackground=self.COLOR_TEXT,
                            relief="flat",
                            bd=0,
                            highlightthickness=1,
                            highlightbackground=self.COLOR_BORDER,
                            highlightcolor=self.COLOR_ACCENT,
                        )
                    elif isinstance(child, tk.Listbox):
                        child.configure(
                            bg=self.BG_INPUT,
                            fg=self.COLOR_TEXT,
                            selectbackground=self.COLOR_ACCENT,
                            selectforeground="#FFFFFF",
                            relief="flat",
                            bd=0,
                            highlightthickness=1,
                            highlightbackground=self.COLOR_BORDER,
                        )
                except Exception:
                    pass
                theme_tree(child)

        theme_tree(self.root)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Leave>", self.on_canvas_leave)
        self.canvas.bind("<Double-Button-1>", lambda e: self.toggle_zoom())
        self.canvas.bind("<Shift-Button-1>", self.on_shift_click)

        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind('<<Drop>>', self.on_drop)

        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)
        self.canvas.bind("<ButtonRelease-2>", self.end_pan)

        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        # Global Slicer Shortcuts (Ctrl/Shift + Scroll) to allow adjusting grid from anywhere
        # Pass explicit flags to avoid ambiguity with event.state
        self.root.bind_all("<Control-MouseWheel>", lambda e: self.on_mouse_wheel(e, force_ctrl=True))
        self.root.bind_all("<Shift-MouseWheel>", lambda e: self.on_mouse_wheel(e, force_shift=True))
        self.root.bind_all("<Left>", self.on_global_left_key, add="+")
        self.root.bind_all("<Right>", self.on_global_right_key, add="+")

        self.root.bind('<Control-z>', self.on_undo_shortcut)
        self.root.bind('<Control-y>', self.on_redo_shortcut)
        self.root.bind('<Control-Z>', self.on_undo_shortcut)
        self.root.bind('<Control-Y>', self.on_redo_shortcut)
        self.root.bind('<Delete>', self.on_delete_key)
        self.root.bind('<Escape>', lambda e: self.clear_lasso_selection())

    def _get_help_sections(self):
        return [
            (
                "Overview",
                f"""{APP_NAME} quick start

1. Open, paste, or drag an image into the editor.
2. Choose an AI model and click Remove Background for a fast first pass.
3. Refine the result with Select Region, the Advanced Color Keyer, lasso protection, or the cleanup tools.
4. Compare the preview with the original, then save the result as PNG, WebP, JPG, or ICO.

AI processing is local. The first use of an AI model downloads its model file, so it needs an internet connection and enough free disk space. Later uses load the cached model.

Important: a manual color-key selection is only a preview until you click Save Rule. Commit it before choosing another color or effect.

Main areas

- Edit tab: AI removal, manual color keying, brush edits, crop, lasso protection, color replacement, and edge cleanup.
- Compose tab: place multiple images on one canvas, move and scale them, and control which layers appear in front.
- PNG -> GIF tab: align and animate PNG or WebP frames, preview the result, and export a GIF or individual PNG/WebP frames.
- Slicer tab: divide a sprite sheet into named cells and export them or send them to the GIF maker.
- File menu: batch AI removal, project save/load, and image export.

Useful habits

- Start with Remove Background, then correct only the areas that need attention.
- Use Side-by-Side to compare the edited preview with the untouched original.
- Add lasso protection before applying an edit that should avoid part of the image.
- Undo and redo committed edits with Ctrl+Z and Ctrl+Y.""",
            ),
            (
                "AI Removal",
                """AI background removal

Transparentor runs the selected model on your computer. Images are not uploaded to an AI service.

Models

- Fusion · Best Overall: the default quality mode. It runs both models, uses BiRefNet for clean structure and chroma screens, and lets ISNet preserve credible glow, particles, and fine detached effects.
- BiRefNet · Clean Shapes & Chroma: the strongest single model for coherent silhouettes and saturated green, blue, or cyan screens. It runs on CPU.
- ISNet · Glow & Fine Effects: the faster single model for luminous artwork, wisps, sparkles, and small detached details. It can use DirectML acceleration when supported.

The first run asks before downloading any missing weights. ISNet is about 179 MB; BiRefNet is about 973 MB; Fusion needs both (about 1.15 GB total). The confirmation shows the cache location and progress appears in the AI status area.

Remove Background

- Load an image and select a model.
- Fusion automatically distinguishes solid chroma screens, noisy or brightness-gradient chroma screens, dark uniform artwork, neutral uniform backgrounds, and complex scenes before combining the masks.
- On a gradient green/blue screen, every model uses the screen's perimeter chromaticity to remove spill while preserving translucent glass, glow, fine tendrils, and foreground color. This targeted cleanup is separate from the older aggressive solid-screen recovery.
- Leave Pure AI Mode off with ISNet when the subject is on a fairly uniform background and you want color-distance refinement.
- Fusion and BiRefNet manage their AI-guided refinement automatically.
- Click Remove Background and wait for the status to return to ready.
- The segmented header meter reports the current preparation, model loading, inference, refinement, and finalization stages rather than looping indefinitely.
- It shows elapsed time and an approximate ETA. Estimates adapt to completed runs on this computer and are saved under the Transparentor local app-data folder.
- Tolerance and Softness influence the hybrid color-key refinement; they do not change a Pure AI mask in the same way.

Regional cleanup

- Click Select Region, then drag a box around an area that the first pass missed.
- Click Refine Selection to rerun the selected model on that region.
- Regional cleanup is added to the edit history and can be undone.

Edit drop queue

- While the Edit tab is active, drag two or more images onto the canvas to create an AI Queue filmstrip at the bottom. This does not switch to Compose.
- The first queued image appears immediately. Click Remove Background once to process the filmstrip sequentially.
- The canvas advances to the image currently being processed, and each filmstrip card changes from Queued to Processing to Done or Error.
- Completed results remain in memory. After the queue finishes, click a filmstrip card to review that image and use Save Image to export it.
- Multi-image drops become layers only when the Compose tab is already active.

Batch AI removal

- Press Ctrl+B or choose File > Batch AI Background Removal.
- Add or drag multiple images into the list.
- Choose the model, mode, tolerance, softness, filename suffix, and optional output directory.
- Choose PNG or lossless WebP output, then click Start Batch.
- The main canvas shows the image currently being processed. The batch filmstrip marks queued, processing, completed, and failed items as the queue advances.
- Closing the batch window requests cancellation after the current work stops.

Troubleshooting

- A first run that appears slow may still be downloading or loading a large model.
- BiRefNet intentionally uses CPU and can take substantially longer than ISNet.
- Closing Transparentor signals every app-owned AI worker, releases cached ONNX sessions, and then ends the Transparentor process. It does not launch or use llama-server.
- Model files are cached in the user's .u2net folder.
- Crash and provider logs may be written to %LOCALAPPDATA%\\Transparentor\\logs.""",
            ),
            (
                "Editor",
                """Editor tools and workflow

Advanced Color Keyer

- Expand Advanced Color Keyer when you need manual control.
- Click a background pixel or use Pick to choose the color to remove.
- Adjust Tolerance to widen or narrow the selected color range.
- Adjust Softness to feather the alpha transition.
- Contiguous limits removal to connected background regions; Clean Holes helps remove enclosed background remnants.
- Auto-remove on click updates the preview immediately.
- Click Save Rule to commit the current key. A preview that is not saved may be lost when you switch tools.

Resize, crop, and protection

- Eraser removes pixels with the brush.
- Replace paints with the chosen replacement color.
- Brush size is controlled from the toolbar.
- Crop & Resize accepts exact width and height in pixels, with an optional aspect-ratio lock.
- Scale resizes the current image from 0.1% to 1,000%, while Quality selects smooth photo resizing or nearest-neighbor pixel-art resizing.
- Exact Crop accepts X, Y, width, and height in pixels. Drag Crop keeps the visual canvas workflow and commits on release.
- Resize and crop operations appear in Edit Stack and support undo, redo, and project save/load.
- Lasso creates a protected region that later compatible edits avoid.
- Clear Protection removes the current lasso mask.

Color and edge cleanup

- Replace Color swaps one selected color for another.
- Run Edge Blend softens edge pixels toward a chosen color or toward transparency.
- Anti-Alias smooths the current image edges.

Comparison and saving

- Side-by-Side shows Preview on the left and Original on the right.
- Save exports the current result; PNG preserves transparency.
- Undo and Redo work on committed actions and brush edits.
- The Rules list shows committed operations. Remove deletes the selected operation; Clear All removes the list of operations.""",
            ),
            (
                "Compose",
                """Layered composition

Use Compose when several still images should exist together on the same canvas. This is separate from Batch AI Removal, which processes files one at a time.

Adding layers

- Select the Compose tab, then click Add Images, paste an image, or drag files onto the main canvas.
- Dropping multiple still images onto the ordinary Edit canvas automatically opens Compose rather than treating them as animation frames.
- The first layer establishes the composition canvas size. New layers are centered on that canvas.
- The top item in the Layers list is visually in front.

Moving, scaling, and rotating

- Click a layer in the canvas or Layers list to select it.
- Drag anywhere inside the selected layer to move it.
- Drag the lower-right selection handle to scale it while preserving its proportions.
- Drag the circular handle above the selection to rotate freely, use the 90-degree buttons, or enter an exact rotation.
- Use the visible Scale slider or enter exact X, Y, Scale, and Rotation values in Transform Selected Layer.
- Fit to Canvas scales the selected layer to fit; Reset returns it to 100% and centers it.
- Flip Horizontal and Flip Vertical mirror only the selected layer.

Layer controls

- Bring Forward and Bring to Front move a layer above others.
- Send Backward and Send to Back move it below others.
- Show / Hide toggles visibility without deleting the layer.
- Duplicate makes an independent copy; Delete removes the selected layer.
- Ctrl+Z and Ctrl+Y undo and redo composition changes.

Appearance and shadow

- Opacity controls how strongly the selected image covers layers beneath it.
- Brightness, Contrast, and Saturation adjust the selected image without changing its source pixels.
- Blur applies a soft-focus effect to the selected layer.
- Drop Shadow adds an adjustable black shadow with independent opacity, softness, and X/Y offset.
- Reset Appearance restores the selected layer's visual adjustments without changing its position or size.

Export and editing

- Save exports the visible composite as PNG, lossless WebP, JPEG, or ICO.
- ICO export creates a compatibility-oriented multi-resolution icon containing 16, 24, 32, 48, 64, 128, and 256 px frames rather than a single 16 px image.
- Save Project preserves every source layer, transform, visibility setting, and layer order.
- Flatten Copy to Edit sends the current composite to the single-image editor for background removal or pixel-level cleanup while retaining the saved composition data.""",
            ),
            (
                "GIF Maker",
                """PNG to GIF instructions

- Click Load Frames to select PNG and/or WebP frames.
- Drag frames left or right in the filmstrip to reorder them.
- Right-click a frame to delete, duplicate, rename, mirror, or omit/include it.
- Omitted frames stay in the strip but are skipped during playback and GIF export.

Alignment and playback

- VFX and Character presets provide useful starting settings.
- Choose an Anchor to align content consistently between differently sized frames.
- Template anchor mode lets you draw a common anchor box with Set Anchor Box.
- Alpha Threshold controls which pixels count as visible during alignment.
- Padding adds transparent room around the aligned output.
- Duration is the display time for each frame in milliseconds.
- Use Prev Frame and Next Frame for manual stepping.
- Use the scrub bar to jump to a frame.
- Press Play to preview the animation.
- Checker preview makes transparency easier to see.

Export

- Save GIF exports only the active, non-omitted frames.
- Export Frames writes the active, non-omitted frames as individual PNG or lossless WebP images using the format selector.
- GIF supports one transparent palette entry, so very soft alpha edges may look different from the PNG preview.
- Frames sent from the Slicer tab appear here automatically.""",
            ),
            (
                "Slicer",
                """Slicer instructions

- Load an image in the editor and switch to Slicer, or click Load Image in the Slicer tab.
- Choose a grid preset or enter rows and columns manually.
- Margins offset the grid from the sheet edges; padding accounts for space between cells.
- Enable Crop Box for extra crop controls around each cell.
- Center On Content recenters visible pixels inside each output.
- Trim Empty Space removes transparent margins using the selected threshold.
- Use Manual Boxes when the source is not a regular grid.
- Rename slices in the Slice Names list; names appear over the preview.

Export options

- Export Slices saves the current slices as separate PNG or lossless WebP files using the format selector.
- Export to GIF sends the slices directly into the PNG -> GIF tab.
- Output size can keep the cropped size or resize to a square target.

Tips

- Ctrl + Mouse Wheel changes columns while slicer mode is active.
- Shift + Mouse Wheel changes rows while slicer mode is active.
- Mouse Wheel zooms the slicer preview.
- Check the name overlays and slice boundaries before exporting a large sheet.""",
            ),
            (
                "Projects",
                """Files, projects, and recovery

Opening and exporting

- Open Image accepts PNG, WebP, JPG, JPEG, BMP, GIF, and TIFF through the file picker. Drag-and-drop and clipboard paste accept common Pillow-supported image formats.
- Save/Export writes the current edited image. PNG and lossless WebP both preserve transparency; JPEG is flattened onto white.
- Discard Current Image clears the editor and its current working state.

Transparentor projects

- Save Project creates a self-contained .tpr package containing the editor source, committed actions and AI masks, lasso protection, every composition layer and transform, slicer source/settings, and GIF frames/settings.
- A .tpr file can be moved to another folder or computer without keeping its original source files beside it.
- Projects made by older Transparentor versions remain supported; an older path-based project may ask you to locate its original image.
- Save Rule before saving a project if you want a pending manual color-key preview included.

Recovery and diagnostics

- Use Undo/Redo before discarding an unwanted committed change.
- Fatal crash logs are written to %LOCALAPPDATA%\\Transparentor\\logs when possible.
- Model-provider information may also appear in that log folder.
- Large AI model files are cached separately in the user's .u2net folder.""",
            ),
            (
                "Shortcuts",
                """Keyboard and mouse shortcuts

Global

- Ctrl + O: open/import an image file.
- Ctrl + S: save the current image.
- Ctrl + V: paste an image from the clipboard.
- Ctrl + B: open Batch AI Background Removal panel.
- Ctrl + Z: undo.
- Ctrl + Y: redo.
- F1: open this help guide.
- Escape: clear the current lasso selection.

Canvas

- Mouse Wheel: zoom the editor preview.
- Double-click: toggle zoom fit.
- Middle Mouse Button drag: pan the canvas.
- Shift + Left Click: start a lasso immediately.
- Drag one image onto Edit to open it. Drag multiple still images, or drag while Compose is active, to add movable layers.

Compose mode

- Left drag: move the selected layer.
- Drag the lower-right selection handle: scale the layer.
- Drag the circular handle above the selection: rotate the layer.
- Delete: remove the selected layer.

GIF tab

- Left Arrow: previous frame when GIF controls are active.
- Right Arrow: next frame when GIF controls are active.
- Right-click a filmstrip frame: open frame actions.
- Delete: delete selected frames.

Slicer mode

- Ctrl + Mouse Wheel: change columns.
- Shift + Mouse Wheel: change rows.
- Mouse Wheel: zoom the slicer preview.""",
            ),
        ]

    def _populate_help_tab(self, parent, text):
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)
        text_widget = tk.Text(
            container,
            wrap="word",
            bg=self.PS1_GREY_LT,
            fg=self.PS1_INK,
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10,
        )
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.insert("1.0", text)
        text_widget.configure(state="disabled")

    def open_about_window(self):
        existing = getattr(self, "about_window", None)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return

        self.about_window = tk.Toplevel(self.root)
        _apply_window_identity(self.about_window, f"About {APP_NAME}")
        _center_window(self.about_window, 560, 430)
        self.about_window.resizable(False, False)
        self.about_window.configure(bg=self.BG_MAIN)

        panel = GlassPanel(
            self.about_window,
            text=f"{APP_NAME}  {APP_VERSION}",
            bullet_color=THEME_COLOR_ACCENT,
        )
        panel.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        tk.Label(
            panel,
            text="LOCAL IMAGE LAB",
            bg=self.BG_SURFACE,
            fg=self.COLOR_ACCENT,
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", padx=18, pady=(18, 2))
        tk.Label(
            panel,
            text="Background removal, alpha cleanup,\nGIF assembly, and sprite-sheet slicing.",
            bg=self.BG_SURFACE,
            fg=self.COLOR_TEXT,
            justify="left",
            font=("Segoe UI Semibold", 16),
        ).pack(anchor="w", padx=18, pady=(0, 14))

        details = (
            "Privacy\n"
            "Images are processed locally and are never uploaded by Transparentor.\n"
            "AI model weights are downloaded only after confirmation and cached locally.\n\n"
            "Diagnostics\n"
            f"Logs: {_get_crash_log_dir()}\n"
            f"Models: {_model_cache_path(DEFAULT_AI_MODEL).parent}\n\n"
            "License\n"
            "Transparentor is released under the MIT License. Third-party components\n"
            "and model files remain subject to their respective licenses."
        )
        tk.Label(
            panel,
            text=details,
            bg=self.BG_SURFACE,
            fg=self.COLOR_MUTED,
            justify="left",
            anchor="nw",
            font=("Segoe UI", 9),
        ).pack(fill=tk.BOTH, expand=True, padx=18)

        button_row = ttk.Frame(panel)
        button_row.pack(fill=tk.X, padx=18, pady=(10, 16))

        def copy_diagnostics():
            text = (
                f"{APP_NAME} {APP_VERSION}\n"
                f"Python {sys.version.split()[0]}\n"
                f"Executable: {sys.executable}\n"
                f"Logs: {_get_crash_log_dir()}\n"
                f"Models: {_model_cache_path(DEFAULT_AI_MODEL).parent}"
            )
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Diagnostics", "Diagnostic paths copied to the clipboard.", parent=self.about_window)

        ttk.Button(button_row, text="Copy Diagnostics", command=copy_diagnostics).pack(side=tk.LEFT)
        ttk.Button(button_row, text="Close", command=self.about_window.destroy).pack(side=tk.RIGHT)

    def open_help_window(self):
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.deiconify()
            self.help_window.lift()
            self.help_window.focus_force()
            return

        self.help_window = tk.Toplevel(self.root)
        _apply_window_identity(self.help_window, f"{APP_NAME} Help")
        _center_window(self.help_window, 920, 680)
        self.help_window.minsize(760, 520)
        self.help_window.configure(bg=self.PS1_GREY)

        def _on_close():
            if self.help_window is not None:
                try:
                    self.help_window.destroy()
                except Exception:
                    pass
            self.help_window = None

        self.help_window.protocol("WM_DELETE_WINDOW", _on_close)

        outer = GlassPanel(self.help_window, text="Help Guide", bullet_color="#00E5FF")
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        intro = ttk.Label(
            outer,
            text="Start with Remove Background for a first pass. For manual color-key previews, click Save Rule before switching tools.",
            wraplength=860,
            justify="left",
        )
        intro.pack(fill=tk.X, padx=10, pady=(10, 6))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        for title, body in self._get_help_sections():
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=title)
            self._populate_help_tab(tab, body)

    def _on_mode_combo_changed(self, _event=None):
        display = self.mode_display_var.get()
        mode_value = getattr(self, "_mode_display_to_value", {}).get(display, "picker")
        self.mode_var.set(mode_value)
        self.set_mode(mode_value)

    def _on_brush_changed(self):
        try:
            self.brush_size = int(self.brush_var.get())
        except Exception:
            pass
        self._update_brush_cursor_overlay()

    def set_mode(self, m):
        self.mode = m
        if m != "replace_single":
            self.brush_replace_color = None
        self._update_replace_color_label()
        cursors = {
            'picker': 'crosshair',
            'erase': 'none',
            'replace_single': 'none',
            'crop': 'cross',
            'lasso': 'tcross',
        }
        self.canvas.config(cursor=cursors.get(m, 'arrow'))
        self._update_brush_cursor_overlay()

    def _should_show_brush_cursor(self):
        return (
            self.mode in ("erase", "replace_single")
            and self.edited_img is not None
            and self.cursor_canvas_pos is not None
            and not self.png_gif_mode.get()
            and not self.is_slicer_active
            and self._is_point_over_edited_panel(*self.cursor_canvas_pos)
        )

    def _use_side_by_side_preview(self):
        return bool(
            self.side_by_side.get()
            and self.original_img is not None
            and self.edited_img is not None
            and not self.png_gif_mode.get()
            and not self.is_slicer_active
            and not self.is_composition_active
            and not self.batch_preview_active
        )

    def _get_editor_canvas_metrics(self):
        if not self.edited_img:
            return None

        edited_w = self.edited_img.width
        edited_h = self.edited_img.height
        if edited_w <= 0 or edited_h <= 0:
            return None

        side_by_side = self._use_side_by_side_preview()
        gap = 24 if side_by_side else 0
        if side_by_side:
            original_w = max(1, self.original_img.width)
            original_h = max(1, self.original_img.height)
            source_w = edited_w + gap + original_w
            source_h = max(original_h, edited_h)
            edited_source_x = 0.0
            edited_source_y = (source_h - edited_h) / 2.0
            original_source_x = float(edited_w + gap)
            original_source_y = (source_h - original_h) / 2.0
        else:
            original_w = 0
            original_h = 0
            source_w = edited_w
            source_h = edited_h
            original_source_x = 0.0
            original_source_y = 0.0
            edited_source_x = 0.0
            edited_source_y = 0.0

        canvas_w = max(1, int(self.canvas.winfo_width()))
        canvas_h = max(1, int(self.canvas.winfo_height()))
        if self.zoom_fit:
            scale = min(canvas_w / float(source_w), canvas_h / float(source_h))
        else:
            scale = float(self.zoom_level)
        scale = max(scale, 0.0001)

        display_w = max(1, int(round(source_w * scale)))
        display_h = max(1, int(round(source_h * scale)))
        center_x = (canvas_w // 2) + self.pan_x
        center_y = (canvas_h // 2) + self.pan_y
        offset_x = center_x - (display_w / 2.0)
        offset_y = center_y - (display_h / 2.0)

        edited_display_w = max(1, int(round(edited_w * scale)))
        edited_display_h = max(1, int(round(edited_h * scale)))
        edited_canvas_x = offset_x + (edited_source_x * scale)
        edited_canvas_y = offset_y + (edited_source_y * scale)

        original_display_w = max(1, int(round(original_w * scale))) if side_by_side else 0
        original_display_h = max(1, int(round(original_h * scale))) if side_by_side else 0
        original_canvas_x = offset_x + (original_source_x * scale)
        original_canvas_y = offset_y + (original_source_y * scale)

        return {
            "side_by_side": side_by_side,
            "display_w": display_w,
            "display_h": display_h,
            "center_x": center_x,
            "center_y": center_y,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "source_w": source_w,
            "source_h": source_h,
            "original_canvas_x": original_canvas_x,
            "original_canvas_y": original_canvas_y,
            "original_display_w": original_display_w,
            "original_display_h": original_display_h,
            "edited_canvas_x": edited_canvas_x,
            "edited_canvas_y": edited_canvas_y,
            "edited_display_w": edited_display_w,
            "edited_display_h": edited_display_h,
            "edited_scale_x": edited_w / float(edited_display_w),
            "edited_scale_y": edited_h / float(edited_display_h),
            "canvas_scale": edited_display_w / float(edited_w),
            "panel_gap": gap,
        }

    def _is_point_over_edited_panel(self, cx, cy, metrics=None):
        metrics = metrics or self._get_editor_canvas_metrics()
        if metrics is None:
            return False
        if not metrics["side_by_side"]:
            return True
        return (
            metrics["edited_canvas_x"] <= cx <= metrics["edited_canvas_x"] + metrics["edited_display_w"]
            and metrics["edited_canvas_y"] <= cy <= metrics["edited_canvas_y"] + metrics["edited_display_h"]
        )

    def _image_to_canvas_scale(self):
        metrics = self._get_editor_canvas_metrics()
        if metrics is None:
            return None
        return metrics["canvas_scale"]

    def _clear_brush_cursor_overlay(self):
        if self.brush_cursor_ring_outer is not None:
            self.canvas.delete(self.brush_cursor_ring_outer)
            self.brush_cursor_ring_outer = None
        if self.brush_cursor_ring is not None:
            self.canvas.delete(self.brush_cursor_ring)
            self.brush_cursor_ring = None
        if self.brush_cursor_crosshair_h is not None:
            self.canvas.delete(self.brush_cursor_crosshair_h)
            self.brush_cursor_crosshair_h = None
        if self.brush_cursor_crosshair_v is not None:
            self.canvas.delete(self.brush_cursor_crosshair_v)
            self.brush_cursor_crosshair_v = None
        if self.brush_cursor_label_shadow is not None:
            self.canvas.delete(self.brush_cursor_label_shadow)
            self.brush_cursor_label_shadow = None
        if self.brush_cursor_label is not None:
            self.canvas.delete(self.brush_cursor_label)
            self.brush_cursor_label = None

    def _invalidate_brush_cursor_overlay_refs(self):
        self.brush_cursor_ring_outer = None
        self.brush_cursor_ring = None
        self.brush_cursor_crosshair_h = None
        self.brush_cursor_crosshair_v = None
        self.brush_cursor_label_shadow = None
        self.brush_cursor_label = None

    def _invalidate_canvas_image_item_ref(self):
        self.canvas_image_item = None

    def _invalidate_live_brush_preview_cache(self):
        self.live_brush_preview_img = None
        self.live_brush_preview_key = None
        self.live_brush_preview_scale = None

    def _show_canvas_photo(self, photo, center_x, center_y):
        if self.canvas_image_item is None:
            self.canvas_image_item = self.canvas.create_image(center_x, center_y, image=photo, anchor="center")
        else:
            self.canvas.coords(self.canvas_image_item, center_x, center_y)
            self.canvas.itemconfig(self.canvas_image_item, image=photo, state="normal")
        self.canvas.tag_lower(self.canvas_image_item)

    def _set_main_canvas_photo(self, img, reuse_existing=False):
        if reuse_existing and self.photo is not None and self.photo_size == img.size:
            try:
                self.photo.paste(img)
                return
            except Exception:
                pass
        self.photo = ImageTk.PhotoImage(img)
        self.photo_size = img.size

    def _get_brush_cursor_colors(self, cx, cy, image_pos=None):
        if not self.edited_img:
            return ("#000000", "#ffffff")
        try:
            if image_pos is None:
                ix, iy = self.canvas_to_image(cx, cy)
            else:
                ix, iy = image_pos
            ix = int(ix)
            iy = int(iy)
            if 0 <= ix < self.edited_img.width and 0 <= iy < self.edited_img.height:
                r, g, b, a = self.edited_img.getpixel((ix, iy))
                if a < 32:
                    brightness = 255
                else:
                    brightness = (0.299 * r) + (0.587 * g) + (0.114 * b)
                if brightness >= 140:
                    return ("#000000", "#ffffff")
                    # Use neon green accent and dark contrast background
                return (THEME_COLOR_ACCENT, "#002005")
        except Exception:
            pass
        return ("#000000", "#ffffff")

    def _update_brush_cursor_overlay(self):
        if not hasattr(self, "canvas"):
            return
        if not self._should_show_brush_cursor():
            self._clear_brush_cursor_overlay()
            return

        metrics = self._get_editor_canvas_metrics()
        if metrics is None:
            self._clear_brush_cursor_overlay()
            return

        cx, cy = self.cursor_canvas_pos
        scale = metrics["canvas_scale"]
        radius = max(1, int(round(max(1, self.brush_size) * scale)))
        x0 = cx - radius
        y0 = cy - radius
        x1 = cx + radius
        y1 = cy + radius
        image_x = (cx - metrics["edited_canvas_x"]) * metrics["edited_scale_x"]
        image_y = (cy - metrics["edited_canvas_y"]) * metrics["edited_scale_y"]
        primary_color, secondary_color = self._get_brush_cursor_colors(cx, cy, (image_x, image_y))

        if self.brush_cursor_ring_outer is None:
            self.brush_cursor_ring_outer = self.canvas.create_oval(
                x0,
                y0,
                x1,
                y1,
                outline=secondary_color,
                width=5,
            )
        else:
            self.canvas.coords(self.brush_cursor_ring_outer, x0, y0, x1, y1)
            self.canvas.itemconfig(self.brush_cursor_ring_outer, outline=secondary_color, state="normal")

        if self.brush_cursor_ring is None:
            self.brush_cursor_ring = self.canvas.create_oval(
                x0,
                y0,
                x1,
                y1,
                outline=primary_color,
                width=3,
            )
        else:
            self.canvas.coords(self.brush_cursor_ring, x0, y0, x1, y1)
            self.canvas.itemconfig(self.brush_cursor_ring, outline=primary_color, state="normal")

        self.canvas.tag_raise(self.brush_cursor_ring_outer)
        self.canvas.tag_raise(self.brush_cursor_ring)

    def _request_live_preview_update(self):
        if self.live_preview_after_id is not None:
            return
        self.live_preview_after_id = self.root.after(16, self._flush_live_preview_update)

    def _flush_live_preview_update(self):
        if self.live_preview_after_id is not None:
            try:
                self.root.after_cancel(self.live_preview_after_id)
            except Exception:
                pass
            self.live_preview_after_id = None
        self.update_preview()

    def _is_live_brushing(self):
        return self.active_brush_action is not None and self.mode in ("erase", "replace_single")

    def _get_editor_preview_resample(self):
        if self._is_live_brushing():
            if self.zoom_fit:
                return Image.Resampling.BILINEAR
            return Image.Resampling.NEAREST if self.zoom_level >= 1.0 else Image.Resampling.BILINEAR
        return Image.Resampling.LANCZOS

    def on_canvas_motion(self, e):
        self.cursor_canvas_pos = (e.x, e.y)
        if not self.edited_img and not self.png_gif_mode.get() and not self.is_slicer_active:
            box = getattr(self, "_welcome_open_box", None)
            over_button = bool(
                box is not None
                and box[0] <= e.x <= box[2]
                and box[1] <= e.y <= box[3]
            )
            self.canvas.config(cursor="hand2" if over_button else "arrow")
            return
        self._update_brush_cursor_overlay()

    def on_canvas_leave(self, _event=None):
        self.cursor_canvas_pos = None
        if not self.edited_img:
            self.canvas.config(cursor="arrow")
        self._clear_brush_cursor_overlay()

    def _update_replace_color_label(self):
        if self.mode != "replace_single":
            self.replace_color_var.set("")
            if hasattr(self, "replace_color_swatch"):
                self.replace_color_swatch.itemconfig(self.replace_color_swatch_rect, fill=self.PS1_GREY_DK)
            if hasattr(self, "replace_color_clear_btn"):
                self.replace_color_clear_btn.state(["disabled"])
            return
        if self.brush_replace_color is None:
            self.replace_color_var.set("Replace: pick color")
            if hasattr(self, "replace_color_swatch"):
                self.replace_color_swatch.itemconfig(self.replace_color_swatch_rect, fill=self.PS1_GREY_DK)
            if hasattr(self, "replace_color_clear_btn"):
                self.replace_color_clear_btn.state(["disabled"])
            return
        r, g, b = self.brush_replace_color
        self.replace_color_var.set(f"Replace: #{r:02x}{g:02x}{b:02x}")
        if hasattr(self, "replace_color_swatch"):
            self.replace_color_swatch.itemconfig(self.replace_color_swatch_rect, fill=f"#{r:02x}{g:02x}{b:02x}")
        if hasattr(self, "replace_color_clear_btn"):
            self.replace_color_clear_btn.state(["!disabled"])

    def _clear_replace_color(self):
        self.brush_replace_color = None
        self._update_replace_color_label()

    def _on_left_scroll(self, first, last):
        try:
            self._left_scroll_range = (float(first), float(last))
        except Exception:
            self._left_scroll_range = (0.0, 1.0)
        self._update_left_scrollbar()

    def _update_left_scrollbar(self):
        if not hasattr(self, "left_scrollbar") or self.left_scrollbar is None:
            return
        h = max(1, int(self.left_scrollbar.winfo_height()))
        track_top = 2
        track_bottom = h - 2
        track_len = max(1, track_bottom - track_top)

        try:
            first, last = self.left_scroll_canvas.yview()
        except Exception:
            first, last = self._left_scroll_range

        thumb_top = int(track_top + (track_len * first))
        thumb_bottom = int(track_top + (track_len * last))

        min_thumb = 24
        if thumb_bottom - thumb_top < min_thumb:
            thumb_bottom = min(track_bottom, thumb_top + min_thumb)

        self.left_scrollbar.delete("thumb")
        self.left_scrollbar.create_rectangle(
            3,
            thumb_top,
            int(self.left_scrollbar.winfo_width()) - 3,
            thumb_bottom,
            fill=self.PS1_GREY_DK,
            outline=self.PS1_GREY_DK,
            tags="thumb",
        )

    def _on_left_scroll_click(self, event):
        h = max(1, int(self.left_scrollbar.winfo_height()))
        track_top = 2
        track_bottom = h - 2
        track_len = max(1, track_bottom - track_top)

        try:
            first, last = self.left_scroll_canvas.yview()
        except Exception:
            first, last = (0.0, 1.0)

        thumb_top = track_top + (track_len * first)
        thumb_bottom = track_top + (track_len * last)

        if thumb_top <= event.y <= thumb_bottom:
            self._left_scroll_dragging = True
            self._left_scroll_drag_offset = event.y - thumb_top
            return

        click_frac = max(0.0, min(1.0, (event.y - track_top) / float(track_len)))
        self.left_scroll_canvas.yview_moveto(click_frac)

    def _on_left_scroll_drag(self, event):
        if not self._left_scroll_dragging:
            return
        h = max(1, int(self.left_scrollbar.winfo_height()))
        track_top = 2
        track_bottom = h - 2
        track_len = max(1, track_bottom - track_top)

        new_top = event.y - self._left_scroll_drag_offset
        new_top = max(track_top, min(track_bottom, new_top))
        frac = (new_top - track_top) / float(track_len)
        self.left_scroll_canvas.yview_moveto(frac)

    def _on_left_scroll_release(self, _event):
        self._left_scroll_dragging = False

    def start_crop(self):
        self.set_mode('crop')

    def _sync_crop_resize_controls(self, reset_crop=True):
        if not hasattr(self, "resize_current_size_var"):
            return
        self._crop_resize_syncing = True
        try:
            if self.edited_img is None:
                self.resize_current_size_var.set("No image loaded")
                self.resize_width_var.set(0)
                self.resize_height_var.set(0)
                if reset_crop:
                    self.crop_x_var.set(0)
                    self.crop_y_var.set(0)
                    self.crop_width_var.set(0)
                    self.crop_height_var.set(0)
                return

            width, height = self.edited_img.size
            self.resize_current_size_var.set(f"CURRENT  •  {width:,} × {height:,} PX")
            self.resize_width_var.set(width)
            self.resize_height_var.set(height)
            if reset_crop:
                self.crop_x_var.set(0)
                self.crop_y_var.set(0)
                self.crop_width_var.set(width)
                self.crop_height_var.set(height)
        finally:
            self._crop_resize_syncing = False

    def _on_resize_dimension_changed(self, changed_dimension):
        if self._crop_resize_syncing or not self.resize_lock_aspect_var.get() or self.edited_img is None:
            return
        current_width, current_height = self.edited_img.size
        if current_width <= 0 or current_height <= 0:
            return
        try:
            if changed_dimension == "width":
                width = int(self.resize_width_var.get())
                if width <= 0:
                    return
                height = max(1, int(round(width * current_height / current_width)))
                self.resize_height_var.set(height)
            else:
                height = int(self.resize_height_var.get())
                if height <= 0:
                    return
                width = max(1, int(round(height * current_width / current_height)))
                self.resize_width_var.set(width)
        except (TypeError, ValueError, tk.TclError):
            return

    def _resize_resample_name(self):
        return {
            "Lanczos (Best)": "lanczos",
            "Bicubic": "bicubic",
            "Bilinear": "bilinear",
            "Nearest (Pixel Art)": "nearest",
        }.get(self.resize_quality_var.get(), "lanczos")

    @staticmethod
    def _resize_resample_filter(name):
        return {
            "nearest": Image.Resampling.NEAREST,
            "bilinear": Image.Resampling.BILINEAR,
            "bicubic": Image.Resampling.BICUBIC,
            "lanczos": Image.Resampling.LANCZOS,
        }.get(str(name).lower(), Image.Resampling.LANCZOS)

    def _validate_resize_dimensions(self, width, height):
        if width <= 0 or height <= 0:
            messagebox.showwarning("Invalid Size", "Width and height must both be greater than zero.")
            return False
        if width > 32768 or height > 32768 or width * height > 268_000_000:
            messagebox.showwarning(
                "Image Too Large",
                "That size would require too much memory. Keep each side at or below "
                "32,768 pixels and the total below 268 million pixels.",
            )
            return False
        return True

    def _commit_resize(self, width, height, description):
        if self.edited_img is None:
            messagebox.showinfo("Resize Image", "Open an image before resizing.")
            return False
        width, height = int(width), int(height)
        if not self._validate_resize_dimensions(width, height):
            return False
        if (width, height) == self.edited_img.size:
            self._sync_crop_resize_controls()
            return False

        quality = self._resize_resample_name()
        desc = f"{description} to {width} × {height} px"
        self.actions.append({
            "type": "resize",
            "width": width,
            "height": height,
            "resample": quality,
            "desc": desc,
        })
        self.rules_list.insert(tk.END, desc)
        self.clear_lasso_selection()
        self.apply_actions()
        self._clear_redo_stack()
        self.update_preview()
        return True

    def apply_pixel_resize(self):
        if self.edited_img is None:
            messagebox.showinfo("Resize Image", "Open an image before resizing.")
            return
        try:
            width = int(self.resize_width_var.get())
            height = int(self.resize_height_var.get())
        except (TypeError, ValueError, tk.TclError):
            messagebox.showwarning("Invalid Size", "Enter whole-pixel width and height values.")
            return
        self._commit_resize(width, height, "Resize")

    def apply_percent_resize(self):
        if self.edited_img is None:
            messagebox.showinfo("Scale Image", "Open an image before scaling.")
            return
        try:
            percent = float(self.resize_percent_var.get())
        except (TypeError, ValueError, tk.TclError):
            messagebox.showwarning("Invalid Scale", "Enter a percentage between 0.1 and 1,000.")
            return
        if not 0.1 <= percent <= 1000.0:
            messagebox.showwarning("Invalid Scale", "Enter a percentage between 0.1 and 1,000.")
            return
        width = max(1, int(round(self.edited_img.width * percent / 100.0)))
        height = max(1, int(round(self.edited_img.height * percent / 100.0)))
        self._commit_resize(width, height, f"Scale {percent:g}%")

    def apply_exact_crop(self):
        if self.edited_img is None:
            messagebox.showinfo("Crop Image", "Open an image before cropping.")
            return
        try:
            x = int(self.crop_x_var.get())
            y = int(self.crop_y_var.get())
            width = int(self.crop_width_var.get())
            height = int(self.crop_height_var.get())
        except (TypeError, ValueError, tk.TclError):
            messagebox.showwarning("Invalid Crop", "Enter whole-pixel X, Y, width, and height values.")
            return
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            messagebox.showwarning(
                "Invalid Crop",
                "X and Y cannot be negative, and width and height must be greater than zero.",
            )
            return
        if x + width > self.edited_img.width or y + height > self.edited_img.height:
            messagebox.showwarning(
                "Crop Outside Image",
                f"The crop must fit inside the current {self.edited_img.width} × "
                f"{self.edited_img.height} px image.",
            )
            return
        if x == 0 and y == 0 and width == self.edited_img.width and height == self.edited_img.height:
            return

        box = (x, y, x + width, y + height)
        desc = f"Crop {width} × {height} px at {x}, {y}"
        self.actions.append({"type": "crop", "box": box, "desc": desc})
        self.rules_list.insert(tk.END, desc)
        self.clear_lasso_selection()
        self.apply_actions()
        self._clear_redo_stack()
        self.update_preview()

    def start_lasso_mode(self):
        self.set_mode('lasso')
        self.lasso_mode = True
        self.lasso_points = []
        if self.lasso_line is not None:
            self.canvas.delete(self.lasso_line)
            self.lasso_line = None

    def _create_menu_bar(self):
        self.menu_frame = tk.Frame(self.root, bg=self.BG_MAIN, height=30)
        self.menu_frame.pack(side=tk.TOP, fill=tk.X, before=self.header_canvas)
        self.menu_frame.pack_propagate(False)

        # Style options for menu buttons
        btn_opts = {
            "bg": self.BG_MAIN,
            "fg": self.COLOR_MUTED,
            "activebackground": self.BG_ELEVATED,
            "activeforeground": self.COLOR_TEXT,
            "relief": tk.FLAT,
            "bd": 0,
            "font": ('Segoe UI', 9),
            "padx": 12,
            "pady": 4,
            "cursor": "hand2",
        }

        # Submenu options for dropdown menus
        menu_opts = {
            "tearoff": 0,
            "bg": self.BG_SURFACE,
            "fg": self.COLOR_TEXT,
            "activebackground": self.COLOR_ACCENT,
            "activeforeground": "#FFFFFF",
            "bd": 1,
            "relief": tk.SOLID,
            "font": ('Segoe UI', 9),
        }

        # File Button & Dropdown Menu
        file_btn = tk.Menubutton(self.menu_frame, text="File", **btn_opts)
        file_btn.pack(side=tk.LEFT)
        file_menu = tk.Menu(file_btn, **menu_opts)
        file_btn.config(menu=file_menu)

        file_menu.add_command(label="Open Image... (Ctrl+O)", command=self.open_image)
        file_menu.add_command(label="Paste Image from Clipboard (Ctrl+V)", command=self.paste_image_from_clipboard)
        file_menu.add_command(label="Discard Current Image", command=self.discard_image)
        file_menu.add_command(label="Batch AI Background Removal... (Ctrl+B)", command=self.open_batch_bg_removal_window)
        file_menu.add_separator()
        file_menu.add_command(label="Save/Export Image... (Ctrl+S)", command=self.save_image)
        file_menu.add_separator()
        file_menu.add_command(label="Load Project...", command=self.load_project)
        file_menu.add_command(label="Save Project...", command=self.save_project)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_app_closing)

        # Edit Button & Dropdown Menu
        edit_btn = tk.Menubutton(self.menu_frame, text="Edit", **btn_opts)
        edit_btn.pack(side=tk.LEFT)
        edit_menu = tk.Menu(edit_btn, **menu_opts)
        edit_btn.config(menu=edit_menu)

        edit_menu.add_command(label="Undo (Ctrl+Z)", command=self.undo)
        edit_menu.add_command(label="Redo (Ctrl+Y)", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Crop Tool", command=self.start_crop)
        edit_menu.add_command(label="Lasso Tool", command=self.start_lasso_mode)
        edit_menu.add_command(label="Clear Lasso Selection (Escape)", command=self.clear_lasso_selection)

        # Help Button & Dropdown Menu
        help_btn = tk.Menubutton(self.menu_frame, text="Help", **btn_opts)
        help_btn.pack(side=tk.LEFT)
        help_menu = tk.Menu(help_btn, **menu_opts)
        help_btn.config(menu=help_menu)

        help_menu.add_command(label="Open Help & Shortcuts (F1)", command=self.open_help_window)
        help_menu.add_separator()
        help_menu.add_command(label=f"About {APP_NAME}", command=self.open_about_window)

    def discard_image(self):
        if not self._confirm_unsaved_changes("discarding the current work"):
            return

        # Clear all image-related attributes
        self.original_img = None
        self.edited_img = None
        self.editor_image_path = None
        self.actions = []
        self.redo_actions = []
        self.history = []
        self.future_history = []
        self.rules.clear()
        self._clear_composition_state()
        self._last_applied_action_count = 0
        self.project_dirty = False
        self.current_project_path = None

        # Clear rules listbox UI
        try:
            self.rules_list.delete(0, tk.END)
        except Exception:
            pass

        # Clean up any other states
        self.clear_lasso_selection()
        self.brush_replace_color = None
        self._update_replace_color_label()
        self.active_brush_action = None
        self.active_brush_rule_index = None
        self.last_brush_point = None
        self._sync_crop_resize_controls()

        # Reset slicer image state if applicable
        if hasattr(self, "slicer_image"):
            self.slicer_image = None
            self.slicer_image_path = None
            self.slicer_info_label.config(text="No image loaded")
            self.slicer_update_preview()

        # Stop playback if playing and exit GIF mode
        self.exit_png_gif_mode()

        # Clear the canvas and redraw welcome message
        self.canvas.delete("all")
        self.update_preview()

    def open_image(self):
        if getattr(self, "is_composition_active", False):
            self.composition_add_images_dialog()
            return
        p = filedialog.askopenfilename(
            title="Open Image",
            filetypes=IMAGE_OPEN_FILETYPES,
        )
        if p:
            self.open_image_from_path(p)

    def _confirm_unsaved_changes(self, action_description):
        if not getattr(self, "project_dirty", False):
            return True
        response = messagebox.askyesnocancel(
            "Unsaved Changes",
            f"You have unsaved project changes. Save them before {action_description}?",
            icon="warning",
        )
        if response is None:
            return False
        if response is True:
            return bool(self.save_project())
        return True

    def open_image_from_pil(
        self,
        img: Image.Image,
        path_info=None,
        confirm_replace=True,
        preserve_composition=False,
        preserve_edit_queue=False,
    ):
        if (
            not preserve_edit_queue
            and getattr(self, "edit_queue_running", False)
        ):
            messagebox.showinfo(
                "AI Queue Running",
                "Wait for the current Edit queue to finish before replacing it.",
            )
            return False
        if confirm_replace and not self._confirm_unsaved_changes("opening another image"):
            return False
        if not preserve_edit_queue:
            self._clear_edit_queue_state()
        if not preserve_composition:
            self._clear_composition_state()
        # Update main editor state
        self.editor_image_path = path_info
        
        # Leaving GIF mode when opening a single image
        self.exit_png_gif_mode()
        self.clear_lasso_selection()
        self.brush_replace_color = None
        self._update_replace_color_label()
        self.active_brush_action = None
        self.active_brush_rule_index = None
        self.last_brush_point = None
        self.original_img = img.convert("RGBA")
        self.auto_pick_background_color(self.original_img)
        self.edited_img = self.original_img.copy()
        self.actions = []
        self.redo_actions = []
        self.history = []
        self.future_history = []
        self.rules.clear()
        self._last_applied_action_count = 0
        try:
            self.rules_list.delete(0, tk.END)
        except Exception:
            pass
        if self.edited_img is not None:
            self.history.append(self.edited_img.copy())
        self._sync_crop_resize_controls()

        # If we are currently in the Slicer tab, immediately sync the new image to it.
        if self.is_slicer_active:
            self._sync_editor_to_slicer()
        
        self.update_preview()
        self.project_dirty = False
        self.current_project_path = None
        return True

    def open_image_from_path(
        self,
        p,
        confirm_replace=True,
        preserve_composition=False,
        preserve_edit_queue=False,
    ):
        try:
            with Image.open(p) as image:
                return self.open_image_from_pil(
                    image.copy(),
                    path_info=p,
                    confirm_replace=confirm_replace,
                    preserve_composition=preserve_composition,
                    preserve_edit_queue=preserve_edit_queue,
                )
        except Exception as e:
            messagebox.showerror("Open Failed", f"Could not open image:\n{e}")
            return False

    def _on_paste_shortcut(self, event=None):
        # If a text entry has focus, let normal paste work.
        try:
            w = self.root.focus_get()
            cls = w.winfo_class() if w is not None else ""
            if cls in ("Entry", "Text", "TEntry", "TCombobox", "Spinbox"):
                return None
        except Exception:
            pass
        self.paste_image_from_clipboard()
        return "break"

    def paste_image_from_clipboard(self):
        if ImageGrab is None:
            messagebox.showwarning(
                "Clipboard Unavailable",
                "Clipboard image paste requires Pillow's ImageGrab on this platform.",
            )
            return

        try:
            data = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("Paste Failed", f"Could not read clipboard:\n{e}")
            return

        if data is None:
            messagebox.showinfo("Paste", "Clipboard does not contain an image.")
            return

        # ImageGrab can return an Image or a list of file paths.
        if isinstance(data, Image.Image):
            if getattr(self, "is_composition_active", False):
                self.composition_add_pil_image(data, name="Clipboard image")
            else:
                self.open_image_from_pil(data)
            return

        if isinstance(data, (list, tuple)):
            valid_paths = []
            for p in data:
                try:
                    if not isinstance(p, str):
                        continue
                    ext = os.path.splitext(p)[1].lower()
                    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp") and os.path.exists(p):
                        valid_paths.append(p)
                except Exception:
                    continue
            if valid_paths:
                if getattr(self, "is_composition_active", False):
                    self.composition_add_paths(valid_paths)
                elif len(valid_paths) > 1:
                    self._start_edit_image_queue(valid_paths)
                else:
                    self.open_image_from_path(valid_paths[0])
                return

        messagebox.showinfo("Paste", "Clipboard does not contain an image.")

    # ===== Multi-image layered composition =====

    def _normalize_composition_layer(self, layer):
        for key, value in COMPOSITION_LAYER_DEFAULTS.items():
            layer.setdefault(key, value)
        layer["rotation"] = float(layer.get("rotation", 0.0))
        layer["opacity"] = max(0.0, min(1.0, float(layer.get("opacity", 1.0))))
        layer["brightness"] = max(0.0, float(layer.get("brightness", 1.0)))
        layer["contrast"] = max(0.0, float(layer.get("contrast", 1.0)))
        layer["saturation"] = max(0.0, float(layer.get("saturation", 1.0)))
        layer["blur"] = max(0.0, float(layer.get("blur", 0.0)))
        layer["shadow_opacity"] = max(
            0.0,
            min(1.0, float(layer.get("shadow_opacity", 0.45))),
        )
        layer["shadow_blur"] = max(0.0, float(layer.get("shadow_blur", 18.0)))
        layer["shadow_x"] = float(layer.get("shadow_x", 14.0))
        layer["shadow_y"] = float(layer.get("shadow_y", 14.0))
        layer["shadow_enabled"] = bool(layer.get("shadow_enabled", False))
        layer["flip_x"] = bool(layer.get("flip_x", False))
        layer["flip_y"] = bool(layer.get("flip_y", False))
        return layer

    def _new_composition_layer(self, image, name, path, x, y):
        layer = {
            "name": name or "Layer",
            "path": path,
            "image": image.copy().convert("RGBA"),
            "x": float(x),
            "y": float(y),
            "scale": 1.0,
            "visible": True,
        }
        return self._normalize_composition_layer(layer)

    def _clear_composition_state(self):
        self.is_composition_active = False
        self.composition_layers = []
        self.composition_selected_index = None
        self.composition_canvas_size = None
        self.composition_history = []
        self.composition_future_history = []
        self.composition_drag_state = None
        self.composition_drag_history_pushed = False
        self.composition_preview_cache = {}
        self.composition_effect_cache = {}
        if self.composition_preview_after_id is not None:
            try:
                self.root.after_cancel(self.composition_preview_after_id)
            except Exception:
                pass
            self.composition_preview_after_id = None
        if self.composition_control_commit_after_id is not None:
            try:
                self.root.after_cancel(self.composition_control_commit_after_id)
            except Exception:
                pass
            self.composition_control_commit_after_id = None
        if hasattr(self, "composition_layer_listbox"):
            self.composition_layer_listbox.delete(0, tk.END)

    def _composition_snapshot(self):
        return {
            "canvas_size": tuple(self.composition_canvas_size) if self.composition_canvas_size else None,
            "selected_index": self.composition_selected_index,
            "layers": [
                {
                    "name": layer.get("name", "Layer"),
                    "path": layer.get("path"),
                    "image": layer["image"].copy(),
                    "x": float(layer.get("x", 0.0)),
                    "y": float(layer.get("y", 0.0)),
                    "scale": float(layer.get("scale", 1.0)),
                    "visible": bool(layer.get("visible", True)),
                    **{
                        key: layer.get(key, default)
                        for key, default in COMPOSITION_LAYER_DEFAULTS.items()
                    },
                }
                for layer in self.composition_layers
            ],
        }

    def _composition_restore_snapshot(self, state):
        self.composition_canvas_size = (
            tuple(state["canvas_size"]) if state.get("canvas_size") else None
        )
        self.composition_layers = [
            self._normalize_composition_layer({
                "name": layer.get("name", "Layer"),
                "path": layer.get("path"),
                "image": layer["image"].copy(),
                "x": float(layer.get("x", 0.0)),
                "y": float(layer.get("y", 0.0)),
                "scale": float(layer.get("scale", 1.0)),
                "visible": bool(layer.get("visible", True)),
                **{
                    key: layer.get(key, default)
                    for key, default in COMPOSITION_LAYER_DEFAULTS.items()
                },
            })
            for layer in state.get("layers", [])
        ]
        selected = state.get("selected_index")
        if selected is not None and not (0 <= selected < len(self.composition_layers)):
            selected = len(self.composition_layers) - 1 if self.composition_layers else None
        self.composition_selected_index = selected
        self._refresh_composition_layer_list()
        self._update_composition_output(mark_dirty=True)

    def _push_composition_history(self):
        self.composition_history.append(self._composition_snapshot())
        if len(self.composition_history) > 30:
            self.composition_history.pop(0)
        self.composition_future_history.clear()

    def composition_undo(self):
        if not self.composition_history:
            return
        self.composition_future_history.append(self._composition_snapshot())
        self._composition_restore_snapshot(self.composition_history.pop())

    def composition_redo(self):
        if not self.composition_future_history:
            return
        self.composition_history.append(self._composition_snapshot())
        self._composition_restore_snapshot(self.composition_future_history.pop())

    def _ensure_composition_seed(self):
        if self.composition_layers or self.edited_img is None:
            return
        seed = self.edited_img.copy().convert("RGBA")
        name = (
            os.path.basename(self.editor_image_path)
            if self.editor_image_path
            else "Base image"
        )
        self.composition_canvas_size = seed.size
        self.composition_layers = [
            self._new_composition_layer(
                seed,
                name,
                self.editor_image_path,
                0.0,
                0.0,
            )
        ]
        self.composition_selected_index = 0
        self._refresh_composition_layer_list()

    def enter_composition_mode(self):
        if getattr(self, "edit_queue_running", False):
            messagebox.showinfo(
                "AI Queue Running",
                "Wait for the Edit queue to finish before opening Compose.",
            )
            return False
        self._clear_edit_queue_state()
        self.is_composition_active = True
        self.png_gif_mode.set(False)
        self.is_slicer_active = False
        self.gif_stop_play()
        self.mode = "compose_select"
        self.canvas.config(cursor="arrow")
        self._ensure_composition_seed()
        if hasattr(self, "left_notebook") and hasattr(self, "compose_tab"):
            try:
                self.left_notebook.select(self.compose_tab)
            except Exception:
                pass
        self._update_composition_output(mark_dirty=False)
        return True

    def composition_add_images_dialog(self):
        paths = filedialog.askopenfilenames(
            title="Add Images to Composition",
            filetypes=IMAGE_OPEN_FILETYPES,
        )
        if paths:
            if self.enter_composition_mode() is False:
                return
            self.composition_add_paths(paths)

    def composition_add_paths(self, paths):
        valid = []
        for path in paths:
            if not isinstance(path, str) or not os.path.exists(path):
                continue
            try:
                with Image.open(path) as source:
                    valid.append((source.copy().convert("RGBA"), path))
            except Exception as error:
                messagebox.showerror(
                    "Add Layer Failed",
                    f"Could not add {os.path.basename(path)}:\n{error}",
                )
        if not valid:
            return
        if not self.is_composition_active:
            if self.enter_composition_mode() is False:
                return
        self._push_composition_history()
        for image, path in valid:
            self.composition_add_pil_image(
                image,
                name=os.path.basename(path),
                path=path,
                push_history=False,
                refresh=False,
            )
        self._refresh_composition_layer_list()
        self._update_composition_output(mark_dirty=True)

    def composition_add_pil_image(
        self,
        image,
        name="Layer",
        path=None,
        push_history=True,
        refresh=True,
    ):
        if not self.is_composition_active:
            self.enter_composition_mode()
        rgba = image.copy().convert("RGBA")
        if push_history:
            self._push_composition_history()
        if self.composition_canvas_size is None:
            self.composition_canvas_size = rgba.size
        canvas_w, canvas_h = self.composition_canvas_size
        x = (canvas_w - rgba.width) / 2.0
        y = (canvas_h - rgba.height) / 2.0
        self.composition_layers.append(
            self._new_composition_layer(rgba, name, path, x, y)
        )
        self.composition_selected_index = len(self.composition_layers) - 1
        if refresh:
            self._refresh_composition_layer_list()
            self._update_composition_output(mark_dirty=True)

    def _composition_transform_cache_key(self, layer, display_factor, fast):
        return (
            id(layer["image"]),
            round(float(layer.get("scale", 1.0)), 4),
            round(float(layer.get("rotation", 0.0)) % 360.0, 2),
            round(float(layer.get("opacity", 1.0)), 3),
            round(float(layer.get("brightness", 1.0)), 3),
            round(float(layer.get("contrast", 1.0)), 3),
            round(float(layer.get("saturation", 1.0)), 3),
            round(float(layer.get("blur", 0.0)), 2),
            bool(layer.get("flip_x", False)),
            bool(layer.get("flip_y", False)),
            round(float(display_factor), 5),
            bool(fast),
        )

    def _composition_transformed_layer(self, layer, display_factor=1.0, fast=False):
        self._normalize_composition_layer(layer)
        if not hasattr(self, "composition_preview_cache"):
            self.composition_preview_cache = {}
        key = self._composition_transform_cache_key(layer, display_factor, fast)
        allow_cache = display_factor < 0.9999
        cached = self.composition_preview_cache.get(key) if allow_cache else None
        if cached is not None:
            return cached

        source = layer["image"].convert("RGBA")
        if layer.get("flip_x", False):
            source = ImageOps.mirror(source)
        if layer.get("flip_y", False):
            source = ImageOps.flip(source)

        document_scale = max(0.02, min(20.0, float(layer.get("scale", 1.0))))
        render_scale = max(0.0001, document_scale * display_factor)
        unrotated_w = max(1, int(round(source.width * render_scale)))
        unrotated_h = max(1, int(round(source.height * render_scale)))
        if source.size != (unrotated_w, unrotated_h):
            resample = Image.Resampling.BILINEAR if fast else Image.Resampling.LANCZOS
            source = source.resize((unrotated_w, unrotated_h), resample)

        brightness = float(layer.get("brightness", 1.0))
        contrast = float(layer.get("contrast", 1.0))
        saturation = float(layer.get("saturation", 1.0))
        if abs(brightness - 1.0) > 0.001:
            source = ImageEnhance.Brightness(source).enhance(brightness)
        if abs(contrast - 1.0) > 0.001:
            source = ImageEnhance.Contrast(source).enhance(contrast)
        if abs(saturation - 1.0) > 0.001:
            source = ImageEnhance.Color(source).enhance(saturation)

        blur_radius = max(0.0, float(layer.get("blur", 0.0)) * display_factor)
        if blur_radius > 0.05:
            source = source.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        opacity = max(0.0, min(1.0, float(layer.get("opacity", 1.0))))
        if opacity < 0.999:
            alpha = source.getchannel("A").point(
                lambda value: int(round(value * opacity))
            )
            source.putalpha(alpha)

        rotation = float(layer.get("rotation", 0.0)) % 360.0
        if abs(rotation) > 0.01:
            resample = Image.Resampling.BILINEAR if fast else Image.Resampling.BICUBIC
            source = source.rotate(-rotation, resample=resample, expand=True)

        offset_x = (unrotated_w - source.width) / 2.0
        offset_y = (unrotated_h - source.height) / 2.0
        cached = (source, offset_x, offset_y)
        if allow_cache:
            if len(self.composition_preview_cache) > 160:
                self.composition_preview_cache.clear()
            self.composition_preview_cache[key] = cached
        return cached

    @staticmethod
    def _alpha_composite_clipped(destination, source, x, y):
        x = int(round(x))
        y = int(round(y))
        left = max(0, x)
        top = max(0, y)
        right = min(destination.width, x + source.width)
        bottom = min(destination.height, y + source.height)
        if left >= right or top >= bottom:
            return
        crop = source.crop((left - x, top - y, right - x, bottom - y))
        destination.alpha_composite(crop, (left, top))

    def _render_composition_image(self, preview_size=None, fast=False):
        if not self.composition_layers:
            return None
        if self.composition_canvas_size is None:
            self.composition_canvas_size = self.composition_layers[0]["image"].size
        canvas_w = max(1, int(self.composition_canvas_size[0]))
        canvas_h = max(1, int(self.composition_canvas_size[1]))
        if preview_size is None:
            output_w, output_h = canvas_w, canvas_h
            display_factor = 1.0
        else:
            output_w = max(1, int(preview_size[0]))
            output_h = max(1, int(preview_size[1]))
            display_factor = min(
                output_w / float(canvas_w),
                output_h / float(canvas_h),
            )
        result = Image.new("RGBA", (output_w, output_h), (0, 0, 0, 0))
        for layer in self.composition_layers:
            if not layer.get("visible", True):
                continue
            source, rotation_offset_x, rotation_offset_y = (
                self._composition_transformed_layer(
                    layer,
                    display_factor=display_factor,
                    fast=fast,
                )
            )
            x = float(layer.get("x", 0.0)) * display_factor + rotation_offset_x
            y = float(layer.get("y", 0.0)) * display_factor + rotation_offset_y

            if layer.get("shadow_enabled", False):
                shadow_alpha = source.getchannel("A")
                shadow_opacity = max(
                    0.0,
                    min(1.0, float(layer.get("shadow_opacity", 0.45))),
                )
                if shadow_opacity < 0.999:
                    shadow_alpha = shadow_alpha.point(
                        lambda value: int(round(value * shadow_opacity))
                    )
                shadow_blur = max(
                    0.0,
                    float(layer.get("shadow_blur", 18.0)) * display_factor,
                )
                if shadow_blur > 0.05:
                    shadow_alpha = shadow_alpha.filter(
                        ImageFilter.GaussianBlur(radius=shadow_blur)
                    )
                shadow = Image.new("RGBA", source.size, (0, 0, 0, 0))
                shadow.putalpha(shadow_alpha)
                self._alpha_composite_clipped(
                    result,
                    shadow,
                    x + float(layer.get("shadow_x", 14.0)) * display_factor,
                    y + float(layer.get("shadow_y", 14.0)) * display_factor,
                )

            self._alpha_composite_clipped(result, source, x, y)
        return result

    def _update_composition_output(self, mark_dirty=True):
        self.composition_effect_cache = {}
        composite = self._render_composition_image()
        if composite is not None:
            self.edited_img = composite
            if mark_dirty:
                self.project_dirty = True
        elif self.is_composition_active:
            self.edited_img = None
            if mark_dirty:
                self.project_dirty = True
        self._sync_composition_controls()
        if getattr(self, "is_composition_active", False):
            self.update_preview()

    def _refresh_composition_layer_list(self):
        if not hasattr(self, "composition_layer_listbox"):
            return
        self.composition_layer_listbox.delete(0, tk.END)
        for layer in reversed(self.composition_layers):
            visibility = "●" if layer.get("visible", True) else "○"
            self.composition_layer_listbox.insert(
                tk.END,
                f"{visibility}  {layer.get('name', 'Layer')}",
            )
        if self.composition_selected_index is not None:
            ui_index = len(self.composition_layers) - 1 - self.composition_selected_index
            if 0 <= ui_index < self.composition_layer_listbox.size():
                self.composition_layer_listbox.selection_set(ui_index)
                self.composition_layer_listbox.see(ui_index)
        self._sync_composition_controls()

    def _on_composition_list_selection(self, _event=None):
        if not hasattr(self, "composition_layer_listbox"):
            return
        selected = self.composition_layer_listbox.curselection()
        if not selected:
            return
        self.composition_selected_index = (
            len(self.composition_layers) - 1 - int(selected[0])
        )
        self._sync_composition_controls()
        if self.is_composition_active:
            self.update_preview()

    def _selected_composition_layer(self):
        index = self.composition_selected_index
        if index is None or not (0 <= index < len(self.composition_layers)):
            return None
        return self.composition_layers[index]

    def _sync_composition_controls(self):
        layer = self._selected_composition_layer()
        if layer is None:
            return
        self._normalize_composition_layer(layer)
        self.composition_controls_syncing = True
        try:
            self.composition_x_var.set(int(round(layer.get("x", 0.0))))
            self.composition_y_var.set(int(round(layer.get("y", 0.0))))
            self.composition_scale_var.set(
                round(layer.get("scale", 1.0) * 100.0, 1)
            )
            self.composition_rotation_var.set(
                round(layer.get("rotation", 0.0), 1)
            )
            self.composition_opacity_var.set(
                round(layer.get("opacity", 1.0) * 100.0, 1)
            )
            self.composition_brightness_var.set(
                round(layer.get("brightness", 1.0) * 100.0, 1)
            )
            self.composition_contrast_var.set(
                round(layer.get("contrast", 1.0) * 100.0, 1)
            )
            self.composition_saturation_var.set(
                round(layer.get("saturation", 1.0) * 100.0, 1)
            )
            self.composition_blur_var.set(round(layer.get("blur", 0.0), 1))
            self.composition_shadow_enabled_var.set(
                bool(layer.get("shadow_enabled", False))
            )
            self.composition_shadow_opacity_var.set(
                round(layer.get("shadow_opacity", 0.45) * 100.0, 1)
            )
            self.composition_shadow_blur_var.set(
                round(layer.get("shadow_blur", 18.0), 1)
            )
            self.composition_shadow_x_var.set(
                int(round(layer.get("shadow_x", 14.0)))
            )
            self.composition_shadow_y_var.set(
                int(round(layer.get("shadow_y", 14.0)))
            )
        finally:
            self.composition_controls_syncing = False

    def _composition_values_from_controls(self):
        return {
            "x": float(self.composition_x_var.get()),
            "y": float(self.composition_y_var.get()),
            "scale": max(
                0.02,
                min(20.0, float(self.composition_scale_var.get()) / 100.0),
            ),
            "rotation": float(self.composition_rotation_var.get()),
            "opacity": max(
                0.0,
                min(1.0, float(self.composition_opacity_var.get()) / 100.0),
            ),
            "brightness": max(
                0.0,
                float(self.composition_brightness_var.get()) / 100.0,
            ),
            "contrast": max(
                0.0,
                float(self.composition_contrast_var.get()) / 100.0,
            ),
            "saturation": max(
                0.0,
                float(self.composition_saturation_var.get()) / 100.0,
            ),
            "blur": max(0.0, float(self.composition_blur_var.get())),
            "shadow_enabled": bool(self.composition_shadow_enabled_var.get()),
            "shadow_opacity": max(
                0.0,
                min(
                    1.0,
                    float(self.composition_shadow_opacity_var.get()) / 100.0,
                ),
            ),
            "shadow_blur": max(
                0.0,
                float(self.composition_shadow_blur_var.get()),
            ),
            "shadow_x": float(self.composition_shadow_x_var.get()),
            "shadow_y": float(self.composition_shadow_y_var.get()),
        }

    @staticmethod
    def _composition_values_differ(layer, values):
        for key, value in values.items():
            current = layer.get(key, COMPOSITION_LAYER_DEFAULTS.get(key, 0.0))
            if isinstance(value, bool):
                if bool(current) != value:
                    return True
            elif abs(float(current) - float(value)) > 0.0001:
                return True
        return False

    def _apply_composition_control_values(self, commit_full):
        layer = self._selected_composition_layer()
        if layer is None or self.composition_controls_syncing:
            return False
        try:
            values = self._composition_values_from_controls()
        except (TypeError, ValueError, tk.TclError):
            self._sync_composition_controls()
            return False
        if not self._composition_values_differ(layer, values):
            return False
        layer.update(values)
        self.composition_preview_cache.clear()
        self.project_dirty = True
        if commit_full:
            self._update_composition_output(mark_dirty=True)
        else:
            self._request_composition_preview()
        return True

    def composition_apply_all_controls(self, _event=None):
        layer = self._selected_composition_layer()
        if layer is None or self.composition_controls_syncing:
            return
        try:
            values = self._composition_values_from_controls()
        except (TypeError, ValueError, tk.TclError):
            self._sync_composition_controls()
            return
        if not self._composition_values_differ(layer, values):
            return
        if not self.composition_control_history_pushed:
            self._push_composition_history()
        layer.update(values)
        self.composition_preview_cache.clear()
        self._update_composition_output(mark_dirty=True)

    def composition_apply_transform_controls(self, _event=None):
        self.composition_apply_all_controls(_event)

    def _composition_begin_control_change(self, _event=None):
        if self.composition_controls_syncing or self._selected_composition_layer() is None:
            return
        if not self.composition_control_history_pushed:
            self._push_composition_history()
            self.composition_control_history_pushed = True

    def _on_composition_adjustment_live(self, _value=None):
        if self.composition_controls_syncing:
            return
        if (
            not self.composition_control_history_pushed
            and self._selected_composition_layer() is not None
        ):
            self._push_composition_history()
            self.composition_control_history_pushed = True
        self._apply_composition_control_values(commit_full=False)
        if self.composition_control_commit_after_id is not None:
            try:
                self.root.after_cancel(self.composition_control_commit_after_id)
            except Exception:
                pass
        try:
            self.composition_control_commit_after_id = self.root.after(
                300,
                self._composition_finish_control_change,
            )
        except Exception:
            self.composition_control_commit_after_id = None

    def _composition_finish_control_change(self, _event=None):
        if self.composition_controls_syncing:
            return
        if self.composition_control_commit_after_id is not None:
            try:
                self.root.after_cancel(self.composition_control_commit_after_id)
            except Exception:
                pass
            self.composition_control_commit_after_id = None
        changed = self._apply_composition_control_values(commit_full=False)
        had_history = self.composition_control_history_pushed
        self.composition_control_history_pushed = False
        if changed or had_history:
            self._update_composition_output(mark_dirty=True)

    def _request_composition_preview(self):
        if self.composition_preview_after_id is not None:
            return
        try:
            self.composition_preview_after_id = self.root.after(
                12,
                self._flush_composition_preview,
            )
        except Exception:
            self.update_preview()

    def _flush_composition_preview(self):
        self.composition_preview_after_id = None
        if self.is_composition_active:
            self.update_preview()

    def composition_rotate_selected(self, degrees):
        layer = self._selected_composition_layer()
        if layer is None:
            return
        self._push_composition_history()
        layer["rotation"] = float(layer.get("rotation", 0.0)) + float(degrees)
        self.composition_preview_cache.clear()
        self._update_composition_output(mark_dirty=True)

    def composition_flip_selected(self, direction):
        layer = self._selected_composition_layer()
        if layer is None:
            return
        self._push_composition_history()
        key = "flip_x" if direction == "horizontal" else "flip_y"
        layer[key] = not bool(layer.get(key, False))
        self.composition_preview_cache.clear()
        self._update_composition_output(mark_dirty=True)

    def composition_reset_appearance(self):
        layer = self._selected_composition_layer()
        if layer is None:
            return
        self._push_composition_history()
        for key in (
            "opacity",
            "brightness",
            "contrast",
            "saturation",
            "blur",
            "shadow_enabled",
            "shadow_opacity",
            "shadow_blur",
            "shadow_x",
            "shadow_y",
        ):
            layer[key] = COMPOSITION_LAYER_DEFAULTS[key]
        self.composition_preview_cache.clear()
        self._update_composition_output(mark_dirty=True)

    def composition_fit_selected(self):
        layer = self._selected_composition_layer()
        if layer is None or not self.composition_canvas_size:
            return
        self._push_composition_history()
        canvas_w, canvas_h = self.composition_canvas_size
        image = layer["image"]
        angle = math.radians(float(layer.get("rotation", 0.0)))
        rotated_w = abs(image.width * math.cos(angle)) + abs(image.height * math.sin(angle))
        rotated_h = abs(image.width * math.sin(angle)) + abs(image.height * math.cos(angle))
        scale = min(
            canvas_w / max(1.0, rotated_w),
            canvas_h / max(1.0, rotated_h),
        )
        layer["scale"] = max(0.02, min(20.0, scale))
        layer["x"] = (canvas_w - image.width * layer["scale"]) / 2.0
        layer["y"] = (canvas_h - image.height * layer["scale"]) / 2.0
        self.composition_preview_cache.clear()
        self._update_composition_output(mark_dirty=True)

    def composition_reset_selected(self):
        layer = self._selected_composition_layer()
        if layer is None or not self.composition_canvas_size:
            return
        self._push_composition_history()
        canvas_w, canvas_h = self.composition_canvas_size
        layer["scale"] = 1.0
        layer["rotation"] = 0.0
        layer["flip_x"] = False
        layer["flip_y"] = False
        layer["x"] = (canvas_w - layer["image"].width) / 2.0
        layer["y"] = (canvas_h - layer["image"].height) / 2.0
        self.composition_preview_cache.clear()
        self._update_composition_output(mark_dirty=True)

    def composition_duplicate_selected(self):
        layer = self._selected_composition_layer()
        if layer is None:
            return
        self._push_composition_history()
        duplicate = {
            "name": f"{layer.get('name', 'Layer')} copy",
            "path": layer.get("path"),
            "image": layer["image"].copy(),
            "x": float(layer.get("x", 0.0)) + 18.0,
            "y": float(layer.get("y", 0.0)) + 18.0,
            "scale": float(layer.get("scale", 1.0)),
            "visible": bool(layer.get("visible", True)),
            **{
                key: layer.get(key, default)
                for key, default in COMPOSITION_LAYER_DEFAULTS.items()
            },
        }
        self._normalize_composition_layer(duplicate)
        insert_at = self.composition_selected_index + 1
        self.composition_layers.insert(insert_at, duplicate)
        self.composition_selected_index = insert_at
        self._refresh_composition_layer_list()
        self._update_composition_output(mark_dirty=True)

    def composition_delete_selected(self):
        index = self.composition_selected_index
        if index is None or not (0 <= index < len(self.composition_layers)):
            return
        self._push_composition_history()
        self.composition_layers.pop(index)
        self.composition_selected_index = (
            min(index, len(self.composition_layers) - 1)
            if self.composition_layers
            else None
        )
        self._refresh_composition_layer_list()
        if self.composition_layers:
            self._update_composition_output(mark_dirty=True)
        else:
            self.edited_img = None
            self.project_dirty = True
            self.update_preview()

    def composition_toggle_selected_visibility(self):
        layer = self._selected_composition_layer()
        if layer is None:
            return
        self._push_composition_history()
        layer["visible"] = not layer.get("visible", True)
        self._refresh_composition_layer_list()
        self._update_composition_output(mark_dirty=True)

    def composition_reorder_selected(self, direction):
        index = self.composition_selected_index
        total = len(self.composition_layers)
        if index is None or total < 2:
            return
        if direction == "forward":
            new_index = min(total - 1, index + 1)
        elif direction == "front":
            new_index = total - 1
        elif direction == "backward":
            new_index = max(0, index - 1)
        else:
            new_index = 0
        if new_index == index:
            return
        self._push_composition_history()
        layer = self.composition_layers.pop(index)
        self.composition_layers.insert(new_index, layer)
        self.composition_selected_index = new_index
        self._refresh_composition_layer_list()
        self._update_composition_output(mark_dirty=True)

    def _composition_layer_bounds(self, layer):
        scale = float(layer.get("scale", 1.0))
        x = float(layer.get("x", 0.0))
        y = float(layer.get("y", 0.0))
        width = layer["image"].width * scale
        height = layer["image"].height * scale
        angle = math.radians(float(layer.get("rotation", 0.0)))
        rotated_width = abs(width * math.cos(angle)) + abs(height * math.sin(angle))
        rotated_height = abs(width * math.sin(angle)) + abs(height * math.cos(angle))
        left = x + (width - rotated_width) / 2.0
        top = y + (height - rotated_height) / 2.0
        return (
            left,
            top,
            left + rotated_width,
            top + rotated_height,
        )

    def _composition_hit_test(self, image_x, image_y):
        for index in range(len(self.composition_layers) - 1, -1, -1):
            layer = self.composition_layers[index]
            if not layer.get("visible", True):
                continue
            x0, y0, x1, y1 = self._composition_layer_bounds(layer)
            if x0 <= image_x <= x1 and y0 <= image_y <= y1:
                return index
        return None

    def _composition_handle_radius_image(self):
        metrics = self._get_editor_canvas_metrics()
        scale = metrics["canvas_scale"] if metrics else 1.0
        return 12.0 / max(0.0001, scale)

    def _composition_begin_pointer_action(self, event):
        if not self.composition_layers:
            return
        image_x, image_y = self.canvas_to_image(event.x, event.y)
        selected = self._selected_composition_layer()
        radius = self._composition_handle_radius_image()
        if selected is not None:
            rotation_handle = getattr(
                self,
                "composition_rotation_handle_canvas",
                None,
            )
            if rotation_handle is not None:
                handle_dx = event.x - rotation_handle[0]
                handle_dy = event.y - rotation_handle[1]
                if (handle_dx * handle_dx + handle_dy * handle_dy) <= 14 * 14:
                    scale = float(selected.get("scale", 1.0))
                    center_x = (
                        float(selected.get("x", 0.0))
                        + selected["image"].width * scale / 2.0
                    )
                    center_y = (
                        float(selected.get("y", 0.0))
                        + selected["image"].height * scale / 2.0
                    )
                    self.composition_drag_state = {
                        "type": "rotate",
                        "center_x": center_x,
                        "center_y": center_y,
                        "start_angle": math.atan2(
                            image_y - center_y,
                            image_x - center_x,
                        ),
                        "start_rotation": float(
                            selected.get("rotation", 0.0)
                        ),
                    }
                    self.composition_drag_history_pushed = False
                    self.canvas.config(cursor="exchange")
                    return
            x0, y0, x1, y1 = self._composition_layer_bounds(selected)
            if abs(image_x - x1) <= radius and abs(image_y - y1) <= radius:
                self.composition_drag_state = {
                    "type": "resize",
                    "start_x": image_x,
                    "start_y": image_y,
                    "start_scale": float(selected.get("scale", 1.0)),
                    "start_width": max(1.0, x1 - x0),
                }
                self.composition_drag_history_pushed = False
                self.canvas.config(cursor="sizing")
                return
        hit = self._composition_hit_test(image_x, image_y)
        self.composition_selected_index = hit
        self._refresh_composition_layer_list()
        if hit is None:
            self.composition_drag_state = None
            self.update_preview()
            return
        layer = self.composition_layers[hit]
        self.composition_drag_state = {
            "type": "move",
            "offset_x": image_x - float(layer.get("x", 0.0)),
            "offset_y": image_y - float(layer.get("y", 0.0)),
        }
        self.composition_drag_history_pushed = False
        self.canvas.config(cursor="fleur")
        self.update_preview()

    def _composition_drag_pointer(self, event):
        state = self.composition_drag_state
        layer = self._selected_composition_layer()
        if state is None or layer is None:
            return
        image_x, image_y = self.canvas_to_image(event.x, event.y)
        if not self.composition_drag_history_pushed:
            self._push_composition_history()
            self.composition_drag_history_pushed = True
        if state["type"] == "move":
            layer["x"] = image_x - state["offset_x"]
            layer["y"] = image_y - state["offset_y"]
        elif state["type"] == "resize":
            delta = image_x - state["start_x"]
            width = max(2.0, state["start_width"] + delta)
            layer["scale"] = max(
                0.02,
                min(20.0, state["start_scale"] * (width / state["start_width"])),
            )
            self.composition_preview_cache.clear()
        else:
            angle = math.atan2(
                image_y - state["center_y"],
                image_x - state["center_x"],
            )
            layer["rotation"] = state["start_rotation"] + math.degrees(
                angle - state["start_angle"]
            )
            self.composition_preview_cache.clear()
        self.project_dirty = True
        self._request_composition_preview()

    def _composition_end_pointer_action(self):
        changed = self.composition_drag_history_pushed
        self.composition_drag_state = None
        self.composition_drag_history_pushed = False
        self.canvas.config(cursor="arrow")
        if changed:
            self._update_composition_output(mark_dirty=True)
        else:
            self._sync_composition_controls()

    def composition_flatten_to_editor(self):
        composite = self._render_composition_image()
        if composite is None:
            messagebox.showinfo("Compose", "Add at least one layer before flattening.")
            return
        self.is_composition_active = False
        self.open_image_from_pil(
            composite,
            path_info=None,
            confirm_replace=False,
            preserve_composition=True,
        )
        self.project_dirty = True
        try:
            self.left_notebook.select(self.edit_tab)
        except Exception:
            pass

    def auto_pick_background_color(self, img):
        if img is None:
            return
        w, h = img.size
        if w < 2 or h < 2:
            return
        rgba = img.convert("RGBA")
        corners = [
            rgba.getpixel((0, 0))[:3],
            rgba.getpixel((w - 1, 0))[:3],
            rgba.getpixel((0, h - 1))[:3],
            rgba.getpixel((w - 1, h - 1))[:3]
        ]
        from collections import Counter
        most_common = Counter(corners).most_common(1)[0][0]
        r, g, b = most_common
        col = f"#{r:02x}{g:02x}{b:02x}"
        self.hex_var.set(col)
        self.color_canvas.delete("all")
        self.color_canvas.create_rectangle(8, 8, 52, 52, fill=col, outline="white", width=2)

    def _apply_color_removal_preview(self, img, rule_color, tol, soft, contiguous=None, clean_holes=None):
        import numpy as np
        import cv2
        arr = np.array(img.convert("RGBA"))
        rgb = arr[:, :, :3]
        a_channel = arr[:, :, 3]

        tr, tg, tb = rule_color
        tol_val = tol * 2.55
        soft_val = soft * 2.55

        if contiguous is None:
            contiguous = self.contiguous_var.get()
        if clean_holes is None:
            clean_holes = self.clean_holes_var.get()

        dist = np.sqrt(np.sum((rgb - [tr, tg, tb]) ** 2, axis=-1))

        if soft_val > 0:
            lower_bound = tol_val - soft_val / 2.0
            upper_bound = tol_val + soft_val / 2.0
            if upper_bound > lower_bound:
                factor = np.clip((dist - lower_bound) / (upper_bound - lower_bound), 0.0, 1.0)
            else:
                factor = (dist > tol_val).astype(float)
        else:
            factor = (dist > tol_val).astype(float)

        if contiguous:
            bg_candidate_mask = (factor < 1.0).astype(np.uint8) * 255
            h, w = bg_candidate_mask.shape
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bg_candidate_mask, connectivity=8)
            
            border_labels = set()
            for x in range(w):
                border_labels.add(labels[0, x])
                border_labels.add(labels[h - 1, x])
            for y in range(h):
                border_labels.add(labels[y, 0])
                border_labels.add(labels[y, w - 1])
                
            if 0 in border_labels:
                border_labels.remove(0)
                
            if not clean_holes:
                keep_opaque_mask = np.ones((h, w), dtype=bool)
                for label in range(1, num_labels):
                    if label not in border_labels:
                        keep_opaque_mask[labels == label] = False
                factor[~keep_opaque_mask] = 1.0

        mask_partial = (factor > 0.0) & (factor < 1.0)
        if np.any(mask_partial):
            rgb_f = rgb.astype(float)
            bg_col_f = np.array([tr, tg, tb], dtype=float)
            factor_expanded = np.expand_dims(factor, axis=-1)
            unmultiplied = (rgb_f - (1.0 - factor_expanded) * bg_col_f) / np.maximum(factor_expanded, 0.05)
            unmultiplied = np.clip(unmultiplied, 0.0, 255.0)
            arr[mask_partial, :3] = unmultiplied[mask_partial].astype(np.uint8)

        new_a = (a_channel * factor).astype(np.uint8)
        arr[:, :, 3] = new_a

        return Image.fromarray(arr, "RGBA").copy()

    def _is_shutting_down(self):
        event = getattr(self, "_shutdown_event", None)
        return bool(event and event.is_set())

    def _start_worker(self, target, name):
        """Start and track an app-owned daemon worker."""
        if self._is_shutting_down():
            return None

        def _run():
            try:
                if not self._is_shutting_down():
                    target()
            finally:
                lock = getattr(self, "_worker_threads_lock", None)
                workers = getattr(self, "_worker_threads", None)
                if lock is not None and workers is not None:
                    with lock:
                        workers.discard(threading.current_thread())

        worker = threading.Thread(
            target=_run,
            name=f"Transparentor-{name}",
            daemon=True,
        )
        with self._worker_threads_lock:
            self._worker_threads.add(worker)
        worker.start()
        return worker

    def _queue_ui(self, callback, *args):
        """Queue UI work only while the Tk application is still alive."""
        if self._is_shutting_down():
            return None
        try:
            return self.root.after(0, callback, *args)
        except (RuntimeError, tk.TclError):
            return None

    @staticmethod
    def _format_ai_time(seconds):
        if seconds is None or not math.isfinite(seconds):
            return "estimating…"
        seconds = max(0, int(round(seconds)))
        if seconds < 60:
            return f"{seconds}s"
        minutes, remainder = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m {remainder:02d}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m"

    def _draw_ai_progress(self):
        canvas = getattr(self, "ai_progress", None)
        if canvas is None:
            return
        try:
            width = max(120, int(canvas.cget("width")))
            canvas.delete("all")
        except Exception:
            return

        value = max(0.0, min(100.0, float(self.ai_progress_value)))
        segments = 18
        gap = 2
        left = 1
        top = 3
        bar_h = 10
        segment_w = (width - 2 - gap * (segments - 1)) / segments
        accent = (108, 140, 255)
        finish = (69, 214, 164)
        inactive = self.COLOR_BORDER
        filled_exact = value * segments / 100.0
        lead_index = min(segments - 1, max(0, int(filled_exact)))

        for index in range(segments):
            x0 = left + index * (segment_w + gap)
            x1 = x0 + segment_w
            fraction = index / max(1, segments - 1)
            rgb = tuple(
                int(accent[channel] * (1.0 - fraction) + finish[channel] * fraction)
                for channel in range(3)
            )
            fill = inactive
            if index < int(filled_exact):
                fill = "#%02x%02x%02x" % rgb
            elif index == lead_index and self.ai_progress_active and value > 0:
                pulse = 0.55 + 0.45 * math.sin(self.ai_progress_shimmer * math.tau)
                glow = tuple(min(255, int(channel + (255 - channel) * pulse * 0.45)) for channel in rgb)
                fill = "#%02x%02x%02x" % glow
            canvas.create_rectangle(
                x0,
                top,
                x1,
                top + bar_h,
                fill=fill,
                outline="",
            )

        if self.ai_progress_active:
            elapsed = (
                time.monotonic() - self.ai_progress_task_started
                if self.ai_progress_task_started is not None
                else 0.0
            )
            item_base = getattr(self, "ai_progress_item_base", 0.0)
            item_span = max(0.001, getattr(self, "ai_progress_item_span", 100.0))
            local_fraction = max(0.0, min(1.0, (value - item_base) / item_span))
            item_expected = self.ai_progress_item_expected
            if item_expected is None:
                eta = None
            else:
                current_remaining = max(0.0, item_expected * (1.0 - local_fraction))
                eta = current_remaining + self.ai_progress_queue_remaining * item_expected
            detail = (
                f"{value:3.0f}%  •  {self._format_ai_time(elapsed)} elapsed"
                f"  •  ~{self._format_ai_time(eta)} left"
            )
            text_color = self.COLOR_DANGER if getattr(self, "ai_progress_error", False) else self.COLOR_MUTED
        elif value >= 99.5:
            detail = "100%  •  Complete"
            text_color = self.COLOR_SUCCESS
        else:
            detail = "Ready"
            text_color = self.COLOR_MUTED
        canvas.create_text(
            1,
            26,
            anchor="w",
            text=detail,
            fill=text_color,
            font=("Segoe UI Semibold", 8),
        )

    def _schedule_ai_progress_tick(self):
        if self.ai_progress_after_id is not None or self._is_shutting_down():
            return
        try:
            self.ai_progress_after_id = self.root.after(90, self._ai_progress_tick)
        except Exception:
            self.ai_progress_after_id = None

    def _ai_progress_tick(self):
        self.ai_progress_after_id = None
        if not self.ai_progress_active or self._is_shutting_down():
            self._draw_ai_progress()
            return
        now = time.monotonic()
        if (
            self.ai_progress_stage_started is not None
            and self.ai_progress_stage_expected
            and self.ai_progress_stage_expected > 0
        ):
            elapsed = now - self.ai_progress_stage_started
            ratio = min(0.94, elapsed / self.ai_progress_stage_expected)
            estimated_target = self.ai_progress_stage_start + (
                self.ai_progress_stage_end - self.ai_progress_stage_start
            ) * ratio
            self.ai_progress_target = max(self.ai_progress_target, estimated_target)
        delta = self.ai_progress_target - self.ai_progress_value
        self.ai_progress_value += delta * (0.24 if abs(delta) > 0.5 else 0.45)
        self.ai_progress_shimmer = (self.ai_progress_shimmer + 0.075) % 1.0
        self._draw_ai_progress()
        self._schedule_ai_progress_tick()

    def _estimated_ai_seconds(self, model_name, image_size=None):
        estimate = float(self.ai_duration_estimates.get(model_name, 18.0))
        if image_size:
            megapixels = max(0.1, image_size[0] * image_size[1] / 1_000_000.0)
            estimate *= 0.86 + 0.14 * min(3.0, math.sqrt(megapixels))
        return max(2.0, estimate)

    def _begin_ai_task(self, model_name, image_size=None):
        if self.ai_progress_reset_after_id is not None:
            try:
                self.root.after_cancel(self.ai_progress_reset_after_id)
            except Exception:
                pass
            self.ai_progress_reset_after_id = None
        queue_active = bool(getattr(self, "edit_queue_running", False))
        queue_total = max(1, len(self.batch_files_list)) if queue_active else 1
        queue_index = (
            max(0, int(self.batch_preview_index or 0))
            if queue_active
            else 0
        )
        self.ai_progress_item_base = queue_index * 100.0 / queue_total
        self.ai_progress_item_span = 100.0 / queue_total
        inference_expected = self._estimated_ai_seconds(model_name, image_size)
        self.ai_progress_item_expected = inference_expected + max(3.0, inference_expected * 0.18)
        self.ai_progress_queue_remaining = max(0, queue_total - queue_index - 1)
        if not self.ai_progress_active or queue_index == 0:
            self.ai_progress_task_started = time.monotonic()
        self.ai_progress_active = True
        self.ai_progress_error = False
        self.ai_progress_value = max(self.ai_progress_value, self.ai_progress_item_base)
        self.ai_progress_target = self.ai_progress_item_base
        self._set_ai_stage_ui("Preparing", 0.0, 6.0, 0.7)
        self._schedule_ai_progress_tick()

    def _set_ai_stage(self, label, local_start, local_end, expected_seconds=None):
        self._queue_ui(
            self._set_ai_stage_ui,
            label,
            local_start,
            local_end,
            expected_seconds,
        )

    def _set_ai_stage_ui(self, label, local_start, local_end, expected_seconds=None):
        base = getattr(self, "ai_progress_item_base", 0.0)
        span = getattr(self, "ai_progress_item_span", 100.0)
        self.ai_progress_stage = str(label)
        self.ai_progress_stage_start = base + span * float(local_start) / 100.0
        self.ai_progress_stage_end = base + span * float(local_end) / 100.0
        self.ai_progress_stage_started = time.monotonic()
        self.ai_progress_stage_expected = (
            max(0.1, float(expected_seconds))
            if expected_seconds is not None
            else None
        )
        self.ai_progress_target = max(self.ai_progress_target, self.ai_progress_stage_start)
        self._draw_ai_progress()
        self._schedule_ai_progress_tick()

    def _record_ai_inference_duration(self, model_name, duration):
        if duration <= 0:
            return
        previous = float(self.ai_duration_estimates.get(model_name, duration))
        self.ai_duration_estimates[model_name] = previous * 0.68 + float(duration) * 0.32
        _save_ai_duration_estimates(self.ai_duration_estimates)

    def _ai_sessions_are_cached(self, selected_model):
        return all(
            component in self.ai_sessions
            and self.ai_sessions[component] is not None
            for component in _ai_component_models(selected_model)
        )

    def _release_unused_ai_sessions(self, selected_model):
        """Release cached models that the newly selected mode cannot use."""
        if (
            not hasattr(self, "ai_session_lock")
            or getattr(self, "ai_progress_active", False)
        ):
            return
        required = set(_ai_component_models(selected_model))
        released = []
        with self.ai_session_lock:
            for model_name in list(getattr(self, "ai_sessions", {})):
                if model_name in required:
                    continue
                session = self.ai_sessions.pop(model_name, None)
                if session is not None:
                    released.append(session)
        for session in released:
            try:
                if hasattr(session, "inner_session"):
                    session.inner_session = None
            except Exception:
                pass
        if released:
            released.clear()
            gc.collect()

    def _release_ai_session(self, model_name):
        """Drop one ONNX session and its retained inference arena."""
        session = None
        with self.ai_session_lock:
            session = getattr(self, "ai_sessions", {}).pop(model_name, None)
        if session is not None:
            try:
                if hasattr(session, "inner_session"):
                    session.inner_session = None
            except Exception:
                pass
            session = None
            gc.collect()

    def _ensure_ai_sessions(
        self,
        selected_model,
        new_session,
        ort,
        status_callback=None,
    ):
        components = _ai_component_models(selected_model)
        available_providers = ort.get_available_providers()
        with self.ai_session_lock:
            if not hasattr(self, "ai_sessions"):
                self.ai_sessions = {}
            for index, component in enumerate(components, start=1):
                if self._is_shutting_down():
                    raise RuntimeError("AI processing was cancelled.")
                if (
                    component in self.ai_sessions
                    and self.ai_sessions[component] is not None
                ):
                    continue
                if status_callback:
                    status_callback(
                        f"SESSION: Loading {AI_MODEL_INFO[component]['label']} "
                        f"({index}/{len(components)})..."
                    )
                if component.startswith("birefnet"):
                    providers = ["CPUExecutionProvider"]
                else:
                    providers = (
                        ["DmlExecutionProvider", "CPUExecutionProvider"]
                        if "DmlExecutionProvider" in available_providers
                        else ["CPUExecutionProvider"]
                    )
                self.ai_sessions[component] = new_session(
                    component,
                    providers=providers,
                )
        return components

    def _run_ai_selection_mask(
        self,
        image,
        selected_model,
        remove,
        new_session=None,
        ort=None,
        progress_callback=None,
        status_callback=None,
    ):
        components = _ai_component_models(selected_model)
        masks = {}
        total_started = time.monotonic()
        for index, component in enumerate(components, start=1):
            if self._is_shutting_down():
                raise RuntimeError("AI processing was cancelled.")
            if (
                component not in self.ai_sessions
                or self.ai_sessions[component] is None
            ):
                if new_session is None or ort is None:
                    raise RuntimeError(
                        f"{AI_MODEL_INFO[component]['label']} is not loaded."
                    )
                self._ensure_ai_sessions(
                    component,
                    new_session,
                    ort,
                    status_callback=status_callback,
                )
            if status_callback:
                status_callback(
                    f"INFERENCE: {AI_MODEL_INFO[component]['label']} "
                    f"({index}/{len(components)})..."
                )
            if progress_callback:
                progress_callback(index - 1, len(components), component)
            inference_started = time.monotonic()
            release_after_inference = (
                component.startswith("birefnet")
                or selected_model == FUSION_AI_MODEL
            )
            try:
                masks[component] = remove(
                    image,
                    session=self.ai_sessions[component],
                    only_mask=True,
                )
            finally:
                self._record_ai_inference_duration(
                    component,
                    time.monotonic() - inference_started,
                )
                # BiRefNet's CPU arena can retain many gigabytes after
                # inference. Refinement needs the mask, not the live network,
                # so release it even if inference fails. Fusion thereby runs
                # its models truly sequentially instead of retaining both.
                if release_after_inference:
                    self._release_ai_session(component)
                    if status_callback:
                        status_callback(
                            f"MEMORY: Released "
                            f"{AI_MODEL_INFO[component]['label']} session."
                        )

        if selected_model == FUSION_AI_MODEL:
            if status_callback:
                status_callback("FUSION: Combining structure and fine detail...")
            result = _fuse_ai_masks(
                image,
                masks["birefnet-massive"],
                masks["isnet-general-use"],
            )
        else:
            result = masks[components[0]]

        total_duration = time.monotonic() - total_started
        self._record_ai_inference_duration(selected_model, total_duration)
        if progress_callback:
            progress_callback(len(components), len(components), None)
        return result, total_duration

    def _finish_ai_progress_item(self, final=False, error=False):
        item_end = getattr(self, "ai_progress_item_base", 0.0) + getattr(
            self,
            "ai_progress_item_span",
            100.0,
        )
        self.ai_progress_value = max(self.ai_progress_value, item_end)
        self.ai_progress_target = item_end
        self.ai_progress_error = bool(error)
        if final:
            self.ai_progress_active = False
            self.ai_progress_stage = "Complete" if not error else "Failed"
            self._draw_ai_progress()
            try:
                self.ai_progress_reset_after_id = self.root.after(
                    1800,
                    self._reset_ai_progress,
                )
            except Exception:
                self.ai_progress_reset_after_id = None
        else:
            self.ai_progress_stage = "Advancing queue"
            self.ai_progress_stage_started = time.monotonic()
            self.ai_progress_stage_expected = 0.2
            self._draw_ai_progress()

    def _reset_ai_progress(self):
        self.ai_progress_reset_after_id = None
        if self.ai_progress_active:
            return
        self.ai_progress_value = 0.0
        self.ai_progress_target = 0.0
        self.ai_progress_error = False
        self.ai_progress_stage = "Ready"
        self._draw_ai_progress()

    def update_ai_status(self, text, is_error=False):
        def _update():
            try:
                display = str(text)
                for prefix in ("AI: ", "ENGINE: ", "SYSTEM: ", "SESSION: ", "INFERENCE: ", "POST-PROCESS: "):
                    if display.upper().startswith(prefix):
                        display = display[len(prefix):]
                        break
                display = display.strip().upper()
                if len(display) > 27:
                    display = display[:26] + "…"
                self.ai_status_label.config(text=display)
                color = self.COLOR_DANGER if is_error else (self.COLOR_ACCENT if "running" in text.lower() or "download" in text.lower() or "inf" in text.lower() or "session" in text.lower() or "scan" in text.lower() or "cleanup" in text.lower() else self.COLOR_SUCCESS)
                self.ai_indicator.itemconfig(self.ai_indicator_circle, fill=color, outline=color)
                if is_error:
                    self.ai_progress_error = True
                self._draw_ai_progress()
            except Exception:
                pass
        self._queue_ui(_update)

    def update_ai_progress(self, val, mode='determinate'):
        def _update():
            try:
                if mode == 'indeterminate':
                    if val > 0:
                        if not self.ai_progress_active:
                            model = self.ai_model_var.get()
                            size = self.original_img.size if self.original_img is not None else None
                            self._begin_ai_task(model, size)
                        self._set_ai_stage_ui(
                            self.ai_progress_stage or "Working",
                            10.0,
                            90.0,
                            self.ai_progress_item_expected,
                        )
                else:
                    numeric = max(0.0, min(100.0, float(val)))
                    if numeric > 0 and not self.ai_progress_active:
                        model = self.ai_model_var.get()
                        size = self.original_img.size if self.original_img is not None else None
                        self._begin_ai_task(model, size)
                    if numeric > 0:
                        stage_span = self.ai_progress_stage_end - self.ai_progress_stage_start
                        self.ai_progress_target = max(
                            self.ai_progress_target,
                            self.ai_progress_stage_start + stage_span * numeric / 100.0,
                        )
                        if numeric >= 100:
                            self.ai_progress_value = max(
                                self.ai_progress_value,
                                self.ai_progress_target,
                            )
                    self._draw_ai_progress()
                    self._schedule_ai_progress_tick()
            except Exception:
                pass
        self._queue_ui(_update)

    def toggle_advanced_drawer(self):
        if self.adv_drawer.winfo_manager():
            self.adv_drawer.pack_forget()
            self.adv_header.config(text="Advanced Color Keyer")
        else:
            self.adv_drawer.pack(fill=tk.X, pady=5)
            self.adv_header.config(text="Hide Advanced Color Key")

    def toggle_ai_refine_box_mode(self):
        if self.mode == "ai_refine_box":
            self.mode = "picker"
            self.canvas.config(cursor="crosshair")
            self.refine_tool_btn.config(style='Action.TButton')
            if self.crop_rect:
                self.canvas.delete(self.crop_rect)
                self.crop_rect = None
            self.cleanup_btn.config(state=tk.DISABLED)
        else:
            self.mode = "ai_refine_box"
            self.canvas.config(cursor="tcross")
            self.refine_tool_btn.config(style='Success.TButton')
            if self.crop_rect:
                self.canvas.delete(self.crop_rect)
                self.crop_rect = None
            self.cleanup_btn.config(state=tk.DISABLED)

    def run_local_ai_cleanup(self):
        if not self.original_img or not self.crop_rect:
            return
        
        coords = self.canvas.coords(self.crop_rect)
        if not coords or len(coords) < 4:
            return
        
        cx1, cy1, cx2, cy2 = coords
        ix1, iy1 = self.canvas_to_image(cx1, cy1)
        ix2, iy2 = self.canvas_to_image(cx2, cy2)
        
        w_orig, h_orig = self.original_img.size
        left = max(0, min(w_orig - 1, int(min(ix1, ix2))))
        right = max(0, min(w_orig, int(max(ix1, ix2))))
        top = max(0, min(h_orig - 1, int(min(iy1, iy2))))
        bottom = max(0, min(h_orig, int(max(iy1, iy2))))
        
        box_width = right - left
        box_height = bottom - top
        if box_width < 2 or box_height < 2:
            return
            
        box = (left, top, right, bottom)
        selected_model = self.ai_model_var.get()
        if not _model_is_cached(selected_model):
            info = AI_MODEL_INFO[selected_model]
            missing_size = _missing_ai_model_bytes(selected_model)
            cache_dir = _model_cache_path(
                _ai_component_models(selected_model)[0]
            ).parent
            approved = messagebox.askyesno(
                "Download AI Model?",
                f"{info['label']} needs to download {missing_size / (1024 * 1024):.0f} MB before regional refinement.\n\n"
                f"It will be stored in:\n{cache_dir}\n\n"
                "Download the model now?",
                parent=self.root,
            )
            if not approved:
                return
        
        self.canvas.delete(self.crop_rect)
        self.crop_rect = None
        self.mode = "picker"
        self.canvas.config(cursor="crosshair")
        self.refine_tool_btn.config(style='Action.TButton')
        self.cleanup_btn.config(state=tk.DISABLED)
        
        self._begin_ai_task(selected_model, (box_width, box_height))
        self._set_ai_stage_ui("Preparing region", 0.0, 8.0, 0.5)
        self.update_ai_status("AI: RUNNING LOCAL CLEANUP...")
        
        def local_cleanup_thread():
            if self._is_shutting_down():
                return
            try:
                if not _model_is_cached(selected_model):
                    self._set_ai_stage("Downloading model", 8.0, 24.0, 60.0)
                    _download_ai_model(
                        selected_model,
                        status_callback=self.update_ai_status,
                        progress_callback=self.update_ai_progress,
                    )
                cropped_img = self.original_img.crop(box)
                
                from rembg import remove, new_session
                import onnxruntime as ort
                session_is_cached = self._ai_sessions_are_cached(selected_model)
                self._set_ai_stage(
                    "Loading AI model",
                    24.0,
                    36.0,
                    1.0 if session_is_cached else 7.0,
                )
                self.update_ai_status("AI: INFERENCE ON CROP...")
                inference_expected = max(
                    2.0,
                    self._estimated_ai_seconds(
                        selected_model,
                        (box_width, box_height),
                    ) * 0.55,
                )
                self._set_ai_stage(
                    "Refining selected region",
                    36.0,
                    94.0,
                    inference_expected,
                )
                local_mask, local_duration = self._run_ai_selection_mask(
                    cropped_img,
                    selected_model,
                    remove,
                    new_session=new_session,
                    ort=ort,
                    status_callback=self.update_ai_status,
                )
                self._record_ai_inference_duration(
                    selected_model,
                    local_duration / 0.55,
                )
                if self._is_shutting_down():
                    return
                self._set_ai_stage("Applying cleanup", 94.0, 100.0, 0.6)
                
                def _on_success():
                    desc = f"AI Cleanup Region: ({left}, {top}) to ({right}, {bottom})"
                    action = {
                        "type": "ai_cleanup",
                        "box": box,
                        "local_mask": local_mask,
                        "desc": desc
                    }
                    self.actions.append(action)
                    self.rules_list.insert(tk.END, desc)
                    self.apply_actions()
                    self._clear_redo_stack()
                    self.update_preview()
                    
                    self._finish_ai_progress_item(final=True)
                    self.update_ai_status("ENGINE: READY")
                    
                self._queue_ui(_on_success)
            except Exception as e:
                if self._is_shutting_down():
                    return
                error_text = str(e)
                def _on_failed(message=error_text):
                    self._finish_ai_progress_item(final=True, error=True)
                    self.update_ai_status("ENGINE: ERROR", is_error=True)
                    messagebox.showerror("Local AI Refinement Failed", f"Local refinement failed:\n{message}")
                self._queue_ui(_on_failed)
                
        self._start_worker(local_cleanup_thread, "ai-local-cleanup")

    def _on_ai_model_display_changed(self, _event=None):
        selected = self._ai_model_display_to_value.get(
            self.ai_model_display_var.get(),
            DEFAULT_AI_MODEL,
        )
        if self.ai_model_var.get() != selected:
            self.ai_model_var.set(selected)

    def _on_ai_model_changed(self, *_):
        display_value = self._ai_model_value_to_display.get(self.ai_model_var.get())
        if display_value and self.ai_model_display_var.get() != display_value:
            self.ai_model_display_var.set(display_value)
        self._sync_force_ai_checkbox()
        self._release_unused_ai_sessions(self.ai_model_var.get())
        if hasattr(self, "ai_model_hint"):
            if self.ai_model_var.get() == FUSION_AI_MODEL:
                self.ai_model_hint.config(
                    text="Best overall · runs both models · adaptive fusion"
                )
            elif self.ai_model_var.get().startswith("birefnet"):
                self.ai_model_hint.config(
                    text="Clean silhouettes and green/blue-screen separation"
                )
            else:
                self.ai_model_hint.config(
                    text="Fast · preserves glow, particles, and fine effects"
                )

    def _sync_force_ai_checkbox(self):
        selected = self.ai_model_var.get()
        previous = getattr(self, "_last_ai_model", DEFAULT_AI_MODEL)
        policy = _ai_refinement_policy(selected)
        previous_policy = _ai_refinement_policy(previous)

        if previous_policy == "user" and policy != "user":
            self._isnet_force_ai_pref = self.force_ai_only_var.get()

        if policy == "pure":
            self.force_ai_only_var.set(True)
            self.force_ai_only_cb.state(["disabled", "selected"])
        elif policy == "adaptive":
            self.force_ai_only_var.set(False)
            self.force_ai_only_cb.state(["disabled", "!selected"])
        else:
            self.force_ai_only_cb.state(["!disabled"])
            if previous_policy != "user":
                self.force_ai_only_var.set(self._isnet_force_ai_pref)
            else:
                self._isnet_force_ai_pref = self.force_ai_only_var.get()

        self._last_ai_model = selected

    def run_ai_remove(self):
        if getattr(self, "edit_queue_active", False):
            if getattr(self, "edit_queue_running", False):
                return
            if not any(status == "queued" for status in self.batch_item_statuses):
                self.batch_item_statuses = ["queued"] * len(self.batch_files_list)
                self.edit_queue_results = {}
                self.edit_queue_errors = {}
                self.batch_thumbnail_cache = {}
            self.edit_queue_running = True
            self._process_next_edit_queue_item()
            return
        self._run_ai_remove_current()

    def _run_ai_remove_current(self):
        if not self.original_img:
            return
        
        selected_model = self.ai_model_var.get()
        source_img = self.original_img.copy()
        run_settings = {
            "tol": self.tol_var.get(),
            "soft": self.soft_var.get(),
            "contiguous": self.contiguous_var.get(),
            "clean_holes": self.clean_holes_var.get(),
            "force_ai_only": self.force_ai_only_var.get(),
        }
        info = AI_MODEL_INFO[selected_model]
        first_component = _ai_component_models(selected_model)[0]
        model_path = _model_cache_path(first_component)

        if not _model_is_cached(selected_model):
            size_mb = _missing_ai_model_bytes(selected_model) / (1024 * 1024)
            approved = messagebox.askyesno(
                "Download AI Model?",
                f"{info['label']} needs to download {size_mb:.0f} MB of model data before its first use.\n\n"
                f"It will be stored in:\n{model_path.parent}\n\n"
                "Images remain on this computer. Download the model now?",
                parent=self.root,
            )
            if not approved:
                self.update_ai_status("ENGINE: READY")
                if getattr(self, "edit_queue_running", False):
                    self._finish_edit_queue_run("Queue paused • model download was cancelled")
                return

        self._begin_ai_task(selected_model, source_img.size)
        
        def log_msg(msg):
            self.update_ai_status(f"AI: {msg}")
            print(f"AI Status: {msg}")
            
        def set_status(text):
            self.update_ai_status(text)
            
        def set_progress(val, mode='determinate'):
            self.update_ai_progress(val, mode=mode)
            
        def ai_thread():
            if self._is_shutting_down():
                return
            try:
                session_is_cached = self._ai_sessions_are_cached(selected_model)
                self._set_ai_stage(
                    "Loading AI model",
                    22.0,
                    34.0,
                    1.2 if session_is_cached else 7.0,
                )
                log_msg("SESSION: Initializing ORT...")
                from rembg import remove, new_session
                import onnxruntime as ort

                if session_is_cached:
                    log_msg("SESSION: Using cached ORT.")
                
                log_msg(f"INFERENCE: Running on {source_img.width}x{source_img.height}...")
                inference_expected = self._estimated_ai_seconds(
                    selected_model,
                    source_img.size,
                )
                self._set_ai_stage(
                    "Removing background",
                    34.0,
                    82.0,
                    inference_expected,
                )
                def inference_progress(index, total, _component):
                    if total <= 1:
                        return
                    start = 34.0 + 48.0 * index / total
                    end = 34.0 + 48.0 * (index + 1) / total
                    if index < total:
                        self._set_ai_stage(
                            f"Running model {index + 1} of {total}",
                            start,
                            end,
                            inference_expected / total,
                        )

                raw_mask, inference_duration = self._run_ai_selection_mask(
                    source_img,
                    selected_model,
                    remove,
                    new_session=new_session,
                    ort=ort,
                    progress_callback=inference_progress,
                    status_callback=log_msg,
                )
                if self._is_shutting_down():
                    return
                
                log_msg("INFERENCE: Mask generated.")
                self._set_ai_stage(
                    "Refining edges",
                    82.0,
                    96.0,
                    max(1.5, inference_duration * 0.18),
                )
                
                # Automated Missed Details Restoration Post-Processing
                try:
                    import cv2
                    import numpy as np
                    
                    log_msg("REFINEMENT: Checking for missed details...")
                    raw_mask_arr = (
                        np.asarray(raw_mask, dtype=np.float32) / 255.0
                    )
                    I = np.asarray(
                        source_img.convert("RGB"),
                        dtype=np.float32,
                    )
                    h, w = I.shape[:2]
                    
                    # Estimate background color from corners
                    corners = [I[0, 0], I[0, -1], I[-1, 0], I[-1, w - 1]]
                    B = np.median(corners, axis=0)
                    
                    # Compute chroma distance
                    d = np.sqrt(np.sum((I - B) ** 2, axis=-1))
                    tol_val = run_settings["tol"] * 2.55
                    
                    # Foreground color pixels that were cut out by the AI
                    M_missed = (d > tol_val) & (raw_mask_arr < 0.1)
                    bg_candidate_mask = M_missed.astype(np.uint8) * 255
                    
                    background_profile = _classify_uniform_background(I)
                    is_chroma_screen = background_profile["is_chroma_screen"]
                    
                    soft_val = max(run_settings["soft"], 10.0) * 2.55
                    lower_bound = tol_val - soft_val / 2.0
                    upper_bound = tol_val + soft_val / 2.0
                    chroma_alpha = np.clip((d - lower_bound) / np.maximum(upper_bound - lower_bound, 1.0), 0.0, 1.0)
                    
                    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bg_candidate_mask, connectivity=8)
                    A_composite = raw_mask_arr.copy()
                    has_changes = False
                    refinement_mask = np.zeros_like(raw_mask_arr, dtype=np.uint8)
                    refinement_mask_swirls = np.zeros_like(raw_mask_arr, dtype=np.uint8)
                    
                    if is_chroma_screen:
                        # On genuine chroma screens, flag missed foreground details
                        # for the bounded screen-aware refinement path.
                        # This runs instantly in milliseconds and avoids any crop-based AI inference calls.
                        for label in range(1, num_labels):
                            area = stats[label, cv2.CC_STAT_AREA]
                            if area >= 2:
                                mask_indices = (labels == label)
                                # A_composite[mask_indices] = np.maximum(A_composite[mask_indices], chroma_alpha[mask_indices])
                                refinement_mask[mask_indices] = 255
                                if area >= 100:
                                    refinement_mask_swirls[mask_indices] = 255
                                has_changes = True
                    # Non-chroma modes trust their completed full-image masks
                    # here. Lightweight dark-background recovery is a fast
                    # deterministic alpha-floor step in final post-processing;
                    # it does not launch additional model passes.
                    # Explicit Local AI Cleanup remains available for a region
                    # the user deliberately selects.
                            
                    if has_changes:
                        # Save dilated refinement masks
                        dil_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                        refinement_mask_dilated = cv2.dilate(refinement_mask, dil_kernel)
                        refinement_mask_swirls_dilated = cv2.dilate(refinement_mask_swirls, dil_kernel)
                        
                        self.last_refinement_mask = Image.fromarray(refinement_mask_dilated, "L")
                        self.last_refinement_mask_swirls = Image.fromarray(refinement_mask_swirls_dilated, "L")
                        
                        raw_mask = Image.fromarray((A_composite * 255.0).astype(np.uint8), "L")
                        log_msg("REFINEMENT: Missed details recovery complete.")
                    else:
                        self.last_refinement_mask = None
                        self.last_refinement_mask_swirls = None
                        log_msg("REFINEMENT: No missed regions detected.")
                except Exception as refine_err:
                    log_msg(f"REFINEMENT ERROR: {refine_err}")
                
                self._set_ai_stage("Finalizing", 96.0, 100.0, 0.8)
                self._queue_ui(self._on_ai_complete, raw_mask, selected_model, run_settings)
            except Exception as e:
                if self._is_shutting_down():
                    return
                import traceback
                err_str = str(e)
                tb_str = traceback.format_exc()
                log_msg(f"ERROR: {err_str}")
                try:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_path = _get_crash_log_dir() / f"ai_error_{timestamp}.log"
                    log_path.write_text(f"AI Thread Error:\n{err_str}\n\nTraceback:\n{tb_str}", encoding="utf-8")
                except Exception:
                    pass
                self._queue_ui(self._on_ai_failed, err_str)

        def start_ai_processing():
            try:
                set_status(f"Running {selected_model}...")
                set_progress(10, mode='indeterminate')
                log_msg("SYSTEM: Launching inference...")
                self._start_worker(ai_thread, "ai-background-removal")
            except Exception as e:
                log_msg(f"ERROR: Failed: {e}")

        def download_thread():
            if self._is_shutting_down():
                return
            try:
                self._set_ai_stage("Downloading model", 6.0, 22.0, 60.0)
                _download_ai_model(
                    selected_model,
                    status_callback=set_status,
                    progress_callback=lambda percent: set_progress(percent, mode="determinate"),
                )
                if self._is_shutting_down():
                    return
                log_msg("DOWNLOAD: Verified model data.")
                start_ai_processing()
            except Exception as ex:
                if self._is_shutting_down():
                    return
                err_str = str(ex)
                log_msg(f"ERROR: {err_str}")
                self._queue_ui(self._on_ai_failed, f"Download failed: {err_str}")

        self._set_ai_stage("Checking model", 0.0, 6.0, 0.6)
        log_msg("SYSTEM: Scanning cache...")
        if _model_is_cached(selected_model):
            log_msg("SYSTEM: Using cached model weights.")
            start_ai_processing()
        else:
            log_msg("SYSTEM: Cache miss.")
            self._start_worker(download_thread, "ai-model-download")

    def _on_ai_complete(self, raw_mask_img, selected_model=None, run_settings=None):
        self.update_ai_status("POST-PROCESS: Refining mask...")
        self._set_ai_stage_ui("Finalizing", 96.0, 100.0, 0.8)

        selected_model = selected_model or self.ai_model_var.get()
        run_settings = run_settings or {
            "tol": self.tol_var.get(),
            "soft": self.soft_var.get(),
            "contiguous": self.contiguous_var.get(),
            "clean_holes": self.clean_holes_var.get(),
            "force_ai_only": self.force_ai_only_var.get(),
        }
        desc = f"AI Auto-Remove (tol {run_settings['tol']:.1f} soft {run_settings['soft']:.1f})"
        if selected_model == FUSION_AI_MODEL:
            desc = "AI Auto-Remove (Fusion)"
        elif run_settings["force_ai_only"]:
            desc = "AI Auto-Remove (Pure AI Mode)"
        else:
            if run_settings["contiguous"]:
                desc += " contig"
                if run_settings["clean_holes"]:
                    desc += "+holes"
                
        action = {
            "type": "ai_remove",
            "desc": desc,
            "model_name": selected_model,
            "ai_mask": raw_mask_img,
            "refinement_mask": getattr(self, "last_refinement_mask", None),
            "refinement_mask_swirls": getattr(self, "last_refinement_mask_swirls", None),
            "tol": run_settings["tol"],
            "soft": run_settings["soft"],
            "contiguous": run_settings["contiguous"],
            "clean_holes": run_settings["clean_holes"],
            "force_ai_only": run_settings["force_ai_only"]
        }
        existing_idx = -1
        for idx, act in enumerate(self.actions):
            if act["type"] == "ai_remove":
                existing_idx = idx
                break
        if existing_idx != -1:
            self.actions[existing_idx] = action
            self.rules_list.delete(existing_idx)
            self.rules_list.insert(existing_idx, desc)
        else:
            self.actions.append(action)
            self.rules_list.insert(tk.END, desc)
        
        self.apply_actions()
        self._clear_redo_stack()

        if getattr(self, "edit_queue_running", False):
            index = self.batch_preview_index
            if index is not None and 0 <= index < len(self.batch_files_list):
                result = self.edited_img.copy()
                self.edit_queue_results[index] = result
                path = self.batch_files_list[index]
                self.batch_thumbnail_cache.pop(path, None)
                message = (
                    f"Complete • {index + 1} of {len(self.batch_files_list)} • "
                    f"{os.path.basename(path)}"
                )
                self._set_batch_preview_ui(index, result, "done", message)
            self._finish_ai_progress_item(final=False)
            self.update_ai_status("AI: ADVANCING QUEUE…")
            self.root.after(90, self._process_next_edit_queue_item)
            return

        self.update_preview()
        
        self._finish_ai_progress_item(final=True)
        self.update_ai_status("ENGINE: READY")

    def _on_ai_failed(self, err_msg):
        if getattr(self, "edit_queue_running", False):
            index = self.batch_preview_index
            if index is not None and 0 <= index < len(self.batch_files_list):
                self.batch_item_statuses[index] = "error"
                self.edit_queue_errors[index] = str(err_msg)
                path = self.batch_files_list[index]
                message = (
                    f"Failed • {index + 1} of {len(self.batch_files_list)} • "
                    f"{os.path.basename(path)}"
                )
                self._set_batch_preview_ui(
                    index,
                    self.original_img,
                    "error",
                    message,
                )
            self._finish_ai_progress_item(final=False, error=True)
            self.update_ai_status("AI: ITEM FAILED • CONTINUING", is_error=True)
            self.root.after(90, self._process_next_edit_queue_item)
            return
        self._finish_ai_progress_item(final=True, error=True)
        self.update_ai_status("ENGINE: ERROR", is_error=True)
        messagebox.showerror("AI Auto-Remove Failed", f"Failed to run AI background removal:\n{err_msg}\n\nPlease check your internet connection and try again.")

    def _safe_destroy_window(self, window):
        try:
            if window and window.winfo_exists():
                window.destroy()
        except Exception:
            pass

    def _pre_initialize_ai(self):
        if self._is_shutting_down():
            return
        # Do not preload BiRefNet. Its ONNX CPU arena can reserve several
        # gigabytes before the user starts a task. Sessions are loaded on demand
        # and the heavy model is released immediately after producing its mask.
        self.update_ai_status("ENGINE: READY")

    def _apply_ai_remove_mask(self, img):
        try:
            from rembg import remove, new_session
            import onnxruntime as ort
            selected_model = self.ai_model_var.get()
            if not hasattr(self, "ai_sessions"):
                self.ai_sessions = {}
            mask, _duration = self._run_ai_selection_mask(
                img,
                selected_model,
                remove,
                new_session=new_session,
                ort=ort,
            )
            return mask
        except Exception as e:
            from PIL import Image
            return Image.new("L", img.size, 255)

    def _apply_ai_remove(self, img):
        try:
            mask = self._apply_ai_remove_mask(img)
            selected_model = self.ai_model_var.get()
            action = {
                "model_name": selected_model,
                "ai_mask": mask,
                "tol": self.tol_var.get(),
                "soft": self.soft_var.get(),
                "contiguous": self.contiguous_var.get(),
                "clean_holes": self.clean_holes_var.get()
            }
            return self._apply_refined_ai_remove(img, action)
        except Exception as e:
            messagebox.showerror("AI Auto-Remove Failed", f"Failed to run AI background removal:\n{e}")
            return img

    def _apply_refined_ai_remove(self, img, action):
        import numpy as np
        from PIL import Image
        
        ai_mask = action.get("composite_mask", action["ai_mask"])
        force_ai_only = action.get("force_ai_only", False)
        refinement_mask = action.get("refinement_mask")
        refinement_mask_swirls = action.get("refinement_mask_swirls")
        
        if ai_mask.size != img.size:
            ai_mask = ai_mask.resize(img.size, Image.Resampling.BILINEAR)
        if refinement_mask is not None and refinement_mask.size != img.size:
            refinement_mask = refinement_mask.resize(img.size, Image.Resampling.BILINEAR)
        if refinement_mask_swirls is not None and refinement_mask_swirls.size != img.size:
            refinement_mask_swirls = refinement_mask_swirls.resize(img.size, Image.Resampling.BILINEAR)
            
        arr = np.array(img.convert("RGBA"))
        # Float32 is ample for 8-bit image matting and halves peak memory
        # compared with NumPy's float64 default. This matters while the
        # 973 MB BiRefNet session is still resident after inference.
        rgb = arr[:, :, :3].astype(np.float32)
        h, w = rgb.shape[:2]
        
        background_profile = _classify_uniform_background(rgb)
        B = background_profile["background"]
        is_uniform_bg = background_profile["is_uniform"]
        is_chroma_screen = background_profile["is_chroma_screen"]
        
        A_ai = np.asarray(ai_mask, dtype=np.float32) / np.float32(255.0)
        raw_A_ai = A_ai.copy()
        # Defined for every processing branch. Screen-aware recovery updates
        # this map; pure matting and complex-background paths leave it zero.
        detail_recovery_amount = np.zeros_like(A_ai, dtype=np.float32)
        
        # Chroma-AI Hybrid Matting on solid backgrounds, safe blur on complex ones
        try:
            import cv2
            
            def guided_filter_mono(I_guide, p, r, eps):
                mean_I = cv2.boxFilter(I_guide, -1, (2*r+1, 2*r+1))
                mean_p = cv2.boxFilter(p, -1, (2*r+1, 2*r+1))
                mean_Ip = cv2.boxFilter(I_guide * p, -1, (2*r+1, 2*r+1))
                cov_Ip = mean_Ip - mean_I * mean_p
                mean_II = cv2.boxFilter(I_guide * I_guide, -1, (2*r+1, 2*r+1))
                var_I = mean_II - mean_I * mean_I
                a = cov_Ip / (var_I + eps)
                b = mean_p - a * mean_I
                mean_a = cv2.boxFilter(a, -1, (2*r+1, 2*r+1))
                mean_b = cv2.boxFilter(b, -1, (2*r+1, 2*r+1))
                q = mean_a * I_guide + mean_b
                return np.clip(q, 0.0, 1.0)

            I_gray = (
                cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY)
                .astype(np.float32)
                / np.float32(255.0)
            )
            action_model = action.get("model_name", self.ai_model_var.get())
            is_birefnet = (
                "birefnet" in action_model
                or action_model == FUSION_AI_MODEL
            )
            filter_r = 3  # Edge-preserving smoothing for both models
            filter_eps = 0.01
            is_gradient_chroma = background_profile["is_gradient_chroma"]

            if is_chroma_screen:
                # Color distance is reliable on a uniform screen and can recover
                # tiny detached effects that segmentation models score too softly.
                d = np.sqrt(np.sum((rgb - B) ** 2, axis=-1))

                # Segmentation models can confidently fill an opening enclosed by
                # the subject even when that opening is still the solid screen
                # (for example, the cyan gap between overlapping cards).  Recover
                # those holes from color evidence, but only when the near-screen
                # region is connected to an image edge.  This avoids deleting a
                # detached foreground effect that happens to share the key color.
                tol_distance = action.get("tol", 20.0) * 2.55
                screen_seed_distance = np.clip(
                    tol_distance * 0.25,
                    3.0,
                    18.0,
                )
                near_screen = (d <= screen_seed_distance).astype(np.uint8)
                (
                    screen_label_count,
                    screen_labels,
                    _screen_stats,
                    _screen_centroids,
                ) = cv2.connectedComponentsWithStats(
                    near_screen,
                    connectivity=8,
                )
                border_screen_labels = np.unique(
                    np.concatenate(
                        (
                            screen_labels[0, :],
                            screen_labels[-1, :],
                            screen_labels[:, 0],
                            screen_labels[:, -1],
                        )
                    )
                )
                border_screen_labels = border_screen_labels[
                    border_screen_labels != 0
                ]
                if screen_label_count > 1 and border_screen_labels.size:
                    connected_screen_mask = np.isin(
                        screen_labels,
                        border_screen_labels,
                    )
                else:
                    connected_screen_mask = np.zeros((h, w), dtype=bool)

                # Identify background type (Green vs Blue) based on B
                if B[1] > B[0] and B[1] > B[2]:
                    key_idx = 1
                    other_indices = [0, 2]
                elif B[2] > B[0] and B[2] > B[1]:
                    key_idx = 2
                    other_indices = [0, 1]
                else:
                    key_idx = np.argmax(B)
                    other_indices = [i for i in range(3) if i != key_idx]

                # Calculate intensity-independent normalized key dominance
                sum_rgb = np.maximum(1.0, np.sum(rgb, axis=-1, keepdims=True))
                norm_rgb = rgb / sum_rgb
                key_diff_norm = norm_rgb[:, :, key_idx] - np.maximum(norm_rgb[:, :, other_indices[0]], norm_rgb[:, :, other_indices[1]])

                # Grow the border-connected screen basin using chromaticity
                # rather than raw RGB distance. Shadows and translucent spill
                # can be much darker than the sampled screen while retaining its
                # color ratio. A gradual alpha ceiling removes that spill
                # without cutting into purple or otherwise contrasting wisps.
                background_chroma = B / max(float(np.sum(B)), 1.0)
                screen_chroma_distance = np.sqrt(
                    np.sum(
                        (norm_rgb - background_chroma[None, None, :]) ** 2,
                        axis=-1,
                    )
                )
                screen_chroma_candidates = (
                    screen_chroma_distance < 0.35
                ).astype(np.uint8)
                (
                    _chroma_label_count,
                    chroma_labels,
                    _chroma_stats,
                    _chroma_centroids,
                ) = cv2.connectedComponentsWithStats(
                    screen_chroma_candidates,
                    connectivity=8,
                )
                border_chroma_labels = np.unique(
                    np.concatenate(
                        (
                            chroma_labels[0, :],
                            chroma_labels[-1, :],
                            chroma_labels[:, 0],
                            chroma_labels[:, -1],
                        )
                    )
                )
                border_chroma_labels = border_chroma_labels[
                    border_chroma_labels != 0
                ]
                if border_chroma_labels.size:
                    connected_screen_chroma_mask = np.isin(
                        chroma_labels,
                        border_chroma_labels,
                    )
                else:
                    connected_screen_chroma_mask = np.zeros(
                        (h, w),
                        dtype=bool,
                    )
                screen_chroma_alpha_cap = np.clip(
                    (screen_chroma_distance - 0.03) / (0.32 - 0.03),
                    0.0,
                    1.0,
                )
                enclosed_pocket_cleanup_mask = np.zeros(
                    (h, w),
                    dtype=bool,
                )

                def suppress_screen_pockets(alpha):
                    """Cap border spill and small screen-colored swirl pockets."""
                    nonlocal enclosed_pocket_cleanup_mask
                    cleaned_alpha = np.where(
                        connected_screen_chroma_mask,
                        np.minimum(alpha, screen_chroma_alpha_cap),
                        alpha,
                    )

                    # Some background pockets are completely enclosed by thin
                    # effect strokes, so they cannot be reached by the border
                    # flood above. Use any still-visible, near-exact screen
                    # pixels as conservative seeds, then clean only a narrow
                    # chroma-similar neighborhood around them. Thick card borders
                    # keep this expansion out of legitimate interior artwork.
                    enclosed_screen_seeds = (
                        near_screen.astype(bool)
                        & ~connected_screen_mask
                        & (cleaned_alpha > 0.25)
                    )
                    if np.any(enclosed_screen_seeds):
                        pocket_radius = max(
                            2,
                            round(min(h, w) / 200.0),
                        )
                        pocket_kernel_size = pocket_radius * 2 + 1
                        pocket_neighborhood = cv2.dilate(
                            enclosed_screen_seeds.astype(np.uint8),
                            cv2.getStructuringElement(
                                cv2.MORPH_ELLIPSE,
                                (
                                    pocket_kernel_size,
                                    pocket_kernel_size,
                                ),
                            ),
                        ).astype(bool)
                        pocket_cleanup_mask = (
                            pocket_neighborhood
                            & screen_chroma_candidates.astype(bool)
                        )
                        enclosed_pocket_cleanup_mask = (
                            enclosed_pocket_cleanup_mask
                            | pocket_cleanup_mask
                        )
                        cleaned_alpha = np.where(
                            pocket_cleanup_mask,
                            np.minimum(
                                cleaned_alpha,
                                screen_chroma_alpha_cap,
                            ),
                            cleaned_alpha,
                        )

                    return cleaned_alpha

            if is_gradient_chroma:
                # A gradient/noisy screen cannot use RGB distance to one corner
                # sample: ordinary background pixels may be farther from B than
                # the translucent subject. Keep the AI matte as the subject
                # prior, then cap only pixels that retain the perimeter's
                # intensity-independent key dominance.
                A_ai = guided_filter_mono(
                    I_gray,
                    raw_A_ai,
                    r=filter_r,
                    eps=filter_eps,
                )
                base_ai_alpha = A_ai.copy()
                A_ai, gradient_key_alpha = _refine_gradient_chroma_alpha(
                    rgb,
                    A_ai,
                    key_idx,
                )

                rgb = _reconstruct_gradient_chroma_foreground(
                    rgb,
                    A_ai,
                    key_idx,
                )
            elif is_chroma_screen and not force_ai_only:
                # ═══ PyMatting-based Alpha Matting Pipeline ═══
                # Uses closed-form matting solver for smooth, physically accurate alpha
                
                # Image in [0,1] float64 for PyMatting (sRGB space — avoids bloom from linear conversion)
                img_norm = (rgb / 255.0).astype(np.float64)
                
                # Chroma distance (in 0-255 space for threshold compatibility)
                d = np.sqrt(np.sum((rgb - B) ** 2, axis=-1))
                tol_val = action.get("tol", 20.0) * 2.55
                
                # ── Model-Specific Threshold Calibration ──
                if is_birefnet:
                    weak_ai_threshold = 0.55
                    definite_ai_threshold = 0.985
                    harden_threshold = 0.97
                    
                    # Definite foreground for BiRefNet (stricter to avoid green fringes, but with chroma recovery for clear details)
                    def_fg = (
                        ((A_ai > definite_ai_threshold) & (d > tol_val * 1.2)) |   # Confident core
                        (d > tol_val * 3.0) |                                       # Pure chroma (clearly not bg)
                        ((A_ai > weak_ai_threshold) & (d > tol_val * 2.0))         # Moderate confidence + strong chroma
                    )
                    
                    # Definite background for BiRefNet
                    def_bg = (
                        (d < tol_val * 0.15) |
                        ((A_ai < 0.01) & (d < tol_val * 0.5))
                    )
                else:
                    weak_ai_threshold = 0.20
                    definite_ai_threshold = 0.95
                    harden_threshold = 0.85
                    
                    # Definite foreground for ISNet
                    def_fg = (
                        ((A_ai > definite_ai_threshold) & (d > tol_val * 1.0)) |
                        (d > tol_val * 2.5) |
                        ((A_ai > weak_ai_threshold) & (d > tol_val * 1.5))
                    )
                    
                    # Definite background for ISNet
                    def_bg = (
                        (d < tol_val * 0.15) |
                        ((A_ai < 0.10) & (d < tol_val * 0.5))
                    )
                
                # Moderate erosion sizes to prevent eating away thin details like swirls
                fg_erode_size = 3
                def_fg_eroded = cv2.erode(def_fg.astype(np.uint8), 
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (fg_erode_size, fg_erode_size))) > 0
                
                bg_erode_size = 5
                def_bg_eroded = cv2.erode(def_bg.astype(np.uint8),
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bg_erode_size, bg_erode_size))) > 0
                
                # Build trimap: 1.0 = foreground, 0.0 = background, 0.5 = unknown
                trimap = np.full((h, w), 0.5, dtype=np.float64)
                trimap[def_fg_eroded] = 1.0
                trimap[def_bg_eroded] = 0.0
                # Never let the closed-form solver fill a border-connected patch
                # whose color still matches the sampled screen.
                trimap[connected_screen_mask] = 0.0
                
                # ── Save Debug Images ──
                model_name = action.get("model_name", "model")
                try:
                    Image.fromarray(np.round(raw_A_ai * 255).astype(np.uint8)).save(f"debug_raw_{model_name}.png")
                    trimap_debug = np.zeros((h, w, 3), dtype=np.uint8)
                    trimap_debug[trimap == 0.0] = (255, 0, 0)      # background (red)
                    trimap_debug[trimap == 0.5] = (255, 255, 0)    # unknown (yellow)
                    trimap_debug[trimap == 1.0] = (0, 255, 0)      # foreground (green)
                    Image.fromarray(trimap_debug).save(f"debug_trimap_{model_name}.png")
                except Exception as e:
                    print(f"Debug saving failed: {e}")
                
                # ── Crop to unknown region for speed ──
                unknown_mask = (trimap > 0) & (trimap < 1)
                if np.any(unknown_mask):
                    from pymatting import estimate_alpha_cf, estimate_foreground_ml
                    
                    y_idx, x_idx = np.where(unknown_mask)
                    pad = 30
                    y1 = max(0, int(y_idx.min()) - pad)
                    y2 = min(h, int(y_idx.max()) + pad)
                    x1 = max(0, int(x_idx.min()) - pad)
                    x2 = min(w, int(x_idx.max()) + pad)
                    
                    img_crop = img_norm[y1:y2, x1:x2]
                    trimap_crop = trimap[y1:y2, x1:x2]
                    
                    # ── Run PyMatting alpha estimation ──
                    alpha_crop = estimate_alpha_cf(
                        img_crop, trimap_crop,
                        laplacian_kwargs={"epsilon": 1e-4}
                    )
                    
                    # Build full alpha from trimap (known regions keep 0/1) + matted unknown
                    A_ai = trimap.copy()
                    A_ai[y1:y2, x1:x2] = alpha_crop
                
                # ── Alpha hardening (interior only, away from boundaries) ──
                # Use distance transform to only harden pixels deep inside solid regions
                harden_dist = 4.0 if is_birefnet else 3.0
                solid_binary = (raw_A_ai > harden_threshold).astype(np.uint8)
                distance_inside = cv2.distanceTransform(solid_binary, cv2.DIST_L2, 5)
                confident_interior = (
                    (raw_A_ai > harden_threshold) & (d > tol_val * 1.5) & (distance_inside >= harden_dist)
                )
                A_ai = np.where(confident_interior & (A_ai > 0.8), 1.0, A_ai)
                
                # Kill weak alpha noise
                is_bg_noise = (A_ai < 0.02) | ((A_ai < 0.05) & (d < tol_val * 0.4))
                A_ai = np.where(is_bg_noise, 0.0, A_ai)
                
                # ── Morphological edge band antialiasing ──
                # Build edge band that spans BOTH sides of binary boundaries
                alpha_u8 = (np.clip(A_ai, 0, 1) * 255).astype(np.uint8)
                inside = (alpha_u8 >= 128).astype(np.uint8)
                edge_radius = max(1, round(min(h, w) / 1000))
                kernel_size = edge_radius * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                expanded = cv2.dilate(inside, kernel)
                contracted = cv2.erode(inside, kernel)
                edge_band = expanded != contracted
                
                # Apply Gaussian blur only within the edge band
                blurred = cv2.GaussianBlur(A_ai.astype(np.float32), (0, 0), sigmaX=0.75)
                A_ai = np.where(edge_band, blurred.astype(np.float32), A_ai)
                
                # ── SDF-based antialiasing for geometrically smooth contours ──
                binary = (A_ai >= 0.5).astype(np.uint8)
                dist_inside = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
                dist_outside = cv2.distanceTransform(1 - binary, cv2.DIST_L2, 5)
                signed_distance = dist_inside - dist_outside
                
                aa_width = 1.25
                alpha_sdf = np.clip(0.5 + signed_distance / (2.0 * aa_width), 0.0, 1.0)
                
                # Only replace hard boundaries with SDF, preserve genuine translucency
                boundary_band = np.abs(signed_distance) <= 2.0
                hard_region = (A_ai <= 0.05) | (A_ai >= 0.95)
                replace_mask = boundary_band & hard_region
                A_ai = np.where(replace_mask, alpha_sdf, A_ai)

                A_ai = suppress_screen_pockets(A_ai)
                
                # ── Color decontamination (proven original channel clamping approach) ──
                alpha_expanded = np.expand_dims(A_ai, axis=-1)
                F_decont = rgb.copy()
                key_val = F_decont[:, :, key_idx]
                other_idx1, other_idx2 = other_indices[0], other_indices[1]
                limit = np.maximum(F_decont[:, :, other_idx1], F_decont[:, :, other_idx2])
                
                subtracted = key_val - (1.0 - alpha_expanded[:, :, 0]) * B[key_idx]
                # Clamp key channel to prevent hue shift/purpling, but never increase it beyond original value
                F_decont[:, :, key_idx] = np.minimum(key_val, np.maximum(subtracted, limit))
                
                blend_modulated = np.clip(alpha_expanded / 0.02, 0.0, 1.0)
                rgb = F_decont * blend_modulated + rgb * (1.0 - blend_modulated)
            else:
                # Run Guided Filter directly on the raw AI mask on complex backgrounds (or pure AI mode)
                A_ai = guided_filter_mono(I_gray, A_ai, r=filter_r, eps=filter_eps)
                base_ai_alpha = A_ai.copy()
                detail_recovery_amount = np.zeros_like(A_ai)
                
                if is_chroma_screen and not force_ai_only:
                    if is_birefnet:
                        # BiRefNet is excellent on the main silhouette but often
                        # assigns very low alpha to detached sparkles and thin
                        # energy trails. Recover only pixels with strong evidence
                        # that they differ from the uniform screen. The stronger
                        # threshold for AI-unsupported pixels prevents background
                        # texture from leaking into the result.
                        tol_val = action.get("tol", 20.0) * 2.55
                        soft_val = max(action.get("soft", 0.0), 10.0) * 2.55
                        lower_bound = max(1.0, tol_val - soft_val / 2.0)
                        upper_bound = max(lower_bound + 1.0, tol_val + soft_val / 2.0)
                        chroma_detail_alpha = np.clip(
                            (d - lower_bound) / (upper_bound - lower_bound),
                            0.0,
                            1.0,
                        )
                        # Convert the color-distance contour to a spatial signed
                        # distance field. This produces a consistent antialiased
                        # edge on curved wisps instead of following per-pixel
                        # chroma fluctuations, which look stair-stepped.
                        chroma_binary = (d > upper_bound).astype(np.uint8)
                        chroma_distance_inside = cv2.distanceTransform(
                            chroma_binary,
                            cv2.DIST_L2,
                            5,
                        )
                        chroma_distance_outside = cv2.distanceTransform(
                            1 - chroma_binary,
                            cv2.DIST_L2,
                            5,
                        )
                        chroma_signed_distance = (
                            chroma_distance_inside - chroma_distance_outside
                        )

                        # Reconstruct recovered effects on a subpixel grid.
                        # Native-resolution distance fields inherit staircase
                        # corners and can split one-pixel diagonal tips before
                        # antialiasing ever sees them.  A 4x nearest-neighbour
                        # shape, followed by a 1-pixel-equivalent close, repairs
                        # only those tiny gaps.  Area downsampling then produces
                        # stable fractional coverage at curves and sharp tips.
                        sdf_scale = 4
                        chroma_binary_hi = cv2.resize(
                            chroma_binary,
                            (w * sdf_scale, h * sdf_scale),
                            interpolation=cv2.INTER_NEAREST,
                        )
                        chroma_binary_hi = cv2.morphologyEx(
                            chroma_binary_hi,
                            cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(
                                cv2.MORPH_ELLIPSE,
                                (5, 5),
                            ),
                        )
                        chroma_distance_inside_hi = cv2.distanceTransform(
                            chroma_binary_hi,
                            cv2.DIST_L2,
                            5,
                        )
                        chroma_distance_outside_hi = cv2.distanceTransform(
                            1 - chroma_binary_hi,
                            cv2.DIST_L2,
                            5,
                        )
                        chroma_sdf_alpha_hi = np.clip(
                            0.5
                            + (
                                chroma_distance_inside_hi
                                - chroma_distance_outside_hi
                            )
                            / (5.0 * sdf_scale),
                            0.0,
                            1.0,
                        )
                        chroma_sdf_alpha = cv2.resize(
                            chroma_sdf_alpha_hi,
                            (w, h),
                            interpolation=cv2.INTER_AREA,
                        )
                        strong_unsupported_detail = d > (upper_bound * 1.35)
                        confident_heavy = raw_A_ai > 0.50
                        distance_from_confident = cv2.distanceTransform(
                            (~confident_heavy).astype(np.uint8),
                            cv2.DIST_L2,
                            5,
                        )
                        recovery_region = (
                            (raw_A_ai < 0.30)
                            & (distance_from_confident > 2.0)
                            & ((raw_A_ai > 0.01) | strong_unsupported_detail)
                        )
                        recovered_detail_alpha = np.where(
                            recovery_region,
                            chroma_sdf_alpha,
                            0.0,
                        )
                        A_ai = np.maximum(A_ai, recovered_detail_alpha)

                        # Restore opacity only through the interior of genuine
                        # chroma shapes. Keeping a 2.5 px boundary untouched
                        # preserves BiRefNet's clean handle/silhouette edge while
                        # preventing wider wisps from looking washed out.
                        detail_interior = (
                            (chroma_distance_inside >= 2.5)
                            & ((raw_A_ai > 0.01) | strong_unsupported_detail)
                            & (A_ai > 0.05)
                        )
                        A_ai = np.where(detail_interior, 1.0, A_ai)

                        # Preserve one- and two-pixel cyan effect strokes that
                        # the guided filter can attenuate even when BiRefNet is
                        # highly confident. Use a tighter SDF only on pixels
                        # inside the existing contour, so this strengthens the
                        # hairline without widening it or affecting dark edges.
                        red_ch = rgb[:, :, 0]
                        green_ch = rgb[:, :, 1]
                        blue_ch = rgb[:, :, 2]
                        bright_cyan = (
                            (green_ch > 160.0)
                            & (blue_ch > 160.0)
                            & (np.minimum(green_ch, blue_ch) - red_ch > 20.0)
                        )
                        fine_hairline = (
                            (raw_A_ai > 0.90)
                            & bright_cyan
                            & (chroma_distance_inside > 0.0)
                            & (chroma_distance_inside < 2.5)
                        )
                        fine_hairline_alpha = np.clip(
                            0.5 + chroma_signed_distance / 4.0,
                            0.0,
                            1.0,
                        )
                        A_ai = np.maximum(
                            A_ai,
                            np.where(fine_hairline, fine_hairline_alpha, 0.0),
                        )
                        detail_recovery_amount = np.maximum(
                            A_ai - base_ai_alpha,
                            0.0,
                        )

                        # Refine different kinds of edges independently.  A
                        # global alpha remap destroys legitimate low-opacity
                        # artwork, especially the dark rims and fine cyan trails.
                        # Mild spatial averaging smooths those contours without
                        # changing their support.  Stronger fringe suppression is
                        # reserved for pixels that are screen-colored, weak in the
                        # original AI mask, and not restored by detail recovery.
                        contour_smoothed = cv2.GaussianBlur(
                            A_ai.astype(np.float32),
                            (0, 0),
                            sigmaX=0.6,
                            sigmaY=0.6,
                            borderType=cv2.BORDER_REPLICATE,
                        )
                        detail_preserving_alpha = (
                            A_ai.astype(np.float32) * 0.5
                            + contour_smoothed * 0.5
                        )

                        screen_fringe_alpha = np.clip(
                            (contour_smoothed - 0.35) / (0.90 - 0.35),
                            0.0,
                            1.0,
                        )
                        screen_fringe_alpha = (
                            screen_fringe_alpha
                            * screen_fringe_alpha
                            * (3.0 - 2.0 * screen_fringe_alpha)
                        )

                        screen_color_weight = np.clip(
                            (key_diff_norm - 0.08) / (0.20 - 0.08),
                            0.0,
                            1.0,
                        )
                        ai_uncertainty_weight = np.clip(
                            (0.55 - raw_A_ai) / (0.55 - 0.10),
                            0.0,
                            1.0,
                        )
                        recovered_detail_protection = np.clip(
                            detail_recovery_amount / 0.05,
                            0.0,
                            1.0,
                        )
                        fringe_cleanup_weight = (
                            screen_color_weight
                            * ai_uncertainty_weight
                            * (1.0 - recovered_detail_protection)
                        )
                        A_ai = (
                            detail_preserving_alpha
                            * (1.0 - fringe_cleanup_weight)
                            + screen_fringe_alpha * fringe_cleanup_weight
                        )

                        # Resolve only the remaining uncertainty band with a
                        # closed-form matte.  This is an edge solve, not a second
                        # segmentation pass.  Chroma-supported effects are
                        # restored afterward so detached wisps cannot disappear.
                        try:
                            from pymatting import estimate_alpha_cf

                            pre_matte_alpha = A_ai.copy()
                            trimap = np.full((h, w), 0.5, dtype=np.float64)
                            trimap[A_ai <= 0.05] = 0.0
                            trimap[A_ai >= 0.90] = 1.0
                            unknown_matte = trimap == 0.5
                            if np.any(unknown_matte):
                                matte_y, matte_x = np.where(unknown_matte)
                                matte_pad = 12
                                matte_y1 = max(0, int(matte_y.min()) - matte_pad)
                                matte_y2 = min(h, int(matte_y.max()) + matte_pad + 1)
                                matte_x1 = max(0, int(matte_x.min()) - matte_pad)
                                matte_x2 = min(w, int(matte_x.max()) + matte_pad + 1)

                                matte_crop = estimate_alpha_cf(
                                    (rgb[matte_y1:matte_y2, matte_x1:matte_x2] / 255.0).astype(np.float64),
                                    trimap[matte_y1:matte_y2, matte_x1:matte_x2],
                                    laplacian_kwargs={"epsilon": 1e-4},
                                )
                                resolved_alpha = trimap.copy()
                                resolved_alpha[
                                    matte_y1:matte_y2,
                                    matte_x1:matte_x2,
                                ] = matte_crop

                                chroma_detail_floor = (d > 75.0) & (A_ai > 0.03)
                                A_ai = np.maximum(
                                    resolved_alpha,
                                    np.where(chroma_detail_floor, A_ai, 0.0),
                                )
                                screen_matte_guard = np.clip(
                                    (key_diff_norm - 0.25) / (0.60 - 0.25),
                                    0.0,
                                    1.0,
                                )
                                screen_matte_guard = (
                                    screen_matte_guard
                                    * screen_matte_guard
                                    * (3.0 - 2.0 * screen_matte_guard)
                                )
                                A_ai = (
                                    A_ai * (1.0 - screen_matte_guard)
                                    + np.minimum(A_ai, pre_matte_alpha)
                                    * screen_matte_guard
                                )
                        except Exception as e:
                            print(f"Narrow-band matting error: {e}")

                    A_ai = suppress_screen_pockets(A_ai)

                    # Decontaminate solid background color bleed from edges safely
                    alpha_expanded = np.expand_dims(A_ai, axis=-1)
                    F_decont = rgb.copy()
                    key_val = F_decont[:, :, key_idx]
                    other_idx1, other_idx2 = other_indices[0], other_indices[1]
                    limit = np.maximum(F_decont[:, :, other_idx1], F_decont[:, :, other_idx2])
                    
                    # Recovered pixels use BiRefNet's original alpha for despill.
                    # Otherwise making a recovered pixel opaque would also protect
                    # its green-screen contamination from being removed.
                    color_cleanup_alpha = np.where(
                        detail_recovery_amount > 0.0,
                        base_ai_alpha,
                        A_ai,
                    )
                    subtracted = key_val - (1.0 - color_cleanup_alpha) * B[key_idx]
                    # Clamp key channel to prevent hue shift/purpling, but never increase it beyond original value
                    F_decont[:, :, key_idx] = np.minimum(key_val, np.maximum(subtracted, limit))
                    
                    blend_modulated = np.clip(alpha_expanded / 0.02, 0.0, 1.0)
                    rgb = F_decont * blend_modulated + rgb * (1.0 - blend_modulated)

                elif (
                    background_profile["kind"] == "dark"
                    and _uses_dark_background_recovery(action_model)
                    and not force_ai_only
                ):
                    # ISNet detects the silhouette and detached particles well,
                    # but can score dark translucent interiors too softly when
                    # the source itself has a nearly black/navy background.
                    # Recover alpha from distance to the sampled background, and
                    # only ever raise the network mask. The calibrated default
                    # reproduces the older high-quality lightweight behavior
                    # without any additional AI inference.
                    dark_distance = np.sqrt(
                        np.sum((rgb - B) ** 2, axis=-1)
                    )
                    tolerance_px = (
                        float(action.get("tol", 20.0)) * 2.55
                    )
                    dark_recovery_start = max(
                        8.0,
                        tolerance_px * 0.53,
                    )
                    dark_recovery_full = max(
                        dark_recovery_start + 32.0,
                        tolerance_px * 2.51,
                    )
                    dark_alpha_floor = np.clip(
                        (
                            dark_distance - dark_recovery_start
                        )
                        / (
                            dark_recovery_full
                            - dark_recovery_start
                        ),
                        0.0,
                        1.0,
                    )
                    A_ai = np.maximum(A_ai, dark_alpha_floor)

                # Guided filtering and matting can spread foreground alpha back
                # into exact screen-colored pixels.  Reassert this conservative
                # topology-backed background constraint for either solid-screen
                # pipeline.
                if is_chroma_screen and not force_ai_only:
                    A_ai = np.where(connected_screen_mask, 0.0, A_ai)
        except Exception as e:
            print(f"Hybrid matting error: {e}")
        
        F_final = rgb.copy()

        if (
            is_chroma_screen
            and "enclosed_pocket_cleanup_mask" in locals()
            and np.any(enclosed_pocket_cleanup_mask)
        ):
            # Alpha cleanup alone can leave the original cyan RGB visible in a
            # partially transparent pocket. Solve the foreground-over-screen
            # equation only in those detected pockets to recover the underlying
            # purple effect color without recoloring the rest of the artwork.
            source_rgb = arr[:, :, :3].astype(np.float32)
            pocket_alpha = np.clip(A_ai, 0.0, 1.0)
            pocket_unmixed_rgb = (
                source_rgb
                - (1.0 - pocket_alpha[:, :, None]) * B[None, None, :]
            ) / np.maximum(pocket_alpha[:, :, None], 0.05)
            pocket_unmixed_rgb = np.clip(
                pocket_unmixed_rgb,
                0.0,
                255.0,
            )
            F_final = np.where(
                enclosed_pocket_cleanup_mask[:, :, None],
                pocket_unmixed_rgb,
                F_final,
            )
        
        # Despill modulated by edge alpha — only apply in transition zones, preserve opaque interiors
        despill_transition = np.clip(
            1.0 - np.abs(A_ai * 2.0 - 1.0),
            0.0,
            1.0,
        )
        despill_low_alpha = np.sqrt(
            np.clip(1.0 - A_ai, 0.0, 1.0)
        )
        despill_edge_mask = np.maximum(
            despill_transition,
            despill_low_alpha,
        )

        # Spill can also survive well inside a confident AI silhouette when the
        # screen is visible through a small opening or is reflected by glossy
        # artwork. Edge alpha cannot identify that case. Add a conservative,
        # opacity-independent term based on chromaticity similarity to the
        # sampled screen: only strongly key-dominant, screen-hued pixels qualify.
        # This changes color only (never alpha), and coherent non-screen colors
        # such as cyan energy or green-blue artwork remain protected by the hue
        # distance and key-dominance gates.
        if is_chroma_screen:
            source_chroma = arr[:, :, :3].astype(np.float32)
            source_sum = np.sum(
                source_chroma,
                axis=-1,
                dtype=np.float32,
            )
            np.maximum(source_sum, np.float32(1.0), out=source_sum)
            source_chroma /= source_sum[:, :, None]
            screen_chroma = B / max(float(np.sum(B)), 1.0)
            screen_key_idx = int(np.argmax(B))
            screen_other_indices = [
                channel for channel in range(3)
                if channel != screen_key_idx
            ]
            opaque_key_dominance = (
                source_chroma[:, :, screen_key_idx]
                - np.maximum(
                    source_chroma[:, :, screen_other_indices[0]],
                    source_chroma[:, :, screen_other_indices[1]],
                )
            )
            # Reuse the chroma buffer after key dominance is measured instead
            # of allocating another full H×W×3 float image.
            source_chroma -= screen_chroma[None, None, :]
            np.square(source_chroma, out=source_chroma)
            opaque_screen_hue_distance = np.sqrt(
                np.sum(source_chroma, axis=-1, dtype=np.float32)
            )

            opaque_key_weight = np.clip(
                (opaque_key_dominance - 0.28) / (0.58 - 0.28),
                0.0,
                1.0,
            )
            opaque_key_weight = (
                opaque_key_weight
                * opaque_key_weight
                * (3.0 - 2.0 * opaque_key_weight)
            )
            opaque_hue_weight = np.clip(
                (0.37 - opaque_screen_hue_distance) / (0.37 - 0.17),
                0.0,
                1.0,
            )
            opaque_hue_weight = (
                opaque_hue_weight
                * opaque_hue_weight
                * (3.0 - 2.0 * opaque_hue_weight)
            )
            opaque_alpha_weight = np.clip(
                (A_ai - 0.70) / (0.95 - 0.70),
                0.0,
                1.0,
            )
            opaque_screen_spill = (
                opaque_key_weight
                * opaque_hue_weight
                * opaque_alpha_weight
                * 0.80
            )
            despill_edge_mask = np.maximum(
                despill_edge_mask,
                opaque_screen_spill,
            )

        if (
            is_chroma_screen
            and B[1] > B[0] + 15
            and B[1] > B[2] + 15
        ):
            # Green despill (edge-only)
            G_ch = F_final[:, :, 1].astype(np.float32)
            limit = np.maximum(
                F_final[:, :, 0].astype(np.float32),
                F_final[:, :, 2].astype(np.float32),
            )
            G_despilled = np.where(G_ch > limit, limit, G_ch)
            F_final[:, :, 1] = (G_ch * (1.0 - despill_edge_mask) + G_despilled * despill_edge_mask).astype(np.uint8)
        elif (
            is_chroma_screen
            and B[2] > B[0] + 15
            and B[2] > B[1] + 15
        ):
            # Blue despill (edge-only)
            B_ch = F_final[:, :, 2].astype(np.float32)
            limit = np.maximum(
                F_final[:, :, 0].astype(np.float32),
                F_final[:, :, 1].astype(np.float32),
            )
            B_despilled = np.where(B_ch > limit, limit, B_ch)
            F_final[:, :, 2] = (B_ch * (1.0 - despill_edge_mask) + B_despilled * despill_edge_mask).astype(np.uint8)

        # Reconstruct foreground color only where chroma recovery added alpha.
        # Alpha-only antialiasing cannot hide isolated dark/key-colored samples
        # on recovered wisps, but applying this repair to every ordinary edge
        # creates a bright outline around opaque artwork.  A normalized
        # convolution biased toward bright, opaque foreground estimates the
        # nearby clean color; the recovery gate leaves established silhouettes
        # and their intentional dark/pixel-art rims untouched.
        if (
            is_chroma_screen
            and (
                "birefnet" in action.get("model_name", self.ai_model_var.get())
                or action.get("model_name", self.ai_model_var.get())
                == FUSION_AI_MODEL
            )
        ):
            try:
                import cv2

                alpha_color = np.clip(A_ai.astype(np.float32), 0.0, 1.0)
                foreground_support = (alpha_color > 0.05).astype(np.uint8)
                distance_from_edge = cv2.distanceTransform(
                    foreground_support,
                    cv2.DIST_L2,
                    5,
                )

                rgb_unit = np.clip(
                    F_final.astype(np.float32) / 255.0,
                    0.0,
                    1.0,
                )
                brightness = np.max(rgb_unit, axis=2)
                clean_color_weight = (
                    np.power(alpha_color, 4.0)
                    * np.power(
                        np.clip((brightness - 0.15) / 0.45, 0.0, 1.0),
                        3.0,
                    )
                )
                color_weight_blurred = cv2.GaussianBlur(
                    clean_color_weight,
                    (0, 0),
                    sigmaX=6.0,
                    sigmaY=6.0,
                    borderType=cv2.BORDER_REPLICATE,
                )
                weighted_color_blurred = cv2.GaussianBlur(
                    rgb_unit * clean_color_weight[:, :, None],
                    (0, 0),
                    sigmaX=6.0,
                    sigmaY=6.0,
                    borderType=cv2.BORDER_REPLICATE,
                )
                reconstructed_color = weighted_color_blurred / np.maximum(
                    color_weight_blurred[:, :, None],
                    1e-4,
                )

                stable_edge_alpha = np.clip(
                    (alpha_color - 0.35) / (0.75 - 0.35),
                    0.0,
                    1.0,
                )
                stable_edge_alpha = (
                    stable_edge_alpha
                    * stable_edge_alpha
                    * (3.0 - 2.0 * stable_edge_alpha)
                )
                recovered_color_need = np.clip(
                    detail_recovery_amount.astype(np.float32) / 0.10,
                    0.0,
                    1.0,
                )
                recovered_color_need = (
                    recovered_color_need
                    * recovered_color_need
                    * (3.0 - 2.0 * recovered_color_need)
                )
                established_bright_edge = np.clip(
                    (brightness - 0.12) / (0.35 - 0.12),
                    0.0,
                    1.0,
                )
                established_bright_edge = (
                    established_bright_edge
                    * established_bright_edge
                    * (3.0 - 2.0 * established_bright_edge)
                )
                recovered_color_need = np.maximum(
                    recovered_color_need,
                    established_bright_edge,
                )
                edge_color_weight = (
                    np.clip((6.0 - distance_from_edge) / 5.0, 0.0, 1.0)
                    * stable_edge_alpha
                    * recovered_color_need
                )
                rgb_unit = (
                    rgb_unit * (1.0 - edge_color_weight[:, :, None])
                    + reconstructed_color * edge_color_weight[:, :, None]
                )
                F_final = np.clip(rgb_unit * 255.0, 0.0, 255.0)
            except Exception as e:
                print(f"Edge color reconstruction error: {e}")
            
        arr[:, :, :3] = F_final.astype(np.uint8)
        arr[:, :, 3] = np.round(np.clip(A_ai, 0, 1) * 255.0).astype(np.uint8)
        
        if self.protected_mask and not action.get("is_batch", False):
            before_arr = np.array(img.convert("RGBA"))
            for (x, y) in self.protected_mask:
                if 0 <= x < w and 0 <= y < h:
                    arr[y, x] = before_arr[y, x]
                    
        return Image.fromarray(arr, "RGBA").copy()

    def _setup_bg_dots(self):
        # Create a floating canvas for the selector dots in the top-left of the main preview canvas
        # 6 dots * 24px = 144px width, height 26px
        self.bg_dots_canvas = tk.Canvas(
            self.canvas_container,
            width=144,
            height=26,
            bg=self.BG_INPUT,
            highlightthickness=1,
            highlightbackground=self.COLOR_BORDER,
            bd=0
        )
        self.bg_dots_canvas.pack(side=tk.TOP, anchor=tk.W, padx=0, pady=(0, 6))
        
        self.bg_dots_canvas.bind("<Button-1>", self._on_dots_click)
        self.bg_dots_canvas.bind("<Motion>", self._on_dots_motion)
        self.bg_dots_canvas.bind("<Leave>", self._on_dots_leave)
        
        self.hovered_idx = None
        self._update_bg_dots()

    def _update_bg_dots(self):
        if not hasattr(self, "bg_dots_canvas") or self.bg_dots_canvas is None:
            return
            
        canvas = self.bg_dots_canvas
        canvas.delete("all")
        
        current_bg = self.preview_bg_var.get()
        choices = [
            "Checker (Dark)",
            "Checker (Light)",
            "Solid Dark",
            "Solid Light",
            "Chroma Green",
            "Custom Color..."
        ]
        
        is_custom_hex = current_bg.startswith("#")
        selected_idx = -1
        if is_custom_hex or current_bg == "Custom Color...":
            selected_idx = 5
        else:
            if current_bg in choices:
                selected_idx = choices.index(current_bg)
                
        r = 7
        y = 13
        
        for i in range(6):
            cx = 12 + i * 24
            
            # Draw dot backgrounds/fills
            if i == 0:
                # Checker (Dark)
                canvas.create_arc(cx-r, y-r, cx+r, y+r, start=0, extent=90, fill='#2c2c35', outline='')
                canvas.create_arc(cx-r, y-r, cx+r, y+r, start=90, extent=90, fill='#141418', outline='')
                canvas.create_arc(cx-r, y-r, cx+r, y+r, start=180, extent=90, fill='#2c2c35', outline='')
                canvas.create_arc(cx-r, y-r, cx+r, y+r, start=270, extent=90, fill='#141418', outline='')
                canvas.create_oval(cx-r, y-r, cx+r, y+r, outline='#3a3a4a', width=1)
            elif i == 1:
                # Checker (Light)
                canvas.create_arc(cx-r, y-r, cx+r, y+r, start=0, extent=90, fill='#ffffff', outline='')
                canvas.create_arc(cx-r, y-r, cx+r, y+r, start=90, extent=90, fill='#dcdcdc', outline='')
                canvas.create_arc(cx-r, y-r, cx+r, y+r, start=180, extent=90, fill='#ffffff', outline='')
                canvas.create_arc(cx-r, y-r, cx+r, y+r, start=270, extent=90, fill='#dcdcdc', outline='')
                canvas.create_oval(cx-r, y-r, cx+r, y+r, outline='#3a3a4a', width=1)
            elif i == 2:
                # Solid Dark (Black)
                canvas.create_oval(cx-r, y-r, cx+r, y+r, fill='#000000', outline='#3a3a4a', width=1)
            elif i == 3:
                # Solid Light (White)
                canvas.create_oval(cx-r, y-r, cx+r, y+r, fill='#ffffff', outline='#dcdcdc', width=1)
            elif i == 4:
                # Chroma Green
                canvas.create_oval(cx-r, y-r, cx+r, y+r, fill='#00ff00', outline='#00bb00', width=1)
            elif i == 5:
                # Custom Color (Rainbow or custom hex)
                if is_custom_hex:
                    canvas.create_oval(cx-r, y-r, cx+r, y+r, fill=current_bg, outline='#555566', width=1)
                else:
                    canvas.create_arc(cx-r, y-r, cx+r, y+r, start=0, extent=72, fill='#ff0055', outline='')
                    canvas.create_arc(cx-r, y-r, cx+r, y+r, start=72, extent=72, fill='#ffcc00', outline='')
                    canvas.create_arc(cx-r, y-r, cx+r, y+r, start=144, extent=72, fill='#00ff66', outline='')
                    canvas.create_arc(cx-r, y-r, cx+r, y+r, start=216, extent=72, fill='#0099ff', outline='')
                    canvas.create_arc(cx-r, y-r, cx+r, y+r, start=288, extent=72, fill='#aa00ff', outline='')
                    canvas.create_oval(cx-r, y-r, cx+r, y+r, outline='#3a3a4a', width=1)
            
            # Draw hover boundary
            if i == self.hovered_idx:
                canvas.create_oval(cx-r-1, y-r-1, cx+r+1, y+r+1, outline='#ffffff', width=1)
            
            # Draw selection glowy neon green outline
            if i == selected_idx:
                canvas.create_oval(cx-r-2, y-r-2, cx+r+2, y+r+2, outline=self.COLOR_ACCENT, width=1.5)

    def _on_dots_click(self, event):
        clicked_idx = round((event.x - 12) / 24)
        if 0 <= clicked_idx < 6:
            choices = [
                "Checker (Dark)",
                "Checker (Light)",
                "Solid Dark",
                "Solid Light",
                "Chroma Green",
                "Custom Color..."
            ]
            choice = choices[clicked_idx]
            self.preview_bg_var.set(choice)
            self._on_bg_combo_changed()

    def _on_dots_motion(self, event):
        idx = round((event.x - 12) / 24)
        if 0 <= idx < 6:
            cx = 12 + idx * 24
            cy = 13
            dist = ((event.x - cx)**2 + (event.y - cy)**2)**0.5
            if dist <= 9:
                if self.hovered_idx != idx:
                    self.hovered_idx = idx
                    self._update_bg_dots()
                return
        if self.hovered_idx is not None:
            self.hovered_idx = None
            self._update_bg_dots()

    def _on_dots_leave(self, event):
        if self.hovered_idx is not None:
            self.hovered_idx = None
            self._update_bg_dots()

    def _on_bg_combo_changed(self, event=None):
        choice = self.preview_bg_var.get()
        if choice == "Custom Color...":
            color_hex = colorchooser.askcolor(title="Select Custom Preview Background")[1]
            if color_hex:
                self.preview_custom_bg = color_hex
                self.preview_bg_var.set(color_hex)
            else:
                self.preview_bg_var.set("Checker (Dark)")
        self.update_preview()
        if hasattr(self, "_update_bg_dots"):
            self._update_bg_dots()

    def _apply_preview_background(self, image):
        image = image.convert("RGBA")
        choice = self.preview_bg_var.get()
        if choice == "Checker (Dark)":
            bg = self._checkerboard(
                image.size,
                cell=10,
                c1=(24, 24, 28, 255),
                c2=(36, 37, 44, 255),
            )
        elif choice == "Checker (Light)":
            bg = self._checkerboard(
                image.size,
                cell=10,
                c1=(255, 255, 255, 255),
                c2=(220, 220, 220, 255),
            )
        elif choice == "Solid Dark":
            bg = Image.new("RGBA", image.size, (8, 8, 12, 255))
        elif choice == "Solid Light":
            bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
        elif choice == "Chroma Green":
            bg = Image.new("RGBA", image.size, (0, 255, 0, 255))
        elif choice.startswith("#"):
            try:
                value = choice.lstrip("#")
                rgb = tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
                bg = Image.new("RGBA", image.size, rgb + (255,))
            except Exception:
                bg = self._checkerboard(image.size)
        else:
            bg = self._checkerboard(image.size)
        return Image.alpha_composite(bg, image)

    def _update_composition_preview_canvas(self):
        if not self.composition_layers:
            self.canvas.delete("all")
            width = max(10, self.canvas.winfo_width())
            height = max(10, self.canvas.winfo_height())
            self.canvas.create_text(
                width // 2,
                height // 2 - 12,
                text="Compose: drop two or more images here",
                fill=self.COLOR_TEXT,
                font=("Segoe UI Semibold", 16),
            )
            self.canvas.create_text(
                width // 2,
                height // 2 + 18,
                text="Each image becomes a movable, scalable layer.",
                fill=self.COLOR_MUTED,
                font=("Segoe UI", 9),
            )
            return
        if self.edited_img is None and self.composition_canvas_size:
            self.edited_img = Image.new(
                "RGBA",
                self.composition_canvas_size,
                (0, 0, 0, 0),
            )
        metrics = self._get_editor_canvas_metrics()
        if metrics is None:
            return
        live_interaction = bool(
            self.composition_drag_state
            or self.composition_control_history_pushed
        )
        display = self._render_composition_image(
            preview_size=(
                metrics["edited_display_w"],
                metrics["edited_display_h"],
            ),
            fast=live_interaction,
        )
        display = self._apply_preview_background(display)
        self._set_main_canvas_photo(display)
        self.canvas.delete("all")
        self._invalidate_canvas_image_item_ref()
        self._invalidate_brush_cursor_overlay_refs()
        self.canvas_image_item = self.canvas.create_image(
            metrics["center_x"],
            metrics["center_y"],
            image=self.photo,
            anchor="center",
        )

        self.composition_rotation_handle_canvas = None
        selected = self._selected_composition_layer()
        if selected is not None and selected.get("visible", True):
            x0, y0, x1, y1 = self._composition_layer_bounds(selected)
            canvas_scale = metrics["canvas_scale"]
            cx0 = metrics["edited_canvas_x"] + x0 * canvas_scale
            cy0 = metrics["edited_canvas_y"] + y0 * canvas_scale
            cx1 = metrics["edited_canvas_x"] + x1 * canvas_scale
            cy1 = metrics["edited_canvas_y"] + y1 * canvas_scale
            self.canvas.create_rectangle(
                cx0,
                cy0,
                cx1,
                cy1,
                outline=self.COLOR_ACCENT,
                width=2,
                dash=(5, 3),
                tags="composition_selection",
            )
            handle_size = 7
            for hx, hy in ((cx0, cy0), (cx1, cy0), (cx0, cy1), (cx1, cy1)):
                self.canvas.create_rectangle(
                    hx - handle_size,
                    hy - handle_size,
                    hx + handle_size,
                    hy + handle_size,
                    fill="#FFFFFF",
                    outline=self.COLOR_ACCENT,
                    width=2,
                    tags="composition_selection",
                )
            rotation_x = (cx0 + cx1) / 2.0
            rotation_y = cy0 - 28
            self.canvas.create_line(
                rotation_x,
                cy0,
                rotation_x,
                rotation_y + 7,
                fill=self.COLOR_ACCENT,
                width=2,
                tags="composition_selection",
            )
            self.canvas.create_oval(
                rotation_x - 8,
                rotation_y - 8,
                rotation_x + 8,
                rotation_y + 8,
                fill=self.BG_SURFACE,
                outline=self.COLOR_ACCENT,
                width=2,
                tags="composition_selection",
            )
            self.canvas.create_text(
                rotation_x,
                rotation_y,
                text="↻",
                fill="#FFFFFF",
                font=("Segoe UI Symbol", 8),
                tags="composition_selection",
            )
            self.composition_rotation_handle_canvas = (rotation_x, rotation_y)
        self.canvas.create_text(
            16,
            16,
            anchor="nw",
            text=f"COMPOSE  •  {len(self.composition_layers)} LAYER(S)",
            fill=self.COLOR_ACCENT,
            font=("Segoe UI Semibold", 9),
        )

    def _set_edit_queue_button(self, text="Remove Background", enabled=True):
        button = getattr(self, "ai_btn", None)
        if button is None:
            return
        try:
            button.config(text=text, state=tk.NORMAL if enabled else tk.DISABLED)
        except Exception:
            pass

    def _clear_edit_queue_state(self):
        if not getattr(self, "edit_queue_active", False):
            return
        self.edit_queue_active = False
        self.edit_queue_running = False
        self.edit_queue_results = {}
        self.edit_queue_errors = {}
        self.batch_files_list = []
        self.batch_item_statuses = []
        self.batch_preview_active = False
        self.batch_preview_image = None
        self.batch_preview_index = None
        self.batch_preview_status = ""
        self.batch_thumbnail_cache = {}
        self._set_edit_queue_button()
        self._hide_batch_filmstrip()

    def _start_edit_image_queue(self, paths):
        if getattr(self, "edit_queue_running", False):
            messagebox.showinfo(
                "AI Queue Running",
                "Wait for the current Edit queue to finish before replacing it.",
            )
            return False
        if not self._confirm_unsaved_changes("loading an image queue"):
            return False

        valid_paths = [
            path
            for path in paths
            if isinstance(path, str) and os.path.isfile(path)
        ]
        if not valid_paths:
            return False

        self._clear_edit_queue_state()
        self.edit_queue_active = True
        self.edit_queue_running = False
        self.edit_queue_results = {}
        self.edit_queue_errors = {}
        self.batch_files_list = list(valid_paths)
        self.batch_item_statuses = ["queued"] * len(valid_paths)
        self.batch_thumbnail_cache = {}

        # A multi-file Edit drop always stays in Edit. Compose remains an
        # explicit workspace chosen by the user.
        if hasattr(self, "left_notebook") and hasattr(self, "edit_tab"):
            try:
                self.left_notebook.select(self.edit_tab)
            except Exception:
                pass
        self.png_gif_mode.set(False)
        self.is_slicer_active = False
        self.is_composition_active = False

        first_loaded = self.open_image_from_path(
            valid_paths[0],
            confirm_replace=False,
            preserve_edit_queue=True,
        )
        if not first_loaded:
            self.batch_item_statuses[0] = "error"
            self.edit_queue_errors[0] = "Could not open image."
            first_image = None
        else:
            first_image = self.original_img.copy()

        message = (
            f"Queue ready • 1 of {len(valid_paths)} • "
            f"{os.path.basename(valid_paths[0])}"
        )
        self._set_batch_preview_ui(0, first_image, self.batch_item_statuses[0], message)
        self._set_edit_queue_button(
            f"Remove Background from {len(valid_paths)} Images",
            enabled=True,
        )
        return True

    def _finish_edit_queue_run(self, message):
        self.edit_queue_running = False
        self.batch_filmstrip_status_var.set(message)
        self.batch_preview_status = message
        self._set_edit_queue_button("Remove Background Again", enabled=True)
        self._render_batch_filmstrip()
        if self.ai_progress_active:
            self._finish_ai_progress_item(final=True)
        self.update_ai_status("ENGINE: READY")
        self.update_preview()

    def _process_next_edit_queue_item(self):
        if (
            not getattr(self, "edit_queue_active", False)
            or not getattr(self, "edit_queue_running", False)
            or self._is_shutting_down()
        ):
            return

        next_index = next(
            (
                index
                for index, status in enumerate(self.batch_item_statuses)
                if status == "queued"
            ),
            None,
        )
        if next_index is None:
            done_count = sum(status == "done" for status in self.batch_item_statuses)
            error_count = sum(status == "error" for status in self.batch_item_statuses)
            message = f"Queue complete • {done_count} succeeded"
            if error_count:
                message += f" • {error_count} failed"
            self._finish_edit_queue_run(message)
            return

        path = self.batch_files_list[next_index]
        if not self.open_image_from_path(
            path,
            confirm_replace=False,
            preserve_edit_queue=True,
        ):
            self.batch_item_statuses[next_index] = "error"
            self.edit_queue_errors[next_index] = "Could not open image."
            self.root.after(1, self._process_next_edit_queue_item)
            return

        message = (
            f"Removing background • {next_index + 1} of "
            f"{len(self.batch_files_list)} • {os.path.basename(path)}"
        )
        self._set_batch_preview_ui(
            next_index,
            self.original_img,
            "processing",
            message,
        )
        self._set_edit_queue_button(
            f"Processing {next_index + 1} of {len(self.batch_files_list)}…",
            enabled=False,
        )
        self._run_ai_remove_current()

    def on_batch_filmstrip_click(self, event):
        if (
            not getattr(self, "edit_queue_active", False)
            or getattr(self, "edit_queue_running", False)
            or not getattr(self, "batch_files_list", None)
        ):
            return
        card_w = 122
        gap = 8
        x = self.batch_filmstrip_canvas.canvasx(event.x) - 8
        if x < 0:
            return
        index = int(x // (card_w + gap))
        if not (0 <= index < len(self.batch_files_list)):
            return
        if (x % (card_w + gap)) > card_w:
            return

        path = self.batch_files_list[index]
        if not self.open_image_from_path(
            path,
            confirm_replace=False,
            preserve_edit_queue=True,
        ):
            return
        result = self.edit_queue_results.get(index)
        if result is not None:
            self.edited_img = result.copy()
            self.history = [self.edited_img.copy()]
        status = self.batch_item_statuses[index]
        image = result if result is not None else self.original_img
        message = (
            f"{status.title()} • {index + 1} of {len(self.batch_files_list)} • "
            f"{os.path.basename(path)}"
        )
        self._set_batch_preview_ui(index, image, status, message)

    def _show_batch_filmstrip(self):
        if hasattr(self, "bottom_filmstrip_frame"):
            self.bottom_filmstrip_frame.pack_forget()
        if hasattr(self, "batch_filmstrip_frame"):
            self.batch_filmstrip_frame.pack_forget()
            self.batch_filmstrip_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        self._render_batch_filmstrip()

    def _hide_batch_filmstrip(self):
        if hasattr(self, "batch_filmstrip_frame"):
            self.batch_filmstrip_frame.pack_forget()

    def _render_batch_filmstrip(self):
        canvas = getattr(self, "batch_filmstrip_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        self.batch_filmstrip_refs = []
        paths = list(getattr(self, "batch_files_list", []))
        if not paths:
            canvas.create_text(
                12,
                48,
                anchor="w",
                text="Add images to build the batch queue.",
                fill=self.COLOR_MUTED,
                font=("Segoe UI", 9),
            )
            canvas.configure(scrollregion=(0, 0, max(1, canvas.winfo_width()), 100))
            return
        card_w = 122
        gap = 8
        for index, path in enumerate(paths):
            x0 = 8 + index * (card_w + gap)
            y0 = 7
            status = (
                self.batch_item_statuses[index]
                if index < len(self.batch_item_statuses)
                else "queued"
            )
            is_current = index == self.batch_preview_index
            if status == "done":
                accent = self.COLOR_SUCCESS
            elif status == "error":
                accent = self.COLOR_DANGER
            elif status == "processing" or is_current:
                accent = self.COLOR_ACCENT
            else:
                accent = self.COLOR_BORDER_STRONG
            canvas.create_rectangle(
                x0,
                y0,
                x0 + card_w,
                y0 + 82,
                fill=self.BG_SURFACE,
                outline=accent,
                width=2 if is_current else 1,
            )
            thumbnail = self.batch_thumbnail_cache.get(path)
            if thumbnail is None:
                try:
                    result = (
                        self.edit_queue_results.get(index)
                        if getattr(self, "edit_queue_active", False)
                        else None
                    )
                    if result is not None:
                        thumb = result.copy().convert("RGBA")
                    elif background_profile["kind"] == "complex":
                        with Image.open(path) as source:
                            thumb = source.convert("RGBA")
                    thumb.thumbnail((64, 52), Image.Resampling.LANCZOS)
                    thumbnail = ImageTk.PhotoImage(self._apply_preview_background(thumb))
                    self.batch_thumbnail_cache[path] = thumbnail
                except Exception:
                    thumbnail = None
            if thumbnail is not None:
                self.batch_filmstrip_refs.append(thumbnail)
                canvas.create_image(x0 + 34, y0 + 31, image=thumbnail, anchor="center")
            filename = os.path.basename(path)
            if len(filename) > 16:
                filename = filename[:13] + "..."
            canvas.create_text(
                x0 + 70,
                y0 + 18,
                anchor="w",
                text=f"{index + 1}",
                fill=accent,
                font=("Segoe UI Semibold", 9),
            )
            canvas.create_text(
                x0 + 70,
                y0 + 36,
                anchor="w",
                text=status.upper(),
                fill=self.COLOR_TEXT,
                font=("Segoe UI Semibold", 8),
            )
            canvas.create_text(
                x0 + 6,
                y0 + 69,
                anchor="w",
                text=filename,
                fill=self.COLOR_MUTED,
                font=("Segoe UI", 8),
            )
        total_width = 16 + len(paths) * (card_w + gap)
        canvas.configure(scrollregion=(0, 0, total_width, 96))
        if self.batch_preview_index is not None:
            left = max(0, self.batch_preview_index * (card_w + gap) - card_w)
            canvas.xview_moveto(left / max(total_width, 1))

    def _set_batch_preview_ui(self, index, image, state, message):
        self.batch_preview_active = True
        self.batch_preview_index = index
        self.batch_preview_image = image.copy().convert("RGBA") if image is not None else None
        self.batch_preview_status = message
        while len(self.batch_item_statuses) < len(getattr(self, "batch_files_list", [])):
            self.batch_item_statuses.append("queued")
        if index is not None and 0 <= index < len(self.batch_item_statuses):
            self.batch_item_statuses[index] = state
        self.batch_filmstrip_status_var.set(message)
        self._show_batch_filmstrip()
        self.update_preview()

    def _update_batch_preview_canvas(self):
        width = max(10, self.canvas.winfo_width())
        height = max(10, self.canvas.winfo_height())
        self.canvas.delete("all")
        self._invalidate_canvas_image_item_ref()
        self._invalidate_brush_cursor_overlay_refs()
        image = self.batch_preview_image
        if image is None:
            self.canvas.create_text(
                width // 2,
                height // 2,
                text="Preparing batch queue…",
                fill=self.COLOR_TEXT,
                font=("Segoe UI Semibold", 16),
            )
            return
        preview = ImageOps.contain(
            image.convert("RGBA"),
            (max(1, width - 48), max(1, height - 70)),
            Image.Resampling.LANCZOS,
        )
        preview = self._apply_preview_background(preview)
        self._set_main_canvas_photo(preview)
        self.canvas_image_item = self.canvas.create_image(
            width // 2,
            height // 2 + 12,
            image=self.photo,
            anchor="center",
        )
        self.canvas.create_text(
            18,
            16,
            anchor="nw",
            text=self.batch_preview_status,
            fill=self.COLOR_ACCENT,
            font=("Segoe UI Semibold", 10),
        )

    def update_preview(self):
        if self.batch_preview_active:
            self._update_batch_preview_canvas()
            return

        if self.is_composition_active:
            self._update_composition_preview_canvas()
            return

        # In PNG→GIF mode, preview the aligned animation instead of the edited still image.
        if self.png_gif_mode.get():
            self._update_gif_preview_canvas()
            return
        
        # In Slicer mode, preview the slicer image with grid overlay
        if self.is_slicer_active and self.slicer_image is not None:
            self._update_slicer_preview_canvas()
            return
        
        if not self.edited_img:
            self.canvas.delete("all")
            w = max(10, self.canvas.winfo_width())
            h = max(10, self.canvas.winfo_height())
            card_w = min(560, max(320, w - 80))
            card_h = min(300, max(240, h - 100))
            x0 = (w - card_w) // 2
            y0 = (h - card_h) // 2
            x1 = x0 + card_w
            y1 = y0 + card_h

            self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=self.BG_SURFACE,
                outline=self.COLOR_BORDER_STRONG,
                width=1,
                dash=(8, 6),
                tags="welcome_msg",
            )
            cx = w // 2
            icon_y = y0 + 70
            self.canvas.create_oval(
                cx - 26,
                icon_y - 26,
                cx + 26,
                icon_y + 26,
                fill=self.BG_ELEVATED,
                outline=self.COLOR_BORDER,
                width=1,
                tags="welcome_msg",
            )
            self.canvas.create_line(
                cx,
                icon_y + 12,
                cx,
                icon_y - 11,
                fill=self.COLOR_ACCENT,
                width=3,
                arrow=tk.LAST,
                arrowshape=(8, 10, 4),
                tags="welcome_msg",
            )
            self.canvas.create_line(
                cx - 11,
                icon_y + 14,
                cx + 11,
                icon_y + 14,
                fill=self.COLOR_ACCENT,
                width=2,
                tags="welcome_msg",
            )
            self.canvas.create_text(
                cx,
                y0 + 125,
                text="Drop an image to begin",
                fill=self.COLOR_TEXT,
                font=('Segoe UI Semibold', 18),
                justify=tk.CENTER,
                tags="welcome_msg"
            )
            self.canvas.create_text(
                cx,
                y0 + 158,
                text="PNG, JPG, JPEG, WebP, BMP, GIF, or clipboard image",
                fill=self.COLOR_MUTED,
                font=('Segoe UI', 9),
                justify=tk.CENTER,
                tags="welcome_msg",
            )
            button_w = 142
            button_h = 38
            bx0 = cx - button_w // 2
            by0 = y0 + 190
            self._welcome_open_box = (bx0, by0, bx0 + button_w, by0 + button_h)
            self.canvas.create_rectangle(
                bx0,
                by0,
                bx0 + button_w,
                by0 + button_h,
                fill=self.COLOR_ACCENT,
                outline=self.COLOR_ACCENT_HOVER if hasattr(self, "COLOR_ACCENT_HOVER") else self.COLOR_ACCENT,
                width=1,
                tags="welcome_msg",
            )
            self.canvas.create_text(
                cx,
                by0 + button_h // 2,
                text="Open image",
                fill="#FFFFFF",
                font=('Segoe UI Semibold', 9),
                tags="welcome_msg",
            )
            self.canvas.create_text(
                cx,
                min(y1 - 24, by0 + button_h + 28),
                text="or press Ctrl+O",
                fill=self.COLOR_MUTED,
                font=('Segoe UI', 8),
                tags="welcome_msg",
            )
            return
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10:
            self.root.after(100, self.update_preview)
            return
        base_img = self.edited_img
        metrics = self._get_editor_canvas_metrics()
        if metrics is None:
            return
        live_brushing = self._is_live_brushing() and not metrics["side_by_side"]
        preview_resample = self._get_editor_preview_resample()
        preview_key = (metrics["display_w"], metrics["display_h"], base_img.width, base_img.height, metrics["side_by_side"])
        if live_brushing and not self.protected_mask and self.live_brush_preview_img is not None and self.live_brush_preview_key == preview_key:
            img = self.live_brush_preview_img
            scale_x, scale_y = self.live_brush_preview_scale
        else:
            if metrics["side_by_side"]:
                img = Image.new("RGBA", (metrics["display_w"], metrics["display_h"]), (0, 0, 0, 0))
                original_img = self.original_img.copy().convert("RGBA")
                if original_img.size != (metrics["original_display_w"], metrics["original_display_h"]):
                    original_img = original_img.resize((metrics["original_display_w"], metrics["original_display_h"]), preview_resample)

                if base_img.size == (metrics["edited_display_w"], metrics["edited_display_h"]):
                    edited_img = base_img.copy()
                else:
                    edited_img = base_img.resize((metrics["edited_display_w"], metrics["edited_display_h"]), preview_resample)

                scale_x = metrics["edited_display_w"] / base_img.width if base_img.width else 1.0
                scale_y = metrics["edited_display_h"] / base_img.height if base_img.height else 1.0

                if self.current_preview_rule:
                    edited_img = self._apply_color_removal_preview(
                        edited_img,
                        self.current_preview_rule,
                        self.tol_var.get(),
                        self.soft_var.get()
                    )

                if self.protected_mask:
                    px = edited_img.load()
                    for (x, y) in self.protected_mask:
                        sx = int(x * scale_x)
                        sy = int(y * scale_y)
                        if 0 <= sx < edited_img.width and 0 <= sy < edited_img.height:
                            r, g, b, a = px[sx, sy]
                            px[sx, sy] = (
                                min(255, int(r * 0.5 + 255 * 0.5)),
                                int(g * 0.5),
                                min(255, int(b * 0.5 + 255 * 0.5)),
                                a,
                            )

                original_x = int(round(metrics["original_canvas_x"] - metrics["offset_x"]))
                original_y = int(round(metrics["original_canvas_y"] - metrics["offset_y"]))
                edited_x = int(round(metrics["edited_canvas_x"] - metrics["offset_x"]))
                edited_y = int(round(metrics["edited_canvas_y"] - metrics["offset_y"]))
                img.paste(original_img, (original_x, original_y), original_img)
                img.paste(edited_img, (edited_x, edited_y), edited_img)

                divider_x = int(round((metrics["original_canvas_x"] - metrics["offset_x"]) - (metrics["panel_gap"] / 2.0)))
                draw = ImageDraw.Draw(img)
                draw.line((divider_x, 0, divider_x, metrics["display_h"]), fill=(90, 90, 90, 255), width=2)
                _draw_preview_panel_badge(draw, edited_x + 8, edited_y + 8, "Preview")
                _draw_preview_panel_badge(draw, original_x + 8, original_y + 8, "Original")
            else:
                if metrics["display_w"] == base_img.width and metrics["display_h"] == base_img.height:
                    img = base_img.copy()
                else:
                    img = base_img.resize((metrics["display_w"], metrics["display_h"]), preview_resample)

                scale_x = metrics["edited_display_w"] / base_img.width if base_img.width else 1.0
                scale_y = metrics["edited_display_h"] / base_img.height if base_img.height else 1.0

            if live_brushing and not self.protected_mask and not metrics["side_by_side"]:
                self.live_brush_preview_img = img
                self.live_brush_preview_key = preview_key
                self.live_brush_preview_scale = (scale_x, scale_y)
            else:
                self._invalidate_live_brush_preview_cache()

        if self.current_preview_rule and not live_brushing and not metrics["side_by_side"]:
            img = self._apply_color_removal_preview(
                img,
                self.current_preview_rule,
                self.tol_var.get(),
                self.soft_var.get()
            )

        # Visualize protected pixels with a colored overlay in the preview only
        if self.protected_mask and not live_brushing and not metrics["side_by_side"]:
            px = img.load()
            for (x, y) in self.protected_mask:
                sx = int(x * scale_x)
                sy = int(y * scale_y)
                if 0 <= sx < img.width and 0 <= sy < img.height:
                    r, g, b, a = px[sx, sy]
                    # Tint protected pixels slightly magenta while preserving alpha
                    px[sx, sy] = (min(255, int(r * 0.5 + 255 * 0.5)),
                                  int(g * 0.5),
                                  min(255, int(b * 0.5 + 255 * 0.5)),
                                  a)
        
        # Composite background color or pattern
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        
        bg_choice = self.preview_bg_var.get()
        if bg_choice == "Checker (Dark)":
            bg = self._checkerboard(img.size, cell=10, c1=(24, 24, 28, 255), c2=(36, 37, 44, 255))
            img = Image.alpha_composite(bg, img)
        elif bg_choice == "Checker (Light)":
            bg = self._checkerboard(img.size, cell=10, c1=(255, 255, 255, 255), c2=(220, 220, 220, 255))
            img = Image.alpha_composite(bg, img)
        elif bg_choice == "Solid Dark":
            bg = Image.new("RGBA", img.size, (8, 8, 12, 255))
            img = Image.alpha_composite(bg, img)
        elif bg_choice == "Solid Light":
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, img)
        elif bg_choice == "Chroma Green":
            bg = Image.new("RGBA", img.size, (0, 255, 0, 255))
            img = Image.alpha_composite(bg, img)
        elif bg_choice.startswith("#"):
            try:
                hex_str = bg_choice.lstrip('#')
                rgb = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
                bg = Image.new("RGBA", img.size, rgb + (255,))
                img = Image.alpha_composite(bg, img)
            except Exception:
                pass

        self._set_main_canvas_photo(img, reuse_existing=live_brushing and not self.protected_mask)
        if live_brushing and not self.protected_mask:
            self._show_canvas_photo(self.photo, metrics["center_x"], metrics["center_y"])
        else:
            self.canvas.delete("all")
            self._invalidate_canvas_image_item_ref()
            self._invalidate_brush_cursor_overlay_refs()
            self.canvas_image_item = self.canvas.create_image(metrics["center_x"], metrics["center_y"], image=self.photo, anchor="center")
        self._update_brush_cursor_overlay()

    def _checkerboard(self, size, cell=10, c1=(24, 24, 28, 255), c2=(36, 37, 44, 255)):
        w, h = size
        bg = Image.new("RGBA", (w, h), c1)
        draw = ImageDraw.Draw(bg)
        for y in range(0, h, cell):
            for x in range(0, w, cell):
                if ((x // cell) + (y // cell)) % 2 == 0:
                    draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=c2)
        return bg

    def _update_gif_preview_canvas(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10:
            self.root.after(100, self.update_preview)
            return
        if not self.gif_aligned_rgba:
            # Nothing loaded; clear canvas
            self.canvas.delete("all")
            self._invalidate_canvas_image_item_ref()
            self._invalidate_brush_cursor_overlay_refs()
            self.canvas.create_text(w//2, h//2, text="PNG→GIF: Load frames to preview", fill="#dddddd")
            return

        idx = int(max(0, min(self.gif_preview_index, len(self.gif_aligned_rgba) - 1)))
        frame = self.gif_aligned_rgba[idx].copy()

        # Composite on checkerboard for preview
        if self.gif_preview_checker.get():
            bg = self._checkerboard(frame.size)
            frame = Image.alpha_composite(bg, frame)

        if self.zoom_fit:
            frame = ImageOps.contain(frame, (w, h))
        else:
            frame = frame.resize((int(frame.width * self.zoom_level), int(frame.height * self.zoom_level)), Image.LANCZOS)

        self._set_main_canvas_photo(frame)
        self.canvas.delete("all")
        self._invalidate_canvas_image_item_ref()
        self._invalidate_brush_cursor_overlay_refs()
        self.canvas.create_image(w//2 + self.pan_x, h//2 + self.pan_y, image=self.photo, anchor="center")
        if self.gif_anchor.get() == "template" and getattr(self, "gif_aligned_template_box", None) is not None:
            al, at, ar, ab = self.gif_aligned_template_box
            cx0, cy0 = self.gif_image_to_canvas(al, at)
            cx1, cy1 = self.gif_image_to_canvas(ar, ab)
            self.canvas.create_rectangle(cx0, cy0, cx1, cy1, outline="#ff0000", width=2, dash=(4, 4))
        self._update_brush_cursor_overlay()

    def _gif_frame_total(self):
        if self.gif_aligned_rgba:
            return len(self.gif_aligned_rgba)
        return len(self.gif_frame_paths)

    def _ensure_gif_frame_omitted_state(self):
        total = len(self.gif_frame_paths)
        if len(self.gif_frame_omitted) < total:
            self.gif_frame_omitted.extend([False] * (total - len(self.gif_frame_omitted)))
        elif len(self.gif_frame_omitted) > total:
            self.gif_frame_omitted = self.gif_frame_omitted[:total]

    def _gif_frame_is_omitted(self, index: int):
        self._ensure_gif_frame_omitted_state()
        return 0 <= index < len(self.gif_frame_omitted) and bool(self.gif_frame_omitted[index])

    def _get_gif_active_indices(self):
        self._ensure_gif_frame_omitted_state()
        return [index for index, omitted in enumerate(self.gif_frame_omitted) if not omitted]

    def _gif_frame_label(self, index: int):
        if index < 0 or index >= len(self.gif_frame_paths):
            return f"{index + 1:03d}. Frame {index + 1}"
        name = os.path.basename(self.gif_frame_paths[index])
        if index < len(self.gif_src_images):
            width, height = self.gif_src_images[index].size
            return f"{index + 1:03d}. {name} ({width}x{height})"
        return f"{index + 1:03d}. {name}"

    def _get_gif_frame_name(self, index: int):
        if index < 0 or index >= len(self.gif_frame_paths):
            return f"Frame {index + 1}"
        return os.path.basename(self.gif_frame_paths[index])

    def _truncate_gif_caption(self, text: str, max_chars: int = 10):
        if len(text) <= max_chars:
            return text
        if max_chars <= 3:
            return text[:max_chars]
        return text[: max_chars - 3] + "..."

    def _get_gif_filmstrip_metrics(self):
        thumb_w = 46
        thumb_h = 46
        cell_w = 54
        cell_h = 78
        pad = 6
        return thumb_w, thumb_h, cell_w, cell_h, pad

    def _build_gif_thumbnail(self, image: Image.Image, omitted: bool = False):
        thumb_w, thumb_h, _cell_w, _cell_h, _pad = self._get_gif_filmstrip_metrics()
        thumb = Image.new("RGBA", (thumb_w, thumb_h), (0, 0, 0, 0))
        preview = image.copy().convert("RGBA")
        preview = ImageOps.contain(preview, (thumb_w, thumb_h))
        background = self._checkerboard((thumb_w, thumb_h), cell=6)
        if omitted:
            original_alpha = preview.getchannel("A")
            grayscale = ImageOps.grayscale(preview.convert("RGB")).convert("RGBA")
            grayscale.putalpha(original_alpha)
            preview = Image.blend(preview, grayscale, 0.72)
            preview = Image.alpha_composite(
                preview,
                Image.new("RGBA", preview.size, (210, 210, 210, 56)),
            )
            lut = [max(48, int(v * 0.68)) if v > 0 else 0 for v in range(256)]
            alpha = original_alpha.point(lut)
            preview.putalpha(alpha)
            background = Image.new("RGBA", (thumb_w, thumb_h), (194, 194, 194, 255))
        ox = (thumb_w - preview.width) // 2
        oy = (thumb_h - preview.height) // 2
        thumb.paste(preview, (ox, oy), preview)
        thumb = Image.alpha_composite(background, thumb)
        return ImageTk.PhotoImage(thumb)

    def _render_gif_filmstrip(self):
        if not hasattr(self, "gif_filmstrip_canvas"):
            return
        canvas = self.gif_filmstrip_canvas
        canvas.delete("all")
        self.gif_thumb_refs = []

        thumb_w, thumb_h, cell_w, cell_h, pad = self._get_gif_filmstrip_metrics()
        total = len(self.gif_frame_paths)
        if total <= 0:
            canvas.create_text(10, 28, text="Load PNG frames to populate the filmstrip", anchor="w", fill=self.COLOR_MUTED)
            canvas.configure(scrollregion=(0, 0, max(canvas.winfo_width(), 1), 92))
            return

        self._ensure_gif_frame_omitted_state()
        for index, image in enumerate(self.gif_src_images):
            x0 = pad + index * cell_w
            y0 = 8
            x1 = x0 + thumb_w
            y1 = y0 + thumb_h
            is_selected = index == self.gif_preview_index
            is_omitted = self._gif_frame_is_omitted(index)
            cell_fill = self.BG_INPUT if not is_selected else self.BG_SURFACE
            if is_omitted and not is_selected:
                cell_fill = self.BG_MAIN
            outline = self.COLOR_ACCENT if is_selected else self.COLOR_BORDER
            if is_omitted and not is_selected:
                outline = self.COLOR_MUTED
            outline_w = 2 if is_selected else 1
            canvas.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 28, fill=cell_fill, outline=outline, width=outline_w)
            thumb_photo = self._build_gif_thumbnail(image, omitted=is_omitted)
            self.gif_thumb_refs.append(thumb_photo)
            canvas.create_image(x0 + thumb_w // 2, y0 + thumb_h // 2, image=thumb_photo, anchor="center")
            label_fill = self.COLOR_MUTED if is_omitted else self.COLOR_TEXT
            canvas.create_text(x0 + thumb_w // 2, y1 + 9, text=str(index + 1), fill=label_fill, font=("Arial", 8, "bold"))
            stem = os.path.splitext(self._get_gif_frame_name(index))[0]
            caption = self._truncate_gif_caption(stem, max_chars=9)
            canvas.create_text(x0 + thumb_w // 2, y1 + 20, text=caption, fill=label_fill, font=("Arial", 7), anchor="n")
            if is_omitted:
                canvas.create_text(x0 + thumb_w // 2, y0 + 2, text="OMIT", fill=self.COLOR_DANGER, font=("Arial", 6, "bold"), anchor="n")

        if self.gif_dragging and self.gif_drag_target_index is not None:
            marker_index = max(0, min(self.gif_drag_target_index, total - 1))
            marker_x = pad + marker_index * cell_w - 3
            if self.gif_drag_index is not None and marker_index > self.gif_drag_index:
                marker_x += cell_w
            canvas.create_line(marker_x, 6, marker_x, cell_h + 10, fill=self.COLOR_ACCENT, width=3)

        scroll_w = pad * 2 + total * cell_w
        canvas.configure(scrollregion=(0, 0, max(scroll_w, canvas.winfo_width()), 92))

    def _get_gif_filmstrip_index_at(self, x_coord: float):
        total = len(self.gif_frame_paths)
        if total <= 0:
            return None
        _thumb_w, _thumb_h, cell_w, _cell_h, pad = self._get_gif_filmstrip_metrics()
        x = self.gif_filmstrip_canvas.canvasx(x_coord)
        if x < pad:
            return 0
        index = int((x - pad) // cell_w)
        return max(0, min(index, total - 1))

    def _reorder_gif_frames(self, from_index: int, to_index: int):
        total = len(self.gif_frame_paths)
        if total <= 1:
            return False
        self._ensure_gif_frame_omitted_state()
        from_index = max(0, min(from_index, total - 1))
        to_index = max(0, min(to_index, total - 1))
        if from_index == to_index:
            return False

        self._save_gif_state()
        moved_path = self.gif_frame_paths.pop(from_index)
        moved_src = self.gif_src_images.pop(from_index)
        moved_omitted = self.gif_frame_omitted.pop(from_index)
        self.gif_frame_paths.insert(to_index, moved_path)
        self.gif_src_images.insert(to_index, moved_src)
        self.gif_frame_omitted.insert(to_index, moved_omitted)

        if self.gif_aligned_rgba and len(self.gif_aligned_rgba) == total:
            moved_aligned = self.gif_aligned_rgba.pop(from_index)
            self.gif_aligned_rgba.insert(to_index, moved_aligned)

        current_index = self.gif_preview_index
        if current_index == from_index:
            current_index = to_index
        elif from_index < current_index <= to_index:
            current_index -= 1
        elif to_index <= current_index < from_index:
            current_index += 1

        self.gif_preview_index = current_index
        self._sync_gif_frame_ui()
        self.update_preview()
        return True

    def _refresh_gif_frame_list(self):
        if not hasattr(self, "gif_filmstrip_canvas"):
            return
        self._render_gif_filmstrip()
        self._sync_gif_frame_ui()

    def _sync_gif_frame_ui(self):
        total = self._gif_frame_total()
        self._ensure_gif_frame_omitted_state()
        if total > 0:
            self.gif_preview_index = int(max(0, min(self.gif_preview_index, total - 1)))
        else:
            self.gif_preview_index = 0

        summary_text = "No frames loaded"
        if self.gif_frame_paths:
            frame_word = "frame" if len(self.gif_frame_paths) == 1 else "frames"
            summary_text = f"{len(self.gif_frame_paths)} {frame_word} loaded"
            omitted_count = sum(1 for omitted in self.gif_frame_omitted if omitted)
            if omitted_count:
                active_count = len(self.gif_frame_paths) - omitted_count
                summary_text += f" | {omitted_count} omitted | {active_count} active"
            if self.gif_aligned_rgba:
                aligned_width, aligned_height = self.gif_aligned_rgba[0].size
                summary_text += f" | aligned {aligned_width}x{aligned_height}"

        current_text = "Frame 0 / 0"
        if total > 0:
            current_text = f"Frame {self.gif_preview_index + 1} / {total}"
            if self._gif_frame_is_omitted(self.gif_preview_index):
                current_text += " (omitted)"
        selected_name_text = "Selected file: -"
        if total > 0:
            selected_name_text = f"Selected file: {self._get_gif_frame_name(self.gif_preview_index)}"
            if self._gif_frame_is_omitted(self.gif_preview_index):
                selected_name_text += " (omitted)"

        if hasattr(self, "gif_frame_summary_label"):
            self.gif_frame_summary_label.config(text=summary_text)
        if hasattr(self, "gif_current_label"):
            self.gif_current_label.config(text=current_text)
        if hasattr(self, "gif_selected_name_label"):
            self.gif_selected_name_label.config(text=selected_name_text)
        if hasattr(self, "gif_prev_btn"):
            self.gif_prev_btn.state(["!disabled"] if total > 1 else ["disabled"])
        if hasattr(self, "gif_next_btn"):
            self.gif_next_btn.state(["!disabled"] if total > 1 else ["disabled"])

        self._render_gif_filmstrip()

    def gif_set_preview_index(self, index: int, update_scrub: bool = True, stop_playback: bool = False):
        total = self._gif_frame_total()
        if total <= 0:
            return False
        next_index = int(max(0, min(index, total - 1)))
        if stop_playback and self.gif_playing:
            self.gif_stop_play()
        self.gif_preview_index = next_index
        if update_scrub and hasattr(self, "gif_scrub"):
            try:
                self._gif_syncing_scrub = True
                self.gif_scrub.set(self.gif_preview_index)
            except Exception:
                pass
            finally:
                self._gif_syncing_scrub = False
        self._sync_gif_frame_ui()
        self.update_preview()
        return True

    def gif_step_frame(self, delta: int):
        if self._gif_frame_total() <= 0:
            return
        self.gif_set_preview_index(self.gif_preview_index + delta, stop_playback=True)

    def _get_next_active_gif_index(self, current_index: int, delta: int):
        active_indices = self._get_gif_active_indices()
        if not active_indices:
            return None
        direction = 1 if delta >= 0 else -1
        if current_index in active_indices:
            position = active_indices.index(current_index)
            return active_indices[(position + direction) % len(active_indices)]
        if direction > 0:
            for index in active_indices:
                if index > current_index:
                    return index
            return active_indices[0]
        for index in reversed(active_indices):
            if index < current_index:
                return index
        return active_indices[-1]

    def _build_duplicate_gif_frame_name(self, raw_name: str):
        name = os.path.basename(raw_name or "Frame")
        stem, ext = os.path.splitext(name)
        stem = stem or "Frame"
        ext = ext or ".png"
        return f"{stem} copy{ext}"

    def gif_delete_frame(self, index: int):
        total = len(self.gif_frame_paths)
        if total <= 0:
            return
        self._ensure_gif_frame_omitted_state()
        index = max(0, min(index, total - 1))
        self._save_gif_state()
        self.gif_stop_play()
        self.gif_frame_paths.pop(index)
        self.gif_src_images.pop(index)
        self.gif_frame_omitted.pop(index)
        self.gif_aligned_rgba = []
        if not self.gif_frame_paths:
            self.gif_clear_frames()
            return
        if self.gif_preview_index > index:
            self.gif_preview_index -= 1
        self.gif_preview_index = max(0, min(self.gif_preview_index, len(self.gif_frame_paths) - 1))
        self.gif_scrub.configure(from_=0, to=max(0, len(self.gif_frame_paths) - 1))
        self.gif_scrub.set(self.gif_preview_index)
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def gif_duplicate_frame(self, index: int):
        total = len(self.gif_frame_paths)
        if total <= 0:
            return
        self._ensure_gif_frame_omitted_state()
        index = max(0, min(index, total - 1))
        insert_at = index + 1
        self._save_gif_state()
        self.gif_stop_play()
        self.gif_frame_paths.insert(insert_at, self._build_duplicate_gif_frame_name(self.gif_frame_paths[index]))
        self.gif_src_images.insert(insert_at, self.gif_src_images[index].copy())
        self.gif_frame_omitted.insert(insert_at, False)
        self.gif_aligned_rgba = []
        self.gif_preview_index = insert_at
        self.gif_scrub.configure(from_=0, to=max(0, len(self.gif_frame_paths) - 1))
        self.gif_scrub.set(self.gif_preview_index)
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def gif_rename_frame(self, index: int):
        total = len(self.gif_frame_paths)
        if total <= 0:
            return
        self._ensure_gif_frame_omitted_state()
        index = max(0, min(index, total - 1))
        
        current_path = self.gif_frame_paths[index]
        current_name = os.path.basename(current_path)
        current_stem, ext = os.path.splitext(current_name)
        
        new_stem = simpledialog.askstring(
            "Rename Frame",
            f"Enter new name for frame {index + 1}:",
            parent=self.root,
            initialvalue=current_stem
        )
        if new_stem is None:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
            
        self._save_gif_state()
        dir_name = os.path.dirname(current_path)
        new_path = os.path.join(dir_name, new_stem + ext)
        new_path = new_path.replace("\\", "/")
        
        self.gif_frame_paths[index] = new_path
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def gif_mirror_frame(self, index: int, direction: str):
        total = len(self.gif_frame_paths)
        if total <= 0:
            return
        self._ensure_gif_frame_omitted_state()
        index = max(0, min(index, total - 1))
        
        self.gif_stop_play()
        img = self.gif_src_images[index]
        if direction == "horizontal":
            mirrored_img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif direction == "vertical":
            mirrored_img = img.transpose(Image.FLIP_TOP_BOTTOM)
        else:
            return
            
        self._save_gif_state()
        self.gif_src_images[index] = mirrored_img
        self.gif_aligned_rgba = []
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def gif_toggle_frame_omit(self, index: int):
        total = len(self.gif_frame_paths)
        if total <= 0:
            return
        self._ensure_gif_frame_omitted_state()
        index = max(0, min(index, total - 1))
        self._save_gif_state()
        self.gif_frame_omitted[index] = not self.gif_frame_omitted[index]
        self._sync_gif_frame_ui()
        if self.gif_playing and self._gif_frame_is_omitted(self.gif_preview_index):
            next_index = self._get_next_active_gif_index(self.gif_preview_index, 1)
            if next_index is None:
                self.gif_stop_play()
            else:
                self.gif_set_preview_index(next_index, stop_playback=False)

    def on_gif_filmstrip_context_menu(self, event):
        index = self._get_gif_filmstrip_index_at(event.x)
        if index is None:
            return
        self.gif_set_preview_index(index, stop_playback=True)
        if self.gif_filmstrip_menu is not None:
            try:
                self.gif_filmstrip_menu.destroy()
            except Exception:
                pass
        self.gif_filmstrip_menu = tk.Menu(self.root, tearoff=0)
        self.gif_filmstrip_menu.add_command(label="Delete Frame", command=lambda idx=index: self.gif_delete_frame(idx))
        omit_label = "Include Frame" if self._gif_frame_is_omitted(index) else "Omit Frame"
        self.gif_filmstrip_menu.add_command(label=omit_label, command=lambda idx=index: self.gif_toggle_frame_omit(idx))
        self.gif_filmstrip_menu.add_command(label="Duplicate Frame", command=lambda idx=index: self.gif_duplicate_frame(idx))
        self.gif_filmstrip_menu.add_command(label="Rename Frame", command=lambda idx=index: self.gif_rename_frame(idx))
        self.gif_filmstrip_menu.add_separator()
        self.gif_filmstrip_menu.add_command(label="Mirror Horizontally", command=lambda idx=index: self.gif_mirror_frame(idx, "horizontal"))
        self.gif_filmstrip_menu.add_command(label="Mirror Vertically", command=lambda idx=index: self.gif_mirror_frame(idx, "vertical"))
        try:
            self.gif_filmstrip_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.gif_filmstrip_menu.grab_release()

    def on_gif_filmstrip_press(self, event):
        index = self._get_gif_filmstrip_index_at(event.x)
        if index is None:
            return
        self.gif_drag_index = index
        self.gif_drag_target_index = index
        self.gif_drag_start_x = self.gif_filmstrip_canvas.canvasx(event.x)
        self.gif_drag_start_y = event.y
        self.gif_dragging = False
        self.gif_set_preview_index(index, stop_playback=True)

    def on_gif_filmstrip_drag(self, event):
        if self.gif_drag_index is None:
            return
        current_x = self.gif_filmstrip_canvas.canvasx(event.x)
        if abs(current_x - self.gif_drag_start_x) >= 6:
            self.gif_dragging = True
        if not self.gif_dragging:
            return
        self.gif_drag_target_index = self._get_gif_filmstrip_index_at(event.x)
        self._render_gif_filmstrip()

    def on_gif_filmstrip_release(self, event):
        if self.gif_drag_index is None:
            return
        if self.gif_dragging:
            target_index = self._get_gif_filmstrip_index_at(event.x)
            if target_index is not None:
                self._reorder_gif_frames(self.gif_drag_index, target_index)
        self.gif_drag_index = None
        self.gif_drag_target_index = None
        self.gif_dragging = False
        self._render_gif_filmstrip()

    def _should_handle_gif_arrow_key(self):
        if not self.png_gif_mode.get() or self._gif_frame_total() <= 0:
            return False
        focused = self.root.focus_get()
        if focused is None:
            return True
        widget_class = focused.winfo_class()
        if widget_class in ("Entry", "TEntry", "Text", "Spinbox", "TCombobox"):
            return False
        return True

    def on_global_left_key(self, _event=None):
        if not self._should_handle_gif_arrow_key():
            return None
        self.gif_step_frame(-1)
        return "break"

    def on_global_right_key(self, _event=None):
        if not self._should_handle_gif_arrow_key():
            return None
        self.gif_step_frame(1)
        return "break"

    def _update_slicer_preview_canvas(self):
        """Update the canvas with slicer preview and grid overlay."""
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10:
            self.root.after(100, self.update_preview)
            return
        if self.slicer_image is None:
            self.canvas.delete("all")
            self._invalidate_canvas_image_item_ref()
            self._invalidate_brush_cursor_overlay_refs()
            self.canvas.create_text(w//2, h//2, text="Slicer: Load an image to slice", fill="#dddddd")
            return

        # Get the preview image with grid overlay
        preview = self._draw_slicer_preview()
        if preview is None:
            return

        # Fit to canvas while maintaining aspect
        preview_w, preview_h = preview.size
        scale_fit = min(w / preview_w, h / preview_h, 1.0)
        if scale_fit < 1.0:
            new_w = max(1, int(preview_w * scale_fit))
            new_h = max(1, int(preview_h * scale_fit))
            preview = preview.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Add checkerboard background
        bg = self._checkerboard(preview.size)
        preview = Image.alpha_composite(bg, preview)

        # Draw slice-name overlays after final preview sizing so text stays readable.
        final_scale = preview.width / max(1, self.slicer_image.width)
        draw = ImageDraw.Draw(preview)
        self._draw_slicer_name_overlays(draw, final_scale)

        self._set_main_canvas_photo(preview)
        self.canvas.delete("all")
        self._invalidate_canvas_image_item_ref()
        self._invalidate_brush_cursor_overlay_refs()
        self.canvas.create_image(w//2, h//2, image=self.photo, anchor="center")
        self._update_brush_cursor_overlay()

    def on_left_tab_changed(self, _event=None):
        # Keep preview mode in sync with the selected left-panel tab.
        try:
            selected_id = self.left_notebook.select()
            selected = self.left_notebook.nametowidget(selected_id)
        except Exception:
            return

        if (
            selected != getattr(self, "edit_tab", None)
            and getattr(self, "edit_queue_running", False)
        ):
            try:
                self.left_notebook.select(self.edit_tab)
            except Exception:
                pass
            return
        if (
            selected != getattr(self, "edit_tab", None)
            and getattr(self, "edit_queue_active", False)
        ):
            self._clear_edit_queue_state()

        was_composition_active = self.is_composition_active
        if (
            was_composition_active
            and selected != getattr(self, "compose_tab", None)
            and self.composition_layers
        ):
            composite = self._render_composition_image()
            if composite is not None:
                self.edited_img = composite
        
        # Reset state flags
        self.is_slicer_active = False
        self.is_composition_active = False
        try:
            self.mode_combo.configure(state="readonly")
            self.brush_spin.configure(state="normal")
            self.compare_check.configure(state="normal")
        except Exception:
            pass

        # Hide bottom timeline by default, show it only for PNG->GIF tab
        if hasattr(self, "bottom_filmstrip_frame"):
            self.bottom_filmstrip_frame.pack_forget()

        if selected == getattr(self, "gif_tab", None):
            self.png_gif_mode.set(True)
            self.schedule_gif_preview_update()
            if hasattr(self, "bottom_filmstrip_frame") and not self.batch_preview_active:
                self.bottom_filmstrip_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        elif selected == getattr(self, "compose_tab", None):
            self.is_composition_active = True
            self.png_gif_mode.set(False)
            self.gif_stop_play()
            self.mode = "compose_select"
            self.canvas.config(cursor="arrow")
            try:
                self.mode_combo.configure(state="disabled")
                self.brush_spin.configure(state="disabled")
                self.compare_check.configure(state="disabled")
            except Exception:
                pass
            self._ensure_composition_seed()
            self._update_composition_output(mark_dirty=False)
        elif selected == getattr(self, "slicer_tab", None):
            self.is_slicer_active = True
            self.png_gif_mode.set(False)
            self.gif_stop_play()
            # If we have an edited image, sync it to slicer so modification workflows continue seamlessly
            if self.edited_img is not None:
                self._sync_editor_to_slicer()
            if hasattr(self, "slicer_use_manual") and self.slicer_use_manual.get():
                self.mode = "slicer_manual"
                self.canvas.config(cursor="crosshair")
            else:
                self.mode = "picker"
                self.canvas.config(cursor="crosshair")
            self.slicer_update_preview()
        else:
            self.png_gif_mode.set(False)
            self.gif_stop_play()
            self.mode = "picker"
            self.canvas.config(cursor="crosshair")
            self.update_preview()

    def _sync_editor_to_slicer(self):
        """Copies the current editor image state to the slicer."""
        if self.edited_img is None:
            return
        try:
            self.slicer_batch_images = []
            self.slicer_batch_active_idx = 0
            self.slicer_image = self.edited_img.copy()
            self.slicer_image_path = self.editor_image_path
            
            w, h = self.slicer_image.size
            name = os.path.basename(self.slicer_image_path) if self.slicer_image_path else "Edited Image"
            self.slicer_info_label.config(text=f"{name} ({w}×{h})")
            
            # Only rebuild names if dimensions changed radically or we want to be safe
            # But usually it's better to just ensure the grid is valid
            self.slicer_rebuild_names()
        except Exception as e:
            print(f"Slicer sync error: {e}")

    def enter_png_gif_mode(self):
        self.png_gif_mode.set(True)
        if hasattr(self, "left_notebook") and hasattr(self, "gif_tab"):
            try:
                self.left_notebook.select(self.gif_tab)
            except Exception:
                pass
        # Ensure preset is applied once when entering the mode
        self.apply_gif_preset(self.gif_preset.get(), refresh=False)
        self.schedule_gif_preview_update()
        # Prompt to load frames immediately if none
        if not self.gif_frame_paths:
            self.gif_load_frames()

    def exit_png_gif_mode(self):
        self.png_gif_mode.set(False)
        self.gif_stop_play()
        if hasattr(self, "left_notebook") and hasattr(self, "edit_tab"):
            try:
                self.left_notebook.select(self.edit_tab)
            except Exception:
                pass

    def gif_load_frames(self):
        paths = filedialog.askopenfilenames(
            title="Select PNG or WebP frames",
            filetypes=[
                ("PNG and WebP frames", "*.png *.webp"),
                ("PNG files", "*.png"),
                ("WebP files", "*.webp"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        self.png_gif_mode.set(True)
        if hasattr(self, "left_notebook") and hasattr(self, "gif_tab"):
            try:
                self.left_notebook.select(self.gif_tab)
            except Exception:
                pass
        self._save_gif_state()
        self.gif_frame_paths = sorted(list(paths), key=self._natural_sort_key)
        try:
            self.gif_src_images = [Image.open(p).convert("RGBA") for p in self.gif_frame_paths]
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open one or more images:\n{e}")
            self.gif_src_images = []
            self.gif_frame_paths = []
            return
        self.gif_aligned_rgba = []
        self.gif_preview_index = 0
        self.gif_template_box = None
        self.gif_aligned_template_box = None
        self.gif_template_frame_idx = None
        self.gif_scrub.configure(from_=0, to=max(0, len(self.gif_frame_paths) - 1))
        self.gif_scrub.set(0)
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def _load_multiple_gif_images(self, paths):
        self.png_gif_mode.set(True)
        if hasattr(self, "left_notebook") and hasattr(self, "gif_tab"):
            try:
                self.left_notebook.select(self.gif_tab)
            except Exception:
                pass
        self._save_gif_state()
        self.gif_frame_paths = sorted(list(paths), key=self._natural_sort_key)
        try:
            self.gif_src_images = [Image.open(p).convert("RGBA") for p in self.gif_frame_paths]
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open one or more images:\n{e}")
            self.gif_src_images = []
            self.gif_frame_paths = []
            return
        self.gif_aligned_rgba = []
        self.gif_preview_index = 0
        self.gif_template_box = None
        self.gif_aligned_template_box = None
        self.gif_template_frame_idx = None
        self.gif_scrub.configure(from_=0, to=max(0, len(self.gif_frame_paths) - 1))
        self.gif_scrub.set(0)
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def apply_gif_preset(self, preset_name: str, refresh: bool = True):
        # Apply a batch of settings without triggering multiple rebuilds.
        if self._gif_applying_preset:
            return
        self._gif_applying_preset = True
        try:
            name = str(preset_name).strip().lower()
            if name in ("character", "chars", "sprite"):
                # Good for character animation: keep feet planted.
                self.gif_anchor.set("bottom-center")
                self.gif_duration_ms.set(100)
                self.gif_alpha_threshold.set(1)
                self.gif_padding.set(0)
                self.gif_preview_checker.set(True)
                self.gif_preset.set("Character")
            elif name in ("vfx", "fx", "particle", "effect"):
                # VFX loops centered on centroid.
                self.gif_anchor.set("center")
                self.gif_duration_ms.set(80)
                self.gif_alpha_threshold.set(1)
                self.gif_padding.set(0)
                self.gif_preview_checker.set(True)
                self.gif_preset.set("VFX")
            elif name in ("ui", "hud", "menu"):
                # GUI elements: top-left anchored.
                self.gif_anchor.set("top-left")
                self.gif_duration_ms.set(120)
                self.gif_alpha_threshold.set(1)
                self.gif_padding.set(0)
                self.gif_preview_checker.set(True)
                self.gif_preset.set("UI")
            else:
                # Default: VFX
                self.gif_anchor.set("center")
                self.gif_duration_ms.set(80)
                self.gif_alpha_threshold.set(1)
                self.gif_padding.set(0)
                self.gif_preview_checker.set(True)
                self.gif_preset.set("VFX")
        finally:
            self._gif_applying_preset = False

        if refresh:
            self.schedule_gif_preview_update()

    def gif_clear_frames(self):
        self._save_gif_state()
        self.gif_stop_play()
        self.gif_frame_paths = []
        self.gif_src_images = []
        self.gif_aligned_rgba = []
        self.gif_frame_omitted = []
        self.gif_preview_index = 0
        self.gif_template_box = None
        self.gif_aligned_template_box = None
        self.gif_template_frame_idx = None
        self.gif_scrub.configure(from_=0, to=0)
        self.gif_scrub.set(0)
        self._refresh_gif_frame_list()
        self.update_preview()

    def slicer_clear(self):
        self.slicer_image = None
        self.slicer_image_path = None
        self.slicer_boxes = []
        self.slicer_info_label.config(text="No image loaded")
        self.slicer_rebuild_names()
        self.slicer_update_preview()

    def _set_gif_frame_set(self, frame_names, frame_images, switch_to_tab: bool = True):
        self._save_gif_state()
        self.gif_stop_play()
        self.gif_frame_paths = list(frame_names)
        self.gif_src_images = [image.copy().convert("RGBA") for image in frame_images]
        self.gif_aligned_rgba = []
        self.gif_frame_omitted = [False] * len(self.gif_frame_paths)
        self.gif_preview_index = 0
        self.gif_template_box = None
        self.gif_aligned_template_box = None
        self.gif_template_frame_idx = None
        self.gif_scrub.configure(from_=0, to=max(0, len(self.gif_frame_paths) - 1))
        self.gif_scrub.set(0)
        self.png_gif_mode.set(True)
        if switch_to_tab and hasattr(self, "left_notebook") and hasattr(self, "gif_tab"):
            try:
                self.left_notebook.select(self.gif_tab)
            except Exception:
                pass
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def _sanitize_export_name(self, raw_name: str, fallback: str):
        name = (raw_name or "").strip()
        if not name:
            name = fallback
        name = os.path.basename(name)
        stem, _ext = os.path.splitext(name)
        stem = stem.strip() or fallback
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem)
        stem = stem.rstrip(". ")
        return stem or fallback

    def _get_gif_export_frames(self):
        active_indices = self._get_gif_active_indices()
        if not active_indices:
            return [], []
        source_frames = self.gif_aligned_rgba if self.gif_aligned_rgba else self.gif_src_images
        return active_indices, [source_frames[index].copy() for index in active_indices if index < len(source_frames)]

    def gif_export_frames(self):
        active_indices, frames = self._get_gif_export_frames()
        if not frames:
            messagebox.showwarning("PNG→GIF", "Load frames first, or include at least one omitted frame.")
            return
        folder = filedialog.askdirectory(title="Select Output Folder for Frames")
        if not folder:
            return
        export_format = self.gif_frame_export_format.get().upper()
        extension = _export_extension(export_format)

        # Check for conflicting file names
        existing_conflicts = []
        for export_index, frame in enumerate(frames):
            source_index = active_indices[export_index]
            fallback = f"frame_{export_index + 1:03d}"
            base_name = self._sanitize_export_name(self._get_gif_frame_name(source_index), fallback)
            output_path = os.path.join(folder, f"{base_name}{extension}")
            if os.path.exists(output_path):
                existing_conflicts.append(f"{base_name}{extension}")

        overwrite = False
        if existing_conflicts:
            msg = "The following file(s) already exist in the target folder:\n"
            if len(existing_conflicts) > 8:
                msg += "\n".join(existing_conflicts[:8]) + f"\n... and {len(existing_conflicts) - 8} more."
            else:
                msg += "\n".join(existing_conflicts)
            msg += "\n\nDo you want to overwrite the existing file(s)?"
            overwrite = messagebox.askyesno("Overwrite Existing Files?", msg)

        total = len(frames)
        for export_index, frame in enumerate(frames):
            source_index = active_indices[export_index]
            fallback = f"frame_{export_index + 1:03d}"
            base_name = self._sanitize_export_name(self._get_gif_frame_name(source_index), fallback)
            output_path = os.path.join(folder, f"{base_name}{extension}")
            if not overwrite:
                dedupe = 2
                while os.path.exists(output_path):
                    output_path = os.path.join(folder, f"{base_name}_{dedupe}{extension}")
                    dedupe += 1
            _save_transparent_image(frame, output_path, export_format)

        messagebox.showinfo("Exported", f"Exported {total} {export_format} frames to:\n{folder}")

    def on_gif_setting_changed(self):
        # Any setting change regenerates the aligned frames and refreshes preview
        self.schedule_gif_preview_update()

    def schedule_gif_preview_update(self):
        if self.gif_preview_after_id is not None:
            try:
                self.root.after_cancel(self.gif_preview_after_id)
            except Exception:
                pass
            self.gif_preview_after_id = None
        # Debounce so quick typing doesn't reprocess constantly
        self.gif_preview_after_id = self.root.after(140, self.rebuild_gif_preview)

    def rebuild_gif_preview(self):
        self.gif_preview_after_id = None
        if not self.png_gif_mode.get() or not self.gif_src_images:
            self.update_preview()
            return
        # Stop playback while rebuilding to avoid race
        was_playing = self.gif_playing
        self.gif_stop_play()

        alpha_threshold = int(self.gif_alpha_threshold.get())
        padding = int(self.gif_padding.get())
        anchor = str(self.gif_anchor.get())

        self.gif_aligned_rgba = self._align_rgba_frames(self.gif_src_images, alpha_threshold, anchor, padding)

        if not self.gif_aligned_rgba:
            self.gif_scrub.configure(from_=0, to=0)
        else:
            self.gif_preview_index = int(max(0, min(self.gif_preview_index, len(self.gif_aligned_rgba) - 1)))
            self.gif_scrub.configure(from_=0, to=max(0, len(self.gif_aligned_rgba) - 1))
            self.gif_scrub.set(self.gif_preview_index)

        self._sync_gif_frame_ui()
        self.update_preview()
        if was_playing:
            self.gif_start_play()

    def on_gif_scrub(self, value):
        if self._gif_syncing_scrub:
            return
        if self._gif_frame_total() <= 0:
            return
        try:
            index = int(round(float(value)))
        except Exception:
            return
        self.gif_set_preview_index(index, update_scrub=False, stop_playback=True)

    def gif_toggle_play(self):
        if self.gif_playing:
            self.gif_stop_play()
        else:
            self.gif_start_play()

    def gif_start_play(self):
        if not self.gif_aligned_rgba:
            return
        next_index = self._get_next_active_gif_index(self.gif_preview_index, 1)
        if next_index is None:
            self.gif_stop_play()
            return
        self.gif_playing = True
        try:
            self.gif_play_btn.config(text="Stop")
        except Exception:
            pass
        self._gif_play_tick()

    def gif_stop_play(self):
        self.gif_playing = False
        if self.gif_play_after_id is not None:
            try:
                self.root.after_cancel(self.gif_play_after_id)
            except Exception:
                pass
            self.gif_play_after_id = None
        try:
            self.gif_play_btn.config(text="Play")
        except Exception:
            pass

    def _gif_play_tick(self):
        if not self.gif_playing or not self.gif_aligned_rgba:
            return
        next_index = self._get_next_active_gif_index(self.gif_preview_index, 1)
        if next_index is None:
            self.gif_stop_play()
            return
        self.gif_set_preview_index(next_index, update_scrub=True, stop_playback=False)
        delay = int(max(1, self.gif_duration_ms.get()))
        self.gif_play_after_id = self.root.after(delay, self._gif_play_tick)

    def gif_save(self):
        active_indices, active_frames = self._get_gif_export_frames()
        if not active_frames:
            messagebox.showwarning("PNG→GIF", "Load frames first, or include at least one omitted frame.")
            return
        out_path = filedialog.asksaveasfilename(
            title="Save animated GIF",
            defaultextension=".gif",
            filetypes=[("GIF files", "*.gif")],
        )
        if not out_path:
            return

        duration_ms = int(max(1, self.gif_duration_ms.get()))
        gif_frames = [self._rgba_to_gif_frame(im) for im in active_frames]
        try:
            gif_frames[0].save(
                out_path,
                save_all=True,
                append_images=gif_frames[1:],
                duration=duration_ms,
                loop=0,
                optimize=False,
                disposal=2,
                transparency=255,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save GIF:\n{e}")
            return
        messagebox.showinfo("Exported", f"Exported GIF with {len(gif_frames)} frames:\n{os.path.basename(out_path)}")

    def toggle_zoom(self):
        self.zoom_fit = not self.zoom_fit
        if self.zoom_fit:
            self.zoom_level = 1.0
            self.pan_x = 0
            self.pan_y = 0
        self.update_preview()

    def on_mouse_wheel(self, e, force_ctrl=False, force_shift=False):
        # Check if in slicer mode using stable state flag
        if self.is_slicer_active and self.slicer_image is not None:
            # Handle slicer specific actions (Shift=Rows, Ctrl=Cols, Default=Zoom)
            # Use provided flags (from bind_all) OR check event state
            is_ctrl = force_ctrl or ((e.state & 0x4) != 0)
            is_shift = force_shift or ((e.state & 0x1) != 0)
            
            # Windows: e.delta is usually +-120. Linux: Button-4/5 logic is separate usually.
            delta = 1 if e.delta > 0 else -1

            if is_ctrl:
                # Adjust Columns (Vertical Slices)
                val = max(1, self.slicer_cols.get() + delta)
                self.slicer_cols.set(val)
                # Force preview update immediately (trace should handle it, but be sure)
                self.slicer_update_preview()
                return "break"
            elif is_shift:
                # Adjust Rows (Horizontal Slices)
                val = max(1, self.slicer_rows.get() + delta)
                self.slicer_rows.set(val)
                self.slicer_update_preview()
                return "break"

            # Handle slicer zoom
            if e.delta > 0:
                self.slicer_scale.set(min(5.0, self.slicer_scale.get() * 1.1))
            else:
                self.slicer_scale.set(max(0.1, self.slicer_scale.get() / 1.1))
            self.slicer_update_preview()
            return "break"
        
        # Original logic for non-slicer mode
        if e.delta > 0:
            self.zoom_level *= 1.1
        else:
            self.zoom_level /= 1.1
        self.zoom_level = max(0.1, min(10, self.zoom_level))
        self.zoom_fit = False
        self.update_preview()

    def start_pan(self, e):
        self.pan_start = (e.x, e.y)

    def do_pan(self, e):
        if self.pan_start:
            dx = e.x - self.pan_start[0]
            dy = e.y - self.pan_start[1]
            self.pan_x += dx
            self.pan_y += dy
            self.pan_start = (e.x, e.y)
            self.update_preview()

    def end_pan(self, e):
        self.pan_start = None

    def on_click(self, e):
        self.cursor_canvas_pos = (e.x, e.y)
        if self.batch_preview_active:
            return
        if self.is_composition_active:
            self._composition_begin_pointer_action(e)
            return
        if not self.edited_img and not self.png_gif_mode.get() and not self.is_slicer_active:
            box = getattr(self, "_welcome_open_box", None)
            if box is not None and box[0] <= e.x <= box[2] and box[1] <= e.y <= box[3]:
                self.open_image()
            return
        if self._use_side_by_side_preview() and not self._is_point_over_edited_panel(e.x, e.y):
            return
        if self.mode in ("crop", "gif_template", "slicer_manual", "ai_refine_box"):
            self._update_brush_cursor_overlay()
            self.crop_start = (e.x, e.y)
        elif self.mode == "lasso":
            self._update_brush_cursor_overlay()
            # Start free-form lasso: begin path with current point
            self.lasso_points = [(e.x, e.y)]
            if self.lasso_line is not None:
                self.canvas.delete(self.lasso_line)
                self.lasso_line = None

        elif self.mode == "picker":
            self._update_brush_cursor_overlay()
            self.pick_color_at(e.x, e.y, apply_rule=True)
        elif self.mode == "pick_swap":
            self._update_brush_cursor_overlay()
            self.do_pick_swap(e.x, e.y)
        else:
            self.brush(e.x, e.y)

    def do_pick_swap(self, cx, cy):
        if not self.edited_img:
            return
        x, y = self.canvas_to_image(cx, cy)
        x = int(x)
        y = int(y)
        if 0 <= x < self.edited_img.width and 0 <= y < self.edited_img.height:
            r, g, b, _ = self.edited_img.getpixel((x, y))
            new_col = colorchooser.askcolor(title="Choose replacement color")[1]
            if not new_col:
                self.mode = "picker"
                self.canvas.config(cursor="crosshair")
                return
            nr, ng, nb = int(new_col[1:3], 16), int(new_col[3:5], 16), int(new_col[5:7], 16)
            self.add_replace_action((r, g, b), (nr, ng, nb))
            self.mode = "picker"
            self.canvas.config(cursor="crosshair")

    def add_replace_action(self, old_color, new_color):
        tr, tg, tb = old_color
        nr, ng, nb = new_color
        tol = self.tol_var.get()
        desc = f"Replace #{tr:02x}{tg:02x}{tb:02x} with #{nr:02x}{ng:02x}{nb:02x}"
        self.actions.append({"type": "replace", "old": old_color, "new": new_color, "tol": tol, "desc": desc})
        self.rules_list.insert(tk.END, desc)
        self.apply_actions()
        self.future_history.clear()
        self.update_preview()

    def on_drag(self, e):
        self.cursor_canvas_pos = (e.x, e.y)
        if self.batch_preview_active:
            return
        if self.is_composition_active:
            self._composition_drag_pointer(e)
            return
        if self._use_side_by_side_preview() and not self._is_point_over_edited_panel(e.x, e.y):
            return
        if self.mode in ("crop", "gif_template", "slicer_manual", "ai_refine_box") and self.crop_start:
            self._update_brush_cursor_overlay()
            if self.crop_rect: self.canvas.delete(self.crop_rect)
            x0,y0 = self.crop_start
            outline_color = self.COLOR_ACCENT if self.mode in ("slicer_manual", "ai_refine_box") else "#00ff00"
            self.crop_rect = self.canvas.create_rectangle(x0,y0,e.x,e.y, outline=outline_color, width=2, dash=(4,4))
        elif self.mode == "lasso" and self.lasso_points:
            self._update_brush_cursor_overlay()
            # Free-form lasso: append current point to path as we drag
            self.lasso_points.append((e.x, e.y))
            if self.lasso_line is not None:
                self.canvas.delete(self.lasso_line)
            flat = [coord for pt in self.lasso_points for coord in pt]
            if len(flat) >= 4:
                self.lasso_line = self.canvas.create_line(*flat, fill="#00ffff", width=2, smooth=True)
        elif self.mode in ("erase","replace_single"):
            self.brush(e.x, e.y)

    def on_release(self, e):
        self.cursor_canvas_pos = (e.x, e.y)
        if self.is_composition_active:
            self._composition_end_pointer_action()
            return
        if self.mode == "crop" and self.crop_rect:
            self.do_crop()
        elif self.mode == "gif_template" and self.crop_rect:
            self.do_gif_template()
        elif self.mode == "slicer_manual" and self.crop_rect:
            self.do_slicer_manual_box(e.x, e.y)
        elif self.mode == "ai_refine_box" and self.crop_rect:
            self.cleanup_btn.config(state=tk.NORMAL)
        elif self.mode == "lasso" and self.lasso_points:
            # Finishing a lasso stroke finalizes the protected selection
            self._finalize_lasso_selection()
        elif self.mode in ("erase", "replace_single"):
            self._finalize_brush_stroke()
        self._update_brush_cursor_overlay()

    def do_slicer_manual_box(self, ex, ey):
        if self.crop_start and self.crop_rect:
            x0_img, y0_img = self.slicer_canvas_to_image(self.crop_start[0], self.crop_start[1])
            x1_img, y1_img = self.slicer_canvas_to_image(ex, ey)
            
            left_img = min(x0_img, x1_img)
            right_img = max(x0_img, x1_img)
            top_img = min(y0_img, y1_img)
            bottom_img = max(y0_img, y1_img)
            
            if self.slicer_image:
                w_orig, h_orig = self.slicer_image.size
                left_img = max(0.0, min(w_orig, left_img))
                right_img = max(0.0, min(w_orig, right_img))
                top_img = max(0.0, min(h_orig, top_img))
                bottom_img = max(0.0, min(h_orig, bottom_img))
                
                if (right_img - left_img) >= 2 and (bottom_img - top_img) >= 2:
                    self._save_slicer_state()
                    box_name = f"slice_{len(self.slicer_boxes)}"
                    self.slicer_boxes.append({
                        "box": (left_img, top_img, right_img, bottom_img),
                        "name": box_name
                    })
                    self.slicer_rebuild_names()
                    self.slicer_update_preview()
            
            self.canvas.delete(self.crop_rect)
            self.crop_rect = None
            self.crop_start = None

    def on_shift_click(self, e):
        # Shift + click quickly enters lasso mode and starts drawing
        self.start_lasso_mode()
        self.on_click(e)

    def on_drop(self, e):
        data = e.data
        if data:
            try:
                files = list(self.root.tk.splitlist(data))
            except Exception:
                files = data.strip("{}").split()
            
            valid_files = []
            for path in files:
                if not isinstance(path, str):
                    continue
                if os.path.exists(path):
                    valid_files.append(path)
            
            if not valid_files:
                return
                
            if len(valid_files) > 1:
                # Multiple files follow the active workspace. Edit creates an
                # AI queue; Compose only receives layers when explicitly active.
                is_slicer = getattr(self, "is_slicer_active", False)
                is_gif = getattr(self, "png_gif_mode", None) and self.png_gif_mode.get()
                is_composition = getattr(self, "is_composition_active", False)
                
                if not is_slicer and not is_gif:
                    # Fallback check of active tab
                    try:
                        selected_id = self.left_notebook.select()
                        selected = self.left_notebook.nametowidget(selected_id)
                        if selected == getattr(self, "slicer_tab", None):
                            is_slicer = True
                        elif selected == getattr(self, "gif_tab", None):
                            is_gif = True
                        elif selected == getattr(self, "compose_tab", None):
                            is_composition = True
                    except Exception:
                        pass
                
                if is_slicer:
                    self._load_multiple_slicer_images(valid_files)
                elif is_gif:
                    self._load_multiple_gif_images(valid_files)
                elif is_composition:
                    self.composition_add_paths(valid_files)
                else:
                    self._start_edit_image_queue(valid_files)
            else:
                if getattr(self, "is_composition_active", False):
                    self.composition_add_paths(valid_files)
                else:
                    self.open_image_from_path(valid_files[0])



    def canvas_to_image(self, cx, cy):
        metrics = self._get_editor_canvas_metrics()
        if metrics is None:
            return 0, 0
        x = (cx - metrics["edited_canvas_x"]) * metrics["edited_scale_x"]
        y = (cy - metrics["edited_canvas_y"]) * metrics["edited_scale_y"]
        return x, y

    def slicer_canvas_to_image(self, cx, cy):
        if self.slicer_image is None:
            return 0, 0
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10 or h < 10:
            return 0, 0
        
        w_orig, h_orig = self.slicer_image.size
        scale = self.slicer_scale.get()
        new_w = max(1, int(w_orig * scale))
        new_h = max(1, int(h_orig * scale))
        
        scale_fit = min(w / new_w, h / new_h, 1.0)
        final_w = max(1, int(new_w * scale_fit))
        final_h = max(1, int(new_h * scale_fit))
        
        img_x = w // 2 - final_w // 2
        img_y = h // 2 - final_h // 2
        
        x = (cx - img_x) * (w_orig / float(final_w))
        y = (cy - img_y) * (h_orig / float(final_h))
        return x, y

    def start_gif_template_mode(self):
        if not self.gif_src_images:
            messagebox.showwarning("No frames", "Please load PNG frames first.")
            return
        self.mode = "gif_template"
        self.canvas.config(cursor="crosshair")
        messagebox.showinfo("Select Anchor", "Drag a box on the canvas around the stationary part of the animation (e.g., character feet or head) to use as the alignment anchor.")

    def gif_canvas_to_image(self, cx, cy):
        if not self.gif_aligned_rgba:
            if not self.gif_src_images:
                return 0, 0
            idx = int(max(0, min(self.gif_preview_index, len(self.gif_src_images) - 1)))
            img_size = self.gif_src_images[idx].size
        else:
            idx = int(max(0, min(self.gif_preview_index, len(self.gif_aligned_rgba) - 1)))
            img_size = self.gif_aligned_rgba[idx].size

        frame_w, frame_h = img_size
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10 or h < 10:
            return 0, 0

        if self.zoom_fit:
            scale = min(w / frame_w, h / frame_h) if frame_w and frame_h else 1.0
        else:
            scale = self.zoom_level

        scaled_w = frame_w * scale
        scaled_h = frame_h * scale
        center_x = w // 2 + self.pan_x
        center_y = h // 2 + self.pan_y
        img_left = center_x - scaled_w // 2
        img_top = center_y - scaled_h // 2

        ix = (cx - img_left) / scale if scale else 0.0
        iy = (cy - img_top) / scale if scale else 0.0
        return ix, iy

    def do_gif_template(self):
        coords = self.canvas.coords(self.crop_rect)
        self.canvas.delete(self.crop_rect)
        self.crop_rect = None
        self.mode = "picker"
        self.canvas.config(cursor="arrow")

        if not coords or len(coords) != 4:
            return

        cx0, cy0, cx1, cy1 = coords
        ix0, iy0 = self.gif_canvas_to_image(cx0, cy0)
        ix1, iy1 = self.gif_canvas_to_image(cx1, cy1)

        ref_idx = int(max(0, min(self.gif_preview_index, len(self.gif_src_images) - 1)))
        
        # Map aligned frame coordinates back to source frame coordinates
        six0, siy0 = self.gif_aligned_to_source_coords(ix0, iy0, ref_idx)
        six1, siy1 = self.gif_aligned_to_source_coords(ix1, iy1, ref_idx)

        frame_w, frame_h = self.gif_src_images[ref_idx].size

        l = max(0, min(frame_w - 1, int(round(min(six0, six1)))))
        t = max(0, min(frame_h - 1, int(round(min(siy0, siy1)))))
        r = max(1, min(frame_w, int(round(max(six0, six1)))))
        b = max(1, min(frame_h, int(round(max(siy0, siy1)))))

        if r > l and b > t:
            self.gif_template_box = (l, t, r, b)
            self.gif_template_frame_idx = ref_idx
            self.gif_anchor.set("template")
            self.schedule_gif_preview_update()
            messagebox.showinfo("Anchor Box Set", f"Template anchor set at region ({l}, {t}) to ({r}, {b}) on frame {ref_idx + 1}. Aligning frames...")

    def do_crop(self):
        coords = self.canvas.coords(self.crop_rect)
        x1, y1 = self.canvas_to_image(coords[0], coords[1])
        x2, y2 = self.canvas_to_image(coords[2], coords[3])
        l = int(min(x1, x2))
        t = int(min(y1, y2))
        r = int(max(x1, x2))
        b = int(max(y1, y2))
        if r > l and b > t:
            desc = f"Crop to {l},{t},{r},{b}"
            self.actions.append({"type": "crop", "box": (l, t, r, b), "desc": desc})
            self.rules_list.insert(tk.END, desc)
            self.clear_lasso_selection()
            self.apply_actions()
            # New committed change: clear redo stack
            self._clear_redo_stack()
        self.canvas.delete(self.crop_rect)
        self.crop_rect = None
        self.set_mode("picker")
        self.update_preview()

    def _finalize_lasso_selection(self):
        """Convert current lasso polygon to a protected pixel mask."""
        if not self.lasso_points or not self.edited_img:
            return

        # Require at least 3 distinct points to form an area
        pts_canvas = list(self.lasso_points)
        if len(pts_canvas) < 3:
            return

        # Map canvas coordinates to image coordinates and close the loop
        img_points = []
        for cx, cy in pts_canvas:
            x, y = self.canvas_to_image(cx, cy)
            img_points.append((x, y))
        # Explicitly close the polygon by repeating the first point
        if img_points[0] != img_points[-1]:
            img_points.append(img_points[0])

        # Build a mask image and draw the polygon in image space
        mask = Image.new("1", self.edited_img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(img_points, outline=1, fill=1)

        mpx = mask.load()
        w, h = mask.size
        # Reset mask for this selection, then populate
        self.protected_mask.clear()
        for x in range(w):
            for y in range(h):
                if mpx[x, y]:
                    self.protected_mask.add((x, y))

        # Clean up old lasso line
        if self.lasso_line is not None:
            self.canvas.delete(self.lasso_line)
            self.lasso_line = None

        # Draw a visible overlay approximating the protected region
        if self.protected_overlay is not None:
            self.canvas.delete(self.protected_overlay)
            self.protected_overlay = None

        # Rebuild a coarse polygon in canvas space from original lasso_points
        if self.lasso_points:
            flat = [coord for pt in self.lasso_points for coord in pt]
            self.protected_overlay = self.canvas.create_polygon(
                *flat,
                outline="#00ff00",
                width=2,
                dash=(4, 4),
                fill="",
            )

        self.lasso_points = []
        self.lasso_mode = False
        self.set_mode("picker")

    def clear_lasso_selection(self):
        """Clear the protected region and any in-progress lasso overlay."""
        self.protected_mask.clear()
        self.lasso_points = []
        if self.lasso_line is not None:
            self.canvas.delete(self.lasso_line)
            self.lasso_line = None
        if self.protected_overlay is not None:
            self.canvas.delete(self.protected_overlay)
            self.protected_overlay = None
        if self.mode == "lasso":
            self.set_mode("picker")

    def pick_color_at(self, cx, cy, apply_rule: bool = False):
        if not self.edited_img:
            return
        x, y = self.canvas_to_image(cx, cy)
        x = int(x)
        y = int(y)
        if 0 <= x < self.edited_img.width and 0 <= y < self.edited_img.height:
            r,g,b,_ = self.edited_img.getpixel((x,y))
            col = f"#{r:02x}{g:02x}{b:02x}"
            self.hex_var.set(col)
            self.color_canvas.delete("all")
            self.color_canvas.create_rectangle(8,8,52,52, fill=col, outline="white", width=2)
            # If the last action is AI remove, update its background color parameter for decontamination
            if self.actions and self.actions[-1]["type"] == "ai_remove":
                self.actions[-1]["color"] = (r, g, b)
                self.apply_actions()
                self.update_preview()

    def choose_swap_color_ui(self):
        old_col = colorchooser.askcolor(title="Choose color to replace")[1]
        if not old_col:
            return
        new_col = colorchooser.askcolor(title="Choose replacement color")[1]
        if not new_col:
            return
        tr, tg, tb = int(old_col[1:3], 16), int(old_col[3:5], 16), int(old_col[5:7], 16)
        nr, ng, nb = int(new_col[1:3], 16), int(new_col[3:5], 16), int(new_col[5:7], 16)
        self.add_replace_action((tr, tg, tb), (nr, ng, nb))

    def pick_swap_color_ui(self):
        self.swap_old_color = None
        self.mode = "pick_swap"
        self.canvas.config(cursor="crosshair")

    def blend_with_color_ui(self):
        # Legacy UI path kept for compatibility: delegate to new blend_with_color
        self.blend_with_color()

    def blend_with_neighbor_ui(self):
        if not self.blend_color:
            return
        self.current_preview_rule = self.blend_color
        self.blend_with_neighbor()
        self.blend_color = None
        self.edge_blend_mode = tk.StringVar(value="color")  # 'color' or 'transparent'

    def smart_blend_ui(self):
        if not self.blend_color:
            return
        self.current_preview_rule = self.blend_color
        self.smart_blend()
        self.blend_color = None

    def apply_preview(self):
        self.update_preview()

    def on_tol_change(self, *args):
        # Check if the last action is AI remove
        if self.actions and self.actions[-1]["type"] == "ai_remove":
            action = self.actions[-1]
            action["tol"] = self.tol_var.get()
            action["soft"] = self.soft_var.get()
            action["contiguous"] = self.contiguous_var.get()
            action["clean_holes"] = self.clean_holes_var.get()
            
            # Update description in rules_list listbox
            desc = f"AI Auto-Remove (tol {action['tol']:.1f} soft {action['soft']:.1f})"
            if action["contiguous"]:
                desc += " contig"
                if action["clean_holes"]:
                    desc += "+holes"
            
            idx = len(self.actions) - 1
            self.rules_list.delete(idx)
            self.rules_list.insert(idx, desc)
            
            self.apply_actions()
            self.update_preview()
            return

        if self.current_preview_rule is None:
            hex_col = self.hex_var.get()
            try:
                r = int(hex_col[1:3], 16)
                g = int(hex_col[3:5], 16)
                b = int(hex_col[5:7], 16)
                self.current_preview_rule = (r, g, b)
            except Exception:
                pass
        if self.preview_after_id:
            self.root.after_cancel(self.preview_after_id)
        self.preview_after_id = self.root.after(200, self.apply_preview)

    def add_rule(self):
        rule_color = self.current_preview_rule
        if rule_color is None:
            hex_col = self.hex_var.get()
            try:
                r = int(hex_col[1:3], 16)
                g = int(hex_col[3:5], 16)
                b = int(hex_col[5:7], 16)
                rule_color = (r, g, b)
            except Exception:
                pass

        if rule_color:
            r,g,b = rule_color
            tol = self.tol_var.get()
            soft = self.soft_var.get()
            contiguous = self.contiguous_var.get()
            clean_holes = self.clean_holes_var.get()
            
            desc = f"Color: #{r:02x}{g:02x}{b:02x} tol {tol:.1f} soft {soft:.1f}"
            if contiguous:
                desc += " contig"
                if clean_holes:
                    desc += "+holes"
                    
            self.actions.append({
                "type": "color",
                "color": (r,g,b),
                "tol": tol,
                "soft": soft,
                "contiguous": contiguous,
                "clean_holes": clean_holes,
                "desc": desc
            })
            self.rules_list.insert(tk.END, desc)
            self.apply_actions()
            self._clear_redo_stack()
            self.update_preview()
            self.current_preview_rule = None

    def remove_rule(self):
        sel = self.rules_list.curselection()
        if sel:
            idx = sel[0]
            self.actions.pop(idx)
            self.rules_list.delete(idx)
            self._last_applied_action_count = -1
            self.apply_actions()
            self.update_preview()

    def clear_rules(self):
        self.actions = []
        self.future_history.clear()
        self.rules_list.delete(0, tk.END)
        self._last_applied_action_count = 0
        if self.original_img is not None:
            self.edited_img = self.original_img.copy()
            self.history = [self.edited_img.copy()]
        else:
            self.history = []
        self.current_preview_rule = None
        self._sync_crop_resize_controls()
        self.update_preview()

    def apply_actions(self):
        if not self.original_img:
            return
        self.project_dirty = True
        if not self.actions:
            self.edited_img = self.original_img.copy()
            self._last_applied_action_count = 0
            self.history = [self.edited_img.copy()]
            self._sync_crop_resize_controls()
            return

        incremental = False
        if self.edited_img is not None and len(self.history) >= len(self.actions) and len(self.actions) > 0:
            self.history = self.history[:len(self.actions)]
            img = self.history[-1].copy()
            actions_to_apply = [self.actions[-1]]
            incremental = True
        elif self.edited_img is not None and self._last_applied_action_count == len(self.actions) - 1:
            img = self.edited_img.copy()
            actions_to_apply = [self.actions[-1]]
            incremental = True
        else:
            # Start from original baseline and rebuild edited image
            img = self.original_img.copy()
            self.history = [img.copy()]
            actions_to_apply = self.actions

        # Fallback to full rebuild if applying an ai_cleanup action to merge properly
        if incremental and any(act["type"] == "ai_cleanup" for act in actions_to_apply):
            img = self.original_img.copy()
            self.history = [img.copy()]
            actions_to_apply = self.actions
            incremental = False

        for action in actions_to_apply:
            if action["type"] == "color":
                import numpy as np
                import cv2
                before_img = img.copy()
                arr = np.array(img.convert("RGBA"))
                rgb = arr[:, :, :3]
                a_channel = arr[:, :, 3]

                tr, tg, tb = action["color"]
                tol_val = action["tol"] * 2.55
                soft_val = action.get("soft", 0.0) * 2.55
                contiguous = action.get("contiguous", False)
                clean_holes = action.get("clean_holes", False)

                dist = np.sqrt(np.sum((rgb - [tr, tg, tb]) ** 2, axis=-1))

                if soft_val > 0:
                    lower_bound = tol_val - soft_val / 2.0
                    upper_bound = tol_val + soft_val / 2.0
                    if upper_bound > lower_bound:
                        factor = np.clip((dist - lower_bound) / (upper_bound - lower_bound), 0.0, 1.0)
                    else:
                        factor = (dist > tol_val).astype(float)
                else:
                    factor = (dist > tol_val).astype(float)

                if contiguous:
                    bg_candidate_mask = (factor < 1.0).astype(np.uint8) * 255
                    h, w = bg_candidate_mask.shape
                    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bg_candidate_mask, connectivity=8)
                    
                    border_labels = set()
                    for x in range(w):
                        border_labels.add(labels[0, x])
                        border_labels.add(labels[h - 1, x])
                    for y in range(h):
                        border_labels.add(labels[y, 0])
                        border_labels.add(labels[y, w - 1])
                        
                    if 0 in border_labels:
                        border_labels.remove(0)
                        
                    if not clean_holes:
                        keep_opaque_mask = np.ones((h, w), dtype=bool)
                        for label in range(1, num_labels):
                            if label not in border_labels:
                                keep_opaque_mask[labels == label] = False
                        factor[~keep_opaque_mask] = 1.0

                mask_partial = (factor > 0.0) & (factor < 1.0)
                if np.any(mask_partial):
                    rgb_f = rgb.astype(float)
                    bg_col_f = np.array([tr, tg, tb], dtype=float)
                    factor_expanded = np.expand_dims(factor, axis=-1)
                    unmultiplied = (rgb_f - (1.0 - factor_expanded) * bg_col_f) / np.maximum(factor_expanded, 0.05)
                    unmultiplied = np.clip(unmultiplied, 0.0, 255.0)
                    arr[mask_partial, :3] = unmultiplied[mask_partial].astype(np.uint8)

                new_a = (a_channel * factor).astype(np.uint8)
                arr[:, :, 3] = new_a

                img = Image.fromarray(arr, "RGBA").copy()

                # Hard protection: restore protected pixels from before_img
                if self.protected_mask:
                    before_px = before_img.load()
                    px = img.load()
                    for (x, y) in self.protected_mask:
                        if 0 <= x < img.width and 0 <= y < img.height:
                            px[x, y] = before_px[x, y]
            elif action["type"] == "crop":
                l, t, r, b = action["box"]
                img = img.crop((l, t, r, b))
            elif action["type"] == "resize":
                width = max(1, int(action["width"]))
                height = max(1, int(action["height"]))
                resample = self._resize_resample_filter(action.get("resample", "lanczos"))
                img = img.resize((width, height), resample)
            elif action["type"] == "replace":
                import numpy as np
                arr = np.array(img.convert("RGBA"))
                rgb = arr[:, :, :3]
                tr, tg, tb = action["old"]
                nr, ng, nb = action["new"]
                tol_val = action["tol"]
                tol_sq = tol_val ** 2
                
                dist_sq = np.sum((rgb - [tr, tg, tb]) ** 2, axis=-1)
                mask = dist_sq <= tol_sq
                
                if self.protected_mask:
                    protected = np.zeros(dist_sq.shape, dtype=bool)
                    for (x, y) in self.protected_mask:
                        if 0 <= x < img.width and 0 <= y < img.height:
                            protected[y, x] = True
                    mask = mask & (~protected)
                
                arr[mask, :3] = [nr, ng, nb]
                img = Image.fromarray(arr, "RGBA").copy()
            elif action["type"] == "ai_remove":
                if "ai_mask" not in action:
                    action["ai_mask"] = self._apply_ai_remove_mask(img)
                
                # Merge any subsequent local ai_cleanup masks into a composite mask
                composite_mask = action["ai_mask"].copy()
                try:
                    idx = self.actions.index(action)
                    for sub_act in self.actions[idx + 1:]:
                        if sub_act["type"] == "ai_cleanup":
                            l, t, r, b = sub_act["box"]
                            local_mask = sub_act["local_mask"]
                            composite_mask.paste(local_mask, (l, t))
                        elif sub_act["type"] == "ai_remove":
                            # Stop merging if there is a new global AI remove
                            break
                except ValueError:
                    pass
                
                action["composite_mask"] = composite_mask
                img = self._apply_refined_ai_remove(img, action)
            elif action["type"] == "ai_cleanup":
                continue
            elif action["type"] == "blend":
                px = img.load()
                tr, tg, tb = action["old"]
                target = action.get("target")
                amount = action["amount"]
                edge_coords = action.get("edge_coords")
                mode = action.get("mode", "color")
                if edge_coords:
                    # Only affect precomputed edge pixels
                    for (x, y) in edge_coords:
                        if (x, y) in self.protected_mask:
                            continue
                        if 0 <= x < img.width and 0 <= y < img.height:
                            r, g, b, a = px[x, y]
                            if mode == "transparent":
                                # Fade alpha toward 0 by amount
                                new_a = int(a * (1 - amount))
                                px[x, y] = (r, g, b, new_a)
                            else:
                                if target is None:
                                    continue
                                nr, ng, nb = target
                                r = int(r * (1 - amount) + nr * amount)
                                g = int(g * (1 - amount) + ng * amount)
                                b = int(b * (1 - amount) + nb * amount)
                                px[x, y] = (r, g, b, a)
                else:
                    # Fallback: exact-color match across whole image
                    if target is not None:
                        nr, ng, nb = target
                        for x in range(img.width):
                            for y in range(img.height):
                                if (x, y) in self.protected_mask:
                                    continue
                                r, g, b, a = px[x, y]
                                if (r, g, b) == (tr, tg, tb):
                                    r = int(r * (1 - amount) + nr * amount)
                                    g = int(g * (1 - amount) + ng * amount)
                                    b = int(b * (1 - amount) + nb * amount)
                                    px[x, y] = (r, g, b, a)
            elif action["type"] == "edge_smooth":
                # Legacy no-op for backward compatibility
                continue
            elif action["type"] == "antialias":
                scale = int(action.get("scale", 2))
                if scale < 2:
                    continue
                big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
                img = big.resize((img.width, img.height), Image.LANCZOS)
            elif action["type"] == "brush":
                points = action.get("points") or [(action["x"], action["y"])]
                if len(points) == 1:
                    point_x, point_y = points[0]
                    self._apply_brush_dab(img, point_x, point_y, action["r"], action["mode"], action.get("color"))
                else:
                    first_x, first_y = points[0]
                    self._apply_brush_dab(img, first_x, first_y, action["r"], action["mode"], action.get("color"))
                    for start_point, end_point in zip(points, points[1:]):
                        self._apply_brush_segment(img, start_point, end_point, action["r"], action["mode"], action.get("color"))
            
            # Save intermediate snapshot if rebuilding from scratch
            if not incremental:
                self.history.append(img.copy())
                if len(self.history) > 30:
                    self.history.pop(0)

        self.edited_img = img
        self._last_applied_action_count = len(self.actions)

        if incremental and self.edited_img is not None:
            self.history.append(self.edited_img.copy())
            if len(self.history) > 30:
                self.history.pop(0)
        self._sync_crop_resize_controls()

    def _compute_edge_coords(self, tr, tg, tb):
        """Return all pixels that sit directly next to transparency.

        This ignores color and simply finds the full halo of edge pixels
        surrounding transparent regions. Blend code can still use the
        picked color to decide how to recolor them.
        """
        if not self.edited_img:
            return []

        from PIL import ImageFilter, ImageChops
        # Extract alpha channel
        alpha = self.edited_img.getchannel("A")
        # Apply min filter to find pixels where all 3x3 neighbors are opaque
        min_alpha = alpha.filter(ImageFilter.MinFilter(3))
        # Absolute difference highlights only boundary pixels
        edge_mask = ImageChops.difference(alpha, min_alpha)
        
        px = edge_mask.load()
        width, height = edge_mask.size
        edge_coords = []
        for x in range(width):
            for y in range(height):
                if px[x, y] > 0:
                    edge_coords.append((x, y))

        return edge_coords

    def _apply_brush_dab(self, img, x, y, r, mode, color=None):
        if not self.protected_mask:
            draw = ImageDraw.Draw(img)
            bounds = [x - r, y - r, x + r, y + r]
            if mode == "erase":
                draw.ellipse(bounds, fill=(0, 0, 0, 0))
                return
            if mode == "replace_single" and color is not None:
                draw.ellipse(bounds, fill=(*color, 255))
                return
        px = img.load()
        for ix in range(x - r, x + r + 1):
            for iy in range(y - r, y + r + 1):
                if (ix, iy) in self.protected_mask:
                    continue
                if 0 <= ix < img.width and 0 <= iy < img.height:
                    if (ix - x) ** 2 + (iy - y) ** 2 <= r ** 2:
                        if mode == "erase":
                            px[ix, iy] = (0, 0, 0, 0)
                        elif mode == "replace_single" and color is not None:
                            px[ix, iy] = (*color, 255)

    def _apply_brush_segment(self, img, start_point, end_point, r, mode, color=None, scale_x=1.0, scale_y=1.0, respect_protected=True):
        if img is None:
            return

        radius_x = max(1, int(round(r * scale_x)))
        radius_y = max(1, int(round(r * scale_y)))
        fill = (0, 0, 0, 0) if mode == "erase" else ((*color, 255) if color is not None else None)
        if fill is None:
            return

        if respect_protected and self.protected_mask:
            points = [start_point] + self._iter_brush_points(start_point, end_point)
            for point_x, point_y in points:
                sx = int(round(point_x * scale_x))
                sy = int(round(point_y * scale_y))
                self._apply_brush_dab(img, sx, sy, max(radius_x, radius_y), mode, color)
            return

        x0 = int(round(start_point[0] * scale_x))
        y0 = int(round(start_point[1] * scale_y))
        x1 = int(round(end_point[0] * scale_x))
        y1 = int(round(end_point[1] * scale_y))
        stroke_width = max(1, int(round((r * 2 + 1) * max(scale_x, scale_y))))
        draw = ImageDraw.Draw(img)
        draw.line((x0, y0, x1, y1), fill=fill, width=stroke_width)
        draw.ellipse((x0 - radius_x, y0 - radius_y, x0 + radius_x, y0 + radius_y), fill=fill)
        draw.ellipse((x1 - radius_x, y1 - radius_y, x1 + radius_x, y1 + radius_y), fill=fill)

    def _iter_brush_points(self, start_point, end_point):
        x0, y0 = start_point
        x1, y1 = end_point
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy))
        if steps <= 0:
            return [end_point]
        points = []
        for step in range(1, steps + 1):
            px = int(round(x0 + (dx * step / steps)))
            py = int(round(y0 + (dy * step / steps)))
            points.append((px, py))
        return points

    def _begin_brush_stroke(self, x, y):
        color = self.brush_replace_color if self.mode == "replace_single" else None
        desc = "Brush erase stroke" if self.mode == "erase" else "Brush replace stroke"
        action = {
            "type": "brush",
            "x": x,
            "y": y,
            "r": self.brush_size,
            "mode": self.mode,
            "color": color,
            "desc": desc,
            "points": [],
        }
        self.actions.append(action)
        self.rules_list.insert(tk.END, desc)
        self.active_brush_action = action
        self.active_brush_rule_index = self.rules_list.size() - 1
        self.last_brush_point = None

    def _extend_brush_stroke(self, x, y):
        if self.active_brush_action is None or self.edited_img is None:
            return
        current_point = (x, y)
        points = self.active_brush_action.setdefault("points", [])
        if self.last_brush_point is None:
            if not points or points[-1] != current_point:
                points.append(current_point)
            self._apply_brush_dab(
                self.edited_img,
                x,
                y,
                self.active_brush_action["r"],
                self.active_brush_action["mode"],
                self.active_brush_action.get("color"),
            )
            if self.live_brush_preview_img is not None and self.live_brush_preview_scale is not None and not self.protected_mask:
                preview_scale_x, preview_scale_y = self.live_brush_preview_scale
                self._apply_brush_dab(
                    self.live_brush_preview_img,
                    int(round(x * preview_scale_x)),
                    int(round(y * preview_scale_y)),
                    max(1, int(round(self.active_brush_action["r"] * max(preview_scale_x, preview_scale_y)))),
                    self.active_brush_action["mode"],
                    self.active_brush_action.get("color"),
                )
        else:
            if current_point == self.last_brush_point:
                return
            if not points or points[-1] != current_point:
                points.append(current_point)
            self._apply_brush_segment(
                self.edited_img,
                self.last_brush_point,
                current_point,
                self.active_brush_action["r"],
                self.active_brush_action["mode"],
                self.active_brush_action.get("color"),
            )
            if self.live_brush_preview_img is not None and self.live_brush_preview_scale is not None and not self.protected_mask:
                preview_scale_x, preview_scale_y = self.live_brush_preview_scale
                self._apply_brush_segment(
                    self.live_brush_preview_img,
                    self.last_brush_point,
                    current_point,
                    self.active_brush_action["r"],
                    self.active_brush_action["mode"],
                    self.active_brush_action.get("color"),
                    scale_x=preview_scale_x,
                    scale_y=preview_scale_y,
                    respect_protected=False,
                )
        self.last_brush_point = current_point

    def _finalize_brush_stroke(self):
        if self.active_brush_action is None:
            self._flush_live_preview_update()
            return
        if not self.active_brush_action.get("points"):
            action_index = self.actions.index(self.active_brush_action)
            self.actions.pop(action_index)
            try:
                if self.active_brush_rule_index is not None:
                    self.rules_list.delete(self.active_brush_rule_index)
            except Exception:
                pass
        else:
            self._clear_redo_stack()
            self.project_dirty = True
            if self.edited_img is not None:
                self.history.append(self.edited_img.copy())
                if len(self.history) > 5:
                    self.history.pop(0)
            self._last_applied_action_count = len(self.actions)
        self.active_brush_action = None
        self.active_brush_rule_index = None
        self.last_brush_point = None
        self._invalidate_live_brush_preview_cache()
        self._flush_live_preview_update()

    def brush(self, cx, cy):
        x, y = self.canvas_to_image(cx, cy)
        x = int(x)
        y = int(y)
        if not self.edited_img:
            return
        if self.mode == "replace_single" and self.brush_replace_color is None:
            col = colorchooser.askcolor()[1]
            if not col:
                return
            self.brush_replace_color = tuple(int(col[i:i+2], 16) for i in (1, 3, 5))
            self._update_replace_color_label()

        if self.active_brush_action is None:
            self._begin_brush_stroke(x, y)
        self._extend_brush_stroke(x, y)
        self._update_brush_cursor_overlay()
        self._request_live_preview_update()

    def _clear_redo_stack(self):
        self.future_history.clear()
        self.redo_actions.clear()

    def _save_gif_state(self):
        if hasattr(self, "project_dirty") and self.gif_src_images:
            self.project_dirty = True
        state = {
            "paths": list(self.gif_frame_paths),
            "images": [img.copy() for img in self.gif_src_images],
            "omitted": list(self.gif_frame_omitted),
            "preview_index": self.gif_preview_index
        }
        self.gif_history.append(state)
        if len(self.gif_history) > 30:
            self.gif_history.pop(0)
        self.gif_future_history.clear()

    def gif_undo(self):
        if not self.gif_history:
            return
        
        current_state = {
            "paths": list(self.gif_frame_paths),
            "images": [img.copy() for img in self.gif_src_images],
            "omitted": list(self.gif_frame_omitted),
            "preview_index": self.gif_preview_index
        }
        self.gif_future_history.append(current_state)
        
        state = self.gif_history.pop()
        self.gif_frame_paths = state["paths"]
        self.gif_src_images = state["images"]
        self.gif_frame_omitted = state["omitted"]
        self.gif_preview_index = state["preview_index"]
        
        self.gif_aligned_rgba = []
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def gif_redo(self):
        if not self.gif_future_history:
            return
            
        current_state = {
            "paths": list(self.gif_frame_paths),
            "images": [img.copy() for img in self.gif_src_images],
            "omitted": list(self.gif_frame_omitted),
            "preview_index": self.gif_preview_index
        }
        self.gif_history.append(current_state)
        
        state = self.gif_future_history.pop()
        self.gif_frame_paths = state["paths"]
        self.gif_src_images = state["images"]
        self.gif_frame_omitted = state["omitted"]
        self.gif_preview_index = state["preview_index"]
        
        self.gif_aligned_rgba = []
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def _capture_slicer_state(self):
        slicer_boxes_snapshot = []
        for box in self.slicer_boxes:
            name_val = box["name_var"].get() if "name_var" in box else box.get("name", "")
            slicer_boxes_snapshot.append({
                "box": box["box"],
                "name": name_val
            })
            
        slicer_batch_images_snapshot = []
        for item in self.slicer_batch_images:
            name_val = item["name_var"].get() if "name_var" in item else item.get("name", "")
            slicer_batch_images_snapshot.append({
                "image": item["image"].copy(),
                "path": item["path"],
                "name": name_val
            })
            
        return {
            "slicer_image": self.slicer_image.copy() if self.slicer_image is not None else None,
            "slicer_image_path": self.slicer_image_path,
            "slicer_use_manual": self.slicer_use_manual.get(),
            "slicer_trim_transparency": self.slicer_trim_transparency.get(),
            "slicer_trim_threshold": self.slicer_trim_threshold.get(),
            "cols": self.slicer_cols.get(),
            "rows": self.slicer_rows.get(),
            "margin_x": self.slicer_margin_x.get(),
            "margin_y": self.slicer_margin_y.get(),
            "padding_x": self.slicer_padding_x.get(),
            "padding_y": self.slicer_padding_y.get(),
            "expand_w": self.slicer_expand_w.get(),
            "expand_h": self.slicer_expand_h.get(),
            "slicer_boxes": slicer_boxes_snapshot,
            "slicer_batch_images": slicer_batch_images_snapshot,
            "slicer_batch_active_idx": self.slicer_batch_active_idx
        }

    def _save_slicer_state(self):
        state = self._capture_slicer_state()
        self.slicer_history.append(state)
        if len(self.slicer_history) > 50:
            self.slicer_history.pop(0)
        self.slicer_future_history.clear()

    def _restore_slicer_state(self, state):
        # 1. Restore standard variables
        self.slicer_image = state["slicer_image"].copy() if state["slicer_image"] is not None else None
        self.slicer_image_path = state["slicer_image_path"]
        self.slicer_use_manual.set(state["slicer_use_manual"])
        self.slicer_trim_transparency.set(state["slicer_trim_transparency"])
        self.slicer_trim_threshold.set(state["slicer_trim_threshold"])
        
        self.slicer_cols.set(state["cols"])
        self.slicer_rows.set(state["rows"])
        self.slicer_margin_x.set(state["margin_x"])
        self.slicer_margin_y.set(state["margin_y"])
        self.slicer_padding_x.set(state["padding_x"])
        self.slicer_padding_y.set(state["padding_y"])
        self.slicer_expand_w.set(state["expand_w"])
        self.slicer_expand_h.set(state["expand_h"])
        
        # 2. Restore manual boxes
        self.slicer_boxes = []
        for box_info in state["slicer_boxes"]:
            var = tk.StringVar(value=box_info["name"])
            var.trace_add("write", lambda *_: self.slicer_update_preview())
            self.slicer_boxes.append({
                "box": box_info["box"],
                "name": box_info["name"],
                "name_var": var
            })
            
        # 3. Restore batch images
        self.slicer_batch_images = []
        for item in state["slicer_batch_images"]:
            var = tk.StringVar(value=item["name"])
            var.trace_add("write", lambda *_: self.slicer_update_preview())
            self.slicer_batch_images.append({
                "image": item["image"].copy(),
                "path": item["path"],
                "name": item["name"],
                "name_var": var
            })
        self.slicer_batch_active_idx = state["slicer_batch_active_idx"]
        
        # Sync label / active image
        if self.slicer_batch_images:
            if 0 <= self.slicer_batch_active_idx < len(self.slicer_batch_images):
                idx = self.slicer_batch_active_idx
                active_item = self.slicer_batch_images[idx]
                self.slicer_image = active_item["image"].copy()
                self.slicer_image_path = active_item["path"]
                w, h = self.slicer_image.size
                name = os.path.basename(self.slicer_image_path)
                self.slicer_info_label.config(text=f"{name} ({w}×{h}) [Batch {idx+1}/{len(self.slicer_batch_images)}]")
        else:
            if self.slicer_image is not None:
                w, h = self.slicer_image.size
                name = os.path.basename(self.slicer_image_path) if self.slicer_image_path else "Loaded Image"
                self.slicer_info_label.config(text=f"{name} ({w}×{h})")
            else:
                self.slicer_info_label.config(text="No image loaded")
                self.slicer_slice_info.config(text="Cell size: -")
        
        # 4. Refresh UI
        self.slicer_on_mode_toggle()
        self.slicer_rebuild_names()
        self.slicer_update_preview()

    def slicer_undo(self):
        if not self.slicer_history:
            return
            
        current_state = self._capture_slicer_state()
        self.slicer_future_history.append(current_state)
        
        state = self.slicer_history.pop()
        self._restore_slicer_state(state)

    def slicer_redo(self):
        if not self.slicer_future_history:
            return
            
        current_state = self._capture_slicer_state()
        self.slicer_history.append(current_state)
        
        state = self.slicer_future_history.pop()
        self._restore_slicer_state(state)

    def on_undo_shortcut(self, event=None):
        focused = self.root.focus_get()
        if focused is not None and focused.winfo_class() in ("Entry", "TEntry", "Text", "Spinbox", "TCombobox"):
            return None
        if getattr(self, "is_composition_active", False):
            self.composition_undo()
        elif getattr(self, "is_slicer_active", False):
            self.slicer_undo()
        elif self.png_gif_mode.get():
            self.gif_undo()
        else:
            self.undo()
        return "break"

    def on_redo_shortcut(self, event=None):
        focused = self.root.focus_get()
        if focused is not None and focused.winfo_class() in ("Entry", "TEntry", "Text", "Spinbox", "TCombobox"):
            return None
        if getattr(self, "is_composition_active", False):
            self.composition_redo()
        elif getattr(self, "is_slicer_active", False):
            self.slicer_redo()
        elif self.png_gif_mode.get():
            self.gif_redo()
        else:
            self.redo()
        return "break"

    def on_delete_key(self, event=None):
        if getattr(self, "is_composition_active", False):
            self.composition_delete_selected()
            return "break"
        if self._should_handle_gif_arrow_key():
            self.gif_delete_frame(self.gif_preview_index)
            return "break"

    def undo(self):
        if getattr(self, "is_composition_active", False):
            self.composition_undo()
            return
        if not self.actions or len(self.history) <= 1:
            return
        
        # Pop action and add to redo stack
        action = self.actions.pop()
        self.redo_actions.append(action)
        self.project_dirty = True
        
        # Revert rule list UI
        try:
            self.rules_list.delete(tk.END)
        except Exception:
            pass
            
        # Revert image state using snapshot history
        current_state = self.history.pop()
        self.future_history.append(current_state)
        
        self.edited_img = self.history[-1].copy()
        self._sync_crop_resize_controls()
        
        # Adjust last applied action count
        self._last_applied_action_count = len(self.actions)
        
        self.update_preview()

    def redo(self):
        if getattr(self, "is_composition_active", False):
            self.composition_redo()
            return
        if not self.redo_actions or not self.future_history:
            return
            
        # Pop action from redo and put back to actions
        action = self.redo_actions.pop()
        self.actions.append(action)
        self.project_dirty = True
        
        # Re-add to rule list UI
        try:
            desc = action.get("desc", "Action")
            self.rules_list.insert(tk.END, desc)
        except Exception:
            pass
            
        # Restore image state from future history
        state = self.future_history.pop()
        self.history.append(state)
        self.edited_img = state.copy()
        self._sync_crop_resize_controls()
        
        # Adjust last applied action count
        self._last_applied_action_count = len(self.actions)
        
        self.update_preview()

    def choose_color(self):
        col = colorchooser.askcolor()[1]
        if col:
            r,g,b = int(col[1:3],16), int(col[3:5],16), int(col[5:7],16)
            self.hex_var.set(col)
            self.color_canvas.delete("all")
            self.color_canvas.create_rectangle(8,8,52,52, fill=col, outline="white", width=2)
            self.current_preview_rule = (r,g,b)
            self.apply_preview()

    def replace_all_color(self):
        if not self.current_preview_rule:
            return
        new_col = colorchooser.askcolor(title="Choose replacement color")[1]
        if not new_col:
            return
        nr, ng, nb = int(new_col[1:3], 16), int(new_col[3:5], 16), int(new_col[5:7], 16)
        tr, tg, tb = self.current_preview_rule
        tol = self.tol_var.get()
        desc = f"Replace #{tr:02x}{tg:02x}{tb:02x} with #{nr:02x}{ng:02x}{nb:02x}"
        self.actions.append({"type": "replace", "old": (tr, tg, tb), "new": (nr, ng, nb), "tol": tol, "desc": desc})
        self.rules_list.insert(tk.END, desc)
        self.apply_actions()
        self.update_preview()
    def run_edge_blend(self):
        """Apply edge blend to all pixels neighboring transparency.

        - In "color" mode, blend edge pixels toward the currently-selected
          color in the Color Removal panel (hex_var).
        - In "transparent" mode, fade edge pixels toward full transparency
          based on the Blend Strength slider.
        """
        if not self.edited_img:
            return

        # Compute edge mask: all non-transparent pixels neighboring transparency
        edge_coords = self._compute_edge_coords(0, 0, 0)
        if not edge_coords:
            return

        mode = self.edge_blend_mode.get()

        if mode == "color":
            # Use the main color selector as target color
            hex_col = self.hex_var.get()
            try:
                nr = int(hex_col[1:3], 16)
                ng = int(hex_col[3:5], 16)
                nb = int(hex_col[5:7], 16)
            except Exception:
                return
            desc = f"Edge blend to color {hex_col}"
            target = (nr, ng, nb)
            old = target  # old is unused when edge_coords are present
        else:
            # Transparent mode: we will fade alpha toward 0 in apply_actions
            desc = "Edge blend to transparent"
            target = None
            old = (0, 0, 0)

        self.actions.append({
            "type": "blend",
            "old": old,
            "target": target,
            "amount": self.blend_strength.get() / 100.0,
            "tol": 0,
            "edge_coords": edge_coords,
            "mode": mode,
            "desc": desc,
        })
        self.last_blend_index = len(self.actions) - 1
        self.rules_list.insert(tk.END, desc)
        self.apply_actions()
        self.future_history.clear()
        self.update_preview()

    def run_edge_smooth(self):
        """Apply a simple global anti-alias via supersampling.

        Upscales the current image then downsamples it with a high-quality
        filter (LANCZOS) to soften jagged edges everywhere.
        """
        if not self.edited_img:
            return

        img = self.edited_img
        scale = 2  # 2x supersample; increase to 3 for stronger AA
        big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        aa = big.resize((img.width, img.height), Image.LANCZOS)

        self.edited_img = aa
        desc = "Anti-alias image"
        self.actions.append({
            "type": "antialias",
            "scale": scale,
            "desc": desc,
        })
        self.last_blend_index = len(self.actions) - 1
        self.rules_list.insert(tk.END, desc)
        self.future_history.clear()
        self.update_preview()

    def on_blend_strength_change(self, value):
        # Live-update the last edge-related action's strength and reapply
        if self.last_blend_index is None:
            return
        if not (0 <= self.last_blend_index < len(self.actions)):
            return
        action = self.actions[self.last_blend_index]
        if action.get("type") not in ("blend", "edge_smooth"):
            return
        try:
            amount = float(value) / 100.0
        except Exception:
            amount = self.blend_strength.get() / 100.0
        action["amount"] = amount
        self.apply_actions()
        self.update_preview()

    def save_image(self):
        if getattr(self, "is_composition_active", False):
            composite = self._render_composition_image()
            if composite is not None:
                self.edited_img = composite
        if not self.edited_img:
            return
        # Ensure a valid extension and actually write the file
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("WebP files", "*.webp"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("Windows Icon", "*.ico"),
            ],
        )
        if not path:
            return

        root, ext = os.path.splitext(path)
        ext = ext.lower()
        if ext in ("", ".png"):
            if ext == "":
                path = root + ".png"
            _save_transparent_image(self.edited_img, path, "PNG")
        elif ext == ".webp":
            _save_transparent_image(self.edited_img, path, "WEBP")
        elif ext in (".jpg", ".jpeg"):
            bg = Image.new("RGB", self.edited_img.size, (255, 255, 255))
            bg.paste(self.edited_img, mask=self.edited_img.split()[3])
            bg.save(path, "JPEG", quality=95)
        elif ext == ".ico":
            self._save_as_ico(path)
        else:
            # Fallback: force PNG
            path = root + ".png"
            _save_transparent_image(self.edited_img, path, "PNG")

        messagebox.showinfo("Saved", f"Saved as {os.path.basename(path)}")

    def _save_as_ico(self, path: str):
        # Build a standard multi-size ICO. We use Pillow to write the frames,
        # but since Pillow sorts the directory entries in ascending order (smallest first),
        # we post-process the bytes to order them in descending order (largest first)
        # so that Windows Explorer correctly displays the high-resolution frame.
        import io
        import struct
        img = self.edited_img
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

        def _to_square_icon(src: Image.Image, size: int) -> Image.Image:
            # Fit within size x size while preserving aspect ratio, then center-pad.
            if src.width == 0 or src.height == 0:
                return Image.new("RGBA", (size, size), (0, 0, 0, 0))
            scale = min(float(size) / float(src.width), float(size) / float(src.height))
            new_w = max(1, int(round(src.width * scale)))
            new_h = max(1, int(round(src.height * scale)))
            resized = src.resize((new_w, new_h), Image.LANCZOS)
            out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            ox = (size - new_w) // 2
            oy = (size - new_h) // 2
            out.paste(resized, (ox, oy), resized)
            return out

        base_256 = _to_square_icon(img, 256)
        
        # Use DIB/BMP-backed icon frames instead of PNG-compressed frames.
        # Although modern Windows accepts PNG data inside ICO containers, some
        # launchers, game engines, and converters only recognize the smallest
        # PNG-backed entry and incorrectly report the icon as 16x16. DIB frames
        # are larger on disk but remain compatible across old and new readers.
        buf = io.BytesIO()
        base_256.save(
            buf,
            format="ICO",
            sizes=sizes,
            bitmap_format="bmp",
        )
        orig_bytes = buf.getvalue()
        
        # Reorder the directory entries and images to be descending (largest resolution first)
        def reorder_ico(ico_bytes: bytes) -> bytes:
            if len(ico_bytes) < 6:
                return ico_bytes
            reserved, image_type, num_images = struct.unpack("<HHH", ico_bytes[:6])
            if reserved != 0 or image_type != 1 or num_images == 0:
                return ico_bytes
            
            entries = []
            offset = 6
            for i in range(num_images):
                entry_bytes = ico_bytes[offset:offset+16]
                width, height, num_colors, reserved2, planes, bpp, size, img_offset = struct.unpack("<BBBBHHII", entry_bytes)
                w = 256 if width == 0 else width
                h = 256 if height == 0 else height
                img_data = ico_bytes[img_offset:img_offset+size]
                entries.append({
                    'width': w,
                    'height': h,
                    'entry_bytes': entry_bytes,
                    'img_data': img_data,
                    'bpp': bpp,
                    'planes': planes,
                    'num_colors': num_colors,
                    'reserved2': reserved2
                })
                offset += 16
                
            # Sort entries by resolution descending (largest first), then bpp descending
            entries.sort(key=lambda e: (e['width'], e['height'], e['bpp']), reverse=True)
            
            out_bytes = bytearray()
            out_bytes.extend(struct.pack("<HHH", reserved, image_type, num_images))
            
            current_img_offset = 6 + num_images * 16
            img_data_blocks = bytearray()
            
            for entry in entries:
                w_byte = 0 if entry['width'] == 256 else entry['width']
                h_byte = 0 if entry['height'] == 256 else entry['height']
                size = len(entry['img_data'])
                
                entry_packed = struct.pack("<BBBBHHII", 
                                           w_byte, 
                                           h_byte, 
                                           entry['num_colors'], 
                                           entry['reserved2'], 
                                           entry['planes'], 
                                           entry['bpp'], 
                                           size, 
                                           current_img_offset)
                out_bytes.extend(entry_packed)
                img_data_blocks.extend(entry['img_data'])
                current_img_offset += size
                
            out_bytes.extend(img_data_blocks)
            return bytes(out_bytes)

        reordered_bytes = reorder_ico(orig_bytes)
        
        # Write final bytes to file
        with open(path, "wb") as f:
            f.write(reordered_bytes)

    def _project_has_content(self):
        return bool(
            self.original_img
            or self.slicer_image
            or self.gif_src_images
            or getattr(self, "composition_layers", [])
        )

    def _project_slicer_settings(self):
        return {
            "cols": self.slicer_cols.get(),
            "rows": self.slicer_rows.get(),
            "margin_x": self.slicer_margin_x.get(),
            "margin_y": self.slicer_margin_y.get(),
            "padding_x": self.slicer_padding_x.get(),
            "padding_y": self.slicer_padding_y.get(),
            "expand_x": self.slicer_expand_w.get(),
            "expand_y": self.slicer_expand_h.get(),
            "crop_center": self.slicer_crop_center_content.get(),
            "crop_square": self.slicer_crop_square.get(),
            "use_manual": self.slicer_use_manual.get(),
            "trim_transparency": self.slicer_trim_transparency.get(),
            "trim_threshold": self.slicer_trim_threshold.get(),
            "export_format": self.slicer_export_format.get(),
            "manual_boxes": [
                {
                    "box": list(box["box"]),
                    "name": box["name_var"].get() if "name_var" in box else box.get("name", ""),
                }
                for box in self.slicer_boxes
            ],
        }

    def save_project(self):
        if not self._project_has_content():
            messagebox.showwarning("Save Project", "Load an image or GIF frames before saving a project.")
            return False

        path = filedialog.asksaveasfilename(
            title="Save Transparentor Project",
            initialfile=os.path.basename(self.current_project_path) if self.current_project_path else "",
            defaultextension=".tpr",
            filetypes=[("Transparentor Project", "*.tpr")],
        )
        if not path:
            return False

        temp_path = f"{path}.tmp"
        try:
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                editor_asset = None
                if self.original_img is not None:
                    editor_asset = "assets/editor/source.png"
                    archive.writestr(editor_asset, _image_to_png_bytes(self.original_img.convert("RGBA")))

                protected_asset = None
                if self.original_img is not None and self.protected_mask:
                    protection = Image.new("1", self.original_img.size, 0)
                    protection_pixels = protection.load()
                    for x, y in self.protected_mask:
                        if 0 <= x < protection.width and 0 <= y < protection.height:
                            protection_pixels[x, y] = 1
                    protected_asset = "assets/editor/protected_mask.png"
                    archive.writestr(protected_asset, _image_to_png_bytes(protection))

                slicer_asset = None
                if self.slicer_image is not None:
                    slicer_asset = "assets/slicer/source.png"
                    archive.writestr(slicer_asset, _image_to_png_bytes(self.slicer_image.convert("RGBA")))

                serialized_actions = [
                    _serialize_project_action(action, index, archive)
                    for index, action in enumerate(self.actions)
                ]

                gif_frames = []
                for index, frame in enumerate(self.gif_src_images):
                    asset = f"assets/gif/frame_{index:04d}.png"
                    archive.writestr(asset, _image_to_png_bytes(frame.convert("RGBA")))
                    raw_name = self.gif_frame_paths[index] if index < len(self.gif_frame_paths) else ""
                    gif_frames.append({
                        "name": os.path.basename(raw_name) or f"frame_{index + 1:04d}.png",
                        "asset": asset,
                        "omitted": bool(
                            self.gif_frame_omitted[index]
                            if index < len(self.gif_frame_omitted)
                            else False
                        ),
                    })

                composition_layers = []
                for index, layer in enumerate(getattr(self, "composition_layers", [])):
                    asset = f"assets/composition/layer_{index:04d}.png"
                    archive.writestr(
                        asset,
                        _image_to_png_bytes(layer["image"].convert("RGBA")),
                    )
                    composition_layers.append({
                        "name": layer.get("name", f"Layer {index + 1}"),
                        "original_path": layer.get("path"),
                        "asset": asset,
                        "x": float(layer.get("x", 0.0)),
                        "y": float(layer.get("y", 0.0)),
                        "scale": float(layer.get("scale", 1.0)),
                        "visible": bool(layer.get("visible", True)),
                        **{
                            key: layer.get(key, default)
                            for key, default in COMPOSITION_LAYER_DEFAULTS.items()
                        },
                    })

                payload = {
                    "format": "transparentor-project",
                    "format_version": PROJECT_FORMAT_VERSION,
                    "app_version": APP_VERSION,
                    "saved_at": datetime.now().astimezone().isoformat(),
                    "editor": {
                        "source_asset": editor_asset,
                        "original_path": self.editor_image_path,
                        "protected_mask_asset": protected_asset,
                    },
                    "actions": serialized_actions,
                    "slicer": {
                        "source_asset": slicer_asset,
                        "original_path": self.slicer_image_path,
                        "settings": self._project_slicer_settings(),
                    },
                    "gif": {
                        "frames": gif_frames,
                        "anchor": self.gif_anchor.get(),
                        "duration": self.gif_duration_ms.get(),
                        "alpha_threshold": self.gif_alpha_threshold.get(),
                        "padding": self.gif_padding.get(),
                        "frame_export_format": self.gif_frame_export_format.get(),
                        "template_box": list(self.gif_template_box) if self.gif_template_box else None,
                        "template_frame_index": self.gif_template_frame_idx,
                    },
                    "composition": {
                        "active": bool(getattr(self, "is_composition_active", False)),
                        "canvas_size": (
                            list(self.composition_canvas_size)
                            if getattr(self, "composition_canvas_size", None)
                            else None
                        ),
                        "selected_index": getattr(
                            self,
                            "composition_selected_index",
                            None,
                        ),
                        "layers": composition_layers,
                    },
                }
                archive.writestr("project.json", json.dumps(payload, indent=2, ensure_ascii=False))

            os.replace(temp_path, path)
            self.current_project_path = path
            self.project_dirty = False
            messagebox.showinfo(
                "Save Project",
                "Project saved successfully.\n\nThe .tpr file is self-contained and can be moved to another computer.",
            )
            return True
        except Exception as error:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            messagebox.showerror("Save Project", f"Failed to save project:\n{error}")
            return False

    def _resolve_legacy_editor_path(self, payload, project_path):
        image_path = payload.get("editor_image_path")
        if image_path and os.path.exists(image_path):
            return image_path
        if image_path:
            relative_path = os.path.join(os.path.dirname(project_path), os.path.basename(image_path))
            if os.path.exists(relative_path):
                return relative_path
        return filedialog.askopenfilename(
            title=f"Locate Image: {os.path.basename(image_path) if image_path else 'Editor Image'}",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp")],
        )

    def _restore_slicer_settings(self, settings):
        if not settings:
            return
        self.slicer_cols.set(settings.get("cols", 4))
        self.slicer_rows.set(settings.get("rows", 4))
        self.slicer_margin_x.set(settings.get("margin_x", 0))
        self.slicer_margin_y.set(settings.get("margin_y", 0))
        self.slicer_padding_x.set(settings.get("padding_x", 0))
        self.slicer_padding_y.set(settings.get("padding_y", 0))
        self.slicer_expand_w.set(settings.get("expand_x", 0))
        self.slicer_expand_h.set(settings.get("expand_y", 0))
        self.slicer_use_manual.set(settings.get("use_manual", False))
        self.slicer_trim_transparency.set(settings.get("trim_transparency", False))
        self.slicer_trim_threshold.set(settings.get("trim_threshold", 10))
        self.slicer_export_format.set(settings.get("export_format", "PNG"))
        self.slicer_crop_center_content.set(settings.get("crop_center", True))
        self.slicer_crop_square.set(settings.get("crop_square", False))
        self.slicer_boxes = [
            {"box": tuple(box["box"]), "name": box.get("name", "")}
            for box in settings.get("manual_boxes", [])
        ]
        self.slicer_rebuild_names()

    def _restore_project_payload(self, payload, project_path, archive=None):
        self._clear_composition_state()
        is_portable = payload.get("format") == "transparentor-project"
        if is_portable:
            format_version = int(payload.get("format_version", 0))
            if format_version > PROJECT_FORMAT_VERSION:
                raise ValueError(
                    f"This project uses format {format_version}, but this version of Transparentor supports up to {PROJECT_FORMAT_VERSION}."
                )
            editor_data = payload.get("editor", {})
            editor_asset = editor_data.get("source_asset")
            if editor_asset:
                editor_image = _read_archived_image(archive, editor_asset)
                original_path = editor_data.get("original_path")
                path_info = original_path if original_path and os.path.exists(original_path) else None
                self.open_image_from_pil(
                    editor_image,
                    path_info=path_info,
                    confirm_replace=False,
                )
            else:
                self.original_img = None
                self.edited_img = None
                self.editor_image_path = None
                self._sync_crop_resize_controls()

            self.actions = [
                _deserialize_project_action(action, archive)
                for action in payload.get("actions", [])
            ]

            self.protected_mask.clear()
            protected_asset = editor_data.get("protected_mask_asset")
            if protected_asset:
                protection = _read_archived_image(archive, protected_asset).convert("L")
                protection_pixels = protection.load()
                self.protected_mask = {
                    (x, y)
                    for y in range(protection.height)
                    for x in range(protection.width)
                    if protection_pixels[x, y] > 0
                }
        else:
            image_path = self._resolve_legacy_editor_path(payload, project_path)
            if not image_path:
                raise RuntimeError("The source image was not selected.")
            self.open_image_from_path(image_path, confirm_replace=False)
            self.actions = [
                _deserialize_project_action(action)
                for action in payload.get("actions", [])
            ]

        self.rules_list.delete(0, tk.END)
        for action in self.actions:
            self.rules_list.insert(tk.END, action.get("desc", "Action"))
        self._last_applied_action_count = -1
        if self.original_img is not None:
            self.apply_actions()
            self.update_preview()

        if is_portable:
            slicer_data = payload.get("slicer", {})
            slicer_asset = slicer_data.get("source_asset")
            if slicer_asset:
                self.slicer_image = _read_archived_image(archive, slicer_asset).convert("RGBA")
                self.slicer_image_path = slicer_data.get("original_path")
            self._restore_slicer_settings(slicer_data.get("settings", {}))

            gif_data = payload.get("gif", {})
            frames = gif_data.get("frames", [])
            self.gif_frame_paths = [frame.get("name", f"frame_{index + 1:04d}.png") for index, frame in enumerate(frames)]
            self.gif_src_images = [
                _read_archived_image(archive, frame["asset"]).convert("RGBA")
                for frame in frames
            ]
            self.gif_frame_omitted = [bool(frame.get("omitted", False)) for frame in frames]
            self.gif_anchor.set(gif_data.get("anchor", "center"))
            self.gif_duration_ms.set(gif_data.get("duration", 100))
            self.gif_alpha_threshold.set(gif_data.get("alpha_threshold", 128))
            self.gif_padding.set(gif_data.get("padding", 0))
            self.gif_frame_export_format.set(gif_data.get("frame_export_format", "PNG"))
            template_box = gif_data.get("template_box")
            self.gif_template_box = tuple(template_box) if template_box else None
            self.gif_template_frame_idx = gif_data.get("template_frame_index")
            self.gif_aligned_rgba = []
            self.gif_preview_index = 0
            self.gif_scrub.configure(from_=0, to=max(0, len(frames) - 1))
            self.gif_scrub.set(0)
            self._refresh_gif_frame_list()
            if frames:
                self.schedule_gif_preview_update()

            composition_data = payload.get("composition", {})
            self.composition_canvas_size = (
                tuple(composition_data["canvas_size"])
                if composition_data.get("canvas_size")
                else None
            )
            self.composition_layers = [
                self._normalize_composition_layer({
                    "name": layer.get("name", f"Layer {index + 1}"),
                    "path": layer.get("original_path"),
                    "image": _read_archived_image(
                        archive,
                        layer["asset"],
                    ).convert("RGBA"),
                    "x": float(layer.get("x", 0.0)),
                    "y": float(layer.get("y", 0.0)),
                    "scale": float(layer.get("scale", 1.0)),
                    "visible": bool(layer.get("visible", True)),
                    **{
                        key: layer.get(key, default)
                        for key, default in COMPOSITION_LAYER_DEFAULTS.items()
                    },
                })
                for index, layer in enumerate(composition_data.get("layers", []))
            ]
            selected_index = composition_data.get("selected_index")
            self.composition_selected_index = (
                selected_index
                if selected_index is not None
                and 0 <= selected_index < len(self.composition_layers)
                else (len(self.composition_layers) - 1 if self.composition_layers else None)
            )
            self._refresh_composition_layer_list()
            if self.composition_layers:
                self._update_composition_output(mark_dirty=False)
                if composition_data.get("active", False):
                    self.is_composition_active = True
                    try:
                        self.left_notebook.select(self.compose_tab)
                    except Exception:
                        pass
        else:
            self._restore_slicer_settings(payload.get("slicer_settings", {}))
            gif_settings = payload.get("gif_settings", {})
            self.gif_frame_paths = gif_settings.get("frame_paths", [])
            self.gif_anchor.set(gif_settings.get("anchor", "center"))
            self.gif_duration_ms.set(gif_settings.get("duration", 100))
            self.gif_alpha_threshold.set(gif_settings.get("alpha_threshold", 128))
            self.gif_padding.set(gif_settings.get("padding", 0))
            self.gif_frame_export_format.set(gif_settings.get("frame_export_format", "PNG"))
            if self.gif_frame_paths:
                self._reload_gif_frames_from_paths()

        self.current_project_path = project_path
        self.project_dirty = False

    def load_project(self):
        if not self._confirm_unsaved_changes("opening another project"):
            return False
        path = filedialog.askopenfilename(
            title="Load Transparentor Project",
            filetypes=[("Transparentor Project", "*.tpr"), ("Legacy JSON Project", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return False

        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path, "r") as archive:
                    payload = json.loads(archive.read("project.json").decode("utf-8"))
                    self._restore_project_payload(payload, path, archive)
            else:
                with open(path, "r", encoding="utf-8") as project_file:
                    payload = json.load(project_file)
                self._restore_project_payload(payload, path)
            messagebox.showinfo("Load Project", "Project loaded successfully!")
            return True
        except Exception as error:
            messagebox.showerror("Load Project", f"Failed to load project:\n{error}")
            return False

    def _reload_gif_frames_from_paths(self):
        try:
            self.gif_src_images = [Image.open(p).convert("RGBA") for p in self.gif_frame_paths]
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open one or more GIF frames:\n{e}")
            self.gif_src_images = []
            self.gif_frame_paths = []
            return
        self.gif_aligned_rgba = []
        self.gif_preview_index = 0
        self.gif_template_box = None
        self.gif_aligned_template_box = None
        self.gif_template_frame_idx = None
        self.gif_scrub.configure(from_=0, to=max(0, len(self.gif_frame_paths) - 1))
        self.gif_scrub.set(0)
        self._refresh_gif_frame_list()
        self.schedule_gif_preview_update()

    def on_app_closing(self):
        if not self._confirm_unsaved_changes("closing Transparentor"):
            return
        self._cleanup_before_exit()
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _cleanup_before_exit(self):
        if getattr(self, "_cleanup_complete", False):
            return
        self._cleanup_complete = True

        shutdown_event = getattr(self, "_shutdown_event", None)
        if shutdown_event is None:
            shutdown_event = threading.Event()
            self._shutdown_event = shutdown_event
        shutdown_event.set()

        # Prevent queued/batch AI work from starting another image.
        self.batch_running = False

        # Drop every ONNX/rembg session owned by this app. ONNX worker threads
        # are native threads inside Transparentor, not standalone executables.
        sessions = []
        session_lock = getattr(self, "ai_session_lock", None)
        if session_lock is not None:
            lock_acquired = session_lock.acquire(blocking=False)
            if lock_acquired:
                try:
                    sessions = list(getattr(self, "ai_sessions", {}).values())
                    self.ai_sessions = {}
                finally:
                    session_lock.release()
            else:
                # Never make the close button wait for a large model load or
                # inference call. The process-level exit below is the fallback.
                sessions = list(getattr(self, "ai_sessions", {}).values())
                self.ai_sessions = {}
        elif hasattr(self, "ai_sessions"):
            sessions = list(self.ai_sessions.values())
            self.ai_sessions = {}
        for session in sessions:
            try:
                if hasattr(session, "inner_session"):
                    session.inner_session = None
            except Exception:
                pass
        sessions.clear()

        # Explicitly clear all PIL image references and batch variables from memory
        self.original_img = None
        self.edited_img = None
        self.gif_src_images = []
        self.gif_aligned_rgba = []
        self.gif_thumb_refs = []
        self.slicer_batch_images = []
        self.slicer_boxes = []
        self.composition_layers = []
        self.composition_history = []
        self.composition_future_history = []
        self.batch_preview_image = None
        self.batch_filmstrip_refs = []
        self.batch_thumbnail_cache = {}
        self.edit_queue_active = False
        self.edit_queue_running = False
        self.edit_queue_results = {}
        self.edit_queue_errors = {}
        for timer_name in ("ai_progress_after_id", "ai_progress_reset_after_id"):
            timer_id = getattr(self, timer_name, None)
            if timer_id is not None:
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
                setattr(self, timer_name, None)
        gc.collect()

    # ===== PNG -> aligned animated GIF export =====
    def _natural_sort_key(self, path: str):
        name = os.path.basename(path)
        parts = re.split(r'(\d+)', name)
        out = []
        for p in parts:
            if p.isdigit():
                out.append(int(p))
            else:
                out.append(p.lower())
        return out

    def _alpha_bbox(self, img: Image.Image, alpha_threshold: int = 1):
        if img is None:
            return None
        rgba = img.convert("RGBA")
        a = rgba.getchannel("A")
        # Threshold to avoid cropping away antialiased edges (default: keep any nonzero alpha)
        if alpha_threshold <= 0:
            return a.getbbox()
        lut = [255 if v >= alpha_threshold else 0 for v in range(256)]
        mask = a.point(lut)
        return mask.getbbox()

    def _content_centroid(self, rgba: Image.Image, bbox, alpha_threshold: int = 1):
        # Returns centroid (cx, cy) in image coordinates for non-transparent pixels.
        if bbox is None:
            return None
        x0, y0, x1, y1 = bbox
        a = rgba.getchannel("A").crop((x0, y0, x1, y1))
        # Weight by alpha to keep antialiased edges from dominating.
        px = a.load()
        w, h = a.size
        total = 0
        sx = 0
        sy = 0
        for yy in range(h):
            for xx in range(w):
                av = px[xx, yy]
                if av < alpha_threshold:
                    continue
                total += av
                sx += xx * av
                sy += yy * av
        if total <= 0:
            return None
        return (x0 + (sx / total), y0 + (sy / total))

    def _find_best_match(self, frame, template, orig_x, orig_y, search_range=120):
        tw, th = template.size
        fw, fh = frame.size
        
        # Choose downscaling factor based on template size (only downscale if template is big enough)
        if tw < 32 or th < 32:
            return self._find_best_match_raw(frame, template, orig_x, orig_y, search_range, num_samples=64)
            
        coarse_factor = 4
        tw_c = max(8, tw // coarse_factor)
        th_c = max(8, th // coarse_factor)
        fw_c = max(16, fw // coarse_factor)
        fh_c = max(16, fh // coarse_factor)
        
        # Bilinear downsampling is fast and preserves general structure
        template_coarse = template.resize((tw_c, th_c), Image.Resampling.BILINEAR)
        frame_coarse = frame.resize((fw_c, fh_c), Image.Resampling.BILINEAR)
        
        dx_coarse, dy_coarse = self._find_best_match_raw(
            frame_coarse,
            template_coarse,
            int(orig_x / coarse_factor),
            int(orig_y / coarse_factor),
            search_range=int(search_range / coarse_factor),
            num_samples=32
        )
        
        fine_orig_x = orig_x + dx_coarse * coarse_factor
        fine_orig_y = orig_y + dy_coarse * coarse_factor
        
        dx_fine, dy_fine = self._find_best_match_raw(
            frame,
            template,
            fine_orig_x,
            fine_orig_y,
            search_range=3,
            num_samples=128
        )
        
        return dx_coarse * coarse_factor + dx_fine, dy_coarse * coarse_factor + dy_fine

    def _find_best_match_raw(self, frame, template, orig_x, orig_y, search_range=30, num_samples=128):
        tw, th = template.size
        fw, fh = frame.size
        
        min_dx = max(-search_range, -orig_x)
        max_dx = min(search_range, fw - tw - orig_x)
        min_dy = max(-search_range, -orig_y)
        max_dy = min(search_range, fh - th - orig_y)
        
        if min_dx > max_dx:
            min_dx = max_dx = 0
        if min_dy > max_dy:
            min_dy = max_dy = 0
            
        template_pixels = template.load()
        
        # Sample a denser 16x16 grid to locate high-contrast visual features
        xs = sorted(list(set(int(i * tw / 16) for i in range(16))))
        ys = sorted(list(set(int(j * th / 16) for j in range(16))))
        xs = [x for x in xs if 0 <= x < tw - 1]
        ys = [y for y in ys if 0 <= y < th - 1]
        
        candidates = []
        for x in xs:
            for y in ys:
                r, g, b, a = template_pixels[x, y]
                # Compare to right and down neighbors to compute local gradient/contrast
                r_r, g_r, b_r, _ = template_pixels[x + 1, y]
                r_d, g_d, b_d, _ = template_pixels[x, y + 1]
                
                # Weight contrast by alpha so transparent borders don't get selected
                contrast = (abs(r - r_r) + abs(g - g_r) + abs(b - b_r) + 
                            abs(r - r_d) + abs(g - g_d) + abs(b - b_d)) * a
                candidates.append((contrast, x, y, r, g, b, a))
                
        # Sort candidates by contrast descending and pick the top strongest features (edges/corners)
        candidates.sort(key=lambda c: c[0], reverse=True)
        samples = [(x, y, r, g, b, a) for contrast, x, y, r, g, b, a in candidates[:num_samples]]
        
        # Fallback to simple grid if we don't have enough features
        if len(samples) < 16:
            samples = []
            xs_simple = sorted(list(set(int(i * tw / 8) for i in range(8))))
            ys_simple = sorted(list(set(int(j * th / 8) for j in range(8))))
            for x in xs_simple:
                for y in ys_simple:
                    if 0 <= x < tw and 0 <= y < th:
                        r, g, b, a = template_pixels[x, y]
                        samples.append((x, y, r, g, b, a))
        
        if not samples:
            return 0, 0
            
        frame_pixels = frame.load()
        best_mad = float('inf')
        best_dx = 0
        best_dy = 0
        
        orig_x_f = orig_x
        orig_y_f = orig_y
        
        for dy in range(min_dy, max_dy + 1):
            for dx in range(min_dx, max_dx + 1):
                total_diff = 0
                target_x = orig_x_f + dx
                target_y = orig_y_f + dy
                
                for sx, sy, tr, tg, tb, ta in samples:
                    fr, fg, fb, fa = frame_pixels[target_x + sx, target_y + sy]
                    
                    # Division-free alpha weighted matching
                    weight = ta * fa
                    diff_rgb = (abs(fr - tr) + abs(fg - tg) + abs(fb - tb)) * weight
                    total_diff += diff_rgb + abs(fa - ta) * 65025
                    
                    if total_diff >= best_mad:
                        break
                else:
                    best_mad = total_diff
                    best_dx = dx
                    best_dy = dy
                    
        return best_dx, best_dy

    def gif_aligned_to_source_coords(self, ax_coord, ay_coord, frame_idx):
        if hasattr(self, "gif_frame_alignment_info") and self.gif_frame_alignment_info and frame_idx < len(self.gif_frame_alignment_info):
            ox, oy, x0, y0 = self.gif_frame_alignment_info[frame_idx]
            return ax_coord - ox + x0, ay_coord - oy + y0
        return ax_coord, ay_coord

    def gif_image_to_canvas(self, ix, iy):
        if not self.gif_aligned_rgba:
            return 0, 0
        idx = int(max(0, min(self.gif_preview_index, len(self.gif_aligned_rgba) - 1)))
        frame_w, frame_h = self.gif_aligned_rgba[idx].size
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10 or h < 10:
            return 0, 0

        if self.zoom_fit:
            scale = min(w / frame_w, h / frame_h) if frame_w and frame_h else 1.0
        else:
            scale = self.zoom_level

        scaled_w = frame_w * scale
        scaled_h = frame_h * scale
        center_x = w // 2 + self.pan_x
        center_y = h // 2 + self.pan_y
        img_left = center_x - scaled_w // 2
        img_top = center_y - scaled_h // 2

        cx = img_left + ix * scale
        cy = img_top + iy * scale
        return cx, cy

    def _align_rgba_frames(self, images, alpha_threshold: int, anchor: str, padding: int):
        # Align frames by a shared anchor point computed from detected content.
        # This avoids vertical drift when content boxes vary slightly frame-to-frame.
        anchor_key = str(anchor).lower().strip()
        padding = max(0, int(padding))

        if anchor_key == "template" and (not hasattr(self, "gif_template_box") or self.gif_template_box is None):
            anchor_key = "center"

        # Crop template if anchor is template
        template = None
        if anchor_key == "template" and self.gif_template_box is not None:
            ref_idx = self.gif_template_frame_idx
            if ref_idx < len(images):
                template = images[ref_idx].convert("RGBA").crop(self.gif_template_box)
                tx0, ty0, tx1, ty1 = self.gif_template_box
                tw = tx1 - tx0
                th = ty1 - ty0
                tw_half = tw / 2.0
                th_half = th / 2.0

        crops = []
        anchors = []  # (ax, ay) within crop coordinates
        bboxes_info = []  # Store x0, y0 for each frame
        
        for im in images:
            rgba = im.convert("RGBA")
            bbox = self._alpha_bbox(rgba, alpha_threshold)
            if bbox is None:
                content = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                crops.append(content)
                anchors.append((0.0, 0.0))
                bboxes_info.append((0, 0))
                continue
            x0, y0, x1, y1 = bbox
            content = rgba.crop(bbox)
            cw, ch = content.size
            bboxes_info.append((x0, y0))

            if anchor_key == "template" and template is not None:
                dx, dy = self._find_best_match(rgba, template, tx0, ty0, search_range=120)
                tcx = tx0 + dx + tw_half
                tcy = ty0 + dy + th_half
                ax = float(tcx - x0)
                ay = float(tcy - y0)
            elif anchor_key == "centroid":
                c = self._content_centroid(rgba, bbox, max(1, alpha_threshold))
                if c is None:
                    ax = cw * 0.5
                    ay = ch * 0.5
                else:
                    ax = float(c[0] - x0)
                    ay = float(c[1] - y0)
            elif anchor_key in ("bottom", "bottom-center", "bc"):
                ax = cw * 0.5
                ay = float(ch)
            elif anchor_key in ("top", "top-center", "tc"):
                ax = cw * 0.5
                ay = 0.0
            elif anchor_key in ("topleft", "top-left", "tl"):
                ax = 0.0
                ay = 0.0
            elif anchor_key in ("bottomleft", "bottom-left", "bl"):
                ax = 0.0
                ay = float(ch)
            elif anchor_key in ("topright", "top-right", "tr"):
                ax = float(cw)
                ay = 0.0
            elif anchor_key in ("bottomright", "bottom-right", "br"):
                ax = float(cw)
                ay = float(ch)
            else:
                # center
                ax = cw * 0.5
                ay = ch * 0.5

            crops.append(content)
            anchors.append((ax, ay))

        # Compute required extents from anchor point so everything fits on a shared canvas
        max_left = 0.0
        max_right = 0.0
        max_top = 0.0
        max_bottom = 0.0
        for content, (ax, ay) in zip(crops, anchors):
            cw, ch = content.size
            max_left = max(max_left, ax)
            max_right = max(max_right, float(cw) - ax)
            max_top = max(max_top, ay)
            max_bottom = max(max_bottom, float(ch) - ay)

        canvas_w = int(math.ceil(max_left + max_right)) + padding * 2
        canvas_h = int(math.ceil(max_top + max_bottom)) + padding * 2
        canvas_w = max(canvas_w, 1)
        canvas_h = max(canvas_h, 1)

        if anchor_key == "template" and self.gif_template_box is not None:
            self.gif_aligned_template_box = (
                padding + max_left - tw_half,
                padding + max_top - th_half,
                padding + max_left + tw_half,
                padding + max_top + th_half
            )
        else:
            self.gif_aligned_template_box = None

        self.gif_frame_alignment_info = []
        aligned = []
        for content, (ax, ay), (x0, y0) in zip(crops, anchors, bboxes_info):
            frame = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            ox = int(round(padding + max_left - ax))
            oy = int(round(padding + max_top - ay))
            frame.paste(content, (ox, oy), content)
            aligned.append(frame)
            self.gif_frame_alignment_info.append((ox, oy, x0, y0))
        return aligned

    def _rgba_to_gif_frame(self, rgba: Image.Image):
        # Convert RGBA to a paletted frame with a reserved transparency index.
        rgba = rgba.convert("RGBA")
        alpha = rgba.getchannel("A")
        # Use 255 colors so index 255 can be transparency.
        pal = rgba.convert('P', palette=Image.Palette.ADAPTIVE, colors=255)
        # Mark fully transparent pixels to index 255.
        transparent_mask = alpha.point(lambda a: 255 if a == 0 else 0)
        pal.paste(255, transparent_mask)
        pal.info['transparency'] = 255
        return pal

    def export_aligned_gif(self):
        # Backwards-compat entrypoint (older toolbar or scripts).
        self.enter_png_gif_mode()

    # ===== SLICER TOOL =====

    def _setup_slicer_tab(self):
        """Build the Slicer tab UI."""
        slicer_frame = ttk.LabelFrame(self.slicer_tab, text=" Sprite Slicer ", style='Card.TLabelframe')
        slicer_frame.pack(fill=tk.X, pady=10, padx=5)

        # Load button
        btn_row = ttk.Frame(slicer_frame)
        btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row, text="Load Image", style='Action.TButton', command=self.slicer_load_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Clear Slices", style='Danger.TButton', command=self.slicer_clear).pack(side=tk.LEFT, padx=2)

        # Image info label
        self.slicer_info_label = ttk.Label(slicer_frame, text="No image loaded")
        self.slicer_info_label.pack(anchor="w", padx=5, pady=2)

        ttk.Separator(slicer_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # Manual Mode toggle
        mode_toggle_row = ttk.Frame(slicer_frame)
        mode_toggle_row.pack(fill=tk.X, pady=2)
        self.slicer_use_manual_check = ttk.Checkbutton(
            mode_toggle_row, 
            text="Manual Box Mode (Drag on preview to slice)", 
            variable=self.slicer_use_manual, 
            command=self.slicer_on_mode_toggle
        )
        self.slicer_use_manual_check.pack(anchor="w", padx=5)

        ttk.Separator(slicer_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # Grid settings
        grid_frame = ttk.Frame(slicer_frame)
        grid_frame.pack(fill=tk.X, pady=5)

        ttk.Label(grid_frame, text="Columns:").pack(side=tk.LEFT, padx=2)
        self.slicer_cols_spin = tk.Spinbox(grid_frame, from_=1, to=20, textvariable=self.slicer_cols, width=4, command=self.slicer_update_preview)
        self.slicer_cols_spin.pack(side=tk.LEFT, padx=2)
        self.slicer_cols.trace_add("write", lambda *_: self.slicer_update_preview())

        ttk.Label(grid_frame, text="Rows:").pack(side=tk.LEFT, padx=8)
        self.slicer_rows_spin = tk.Spinbox(grid_frame, from_=1, to=20, textvariable=self.slicer_rows, width=4, command=self.slicer_update_preview)
        self.slicer_rows_spin.pack(side=tk.LEFT, padx=2)
        self.slicer_rows.trace_add("write", lambda *_: self.slicer_update_preview())

        # Grid offsets (Margins/Padding)
        offset_frame = ttk.Frame(slicer_frame)
        offset_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(offset_frame, text="Margin X:").pack(side=tk.LEFT, padx=(2, 0))
        self.slicer_margin_x_spin = tk.Spinbox(offset_frame, from_=-999, to=999, textvariable=self.slicer_margin_x, width=4, command=self.slicer_update_preview)
        self.slicer_margin_x_spin.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(offset_frame, text="Y:").pack(side=tk.LEFT, padx=(4, 0))
        self.slicer_margin_y_spin = tk.Spinbox(offset_frame, from_=-999, to=999, textvariable=self.slicer_margin_y, width=4, command=self.slicer_update_preview)
        self.slicer_margin_y_spin.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(offset_frame, text="Pad X:").pack(side=tk.LEFT, padx=(8, 0))
        self.slicer_padding_x_spin = tk.Spinbox(offset_frame, from_=-999, to=999, textvariable=self.slicer_padding_x, width=4, command=self.slicer_update_preview)
        self.slicer_padding_x_spin.pack(side=tk.LEFT, padx=2)

        ttk.Label(offset_frame, text="Y:").pack(side=tk.LEFT, padx=(4, 0))
        self.slicer_padding_y_spin = tk.Spinbox(offset_frame, from_=-999, to=999, textvariable=self.slicer_padding_y, width=4, command=self.slicer_update_preview)
        self.slicer_padding_y_spin.pack(side=tk.LEFT, padx=2)

        self.slicer_margin_x.trace_add("write", lambda *_: self.slicer_update_preview())
        self.slicer_margin_y.trace_add("write", lambda *_: self.slicer_update_preview())
        self.slicer_padding_x.trace_add("write", lambda *_: self.slicer_update_preview())
        self.slicer_padding_y.trace_add("write", lambda *_: self.slicer_update_preview())

        # Segment Expansion (Overlap)
        expand_frame = ttk.Frame(slicer_frame)
        expand_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(expand_frame, text="Expand X:").pack(side=tk.LEFT, padx=(2, 0))
        self.slicer_expand_w_spin = tk.Spinbox(expand_frame, from_=0, to=999, textvariable=self.slicer_expand_w, width=4, command=self.slicer_update_preview)
        self.slicer_expand_w_spin.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(expand_frame, text="Y:").pack(side=tk.LEFT, padx=(4, 0))
        self.slicer_expand_h_spin = tk.Spinbox(expand_frame, from_=0, to=999, textvariable=self.slicer_expand_h, width=4, command=self.slicer_update_preview)
        self.slicer_expand_h_spin.pack(side=tk.LEFT, padx=2)

        # Presets
        preset_frame = ttk.LabelFrame(slicer_frame, text=" Presets ", style='Card.TLabelframe')
        preset_frame.pack(fill=tk.X, pady=5, padx=2)

        preset_row1 = ttk.Frame(preset_frame)
        preset_row1.pack(fill=tk.X, pady=2)
        ttk.Button(preset_row1, text="2×1", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(2, 1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_row1, text="3×1", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(3, 1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_row1, text="4×1", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(4, 1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_row1, text="6×1", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(6, 1)).pack(side=tk.LEFT, padx=2)

        preset_row2 = ttk.Frame(preset_frame)
        preset_row2.pack(fill=tk.X, pady=2)
        ttk.Button(preset_row2, text="2×2", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(2, 2)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_row2, text="3×2", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(3, 2)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_row2, text="4×2", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(4, 2)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_row2, text="4×4", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(4, 4)).pack(side=tk.LEFT, padx=2)

        preset_row3 = ttk.Frame(preset_frame)
        preset_row3.pack(fill=tk.X, pady=2)
        ttk.Button(preset_row3, text="3×3", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(3, 3)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_row3, text="8×8", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(8, 8)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_row3, text="16×16", style='ToolbarGrey.TButton', command=lambda: self.slicer_apply_preset(16, 16)).pack(side=tk.LEFT, padx=2)

        ttk.Separator(slicer_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # Output options
        opt_frame = ttk.Frame(slicer_frame)
        opt_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(opt_frame, text="Enable Crop Box", variable=self.slicer_crop_square, command=self.slicer_update_preview).pack(anchor="w")
        ttk.Checkbutton(opt_frame, text="Center On Content", variable=self.slicer_crop_center_content, command=self.slicer_update_preview).pack(anchor="w", padx=(18, 0))
        ttk.Checkbutton(opt_frame, text="Trim Empty Space (Autocrop transparent margins)", variable=self.slicer_trim_transparency, command=self.slicer_update_preview).pack(anchor="w")
        self.slicer_trim_transparency.trace_add("write", lambda *_: self.slicer_update_preview())

        trim_thresh_row = ttk.Frame(opt_frame)
        trim_thresh_row.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(trim_thresh_row, text="Trim Alpha Thresh:").pack(side=tk.LEFT, padx=(18, 0))
        tk.Spinbox(
            trim_thresh_row, 
            from_=1, 
            to=255, 
            textvariable=self.slicer_trim_threshold, 
            width=4, 
            command=self.slicer_update_preview
        ).pack(side=tk.LEFT, padx=2)
        self.slicer_trim_threshold.trace_add("write", lambda *_: self.slicer_update_preview())

        square_trim_row = ttk.Frame(opt_frame)
        square_trim_row.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(square_trim_row, text="Crop Box X:").pack(side=tk.LEFT, padx=(18, 0))
        tk.Spinbox(square_trim_row, from_=-999, to=999, textvariable=self.slicer_square_trim_x, width=4, command=self.slicer_update_preview).pack(side=tk.LEFT, padx=2)
        ttk.Label(square_trim_row, text="Y:").pack(side=tk.LEFT, padx=(6, 0))
        tk.Spinbox(square_trim_row, from_=-999, to=999, textvariable=self.slicer_square_trim_y, width=4, command=self.slicer_update_preview).pack(side=tk.LEFT, padx=2)

        self.slicer_square_trim_x.trace_add("write", lambda *_: self.slicer_update_preview())
        self.slicer_square_trim_y.trace_add("write", lambda *_: self.slicer_update_preview())
        self.slicer_expand_w.trace_add("write", lambda *_: self.slicer_update_preview())
        self.slicer_expand_h.trace_add("write", lambda *_: self.slicer_update_preview())

        size_row = ttk.Frame(slicer_frame)
        size_row.pack(fill=tk.X, pady=2)
        ttk.Label(size_row, text="Output Size:").pack(side=tk.LEFT, padx=2)
        self.slicer_size_combo = ttk.Combobox(
            size_row,
            textvariable=self.slicer_output_size,
            state="readonly",
            values=["Original", "32×32", "64×64", "128×128", "256×256", "512×512"],
            width=10,
        )
        self.slicer_size_combo.pack(side=tk.LEFT, padx=4)
        self.slicer_size_combo.bind("<<ComboboxSelected>>", lambda _e: self.slicer_update_preview())

        # Scale (mouse wheel info)
        scale_row = ttk.Frame(slicer_frame)
        scale_row.pack(fill=tk.X, pady=5)
        ttk.Label(scale_row, text="Preview Scale:").pack(side=tk.LEFT, padx=2)
        self.slicer_scale_label = ttk.Label(scale_row, text="100%")
        self.slicer_scale_label.pack(side=tk.LEFT, padx=4)
        ttk.Label(scale_row, text="(Mouse wheel to zoom)", font=('Arial', 8)).pack(side=tk.LEFT, padx=4)

        ttk.Separator(slicer_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # Slice info
        self.slicer_slice_info = ttk.Label(slicer_frame, text="Cell size: -")
        self.slicer_slice_info.pack(anchor="w", padx=5, pady=2)

        # Export button
        export_row = ttk.Frame(slicer_frame)
        export_row.pack(fill=tk.X, pady=8)
        ttk.Button(export_row, text="Export Slices", style='Success.TButton', command=self.slicer_export).pack(side=tk.LEFT, padx=2)
        self.slicer_format_combo = ttk.Combobox(
            export_row,
            textvariable=self.slicer_export_format,
            values=TRANSPARENT_EXPORT_FORMATS,
            state="readonly",
            width=6,
        )
        self.slicer_format_combo.pack(side=tk.LEFT, padx=(2, 6))
        ttk.Button(export_row, text="Export to GIF", style='ToolbarBlue.TButton', command=self.slicer_send_to_gif).pack(side=tk.LEFT, padx=2)

        # Scrollable names area (for naming each slice)
        names_frame = ttk.LabelFrame(self.slicer_tab, text=" Slice Names (optional) ", style='Card.TLabelframe')
        names_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)

        # Create a canvas with scrollbar for names
        self.slicer_names_canvas = tk.Canvas(names_frame, bg=self.PS1_GREY_LT, highlightthickness=0)
        self.slicer_names_scrollbar = ttk.Scrollbar(names_frame, orient="vertical", command=self.slicer_names_canvas.yview)
        self.slicer_names_inner = ttk.Frame(self.slicer_names_canvas, style='NamesInner.TFrame')

        self.slicer_names_canvas.configure(yscrollcommand=self.slicer_names_scrollbar.set)
        self.slicer_names_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.slicer_names_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.slicer_names_window = self.slicer_names_canvas.create_window((0, 0), window=self.slicer_names_inner, anchor="nw")

        self.slicer_names_inner.bind("<Configure>", lambda e: self.slicer_names_canvas.configure(scrollregion=self.slicer_names_canvas.bbox("all")))
        self.slicer_names_canvas.bind("<Configure>", lambda e: self.slicer_names_canvas.itemconfig(self.slicer_names_window, width=e.width))

    def slicer_load_image(self):
        """Load an image (or multiple images for batch cropping) for slicing."""
        paths = filedialog.askopenfilenames(
            title="Select Image(s) to Slice/Batch Crop",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All Files", "*.*")]
        )
        if not paths:
            return
        if len(paths) > 1:
            self._load_multiple_slicer_images(paths)
        else:
            self.open_image_from_path(paths[0])

    def slicer_clear(self):
        """Clear the loaded slicer image."""
        if self.slicer_image is not None or (hasattr(self, "slicer_batch_images") and self.slicer_batch_images):
            self._save_slicer_state()
        self.slicer_image = None
        self.slicer_image_path = None
        self.slicer_batch_images = []
        self.slicer_batch_active_idx = 0
        self.slicer_info_label.config(text="No image loaded")
        self.slicer_slice_info.config(text="Cell size: -")
        self.slicer_names = []
        for widget in self.slicer_names_inner.winfo_children():
            widget.destroy()
        try:
            self.slicer_use_manual_check.config(state="normal")
        except:
            pass
        self.slicer_on_mode_toggle()
        self.update_preview()

    def _load_multiple_slicer_images(self, paths):
        self.slicer_clear()
        self.slicer_batch_images = []
        self.slicer_batch_active_idx = 0
        
        self.slicer_use_manual.set(False)
        self.slicer_on_mode_toggle()
        
        for path in sorted(paths, key=self._natural_sort_key):
            try:
                img = Image.open(path)
                name = os.path.basename(path)
                stem, _ = os.path.splitext(name)
                var = tk.StringVar(value=stem)
                var.trace_add("write", lambda *_: self.slicer_update_preview())
                self.slicer_batch_images.append({
                    "image": img,
                    "path": path,
                    "name_var": var
                })
            except Exception as e:
                print(f"Failed to load batch image {path}: {e}")
                
        if self.slicer_batch_images:
            self.slicer_view_batch_image(0)
            self.slicer_rebuild_names()

    def slicer_view_batch_image(self, index: int):
        if hasattr(self, "slicer_batch_images") and 0 <= index < len(self.slicer_batch_images):
            self.slicer_batch_active_idx = index
            item = self.slicer_batch_images[index]
            self.slicer_image = item["image"].copy()
            self.slicer_image_path = item["path"]
            w, h = self.slicer_image.size
            name = os.path.basename(self.slicer_image_path)
            self.slicer_info_label.config(text=f"{name} ({w}×{h}) [Batch {index+1}/{len(self.slicer_batch_images)}]")
            self.slicer_rebuild_names()
            self.slicer_update_preview()

    def slicer_delete_batch_image(self, index: int):
        if hasattr(self, "slicer_batch_images") and 0 <= index < len(self.slicer_batch_images):
            self._save_slicer_state()
            self.slicer_batch_images.pop(index)
            if not self.slicer_batch_images:
                self.slicer_clear()
            else:
                active = getattr(self, "slicer_batch_active_idx", 0)
                if active >= len(self.slicer_batch_images):
                    active = len(self.slicer_batch_images) - 1
                self.slicer_view_batch_image(active)
                self.slicer_rebuild_names()

    def slicer_apply_preset(self, cols: int, rows: int):
        """Apply a grid preset."""
        self.slicer_cols.set(cols)
        self.slicer_rows.set(rows)
        self.slicer_rebuild_names()
        self.slicer_update_preview()

    def slicer_on_mode_toggle(self):
        is_manual = self.slicer_use_manual.get()
        is_batch = hasattr(self, "slicer_batch_images") and bool(self.slicer_batch_images)
        if is_batch:
            self.mode = "picker"
            self.canvas.config(cursor="arrow")
            grid_state = "disabled"
            try:
                self.slicer_use_manual_check.config(state="disabled")
            except Exception:
                pass
        elif is_manual:
            self.mode = "slicer_manual"
            self.canvas.config(cursor="crosshair")
            grid_state = "disabled"
            try:
                self.slicer_use_manual_check.config(state="normal")
            except Exception:
                pass
        else:
            self.mode = "picker"
            self.canvas.config(cursor="crosshair")
            grid_state = "normal"
            try:
                self.slicer_use_manual_check.config(state="normal")
            except Exception:
                pass
            
        for spin in (self.slicer_cols_spin, self.slicer_rows_spin, 
                     self.slicer_margin_x_spin, self.slicer_margin_y_spin,
                     self.slicer_padding_x_spin, self.slicer_padding_y_spin,
                     self.slicer_expand_w_spin, self.slicer_expand_h_spin):
            try:
                spin.config(state=grid_state)
            except Exception:
                pass
                    
        self.slicer_rebuild_names()
        self.slicer_update_preview()

    def slicer_delete_manual_box(self, index: int):
        if 0 <= index < len(self.slicer_boxes):
            self._save_slicer_state()
            self.slicer_boxes.pop(index)
            self.slicer_rebuild_names()
            self.slicer_update_preview()

    def slicer_rebuild_names(self):
        """Rebuild the slice name entry fields."""
        # Clear existing
        for widget in self.slicer_names_inner.winfo_children():
            widget.destroy()
        self.slicer_names = []

        if hasattr(self, "slicer_batch_images") and self.slicer_batch_images:
            for i, item in enumerate(self.slicer_batch_images):
                frame = ttk.Frame(self.slicer_names_inner, style='NamesInner.TFrame')
                frame.pack(fill=tk.X, pady=1)
                
                is_active = (i == getattr(self, "slicer_batch_active_idx", 0))
                lbl_style = 'Action.TLabel' if is_active else 'NamesLabel.TLabel'
                
                lbl = ttk.Label(frame, text=f"{i+1}:", width=3, style=lbl_style)
                lbl.pack(side=tk.LEFT)
                
                entry = ttk.Entry(frame, textvariable=item["name_var"], width=14)
                entry.pack(side=tk.LEFT, padx=1)
                
                view_btn = CustomButton(
                    frame, 
                    text="👁️", 
                    style='Success.TButton' if is_active else 'ToolbarGrey.TButton', 
                    custom_w=28,
                    custom_h=22,
                    command=lambda idx=i: self.slicer_view_batch_image(idx)
                )
                view_btn.pack(side=tk.LEFT, padx=1)

                del_btn = CustomButton(
                    frame, 
                    text="❌", 
                    style='ToolbarRed.TButton', 
                    custom_w=28,
                    custom_h=22,
                    command=lambda idx=i: self.slicer_delete_batch_image(idx)
                )
                del_btn.pack(side=tk.LEFT, padx=1)
                self.slicer_names.append(item["name_var"])
        elif hasattr(self, "slicer_use_manual") and self.slicer_use_manual.get():
            for i, box_info in enumerate(self.slicer_boxes):
                frame = ttk.Frame(self.slicer_names_inner, style='NamesInner.TFrame')
                frame.pack(fill=tk.X, pady=1)
                ttk.Label(frame, text=f"{i+1}:", width=3, style='NamesLabel.TLabel').pack(side=tk.LEFT)
                
                if "name_var" not in box_info:
                    box_info["name_var"] = tk.StringVar(value=box_info.get("name", f"slice_{i}"))
                    box_info["name_var"].trace_add("write", lambda *_: self.slicer_update_preview())
                
                entry = ttk.Entry(frame, textvariable=box_info["name_var"], width=16)
                entry.pack(side=tk.LEFT, padx=2)
                
                del_btn = CustomButton(
                    frame, 
                    text="❌", 
                    style='ToolbarRed.TButton', 
                    custom_w=28,
                    custom_h=22,
                    command=lambda idx=i: self.slicer_delete_manual_box(idx)
                )
                del_btn.pack(side=tk.LEFT, padx=2)
                self.slicer_names.append(box_info["name_var"])
        else:
            try:
                cols = int(self.slicer_cols.get())
                rows = int(self.slicer_rows.get())
            except:
                return

            total = cols * rows
            for i in range(total):
                row_idx = i // cols
                col_idx = i % cols
                frame = ttk.Frame(self.slicer_names_inner, style='NamesInner.TFrame')
                frame.pack(fill=tk.X, pady=1)
                ttk.Label(frame, text=f"{i+1}:", width=3, style='NamesLabel.TLabel').pack(side=tk.LEFT)
                var = tk.StringVar(value=f"slice_{row_idx}_{col_idx}")
                var.trace_add("write", lambda *_: self.slicer_update_preview())
                entry = ttk.Entry(frame, textvariable=var, width=20)
                entry.pack(side=tk.LEFT, padx=2)
                self.slicer_names.append(var)

    def _get_slicer_int_value(self, var, default: int = 0, minimum=None):
        try:
            value = int(var.get())
        except Exception:
            value = default
        if minimum is not None:
            value = max(minimum, value)
        return value

    def _get_slicer_slice_name(self, row_idx: int, col_idx: int):
        if hasattr(self, "slicer_use_manual") and self.slicer_use_manual.get():
            idx = row_idx
            if idx < len(self.slicer_boxes) and "name_var" in self.slicer_boxes[idx]:
                return self.slicer_boxes[idx]["name_var"].get().strip()
            return f"slice_{idx}"
            
        cols = self._get_slicer_int_value(self.slicer_cols, default=1, minimum=1)
        idx = row_idx * cols + col_idx
        if idx < len(self.slicer_names):
            name = self.slicer_names[idx].get().strip()
            if name:
                return name
        return f"slice_{row_idx}_{col_idx}"

    def _get_slicer_overlay_font(self, scale: float):
        font_size = max(14, min(28, int(round(18 * max(0.85, scale)))))
        if font_size in self._slicer_font_cache:
            return self._slicer_font_cache[font_size]
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("segoeui.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
        self._slicer_font_cache[font_size] = font
        return font

    def _fit_text_to_width(self, draw, text: str, font, max_width: int):
        if max_width <= 0:
            return ""
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return text
        ellipsis = "..."
        if draw.textbbox((0, 0), ellipsis, font=font)[2] > max_width:
            return ""
        trimmed = text
        while trimmed:
            candidate = trimmed + ellipsis
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                return candidate
            trimmed = trimmed[:-1]
        return ellipsis

    def _draw_slicer_name_badge(self, draw, text: str, bounds, scale: float):
        x0, y0, x1, y1 = bounds
        if x1 <= x0 or y1 <= y0:
            return
        font = self._get_slicer_overlay_font(scale)
        pad = max(4, min(10, int(round(6 * max(0.85, scale)))))
        max_text_width = max(1, (x1 - x0) - pad * 2)
        display_text = self._fit_text_to_width(draw, text, font, max_text_width)
        if not display_text:
            return
        text_box = draw.textbbox((0, 0), display_text, font=font)
        text_w = text_box[2] - text_box[0]
        text_h = text_box[3] - text_box[1]
        badge_w = min(x1 - x0, text_w + pad * 2)
        badge_h = min(y1 - y0, text_h + pad * 2)
        bx0 = x0
        by0 = y0
        bx1 = bx0 + badge_w
        by1 = by0 + badge_h
        outline_w = 2 if scale >= 1.1 else 1
        draw.rectangle([bx0, by0, bx1, by1], fill=(20, 20, 20, 215), outline=(255, 255, 255, 210), width=outline_w)
        text_x = bx0 + pad
        text_y = by0 + pad - text_box[1]
        draw.text((text_x, text_y), display_text, font=font, fill=(255, 255, 255, 255))

    def _get_slicer_grid_metrics(self):
        cols = self._get_slicer_int_value(self.slicer_cols, default=3, minimum=1)
        rows = self._get_slicer_int_value(self.slicer_rows, default=2, minimum=1)
        mx = self._get_slicer_int_value(self.slicer_margin_x, default=0)
        my = self._get_slicer_int_value(self.slicer_margin_y, default=0)
        px = self._get_slicer_int_value(self.slicer_padding_x, default=0)
        py = self._get_slicer_int_value(self.slicer_padding_y, default=0)

        w_orig, h_orig = self.slicer_image.size
        avail_w = max(1, w_orig - mx)
        avail_h = max(1, h_orig - my)
        total_pad_x = (cols - 1) * px
        total_pad_y = (rows - 1) * py
        cell_w_raw = (avail_w - total_pad_x) / cols
        cell_h_raw = (avail_h - total_pad_y) / rows
        return {
            "cols": cols,
            "rows": rows,
            "mx": mx,
            "my": my,
            "px": px,
            "py": py,
            "w_orig": w_orig,
            "h_orig": h_orig,
            "cell_w_raw": cell_w_raw,
            "cell_h_raw": cell_h_raw,
        }

    def _get_slicer_square_trim_values(self):
        trim_x = self._get_slicer_int_value(self.slicer_square_trim_x, default=0)
        trim_y = self._get_slicer_int_value(self.slicer_square_trim_y, default=0)
        return trim_x, trim_y

    def _get_slicer_crop_center(self, cell_left: float, cell_top: float, cell_w_raw: float, cell_h_raw: float):
        center_x = cell_left + (cell_w_raw * 0.5)
        center_y = cell_top + (cell_h_raw * 0.5)
        if not self.slicer_crop_center_content.get() or self.slicer_image is None:
            return center_x, center_y

        image_w, image_h = self.slicer_image.size
        sample_left = max(0, min(image_w, int(math.floor(cell_left))))
        sample_top = max(0, min(image_h, int(math.floor(cell_top))))
        sample_right = max(0, min(image_w, int(math.ceil(cell_left + cell_w_raw))))
        sample_bottom = max(0, min(image_h, int(math.ceil(cell_top + cell_h_raw))))
        if sample_right <= sample_left or sample_bottom <= sample_top:
            return center_x, center_y

        cell_img = self.slicer_image.crop((sample_left, sample_top, sample_right, sample_bottom))
        bbox = self._alpha_bbox(cell_img, alpha_threshold=1)
        if bbox is None:
            return center_x, center_y

        bbox_center_x = sample_left + ((bbox[0] + bbox[2]) * 0.5)
        bbox_center_y = sample_top + ((bbox[1] + bbox[3]) * 0.5)
        return bbox_center_x, bbox_center_y

    def _get_slicer_square_crop_box(self, cell_left: float, cell_top: float, cell_w_raw: float, cell_h_raw: float):
        trim_x, trim_y = self._get_slicer_square_trim_values()
        base_square_size = min(cell_w_raw, cell_h_raw)
        crop_w = max(1.0, base_square_size - trim_x)
        crop_h = max(1.0, base_square_size - trim_y)
        
        # Apply segment width/height expansion
        expand_w = self.slicer_expand_w.get()
        expand_h = self.slicer_expand_h.get()
        crop_w += expand_w * 2
        crop_h += expand_h * 2
        
        center_x, center_y = self._get_slicer_crop_center(cell_left, cell_top, cell_w_raw, cell_h_raw)
        return (
            center_x - (crop_w * 0.5),
            center_y - (crop_h * 0.5),
            center_x + (crop_w * 0.5),
            center_y + (crop_h * 0.5),
        )

    def _draw_slicer_name_overlays(self, draw, scale: float):
        if self.slicer_image is None:
            return
            
        if hasattr(self, "slicer_batch_images") and self.slicer_batch_images:
            active = getattr(self, "slicer_batch_active_idx", 0)
            if active < len(self.slicer_batch_images):
                item = self.slicer_batch_images[active]
                name = item["name_var"].get().strip()
                left = 0
                top = 0
                right = self.slicer_image.width
                bottom = self.slicer_image.height
                if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                    thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                    bbox = self._alpha_bbox(self.slicer_image, alpha_threshold=thresh)
                    if bbox:
                        left, top, right, bottom = bbox
                
                label_bounds = [
                    int(left * scale) + 3,
                    int(top * scale) + 3,
                    int(right * scale) - 3,
                    int(bottom * scale) - 3,
                ]
                self._draw_slicer_name_badge(draw, name, label_bounds, scale)
            return

        if hasattr(self, "slicer_use_manual") and self.slicer_use_manual.get():
            for i, box_info in enumerate(self.slicer_boxes):
                name = box_info["name_var"].get().strip() if "name_var" in box_info else f"slice_{i}"
                left, top, right, bottom = box_info["box"]
                
                if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                    sub_img = self.slicer_image.crop((int(round(left)), int(round(top)), int(round(right)), int(round(bottom))))
                    thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                    bbox = self._alpha_bbox(sub_img, alpha_threshold=thresh)
                    if bbox:
                        left += bbox[0]
                        top += bbox[1]
                        right = left + (bbox[2] - bbox[0])
                        bottom = top + (bbox[3] - bbox[1])
                
                label_bounds = [
                    int(left * scale) + 3,
                    int(top * scale) + 3,
                    int(right * scale) - 3,
                    int(bottom * scale) - 3,
                ]
                self._draw_slicer_name_badge(draw, name, label_bounds, scale)
            return

        metrics = self._get_slicer_grid_metrics()
        cols = metrics["cols"]
        rows = metrics["rows"]
        mx = metrics["mx"]
        my = metrics["my"]
        px = metrics["px"]
        py = metrics["py"]
        cell_w_raw = metrics["cell_w_raw"]
        cell_h_raw = metrics["cell_h_raw"]

        crop_square = self.slicer_crop_square.get()

        for row_idx in range(rows):
            for col_idx in range(cols):
                x0 = mx + col_idx * (cell_w_raw + px)
                y0 = my + row_idx * (cell_h_raw + py)
                x1 = x0 + cell_w_raw
                y1 = y0 + cell_h_raw

                if crop_square:
                    x0, y0, x1, y1 = self._get_slicer_square_crop_box(x0, y0, cell_w_raw, cell_h_raw)
                else:
                    expand_w = self.slicer_expand_w.get()
                    expand_h = self.slicer_expand_h.get()
                    x0 -= expand_w
                    y0 -= expand_h
                    x1 += expand_w
                    y1 += expand_h

                if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                    w_orig, h_orig = self.slicer_image.size
                    crop_l = max(0, min(w_orig, int(round(x0))))
                    crop_t = max(0, min(h_orig, int(round(y0))))
                    crop_r = max(0, min(w_orig, int(round(x1))))
                    crop_b = max(0, min(h_orig, int(round(y1))))
                    if crop_r > crop_l and crop_b > crop_t:
                        sub_img = self.slicer_image.crop((crop_l, crop_t, crop_r, crop_b))
                        thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                        bbox = self._alpha_bbox(sub_img, alpha_threshold=thresh)
                        if bbox:
                            x0 = crop_l + bbox[0]
                            y0 = crop_t + bbox[1]
                            x1 = crop_l + bbox[2]
                            y1 = crop_t + bbox[3]

                label_bounds = [
                    int(x0 * scale) + 3,
                    int(y0 * scale) + 3,
                    int(x1 * scale) - 3,
                    int(y1 * scale) - 3,
                ]
                self._draw_slicer_name_badge(
                    draw,
                    self._get_slicer_slice_name(row_idx, col_idx),
                    label_bounds,
                    scale,
                )

    def slicer_update_preview(self):
        """Update the preview with slice grid overlay."""
        if hasattr(self, "project_dirty") and self.slicer_image is not None:
            self.project_dirty = True
        # Switch to slicer tab view if we have an image
        if self.is_slicer_active and self.slicer_image is not None:
            # Update scale label
            scale_pct = int(self.slicer_scale.get() * 100)
            self.slicer_scale_label.config(text=f"{scale_pct}%")

            metrics = self._get_slicer_grid_metrics()
            cols = metrics["cols"]
            rows = metrics["rows"]
            mx = metrics["mx"]
            my = metrics["my"]
            px = metrics["px"]
            py = metrics["py"]
            cell_w = max(1, int(metrics["cell_w_raw"]))
            cell_h = max(1, int(metrics["cell_h_raw"]))

            is_batch = hasattr(self, "slicer_batch_images") and bool(self.slicer_batch_images)
            is_manual = hasattr(self, "slicer_use_manual") and self.slicer_use_manual.get()

            if is_batch:
                active = getattr(self, "slicer_batch_active_idx", 0)
                self.slicer_slice_info.config(text=f"Batch Mode: {len(self.slicer_batch_images)} files loaded (active: {active + 1})")
            elif is_manual:
                self.slicer_slice_info.config(text=f"Manual Box Mode: {len(self.slicer_boxes)} slices defined")
            elif self.slicer_crop_square.get():
                square_box = self._get_slicer_square_crop_box(0.0, 0.0, metrics["cell_w_raw"], metrics["cell_h_raw"])
                crop_w = max(1, int(square_box[2] - square_box[0]))
                crop_h = max(1, int(square_box[3] - square_box[1]))
                trim_x, trim_y = self._get_slicer_square_trim_values()
                anchor_text = "content" if self.slicer_crop_center_content.get() else "cell"
                self.slicer_slice_info.config(text=f"Cell: {cell_w}×{cell_h} → {crop_w}×{crop_h} (crop box, {anchor_text}-centered, adjust {trim_x},{trim_y})")
            else:
                self.slicer_slice_info.config(text=f"Cell: {cell_w}×{cell_h} (Margin: {mx},{my} Pad: {px},{py})")

            # Rebuild names if count changed
            if is_batch:
                expected_count = len(self.slicer_batch_images)
            elif is_manual:
                expected_count = len(self.slicer_boxes)
            else:
                expected_count = (cols * rows)
                
            if len(self.slicer_names) != expected_count:
                self.slicer_rebuild_names()

        self.update_preview()

    def slicer_on_mouse_wheel(self, event):
        """Handle mouse wheel for slicer zoom."""
        if self.slicer_image is None:
            return
        
        # Zoom in/out
        if event.delta > 0:
            self.slicer_scale.set(min(5.0, self.slicer_scale.get() * 1.1))
        else:
            self.slicer_scale.set(max(0.1, self.slicer_scale.get() / 1.1))
        
        self.slicer_update_preview()

    def _get_slicer_output_size(self):
        output_size_str = self.slicer_output_size.get()
        if output_size_str == "Original":
            return None
        try:
            size_val = int(output_size_str.split("×")[0])
            return (size_val, size_val)
        except Exception:
            return None

    def _build_slicer_slices(self):
        if self.slicer_image is None:
            raise ValueError("No slicer image loaded")

        output_size = self._get_slicer_output_size()
        slices = []

        if hasattr(self, "slicer_batch_images") and self.slicer_batch_images:
            for i, item in enumerate(self.slicer_batch_images):
                name = item["name_var"].get().strip() if "name_var" in item else f"slice_{i}"
                img = item["image"].copy()
                if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                    thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                    bbox = self._alpha_bbox(img, alpha_threshold=thresh)
                    if bbox:
                        img = img.crop(bbox)
                if output_size:
                    img = img.resize(output_size, Image.Resampling.LANCZOS)
                slices.append((name, img.convert("RGBA")))
            return slices

        if hasattr(self, "slicer_use_manual") and self.slicer_use_manual.get():
            w_orig, h_orig = self.slicer_image.size
            for i, box_info in enumerate(self.slicer_boxes):
                name = box_info["name_var"].get().strip() if "name_var" in box_info else f"slice_{i}"
                left, top, right, bottom = box_info["box"]
                
                left = int(round(left))
                top = int(round(top))
                right = int(round(right))
                bottom = int(round(bottom))
                
                left = max(0, min(w_orig, left))
                top = max(0, min(h_orig, top))
                right = max(0, min(w_orig, right))
                bottom = max(0, min(h_orig, bottom))
                if right <= left or bottom <= top:
                    continue
                    
                slice_img = self.slicer_image.crop((left, top, right, bottom))
                if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                    thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                    bbox = self._alpha_bbox(slice_img, alpha_threshold=thresh)
                    if bbox:
                        slice_img = slice_img.crop(bbox)
                if output_size:
                    slice_img = slice_img.resize(output_size, Image.Resampling.LANCZOS)
                slices.append((name, slice_img.convert("RGBA")))
        else:
            metrics = self._get_slicer_grid_metrics()
            cols = metrics["cols"]
            rows = metrics["rows"]
            mx = metrics["mx"]
            my = metrics["my"]
            px = metrics["px"]
            py = metrics["py"]
            w_orig = metrics["w_orig"]
            h_orig = metrics["h_orig"]
            cell_w = metrics["cell_w_raw"]
            cell_h = metrics["cell_h_raw"]
            crop_square = self.slicer_crop_square.get()

            for row_idx in range(rows):
                for col_idx in range(cols):
                    name = self._get_slicer_slice_name(row_idx, col_idx)
                    left = mx + col_idx * (cell_w + px)
                    top = my + row_idx * (cell_h + py)
                    right = left + cell_w
                    bottom = top + cell_h

                    if crop_square:
                        left, top, right, bottom = self._get_slicer_square_crop_box(left, top, cell_w, cell_h)
                    else:
                        expand_w = self.slicer_expand_w.get()
                        expand_h = self.slicer_expand_h.get()
                        left -= expand_w
                        right += expand_w
                        top -= expand_h
                        bottom += expand_h

                    left = int(round(left))
                    top = int(round(top))
                    right = int(round(right))
                    bottom = int(round(bottom))

                    left = max(0, min(w_orig, left))
                    top = max(0, min(h_orig, top))
                    right = max(0, min(w_orig, right))
                    bottom = max(0, min(h_orig, bottom))
                    if right <= left or bottom <= top:
                        continue

                    slice_img = self.slicer_image.crop((left, top, right, bottom))
                    if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                        thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                        bbox = self._alpha_bbox(slice_img, alpha_threshold=thresh)
                        if bbox:
                            slice_img = slice_img.crop(bbox)

                    if output_size:
                        slice_img = slice_img.resize(output_size, Image.Resampling.LANCZOS)

                    slices.append((name, slice_img.convert("RGBA")))

        return slices

    def slicer_send_to_gif(self):
        if self.slicer_image is None:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        try:
            slices = self._build_slicer_slices()
        except Exception as e:
            messagebox.showerror("Slicer", f"Failed to slice image:\n{e}")
            return
        if not slices:
            messagebox.showwarning("Slicer", "No valid slices were generated.")
            return

        frame_names = [f"{self._sanitize_export_name(name, f'slice_{index + 1:03d}')}.png" for index, (name, _img) in enumerate(slices)]
        frame_images = [image for _name, image in slices]
        self._set_gif_frame_set(frame_names, frame_images, switch_to_tab=True)
        messagebox.showinfo("PNG→GIF", f"Loaded {len(frame_images)} sliced frames into the PNG→GIF tab.")

    def slicer_export(self):
        """Export all slices to a folder."""
        if self.slicer_image is None:
            messagebox.showwarning("No Image", "Please load an image first.")
            return

        # Ask for output folder
        folder = filedialog.askdirectory(title="Select Output Folder")
        if not folder:
            return
        export_format = self.slicer_export_format.get().upper()
        extension = _export_extension(export_format)

        try:
            slices = self._build_slicer_slices()
        except Exception as e:
            messagebox.showerror("Slicer", f"Failed to slice image:\n{e}")
            return

        # Check for conflicting file names
        existing_conflicts = []
        for index, (name, _) in enumerate(slices):
            fallback = f"slice_{index + 1:03d}"
            base_name = self._sanitize_export_name(name, fallback)
            output_path = os.path.join(folder, f"{base_name}{extension}")
            if os.path.exists(output_path):
                existing_conflicts.append(f"{base_name}{extension}")

        overwrite = False
        if existing_conflicts:
            msg = "The following file(s) already exist in the target folder:\n"
            if len(existing_conflicts) > 8:
                msg += "\n".join(existing_conflicts[:8]) + f"\n... and {len(existing_conflicts) - 8} more."
            else:
                msg += "\n".join(existing_conflicts)
            msg += "\n\nDo you want to overwrite the existing file(s)?"
            overwrite = messagebox.askyesno("Overwrite Existing Files?", msg)

        count = 0
        for index, (name, slice_img) in enumerate(slices):
            fallback = f"slice_{index + 1:03d}"
            base_name = self._sanitize_export_name(name, fallback)
            output_path = os.path.join(folder, f"{base_name}{extension}")
            if not overwrite:
                dedupe = 2
                while os.path.exists(output_path):
                    output_path = os.path.join(folder, f"{base_name}_{dedupe}{extension}")
                    dedupe += 1
            _save_transparent_image(slice_img, output_path, export_format)
            count += 1

        messagebox.showinfo("Export Complete", f"Exported {count} {export_format} slices to:\n{folder}")

    def _draw_slicer_preview(self):
        """Draw the slicer preview with grid overlay."""
        if self.slicer_image is None:
            return None

        w_orig, h_orig = self.slicer_image.size
        scale = self.slicer_scale.get()
        new_w = max(1, int(w_orig * scale))
        new_h = max(1, int(h_orig * scale))

        preview = self.slicer_image.resize((new_w, new_h), Image.Resampling.NEAREST if scale > 1 else Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(preview)
        
        
        if hasattr(self, "slicer_batch_images") and self.slicer_batch_images:
            left = 0
            top = 0
            right = w_orig
            bottom = h_orig
            if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                bbox = self._alpha_bbox(self.slicer_image, alpha_threshold=thresh)
                if bbox:
                    left, top, right, bottom = bbox
            sx0 = int(left * scale)
            sy0 = int(top * scale)
            sx1 = int(right * scale)
            sy1 = int(bottom * scale)
            draw.rectangle([sx0, sy0, sx1, sy1], outline=(0, 255, 0, 255), width=2)
            return preview

        if hasattr(self, "slicer_use_manual") and self.slicer_use_manual.get():
            for i, box_info in enumerate(self.slicer_boxes):
                left, top, right, bottom = box_info["box"]
                if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                    sub_img = self.slicer_image.crop((int(round(left)), int(round(top)), int(round(right)), int(round(bottom))))
                    thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                    bbox = self._alpha_bbox(sub_img, alpha_threshold=thresh)
                    if bbox:
                        left += bbox[0]
                        top += bbox[1]
                        right = left + (bbox[2] - bbox[0])
                        bottom = top + (bbox[3] - bbox[1])
                sx0 = int(left * scale)
                sy0 = int(top * scale)
                sx1 = int(right * scale)
                sy1 = int(bottom * scale)
                draw.rectangle([sx0, sy0, sx1, sy1], outline=(0, 255, 0, 255), width=2)
            return preview

        metrics = self._get_slicer_grid_metrics()
        cols = metrics["cols"]
        rows = metrics["rows"]
        mx = metrics["mx"]
        my = metrics["my"]
        px = metrics["px"]
        py = metrics["py"]
        cell_w_raw = metrics["cell_w_raw"]
        cell_h_raw = metrics["cell_h_raw"]
        
        for r in range(rows):
            for c in range(cols):
                x0 = mx + c * (cell_w_raw + px)
                y0 = my + r * (cell_h_raw + py)
                x1 = x0 + cell_w_raw
                y1 = y0 + cell_h_raw
                
                sx0, sy0 = int(x0 * scale), int(y0 * scale)
                sx1, sy1 = int(x1 * scale), int(y1 * scale)
                
                if not self.slicer_crop_square.get():
                    expand_w = self.slicer_expand_w.get()
                    expand_h = self.slicer_expand_h.get()
                    
                    if expand_w > 0 or expand_h > 0:
                        sx0, sy0 = int(x0 * scale), int(y0 * scale)
                        sx1, sy1 = int(x1 * scale), int(y1 * scale)
                        draw.rectangle([sx0, sy0, sx1, sy1], outline=(0, 255, 0, 80), width=1)
                        
                        ex0 = x0 - expand_w
                        ey0 = y0 - expand_h
                        ex1 = x1 + expand_w
                        ey1 = y1 + expand_h

                        if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                            w_orig, h_orig = self.slicer_image.size
                            crop_l = max(0, min(w_orig, int(round(ex0))))
                            crop_t = max(0, min(h_orig, int(round(ey0))))
                            crop_r = max(0, min(w_orig, int(round(ex1))))
                            crop_b = max(0, min(h_orig, int(round(ey1))))
                            if crop_r > crop_l and crop_b > crop_t:
                                sub_img = self.slicer_image.crop((crop_l, crop_t, crop_r, crop_b))
                                thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                                bbox = self._alpha_bbox(sub_img, alpha_threshold=thresh)
                                if bbox:
                                    ex0 = crop_l + bbox[0]
                                    ey0 = crop_t + bbox[1]
                                    ex1 = crop_l + bbox[2]
                                    ey1 = crop_t + bbox[3]

                        sex0, sey0 = int(ex0 * scale), int(ey0 * scale)
                        sex1, sey1 = int(ex1 * scale), int(ey1 * scale)
                        draw.rectangle([sex0, sey0, sex1, sey1], outline=(0, 255, 0, 255), width=2)
                    else:
                        ex0, ey0, ex1, ey1 = x0, y0, x1, y1
                        if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                            w_orig, h_orig = self.slicer_image.size
                            crop_l = max(0, min(w_orig, int(round(ex0))))
                            crop_t = max(0, min(h_orig, int(round(ey0))))
                            crop_r = max(0, min(w_orig, int(round(ex1))))
                            crop_b = max(0, min(h_orig, int(round(ey1))))
                            if crop_r > crop_l and crop_b > crop_t:
                                sub_img = self.slicer_image.crop((crop_l, crop_t, crop_r, crop_b))
                                thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                                bbox = self._alpha_bbox(sub_img, alpha_threshold=thresh)
                                if bbox:
                                    ex0 = crop_l + bbox[0]
                                    ey0 = crop_t + bbox[1]
                                    ex1 = crop_l + bbox[2]
                                    ey1 = crop_t + bbox[3]
                        sx0, sy0 = int(ex0 * scale), int(ey0 * scale)
                        sx1, sy1 = int(ex1 * scale), int(ey1 * scale)
                        draw.rectangle([sx0, sy0, sx1, sy1], outline=(0, 255, 0, 255), width=2)
                else:
                    sx0, sy0 = int(x0 * scale), int(y0 * scale)
                    sx1, sy1 = int(x1 * scale), int(y1 * scale)
                    draw.rectangle([sx0, sy0, sx1, sy1], outline=(0, 255, 0, 180), width=1)

        # Border around update area
        # draw.rectangle([0, 0, new_w - 1, new_h - 1], outline=(255, 0, 0, 255), width=2)
        
        # Draw margin boundary if margins are set
        if mx > 0 or my > 0:
             draw.rectangle([int(mx*scale), int(my*scale), new_w-1, new_h-1], outline=(255, 0, 0, 100), width=1)

        # If crop to square, show the crop region
        if self.slicer_crop_square.get():
            for r in range(rows):
                for c in range(cols):
                    # Base cell origin
                    cx_raw = mx + c * (cell_w_raw + px)
                    cy_raw = my + r * (cell_h_raw + py)

                    sq_x0, sq_y0, sq_x1, sq_y1 = self._get_slicer_square_crop_box(cx_raw, cy_raw, cell_w_raw, cell_h_raw)

                    if hasattr(self, "slicer_trim_transparency") and self.slicer_trim_transparency.get():
                        w_orig, h_orig = self.slicer_image.size
                        crop_l = max(0, min(w_orig, int(round(sq_x0))))
                        crop_t = max(0, min(h_orig, int(round(sq_y0))))
                        crop_r = max(0, min(w_orig, int(round(sq_x1))))
                        crop_b = max(0, min(h_orig, int(round(sq_y1))))
                        if crop_r > crop_l and crop_b > crop_t:
                            sub_img = self.slicer_image.crop((crop_l, crop_t, crop_r, crop_b))
                            thresh = self.slicer_trim_threshold.get() if hasattr(self, "slicer_trim_threshold") else 10
                            bbox = self._alpha_bbox(sub_img, alpha_threshold=thresh)
                            if bbox:
                                sq_x0 = crop_l + bbox[0]
                                sq_y0 = crop_t + bbox[1]
                                sq_x1 = crop_l + bbox[2]
                                sq_y1 = crop_t + bbox[3]

                    sx0 = int(sq_x0 * scale)
                    sy0 = int(sq_y0 * scale)
                    sx1 = int(sq_x1 * scale)
                    sy1 = int(sq_y1 * scale)

                    # Draw yellow inner square
                    draw.rectangle([sx0, sy0, sx1, sy1], outline=(255, 255, 0, 200), width=1)
        
        return preview

    def open_batch_bg_removal_window(self):
        if getattr(self, "edit_queue_running", False):
            messagebox.showinfo(
                "AI Queue Running",
                "Wait for the Edit queue to finish before opening another batch.",
            )
            return
        self._clear_edit_queue_state()
        if hasattr(self, "batch_window") and self.batch_window is not None and self.batch_window.winfo_exists():
            self.batch_window.deiconify()
            self.batch_window.lift()
            self.batch_window.focus_force()
            return

        self.batch_window = tk.Toplevel(self.root)
        _apply_window_identity(self.batch_window, f"{APP_NAME} Batch AI Background Removal")
        _center_window(self.batch_window, 820, 620)
        self.batch_window.minsize(780, 560)
        self.batch_window.configure(bg=self.PS1_GREY)
        self.batch_window.protocol("WM_DELETE_WINDOW", self.close_batch_window)

        self.batch_files_list = []
        self.batch_running = False

        # Build local variables
        self.batch_model_var = tk.StringVar(value=self.ai_model_var.get())
        self.batch_pure_ai_var = tk.BooleanVar(value=self.force_ai_only_var.get())
        self.batch_tol_var = tk.DoubleVar(value=self.tol_var.get())
        self.batch_soft_var = tk.DoubleVar(value=self.soft_var.get())
        self.batch_suffix_var = tk.StringVar(value="_nobg")
        self.batch_output_format_var = tk.StringVar(value="PNG")
        self.batch_out_dir_var = tk.StringVar(value="")

        # Master Panel
        glass_panel = GlassPanel(self.batch_window, text="Batch Background Removal", bullet_color=THEME_COLOR_SUCCESS)
        glass_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Content frame containing left and right columns
        content_frame = ttk.Frame(glass_panel)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(5, 12))

        # Left Column: Configuration Settings
        left_col = ttk.Frame(content_frame, width=280)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 15))
        left_col.pack_propagate(False)

        # Right Column: Files & Logs
        right_col = ttk.Frame(content_frame)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Populate Left Column (Configuration settings)
        ttk.Label(left_col, text="SELECT AI MODEL:").pack(anchor=tk.W, pady=(5, 2))
        self.batch_model_combo = ttk.Combobox(
            left_col,
            textvariable=self.batch_model_var,
            values=[
                FUSION_AI_MODEL,
                "birefnet-massive",
                "isnet-general-use",
            ],
            state="readonly",
        )
        self.batch_model_combo.pack(fill=tk.X, pady=(0, 15))

        self.batch_pure_ai_check = ttk.Checkbutton(left_col, text="Pure AI Mode (Bypass Keying)", variable=self.batch_pure_ai_var)
        self.batch_pure_ai_check.pack(anchor=tk.W, pady=(0, 15))

        batch_model_state = {
            "previous": self.batch_model_var.get(),
            "isnet_pref": self.batch_pure_ai_var.get(),
        }

        def _sync_batch_force_ai_checkbox(*_):
            selected = self.batch_model_var.get()
            previous = batch_model_state["previous"]
            policy = _ai_refinement_policy(selected)
            previous_policy = _ai_refinement_policy(previous)

            if previous_policy == "user" and policy != "user":
                batch_model_state["isnet_pref"] = self.batch_pure_ai_var.get()

            if policy == "pure":
                self.batch_pure_ai_var.set(True)
                self.batch_pure_ai_check.state(["disabled", "selected"])
            elif policy == "adaptive":
                self.batch_pure_ai_var.set(False)
                self.batch_pure_ai_check.state(["disabled", "!selected"])
            else:
                self.batch_pure_ai_check.state(["!disabled"])
                if previous_policy != "user":
                    self.batch_pure_ai_var.set(batch_model_state["isnet_pref"])
                else:
                    batch_model_state["isnet_pref"] = self.batch_pure_ai_var.get()

            batch_model_state["previous"] = selected

        self._sync_batch_force_ai_checkbox = _sync_batch_force_ai_checkbox
        self.batch_model_var.trace_add("write", _sync_batch_force_ai_checkbox)
        _sync_batch_force_ai_checkbox()

        # Tolerance
        tol_label_var = tk.StringVar(value=f"Tolerance: {self.batch_tol_var.get():.1f}")
        ttk.Label(left_col, textvariable=tol_label_var).pack(anchor=tk.W)
        def _update_tol_lbl(*_):
            tol_label_var.set(f"Tolerance: {self.batch_tol_var.get():.1f}")
        self.batch_tol_var.trace_add("write", _update_tol_lbl)
        self.batch_tol_scale = ttk.Scale(left_col, from_=0, to=100, variable=self.batch_tol_var)
        self.batch_tol_scale.pack(fill=tk.X, pady=(0, 15))

        # Softness
        soft_label_var = tk.StringVar(value=f"Softness: {self.batch_soft_var.get():.1f}")
        ttk.Label(left_col, textvariable=soft_label_var).pack(anchor=tk.W)
        def _update_soft_lbl(*_):
            soft_label_var.set(f"Softness: {self.batch_soft_var.get():.1f}")
        self.batch_soft_var.trace_add("write", _update_soft_lbl)
        self.batch_soft_scale = ttk.Scale(left_col, from_=0, to=100, variable=self.batch_soft_var)
        self.batch_soft_scale.pack(fill=tk.X, pady=(0, 15))

        # Filename Suffix
        ttk.Label(left_col, text="FILENAME SUFFIX:").pack(anchor=tk.W, pady=(0, 2))
        self.batch_suffix_entry = ttk.Entry(left_col, textvariable=self.batch_suffix_var)
        self.batch_suffix_entry.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(left_col, text="OUTPUT FORMAT:").pack(anchor=tk.W, pady=(0, 2))
        self.batch_output_format_combo = ttk.Combobox(
            left_col,
            textvariable=self.batch_output_format_var,
            values=TRANSPARENT_EXPORT_FORMATS,
            state="readonly",
        )
        self.batch_output_format_combo.pack(fill=tk.X, pady=(0, 15))

        # Output Directory
        ttk.Label(left_col, text="OUTPUT DIRECTORY:").pack(anchor=tk.W, pady=(0, 2))
        out_dir_frame = ttk.Frame(left_col)
        out_dir_frame.pack(fill=tk.X, pady=(0, 15))
        self.batch_out_dir_entry = ttk.Entry(out_dir_frame, textvariable=self.batch_out_dir_var)
        self.batch_out_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        def _browse_out_dir():
            d = filedialog.askdirectory(title="Select Output Directory")
            if d:
                self.batch_out_dir_var.set(d)
        self.batch_browse_btn = ttk.Button(out_dir_frame, text="Browse...", width=8, command=_browse_out_dir)
        self.batch_browse_btn.pack(side=tk.RIGHT, padx=(4, 0))

        # Populate Right Column (Files list, buttons, progress, logs)
        ttk.Label(right_col, text="INPUT IMAGES (DRAG & DROP SUPPORTED):").pack(anchor=tk.W, pady=(5, 2))
        
        list_frame = ttk.Frame(right_col)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.batch_listbox = tk.Listbox(list_frame, height=5, selectmode=tk.EXTENDED, bg=self.BG_INPUT, fg=self.COLOR_TEXT, highlightthickness=0, bd=0)
        self.batch_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.batch_listbox.yview)
        self.batch_listbox.configure(yscrollcommand=list_scroll.set)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # List Actions buttons
        list_btn_frame = ttk.Frame(right_col)
        list_btn_frame.pack(fill=tk.X, pady=(0, 10))

        def _add_files():
            paths = filedialog.askopenfilenames(
                title="Select Images for Batch Background Removal",
                filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All Files", "*.*")]
            )
            if paths:
                for p in paths:
                    if p not in self.batch_files_list:
                        self.batch_files_list.append(p)
                        self.batch_listbox.insert(tk.END, p)
                _update_status()

        def _remove_selected():
            selected_indices = list(self.batch_listbox.curselection())
            for idx in sorted(selected_indices, reverse=True):
                self.batch_listbox.delete(idx)
                self.batch_files_list.pop(idx)
            _update_status()

        def _clear_all():
            self.batch_listbox.delete(0, tk.END)
            self.batch_files_list.clear()
            _update_status()

        self.batch_add_btn = ttk.Button(list_btn_frame, text="Add Images...", command=_add_files)
        self.batch_add_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.batch_remove_btn = ttk.Button(list_btn_frame, text="Remove Selected", command=_remove_selected)
        self.batch_remove_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.batch_clear_btn = ttk.Button(list_btn_frame, text="Clear All", command=_clear_all)
        self.batch_clear_btn.pack(side=tk.LEFT)

        # Enable Drag and Drop on listbox
        try:
            self.batch_listbox.drop_target_register(DND_FILES)
            def _on_listbox_drop(event):
                data = event.data
                if data:
                    try:
                        files = list(self.root.tk.splitlist(data))
                    except Exception:
                        files = data.strip("{}").split()
                    
                    for path in files:
                        if not isinstance(path, str):
                            continue
                        if os.path.exists(path) and path not in self.batch_files_list:
                            self.batch_files_list.append(path)
                            self.batch_listbox.insert(tk.END, path)
                    _update_status()
            self.batch_listbox.dnd_bind('<<Drop>>', _on_listbox_drop)
        except Exception as dnd_err:
            print(f"Failed to bind DnD to batch listbox: {dnd_err}")

        # Progress Log
        ttk.Label(right_col, text="PROGRESS LOG:").pack(anchor=tk.W, pady=(5, 2))
        log_frame = ttk.Frame(right_col)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.batch_log_text = tk.Text(log_frame, height=5, bg="#121218", fg="#E0E0FF", insertbackground="#E0E0FF", font=("Consolas", 9), wrap=tk.WORD, bd=0, highlightthickness=0)
        self.batch_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.batch_log_text.yview)
        self.batch_log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.batch_log_text.config(state=tk.DISABLED)

        # Progressbar
        self.batch_progress = ttk.Progressbar(right_col, mode="determinate")
        self.batch_progress.pack(fill=tk.X, pady=(0, 5))

        # Status Label
        self.batch_status_lbl = ttk.Label(right_col, text="0 images loaded. Ready.")
        self.batch_status_lbl.pack(anchor=tk.W, pady=(0, 5))

        def _update_status():
            count = len(self.batch_files_list)
            self.batch_status_lbl.config(text=f"{count} image(s) loaded. Ready.")

        # Bottom actions
        bottom_frame = ttk.Frame(glass_panel)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))

        self.batch_start_btn = CustomButton(bottom_frame, text="Start Batch", style="Success.TButton", command=self.start_batch_bg_removal)
        self.batch_start_btn.pack(side=tk.RIGHT, padx=(5, 0))

        self.batch_cancel_btn = CustomButton(bottom_frame, text="Close", style="ToolbarGrey.TButton", command=self.close_batch_window)
        self.batch_cancel_btn.pack(side=tk.RIGHT)

    def close_batch_window(self):
        self.batch_running = False
        self.batch_preview_active = False
        self.batch_preview_image = None
        self.batch_preview_index = None
        self.batch_preview_status = ""
        self.batch_item_statuses = []
        self.batch_thumbnail_cache = {}
        self._hide_batch_filmstrip()
        if hasattr(self, "batch_window") and self.batch_window is not None:
            try:
                self.batch_window.destroy()
            except Exception:
                pass
        self.batch_window = None
        self.on_left_tab_changed()
        self.update_preview()

    def start_batch_bg_removal(self):
        if not self.batch_files_list:
            messagebox.showwarning("No Images", "Please add at least one image to process.")
            return
            
        if self.batch_running:
            self.stop_batch_bg_removal()
            return

        selected_model = self.batch_model_var.get()
        if not _model_is_cached(selected_model):
            info = AI_MODEL_INFO[selected_model]
            size_mb = _missing_ai_model_bytes(selected_model) / (1024 * 1024)
            cache_dir = _model_cache_path(
                _ai_component_models(selected_model)[0]
            ).parent
            approved = messagebox.askyesno(
                "Download AI Model?",
                f"{info['label']} needs to download {size_mb:.0f} MB of model data before this batch can start.\n\n"
                f"It will be stored in:\n{cache_dir}\n\n"
                "Download the model now?",
                parent=self.batch_window,
            )
            if not approved:
                return
            
        self.batch_running = True
        self.batch_start_btn.config(text="Stop Batch", fg=self.COLOR_DANGER)
        self.batch_cancel_btn.config(state=tk.DISABLED)
        
        self._set_batch_inputs_state(tk.DISABLED)
        
        self.batch_log_text.config(state=tk.NORMAL)
        self.batch_log_text.delete(1.0, tk.END)
        self.batch_log_text.config(state=tk.DISABLED)
        
        self.batch_progress["value"] = 0
        self.batch_progress["maximum"] = len(self.batch_files_list)
        self.batch_item_statuses = ["queued"] * len(self.batch_files_list)
        self.batch_thumbnail_cache = {}
        self.batch_preview_active = True
        self.batch_preview_image = None
        self.batch_preview_index = 0
        self.batch_preview_status = f"Batch ready • 1 of {len(self.batch_files_list)}"
        self.batch_filmstrip_status_var.set(self.batch_preview_status)
        self._show_batch_filmstrip()
        self.update_preview()
        
        self._start_worker(self._run_batch_bg_removal_thread, "ai-batch")

    def stop_batch_bg_removal(self):
        if self.batch_running:
            self.batch_running = False
            self.add_batch_log("Cancellation requested... Stopping after the current image completes.")

    def _set_batch_inputs_state(self, state):
        for w in [self.batch_model_combo, self.batch_pure_ai_check, self.batch_tol_scale, self.batch_soft_scale, self.batch_suffix_entry, self.batch_output_format_combo, self.batch_out_dir_entry, self.batch_browse_btn, self.batch_add_btn, self.batch_remove_btn, self.batch_clear_btn]:
            try:
                w.config(state=state)
            except Exception:
                pass
        if state != tk.DISABLED and hasattr(self, "_sync_batch_force_ai_checkbox"):
            self._sync_batch_force_ai_checkbox()

    def _run_batch_bg_removal_thread(self):
        if self._is_shutting_down():
            return
        import time
        import os
        import numpy as np
        from PIL import Image
        import cv2
        from rembg import remove, new_session
        import onnxruntime as ort
        
        selected_model = self.batch_model_var.get()
        pure_ai = self.batch_pure_ai_var.get()
        tol = self.batch_tol_var.get()
        soft = self.batch_soft_var.get()
        suffix = self.batch_suffix_var.get()
        output_format = self.batch_output_format_var.get().upper()
        output_extension = _export_extension(output_format)
        output_dir = self.batch_out_dir_var.get()
        
        self.add_batch_log(f"--- BATCH BACKGROUND REMOVAL STARTED ---")
        self.add_batch_log(f"Model: {selected_model}")
        self.add_batch_log(f"Pure AI Mode: {pure_ai}")
        self.add_batch_log(f"Tolerance: {tol:.1f} | Softness: {soft:.1f}")
        self.add_batch_log(f"Output Format: {output_format}")
        if output_dir:
            self.add_batch_log(f"Output Directory: {output_dir}")
        else:
            self.add_batch_log(f"Output Directory: [Same as original files]")
        self.add_batch_log(f"Processing {len(self.batch_files_list)} images...")

        if not _model_is_cached(selected_model):
            try:
                self.add_batch_log(f"Downloading {AI_MODEL_INFO[selected_model]['label']}...")
                _download_ai_model(
                    selected_model,
                    status_callback=self.add_batch_log,
                    progress_callback=lambda percent: self._queue_ui(
                        lambda value=percent: self.batch_progress.config(value=value, maximum=100)
                    ),
                )
                if self._is_shutting_down():
                    return
                self._queue_ui(
                    lambda: self.batch_progress.config(
                        value=0, maximum=max(1, len(self.batch_files_list))
                    ),
                )
            except Exception as error:
                if self._is_shutting_down():
                    return
                self.add_batch_log(f"MODEL DOWNLOAD ERROR: {error}")
                self._queue_ui(
                    self._on_batch_complete,
                    False,
                    f"Model download failed: {error}",
                )
                return
        
        success_count = 0
        total_files = len(self.batch_files_list)
        
        for idx, path in enumerate(self.batch_files_list):
            if not self.batch_running or self._is_shutting_down():
                self.add_batch_log("\nProcess stopped by user.")
                break
                
            name = os.path.basename(path)
            self.add_batch_log(f"\n[{idx+1}/{total_files}] Processing: {name}...")
            
            # Select item in listbox
            self._queue_ui(lambda i=idx: self._select_listbox_item(i))
            
            img_rgba = None
            try:
                t_start = time.time()
                
                # Load image
                img_rgba = Image.open(path).convert("RGBA")
                w, h = img_rgba.size
                self._queue_ui(
                    self._set_batch_preview_ui,
                    idx,
                    img_rgba.copy(),
                    "processing",
                    f"Removing background • {idx + 1} of {total_files} • {name}",
                )
                
                arr = np.array(img_rgba)
                rgb = arr[:, :, :3].astype(np.float32)
                
                background_profile = _classify_uniform_background(rgb)
                B = background_profile["background"]
                is_chroma_screen = background_profile["is_chroma_screen"]
                
                # Run AI Model
                self.add_batch_log("  Running segmentation model(s)...")
                raw_mask, _inference_duration = self._run_ai_selection_mask(
                    img_rgba.copy(),
                    selected_model,
                    remove,
                    new_session=new_session,
                    ort=ort,
                    status_callback=self.add_batch_log,
                )
                if self._is_shutting_down():
                    return
                
                # Resize if necessary
                if raw_mask.size != img_rgba.size:
                    raw_mask = raw_mask.resize(img_rgba.size, Image.Resampling.BILINEAR)
                
                raw_mask_arr = np.asarray(raw_mask, dtype=np.float32) / 255.0
                
                # Refinement / details restoration
                self.add_batch_log("  Applying details refinement & matting...")
                d = np.sqrt(np.sum((rgb - B) ** 2, axis=-1))
                tol_val = tol * 2.55
                M_missed = (d > tol_val) & (raw_mask_arr < 0.1)
                bg_candidate_mask = M_missed.astype(np.uint8) * 255
                
                soft_val = max(soft, 10.0) * 2.55
                lower_bound = tol_val - soft_val / 2.0
                upper_bound = tol_val + soft_val / 2.0
                chroma_alpha = np.clip((d - lower_bound) / np.maximum(upper_bound - lower_bound, 1.0), 0.0, 1.0)
                
                num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bg_candidate_mask, connectivity=8)
                A_composite = raw_mask_arr.copy()
                has_changes = False
                refinement_mask = np.zeros_like(raw_mask_arr, dtype=np.uint8)
                refinement_mask_swirls = np.zeros_like(raw_mask_arr, dtype=np.uint8)
                
                if is_chroma_screen:
                    for label in range(1, num_labels):
                        area = stats[label, cv2.CC_STAT_AREA]
                        if area >= 2:
                            mask_indices = (labels == label)
                            refinement_mask[mask_indices] = 255
                            if area >= 100:
                                refinement_mask_swirls[mask_indices] = 255
                            has_changes = True
                # Non-chroma modes do not launch automatic crop inference.
                # Lightweight dark-background recovery is handled later by the
                # same deterministic post-processing used in the editor.
                            
                if has_changes:
                    dil_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                    refinement_mask_dilated = cv2.dilate(refinement_mask, dil_kernel)
                    refinement_mask_swirls_dilated = cv2.dilate(refinement_mask_swirls, dil_kernel)
                    
                    refinement_mask_pil = Image.fromarray(refinement_mask_dilated, "L")
                    refinement_mask_swirls_pil = Image.fromarray(refinement_mask_swirls_dilated, "L")
                    composite_mask_pil = Image.fromarray((A_composite * 255.0).astype(np.uint8), "L")
                else:
                    refinement_mask_pil = None
                    refinement_mask_swirls_pil = None
                    composite_mask_pil = raw_mask
                    
                # Setup action dict for _apply_refined_ai_remove
                action = {
                    "type": "ai_remove",
                    "model_name": selected_model,
                    "ai_mask": raw_mask,
                    "composite_mask": composite_mask_pil,
                    "refinement_mask": refinement_mask_pil,
                    "refinement_mask_swirls": refinement_mask_swirls_pil,
                    "tol": tol,
                    "soft": soft,
                    "contiguous": False,
                    "clean_holes": False,
                    "force_ai_only": pure_ai,
                    "is_batch": True
                }
                
                final_img = self._apply_refined_ai_remove(img_rgba, action)
                
                # Save output
                dir_name = output_dir if output_dir else os.path.dirname(path)
                os.makedirs(dir_name, exist_ok=True)
                base_name = os.path.splitext(name)[0]
                out_path = os.path.join(dir_name, f"{base_name}{suffix}{output_extension}")
                
                _save_transparent_image(final_img, out_path, output_format)
                success_count += 1
                t_end = time.time()
                self.add_batch_log(f"  Success -> Saved to: {os.path.basename(out_path)} ({t_end - t_start:.2f}s)")
                self._queue_ui(
                    self._set_batch_preview_ui,
                    idx,
                    final_img.copy(),
                    "done",
                    f"Complete • {idx + 1} of {total_files} • {name}",
                )
                
            except Exception as item_err:
                if self._is_shutting_down():
                    return
                self.add_batch_log(f"  ERROR: Failed to process {name}: {item_err}")
                failed_preview = locals().get("img_rgba")
                self._queue_ui(
                    self._set_batch_preview_ui,
                    idx,
                    failed_preview.copy() if failed_preview is not None else None,
                    "error",
                    f"Failed • {idx + 1} of {total_files} • {name}",
                )
                
            # Update progress
            self._queue_ui(lambda val=idx+1: self.batch_progress.config(value=val))
            
        self._queue_ui(
            self._on_batch_complete,
            True,
            f"Processed {success_count} / {total_files} successfully.",
        )

    def _select_listbox_item(self, idx):
        if hasattr(self, "batch_listbox") and self.batch_listbox.winfo_exists():
            self.batch_listbox.select_clear(0, tk.END)
            self.batch_listbox.select_set(idx)
            self.batch_listbox.see(idx)

    def _on_batch_complete(self, clean, message):
        self.batch_running = False
        self.batch_start_btn.config(text="Start Batch", fg="#E2F1FF")
        self.batch_cancel_btn.config(state=tk.NORMAL)
        
        self._set_batch_inputs_state(tk.NORMAL)
        self.batch_status_lbl.config(text=f"Batch complete. {message}")
        self.batch_filmstrip_status_var.set(f"Batch complete • {message}")
        self._render_batch_filmstrip()
        self.add_batch_log(f"\n--- BATCH COMPLETE: {message} ---")
        
        if clean:
            messagebox.showinfo("Batch Background Removal Complete", f"Batch processing completed!\n\n{message}")
        else:
            messagebox.showerror("Batch Background Removal Error", f"Batch processing encountered errors:\n\n{message}")

    def add_batch_log(self, message):
        if (
            not self._is_shutting_down()
            and hasattr(self, "batch_log_text")
            and self.batch_log_text.winfo_exists()
        ):
            self._queue_ui(self._add_batch_log_ui, message)

    def _add_batch_log_ui(self, message):
        self.batch_log_text.config(state=tk.NORMAL)
        self.batch_log_text.insert(tk.END, message + "\n")
        self.batch_log_text.see(tk.END)
        self.batch_log_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = None
    app = None
    exit_code = 0
    try:
        # Must be set before Tk creates its first top-level window. Otherwise
        # Windows groups the app under pythonw.exe and shows Python's taskbar
        # icon even though the window itself has Transparentor's ICO.
        _set_windows_app_identity()
        root = TkinterDnD.Tk()
        root.report_callback_exception = lambda exc_type, exc_value, exc_tb: _handle_fatal_exception(
            exc_type,
            exc_value,
            exc_tb,
            "Unexpected UI error",
        )
        app = TransparentorApp(root)
        root.mainloop()
    except Exception:
        exit_code = 1
        _handle_fatal_exception(*sys.exc_info(), context="Unexpected startup error")
    finally:
        if app is not None:
            try:
                app._cleanup_before_exit()
            except Exception:
                pass
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
        if app is not None:
            # AI inference and model downloads are in-process threads. A hard
            # process exit after the UI/save path completes guarantees that no
            # native ONNX work survives a Transparentor close.
            os._exit(exit_code)
