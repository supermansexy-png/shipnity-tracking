# Shipnity Tracking Skill for Hermes Agent

Skill และ CLI Tool สำหรับให้ **Hermes Agent** เชื่อมต่อกับระบบหลังบ้านของ **Shipnity** (`shipnity.com`) ผ่าน GraphQL API เพื่อ:
1. ดึงรายการออเดอร์ที่รอส่ง (`READY_TO_SHIP`) หรือค้นหาออเดอร์ทั้งหมด
2. รับไฟล์ **รูปภาพใบเสร็จขนส่ง** หรือ **PDF** จากแชท (เช่น LINE Bot) แล้วจับคู่ชื่อผู้รับ/เบอร์โทร/รหัสไปรษณีย์กับออเดอร์ใน Shipnity
3. กรอกเลขพัสดุ (`closedNote`) ปิดออเดอร์เป็นสถานะจัดส่งแล้ว (`closeOrder`) หรืออัปเดตแท็ก (`updateOrder` / `updateCustomer`) อัตโนมัติ

---

## วิธีติดตั้งลงใน Hermes Agent บน VPS

รันคำสั่งนี้บน VPS เพื่อติดตั้งเข้าโฟลเดอร์ Skill ของ Hermes โดยตรง:

```bash
mkdir -p ~/.hermes/skills
git clone https://github.com/supermansexy-png/shipnity-tracking.git ~/.hermes/skills/shipnity-tracking
chmod +x ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py
```

หรือใช้คำสั่งติดตั้ง Skill ของ Hermes:
```bash
hermes skills install supermansexy-png/shipnity-tracking
```

---

## การตั้งค่า Cookie (`SHIPNITY_COOKIE`)

ใส่ค่า Cookie จากการล็อกอินเว็บ `https://www.shipnity.com` ไว้ใน `.env` ของ Hermes หรือ `~/.bashrc` บน VPS:

```bash
export SHIPNITY_COOKIE="remember_user_token=<ค่าจากเบราว์เซอร์>; _shipnity_session=<ค่าจากเบราว์เซอร์>"
```

---

## ทดสอบใช้งาน

```bash
# ดึงรายการออเดอร์ที่รอส่ง
python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py list --status READY_TO_SHIP --limit 20

# กรอกเลขพัสดุและปิดออเดอร์เป็นส่งแล้ว
python3 ~/.hermes/skills/shipnity-tracking/scripts/shipnity_tool.py set-tracking \
  --order-id "136430164" \
  --tracking "TH0123456789A" \
  --cost 35 \
  --mode close
```
