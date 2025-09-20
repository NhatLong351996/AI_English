from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("AZURE_OPENAI_API_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

client = AzureOpenAI(
    api_version="2024-07-01-preview",
    azure_endpoint=endpoint,
    api_key=api_key,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str

# --- Translate Topic Mode ---
class TranslateStartRequest(BaseModel):
    topic: str
    level: str
    prev_history: list = []
    paragraph: list = []  # Danh sách các câu song ngữ đã dịch (nếu có)

class TranslateNextRequest(BaseModel):
    topic: str
    level: str
    prev_history: list
    user_answer: str

class TranslateResponse(BaseModel):
    vi_sentence: str
    feedback: Optional[str] = None
import random

# Dữ liệu mẫu cho các chủ đề/mức độ
TRANSLATE_DATA = {
    'travel': {
        'easy': [
            'Tôi muốn đặt một phòng khách sạn.',
            'Bạn có thể chỉ đường đến sân bay không?',
            'Tôi thích đi du lịch bằng tàu hỏa.'
        ],
        'medium': [
            'Tôi đã từng bị lạc khi đi du lịch ở nước ngoài.',
            'Bạn có thể giới thiệu một nhà hàng địa phương nổi tiếng không?',
            'Tôi muốn trải nghiệm văn hóa bản địa khi đi du lịch.'
        ],
        'hard': [
            'Việc chuẩn bị hành lý kỹ càng giúp chuyến đi suôn sẻ hơn.',
            'Tôi muốn tìm hiểu về lịch sử và phong tục của nơi tôi đến.',
            'Bạn nghĩ điều gì là khó khăn nhất khi du lịch nước ngoài?' 
        ]
    },
    'school': {
        'easy': [
            'Tôi đi học bằng xe đạp.',
            'Môn học yêu thích của tôi là tiếng Anh.',
            'Tôi có nhiều bạn ở trường.'
        ],
        'medium': [
            'Tôi thường làm bài tập về nhà vào buổi tối.',
            'Giáo viên của tôi rất thân thiện và nhiệt tình.',
            'Tôi muốn tham gia câu lạc bộ tiếng Anh.'
        ],
        'hard': [
            'Việc học nhóm giúp tôi hiểu bài nhanh hơn.',
            'Tôi nghĩ rằng kỹ năng thuyết trình rất quan trọng trong học tập.',
            'Bạn có thể chia sẻ kinh nghiệm học tập hiệu quả không?'
        ]
    },
    # ... các chủ đề khác tương tự ...
}
@app.post("/translate/start", response_model=TranslateResponse)
async def translate_start(req: TranslateStartRequest):
    topic = req.topic
    level = req.level
    prev_history = req.prev_history if hasattr(req, 'prev_history') else []
    paragraph = req.paragraph if hasattr(req, 'paragraph') else []
    import time
    rand_seed = str(random.randint(1000,9999)) + '-' + str(int(time.time()*1000)%10000)
    history_text = '\n'.join(prev_history) if prev_history else ''
    # Nếu có đoạn song ngữ, đưa vào prompt để AI nối tiếp ngữ cảnh
    paragraph_text = ''
    if paragraph and isinstance(paragraph, list):
        for idx, pair in enumerate(paragraph, 1):
            vi = pair.get('vi', '')
            en = pair.get('en', '')
            if vi and en:
                paragraph_text += f"{idx}. Tiếng Việt: {vi}\n   Tiếng Anh: {en}\n"
            elif vi:
                paragraph_text += f"{idx}. Tiếng Việt: {vi}\n"
    system_prompt = (
        "Bạn là giáo viên tiếng Anh. Hãy tạo ra 1 câu tiếng Việt ngắn gọn, phù hợp để học sinh luyện dịch sang tiếng Anh. "
        f"Chủ đề: {topic}. Độ khó: {level}. Câu phải tự nhiên, không quá dài, không quá dễ nếu độ khó cao. "
        f"Không được lặp lại bất kỳ câu nào trong danh sách sau (nếu có): {history_text}. "
        f"Nếu có đoạn hội thoại hoặc đoạn văn trước đó, hãy nối tiếp mạch nội dung, đảm bảo ngữ cảnh liền mạch. "
        f"Đoạn trước đó (nếu có):\n{paragraph_text}"
        f"Chỉ trả về đúng 1 câu tiếng Việt, không giải thích, không thêm gì khác. (seed: {rand_seed})"
    )
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hãy cho tôi 1 câu tiếng Việt phù hợp."}
            ],
            max_tokens=60,
            temperature=1.0
        )
        vi_sentence = response.choices[0].message.content.strip()
        # Đảm bảo chỉ lấy 1 câu, không có giải thích
        if '.' in vi_sentence:
            vi_sentence = vi_sentence.split('.')[0].strip('.') + '.'
        return {"vi_sentence": vi_sentence}
    except Exception as e:
        # Nếu lỗi, fallback sang câu mẫu chưa xuất hiện
        vi_list = TRANSLATE_DATA.get(topic, {}).get(level, [])
        unused = [s for s in vi_list if s not in prev_history]
        vi_sentence = random.choice(unused) if unused else "(Không có dữ liệu cho chủ đề/mức độ này)"
        return {"vi_sentence": vi_sentence}

