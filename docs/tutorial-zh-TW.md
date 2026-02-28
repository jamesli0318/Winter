# Winter Daily Digest — 使用教學

自動追蹤 aespa Winter 相關 Twitter 帳號，每日彙整推文並透過 Telegram 發送摘要。

---

## 目錄

1. [事前準備](#1-事前準備)
2. [取得 API 金鑰](#2-取得-api-金鑰)
3. [安裝與設定](#3-安裝與設定)
4. [執行帳號探索](#4-執行帳號探索)
5. [測試每日摘要](#5-測試每日摘要)
6. [正式發送](#6-正式發送)
7. [自動化排程](#7-自動化排程)
8. [設定檔詳解](#8-設定檔詳解)
9. [常見問題](#9-常見問題)

---

## 1. 事前準備

- Python 3.10 以上（建議 3.12）
- 一個 Telegram 帳號
- 網路環境能存取 RapidAPI 與 Telegram API

## 2. 取得 API 金鑰

你需要三組金鑰：

### RapidAPI Key（Twitter 資料來源）

1. 前往 [rapidapi.com](https://rapidapi.com) 註冊帳號
2. 搜尋 **Twitter API45** 並訂閱（免費方案每月 50 萬次請求）
3. 在 API 頁面的 **Header Parameters** 區塊找到你的 `X-RapidAPI-Key`

### Anthropic API Key（Claude 摘要分組）

1. 前往 [console.anthropic.com](https://console.anthropic.com) 註冊
2. 在 **API Keys** 頁面建立一組新金鑰

### Telegram Bot Token（訊息發送）

1. 在 Telegram 搜尋 **@BotFather** 並開始對話
2. 發送 `/newbot`，依照指示命名你的 Bot
3. BotFather 會回覆一組格式如 `123456:ABC-DEF...` 的 Token

### 取得 Telegram Chat ID

1. 將你的 Bot 加入目標群組（或直接私訊 Bot 任意一則訊息）
2. 在瀏覽器開啟：
   ```
   https://api.telegram.org/bot<你的TOKEN>/getUpdates
   ```
3. 在回傳的 JSON 中找到 `"chat": {"id": -1001234567890}`，這就是你的 Chat ID

> 群組 Chat ID 通常為負數，私人對話為正數。

---

## 3. 安裝與設定

### 安裝套件

```bash
cd Winter
pip install -e .
```

### 建立環境變數檔

```bash
cp .env.example .env
```

編輯 `.env`，填入你的三組金鑰：

```
ANTHROPIC_API_KEY=sk-ant-你的金鑰
TELEGRAM_BOT_TOKEN=123456:你的Token
RAPIDAPI_KEY=你的RapidAPI金鑰
```

### 建立設定檔

```bash
cp config.example.yaml config.yaml
```

編輯 `config.yaml`，至少要設定 `telegram.chat_id`：

```yaml
discovery:
  keywords:
    - "Winter aespa"
    - "윈터 에스파"
    - "ウィンター aespa"
    - "aespa winter fan"
    - "김민정 에스파"
  min_followers: 500
  min_winter_ratio: 0.25
  max_accounts: 25
  rescan_interval_days: 7

telegram:
  chat_id: "-1001234567890"    # ← 換成你的 Chat ID

claude:
  model: "claude-haiku-4-5-20251001"

timezone: "Asia/Taipei"

manual_include:
  - "aespa_official"

manual_exclude: []
```

---

## 4. 執行帳號探索

帳號探索會自動搜尋 Twitter 上與 Winter 相關的帳號，依據追蹤者數量與推文相關度篩選：

```bash
python main.py discover --verbose
```

執行過程會顯示：

```
Added seed account @aespa_official
Searched 'Winter aespa': found 12 candidates so far
Searched '윈터 에스파': found 18 candidates so far
Discovery complete: 10 accounts from 18 candidates
  @aespa_official       official    12000000 followers  100% winter
  @WinterDailyPics      fansite       85000 followers   92% winter
  @winterlogs_          translator    42000 followers   88% winter
  ...
```

結果會儲存在 `data/accounts.json`。

### 探索邏輯說明

1. **種子帳號**：`manual_include` 中的帳號一定會被加入
2. **關鍵字搜尋**：用 `discovery.keywords` 中的每組關鍵字搜尋 Twitter 用戶
3. **篩選條件**：
   - 追蹤者 ≥ `min_followers`（預設 500）
   - 帳號簡介自動分類（官方/粉絲站/翻譯/新聞/其他）
   - 取樣近期推文，計算提及 Winter 的比例（winter_ratio）
   - winter_ratio ≥ `min_winter_ratio`（預設 25%）
4. **上限**：最多保留 `max_accounts` 個帳號（預設 25）
5. **排除**：`manual_exclude` 中的帳號會被移除

---

## 5. 測試每日摘要

用 `--dry-run` 測試完整流程，摘要只會印在終端機，不會發送到 Telegram：

```bash
python main.py run --dry-run --verbose
```

輸出範例：

```
============================================================
DRY RUN — Telegram message preview:
============================================================
📅 <b>Winter Daily Digest</b>
2026-02-28 (六)

📸 <b>媒體更新</b>
<b>Winter 最新自拍</b>
  └ @aespa_official: 윈터가 보낸 셀카 💕 [❤️ 125,000 🔁 42,000]
  └ @WinterDailyPics: HD photos from today's post...

...
============================================================
(2 message(s), 1847 chars total)
```

如果看到摘要內容正常顯示，表示整條流程都沒問題。

---

## 6. 正式發送

確認測試無誤後，執行：

```bash
python main.py run
```

Bot 會將每日摘要發送到你設定的 Telegram 對話中。

---

## 7. 自動化排程

### 方法一：Docker（推薦）

專案已內建 Docker 設定，使用 supercronic 每天 UTC 00:00（台北時間 08:00）自動執行：

```bash
# 啟動
docker compose up -d

# 查看 log
docker compose logs -f digest

# 停止
docker compose down
```

Docker 會自動掛載 `config.yaml`（唯讀）和 `data/` 目錄（讀寫）。

### 方法二：系統 crontab

```bash
crontab -e
```

新增以下排程（每天台北時間 08:00 執行）：

```
0 0 * * * cd /你的路徑/Winter && /usr/bin/python3 main.py run >> data/cron.log 2>&1
```

---

## 8. 設定檔詳解

### config.yaml

| 欄位 | 說明 | 預設值 |
|------|------|--------|
| `discovery.keywords` | 搜尋用關鍵字清單 | `["Winter aespa", "윈터 에스파"]` |
| `discovery.min_followers` | 最低追蹤者門檻 | `500` |
| `discovery.min_winter_ratio` | 推文中提及 Winter 的最低比例 | `0.25`（25%） |
| `discovery.max_accounts` | 追蹤帳號上限 | `25` |
| `discovery.rescan_interval_days` | 自動重新探索間隔天數 | `7` |
| `telegram.chat_id` | Telegram 目標對話 ID | （必填） |
| `claude.model` | Claude 模型名稱 | `claude-haiku-4-5-20251001` |
| `timezone` | 時區 | `Asia/Taipei` |
| `manual_include` | 強制加入的帳號列表 | `["aespa_official"]` |
| `manual_exclude` | 強制排除的帳號列表 | `[]` |

### .env

| 變數 | 說明 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API 金鑰 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `RAPIDAPI_KEY` | RapidAPI 金鑰 |

### data/ 目錄（自動產生）

| 檔案 | 說明 |
|------|------|
| `accounts.json` | 探索結果，追蹤中的帳號清單 |
| `cache.db` | SQLite 快取，防止推文重複處理（保留 30 天） |
| `last_discovery.txt` | 上次探索的時間戳記 |

---

## 9. 常見問題

### RapidAPI 回傳 403 或 429

- **403**：確認你的 RapidAPI Key 正確，且已訂閱 Twitter API45
- **429**：超過速率限制。程式會自動重試（最多 3 次，間隔 5/15/30 秒），通常等待後即可恢復

### 沒有收到 Telegram 訊息

1. 確認 Bot 已加入目標群組或已私訊過 Bot
2. 確認 `chat_id` 正確（群組為負數）
3. 用 `--dry-run` 確認有產出內容（可能是過去 24 小時沒有新推文）

### 探索結果太少

- 增加 `discovery.keywords` 中的關鍵字
- 降低 `min_followers` 門檻
- 降低 `min_winter_ratio` 門檻
- 在 `manual_include` 手動加入你知道的帳號

### 探索結果包含不相關帳號

- 提高 `min_winter_ratio`（例如 `0.4`）
- 將不想追蹤的帳號加入 `manual_exclude`

### 想立即重新探索

刪除 `data/last_discovery.txt` 後執行摘要，程式會自動觸發探索：

```bash
rm data/last_discovery.txt
python main.py run --dry-run --verbose
```

或直接執行探索指令：

```bash
python main.py discover --verbose
```
