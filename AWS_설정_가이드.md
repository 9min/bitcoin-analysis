# 🚀 AWS 환경에서 환경 변수 설정 가이드

기존에 하드코딩된 이메일 정보를 환경 변수로 변경했으므로, AWS에서도 환경 변수 설정이 필요합니다.

---

## 📋 목차
1. [AWS Lambda 설정](#1-aws-lambda-설정)
2. [AWS EC2 설정](#2-aws-ec2-설정)
3. [AWS Elastic Beanstalk 설정](#3-aws-elastic-beanstalk-설정)
4. [코드 업데이트](#4-코드-업데이트)

---

## 1. AWS Lambda 설정

### 환경 변수 추가 방법:

1. **AWS Lambda 콘솔 접속**
   ```
   https://console.aws.amazon.com/lambda
   ```

2. **함수 선택** → **구성(Configuration)** 탭 클릭

3. **환경 변수(Environment variables)** 섹션에서 **편집(Edit)** 클릭

4. **환경 변수 추가:**
   
   | Key | Value |
   |-----|-------|
   | `EMAIL_ADDRESS` | `gm870711@gmail.com` |
   | `EMAIL_PASSWORD` | `새로운_Gmail_앱_비밀번호` |
   | `RECIPIENT_EMAIL` | `gm0711@kakao.com` |

5. **저장(Save)** 클릭

### 코드 업데이트:

```bash
# 로컬에서 zip 파일 생성
zip -r bitcoin_analysis.zip bitcoin_analysis.py requirements.txt

# Lambda 콘솔에서 업로드
# 또는 AWS CLI 사용:
aws lambda update-function-code --function-name your-function-name --zip-file fileb://bitcoin_analysis.zip
```

---

## 2. AWS EC2 설정

### 방법 1: .env 파일 사용 (권장)

#### 1단계: EC2 인스턴스 접속
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
```

#### 2단계: 프로젝트 디렉토리로 이동
```bash
cd /path/to/your/bitcoin-analysis
```

#### 3단계: .env 파일 생성
```bash
nano .env
```

#### 4단계: 환경 변수 입력
```bash
EMAIL_ADDRESS=gm870711@gmail.com
EMAIL_PASSWORD=새로운_Gmail_앱_비밀번호
RECIPIENT_EMAIL=gm0711@kakao.com
```

**Ctrl + X** → **Y** → **Enter** 로 저장

#### 5단계: python-dotenv 설치
```bash
pip install python-dotenv
# 또는
pip3 install python-dotenv
```

#### 6단계: 코드 업데이트
```bash
# GitHub에서 최신 코드 가져오기
git pull origin main

# 또는 직접 파일 업로드
scp -i your-key.pem bitcoin_analysis.py ec2-user@your-ec2-ip:/path/to/bitcoin-analysis/
```

#### 7단계: 테스트
```bash
python bitcoin_analysis.py
# 또는
python3 bitcoin_analysis.py
```

---

### 방법 2: 시스템 환경 변수 설정

#### ~/.bashrc 또는 ~/.bash_profile 수정:
```bash
nano ~/.bashrc
```

#### 파일 맨 아래에 추가:
```bash
export EMAIL_ADDRESS="gm870711@gmail.com"
export EMAIL_PASSWORD="새로운_Gmail_앱_비밀번호"
export RECIPIENT_EMAIL="gm0711@kakao.com"
```

#### 적용:
```bash
source ~/.bashrc
```

---

## 3. AWS Elastic Beanstalk 설정

### 환경 변수 추가:

1. **Elastic Beanstalk 콘솔 접속**
   ```
   https://console.aws.amazon.com/elasticbeanstalk
   ```

2. **환경(Environment) 선택**

3. **구성(Configuration)** 클릭

4. **소프트웨어(Software)** 섹션에서 **편집(Edit)** 클릭

5. **환경 속성(Environment properties)** 섹션에서 추가:
   - `EMAIL_ADDRESS` = `gm870711@gmail.com`
   - `EMAIL_PASSWORD` = `새로운_앱_비밀번호`
   - `RECIPIENT_EMAIL` = `gm0711@kakao.com`

6. **적용(Apply)** 클릭

---

## 4. 코드 업데이트

### 현재 코드 상태:
✅ 이미 `os.getenv()`를 사용하도록 수정됨
✅ `.env` 파일 자동 로드 기능 추가됨
✅ `python-dotenv` 의존성 추가됨

### AWS에 코드 업데이트 방법:

#### Git 사용 (EC2):
```bash
cd /path/to/bitcoin-analysis
git pull origin main
pip install -r requirements.txt
```

#### 직접 업로드 (EC2):
```bash
scp -i your-key.pem bitcoin_analysis.py ec2-user@your-ec2-ip:/path/to/bitcoin-analysis/
scp -i your-key.pem requirements.txt ec2-user@your-ec2-ip:/path/to/bitcoin-analysis/
```

#### Lambda:
- ZIP 파일로 압축 후 콘솔에서 업로드
- 또는 AWS CLI 사용

---

## 🔒 보안 참고사항

### ⚠️ 중요!
1. **기존 Gmail 앱 비밀번호 삭제**
   - https://myaccount.google.com/apppasswords
   - 노출된 비밀번호: `riqntklboduwdnoz` 삭제

2. **새 앱 비밀번호 발급**
   - 같은 페이지에서 새로 발급
   - AWS 환경 변수에 등록

3. **.env 파일 보안**
   - `.gitignore`에 포함 확인 (이미 포함됨)
   - 절대 Git에 커밋하지 말 것
   - EC2에서만 사용

---

## ✅ 테스트 체크리스트

### EC2에서 테스트:
```bash
# 환경 변수 확인
echo $EMAIL_ADDRESS
echo $RECIPIENT_EMAIL

# 스크립트 실행
python bitcoin_analysis.py
```

### Lambda에서 테스트:
1. Lambda 콘솔에서 **테스트(Test)** 클릭
2. 이메일 수신 확인

---

## 📞 문제 해결

### 환경 변수가 인식되지 않을 때:

**EC2:**
```bash
# .env 파일 확인
cat .env

# python-dotenv 설치 확인
pip list | grep dotenv

# 환경 변수 직접 설정 후 테스트
export EMAIL_ADDRESS="gm870711@gmail.com"
export EMAIL_PASSWORD="비밀번호"
export RECIPIENT_EMAIL="gm0711@kakao.com"
python bitcoin_analysis.py
```

**Lambda:**
- 환경 변수 섹션에 올바르게 입력되었는지 확인
- 함수 재배포 필요할 수 있음

---

## 📚 추가 참고

- **GitHub 버전**: 환경 변수는 GitHub Secrets로 관리
- **AWS 버전**: 각 환경의 환경 변수 기능 사용
- **로컬 개발**: `.env` 파일 사용

모든 환경에서 동일한 코드가 작동합니다! 🎉

