# 名片正反面辨識合併 — 設計文件

日期: 2026-07-22

## 背景與目標

中文名片常見背面印有英文版資訊（姓名、職稱、公司皆有中英對照）。目前 `handle_image_event` 每次只處理單張圖片，正反面會被存成兩筆獨立資料，或後傳的一面覆蓋/漏掉前一面的欄位。

目標：讓使用者依序傳送正面、背面圖片後，系統自動合併辨識結果為單一筆名片資料（中英文欄位合併呈現），並維持既有的重複檢查與存檔流程不變。

## 使用者流程

1. 使用者傳送名片正面圖片。
2. Bot 執行既有 OCR（`generate_json_from_image`），解析成功後**不立即存檔**，改回覆：
   > 📇 已辨識正面資料，這張名片還有背面嗎？
   附 Quick Reply 兩顆按鈕（PostbackAction，比照現有 `confirm_update` 的 `data` 格式）：
   - `action=backside_confirm&has_backside=no`
   - `action=backside_confirm&has_backside=yes`
3. **選「沒有」**：直接走現有的「重複檢查 → 存檔 → 回傳 Flex」流程，清除 state。
4. **選「有背面」**：狀態轉為等待背面圖片，回覆「請傳送背面照片 📸」。
5. 使用者傳下一張圖片：
   - 若 pending 狀態仍有效（見下方逾時規則）→ 視為背面圖片，走「合併辨識」路徑。
   - 若已逾時或無 pending 狀態 → 視為全新名片，走原本單面流程（並清除舊 state）。
6. 使用者在等待背面圖片期間傳送**文字**而非圖片 → 比照現有文字查詢流程正常處理，同時清除 pending state（不強迫使用者一定要完成合併）。

## 狀態機（`user_states[user_id]`）

```python
# 步驟 2 之後
{
    'action': 'pending_backside_confirm',
    'card_obj': card_obj,             # 正面 OCR 結果
    'front_image_bytes': image_content,
    'expires_at': time.time() + 300,  # 5 分鐘逾時
}

# 使用者選「有背面」之後
{
    'action': 'awaiting_backside_image',
    'front_image_bytes': image_content,
    'expires_at': time.time() + 300,
}
```

逾時規則：任何 pending 狀態超過 5 分鐘未完成下一步，視為失效；下一次收到的圖片或文字一律當作全新事件處理，並清除舊 state。

## 合併辨識邏輯

新增 `gemini_utils.generate_json_from_two_images(front_img, back_img, prompt)`：

- 沿用既有 `NAMECARD_SCHEMA`（`response_schema` + `response_mime_type: application/json`）。
- 單次 `generate_content` 呼叫，`contents = [prompt, front_part, back_part]`（兩個 `Part.from_data`）。
- Prompt 在現有 `config.IMGAGE_PROMPT` 基礎上，追加合併指示：

  > 這兩張圖片是同一張名片的正面與背面，請整合成一筆完整資料。若同一欄位中英文都有出現（如姓名、公司），請合併呈現（例如「王大明 David Wang」）；若某欄位只有一面出現，直接採用該面的值；忽略明顯重複的資訊。

- 回傳結果同樣經過 `utils.parse_gemini_result_to_json` 解析成 `card_obj`。

## 存檔與重複檢查

正面單面流程與正反面合併流程，最終都收斂到同一段共用邏輯（重構為 `_finalize_and_save_card(card_obj, event, user_id)`）：

1. `firebase_utils.check_if_card_exists` 重複檢查。
2. 若重複 → 回傳既有卡片 Flex + 提示已存在。
3. 若不重複 → `firebase_utils.add_namecard` 存檔 → 回傳新卡片 Flex。

**重複檢查時機**：統一放在「最終資料底定之後」才做（不論單面或合併），不在正面辨識完就提前判斷重複，避免背面帶有更新資訊（如新 email）時被提早誤判成重複而漏採。

## 邊界情況處理

| 情況 | 處理方式 |
|---|---|
| 選「有背面」後逾時才傳圖 | 視為全新名片，走單面流程，清除舊 state |
| 選「有背面」後傳文字或不相關指令 | 照常處理文字流程，清除 pending state |
| 合併辨識解析失敗（回傳非合法 JSON） | 回覆現有的「無法解析這張名片」錯誤訊息，清除 state，使用者需重新開始 |
| 正面 OCR 完成後即與既有名片重複 | 不提前結束，仍詢問背面 → 合併（或選無背面）→ 最終資料才做重複檢查 |

## 涉及檔案

- `app/line_handlers.py`：`handle_image_event` 改為先問背面 → 新增 postback action `backside_confirm` 處理 → 抽出共用的 `_finalize_and_save_card`。
- `app/gemini_utils.py`：新增 `generate_json_from_two_images`。
- `app/config.py`：`IMGAGE_PROMPT` 旁新增合併用的 prompt 片段（或在呼叫端組合）。

## 測試計畫

- 單面：傳一張圖 → 選「沒有背面」→ 確認存檔內容與現有行為一致（不回歸）。
- 雙面合併：傳正面 → 選「有背面」→ 傳背面 → 確認合併後的 `card_obj` 欄位（中英文姓名/公司合併呈現）與最終存檔資料正確。
- 逾時：選「有背面」後等待超過設定逾時時間才傳圖 → 確認被當成全新名片處理，而非誤合併到舊 state。
- 中斷：選「有背面」後改傳文字查詢 → 確認文字查詢正常運作，且 state 已清除（後續再傳圖片不會被誤判為背面）。
- 合併辨識失敗：模擬 Gemini 回傳非合法 JSON → 確認錯誤訊息與 state 清除行為正確。
- 重複檢查時機：構造背面才帶有重複 email 的情境 → 確認最終仍正確判定為重複並回傳既有卡片。