@app.post("/translate/next", response_model=TranslateResponse)
async def translate_next(req: TranslateNextRequest):
    import json
    topic = req.topic
    level = req.level
    prev_history = req.prev_history
    user_answer = req.user_answer
    vi_list = TRANSLATE_DATA.get(topic, {}).get(level, [])
    used = set(prev_history)
    next_candidates = [s for s in vi_list if s not in used]
    next_vi = random.choice(next_candidates) if next_candidates else "(Hết câu luyện tập)"
    system_prompt = (
        "Bạn là giáo viên tiếng Anh. Học sinh đang luyện dịch từng câu theo chủ đề. Hãy sửa câu tiếng Anh học sinh vừa trả lời, chấm điểm (thang 10), nhận xét rõ ràng, và gợi ý diễn đạt tự nhiên hơn. "
        "Đặc biệt, hãy giải thích rõ cấu trúc ngữ pháp và thì (tense) cần sử dụng trong câu, lý do vì sao lại sửa như vậy. "
        "Trả lời bằng JSON với 4 trường: user_answer (câu học sinh vừa trả lời), correct_answer (câu đúng), score (điểm, số hoặc chuỗi), explanation (nhận xét, giải thích, gợi ý tự nhiên, trình bày đẹp, có thể xuống dòng, dùng markdown hoặc HTML nếu cần. Đặc biệt, hãy giải thích rõ cấu trúc ngữ pháp và thì (tense) cần sử dụng trong câu, lý do vì sao lại sửa như vậy. ). Ví dụ: {\"user_answer\":..., \"correct_answer\":..., \"score\":..., \"explanation\":...}. Không thêm bất kỳ giải thích nào ngoài JSON."
    )
    feedback = ""
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Câu tiếng Việt: {prev_history[-1] if prev_history else ''}\nCâu tiếng Anh học sinh trả lời: {user_answer}"}
            ],
            max_tokens=400,
            temperature=0.2
        )
        feedback = response.choices[0].message.content
        print("[DEBUG] /translate/next feedback:", feedback)
    except Exception as e:
        feedback = f"[Error contacting Azure OpenAI: {e}]"
        print("[ERROR] /translate/next:", e)
    print("[DEBUG] /translate/next response:", {"vi_sentence": next_vi, "feedback": feedback})
    return {"vi_sentence": next_vi, "feedback": feedback}

class ChatResponse(BaseModel):
    reply: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(chat: ChatRequest):
    user_message = chat.message
    system_prompt = (
        "Bạn là giáo viên tiếng Anh. Hãy sửa câu tiếng Anh của học sinh, chấm điểm (thang 10), nhận xét từng ý rõ ràng (mỗi ý xuống dòng), và cuối cùng hãy gợi ý một cách diễn đạt hay hơn, tự nhiên hơn cho câu của học sinh. "
        "Trả lời bằng tiếng Việt. Ví dụ:"
        "\n- Câu đúng: ..."
        "\n- Điểm: ..."
        "\n- Nhận xét: ..."
        "\n- Giải thích: ..."
        "\n- Gợi ý diễn đạt tự nhiên hơn: ..."
    )
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=600,
            temperature=0.2
        )
        print("DEBUG reply:", response.choices[0].message.content)
        reply = response.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        import traceback
        print("ERROR:", e)
        traceback.print_exc()
        return {"reply": f"[Error contacting Azure OpenAI: {e}]"}
# --- Gợi ý từ vựng/cấu trúc cho câu tiếng Việt ---
from pydantic import BaseModel

class HintRequest(BaseModel):
    vi_sentence: str

class HintItem(BaseModel):
    word: str = None
    grammar: str = None
    vi: str = None
    info: str = None

@app.post("/translate/hint")
async def translate_hint(req: HintRequest):
    vi_sentence = req.vi_sentence.strip()
    if not vi_sentence:
        return {"hints": [{"info": "Không có câu để gợi ý."}]}
    # Prompt tối ưu: yêu cầu AI liệt kê từ vựng, cấu trúc ngữ pháp cần dùng để viết đúng câu tiếng Anh
    system_prompt = (
        "Bạn là giáo viên tiếng Anh. Hãy phân tích câu tiếng Việt sau và liệt kê các từ vựng quan trọng (word), cấu trúc ngữ pháp cần sử dụng (grammar) để viết đúng câu tiếng Anh tương ứng. "
        "Mỗi gợi ý là 1 object JSON với các trường: 'word' (từ/cụm từ), 'grammar' (cấu trúc), 'vi' (giải thích ngắn gọn bằng tiếng Việt). Nếu không có gợi ý đặc biệt, trả về mảng rỗng. Không giải thích thêm ngoài JSON."
    )
    user_prompt = f"Câu tiếng Việt: {vi_sentence}\nHãy trả về JSON array như hướng dẫn."
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        import json
        import re
        content = response.choices[0].message.content
        # Tìm đoạn JSON array trong content
        match = re.search(r'(\[.*\])', content, re.DOTALL)
        if match:
            arr = match.group(1)
            hints = json.loads(arr)
            if isinstance(hints, list) and hints:
                return {"hints": hints}
            else:
                return {"hints": []}
        # Nếu không có JSON array, thử parse từng dòng text
        lines = [l.strip('-•* \n') for l in content.split('\n') if l.strip()]
        parsed = []
        for line in lines:
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip().lower()
                val = val.strip()
                if key in ['từ vựng', 'từ', 'cụm từ', 'từ/cụm từ', 'word']:
                    parsed.append({"word": val, "vi": val})
                elif key in ['ngữ pháp', 'cấu trúc', 'grammar']:
                    parsed.append({"grammar": val, "vi": val})
                else:
                    parsed.append({"info": line})
            else:
                parsed.append({"info": line})
        if parsed:
            return {"hints": parsed}
        return {"hints": []}
    except Exception as e:
        return {"hints": [{"info": f"[Lỗi AI]: {e}"}]}
