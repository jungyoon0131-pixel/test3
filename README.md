# 🌐 간단 번역기

글을 입력하고 [영어] / [일본어] / [베트남어] 버튼을 누르면 해당 언어로 번역해주는 Streamlit 앱입니다.

## 로컬 실행 방법

### 1. 가상환경 생성 및 활성화

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example`을 복사해 `.env` 파일을 만들고 API 키를 입력합니다.

```bash
# Windows (PowerShell)
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-6.1-sol
```

> `.env` 파일은 `.gitignore`에 포함되어 있으므로 Git에 올라가지 않습니다.

### 4. 앱 실행

```bash
streamlit run app.py
```

브라우저에서 http://localhost:8501 로 접속합니다.

## 배포 방법 (Streamlit Community Cloud)

1. GitHub 저장소를 만들고 코드를 푸시합니다. `.env`가 올라가지 않았는지 확인하세요.
2. [Streamlit Community Cloud](https://share.streamlit.io)에 접속해 저장소를 연결합니다.
3. Main file로 `app.py`를 지정합니다.
4. **App settings → Secrets**에 아래 내용을 등록합니다. `.env`는 배포되지 않으므로 이 단계가 필요합니다.

   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_MODEL = "gpt-6.1-sol"
   ```

5. Deploy 후 발급된 URL로 접속해 번역이 되는지 확인합니다.

> 앱은 `.env` → Secrets 순서로 설정을 읽으므로, 로컬과 배포 환경에서 코드를 바꿀 필요가 없습니다.
