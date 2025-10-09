# 🚀 GitHub 저장소 생성 및 배포 가이드

## 1단계: Git 초기화 (로컬)

현재 폴더에서 다음 명령어를 실행하세요:

```bash
# Git 저장소 초기화
git init

# 모든 파일 추가
git add .

# 첫 커밋
git commit -m "Initial commit: 비트코인 분석 리포트 시스템"
```

## 2단계: GitHub 저장소 생성

1. **GitHub 웹사이트 접속**
   - https://github.com 접속
   - 로그인

2. **새 저장소 생성**
   - 우측 상단 `+` 클릭 → `New repository` 선택
   - 또는 https://github.com/new 직접 접속

3. **저장소 설정**
   ```
   Repository name: bitcoin-analysis
   Description: 📊 비트코인 기술적 분석 자동 리포트 시스템
   
   ⚠️ 중요: Public 선택! (Private는 GitHub Pages 무료 안됨)
   
   ❌ Initialize this repository with:
      - Add a README file (체크 안 함)
      - Add .gitignore (체크 안 함)
      - Choose a license (체크 안 함)
   ```

4. **Create repository 클릭**

## 3단계: GitHub에 푸시

저장소를 만들면 나오는 명령어를 복사해서 실행:

```bash
# 원격 저장소 연결 (YOUR_USERNAME을 본인 이름으로 변경!)
git remote add origin https://github.com/YOUR_USERNAME/bitcoin-analysis.git

# 기본 브랜치 이름을 main으로 변경
git branch -M main

# GitHub에 푸시
git push -u origin main
```

## 4단계: GitHub Pages 활성화

1. **GitHub 저장소 페이지에서**
   - `Settings` 탭 클릭
   
2. **Pages 설정**
   - 왼쪽 메뉴에서 `Pages` 클릭
   
3. **Source 설정**
   ```
   Branch: gh-pages (첫 실행 후에 생성됨)
   Folder: / (root)
   ```
   
4. **저장하고 기다리기**
   - `Save` 버튼 클릭
   - 1-2분 대기

## 5단계: GitHub Actions 실행

1. **Actions 탭으로 이동**
   - 저장소 페이지에서 `Actions` 탭 클릭

2. **워크플로우 확인**
   - "비트코인 분석 리포트 자동 배포" 워크플로우가 보임

3. **수동 실행 (첫 실행)**
   - 워크플로우 클릭
   - 우측 `Run workflow` 버튼 클릭
   - `Run workflow` 다시 클릭하여 확인

4. **실행 확인**
   - 노란색 동그라미 🟡 → 실행 중
   - 초록색 체크 ✅ → 성공!
   - 빨간색 X ❌ → 실패 (로그 확인 필요)

## 6단계: 웹사이트 확인

**첫 실행이 성공하면 다음 주소로 접속:**

```
https://YOUR_USERNAME.github.io/bitcoin-analysis/
```

예시:
- Username이 `johndoe`라면
- https://johndoe.github.io/bitcoin-analysis/

## ✅ 완료!

이제 매 시간마다 자동으로 업데이트됩니다! 🎉

## 🔧 문제 해결

### GitHub Pages가 활성화 안 됨
- 첫 GitHub Actions 실행이 성공해야 `gh-pages` 브랜치가 생성됩니다
- Actions 탭에서 워크플로우가 성공했는지 확인하세요

### 404 Not Found
- GitHub Pages 활성화 후 1-2분 대기
- 브라우저 캐시 삭제 후 다시 시도

### Actions 실행 실패
- Actions 탭에서 실행 로그 확인
- 빨간색 X 부분을 클릭하여 오류 메시지 확인

## 📝 다음 단계

### 수동 업데이트
언제든지 GitHub 저장소 → Actions → Run workflow 클릭

### 자동 업데이트 시간 변경
`.github/workflows/deploy.yml` 파일의 cron 수정 후 커밋

### 코드 수정
1. 로컬에서 파일 수정
2. `git add .`
3. `git commit -m "설명"`
4. `git push`

---

**문제가 있으면 GitHub Issues에 등록해주세요!**

