---
name: shipnity-tracking
description: อ่านรายการออเดอร์จากเว็บ Shipnity (shipnity.com), จับคู่ใบเสร็จขนส่ง (รูปภาพ/PDF) กับออเดอร์ที่รอส่ง, และกรอกเลขพัสดุ (Tracking Number) หรือใส่แท็กออเดอร์อัตโนมัติ
---

# Shipnity Order & Tracking Skill

ใช้ Skill นี้เมื่อผู้ใช้ต้องการ:
1. ตรวจสอบหรืออ่านรายการออเดอร์จากระบบ **Shipnity** (`shipnity.com`)
2. ส่งไฟล์ **PDF หรือ รูปภาพใบเสร็จขนส่ง** (เช่น Flash Express, Thailand Post, Kerry/KEX, J&T ฯลฯ) เพื่อให้จับคู่และกรอกเลขพัสดุ (Tracking Number) ลงในออเดอร์ของ Shipnity
3. แก้ไขหรือเพิ่ม **แท็ก (Tag)** ของออเดอร์หรือของลูกค้าในระบบ Shipnity

---

## การตั้งค่า Environment Variable บน VPS
สคริปต์ใช้คุกกี้จากการล็อกอิน Shipnity โดยอ่านจากตัวแปร `SHIPNITY_COOKIE`:
```bash
export SHIPNITY_COOKIE="remember_user_token=<ค่าจากเบราว์เซอร์>; _shipnity_session=<ค่าจากเบราว์เซอร์>"
```
*(แนะนำให้ใส่ไว้ในไฟล์ `.env` ของ Hermes หรือ `~/.bashrc` บน VPS โดยคุกกี้ `remember_user_token` จะทำหน้าที่ต่ออายุ Session อัตโนมัติ)*

---

## คำสั่งเครื่องมือ (CLI Commands)

สคริปต์หลักอยู่ที่: `~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py`

### 1. ดึงรายการออเดอร์จาก Shipnity
* **ดึงเฉพาะออเดอร์ที่ "รอส่ง" (READY_TO_SHIP):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --status READY_TO_SHIP --limit 50
  ```
* **ดึงออเดอร์ทั้งหมด (ALL) หรือค้นหาจากชื่อ/เลขออเดอร์ (เช่น DN92):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --status ALL --search "DN92"
  ```

### 2. กรอกเลขพัสดุ (Tracking Number) ลงในออเดอร์
* **กรณีออเดอร์อยู่สถานะ "รอส่ง" และต้องการใส่เลขพัสดุพร้อมเปลี่ยนสถานะเป็น "ส่งแล้ว" (`--mode close`):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py set-tracking \
    --order-id "<ORDER_ID>" \
    --tracking "<TRACKING_NUMBER>" \
    --cost <SHIPPING_COST> \
    --mode close
  ```
  *(หมายเหตุ: `<ORDER_ID>` คือฟิลด์ `id` ที่ได้จากคำสั่ง `list` เช่น `136430164` ไม่ใช่ `invoiceNumber`)*
* **กรณีออเดอร์ปิดรายการไปแล้ว แต่ต้องการแก้ไขเฉพาะเลขพัสดุ (`--mode update`):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py set-tracking \
    --order-id "<ORDER_ID>" \
    --tracking "<TRACKING_NUMBER>" \
    --mode update
  ```

### 3. ใส่หรือแก้ไขแท็ก (Tag)
* **ใส่แท็กประจำออเดอร์ (`tag`):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py set-tag \
    --order-id "<ORDER_ID>" \
    --tag "<ข้อความแท็ก>"
  ```
* **ใส่แท็กประจำตัวลูกค้า (`customer.tags`):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py set-tag \
    --customer-id "<CUSTOMER_ID>" \
    --customer-tags "แท็ก1,แท็ก2"
  ```

---

## ขั้นตอนมาตรฐานเมื่อผู้ใช้ส่งไฟล์ PDF หรือ รูปภาพใบเสร็จขนส่งมาในแชท (Workflow)

1. **อ่านข้อมูลจากไฟล์ใบเสร็จ (Extract):**
   * หากเป็นไฟล์รูปภาพ: ใช้ความสามารถ Vision หรือ OCR อ่านรายชื่อผู้รับ, เบอร์โทรศัพท์, รหัสไปรษณีย์, ค่าส่ง (ถ้ามี) และ **เลขพัสดุ (Tracking Number)** ทุกบรรทัด
   * หากเป็นไฟล์ PDF: ใช้ `pdftotext` หรือ `python3 -c "import fitz; ..."` (PyMuPDF) หรือ `pdfplumber` เพื่อดึงข้อความทั้งหมดออกมา
2. **ดึงรายการออเดอร์ที่รอส่ง (Fetch Pending Orders):**
   * รันคำสั่ง `shipnity_tool.py list --status READY_TO_SHIP --limit 50` (หากไม่เจอใน `READY_TO_SHIP` ให้ลองดึง `--status ALL --limit 50`)
3. **จับคู่ข้อมูลอัจฉริยะ (Smart Matching):**
   * นำรายชื่อผู้รับ/เบอร์โทร/รหัสไปรษณีย์จากใบเสร็จ มาเทียบกับ `customer.name`, `customer.tel`, `customer.address` หรือ `invoiceNumber` ของออเดอร์ใน Shipnity
   * คำนึงถึงว่าชื่อในใบเสร็จอาจสะกดย่อหรือมีคำนำหน้าต่างกันเล็กน้อย (เช่น `"คุณสมชาย"` กับ `"สมชาย ใจดี"`) ให้ใช้เบอร์โทรหรือรหัสไปรษณีย์ใน `address` ช่วยยืนยันความถูกต้อง
4. **อัปเดตเลขพัสดุ (Update Tracking):**
   * สำหรับรายการที่จับคู่ได้ชัดเจน ให้รัน `shipnity_tool.py set-tracking` เพื่อบันทึกเลขพัสดุทันที (เช็คก่อนว่า `shippop` เป็น `false` เพราะถ้า `shippop: true` จะเป็นขนส่งในระบบที่แก้ไขเลขพัสดุไม่ได้)
   * สำหรับรายการที่ไม่แน่ใจ (เช่น ชื่อซ้ำกันหลายออเดอร์ หรือหาออเดอร์ไม่เจอ) **ห้ามเดาสุ่ม** ให้เว้นไว้แล้วถามผู้ใช้ในแชท
5. **สรุปผลตอบกลับผู้ใช้:**
   * แจ้งสรุปรายการที่อัปเดตสำเร็จ: `[เลขใบสั่งซื้อ] ชื่อลูกค้า -> เลขพัสดุ`
   * แจ้งรายการที่ตกหล่นหรือรอการยืนยันเพิ่มเติม (ถ้ามี)
