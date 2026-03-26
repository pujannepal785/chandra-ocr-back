import base64
import html as html_mod
import json
import mimetypes
import os
from io import BytesIO
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont

API_BASE = os.getenv("OCR_API_BASE", "http://localhost:8080")
IMAGES_DIR = Path("images")
RESULTS_DIR = Path("results")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"}
UPLOAD_TYPES = sorted(ext.lstrip(".") for ext in IMAGE_EXTENSIONS)

LABEL_COLORS = {
    "Text": "#2ecc71",
    "Section-Header": "#e74c3c",
    "Table": "#3498db",
    "Image": "#9b59b6",
    "Figure": "#9b59b6",
    "List-Group": "#f39c12",
    "Code-Block": "#1abc9c",
    "Equation-Block": "#e67e22",
    "Caption": "#95a5a6",
    "Footnote": "#7f8c8d",
    "Page-Header": "#bdc3c7",
    "Page-Footer": "#bdc3c7",
    "Complex-Block": "#d35400",
    "Form": "#2980b9",
    "Table-Of-Contents": "#8e44ad",
    "Chemical-Block": "#16a085",
    "Diagram": "#c0392b",
    "Bibliography": "#27ae60",
    "Blank-Page": "#ecf0f1",
}
DEFAULT_COLOR = "#e74c3c"

# =============================================
# CUSTOM CSS — Warm & Earthy Theme
# =============================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* === Root & Global === */
.stApp {
    font-family: 'Inter', sans-serif;
}

section[data-testid="stSidebar"] {
    background: #2C2417;
    border-right: 1px solid #3D3228;
}
section[data-testid="stSidebar"] * {
    color: #F5E6D3 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: #3D3228;
    color: #F5E6D3 !important;
    border: 1px solid #5A4A3A;
    border-radius: 8px;
    transition: all 0.2s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #5A4A3A;
    border-color: #E67E22;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {
    background: #E67E22 !important;
    color: #fff !important;
    border: none;
    font-weight: 600;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover,
section[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"]:hover {
    background: #D35400 !important;
}
section[data-testid="stSidebar"] .stDivider {
    border-color: #3D3228 !important;
}

/* === Main Content === */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 1rem;
    max-width: 1200px;
}

/* === Title === */
h1 {
    color: #2C2417 !important;
    font-weight: 700 !important;
    font-size: 1.8rem !important;
    letter-spacing: -0.02em;
    padding-bottom: 0.5rem;
    border-bottom: 3px solid #E67E22;
    display: inline-block;
}

/* === Metric Cards === */
[data-testid="stMetric"] {
    background: #FFF9F0;
    border: 1px solid #F0E0C8;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(44, 36, 23, 0.06);
    border-top: none;
}
[data-testid="stMetricLabel"] {
    color: #8B7355 !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="stMetricValue"] {
    color: #2C2417 !important;
    font-weight: 700 !important;
    font-size: 1.8rem !important;
}

/* === Tabs === */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 2px solid #F0E0C8;
}
.stTabs [data-baseweb="tab"] {
    padding: 0.6rem 1.2rem;
    color: #8B7355;
    font-weight: 500;
    border-radius: 8px 8px 0 0;
    border: none;
    background: transparent;
}
.stTabs [aria-selected="true"] {
    color: #E67E22 !important;
    background: #FFF9F0;
    border-bottom: 3px solid #E67E22;
    font-weight: 600;
}

/* === Buttons (main area) === */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s ease;
    border: 1px solid #D4C4A8;
}
.stButton > button:hover {
    border-color: #E67E22;
    color: #E67E22;
}
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
    background: #E67E22 !important;
    color: #fff !important;
    border: none !important;
    font-weight: 600;
}
.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {
    background: #D35400 !important;
}

/* === Chunk Cards === */
.chunk-card {
    background: #FFF9F0;
    border-left: 4px solid #E67E22;
    padding: 0.7rem 1rem;
    margin-bottom: 0.6rem;
    border-radius: 0 8px 8px 0;
    font-size: 0.85rem;
    box-shadow: 0 1px 2px rgba(44, 36, 23, 0.04);
    transition: box-shadow 0.2s ease;
}
.chunk-card:hover {
    box-shadow: 0 2px 8px rgba(44, 36, 23, 0.1);
}
.chunk-label {
    font-weight: 700;
    font-size: 0.7rem;
    text-transform: uppercase;
    margin-bottom: 0.2rem;
    letter-spacing: 0.03em;
}
.chunk-bbox {
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 0.7rem;
    color: #8B7355;
}

