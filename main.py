from typing import Optional, List
from fastapi import FastAPI, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import AzureOpenAI

from dotenv import load_dotenv
from pathlib import Path
dotenv_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path)

# Hardcode Azure OpenAI credentials (for environments where .env is not read)
api_key = "sk-ups5H5N5hbV0SZ4M0OnGuA"
endpoint = "https://aiportalapi.stu-platform.live/jpe"
deployment_name = "GPT-4o-mini"

client = AzureOpenAI(
    api_version="2024-07-01-preview",
    azure_endpoint=endpoint,
    api_key=api_key,
)

app = FastAPI()

# Mount static directory for frontend
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
@app.get("/")
async def root():
    # Serve the main frontend file
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    # fallback: if not found, show error
    return {"error": "index.html not found in static/"}

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

# Simple word translation endpoint for hover tooltips
class SimpleTranslateRequest(BaseModel):
    text: str
    topic: str = "vocabulary"
    level: str = "basic"

class TranslateHint(BaseModel):
    word: str
    meaning: str
    pronunciation: str = ""
    type: str = "vocabulary"

class SimpleTranslateResponse(BaseModel):
    hints: List[TranslateHint]

@app.post("/translate", response_model=SimpleTranslateResponse)
async def translate_word(req: SimpleTranslateRequest):
    """
    Endpoint đơn giản để dịch từ cho hover tooltip
    """
    import traceback
    word = req.text.strip().lower()
    
    try:
        print(f"[DEBUG] /translate request for word: '{word}', topic: {req.topic}, level: {req.level}")
        
        # Validate input
        if not word or len(word) == 0:
            print("[ERROR] /translate empty word")
            return {"hints": []}
        
        # Simple word translation using AI
        system_prompt = (
            f"Bạn là từ điển tiếng Anh - Việt chuyên nghiệp. Hãy dịch từ '{word}' sang tiếng Việt.\n"
            "Yêu cầu:\n"
            "- Trả về nghĩa chính xác nhất, phổ biến nhất\n"
            "- Nghĩa phải ngắn gọn (1-4 từ), dễ hiểu\n"
            "- Chỉ trả về nghĩa tiếng Việt, không giải thích thêm\n"
            "- Nếu là từ rất cơ bản (a, an, the, is, are...) thì trả về nghĩa đơn giản nhất"
        )
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Dịch từ: {word}"}
            ],
            max_tokens=50,
            temperature=0.1  # Giảm temperature để ổn định hơn
        )
        
        meaning = response.choices[0].message.content.strip()
        print(f"[DEBUG] /translate AI response for '{word}': {meaning}")
        
        # Clean up the meaning
        if meaning.startswith('"') and meaning.endswith('"'):
            meaning = meaning[1:-1]
        
        # Create response
        hints = [TranslateHint(
            word=word,
            meaning=meaning or word,  # Fallback to original word if empty
            pronunciation="",
            type="vocabulary"
        )]
        
        return {"hints": hints}
        
    except Exception as e:
        print(f"[ERROR] /translate error for word '{word}': {e}")
        traceback.print_exc()
        # Fallback response
        return {"hints": [TranslateHint(
            word=word,
            meaning=word,  # Show original word as fallback
            pronunciation="",
            type="vocabulary"
        )]}

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
    pronunciation: str = None  # Thêm phiên âm
    pos: str = None  # Thêm từ loại (part of speech)

