# 🔐 GitHub Secrets 설정 가이드

## ⚠️ 중요: 이메일 기능 사용을 위한 필수 단계

GitHub Actions에서 이메일을 보내려면 환경 변수를 GitHub Secrets에 등록해야 합니다.

---

## 📝 설정 방법

### 1단계: GitHub 저장소 Settings로 이동

```
https://github.com/9min/bitcoin-analysis/settings/secrets/actions
```

### 2단계: "New repository secret" 버튼 클릭

### 3단계: 다음 3개의 Secret 추가

#### Secret 1: EMAIL_ADDRESS
- **Name**: `EMAIL_ADDRESS`
- **Value**: `gm870711@gmail.com`
- **"Add secret" 클릭**

#### Secret 2: EMAIL_PASSWORD
- **Name**: `EMAIL_PASSWORD`
- **Value**: `새로_발급받은_Gmail_앱_비밀번호`
- **"Add secret" 클릭**

⚠️ **중요:** 기존 비밀번호(`riqntklboduwdnoz`)는 이미 노출되었으므로 **절대 사용하지 마세요!**
새로운 앱 비밀번호를 발급받으세요: https://myaccount.google.com/apppasswords

#### Secret 3: RECIPIENT_EMAIL
- **Name**: `RECIPIENT_EMAIL`
- **Value**: `gm0711@kakao.com`
- **"Add secret" 클릭**

---

## 🔄 GitHub Actions Workflow 파일 수정 필요

`.github/workflows/deploy.yml` 파일에 환경 변수를 전달해야 합니다.

---

## ✅ 완료 확인

모든 Secret이 등록되면 다음과 같이 표시됩니다:
- EMAIL_ADDRESS
- EMAIL_PASSWORD
- RECIPIENT_EMAIL

---

## 📌 로컬 환경 사용법

로컬에서 테스트할 때는 `.env` 파일을 사용하세요:

```bash
# .env 파일 내용
EMAIL_ADDRESS=gm870711@gmail.com
EMAIL_PASSWORD=새로운_앱_비밀번호
RECIPIENT_EMAIL=gm0711@kakao.com
```

**주의:** `.env` 파일은 `.gitignore`에 포함되어 있어 Git에 올라가지 않습니다.