/* === Status Card === */
.status-card {
    border: 1px solid #F0E0C8;
    border-radius: 12px;
    padding: 1.2rem;
    background: #FFF9F0;
    color: #5A4A3A;
    line-height: 1.6;
}

/* === Image Container === */
.image-viewer {
    border: 1px solid #F0E0C8;
    border-radius: 12px;
    padding: 0.75rem;
    background: #FEFCF8;
    display: inline-block;
}

/* === Nav Buttons for Extracted Results === */
.nav-btn-container .stButton > button {
    background: #FFF9F0;
    border: 1px solid #D4C4A8;
    color: #5A4A3A;
    font-weight: 600;
    border-radius: 8px;
}
.nav-btn-container .stButton > button:hover {
    background: #E67E22;
    color: #fff;
    border-color: #E67E22;
}

/* === Result Counter Badge === */
.result-counter {
    background: #E67E22;
    color: #fff;
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    display: inline-block;
    margin: 0.5rem 0;
}

/* === Gallery Item in Sidebar === */
.gallery-item {
    background: #3D3228;
    border-radius: 8px;
    padding: 0.5rem;
    margin-bottom: 0.4rem;
    border: 1px solid #5A4A3A;
    transition: border-color 0.2s;
}
.gallery-item:hover {
    border-color: #E67E22;
}
.gallery-item-active {
    border-color: #E67E22 !important;
    background: #4A3A2A;
}
.gallery-status {
    font-size: 0.65rem;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.gallery-status-done {
    background: #27ae60;
    color: #fff;
}
.gallery-status-pending {
    background: #5A4A3A;
    color: #A89070;
}

/* === Selectbox / Inputs === */
.stSelectbox > div > div {
    border-radius: 8px;
}

/* === Slider === */
.stSlider [data-testid="stTickBar"] { display: none; }

/* === Progress === */
.stProgress > div > div {
    background-color: #E67E22 !important;
}

/* === Expander === */
.streamlit-expanderHeader {
    font-weight: 600;
    color: #2C2417;
}

/* === Scrollable content === */
.extracted-content {
    max-height: 600px;
    overflow-y: auto;
    padding-right: 0.5rem;
}

/* === Legend pills === */
.label-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 600;
    margin: 2px;
    color: #fff;
}
</style>
"""


def ensure_directories() -> None:
    IMAGES_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)


def list_images() -> list[Path]:
    if not IMAGES_DIR.exists():
        return []
    return sorted(p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)


def get_result_path(image_path: Path) -> Path:
    return RESULTS_DIR / f"{image_path.stem}.json"


def list_result_files() -> list[Path]:
    if not RESULTS_DIR.exists():
        return []
    return sorted(RESULTS_DIR.glob("*.json"))


def get_unique_image_path(filename: str) -> Path:
    raw_name = Path(filename).name or "image"
    suffix = Path(raw_name).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        suffix = ".jpg"

    stem = Path(raw_name).stem.strip() or "image"
    candidate = IMAGES_DIR / f"{stem}{suffix}"
    counter = 1

    while candidate.exists():
        candidate = IMAGES_DIR / f"{stem}_{counter}{suffix}"
        counter += 1

    return candidate


def save_uploaded_files(uploaded_files) -> tuple[list[str], list[str]]:
    saved_names: list[str] = []
    skipped_messages: list[str] = []

    ensure_directories()
    for uploaded_file in uploaded_files:
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            skipped_messages.append(f"{uploaded_file.name}: unsupported file type")
            continue

        content = uploaded_file.getvalue()
        if not content:
            skipped_messages.append(f"{uploaded_file.name}: file was empty")
            continue

        destination = get_unique_image_path(uploaded_file.name)
        destination.write_bytes(content)
        saved_names.append(destination.name)

    return saved_names, skipped_messages


def make_thumbnail(image: Image.Image, size: int = 80) -> Image.Image:
    thumb = image.copy()
    thumb.thumbnail((size, size))
    return thumb


def draw_bboxes(image: Image.Image, chunks: list[dict]) -> Image.Image:
    overlay = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except (OSError, IOError):
        font = ImageFont.load_default()

    for chunk in chunks:
        bbox = chunk.get("bbox")
        label = chunk.get("label", "Unknown")
        if not bbox:
            continue
        x0, y0, x1, y1 = bbox
        color = LABEL_COLORS.get(label, DEFAULT_COLOR)
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)

        fill_layer = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
        ImageDraw.Draw(fill_layer).rectangle([x0, y0, x1, y1], fill=(r, g, b, 35))
        overlay = Image.alpha_composite(overlay, fill_layer)
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([x0, y0, x1, y1], outline=color, width=2)

        tb = font.getbbox(label)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        tag_x, tag_y = x0, max(y0 - th - 6, 0)
        draw.rectangle([tag_x, tag_y, tag_x + tw + 8, tag_y + th + 4], fill=color)
        draw.text((tag_x + 4, tag_y + 1), label, fill="white", font=font)
    return overlay.convert("RGB")


def image_to_base64(image: Image.Image) -> str:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def render_interactive_image(image: Image.Image, chunks: list[dict], display_width: int) -> None:
    """Render image with interactive bounding box overlays. Hover shows text content."""
    orig_w, orig_h = image.size
    scale = display_width / orig_w
    display_height = int(orig_h * scale)
    img_b64 = image_to_base64(image)

    # Build bbox overlay divs
    bbox_divs = []
    for i, chunk in enumerate(chunks):
        bbox = chunk.get("bbox")
        label = chunk.get("label", "Unknown")
        content = chunk.get("content", "")
        if not bbox:
            continue
        x0, y0, x1, y1 = bbox
        sx0, sy0 = x0 * scale, y0 * scale
        sx1, sy1 = x1 * scale, y1 * scale
        w, h = sx1 - sx0, sy1 - sy0
        color = LABEL_COLORS.get(label, DEFAULT_COLOR)

        # Escape content for HTML
        safe_content = html_mod.escape(content[:200])
        safe_label = html_mod.escape(label)

        bbox_divs.append(f"""
        <div class="bbox-overlay" id="bbox-{i}"
             style="left:{sx0:.1f}px;top:{sy0:.1f}px;width:{w:.1f}px;height:{h:.1f}px;
                    border-color:{color};"
             data-color="{color}">
            <div class="bbox-tag" style="background:{color};">{safe_label}</div>
            <div class="bbox-tooltip">
                <div class="tooltip-label" style="color:{color};">{safe_label}</div>
                <div class="tooltip-content">{safe_content}</div>
            </div>
        </div>
        """)

    bbox_html = "\n".join(bbox_divs)

    html_content = f"""
    <div id="image-container" style="position:relative;width:{display_width}px;height:{display_height}px;
         border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(44,36,23,0.1);
         border:1px solid #F0E0C8;">
        <img src="data:image/png;base64,{img_b64}"
             style="width:{display_width}px;height:{display_height}px;display:block;" />
        {bbox_html}
    </div>
    <style>
        #image-container {{ font-family: 'Inter', -apple-system, sans-serif; }}
        .bbox-overlay {{
            position: absolute;
            border: 2px solid;
            background: rgba(0,0,0,0);
            cursor: pointer;
            transition: background 0.15s ease, box-shadow 0.15s ease;
            z-index: 2;
        }}
        .bbox-overlay:hover {{
            background: rgba(230, 126, 34, 0.15);
            box-shadow: 0 0 0 2px rgba(230, 126, 34, 0.4);
            z-index: 10;
        }}
        .bbox-tag {{
            position: absolute;
            top: -20px; left: 0;
            color: #fff;
            font-size: 10px;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 3px;
            white-space: nowrap;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            opacity: 0;
            transition: opacity 0.15s ease;
            pointer-events: none;
        }}
        .bbox-overlay:hover .bbox-tag {{
            opacity: 1;
        }}
        .bbox-tooltip {{
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            margin-top: 4px;
            background: #2C2417;
            color: #F5E6D3;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 12px;
            line-height: 1.4;
            max-width: 280px;
            min-width: 120px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.25);
            z-index: 100;
            pointer-events: none;
        }}
        .bbox-overlay:hover .bbox-tooltip {{
            display: block;
        }}
        .tooltip-label {{
            font-weight: 700;
            font-size: 10px;
            text-transform: uppercase;
            margin-bottom: 4px;
            letter-spacing: 0.03em;
        }}
        .tooltip-content {{
            color: #D4C4A8;
            word-break: break-word;
        }}
    </style>
    """

    components.html(html_content, height=display_height + 30, scrolling=False)


def call_ocr_api(api_base: str, image_path: Path) -> tuple[dict | None, str | None]:
    content_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    try:
        resp = requests.post(
            f"{api_base.rstrip('/')}/ocr/image",
            files={"file": (image_path.name, image_path.read_bytes(), content_type)},
            timeout=660,
        )
        resp.raise_for_status()
        return resp.json(), None
    except requests.RequestException as error:
        return None, str(error)


def set_viewing(name: str) -> None:
    st.session_state.viewing = name


def toggle_select(name: str) -> None:
    if name in st.session_state.selected:
        st.session_state.selected.discard(name)
    else:
        st.session_state.selected.add(name)


def start_processing(names: list[str]) -> None:
    valid_names = [name for name in names if (IMAGES_DIR / name).exists()]
    if not valid_names:
        st.warning("No valid images were available to process.")
        return

    st.session_state.selected = set(valid_names)
    st.session_state.viewing = valid_names[0]
    st.session_state.processing = True
    st.rerun()


def step_extracted_result(step: int) -> None:
    result_files = list_result_files()
    result_names = [result_file.stem for result_file in result_files]
    if not result_names:
        return

    current_name = st.session_state.get("extracted_result_stem")
    if current_name not in result_names:
        current_name = result_names[0]

    try:
        current_index = result_names.index(current_name)
    except ValueError:
        current_index = 0

    next_index = max(0, min(len(result_names) - 1, current_index + step))
    st.session_state.extracted_result_stem = result_names[next_index]


def show_flash_messages() -> None:
    upload_feedback = st.session_state.pop("upload_feedback", None)
    if upload_feedback:
        saved_count = len(upload_feedback["saved"])
        skipped_count = len(upload_feedback["skipped"])
        if saved_count:
            st.success(f"Imported {saved_count} image(s) into the gallery.")
        if skipped_count:
            st.warning("\n".join(upload_feedback["skipped"]))

    process_feedback = st.session_state.pop("process_feedback", None)
    if process_feedback:
        if process_feedback["processed"]:
            names = ", ".join(process_feedback["processed"])
            st.success(f"Processed {len(process_feedback['processed'])} image(s): {names}")
        if process_feedback["skipped"]:
            names = ", ".join(process_feedback["skipped"])
            st.info(f"Skipped already processed image(s): {names}")
        if process_feedback["failed"]:
            st.error("\n".join(process_feedback["failed"]))


def process_selected_images(api_base: str) -> None:
    selected_paths = sorted(IMAGES_DIR / name for name in st.session_state.selected if (IMAGES_DIR / name).exists())
    if not selected_paths:
        st.warning("Select at least one image before processing.")
        return

    progress = st.progress(0, text="Processing selected images...")
    processed: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    total = len(selected_paths)

    for index, image_path in enumerate(selected_paths, start=1):
        result_path = get_result_path(image_path)
        if result_path.exists():
            skipped.append(image_path.name)
            progress.progress(index / total, text=f"Skipping {image_path.name} (already processed)")
            continue

        progress.progress(index / total, text=f"Sending {image_path.name} to OCR API...")
        result, error = call_ocr_api(api_base, image_path)
        if result is None:
            failed.append(f"{image_path.name}: {error}")
            continue

        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        processed.append(image_path.name)

    progress.progress(1.0, text="Processing complete.")
    st.session_state.process_feedback = {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
    }

    if processed:
        st.session_state.viewing = processed[0]

    st.rerun()


def find_image_for_result(result_data: dict, result_stem: str) -> Path | None:
    """Find the source image for a result JSON, trying filename field first, then stem matching."""
    filename = result_data.get("filename")
    if filename:
        candidate = IMAGES_DIR / filename
        if candidate.exists():
            return candidate

    for ext in IMAGE_EXTENSIONS:
        candidate = IMAGES_DIR / f"{result_stem}{ext}"
        if candidate.exists():
            return candidate
    return None


# --- Config ---
st.set_page_config(page_title="Chandra OCR", layout="wide", page_icon="🔍")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- State ---
if "selected" not in st.session_state:
    st.session_state.selected = set()
if "viewing" not in st.session_state:
    st.session_state.viewing = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "extracted_result_stem" not in st.session_state:
    st.session_state.extracted_result_stem = None
if "image_zoom" not in st.session_state:
    st.session_state.image_zoom = 350

ensure_directories()
images = list_images()
available_names = {image.name for image in images}
st.session_state.selected &= available_names
if st.session_state.viewing and st.session_state.viewing not in available_names:
    st.session_state.viewing = None
if not st.session_state.viewing and images:
    st.session_state.viewing = images[0].name

n_total = len(images)
n_done = sum(1 for image in images if get_result_path(image).exists())
n_pending = n_total - n_done

show_flash_messages()

# =============================================
# LEFT SIDEBAR
# =============================================
with st.sidebar:
    st.markdown("### Chandra OCR")
    st.caption("Upload images, select, and send to OCR API.")
    api_base = st.text_input("API URL", value=API_BASE, label_visibility="collapsed", placeholder="API URL...")

    st.divider()
    uploads = st.file_uploader(
        "Add images",
        type=UPLOAD_TYPES,
        accept_multiple_files=True,
        help="Upload multiple images at once.",
    )
    col_upload_a, col_upload_b = st.columns(2)
    if col_upload_a.button("Import", use_container_width=True, disabled=not uploads):
        saved, skipped = save_uploaded_files(uploads)
        if saved:
            st.session_state.selected.update(saved)
            st.session_state.viewing = saved[0]
        st.session_state.upload_feedback = {"saved": saved, "skipped": skipped}
        st.rerun()
    if col_upload_b.button("Import + Extract", use_container_width=True, disabled=not uploads):
        saved, skipped = save_uploaded_files(uploads)
        st.session_state.upload_feedback = {"saved": saved, "skipped": skipped}
        if saved:
            start_processing(saved)
        st.rerun()

    st.divider()

    select_all_disabled = not images
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Select All", use_container_width=True, disabled=select_all_disabled):
            st.session_state.selected = {p.name for p in images}
            st.rerun()
    with col_b:
        if st.button("Clear", use_container_width=True, disabled=select_all_disabled):
            st.session_state.selected = set()
            st.rerun()

    if st.button("Select Pending", use_container_width=True, disabled=select_all_disabled):
        st.session_state.selected = {p.name for p in images if not get_result_path(p).exists()}
        st.rerun()

    n_selected = len(st.session_state.selected)
    if st.button(
        f"Process Selected ({n_selected})",
        type="primary",
        disabled=n_selected == 0,
        use_container_width=True,
    ):
        st.session_state.processing = True

    st.divider()

    # Stats row
    stat_cols = st.columns(3)
    stat_cols[0].markdown(f"**{n_total}**<br><span style='font-size:0.7rem;color:#A89070;'>Total</span>", unsafe_allow_html=True)
    stat_cols[1].markdown(f"**{n_done}**<br><span style='font-size:0.7rem;color:#27ae60;'>Done</span>", unsafe_allow_html=True)
    stat_cols[2].markdown(f"**{n_pending}**<br><span style='font-size:0.7rem;color:#E67E22;'>Pending</span>", unsafe_allow_html=True)

    st.divider()

    if not images:
        st.info("Upload images to start building the gallery.")
    else:
        for image_path in images:
            has_result = get_result_path(image_path).exists()
            name = image_path.name
            is_selected = name in st.session_state.selected
            is_viewing = st.session_state.viewing == name

            # Status badge
            status_html = (
                '<span class="gallery-status gallery-status-done">done</span>'
                if has_result
                else '<span class="gallery-status gallery-status-pending">pending</span>'
            )

            # Thumbnail + name button row
            thumb_col, info_col = st.columns([1, 2])
            with thumb_col:
                with Image.open(image_path) as opened_image:
                    thumb = make_thumbnail(opened_image.convert("RGB"), 60)
                st.image(thumb, use_container_width=True)
            with info_col:
                if st.button(f"{'▸ ' if is_viewing else ''}{name}", key=f"open_{name}", use_container_width=True):
                    st.session_state.viewing = name
                    st.rerun()
                st.markdown(status_html, unsafe_allow_html=True)

            btn_cols = st.columns([1, 1, 1])
            with btn_cols[0]:
                st.checkbox(
                    "Sel",
                    value=is_selected,
                    key=f"cb_{name}",
                    on_change=toggle_select,
                    args=(name,),
                    label_visibility="collapsed",
                )
            with btn_cols[1]:
                if st.button("OCR", key=f"extract_{name}", use_container_width=True):
                    start_processing([name])

    st.divider()

    st.markdown("**Image Display**")
    st.session_state.image_zoom = st.slider(
        "Image size",
        min_value=150,
        max_value=800,
        value=st.session_state.image_zoom,
        step=50,
        help="Adjust the display size of images",
        label_visibility="collapsed",
    )
    st.caption(f"Image width: {st.session_state.image_zoom}px")

    st.divider()
    show_labels = st.multiselect(
        "Filter labels",
        options=list(LABEL_COLORS.keys()),
        default=list(LABEL_COLORS.keys()),
    )

# =============================================
# PROCESS SELECTED
# =============================================
if st.session_state.processing:
    st.session_state.processing = False
    process_selected_images(api_base)

# =============================================
# MAIN AREA
# =============================================
st.title("Chandra OCR")

metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Gallery Images", n_total)
metric_b.metric("Selected", len(st.session_state.selected))
metric_c.metric("Processed", n_done)

image_width = st.session_state.image_zoom

workspace_tab, extracted_tab = st.tabs(["Workspace", "Extracted Results"])

with workspace_tab:
    if not images:
        st.markdown(
            '<div class="status-card">Upload one or more images from the sidebar to start a batch OCR run.</div>',
            unsafe_allow_html=True,
        )
    elif st.session_state.viewing:
        selected_name = st.session_state.viewing
        image_path = IMAGES_DIR / selected_name

        if not image_path.exists():
            st.error(f"Image not found: {selected_name}")
            st.stop()

        result_path = get_result_path(image_path)
        with Image.open(image_path) as opened_image:
            original = opened_image.convert("RGB")

        st.markdown(f"#### {selected_name}")

        action_col_a, action_col_b, _ = st.columns([1, 1, 2])
        with action_col_a:
            if st.button("Extract This Image", type="primary", use_container_width=True):
                start_processing([selected_name])
        with action_col_b:
            if st.button("Select This Image", use_container_width=True):
                st.session_state.selected.add(selected_name)
                st.rerun()

        if not result_path.exists():
            col_preview, col_help = st.columns([1, 1], gap="large")
            with col_preview:
                st.image(original, width=image_width)
            with col_help:
                st.markdown(
                    '<div class="status-card">This image has not been processed yet. '
                    'Select it and click <strong>Process Selected</strong> in the sidebar, '
                    'or click <strong>Extract This Image</strong> above.</div>',
                    unsafe_allow_html=True,
                )
        else:
            result = json.loads(result_path.read_text())
            chunks = result.get("chunks", [])
            filtered_chunks = [chunk for chunk in chunks if chunk.get("label") in show_labels]

            col_image, col_text = st.columns([1, 1], gap="large")

            with col_image:
                render_interactive_image(original, filtered_chunks, image_width)
                st.caption(f"{len(filtered_chunks)} visible blocks")
                labels_found = sorted({chunk.get("label", "") for chunk in filtered_chunks if chunk.get("label")})
                if labels_found:
                    legend = " ".join(
                        f'<span class="label-pill" style="background:{LABEL_COLORS.get(label, DEFAULT_COLOR)};">'
                        f'{label}</span>'
                        for label in labels_found
                    )
                    st.markdown(legend, unsafe_allow_html=True)

            with col_text:
                tab_md, tab_chunks, tab_html, tab_json = st.tabs(["Markdown", "Chunks", "HTML", "JSON"])
                with tab_md:
                    st.markdown(result.get("markdown", ""))
                with tab_chunks:
                    if not filtered_chunks:
                        st.info("No chunks matched the current label filter.")
                    for chunk in filtered_chunks:
                        label = chunk.get("label", "Unknown")
                        color = LABEL_COLORS.get(label, DEFAULT_COLOR)
                        st.markdown(
                            f'<div class="chunk-card" style="border-left-color:{color};">'
                            f'<div class="chunk-label" style="color:{color};">{label}</div>'
                            f'<div class="chunk-bbox">bbox: {chunk.get("bbox")}</div>'
                            f'<div>{chunk.get("content", "")}</div></div>',
                            unsafe_allow_html=True,
                        )
                with tab_html:
                    st.code(result.get("raw_html", ""), language="html")
                with tab_json:
                    st.json(result)
    else:
        st.markdown(
            '<div class="status-card">Pick an image from the sidebar to preview it, '
            'or upload a new batch and process it in one go.</div>',
            unsafe_allow_html=True,
        )

# =============================================
# EXTRACTED RESULTS TAB
# =============================================
with extracted_tab:
    result_files = list_result_files()
    if not result_files:
        st.info("No extracted results found in `results/` yet.")
    else:
        result_stems = [rf.stem for rf in result_files]

        # Initialize or validate current selection
        if st.session_state.extracted_result_stem not in result_stems:
            st.session_state.extracted_result_stem = result_stems[0]

        current_index = result_stems.index(st.session_state.extracted_result_stem)

        # Navigation bar
        nav_a, nav_b, nav_c, nav_d = st.columns([1, 1, 3, 1])
        with nav_a:
            if st.button("← Previous", disabled=current_index == 0, use_container_width=True, key="ext_prev"):
                step_extracted_result(-1)
                st.rerun()
        with nav_b:
            if st.button("Next →", disabled=current_index == len(result_stems) - 1, use_container_width=True, key="ext_next"):
                step_extracted_result(1)
                st.rerun()
        with nav_c:
            selected_stem = st.selectbox(
                "Result",
                options=result_stems,
                index=current_index,
                key="extracted_result_selector",
                label_visibility="collapsed",
            )
            if selected_stem != st.session_state.extracted_result_stem:
                st.session_state.extracted_result_stem = selected_stem
                st.rerun()
        with nav_d:
            st.markdown(
                f'<span class="result-counter">{current_index + 1} / {len(result_stems)}</span>',
                unsafe_allow_html=True,
            )

        # Load result
        selected_result_path = RESULTS_DIR / f"{st.session_state.extracted_result_stem}.json"
        extracted_result = json.loads(selected_result_path.read_text())
        extracted_chunks = extracted_result.get("chunks", [])
        filtered_extracted_chunks = [
            chunk for chunk in extracted_chunks if chunk.get("label") in show_labels
        ]

        # Metrics row
        info_a, info_b, info_c = st.columns(3)
        info_a.metric("Chunks", len(extracted_chunks))
        info_b.metric("Visible", len(filtered_extracted_chunks))
        info_c.metric("Model", extracted_result.get("model", "unknown"))

        # Image + Results side by side
        linked_image_path = find_image_for_result(extracted_result, st.session_state.extracted_result_stem)

        col_img, col_res = st.columns([1, 1], gap="large")

        with col_img:
            if linked_image_path and linked_image_path.exists():
                with Image.open(linked_image_path) as opened_image:
                    original = opened_image.convert("RGB")
                render_interactive_image(original, filtered_extracted_chunks, image_width)

                labels_found = sorted({c.get("label", "") for c in filtered_extracted_chunks if c.get("label")})
                if labels_found:
                    legend = " ".join(
                        f'<span class="label-pill" style="background:{LABEL_COLORS.get(l, DEFAULT_COLOR)};">{l}</span>'
                        for l in labels_found
                    )
                    st.markdown(legend, unsafe_allow_html=True)
            else:
                st.warning(f"Original image not found for this result.")

        with col_res:
            result_tab_md, result_tab_chunks, result_tab_html, result_tab_json = st.tabs(
                ["Markdown", "Chunks", "HTML", "JSON"]
            )
            with result_tab_md:
                st.markdown(extracted_result.get("markdown", ""))
            with result_tab_chunks:
                if not filtered_extracted_chunks:
                    st.info("No chunks matched the current label filter.")
                for chunk in filtered_extracted_chunks:
                    label = chunk.get("label", "Unknown")
                    color = LABEL_COLORS.get(label, DEFAULT_COLOR)
                    st.markdown(
                        f'<div class="chunk-card" style="border-left-color:{color};">'
                        f'<div class="chunk-label" style="color:{color};">{label}</div>'
                        f'<div class="chunk-bbox">bbox: {chunk.get("bbox")}</div>'
                        f'<div>{chunk.get("content", "")}</div></div>',
                        unsafe_allow_html=True,
                    )
            with result_tab_html:
                st.code(extracted_result.get("raw_html", ""), language="html")
            with result_tab_json:
                st.json(extracted_result)