@app.post("/translate/hint")
async def translate_hint(req: HintRequest):
    vi_sentence = req.vi_sentence.strip()
    if not vi_sentence:
        return {"hints": [{"info": "Không có câu để gợi ý."}]}
    # Prompt tối ưu: yêu cầu AI liệt kê từ vựng, cấu trúc ngữ pháp cần dùng để viết đúng câu tiếng Anh
    system_prompt = (
        "Bạn là giáo viên tiếng Anh. Hãy phân tích câu tiếng Việt sau và liệt kê các từ vựng tiếng Anh quan trọng (word), cấu trúc ngữ pháp tiếng Anh cần sử dụng (grammar) để viết đúng câu tiếng Anh tương ứng. "
        "Mỗi gợi ý là 1 object JSON với các trường: 'word' (từ/cụm từ TIẾNG ANH), 'pos' (từ loại viết tắt: n, v, adj, adv, prep, conj, etc.), 'pronunciation' (phiên âm IPA), 'grammar' (cấu trúc TIẾNG ANH), 'vi' (giải thích ngắn gọn bằng tiếng Việt). "
        "Ví dụ: [{\"word\": \"dolphin\", \"pos\": \"n\", \"pronunciation\": \"/ˈdɒlfɪn/\", \"vi\": \"cá heo\"}, {\"word\": \"intelligent\", \"pos\": \"adj\", \"pronunciation\": \"/ɪnˈtelɪdʒənt/\", \"vi\": \"thông minh\"}, {\"grammar\": \"be + adjective\", \"vi\": \"cấu trúc tính từ\"}]. "
        "Nếu không có gợi ý đặc biệt, trả về mảng rỗng. Chỉ trả về JSON array, không giải thích thêm."
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
                    # Tìm từ tiếng Anh trong val
                    english_word = val.split('(')[0].strip() if '(' in val else val
                    parsed.append({"word": english_word, "vi": f"từ vựng: {val}"})
                elif key in ['ngữ pháp', 'cấu trúc', 'grammar']:
                    # Tìm cấu trúc tiếng Anh trong val
                    english_grammar = val.split('(')[0].strip() if '(' in val else val
                    parsed.append({"grammar": english_grammar, "vi": f"cấu trúc: {val}"})
                else:
                    parsed.append({"info": line})
            else:
                parsed.append({"info": line})
        if parsed:
            return {"hints": parsed}
        return {"hints": []}
    except Exception as e:
        return {"hints": [{"info": f"[Lỗi AI]: {e}"}]}

# --- Quiz API ---
class QuizStartRequest(BaseModel):
    topic: str
    level: str
    num_questions: int = 5
    passage: str = None  # Thêm trường passage cho reading

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    answer: int  # index của đáp án đúng
    explain: str = ""
    evidence: str = None  # Câu hoặc đoạn liên quan trong passage

class QuizStartResponse(BaseModel):
    questions: List[QuizQuestion]

# Dữ liệu quiz mẫu
QUIZ_DATA = {
    'grammar': {
        'easy': [
            {
                'question': 'Chọn đáp án đúng: She ___ to school every day.',
                'options': ['go', 'goes', 'going', 'gone'],
                'answer': 1,
                'explain': '"She" là ngôi số 3 số ít, động từ thêm -es.'
            },
            {
                'question': 'Chọn đáp án đúng: They ___ football on Sundays.',
                'options': ['play', 'plays', 'playing', 'played'],
                'answer': 0,
                'explain': '"They" là số nhiều, dùng động từ nguyên mẫu.'
            },
        ],
        'medium': [
            {
                'question': 'Chọn đáp án đúng: If I ___ time, I will help you.',
                'options': ['have', 'has', 'had', 'having'],
                'answer': 0,
                'explain': 'Câu điều kiện loại 1: If + S + V (hiện tại đơn), ... will + V.'
            },
        ],
        'hard': [
            {
                'question': 'Chọn đáp án đúng: The book ___ by my friend yesterday.',
                'options': ['is given', 'was given', 'gave', 'has given'],
                'answer': 1,
                'explain': 'Câu bị động thì quá khứ đơn: was/were + V3.'
            },
        ]
    },
    'vocabulary': {
        'easy': [
            {
                'question': 'Từ nào sau đây là tên một loại trái cây?',
                'options': ['apple', 'table', 'car', 'house'],
                'answer': 0,
                'explain': 'Apple là quả táo.'
            },
        ],
        'medium': [],
        'hard': []
    },
    'reading': {
        'easy': [],
        'medium': [],
        'hard': []
    }
}

@app.post("/quiz/start", response_model=QuizStartResponse)
async def quiz_start(req: QuizStartRequest = Body(...)):
    topic = req.topic
    level = req.level
    num = req.num_questions
    passage = getattr(req, 'passage', None)
    pool = QUIZ_DATA.get(topic, {}).get(level, [])
    import random
    if pool and len(pool) >= num:
        questions = random.sample(pool, min(num, len(pool)))
        return {"questions": questions}
    # Nếu không đủ câu hỏi mẫu, dùng AI sinh quiz
    if topic == "reading" and passage:
        system_prompt = (
            f"Bạn là giáo viên luyện thi IELTS. Dưới đây là một đoạn đọc hiểu tiếng Anh (Reading passage):\n{passage}\n"
            f"Hãy tạo ra {num} câu hỏi trắc nghiệm tiếng Anh theo phong cách đề thi IELTS (dạng Multiple Choice), sát với nội dung đoạn văn trên, cấu trúc và độ khó của đề thi IELTS thực tế. "
            "Mỗi câu hỏi phải kiểm tra khả năng đọc hiểu, nắm ý chính, chi tiết, suy luận hoặc từ vựng trong đoạn văn. "
            "Mỗi câu hỏi gồm: question (nội dung), options (4 đáp án), answer (chỉ số đáp án đúng, bắt đầu từ 0), explain (giải thích ngắn gọn bằng tiếng Việt, nêu lý do chọn đáp án đúng, giải thích bẫy nếu có), evidence (chỉ rõ câu hoặc đoạn trong passage liên quan trực tiếp đến đáp án đúng, chỉ trả về đúng 1 câu hoặc đoạn ngắn nhất có thể, không lặp lại toàn bộ passage). "
            "Trả về một mảng JSON các object như sau: {question, options, answer, explain, evidence}. Không giải thích gì ngoài JSON."
        )
    else:
        system_prompt = (
            f"Bạn là giáo viên luyện thi IELTS. Hãy tạo ra {num} câu hỏi trắc nghiệm tiếng Anh theo phong cách đề thi IELTS (dạng Multiple Choice), sát với nội dung, cấu trúc, và độ khó của đề thi IELTS thực tế. "
            f"Chủ đề: {topic}. "
            f"Yêu cầu: Độ khó, từ vựng, cấu trúc ngữ pháp, chủ đề và cách diễn đạt của từng câu hỏi phải tương ứng với band điểm IELTS {level}. "
            "Mỗi câu hỏi nên có ngữ cảnh ngắn gọn (nếu cần), nội dung sát với đề thi IELTS (đặc biệt Reading/Listening). "
            "Mỗi câu hỏi gồm: question (nội dung), options (4 đáp án), answer (chỉ số đáp án đúng, bắt đầu từ 0), explain (giải thích ngắn gọn bằng tiếng Việt, nêu lý do chọn đáp án đúng, giải thích bẫy nếu có). "
            "Trả về một mảng JSON các object như sau: {question, options, answer, explain}. Không giải thích gì ngoài JSON."
        )
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Hãy sinh {num} câu hỏi quiz. Giải thích (explain) phải bằng tiếng Việt."}
            ],
            max_tokens=1200,
            temperature=0.7
        )
        import json, re
        content = response.choices[0].message.content
        # Tìm đoạn JSON array trong content
        match = re.search(r'(\[.*\])', content, re.DOTALL)
        if match:
            arr = match.group(1)
            questions = json.loads(arr)
            # Đảm bảo đúng định dạng QuizQuestion
            for q in questions:
                if 'answer' in q and isinstance(q['answer'], str) and q['answer'].isdigit():
                    q['answer'] = int(q['answer'])
            return {"questions": questions}
        return {"questions": []}
    except Exception as e:
        return {"questions": []}
