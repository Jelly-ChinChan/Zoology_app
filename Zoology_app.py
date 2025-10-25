import streamlit as st
import random
import uuid
import pandas as pd

# ====== App 基本設定 ======
st.set_page_config(
    page_title="Zoology Term Practice",
    page_icon="📝",
    layout="centered"
)

# ===================== 題庫載入（新版，容錯版） =====================
@st.cache_data
def load_question_bank(xlsx_path="Zoology_Terms_Bilingual.xlsx"):
    """
    嘗試讀取 Excel 並自動對應「中文名欄」與「英文名欄」.
    支援常見欄位名稱（不分大小寫、會strip空白）：
      中文欄候選: Name, 中文, 名稱, Chinese, CN
      英文欄候選: English, 英文, Term, 英文名, EN
    """
    try:
        df = pd.read_excel(xlsx_path)
    except Exception as e:
        return {
            "ok": False,
            "error": f"無法讀取題庫檔案 {xlsx_path} ：{e}",
            "bank": [],
            "debug_cols": []
        }

    # 先把欄名整理成乾淨的小寫字串方便比對
    def norm(s):
        return str(s).strip().lower()

    cols_norm = {norm(c): c for c in df.columns}  # "name" -> 原本"Name "之類

    # 我們接受的候選名稱
    cn_candidates = ["name", "中文", "名稱", "chinese", "cn"]
    en_candidates = ["english", "英文", "term", "英文名", "en", "english term"]

    # 找出真正的欄名
    cn_col = None
    en_col = None
    for cand in cn_candidates:
        if cand in cols_norm:
            cn_col = cols_norm[cand]
            break
    for cand in en_candidates:
        if cand in cols_norm:
            en_col = cols_norm[cand]
            break

    if cn_col is None or en_col is None:
        # 找不到的話就回報錯誤 + 把目前欄位丟回去做debug
        return {
            "ok": False,
            "error": (
                "找不到必要欄位。\n"
                f"目前檔案欄位是：{list(df.columns)}\n"
                f"我在找的中文欄候選：{cn_candidates}\n"
                f"我在找的英文欄候選：{en_candidates}\n"
                "請把你的 Excel 其中兩個欄名改成上面其中一個就好，例如：Name / English。"
            ),
            "bank": [],
            "debug_cols": list(df.columns)
        }

    # 真的有兩欄就開始清洗
    def clean(x):
        if pd.isna(x):
            return ""
        return str(x).strip()

    bank_list = []
    for _, row in df.iterrows():
        cn_val = clean(row.get(cn_col, ""))
        en_val = clean(row.get(en_col, ""))
        if cn_val and en_val:
            bank_list.append({
                "name": cn_val,      # 中文名稱
                "english": en_val,   # 英文術語
            })

    return {
        "ok": True,
        "error": "",
        "bank": bank_list,
        "debug_cols": list(df.columns)
    }

loaded = load_question_bank()
QUESTION_BANK = loaded["bank"]

# debug 區（會在畫面上顯示目前抓到的欄位跟筆數，方便你檢查）
with st.expander("📂 題庫偵測狀態（老師看得到就好，學生可以不用管）"):
    st.write("Excel 欄位 =", loaded["debug_cols"])
    st.write("成功載入幾筆題目 =", len(QUESTION_BANK))
    if not loaded["ok"]:
        st.error(loaded["error"])

# 如果真的沒載到，就直接停
if not loaded["ok"] or not QUESTION_BANK:
    st.warning("⚠ 題庫是空的，請把 Excel 欄名改成能被辨識（例如 Name / English）再重新整理。")
    st.stop()


# ===================== 常數 / 模式名稱 =====================
MAX_ROUNDS = 3
QUESTIONS_PER_ROUND = 10

MODE_1 = "模式一：中文 ➜ 英文（二選一）"
MODE_2 = "模式二：英文 ➜ 中文（二選一）"
MODE_3 = "模式三：中文 ➜ 英文（手寫輸入＋提示）"

ALL_MODES = [MODE_1, MODE_2, MODE_3]

# ===================== 工具函式 =====================
def head_tail_hint(word: str):
    """英文提示：顯示首字母…尾字母"""
    w = word.strip()
    if len(w) <= 2:
        return w
    return f"{w[0]}…{w[-1]}"

def init_state():
    """一次性初始化整個 session_state"""
    st.session_state.mode = MODE_1
    st.session_state.round = 1
    st.session_state.used_pairs = set()   # 用英文當 key，避免重複
    st.session_state.cur_round_qidx = []  # 這回合抽到的題目 index
    st.session_state.cur_idx_in_round = 0 # 目前在這回合第幾題
    st.session_state.records = []         # 做題紀錄
    st.session_state.score_this_round = 0
    st.session_state.submitted = False    # 這一題已經按過「送出答案」了嗎
    st.session_state.last_feedback = ""   # 顯示的 ✅/❌ 訊息（HTML）
    st.session_state.answer_cache = ""    # 模式三 text_input 暫存
    st.session_state.options_cache = {}   # (qidx, mode) -> 選項們，避免重抽
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

