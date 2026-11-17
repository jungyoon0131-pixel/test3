import logging
import os
import time

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-6.1-sol"
MAX_CHARS = 5000

# API가 응답하지 않을 때 오래 기다리지 않도록 제한한다.
# 스트리밍에서는 청크 사이 대기 시간에 적용되므로 긴 번역도 끊기지 않는다.
API_TIMEOUT_SECONDS = 60
API_MAX_RETRIES = 1

# 스트리밍 중 화면 갱신 간격(초)
STREAM_REFRESH_SECONDS = 0.1

# 버튼 라벨(한국어) -> 모델에 전달할 언어 이름
LANGUAGES = {
    "영어": "English",
    "일본어": "Japanese",
    "베트남어": "Vietnamese",
}

# 버튼에 붙일 국기 아이콘
FLAGS = {
    "영어": "🇺🇸",
    "일본어": "🇯🇵",
    "베트남어": "🇻🇳",
}

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text into "
    "{target_language}. Output only the translated text without any explanation."
)

GENERIC_ERROR = "번역 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

# Windows는 국기 이모지를 지원하지 않으므로 국기 문자에만 Twemoji 폰트를 적용한다.
# Streamlit 테마 변수만 사용해 라이트/다크 모드 모두에서 자연스럽게 보이도록 함.
CUSTOM_CSS = """
<style>
@font-face {
    font-family: "Twemoji Country Flags";
    unicode-range: U+1F1E6-1F1FF, U+1F3F4, U+E0062-E0063, U+E0065, U+E0067, U+E006C, U+E006E, U+E0073-E0074, U+E0077, U+E007F;
    src: url("https://cdn.jsdelivr.net/npm/country-flag-emoji-polyfill@0.1.8/dist/TwemojiCountryFlags.woff2") format("woff2");
    font-display: swap;
}
.stButton button p, .result-title {
    font-family: "Twemoji Country Flags", "Source Sans", sans-serif;
}
.block-container { padding-top: 2.5rem; max-width: 720px; }
.stTextArea textarea { border-radius: 10px; font-size: 1rem; line-height: 1.6; }
.stButton > button {
    border-radius: 10px;
    padding: 0.6rem 0.5rem;
    font-weight: 600;
    transition: transform 0.1s ease, box-shadow 0.15s ease;
}
.stButton > button:hover:enabled { transform: translateY(-1px); box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12); }
.stButton > button:active { transform: translateY(0); }
.result-title { font-weight: 600; margin-bottom: 0.5rem; }
.char-count { text-align: right; font-size: 0.85rem; opacity: 0.65; margin-top: -0.5rem; }
.char-count.over { color: #e5484d; opacity: 1; font-weight: 600; }
.footer { text-align: center; font-size: 0.8rem; opacity: 0.5; margin-top: 3rem; }
</style>
"""

# Streamlit은 입력창에서 포커스가 빠질 때만 값을 서버로 보내므로,
# 글자 수는 브라우저에서 입력할 때마다 직접 갱신한다.
CHAR_COUNT_SCRIPT = """
<script>
(() => {
  if (window.__charCounterInstalled) return;
  window.__charCounterInstalled = true;
  const max = %d;
  document.addEventListener("input", (e) => {
    if (e.target.tagName !== "TEXTAREA") return;
    const el = document.querySelector(".char-count");
    if (!el) return;
    const n = [...e.target.value].length;  // Python len()과 같은 기준(코드 포인트)
    el.textContent = n.toLocaleString("en-US") + " / " + max.toLocaleString("en-US") + "자";
    el.classList.toggle("over", n > max);
  });
})();
</script>
""" % MAX_CHARS


class ConfigError(Exception):
    """API 키 등 필수 설정이 없을 때 발생."""


class TranslationError(Exception):
    """번역 API 호출이 실패했을 때 발생."""


# ---------- 설정 ----------

