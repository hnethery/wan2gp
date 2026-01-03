# wan2gp-model-status

A lightweight Wan2GP plugin that surfaces download status for every model definition:

- Adds a badge directly under the main model dropdown showing whether the selected model is downloaded, partial, or missing.
- Provides an **Availability** tab with a quick scan of every model definition and any missing files.

## How it works

The plugin reads Wan2GP's `models_def` registry and uses the existing `get_local_model_filename` helper to resolve file paths referenced in `URLs`, `URLs2`, `preload_URLs`, and `loras` fields.

## Installation

Install from a blank repository named `wan2gp-model-status` (one repo per plugin), then enable it from the **Plugins** tab and restart Wan2GP.
