# Shipnity Tracking Skill for Hermes Agent

Skill และ CLI Tool สำหรับให้ **Hermes Agent** เชื่อมต่อกับระบบหลังบ้านของ **Shipnity** (`shipnity.com`) ผ่าน GraphQL API (ผ่านการทดสอบกับ Schema จริงแล้ว) เพื่อ:
1. ดึงรายการออเดอร์ทั้งหมด, ออเดอร์ที่รอส่ง (`READY_TO_SHIP`) หรือค้นหาออเดอร์ตามเลขใบสั่งซื้อ (เช่น `DN92`)
2. รับไฟล์ **รูปภาพใบเสร็จขนส่ง** หรือ **PDF** จากแชท (เช่น LINE Bot) แล้วจับคู่ชื่อผู้รับ/เบอร์โทร/รหัสไปรษณีย์กับออเดอร์ใน Shipnity
3. กรอกเลขพัสดุ (`closedNote`) ปิดออเดอร์เป็นสถานะจัดส่งแล้ว (`closeOrder`) หรืออัปเดตแท็ก (`updateOrder` / `updateCustomer`) อัตโนมัติ

---

## วิธีติดตั้งหรืออัปเดตลงใน Hermes Agent บน VPS

หากติดตั้งครั้งแรก:
```bash
mkdir -p ~/.hermes/skills
git clone https://github.com/supermansexy-png/shipnity-tracking.git ~/.hermes/skills/shipnity-tracking
chmod +x ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py
```

หากเคย clone ไปแล้ว ให้ดึงโค้ดเวอร์ชันล่าสุด:
```bash
cd ~/.hermes/skills/shipnity-tracking && git pull origin main
```

---

## การตั้งค่าการยืนยันตัวตน (เลือกวิธีใดวิธีหนึ่ง)

### วิธีที่ 1: ใช้ Cookie (`SHIPNITY_COOKIE`)
```bash
export SHIPNITY_COOKIE="remember_user_token=<ค่าจากเบราว์เซอร์>; _shipnity_session=<ค่าจากเบราว์เซอร์>"
```

### วิธีที่ 2: ใช้ Email และ Password (`SHIPNITY_EMAIL` + `SHIPNITY_PASSWORD`)
```bash
export SHIPNITY_EMAIL="your_email@example.com"
export SHIPNITY_PASSWORD="your_password"
```

---

## ทดสอบใช้งาน

```bash
# ค้นหาออเดอร์ DN92
python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --search "DN92"

# ดึงรายการออเดอร์ที่รอส่ง
python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --status READY_TO_SHIP --limit 20

# กรอกเลขพัสดุและปิดออเดอร์เป็นส่งแล้ว
python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py set-tracking \
  --order-id "136430164" \
  --tracking "TH0123456789A" \
  --cost 35 \
  --mode close
```
