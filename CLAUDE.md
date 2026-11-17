# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A single-page Streamlit app: the user enters text and clicks [영어] / [일본어] / [베트남어] to translate it into English / Japanese / Vietnamese via the OpenAI API. UI text and docs are in Korean.

- `PRD.md` — the spec (feature requirements F1–F5, env vars, acceptance criteria). Treat it as the source of truth.
- `PROMPTS.md` — the staged development plan (1: skeleton, 2: translation feature, 3: UI design, 4: Playwright review). All four stages are done, and the stage-4 review findings have been fixed.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py          # http://localhost:8501
python -m streamlit run app.py --server.headless true   # for background runs / Playwright testing
```

Changes to `.streamlit/config.toml` need a server restart; changes to `app.py` are picked up on the next rerun.

There is no test suite, linter, or build step. Verification is done by running the app and driving it with the Playwright MCP tools; their output goes to `.playwright-mcp/` (gitignored).
- Use `locator.fill()` to enter text. Setting `textarea.value` via JS does not reach Streamlit's state.
- Because the result card keeps its heading across runs, wait for the result text itself to change (or for the buttons to become enabled again) rather than for the heading to appear.

The logic functions can be called directly without the UI, e.g. `OPENAI_API_KEY="" python -c "import app; app.translate('hi', 'Japanese')"` to check missing-key handling. Env vars set this way take precedence because `load_dotenv` does not override them. `run_translation` can also be called directly; it writes to `st.session_state["notice"]` / `["result"]`.

## Architecture

All code is in `app.py`, split into config (`get_config`), translation (`translate_stream`, `translate`, `validate_input`), and UI (`main` plus `run_translation` / `render_*`).

- **Click flow:** a button's `on_click` sets `st.session_state["pending"]`. The next run renders all buttons `disabled`, pops `pending`, calls `run_translation`, then `st.rerun()`. This prevents repeated clicks from sending several API calls. Popping `pending` before translating means an interrupted run never leaves the buttons stuck disabled.
- **Results and messages** are stored in `session_state` as `result` / `notice`, each with the `source` text. They are only shown while the textarea still matches `source`, so an edited source never sits next to an old translation.
- **Streaming:** `stream_into_card` draws partial output into a placeholder with `st.code` (throttled by `STREAM_REFRESH_SECONDS`). The `st.rerun()` afterwards redraws the final card through `render_result`.
- **Errors:** `translate_stream` raises `ConfigError` / `TranslationError`. `TranslationError` carries only the exception class name, so API keys never reach the screen. `run_translation` also catches any other `Exception` and shows the same generic message; Streamlit's rerun/stop exceptions derive from `BaseException`, so they are not swallowed. `.streamlit/config.toml` sets `showErrorDetails = "type"` as a backstop. The real error type is logged to the server console (`번역 실패: ...`), so check there first when the UI shows the generic error.
- **OpenAI client:** cached by `st.cache_resource` with `timeout=60, max_retries=1`. With streaming, the timeout applies to the wait between chunks, so long translations are not cut off.
- **Languages:** `LANGUAGES` maps the Korean button label to the language name sent to the model, and `FLAGS` holds the button emoji. Add an entry to both to add a language.
- **Styling:** a small `CUSTOM_CSS` block avoids hardcoded background/text colors so Streamlit's light and dark themes both work. Windows lacks flag emoji, so a Twemoji flag font is loaded from jsDelivr and applied only to flag code points on the buttons and `.result-title`.
- **Character counter:** Streamlit only sends textarea values on blur, so `CHAR_COUNT_SCRIPT` (injected via `st.html(..., unsafe_allow_javascript=True)`) updates `.char-count` on every keystroke in the browser. It counts code points to match Python's `len()`.
- **Config (PRD §8):** `OPENAI_API_KEY` and `OPENAI_MODEL` (default `gpt-6.1-sol`). They are read from `.env` locally, falling back to `st.secrets` on Streamlit Community Cloud, where `.env` is not deployed. Accessing `st.secrets` without a secrets file raises, so it is guarded.
- Input limit is 5,000 characters. Empty or over-limit input never triggers an API call.
