import telebot
from nudenet import NudeDetector
import os

# =======================
# إعدادات البوت
# =======================
API_TOKEN = "7198993899:AAFS9_BRQvrQNCiphd8CuwZouPjL5DPzfOQ"  # ضع توكن بوتك هنا
bot = telebot.TeleBot(API_TOKEN)

# تهيئة كاشف الصور
detector = NudeDetector()

# =======================
# رسالة الترحيب
# =======================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحبا! أرسل لي صورة وسأكشف لك إذا كانت تحتوي على محتوى غير لائق.")

# =======================
# استقبال الصور
# =======================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        # الحصول على ملف الصورة الأعلى جودة
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # حفظ الصورة مؤقتًا
        img_path = f"temp_{message.chat.id}.jpg"
        with open(img_path, 'wb') as f:
            f.write(downloaded_file)

        # كشف محتوى NSFW
        result = detector.detect(img_path)

        # إرسال النتيجة للمستخدم
        bot.reply_to(message, f"نتيجة الكشف:\n{result}")

        # حذف الصورة بعد الكشف
        os.remove(img_path)

    except Exception as e:
        bot.reply_to(message, f"حدث خطأ: {e}")

# =======================
# بدء البوت
# =======================
print("البوت جاهز للعمل...")
bot.polling(none_stop=True)