# --- Reading Passage API ---
class ReadingPassageRequest(BaseModel):
    level: str

class ReadingPassageResponse(BaseModel):
    passage: str
    vocabulary: dict = {}  # Thêm từ điển nghĩa của các từ

@app.post("/reading/passage", response_model=ReadingPassageResponse)
async def reading_passage(req: ReadingPassageRequest):
    import traceback
    level = req.level
    print("========== [READING PASSAGE REQUEST] ==========")
    print(f"[RECEIVED LEVEL]: {level}")
    # ...existing code...
    
    # Điều chỉnh độ dài theo band điểm
    word_counts = {
        '5.0': '80-120 từ',
        '5.5': '100-150 từ', 
        '6.0': '130-180 từ',
        '6.5': '160-220 từ',
        '7.0': '200-280 từ',
        '7.5': '250-350 từ',
        '8.0': '300-400 từ',
        '8.5': '350-450 từ',
        '9.0': '400-500 từ'
    }
    
    # Lấy độ dài tương ứng với level, mặc định medium nếu không tìm thấy
    word_range = word_counts.get(level, '150-200 từ')
    
    # Chủ đề IELTS Reading đa dạng theo band điểm - Mở rộng toàn diện
    ielts_topics_by_band = {
        # Band 1.0-3.5: Chủ đề cơ bản, quen thuộc trong đời sống hàng ngày
        'basic': [
            # Cuộc sống hàng ngày
            "daily routines and lifestyle", "family and friends", "food and cooking",
            "pets and animals", "weather and seasons", "shopping and clothes",
            "house and home", "school life", "hobbies and free time",
            "transportation and travel", "sports and games", "festivals and celebrations",
            
            # Cơ bản về công việc và sức khỏe
            "work and jobs", "health and medicine", "numbers and time",
            "colors and shapes", "body parts", "simple technology use",
            
            # Giải trí và hoạt động
            "playground activities", "birthday parties", "weekend plans",
            "favorite foods", "my bedroom", "visiting relatives",
            "playing with friends", "going to the park", "watching TV",
            
            # Thiên nhiên và môi trường đơn giản
            "flowers and plants", "ocean and beach", "mountains and forests",
            "rain and sunshine", "birds and insects", "caring for plants"
        ],
        
        # Band 4.0-5.5: Chủ đề thông dụng, dễ hiểu, liên quan đời sống thực tế
        'intermediate': [
            # Xã hội và văn hóa
            "city life vs countryside", "popular sports and fitness", "movies and entertainment",
            "social media and internet", "environmental problems", "healthy eating habits",
            "education and learning", "tourism and holidays", "money and shopping",
            "friendship and relationships", "music and art", "books and reading",
            
            # Công nghệ và giao tiếp
            "computers and smartphones", "public transport", "restaurants and cafes",
            "weekend activities", "cultural differences", "news and media",
            "online learning", "video games", "photography",
            
            # Đời sống đô thị
            "apartment living", "neighborhood community", "local markets",
            "traffic and commuting", "recycling and waste", "volunteer work",
            "part-time jobs", "university life", "fashion trends",
            
            # Sở thích và kỹ năng
            "learning musical instruments", "cooking techniques", "gardening tips",
            "exercise routines", "time management", "budgeting money",
            "language exchange", "cultural festivals", "travel experiences"
        ],
        
        # Band 6.0-7.0: Chủ đề phức tạp hơn, xã hội và khoa học ứng dụng
        'advanced': [
            # Quy hoạch và phát triển
            "urban planning and cities", "climate change effects", "workplace trends",
            "cultural diversity", "technology in education", "healthcare systems",
            "sustainable living", "economic development", "social media impacts",
            
            # Năng lượng và môi trường
            "renewable energy basics", "population changes", "language learning",
            "business and marketing", "scientific discoveries", "historical events",
            "innovation and invention", "global communication", "youth culture",
            
            # Tâm lý và xã hội học
            "stress management", "work-life balance", "digital addiction",
            "generational gaps", "consumer psychology", "urban agriculture",
            "sustainable fashion", "food security", "mental health awareness",
            
            # Giáo dục và công nghệ
            "online education trends", "artificial intelligence basics", "data privacy",
            "startup culture", "remote working", "environmental conservation",
            "cultural preservation", "tourism impacts", "media influence",
            
            # Khoa học ứng dụng
            "medical breakthroughs", "space technology", "robotics applications",
            "genetic research basics", "archaeological findings", "weather patterns"
        ],
        
        # Band 7.5-9.0: Chủ đề academic, chuyên sâu và nghiên cứu khoa học
        'expert': [
            # Công nghệ tiên tiến
            "artificial intelligence and automation", "biotechnology and genetics",
            "quantum computing applications", "nanotechnology research",
            "cybersecurity and digital privacy", "blockchain technology",
            "virtual reality applications", "autonomous vehicles",
            
            # Khoa học tự nhiên
            "space exploration and astronomy", "neuroscience and brain research",
            "marine science and oceans", "geological formations",
            "pharmaceutical research", "climate modeling",
            "biodiversity conservation", "ecosystem dynamics",
            
            # Khoa học xã hội và nhân văn
            "psychological studies", "economic theories", "political science",
            "anthropological research", "linguistic evolution",
            "cultural anthropology", "social psychology", "behavioral economics",
            
            # Nghiên cứu chuyên sâu
            "archaeological discoveries", "historical linguistics",
            "architectural design principles", "urban sociology",
            "environmental engineering", "renewable vs fossil fuels",
            "international trade policies", "demographic transitions",
            
            # Lĩnh vực đa ngành
            "interdisciplinary research", "systems thinking",
            "computational biology", "environmental economics",
            "medical anthropology", "cognitive science",
            "materials science", "energy policy analysis",
            "sustainable development goals", "global governance"
        ]
    }
    
    # Chọn chủ đề phù hợp với band điểm
    def get_topic_by_band(level):
        try:
            band_score = float(level)
            if band_score <= 3.5:
                return random.choice(ielts_topics_by_band['basic'])
            elif band_score <= 5.5:
                return random.choice(ielts_topics_by_band['intermediate'])
            elif band_score <= 7.0:
                return random.choice(ielts_topics_by_band['advanced'])
            else:
                return random.choice(ielts_topics_by_band['expert'])
        except:
            return random.choice(ielts_topics_by_band['intermediate'])
    
    import random
    selected_topic = get_topic_by_band(level)
    
    system_prompt = (
        f"Bạn là Cambridge IELTS examiner. Hãy tạo Reading passage theo chuẩn IELTS Academic, độ dài {word_range}.\n"
        f"Chủ đề: {selected_topic}\n"
        f"Band điểm: {level}\n\n"
        "YÊU CẦU THEO BAND ĐIỂM:\n"
        f"- Band 1.0-3.5: Văn bản đơn giản, từ vựng cơ bản, câu ngắn, chủ đề quen thuộc hàng ngày\n"
        f"- Band 4.0-5.5: Văn bản trung bình, từ vựng thông dụng, cấu trúc câu đơn giản, chủ đề thực tế\n" 
        f"- Band 6.0-7.0: Văn bản phức tạp hơn, từ vựng đa dạng, câu ghép, chủ đề xã hội\n"
        f"- Band 7.5-9.0: Văn phong academic, từ vựng chuyên môn, câu phức, chủ đề khoa học\n\n"
        "ĐIỀU CHỈNH THEO LEVEL:\n"
        f"- Độ khó từ vựng phù hợp band {level}\n"
        f"- Cấu trúc câu phù hợp band {level}\n"
        f"- Độ phức tạp nội dung phù hợp band {level}\n"
        f"- Giọng văn phù hợp band {level} (đơn giản → academic)\n\n"
        "Format: Đoạn văn liền mạch, có đầu - giữa - cuối rõ ràng.\n"
        f"Chỉ trả về passage tiếng Anh, độ dài {word_range}, không giải thích."
    )
    print("[DEBUG] /reading/passage request level:", level)
    print("[DEBUG] /reading/passage system_prompt:", system_prompt)
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hãy viết đoạn đọc hiểu IELTS."}
            ],
            max_tokens=700,  # Tăng từ 300 lên 700 để xử lý đoạn văn dài hơn
            temperature=0.8
        )
        passage = response.choices[0].message.content.strip()
        print("[DEBUG] /reading/passage AI response:", passage)
        
        # Tạo vocabulary meanings cho passage
        vocabulary = await generate_vocabulary_meanings(passage)
        print("[DEBUG] /reading/passage vocabulary:", vocabulary)
        
        return {"passage": passage, "vocabulary": vocabulary}
    except Exception as e:
        print("[ERROR] /reading/passage Exception:", e)
        traceback.print_exc()
        return {"passage": "(Không tạo được đoạn đọc hiểu)"}