def start_new_round():
    """抽一回合的新題目"""
    available = [
        i for i, it in enumerate(QUESTION_BANK)
        if it["english"] not in st.session_state.used_pairs
    ]
    if len(available) == 0:
        st.session_state.used_pairs = set()
        available = list(range(len(QUESTION_BANK)))

    if len(available) <= QUESTIONS_PER_ROUND:
        chosen = available[:]
        random.shuffle(chosen)
    else:
        chosen = random.sample(available, QUESTIONS_PER_ROUND)

    st.session_state.cur_round_qidx = chosen
    st.session_state.cur_idx_in_round = 0
    st.session_state.score_this_round = 0
    st.session_state.submitted = False
    st.session_state.last_feedback = ""
    st.session_state.answer_cache = ""
    st.session_state.options_cache = {}

def ensure_state_ready():
    """確保所有必要的 session_state key 都存在，否則初始化+抽題"""
    needed_keys = [
        "mode", "round", "used_pairs", "cur_round_qidx", "cur_idx_in_round",
        "records", "score_this_round", "submitted", "last_feedback",
        "answer_cache", "options_cache", "session_id"
    ]
    if any(k not in st.session_state for k in needed_keys):
        init_state()
        start_new_round()
    if st.session_state.round and not st.session_state.cur_round_qidx:
        start_new_round()

ensure_state_ready()

def get_options_for_q(qidx, mode_label):
    key = (qidx, mode_label)
    if key in st.session_state.options_cache:
        return st.session_state.options_cache[key]

    item = QUESTION_BANK[qidx]
    correct_name = item["name"].strip()
    correct_eng  = item["english"].strip()

    if mode_label == MODE_1:
        # 干擾英文
        pool = [
            it["english"].strip()
            for it in QUESTION_BANK
            if it["english"].strip().lower() != correct_eng.lower()
        ]
        distractor = random.choice(pool) if pool else "???"
        display_list = [correct_eng, distractor]

    elif mode_label == MODE_2:
        # 干擾中文
        pool = [
            it["name"].strip()
            for it in QUESTION_BANK
            if it["name"].strip() != correct_name
        ]
        distractor = random.choice(pool) if pool else "???"
        display_list = [correct_name, distractor]

    else:
        display_list = []

    random.shuffle(display_list)
    payload = {
        "display": display_list,
        "value": display_list[:],
    }
    st.session_state.options_cache[key] = payload
    return payload

# ===================== 樣式 =====================
st.markdown("""
<style>

/* ====== 1. 移除 Streamlit 頂部那條黑/灰工具列、右上角的Menu ====== */
header[data-testid="stHeader"] {
    display: none !important;
}
div[data-testid="stToolbar"] {
    display: none !important;
}

/* 有些部署環境(Cloud)會把主內容往下推，這邊把上邊距歸零 */
main.block-container {
    padding-top: 0rem !important;
}

/* ====== 2. 全域字級 / 版面壓緊 ====== */
html, body, [class*="css"]  { 
    font-size: 22px !important;
}

h2 {
    font-size: 26px !important;
    margin-top: 0.22em !important;
    margin-bottom: 0.22em !important;
}

/* 主要容器：上邊距我們已經在 main.block-container 改成0
   下面這段仍可保留左右寬度 & 下邊距設定 */
.block-container {
    padding-bottom: 0.9rem !important;
    max-width: 1000px;
}

/* 3. 進度卡 / radio / 按鈕 / 回饋樣式 ====== */
.progress-card { 
    margin-bottom: 0.22rem !important;
}

.stRadio { 
    margin-top: 0 !important;
}

/* 把 radio 上方多出來的空行也壓掉 */
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stRadio"]) {
    margin-top: 0 !important;
}

.stButton>button{
    height: 44px;
    padding: 0 18px;
    font-size: 20px;
}

.feedback-small {
    font-size: 17px !important;
    line-height: 1.4;
    margin: 6px 0 2px 0;
    display: inline-block;
    padding: 4px 6px;
    border-radius: 4px;
    border: 2px solid transparent;
}

.feedback-correct {
    color: #1a7f37;
    border-color: #1a7f37;
    background-color: #e8f5e9;
    font-weight: 700;
}

.feedback-wrong {
    color: #c62828;
    border-color: #c62828;
    background-color: #ffebee;
    font-weight: 700;
}

/* 輸入框放大（模式三） */
.text-input-big input {
    font-size: 24px !important;
    height: 3em !important;
}

</style>
""", unsafe_allow_html=True)


