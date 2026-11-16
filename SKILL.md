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

## การตั้งค่าการยืนยันตัวตนบน VPS (เลือกได้ 2 วิธี)

### วิธีที่ 1: ใช้ Cookie จากเบราว์เซอร์ (`SHIPNITY_COOKIE`)
```bash
export SHIPNITY_COOKIE="remember_user_token=<ค่าจากเบราว์เซอร์>; _shipnity_session=<ค่าจากเบราว์เซอร์>"
```

### วิธีที่ 2: ใช้ Email และ Password (`SHIPNITY_EMAIL` + `SHIPNITY_PASSWORD`)
สคริปต์รองรับการล็อกอินผ่าน GraphQL `signInUser` อัตโนมัติหากตั้งค่า:
```bash
export SHIPNITY_EMAIL="your_email@example.com"
export SHIPNITY_PASSWORD="your_password"
```

---

## คำสั่งเครื่องมือ (CLI Commands)

สคริปต์หลักอยู่ที่: `~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py`

### 1. ดึงรายการออเดอร์จาก Shipnity (`orderList`)
* **ดึงออเดอร์ล่าสุดทั้งหมด (50 รายการแรก):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --status ALL --limit 50
  ```
* **ดึงเฉพาะออเดอร์ที่ยังไม่ปิดรายการ / รอส่ง (`READY_TO_SHIP`):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --status READY_TO_SHIP --limit 50
  ```
* **ค้นหาออเดอร์จากเลขใบสั่งซื้อ ชื่อลูกค้า หรือเบอร์โทร (เช่น `DN92`):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --search "DN92"
  ```
* **ดึงออเดอร์ตาม Internal Order ID (เช่น `136430164`):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --id "136430164"
  ```

### 2. กรอกเลขพัสดุ (Tracking Number) ลงในออเดอร์ (`closedNote`)
* **กรณีออเดอร์อยู่สถานะ "รอส่ง" และต้องการใส่เลขพัสดุพร้อมเปลี่ยนสถานะเป็น "ส่งแล้ว" (`--mode close`):**
  ```bash
  python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py set-tracking \
    --order-id "<ORDER_ID>" \
    --tracking "<TRACKING_NUMBER>" \
    --cost <SHIPPING_COST> \
    --mode close
  ```
  *(หมายเหตุ: `<ORDER_ID>` คือฟิลด์ `id` ที่ได้จากคำสั่ง `list` เช่น `136430164` ไม่ใช่ `invoiceNumber`)*
* **กรณีออเดอร์ปิดรายการไปแล้ว (`status: "CLOSE"`) แต่ต้องการเพิ่มหรือแก้ไขเฉพาะเลขพัสดุ (`--mode update`):**
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
2. **ดึงรายการออเดอร์จาก Shipnity:**
   * รันคำสั่ง `shipnity_tool.py list --status ALL --limit 50` (หรือใช้ `--search "<ชื่อหรือเบอร์โทร>"` หากต้องการค้นหาเฉพาะเจาะจง)
3. **จับคู่ข้อมูลอัจฉริยะ (Smart Matching):**
   * นำรายชื่อผู้รับ/เบอร์โทร/รหัสไปรษณีย์จากใบเสร็จ มาเทียบกับ `name`, `tel`, `address`, `customer.name` หรือ `invoiceNumber` ของออเดอร์ใน Shipnity
   * คำนึงถึงว่าชื่อในใบเสร็จอาจสะกดย่อหรือมีคำนำหน้าต่างกันเล็กน้อย ให้ใช้เบอร์โทรหรือรหัสไปรษณีย์ใน `address` ช่วยยืนยันความถูกต้อง
4. **อัปเดตเลขพัสดุ (Update Tracking):**
   * ถ้ารายการนั้นยังไม่ปิดออเดอร์ (`closed: false`) ให้ใช้ `--mode close`
   * ถ้ารายการนั้นปิดออเดอร์ไปแล้ว (`closed: true` / `status: "CLOSE"`) ให้ใช้ `--mode update`
   * เช็คก่อนว่า `shippop` เป็น `false` (เพราะถ้า `shippop: true` จะเป็นขนส่งในระบบที่แก้ไขเลขพัสดุไม่ได้)
   * สำหรับรายการที่ไม่แน่ใจ (เช่น ชื่อซ้ำกันหลายออเดอร์ หรือหาออเดอร์ไม่เจอ) **ห้ามเดาสุ่ม** ให้เว้นไว้แล้วถามผู้ใช้ในแชท
5. **สรุปผลตอบกลับผู้ใช้:**
   * แจ้งสรุปรายการที่อัปเดตสำเร็จ: `[เลขใบสั่งซื้อ] ชื่อลูกค้า -> เลขพัสดุ`
   * แจ้งรายการที่ตกหล่นหรือรอการยืนยันเพิ่มเติม (ถ้ามี)
