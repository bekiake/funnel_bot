# funnel_bot

## Loyihaning qisqacha tavsifi

`funnel_bot` — bu Telegram bot uchun mo‘ljallangan Python asosidagi loyiha. Bot foydalanuvchilarni turli funnel (savdo, o‘quv va boshqalar) jarayonlari orqali boshqaradi, ma’lumotlar bazasi bilan ishlaydi va bir nechta yordamchi modullarga ega.

## O‘rnatish

1. Python 3.12 yoki undan yuqori versiyasini o‘rnating.
2. Zarur kutubxonalarni o‘rnatish uchun quyidagi buyruqni bajaring:
	```powershell
	pip install -r requirements.txt
	```

## Ishga tushirish

Botni ishga tushirish uchun quyidagilarni bajaring:
```powershell
python app.py
```

## Loyihaning tuzilmasi

- `app.py` — asosiy bot fayli.
- `common/` — umumiy buyruqlar va yordamchi funksiyalar.
- `database/` — ma’lumotlar bazasi bilan ishlash uchun modullar.
- `filters/` — chat turlari va filtrlar.
- `funnels/` — funnel konfiguratsiyalari (json fayllar).
- `handlers/` — bot handlerlari (admin va user uchun).
- `kbds/` — klaviatura (inline va reply) modullari.
- `middlewares/` — oraliq modullar (masalan, db).
- `services/` — asosiy servislar (funnel logikasi).

## Foydalanish

Botni Telegramda ishga tushirish uchun token va kerakli sozlamalarni `app.py` yoki konfiguratsiya fayllariga joylashtiring.