# ===================== UI: 進度卡 =====================
def render_top_card():
    r = st.session_state.round
    i = st.session_state.cur_idx_in_round + 1
    n = len(st.session_state.cur_round_qidx)
    percent = int(i / n * 100) if n else 0

    st.markdown(
        f"""
        <div class="progress-card"
             style='background-color:#f5f5f5;
                    padding:9px 14px;
                    border-radius:12px;'>
            <div style='display:flex;
                        align-items:center;
                        justify-content:space-between;
                        margin-bottom:4px;'>
                <div style='font-size:18px;'>
                    🎯 第 {r} 回合｜進度：{i} / {n}
                </div>
                <div style='font-size:16px; color:#555;'>{percent}%</div>
            </div>
            <progress value='{i}'
                      max='{n if n else 1}'
                      style='width:100%; height:14px;'></progress>
        </div>
        """,
        unsafe_allow_html=True
    )

# ===================== 題目顯示 =====================
def render_question():
    cur_pos = st.session_state.cur_idx_in_round
    qidx = st.session_state.cur_round_qidx[cur_pos]
    q = QUESTION_BANK[qidx]
    mode_label = st.session_state.mode

    if mode_label == MODE_1:
        # 題幹：中文 -> 選英文
        prompt = q["name"].strip()
        st.markdown(
            f"<h2>Q{cur_pos + 1}. 「{prompt}」的正確英文是？</h2>",
            unsafe_allow_html=True
        )
        payload = get_options_for_q(qidx, MODE_1)
        options_disp = payload["display"]
        if not options_disp:
            st.info("No options to select.")
            user_choice_disp = None
        else:
            user_choice_disp = st.radio(
                "",
                options_disp,
                key=f"mc_{qidx}",
                label_visibility="collapsed"
            )
        return qidx, q, ("mc", user_choice_disp, payload)

    elif mode_label == MODE_2:
        # 題幹：英文 -> 選中文
        prompt = q["english"].strip()
        st.markdown(
            f"<h2>Q{cur_pos + 1}. 「{prompt}」對應的正確中文是？</h2>",
            unsafe_allow_html=True
        )
        payload = get_options_for_q(qidx, MODE_2)
        options_disp = payload["display"]
        if not options_disp:
            st.info("No options to select.")
            user_choice_disp = None
        else:
            user_choice_disp = st.radio(
                "",
                options_disp,
                key=f"mc_{qidx}",
                label_visibility="collapsed"
            )
        return qidx, q, ("mc", user_choice_disp, payload)

    else:
        # MODE_3：中文 -> 學生輸入英文
        prompt_name = q["name"].strip()
        target_eng = q["english"].strip()
        hint = head_tail_hint(target_eng)

        st.markdown(
            f"<h2>Q{cur_pos + 1}. 「{prompt_name}」的英文是？</h2>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<div style='color:#555;font-size:18px;'>提示：{hint}</div>",
            unsafe_allow_html=True
        )

        ans = st.text_input(
            "請輸入英文術語：",
            key=f"ti_{qidx}",
            value=st.session_state.answer_cache,
        )
        return qidx, q, ("text", ans, None)

# ===================== 答案處理 =====================
def handle_action(qidx, q, user_input):
    mode_label = st.session_state.mode
    correct_name = q["name"].strip()
    correct_eng  = q["english"].strip()

    ui_type, data, payload = user_input

    # 判斷學生的答案
    if mode_label in (MODE_1, MODE_2):
        chosen_disp = data
        if chosen_disp is None:
            st.warning("請先選擇一個選項。")
            return

        if mode_label == MODE_1:
            # 中文 -> 英文
            is_correct = (chosen_disp.strip().lower() == correct_eng.lower())
            chosen_label = chosen_disp.strip()
        else:
            # 英文 -> 中文
            is_correct = (chosen_disp.strip() == correct_name)
            chosen_label = chosen_disp.strip()

    else:
        # MODE_3（手寫英文）
        typed_ans = data or ""
        chosen_label = typed_ans.strip()
        is_correct = (chosen_label.lower() == correct_eng.lower())

    # 第一次按（送出答案）
    if not st.session_state.submitted:
        st.session_state.submitted = True

        st.session_state.records.append((
            st.session_state.round,
            (q["name"] if mode_label != MODE_2 else q["english"]),
            chosen_label,
            correct_eng,
            correct_name,
            is_correct,
            (payload["display"] if (payload and "display" in payload) else None)
        ))

        if is_correct:
            st.session_state.last_feedback = (
                "<div class='feedback-small feedback-correct'>✅ 回答正確</div>"
            )
            st.session_state.score_this_round += 1
        else:
            if mode_label == MODE_1:
                st.session_state.last_feedback = (
                    f"<div class='feedback-small feedback-wrong'>❌ Incorrect. 正確答案："
                    f"{correct_eng} ({correct_name})</div>"
                )
            elif mode_label == MODE_2:
                st.session_state.last_feedback = (
                    f"<div class='feedback-small feedback-wrong'>❌ Incorrect. 正確答案："
                    f"{correct_name} ({correct_eng})</div>"
                )
            else:
                st.session_state.last_feedback = (
                    f"<div class='feedback-small feedback-wrong'>❌ Incorrect. 正確答案："
                    f"{correct_eng} ({correct_name})</div>"
                )

        if mode_label == MODE_3:
            st.session_state.answer_cache = chosen_label

        st.rerun()
        return

    # 第二次按（下一題）
    else:
        st.session_state.used_pairs.add(correct_eng)

        st.session_state.cur_idx_in_round += 1
        st.session_state.submitted = False
        st.session_state.last_feedback = ""
        st.session_state.answer_cache = ""

        if st.session_state.cur_idx_in_round >= len(st.session_state.cur_round_qidx):
            full_score = (
                st.session_state.score_this_round
                == len(st.session_state.cur_round_qidx)
            )
            has_more_rounds = (st.session_state.round < MAX_ROUNDS)

            if full_score and has_more_rounds:
                st.session_state.round += 1
                start_new_round()
            else:
                st.session_state.round = None

        st.rerun()
        return