# --- Listening Practice API ---
class ListeningRequest(BaseModel):
    topic: str
    band: str

class ListeningResponse(BaseModel):
    text: str
    answer: str
    audioUrl: str = None

@app.post("/api/generate-listening", response_model=ListeningResponse)
async def generate_listening(req: ListeningRequest):
    import traceback
    topic = req.topic
    band = req.band
    print("========== [LISTENING REQUEST] ==========")
    print(f"[RECEIVED TOPIC]: {topic}")
    print(f"[RECEIVED BAND]: {band}")
    # Prompt cho AI sinh câu luyện nghe
    system_prompt = (
        f"Bạn là giáo viên luyện thi IELTS. Hãy tạo ra 1 câu tiếng Anh phù hợp để luyện nghe, sát với đề thi IELTS Listening, chủ đề: {topic}, band điểm: {band}. "
        "Câu phải tự nhiên, không quá dài, không quá dễ nếu band cao. Trả về đúng 1 câu tiếng Anh, không giải thích, không thêm gì khác."
    )
    print("[DEBUG] /api/generate-listening system_prompt:", system_prompt)
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hãy cho tôi 1 câu tiếng Anh phù hợp để luyện nghe."}
            ],
            max_tokens=60,
            temperature=1.0
        )
        text = response.choices[0].message.content.strip()
        answer = text
        print("[DEBUG] /api/generate-listening AI response:", text)
        # Nếu có dịch vụ tạo audio, có thể tích hợp ở đây
        audioUrl = ""  # Luôn trả về chuỗi rỗng nếu không có audio
        # Ví dụ: sử dụng dịch vụ TTS bên ngoài để tạo audio file, trả về url
        # audioUrl = tts_service_generate(text)
        return {"text": text, "answer": answer, "audioUrl": audioUrl}
    except Exception as e:
        print("[ERROR] /api/generate-listening Exception:", e)
        traceback.print_exc()
        return {"text": "(Không tạo được câu luyện nghe)", "answer": "", "audioUrl": ""}

