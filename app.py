import json
import mimetypes
import os
from pathlib import Path

import requests
import streamlit as st
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


def make_thumbnail(image: Image.Image, size: int = 100) -> Image.Image:
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
    result_names = [result_file.name for result_file in result_files]
    if not result_names:
        return

    current_name = st.session_state.get("extracted_result", result_names[0])
    try:
        current_index = result_names.index(current_name)
    except ValueError:
        current_index = 0

    next_index = max(0, min(len(result_names) - 1, current_index + step))
    st.session_state.extracted_result = result_names[next_index]


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


# --- Config ---
st.set_page_config(page_title="Chandra OCR", layout="wide")

st.markdown(
    """
<style>
.block-container { padding-top: 1rem; padding-bottom: 1rem; }
.chunk-card {
    background: #f8f9fa;
    border-left: 4px solid #3498db;
    padding: 0.6rem 0.8rem;
    margin-bottom: 0.5rem;
    border-radius: 0 6px 6px 0;
    font-size: 0.85rem;
}
.chunk-label { font-weight: 700; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.2rem; }
.chunk-bbox { font-family: monospace; font-size: 0.7rem; color: #666; }
.status-card {
    border: 1px solid #e6e8eb;
    border-radius: 14px;
    padding: 1rem;
    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}
</style>
""",
    unsafe_allow_html=True,
)

# --- State ---
if "selected" not in st.session_state:
    st.session_state.selected = set()
if "viewing" not in st.session_state:
    st.session_state.viewing = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "extracted_result" not in st.session_state:
    st.session_state.extracted_result = None

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
    st.header("Chandra OCR")
    st.caption("Upload many images, select the ones you want, then send them to the OCR API.")
    api_base = st.text_input("API URL", value=API_BASE)

    st.divider()
    uploads = st.file_uploader(
        "Add images",
        type=UPLOAD_TYPES,
        accept_multiple_files=True,
        help="You can upload multiple images at once.",
    )
    col_upload_a, col_upload_b = st.columns(2)
    if col_upload_a.button("Import", width="stretch", disabled=not uploads):
        saved, skipped = save_uploaded_files(uploads)
        if saved:
            st.session_state.selected.update(saved)
            st.session_state.viewing = saved[0]
        st.session_state.upload_feedback = {"saved": saved, "skipped": skipped}
        st.rerun()
    if col_upload_b.button("Import + Extract", width="stretch", disabled=not uploads):
        saved, skipped = save_uploaded_files(uploads)
        st.session_state.upload_feedback = {"saved": saved, "skipped": skipped}
        if saved:
            start_processing(saved)
        st.rerun()

    st.divider()

    select_all_disabled = not images
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Select All", width="stretch", disabled=select_all_disabled):
            st.session_state.selected = {p.name for p in images}
            st.rerun()
    with col_b:
        if st.button("Clear", width="stretch", disabled=select_all_disabled):
            st.session_state.selected = set()
            st.rerun()

    if st.button("Select Pending", width="stretch", disabled=select_all_disabled):
        st.session_state.selected = {p.name for p in images if not get_result_path(p).exists()}
        st.rerun()

    n_selected = len(st.session_state.selected)
    if st.button(
        f"Process Selected ({n_selected})",
        type="primary",
        disabled=n_selected == 0,
        width="stretch",
    ):
        st.session_state.processing = True

    st.divider()
    st.caption(f"{n_total} images in gallery")
    st.caption(f"{n_done} processed, {n_pending} pending")

    if not images:
        st.info("Upload images to start building the gallery.")
    else:
        for image_path in images:
            has_result = get_result_path(image_path).exists()
            name = image_path.name
            is_selected = name in st.session_state.selected
            is_viewing = st.session_state.viewing == name

            label = name
            if has_result:
                label += "  |  done"
            if st.button(label, key=f"open_{name}", width="stretch"):
                st.session_state.viewing = name
                st.rerun()
            if is_viewing:
                st.caption("Currently open")

            with Image.open(image_path) as opened_image:
                thumb = make_thumbnail(opened_image.convert("RGB"), 96)
            st.image(thumb, width="stretch")

            c1, c2 = st.columns(2, gap="small")
            with c1:
                st.checkbox(
                    "Select",
                    value=is_selected,
                    key=f"cb_{name}",
                    on_change=toggle_select,
                    args=(name,),
                    label_visibility="collapsed",
                )
            with c2:
                if st.button("Extract", key=f"extract_{name}", width="stretch"):
                    start_processing([name])

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
st.title("Chandra OCR Workspace")

metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Gallery Images", n_total)
metric_b.metric("Selected", len(st.session_state.selected))
metric_c.metric("Processed", n_done)

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

        st.markdown(f"### {selected_name}")

        action_col_a, action_col_b = st.columns(2)
        with action_col_a:
            if st.button("Extract This Image", type="primary", width="stretch"):
                start_processing([selected_name])
        with action_col_b:
            if st.button("Select This Image", width="stretch"):
                st.session_state.selected.add(selected_name)
                st.rerun()

        if not result_path.exists():
            col_preview, col_help = st.columns([1.4, 1], gap="large")
            with col_preview:
                st.image(original, width="stretch")
            with col_help:
                st.markdown(
                    '<div class="status-card">This image has not been processed yet. Keep it selected and click <strong>Process Selected</strong> in the sidebar.</div>',
                    unsafe_allow_html=True,
                )
        else:
            result = json.loads(result_path.read_text())
            chunks = result.get("chunks", [])
            filtered_chunks = [chunk for chunk in chunks if chunk.get("label") in show_labels]

            col_image, col_text = st.columns([1.1, 1], gap="large")

            with col_image:
                annotated = draw_bboxes(original, filtered_chunks)
                st.image(annotated, width="stretch")
                st.caption(f"{len(filtered_chunks)} visible blocks")
                labels_found = sorted({chunk.get("label", "") for chunk in filtered_chunks if chunk.get("label")})
                if labels_found:
                    legend = " ".join(
                        f'<span style="background:{LABEL_COLORS.get(label, DEFAULT_COLOR)};color:#fff;'
                        f'padding:2px 6px;border-radius:3px;font-size:0.7rem;">{label}</span>'
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
            '<div class="status-card">Pick an image from the sidebar to preview it, or upload a new batch and process it in one go.</div>',
            unsafe_allow_html=True,
        )

with extracted_tab:
    result_files = list_result_files()
    if not result_files:
        st.info("No extracted results found in `results/` yet.")
    else:
        result_names = [result_file.name for result_file in result_files]
        if st.session_state.extracted_result not in result_names:
            st.session_state.extracted_result = result_names[0]

        current_index = result_names.index(st.session_state.extracted_result)

        nav_col_a, nav_col_b, nav_col_c = st.columns([1, 2, 1])
        with nav_col_a:
            st.button(
                "Previous",
                on_click=step_extracted_result,
                args=(-1,),
                disabled=current_index == 0,
                width="stretch",
            )
        with nav_col_b:
            selected_result_name = st.selectbox(
                "Choose extracted result",
                options=result_names,
                index=current_index,
                key="extracted_result_selector",
            )
            st.session_state.extracted_result = selected_result_name
        with nav_col_c:
            st.button(
                "Next",
                on_click=step_extracted_result,
                args=(1,),
                disabled=current_index == len(result_names) - 1,
                width="stretch",
            )

        st.caption(f"Showing result {current_index + 1} of {len(result_names)}")
        selected_result_path = RESULTS_DIR / selected_result_name
        extracted_result = json.loads(selected_result_path.read_text())
        extracted_chunks = extracted_result.get("chunks", [])
        filtered_extracted_chunks = [
            chunk for chunk in extracted_chunks if chunk.get("label") in show_labels
        ]

        image_filename = extracted_result.get("filename") or f"{selected_result_path.stem}.jpg"
        linked_image_path = IMAGES_DIR / image_filename

        info_col_a, info_col_b, info_col_c = st.columns(3)
        info_col_a.metric("Chunks", len(extracted_chunks))
        info_col_b.metric("Visible", len(filtered_extracted_chunks))
        info_col_c.metric("Model", extracted_result.get("model", "unknown"))

        if linked_image_path.exists():
            with Image.open(linked_image_path) as opened_image:
                original = opened_image.convert("RGB")
            annotated = draw_bboxes(original, filtered_extracted_chunks)
            st.image(annotated, width="stretch")
        else:
            st.warning(f"Original image not found for {image_filename}. Showing text output only.")

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