# ===================== Sidebar（身分 + 模式切換） =====================
with st.sidebar:
    st.markdown("### 設定 / 身分")
    st.session_state.user_name = st.text_input(
        "姓名", st.session_state.get("user_name", "")
    )
    st.session_state.user_class = st.text_input(
        "班級", st.session_state.get("user_class", "")
    )
    st.session_state.user_seat = st.text_input(
        "座號", st.session_state.get("user_seat", "")
    )

    can_change_mode = (
        st.session_state.round == 1 and
        st.session_state.cur_idx_in_round == 0 and
        (not st.session_state.submitted) and
        len(st.session_state.records) == 0
    )

    current_mode_index = ALL_MODES.index(st.session_state.mode)
    chosen_mode = st.radio(
        "選擇練習模式",
        ALL_MODES,
        index=current_mode_index,
        disabled=not can_change_mode,
    )
    if can_change_mode:
        st.session_state.mode = chosen_mode

    if st.button("🔄 重新開始"):
        init_state()
        start_new_round()
        st.rerun()

# ===================== 主畫面 =====================
if st.session_state.round:
    render_top_card()
    qidx, q, user_input = render_question()

    if st.session_state.submitted and st.session_state.last_feedback:
        st.markdown(st.session_state.last_feedback, unsafe_allow_html=True)

    action_label = "下一題" if st.session_state.submitted else "送出答案"
    if st.button(action_label, key="action_btn"):
        handle_action(qidx, q, user_input)

    if st.session_state.submitted and st.session_state.records:
        last = st.session_state.records[-1]
        _, _, _, correct_eng, correct_name, _, opts_disp = last
        mode_now = st.session_state.mode

        st.markdown("---")

        if mode_now == MODE_1:
            st.markdown(
                f"**正確英文術語：{correct_eng}（{correct_name}）**"
            )
        elif mode_now == MODE_2:
            st.markdown(
                f"**正確中文名稱：{correct_name}（{correct_eng}）**"
            )
        else:
            st.markdown(
                f"**正確英文術語：{correct_eng}（{correct_name}）**"
            )

        if opts_disp:
            st.markdown("**本題兩個選項：**")
            bipairs = []
            for opt in opts_disp:
                match_pair = None
                for it in QUESTION_BANK:
                    n = it["name"].strip()
                    e = it["english"].strip()
                    if opt.strip().lower() == e.lower() or opt.strip() == n:
                        match_pair = (n, e)
                        break
                if match_pair:
                    n, e = match_pair
                    if mode_now == MODE_1:
                        bipairs.append(f"{e}（{n}）")
                    elif mode_now == MODE_2:
                        bipairs.append(f"{n}（{e}）")
                    else:
                        bipairs.append(f"{e}（{n}）")
                else:
                    bipairs.append(opt.strip())
            st.markdown("、".join(bipairs))

else:
    # 總結畫面
    total_answered = len(st.session_state.records)
    total_correct = sum(1 for rec in st.session_state.records if rec[5])
    acc = (total_correct / total_answered * 100) if total_answered else 0.0

    st.subheader("📊 總結")
    st.markdown(
        f"<h3>Total Answered: {total_answered}</h3>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<h3>Total Correct: {total_correct}</h3>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<h3>Accuracy: {acc:.1f}%</h3>",
        unsafe_allow_html=True
    )

    if st.button("🔄 再玩一次"):
        init_state()
        start_new_round()
        st.rerun()