# Thêm route GET để tránh lỗi khi truy cập trực tiếp bằng GET
@app.post("/api/generate-listening")
async def get_listening_info():
    return {"message": "Vui lòng sử dụng phương thức POST để tạo câu luyện nghe."}

# --- IELTS Vocabulary Extraction API ---
from fastapi import Request
class IELTSVocabRequest(BaseModel):
    passage: str
    level: Optional[str] = None

class IELTSVocabWord(BaseModel):
    word: str
    meaning: str
    part_of_speech: str
    phonetic: str
    example: str
    analysis: str

class IELTSVocabResponse(BaseModel):
    vocab: List[IELTSVocabWord]

@app.post("/api/ielts-vocab", response_model=IELTSVocabResponse)
async def ielts_vocab(req: IELTSVocabRequest):
    passage = req.passage
    level = req.level or "all"
    system_prompt = (
        "Bạn là giáo viên luyện thi IELTS. Dưới đây là một đoạn đọc hiểu tiếng Anh (Reading passage):\n" + passage + "\n"
        "Hãy phân tích đoạn văn trên và chỉ trích xuất các từ vựng thực sự phổ biến trong kỳ thi IELTS (high-frequency IELTS vocabulary, academic word list, hoặc các từ thường xuất hiện trong đề thi IELTS band 5-9). "
        "Bỏ qua các từ thông dụng, từ không phải từ vựng học thuật IELTS. Không chọn các từ như: the, and, is, are, have, do, go, come, get, make, take, see, say, can, will, should, must, may, might, would, could, shall, to, of, in, on, at, for, with, by, from, as, but, or, if, so, because, very, really, just, only, also, too, more, most, much, many, some, any, every, each, all, no, not, nor, neither, either, both, few, little, less, least, enough, again, always, never, sometimes, often, usually, rarely, seldom, ever, never, before, after, then, now, soon, later, today, tomorrow, yesterday, here, there, where, when, why, how, what, which, who, whom, whose, this, that, these, those, I, you, he, she, it, we, they, me, him, her, us, them, my, your, his, her, its, our, their, mine, yours, hers, ours, theirs, a, an. "
        "Chỉ chọn các từ academic, collocation, hoặc technical thường gặp trong đề IELTS. "
        "Với mỗi từ vựng, hãy trả về thông tin sau: word (từ), meaning (nghĩa tiếng Việt), part_of_speech (loại từ), phonetic (phiên âm IPA), example (ví dụ sử dụng từ trong ngữ cảnh đoạn văn), analysis (giải thích ngắn gọn về ý nghĩa/ngữ cảnh sử dụng từ trong đoạn). "
        "Chỉ trả về một mảng JSON các object như sau: {word, meaning, part_of_speech, phonetic, example, analysis}. Không giải thích gì ngoài JSON."
    )
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hãy trích xuất từ vựng IELTS từ đoạn văn trên."}
            ],
            max_tokens=1200,
            temperature=0.7
        )
        import json, re
        content = response.choices[0].message.content
        match = re.search(r'(\[.*\])', content, re.DOTALL)
        vocab_list = []
        if match:
            arr = match.group(1)
            vocab_list = json.loads(arr)
        # Chuyển đổi sang định dạng chuẩn
        result = []
        for v in vocab_list:
            result.append({
                "word": v.get("word", ""),
                "meaning": v.get("meaning", ""),
                "part_of_speech": v.get("part_of_speech", ""),
                "phonetic": v.get("phonetic", ""),
                "example": v.get("example", ""),
                "analysis": v.get("analysis", "")
            })
        return {"vocab": result}
    except Exception as e:
        return {"vocab": []}

