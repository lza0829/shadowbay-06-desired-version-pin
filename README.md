# 影湾 Shadowbay

系统与底层 · IoT 开发底座。

- 前端 http://127.0.0.1:7100
- 接口 http://127.0.0.1:12100

```powershell
docker compose up -d --build
```

本机开发：

```powershell
# 后端
cd backend
pip install -r requirements.txt
$env:预置目录 = (Resolve-Path ..\fixtures)
uvicorn app.main:app --reload --port 12100

# 前端
cd frontend
npm install
npm run dev
```
