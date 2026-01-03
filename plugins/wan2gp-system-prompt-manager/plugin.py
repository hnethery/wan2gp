import json
import os
from typing import Optional, Tuple

import gradio as gr

from shared.utils.plugins import WAN2GPPlugin
from models.ltx_video.utils import prompt_enhance_utils


DEFAULT_IMAGE_PROMPT = prompt_enhance_utils.T2I_VISUAL_PROMPT.strip()
DEFAULT_VIDEO_PROMPT = prompt_enhance_utils.T2V_CINEMATIC_PROMPT.strip()
DEFAULT_I2I_PROMPT = prompt_enhance_utils.IT2I_VISUAL_PROMPT.strip()
DEFAULT_I2V_PROMPT = prompt_enhance_utils.IT2V_CINEMATIC_PROMPT.strip()


class ConfigTabPlugin(WAN2GPPlugin):
    def __init__(self):
        super().__init__()
        self.name = "System Prompt Manager"
        self.version = "1.0.0"
        self.description = "Edit the prompt enhancer system prompts used by each model."

    def setup_ui(self):
        self.request_global("models_def")
        self.request_global("displayed_model_types")
        self.request_global("get_state_model_type")

        self.request_component("state")

        self.add_tab(
            tab_id="system_prompt_manager",
            label="System Prompts",
            component_constructor=self.create_ui,
        )

    def on_tab_select(self, state: dict):
        return self._load_for_tab(state, None)

    def create_ui(self):
        def load_model_prompts(state, selected_model_type):
            return self._load_for_tab(state, selected_model_type)

        def apply_updates(state, selected_model_type, image_prompt_text, video_prompt_text, persist):
            status = self._apply_prompt_updates(state, selected_model_type, image_prompt_text, video_prompt_text, persist)
            model_type, image_prompt, video_prompt, summary = self._load_for_tab(state, selected_model_type)
            combined_status = status if status else summary
            if status and summary:
                combined_status = f"{status}\n\n{summary}"
            return model_type, image_prompt, video_prompt, combined_status

        with gr.Column():
            gr.Markdown(
                """Manage the **system prompts** used by the prompt enhancer. Leave a field empty to fall back to the built-in defaults."""
            )

            with gr.Row():
                model_selector = gr.Dropdown(
                    choices=self.displayed_model_types,
                    label="Model",
                    value=None,
                    allow_custom_value=False,
                )
                status_box = gr.Markdown()

            with gr.Row():
                image_prompt_box = gr.Textbox(
                    label="Image prompt enhancer system prompt",
                    lines=10,
                    placeholder="Leave empty to use the built-in image defaults",
                )
                video_prompt_box = gr.Textbox(
                    label="Video prompt enhancer system prompt",
                    lines=10,
                    placeholder="Leave empty to use the built-in video defaults",
                )

            with gr.Row():
                apply_btn = gr.Button("Apply (session only)", variant="primary")
                persist_btn = gr.Button("Apply and save to model file")

            with gr.Accordion("Built-in defaults (reference)", open=False):
                gr.Markdown(
                    f"""
**Image (text-only prompt)**:

```
{DEFAULT_IMAGE_PROMPT}
```

**Image (with start/reference images)**:

```
{DEFAULT_I2I_PROMPT}
```

**Video (text-only prompt)**:

```
{DEFAULT_VIDEO_PROMPT}
```

**Video (with start/reference images)**:

```
{DEFAULT_I2V_PROMPT}
```
"""
                )

        self.on_tab_outputs = [model_selector, image_prompt_box, video_prompt_box, status_box]

        model_selector.change(
            fn=load_model_prompts,
            inputs=[self.state, model_selector],
            outputs=self.on_tab_outputs,
        )

        apply_btn.click(
            fn=lambda state, model_type, image_text, video_text: apply_updates(
                state, model_type, image_text, video_text, False
            ),
            inputs=[self.state, model_selector, image_prompt_box, video_prompt_box],
            outputs=self.on_tab_outputs,
        )

        persist_btn.click(
            fn=lambda state, model_type, image_text, video_text: apply_updates(
                state, model_type, image_text, video_text, True
            ),
            inputs=[self.state, model_selector, image_prompt_box, video_prompt_box],
            outputs=self.on_tab_outputs,
        )

    def _load_for_tab(self, state: dict, selected_model_type: Optional[str]):
        model_type = self._resolve_model_type(state, selected_model_type)
        image_prompt, video_prompt, summary = self._get_model_prompts(model_type)
        return model_type, image_prompt, video_prompt, summary

    def _resolve_model_type(self, state: dict, selected_model_type: Optional[str]) -> Optional[str]:
        model_type = selected_model_type or (self.get_state_model_type(state) if state is not None else None)
        if not model_type and self.displayed_model_types:
            model_type = self.displayed_model_types[0]

        if model_type and self.displayed_model_types and model_type not in self.displayed_model_types:
            model_type = self.displayed_model_types[0]
        return model_type

    def _get_model_prompts(self, model_type: Optional[str]) -> Tuple[str, str, str]:
        if not model_type:
            return "", "", "Select a model to view its prompt enhancer instructions."

        model_def = self.models_def.get(model_type)
        if model_def is None:
            return "", "", f"No model definition found for '{model_type}'."

        image_prompt = model_def.get("image_prompt_enhancer_instructions") or ""
        video_prompt = model_def.get("video_prompt_enhancer_instructions") or ""

        details = [f"Editing model: **{model_def.get('name', model_type)}**"]
        details.append(
            "Image prompt enhancer: **custom** value set."
            if image_prompt
            else "Image prompt enhancer: using built-in defaults."
        )
        details.append(
            "Video prompt enhancer: **custom** value set."
            if video_prompt
            else "Video prompt enhancer: using built-in defaults."
        )

        return image_prompt, video_prompt, "\n".join(f"- {line}" for line in details)

    def _apply_prompt_updates(
        self,
        state: dict,
        selected_model_type: Optional[str],
        image_prompt_text: Optional[str],
        video_prompt_text: Optional[str],
        persist: bool,
    ) -> str:
        model_type = self._resolve_model_type(state, selected_model_type)
        if not model_type:
            return "Select a model before applying changes."

        model_def = self.models_def.get(model_type)
        if model_def is None:
            return f"No model definition found for '{model_type}'."

        image_prompt = self._clean_prompt(image_prompt_text)
        video_prompt = self._clean_prompt(video_prompt_text)

        changes_applied = self._set_model_prompts(model_def, image_prompt, video_prompt)

        status_parts = []
        if changes_applied:
            status_parts.append("Updated session prompts.")
        else:
            status_parts.append("No changes detected for the session prompts.")

        if persist:
            saved, save_msg = self._persist_prompts(model_def, image_prompt, video_prompt)
            status_parts.append(save_msg)
            if saved:
                status_parts.append("Saved changes will be used on next start as well.")
        else:
            status_parts.append("Changes are in-memory only for this session.")

        return "\n".join(status_parts)

    def _set_model_prompts(
        self,
        model_def: dict,
        image_prompt: Optional[str],
        video_prompt: Optional[str],
    ) -> bool:
        changed = False

        if image_prompt is None:
            if "image_prompt_enhancer_instructions" in model_def:
                model_def.pop("image_prompt_enhancer_instructions", None)
                changed = True
        elif model_def.get("image_prompt_enhancer_instructions") != image_prompt:
            model_def["image_prompt_enhancer_instructions"] = image_prompt
            changed = True

        if video_prompt is None:
            if "video_prompt_enhancer_instructions" in model_def:
                model_def.pop("video_prompt_enhancer_instructions", None)
                changed = True
        elif model_def.get("video_prompt_enhancer_instructions") != video_prompt:
            model_def["video_prompt_enhancer_instructions"] = video_prompt
            changed = True

        return changed

    def _persist_prompts(
        self,
        model_def: dict,
        image_prompt: Optional[str],
        video_prompt: Optional[str],
    ) -> Tuple[bool, str]:
        path = model_def.get("path")
        model_name = model_def.get("name") or model_def.get("architecture") or "model"

        if not path or not os.path.isfile(path):
            return False, f"Cannot save prompts for {model_name}: definition file not found."

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:  # noqa: BLE001
            return False, f"Failed to read model file '{path}': {e}"

        model_block = data.get("model", {})

        if image_prompt is None:
            model_block.pop("image_prompt_enhancer_instructions", None)
        else:
            model_block["image_prompt_enhancer_instructions"] = image_prompt

        if video_prompt is None:
            model_block.pop("video_prompt_enhancer_instructions", None)
        else:
            model_block["video_prompt_enhancer_instructions"] = video_prompt

        data["model"] = model_block

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:  # noqa: BLE001
            return False, f"Failed to write model file '{path}': {e}"

        return True, f"Persisted prompts to {os.path.basename(path)}."

    @staticmethod
    def _clean_prompt(prompt_text: Optional[str]) -> Optional[str]:
        if prompt_text is None:
            return None
        stripped = prompt_text.strip()
        return stripped if stripped else None
