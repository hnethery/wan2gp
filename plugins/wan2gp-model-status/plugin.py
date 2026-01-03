"""
Model Status Plugin

Adds quick “downloaded vs missing” badges next to the core model dropdown
and a dedicated tab to scan every model definition.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import gradio as gr

from shared.utils.plugins import WAN2GPPlugin


class ModelAvailabilityAnalyzer:
    """Lightweight analyzer for checking model file presence."""

    def __init__(self, models_def: Dict, locator_func):
        self.models_def = models_def or {}
        self.locator_func = locator_func

    def _extract_urls(self, model_def: Dict) -> List[str]:
        urls: List[str] = []
        # Some definitions wrap fields under "model", others are flat
        source = model_def.get("model", model_def)

        for key in ("URLs", "URLs2", "preload_URLs", "loras"):
            if key not in source:
                continue
            value = source.get(key)
            if isinstance(value, list):
                urls.extend([v for v in value if isinstance(v, str)])
            elif isinstance(value, str):
                urls.append(value)
        return urls

    def _resolve_local_path(self, url: str) -> Optional[str]:
        if callable(self.locator_func):
            try:
                path = self.locator_func(url)
                if path:
                    return path
            except Exception:
                return None
        return None

    def describe_files(self, model_type: str) -> List[Dict]:
        if model_type not in self.models_def:
            return []

        model_def = self.models_def[model_type]
        urls = self._extract_urls(model_def)
        details: List[Dict] = []

        for url in urls:
            filename = os.path.basename(url)
            local_path = self._resolve_local_path(url)
            exists = os.path.exists(local_path) if local_path else False
            details.append(
                {
                    "filename": filename,
                    "status": "downloaded" if exists else "missing",
                    "path": local_path if exists else None,
                }
            )
        return details

    def status(self, model_type: str) -> str:
        details = self.describe_files(model_type)
        if not details:
            return "unknown"
        downloaded = sum(1 for item in details if item["status"] == "downloaded")
        if downloaded == len(details):
            return "downloaded"
        if downloaded == 0:
            return "missing"
        return "partial"

    def summary_rows(self) -> List[Dict]:
        rows: List[Dict] = []
        for model_type in sorted(self.models_def.keys()):
            status = self.status(model_type)
            details = self.describe_files(model_type)
            missing = [d["filename"] for d in details if d["status"] != "downloaded"]
            rows.append(
                {
                    "model_type": model_type,
                    "status": status,
                    "missing_files": ", ".join(missing) if missing else "",
                }
            )
        return rows


class ModelStatusPlugin(WAN2GPPlugin):
    def __init__(self):
        super().__init__()
        self.name = "Model Status"
        self.version = "1.0.0"
        self.description = "Badges next to the model picker plus a full model scan tab."
        self.analyzer: Optional[ModelAvailabilityAnalyzer] = None

    def setup_ui(self):
        # Globals
        self.request_global("models_def")
        self.request_global("get_local_model_filename")

        # Core model pickers
        self.request_component("model_list")
        self.request_component("model_base_types_list")

        # Tab for overview
        self.add_tab(
            tab_id="model_status_overview",
            label="Availability",
            component_constructor=self._build_tab,
            position=3,
        )

    def _init_analyzer(self):
        if self.analyzer is None:
            models_def = getattr(self, "models_def", {})
            locator = getattr(self, "get_local_model_filename", None)
            self.analyzer = ModelAvailabilityAnalyzer(models_def, locator)
        return self.analyzer

    def post_ui_setup(self, components: Dict):
        analyzer = self._init_analyzer()

        if not hasattr(self, "model_list") or self.model_list is None:
            return {}

        def create_badge():
            badge = gr.Markdown("", elem_id="model_availability_badge", visible=True)

            def render(model_choice):
                if not model_choice:
                    return ""
                status = analyzer.status(model_choice)
                files = analyzer.describe_files(model_choice)
                missing = [f"`{f['filename']}`" for f in files if f["status"] != "downloaded"]

                if status == "downloaded":
                    icon = "✅"
                    caption = "All files present"
                elif status == "partial":
                    icon = "◐"
                    caption = "Some files missing"
                elif status == "missing":
                    icon = "❌"
                    caption = "No files found"
                else:
                    icon = "❓"
                    caption = "Unknown status"

                lines = [f"{icon} **Model availability:** {caption}"]
                if missing:
                    lines.append("Missing: " + ", ".join(missing))
                return "\n".join(lines)

            self.model_list.change(
                fn=render,
                inputs=[self.model_list],
                outputs=[badge],
                show_progress=False,
            )

            return badge

        self.insert_after("model_list", create_badge)
        return {}

    def _build_tab(self):
        analyzer = self._init_analyzer()

        def rescan():
            return analyzer.summary_rows()

        with gr.Blocks() as tab:
            gr.Markdown(
                """
                ### Model availability overview
                Quickly see which definitions have all of their referenced files locally.
                """
            )
            scan_button = gr.Button("Rescan models", variant="primary")
            table = gr.Dataframe(
                headers=["model_type", "status", "missing_files"],
                datatype=["str", "str", "str"],
                interactive=False,
                wrap=True,
            )

            scan_button.click(fn=rescan, inputs=None, outputs=table)
            # Populate once on load
            tab.load(fn=rescan, inputs=None, outputs=table)
        return tab
