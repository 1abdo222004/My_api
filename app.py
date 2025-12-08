from flask import Flask, request, jsonify
from nsfw_detector import predict
import requests
import os
import shutil # لإزالة المجلد بالكامل
from werkzeug.utils import secure_filename

# ==========================================================
# الإعدادات الأولية وتحميل النموذج
# ==========================================================

app = Flask(__name__)
MODEL_PATH = './nsfw_mobilenet2.224x224.h5'
TEMP_FOLDER = 'temp_downloaded_images' # اسم المجلد المؤقت

try:
    # تحميل النموذج مرة واحدة عند تشغيل التطبيق
    model = predict.load_model(MODEL_PATH)
    print(f"✅ تم تحميل النموذج بنجاح من: {MODEL_PATH}")
except Exception as e:
    print(f"❌ خطأ في تحميل النموذج: {e}")
    model = None


# ==========================================================
# الدالة المساعدة: لتنزيل الصورة من الرابط
# ==========================================================

def download_image_from_url(url, download_dir, index):
    """
    يقوم بتنزيل صورة من رابط URL إلى ملف مؤقت داخل مجلد محدد.
    """
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status() # رفع استثناء للأكواد 4xx/5xx

        # إنشاء اسم ملف فريد وآمن
        original_filename = secure_filename(os.path.basename(url) or f'temp_{index}.jpg')
        # نضيف Index لضمان عدم تكرار الأسماء
        filename = f"{index}_{original_filename}" 
        temp_path = os.path.join(download_dir, filename)

        # حفظ محتوى الصورة
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        
        return temp_path
    
    except requests.exceptions.RequestException as e:
        print(f"خطأ في تنزيل الرابط: {e}")
        return None
    except Exception as e:
        print(f"خطأ غير متوقع في التنزيل: {e}")
        return None

# ==========================================================
# نقطة النهاية (Endpoint) الرئيسية - تحليل الصور
# ==========================================================

@app.route('/predict', methods=['POST'])
def classify_nsfw():
    if model is None:
        return jsonify({"error": "Model failed to load."}), 503

    data = request.get_json()
    if not data or 'image_urls' not in data or not isinstance(data.get('image_urls'), list):
        return jsonify({"error": "الرجاء توفير قائمة 'image_urls' صالحة في طلب JSON."}), 400
    
    image_urls = data.get('image_urls', [])
    results = {}
    
    # 1. إنشاء المجلد المؤقت
    temp_dir_path = os.path.join(os.getcwd(), TEMP_FOLDER)
    os.makedirs(temp_dir_path, exist_ok=True)
    
    temp_paths = []

    try:
        # 2. تنزيل الصور وإعداد قائمة بمسارات الملفات المؤقتة
        for i, url in enumerate(image_urls):
            temp_path = download_image_from_url(url, temp_dir_path, i)
            if temp_path:
                temp_paths.append(temp_path)
            else:
                results[url] = {"error": "Failed to download image."}

        if not temp_paths:
             return jsonify({"error": "لم يتم تنزيل أي صور بنجاح للمعالجة."}), 422

        # 3. تصنيف الصور
        classification_results = predict.classify(model, temp_paths)
        
        # 4. دمج النتائج: نربط النتائج المصنفة مرة أخرى بالروابط الأصلية
        # يجب أن نستخدم ترتيب URL الأصلي هنا لتجنب المشاكل
        
        url_to_path_map = {path: url for url, path in zip(image_urls, temp_paths)}
        
        for file_path, classification in classification_results.items():
            # os.path.basename(file_path) هو اسم الملف في المجلد المؤقت
            file_key_in_results = os.path.basename(file_path)
            
            # نحتاج إلى البحث عن الرابط الأصلي الذي يطابق المسار
            original_url = None
            for path, url in url_to_path_map.items():
                if os.path.basename(path) == file_key_in_results:
                    original_url = url
                    break
            
            if original_url:
                results[original_url] = classification
            else:
                 # في حالة وجود خطأ غير متوقع في مطابقة المسارات
                 results[file_key_in_results] = {"error": "Classification successful, but failed to match to original URL."}
                 
    except Exception as main_e:
        print(f"حدث خطأ رئيسي أثناء التصنيف: {main_e}")
        return jsonify({"error": f"Internal server error during classification: {main_e}"}), 500
        
    finally:
        # 5. حذف المجلد المؤقت بالكامل
        try:
            if os.path.exists(temp_dir_path):
                shutil.rmtree(temp_dir_path)
                print(f"تم حذف المجلد المؤقت: {temp_dir_path}")
        except Exception as e:
            print(f"❌ فشل في حذف المجلد المؤقت: {e}")

    return jsonify(results)


if __name__ == '__main__':
    # تشغيل التطبيق
    app.run(debug=True, host='0.0.0.0', port=5000)
