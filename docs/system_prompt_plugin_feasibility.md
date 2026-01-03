# Plugin feasibility for system prompt control

## Current system prompt flow
- The prompt enhancer pulls its system prompt instructions from the model definition (`image_prompt_enhancer_instructions` or `video_prompt_enhancer_instructions`) before generating prompts, so updating those values changes what the model receives. These values can also be overridden per finetune file.
- `process_prompt_enhancer` reads the instruction fields, forwards them to `generate_cinematic_prompt`, and returns the enhanced prompt, meaning a plugin only needs to change the instruction text before this function runs to affect output.

## Plugin capabilities that help
- The plugin API allows requesting globals from the main app (e.g., `server_config` or other state) and setting them at runtime via `set_global`, so a plugin can swap prompt-enhancer instruction strings without editing core code.
- Plugins can also insert UI elements after existing components, letting users edit instruction text interactively and persist it in plugin-managed state or by writing back to model/finetune configs.

## Feasibility assessment
- Because the prompt enhancer reads instruction strings at call time and plugins can both modify globals and inject UI, a plugin can surface text boxes for image/video system prompts and update the in-memory instruction fields before `process_prompt_enhancer` runs. Persisting changes could be done by writing to finetune JSON files, which already support overriding prompt enhancer instructions.
- No core changes are required: the existing hooks are sufficient for reading/writing globals and injecting controls. The main work is UI wiring and ensuring any persisted edits respect the finetune schema.

## Confidence and scope
- Confidence to deliver a first working version in one iteration: **high**. The plugin API already exposes the necessary hooks to read and mutate the instruction strings at runtime, and the UI surface can reuse existing pattern of text inputs added after a component.
- Expected effort: wiring the UI controls to the instruction values, validating input, and adding an optional persistence step that writes back to finetune JSON. No novel algorithmic work is required.
