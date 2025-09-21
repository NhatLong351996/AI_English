# English Practice AI Web App

## Mô tả
Ứng dụng web luyện tập tiếng Anh với các tính năng:
- Luyện dịch, sửa ngữ pháp, quiz (từ vựng, ngữ pháp, đọc hiểu)
- Sinh câu hỏi, đoạn đọc, dịch tự động bằng AI (Azure OpenAI)
- Hiển thị kết quả, giải thích, dịch tiếng Việt cho từng câu hỏi

## Yêu cầu hệ thống
- Python 3.8+
- Node.js (nếu muốn phát triển frontend nâng cao)
- Tài khoản Azure OpenAI (hoặc sửa lại backend để dùng OpenAI thường)

## Cài đặt
1. **Clone repo**

```bash
git clone <repo-url>
cd AI_English
```

2. **Cài đặt Python packages**

```bash
pip install -r requirements.txt
```

3. **Cấu hình Azure OpenAI**
- Tạo file `.env` hoặc sửa trực tiếp biến môi trường trong `main.py`:
  - `AZURE_OPENAI_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_DEPLOYMENT`

4. **Chạy backend (FastAPI)**

```bash
uvicorn main:app --reload
```

5. **Mở frontend**
- Mở file `index.html` trong trình duyệt (double click hoặc dùng Live Server extension của VS Code)
- Đảm bảo backend chạy ở `http://127.0.0.1:8000`

## Sử dụng
- Chọn chức năng: Luyện dịch, Quiz, Sửa ngữ pháp
- Làm bài, xem kết quả, giải thích và bản dịch tiếng Việt cho từng câu hỏi

## Ghi chú
- Nếu dùng OpenAI thường, cần sửa lại phần gọi API trong `main.py`
- Nếu gặp lỗi dịch hoặc quiz, kiểm tra lại cấu hình API key và endpoint

## Liên hệ
- Tác giả: NhatLong351996
- Email: <your-email@example.com>
