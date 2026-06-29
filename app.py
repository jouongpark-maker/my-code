from flask import Flask, render_template, request, send_file
from docx import Document
from PIL import Image, ImageDraw, ImageFont
import os
import zipfile
import io

app = Flask(__name__)

# تنظیم مسیرها برای ذخیره موقت فایل‌ها
UPLOAD_FOLDER = 'tmp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def process_novel_to_images(word_path, bg_path, font_path, vol_num, ch_num):
    # ۱. خواندن متن از فایل ورد بدون نیاز به نرم‌افزار آفیس
    doc = Document(word_path)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    
    # ۲. باز کردن عکس پس‌زمینه اصلی
    bg_image = Image.open(bg_path)
    img_w, img_h = bg_image.size
    
    # تنظیمات فونت و ابعاد کادر متنی (باید بر اساس کادر مشکی بک‌گراند تنظیم شود)
    font_size = 28
    font = ImageFont.truetype(font_path, font_size)
    
    # حاشیه‌ها (تخمین برای اینکه متن روی لبه‌های اسلیمی سفید نرود)
    margin_left = int(img_w * 0.1)
    margin_right = int(img_w * 0.1)
    margin_top = int(img_h * 0.15)
    margin_bottom = int(img_h * 0.1)
    max_width = img_w - margin_left - margin_right
    max_height = img_h - margin_top - margin_bottom

    # منطق تقسیم‌بندی متن به صفحات مختلف
    pages_data = []
    current_page_text = []
    current_height = 0
    
    # شبیه‌سازی تراز و شکستن خطوط برای متن فارسی
    for paragraph in full_text:
        words = paragraph.split(' ')
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            # محاسبه اندازه خط متنی
            bbox = font.getbbox(test_line)
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1] + 15  # اضافه کردن فاصله خطوط
            
            if line_w <= max_width:
                current_line = test_line
            else:
                current_page_text.append(current_line)
                current_height += line_h
                current_line = word
                
                if current_height >= max_height:
                    pages_data.append(current_page_text)
                    current_page_text = []
                    current_height = 0
        
        if current_line:
            current_page_text.append(current_line)
            current_height += 35 # فاصله بین پاراگراف‌ها
            
        if current_height >= max_height:
            pages_data.append(current_page_text)
            current_page_text = []
            current_height = 0

    if current_page_text:
        pages_data.append(current_page_text)

    # ایجاد فایل ZIP در حافظه موقت برای ارسال به گوشی
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        padding = len(str(len(pages_data)))
        
        for idx, page_lines in enumerate(pages_data):
            page_img = bg_image.copy()
            draw = ImageDraw.Draw(page_img)
            
            # نوشتن شماره چپتر/صفحه در بالای بک‌گراند
            header_text = f"Ch {ch_num} - Page {idx+1}"
            draw.text((img_w//2, margin_top - 50), header_text, font=font, fill="#ffd700", anchor="mm")
            
            # نوشتن متن رمان روی بوم گرافیکی
            y_offset = margin_top
            for line in page_lines:
                # رندر راست به چین متن فارسی
                draw.text((img_w - margin_right, y_offset), line, font=font, fill="#ffffff", anchor="ra")
                bbox = font.getbbox(line)
                y_offset += (bbox[3] - bbox[1] + 15)
            
            # تبدیل صفحه به فرمت مانهوایی WEBP با کیفیت تمیز
            img_byte_arr = io.BytesIO()
            page_img.save(img_byte_arr, format='WEBP', quality=85)
            img_byte_arr.seek(0)
            
            image_filename = f"{idx + 1:0{padding}d}.webp"
            zipf.writestr(image_filename, img_byte_arr.read())
            
    zip_buffer.seek(0)
    return zip_buffer

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        word_file = request.files['word']
        bg_file = request.files['background']
        vol = request.form.get('volume', '1')
        ch = request.form.get('chapter', '1')
        
        word_path = os.path.join(UPLOAD_FOLDER, word_file.filename)
        bg_path = os.path.join(UPLOAD_FOLDER, bg_file.filename)
        font_path = "B_Yekan.ttf" # فونت دلخواه شما که روی سرور آپلود شده
        
        word_file.save(word_path)
        bg_file.save(bg_path)
        
        # اجرای فرآیند تبدیل و ساخت زیپ تصاویری
        zip_output = process_novel_to_images(word_path, bg_path, font_path, vol, ch)
        
        # ارسال مستقیم فایل زیپ نهایی به مرورگر گوشی
        return send_file(
            zip_output,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"Novel_Vol{vol}_Ch{ch}.zip"
        )
        
    return '''
    <!doctype html>
    <title>تایپوگرافی هوشمند ناول موبایل</title>
    <style>
        body { background: #282c34; color: white; font-family: Tahoma; text-align: center; padding: 50px; }
        form { background: #3a3f4b; padding: 30px; display: inline-block; border-radius: 10px; }
        input, button { display: block; margin: 15px auto; padding: 10px; width: 80%; border-radius: 5px; border: none; }
        button { background: #ffd700; color: #282c34; font-weight: bold; cursor: pointer; }
    </style>
    <form method=post enctype=multipart/form-file>
      <h3>تنظیم چیدمان و تبدیل مانهوایی ناول</h3>
      <label>فایل ورد (.docx):</label><input type=file name=word>
      <label>عکس پس‌زمینه با واترمرک:</label><input type=file name=background>
      <input type=text name=volume placeholder="شماره ولوم">
      <input type=text name=chapter placeholder="شماره چپتر">
      <button type=submit>بزن بریم و خروجی ZIP بگیر!</button>
    </form>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