def _read_secret(name):
    """st.secrets에서 값을 읽는다. secrets 파일이 없으면 None."""
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def get_config():
    """.env(로컬) -> st.secrets(Streamlit Cloud) 순으로 설정을 읽는다."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY") or _read_secret("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL") or _read_secret("OPENAI_MODEL") or DEFAULT_MODEL
    return {"api_key": api_key, "model": model}


# ---------- 번역 ----------

@st.cache_resource
def _get_client(api_key):
    return OpenAI(api_key=api_key, timeout=API_TIMEOUT_SECONDS, max_retries=API_MAX_RETRIES)


def translate_stream(text, target_language):
    """text를 target_language(예: "English")로 번역하며 조각(str)을 차례로 내보낸다."""
    config = get_config()
    if not config["api_key"]:
        raise ConfigError("API 키가 설정되지 않았습니다.")

    try:
        stream = _get_client(config["api_key"]).chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(target_language=target_language)},
                {"role": "user", "content": text},
            ],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except OpenAIError as e:
        # 상세 메시지에는 키 일부 등이 포함될 수 있으므로 오류 종류만 남긴다.
        raise TranslationError(type(e).__name__) from None


def translate(text, target_language):
    """번역 결과 전체를 한 번에 반환한다. (UI 없이 직접 호출할 때 사용)"""
    result = "".join(translate_stream(text, target_language)).strip()
    if not result:
        raise TranslationError("EmptyResponse")
    return result


def validate_input(text):
    """입력이 올바르지 않으면 경고 문구를, 괜찮으면 None을 반환한다."""
    if not text.strip():
        return "번역할 내용을 입력해주세요."
    if len(text) > MAX_CHARS:
        return f"{MAX_CHARS:,}자 이하로 입력해주세요. (현재 {len(text):,}자)"
    return None


# ---------- UI ----------

def request_translation(label):
    """버튼 콜백: 번역 요청을 기록한다. 다음 실행에서 버튼이 비활성화된다."""
    st.session_state["pending"] = label


def result_card_title(label):
    st.markdown(
        f'<div class="result-title">{FLAGS[label]} {label} 번역 결과</div>',
        unsafe_allow_html=True,
    )


def stream_into_card(text, label):
    """결과 카드 안에 번역문을 스트리밍으로 보여주고, 완성된 번역문을 반환한다."""
    translated = ""
    with st.container(border=True):
        result_card_title(label)
        box = st.empty()
        with st.spinner(f"{label}로 번역하는 중..."):
            last_draw = 0.0
            for piece in translate_stream(text, LANGUAGES[label]):
                translated += piece
                now = time.monotonic()
                if now - last_draw >= STREAM_REFRESH_SECONDS:
                    box.code(translated + " ▌", language=None, wrap_lines=True)
                    last_draw = now
    return translated.strip()


def run_translation(text, label):
    """검증 -> 스트리밍 번역 -> 결과/알림을 session_state에 저장한다."""
    st.session_state.pop("result", None)
    st.session_state.pop("notice", None)

    def notify(kind, message):
        st.session_state["notice"] = {"kind": kind, "message": message, "source": text}

    warning = validate_input(text)
    if warning:
        notify("warning", warning)
        return

    try:
        translated = stream_into_card(text, label)
    except ConfigError as e:
        notify("error", str(e))
        return
    except TranslationError as e:
        logger.warning("번역 실패: %s", e)
        notify("error", GENERIC_ERROR)
        return
    except Exception as e:
        # 예상하지 못한 에러도 화면에는 일반 문구만 보여준다.
        logger.error("예상하지 못한 번역 오류: %s", type(e).__name__)
        notify("error", GENERIC_ERROR)
        return

    if not translated:
        notify("error", GENERIC_ERROR)
        return

    st.session_state["result"] = {"label": label, "text": translated, "source": text}


def render_char_count(text):
    count = len(text)
    css_class = "char-count over" if count > MAX_CHARS else "char-count"
    st.markdown(
        f'<div class="{css_class}">{count:,} / {MAX_CHARS:,}자</div>',
        unsafe_allow_html=True,
    )


def render_notice(text):
    notice = st.session_state.get("notice")
    # 원문이 바뀌면 이전 경고/오류는 더 이상 의미가 없으므로 숨긴다.
    if not notice or notice["source"] != text:
        return
    getattr(st, notice["kind"])(notice["message"])


def render_result(text):
    result = st.session_state.get("result")
    if not result:
        return
    if result["source"] != text:
        st.caption("원문이 바뀌었습니다. 버튼을 눌러 다시 번역하세요.")
        return
    with st.container(border=True):
        result_card_title(result["label"])
        # st.code는 오른쪽 위에 복사 버튼을 제공한다
        st.code(result["text"], language=None, wrap_lines=True)


def render_footer():
    st.markdown('<div class="footer">Powered by OpenAI</div>', unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="간단 번역기", page_icon="🌐", layout="centered")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.html(CHAR_COUNT_SCRIPT, unsafe_allow_javascript=True)

    st.title("🌐 간단 번역기")
    st.caption("글을 입력하고 번역할 언어를 선택하세요")

    text = st.text_area(
        "번역할 글",
        key="source_text",
        height=200,
        placeholder="여기에 번역할 글을 입력하세요...",
        label_visibility="collapsed",
    )
    render_char_count(text)

    # 번역 중에는 버튼을 비활성화해 연타로 API가 여러 번 호출되는 것을 막는다.
    pending = st.session_state.get("pending")
    cols = st.columns(len(LANGUAGES))
    for col, label in zip(cols, LANGUAGES):
        col.button(
            f"{FLAGS[label]} {label}",
            key=f"btn_{label}",
            width="stretch",
            disabled=pending is not None,
            on_click=request_translation,
            args=(label,),
        )

    if pending:
        # 먼저 요청을 지워 두면, 번역 도중 입력창 수정 등으로 실행이 끊겨도 버튼이 잠긴 채 남지 않는다.
        st.session_state.pop("pending", None)
        run_translation(text, pending)
        st.rerun()  # 버튼을 다시 활성화하고 최종 결과(복사 버튼 포함)를 그린다

    render_notice(text)
    render_result(text)
    render_footer()


if __name__ == "__main__":
    main()
