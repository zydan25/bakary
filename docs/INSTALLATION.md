# التثبيت والتشغيل — Bakary

هذا دليل التشغيل المستهدف. يجب تنفيذ الأوامر واختبار نتائجها على البيئة الفعلية قبل وصف النظام بأنه جاهز للإنتاج.

## المتطلبات

Python 3.10+، PostgreSQL، وPM2 للنشر. يلزم HTTPS لتثبيت PWA في الإنتاج.

## 1. إعداد PostgreSQL المحلي

افتح جلسة مسؤول PostgreSQL:

```sql
CREATE USER bakary WITH LOGIN;
\password bakary
CREATE DATABASE bakary OWNER bakary;
GRANT ALL PRIVILEGES ON DATABASE bakary TO bakary;
```

سيطلب الأمر `\password` إدخال كلمة مرور المستخدم وإعادة تأكيدها. استخدم كلمة المرور المحلية التي حددتها للمشروع، ولا تستخدم كلمة مرور التطوير نفسها على خادم مكشوف للإنترنت.

اختبر الاتصال:

```bash
psql "postgresql://bakary@127.0.0.1:5432/bakary" -c "SELECT 1;"
```

## 2. تجهيز Python

```bash
git clone https://github.com/zydan25/bakary.git
cd bakary
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

حرر `.env` واضبط `SECRET_KEY` على قيمة عشوائية طويلة وتحقق من أن `DATABASE_URL` يشير إلى قاعدة البيانات المحلية. لا ترفع `.env` إلى Git.

## 3. إعداد المخطط والبيانات الأولية

```bash
flask --app wsgi:app db upgrade
flask --app wsgi:app seed-roles
flask --app wsgi:app seed-defaults
flask --app wsgi:app create-admin
```

`seed-defaults` قابل لإعادة التنفيذ وينشئ صنف «روتي» الافتراضي والصندوق الرئيسي عند غيابهما. الأسعار الأولية تساوي صفرًا لأن الأسعار الفعلية لم تحدد؛ اضبطها قبل تنفيذ عمليات مالية. `create-admin` يطلب بيانات المدير بشكل تفاعلي، ويلزم بتغيير كلمة المرور بعد أول دخول.

## 4. الفحص والتشغيل المحلي

```bash
pytest
FLASK_CONFIG=development flask --app wsgi:app run --host 127.0.0.1 --port 4043
```

افتح `/health` للتحقق من صحة الخدمة واتصال قاعدة البيانات. اختبر الترحيلات على قاعدة اختبار فارغة؛ مجرد وجود ملفات migration لا يثبت نجاحها.

## 5. التشغيل عبر PM2

بعد تثبيت PM2 وضبط `.env`:

```bash
pm2 start ecosystem.config.cjs
pm2 save
pm2 status
pm2 logs bakary --lines 100
```

إعداد PM2 يستهدف Gunicorn على `127.0.0.1:4043`. بعد تحديث الكود:

```bash
git pull --ff-only origin main
source .venv/bin/activate
pip install -r requirements.txt
flask --app wsgi:app db upgrade
pm2 restart bakary --update-env
pm2 save
```

لا تنشئ القاعدة أكثر من مرة، وخذ نسخة احتياطية قبل الترحيل على بيانات فعلية.

## حدود المرحلة الحالية

- خدمة استعادة كلمة المرور عبر SMS/OTP غير مفعلة؛ صفحة الاستعادة لا ترسل رمزًا. يمكن للمدير استخدام أمر `flask --app wsgi:app reset-password` لإعادة التعيين يدويًا.
- ملفات PWA موجودة، لكنها تحتاج اختبار التثبيت والتحديث وسلوك الانقطاع على أجهزة الهاتف وبيئة HTTPS.
- لا تسجل أي عملية مالية نهائيًا قبل تأكيد الخادم حفظها.

**التوقيع:** برمجة وتصميم م. زيدان العطاب — 774952665 — يمن كود للتقنيات الذكية.