# Helper function để tạo vocabulary meanings cho reading passage
async def generate_vocabulary_meanings(passage: str) -> dict:
    """
    Tạo từ điển nghĩa của các từ trong passage theo ngữ cảnh
    """
    import re
    import json
    
    try:
        # Extract ALL words from passage - không filter gì cả
        words = re.findall(r'\b[a-zA-Z]+\b', passage)
        
        # Lấy tất cả từ unique, giữ nguyên case gốc
        all_words = list(set(words))
        
        if not all_words:
            return {}
        
        print(f"[DEBUG] Vocabulary generation - Total unique words: {len(all_words)}")
        print(f"[DEBUG] Words to translate: {all_words}")
        
        # Gọi AI để dịch TẤT CẢ từ trong passage
        words_str = ', '.join(all_words)
        
        system_prompt = (
            f"Bạn là từ điển Cambridge Dictionary chuyên nghiệp. Đoạn văn:\n\n{passage}\n\n"
            f"Dịch CHÍNH XÁC {len(all_words)} từ sau sang tiếng Việt theo ngữ cảnh:\n{words_str}\n\n"
            "QUAN TRỌNG: JSON phải có ĐÚNG {len(all_words)} entries, không được thiếu!\n\n"
            "Format: {{\"word1\":\"nghĩa\", \"word2\":\"nghĩa\", ...}}\n\n"
            "Quy tắc dịch:\n"
            "- Từ nội dung: dịch theo nghĩa chính xác trong ngữ cảnh\n"
            "- Từ ngữ pháp (the, and, is, are...): dịch nghĩa đơn giản nhất\n"
            "- Nghĩa ngắn gọn 1-3 từ\n"
            "- Bắt buộc phải có đủ tất cả từ trong response\n"
            "- Chỉ trả JSON, không giải thích"
        )
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Dịch tất cả {len(all_words)} từ trong đoạn văn."}
            ],
            max_tokens=1500,  # Tăng từ 1000 lên 1500 để đảm bảo dịch đủ từ
            temperature=0.05  # Giảm temperature để AI consistent hơn
        )
        
        ai_response = response.choices[0].message.content.strip()
        print("[DEBUG] Vocabulary AI response:", ai_response)
        
        # Parse JSON response
        try:
            vocabulary_dict = json.loads(ai_response)
            
            # Log coverage statistics
            provided_words = len(vocabulary_dict)
            requested_words = len(all_words)
            coverage = (provided_words / requested_words) * 100 if requested_words > 0 else 0
            
            print(f"[DEBUG] Vocabulary coverage: {provided_words}/{requested_words} words ({coverage:.1f}%)")
            
            if coverage < 80:  # If coverage is poor, log missing words
                missing_words = [word for word in all_words if word not in vocabulary_dict]
                print(f"[WARNING] Missing translations for: {missing_words[:10]}...")  # Log first 10 missing
            
            return vocabulary_dict
            
        except json.JSONDecodeError:
            # Fallback: extract JSON from response if wrapped in markdown
            import re
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                try:
                    vocabulary_dict = json.loads(json_match.group())
                    print(f"[DEBUG] Extracted JSON from markdown response")
                    return vocabulary_dict
                except json.JSONDecodeError:
                    pass
            
            print("[ERROR] Could not parse vocabulary JSON:", ai_response[:200])
            return {}
                
    except Exception as e:
        print(f"[ERROR] generate_vocabulary_meanings: {e}")
        return {}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
