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

# ===================== 題庫載入 =====================
def load_question_bank(xlsx_path="Zoology_Terms_Bilingual.xlsx"):
    df = pd.read_excel(xlsx_path)

    def clean(x):
        if pd.isna(x):
            return ""
        return str(x).strip()

    bank = []
    for _, row in df.iterrows():
        cn = clean(row.get("Name", ""))
        en = clean(row.get("English", ""))
        if cn and en:
            bank.append({
                "name": cn,       # 中文名稱
                "english": en,    # 英文術語
            })
    return bank

QUESTION_BANK = load_question_bank()

# ===================== 樣式 =====================
st.markdown("""
<style>
html, body, [class*="css"]  { font-size: 22px !important; }
h2 { font-size: 26px !important;
     margin-top: 0.22em !important;
     margin-bottom: 0.22em !important; }
.block-container {
     padding-top: 0.4rem !important;
     padding-bottom: 0.9rem !important;
     max-width: 1000px;
}
.progress-card { margin-bottom: 0.22rem !important; }
.stRadio { margin-top: 0 !important; }
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stRadio"]) {
    margin-top: 0 !important;
}
.stButton>button{
    height: 44px;
    padding: 0 18px;
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
.text-input-big input {
    font-size: 24px !important;
    height: 3em !important;
}
</style>
""", unsafe_allow_html=True)

# ===================== 遊戲參數 =====================
MAX_ROUNDS = 3
QUESTIONS_PER_ROUND = 10

MODE_1 = "模式一：中文 ➜ 英文（二選一）"
MODE_2 = "模式二：英文 ➜ 中文（二選一）"
MODE_3 = "模式三：中文 ➜ 英文（手寫輸入＋提示）"

# ===================== 狀態初始化 =====================
def init_state():
    st.session_state.mode = MODE_1
    st.session_state.round = 1
    st.session_state.used_pairs = set()   # 用英文當 key，避免整個 session 重複太多
    st.session_state.cur_round_qidx = []
    st.session_state.cur_idx_in_round = 0
    st.session_state.records = []         # (round, prompt, chosen_label, correct_eng, correct_name, is_correct, options_disp)
    st.session_state.score_this_round = 0
    st.session_state.submitted = False
    st.session_state.last_feedback = ""
    st.session_state.answer_cache = ""    # for mode3 text_input
    st.session_state.options_cache = {}
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

def start_new_round():
    available = [i for i, it in enumerate(QUESTION_BANK)
                 if it["english"] not in st.session_state.used_pairs]
    if len(available) == 0:
        st.session_state.used_pairs = set()
        available = list(range(len(QUESTION_BANK)))

    if len(available) <= QUESTIONS_PER_ROUND:
        chosen = available[:]
    else:
        chosen = random.sample(available, QUESTIONS_PER_ROUND)

    st.session_state.cur_round_qidx = chosen
    st.session_state.cur_idx_in_round = 0
    st.session_state.score_this_round = 0
    st.session_state.submitted = False
    st.session_state.last_feedback = ""
    st.session_state.answer_cache = ""
    st.session_state.options_cache = {}

if "round" not in st.session_state:
    init_state()
    start_new_round()

# ===================== 小工具：提示字首字尾 =====================
def head_tail_hint(word: str):
    w = word.strip()
    if len(w) <= 2:
        return w  # 太短就直接顯示整個字
    return f"{w[0]}…{w[-1]}"

# ===================== 產生選項（模式一/二用） =====================
def get_options_for_q(qidx, mode):
    """
    mode1: 題幹=中文name，選項=英文english（正確英文 + 干擾英文）
    mode2: 題幹=英文english，選項=中文name（正確中文 + 干擾中文）
    mode3: 自由輸入，不走這個函式
    """
    key = (qidx, mode)
    if key in st.session_state.options_cache:
        return st.session_state.options_cache[key]

    item = QUESTION_BANK[qidx]
    correct_name = item["name"].strip()
    correct_eng  = item["english"].strip()

    if mode == MODE_1:
        # 要另一個英文當干擾
        pool = [it["english"].strip() for it in QUESTION_BANK
                if it["english"].strip() and it["english"].strip() != correct_eng]
        distractor = random.choice(pool) if pool else "???"
        display = [correct_eng, distractor]

    else:  # MODE_2
        # 要另一個中文當干擾
        pool = [it["name"].strip() for it in QUESTION_BANK
                if it["name"].strip() and it["name"].strip() != correct_name]
        distractor = random.choice(pool) if pool else "???"
        display = [correct_name, distractor]

    random.shuffle(display)
    payload = {
        "display": display,
        "value": display[:],
    }
    st.session_state.options_cache[key] = payload
    return payload

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
    mode = st.session_state.mode

    if mode == MODE_1:
        # 題幹 = 中文名稱 -> 選英文
        prompt = q["name"]
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

    elif mode == MODE_2:
        # 題幹 = 英文術語 -> 選中文
        prompt = q["english"]
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
        # MODE_3：中文名稱 -> 學生手寫英文，並顯示英文提示首尾
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

        # 文字輸入
        ans = st.text_input(
            "請輸入英文術語：",
            key=f"ti_{qidx}",
            value=st.session_state.answer_cache,
        )
        return qidx, q, ("text", ans, None)

# ===================== 答案處理 =====================
def handle_action(qidx, q, user_input):
    mode = st.session_state.mode
    correct_name = q["name"].strip()
    correct_eng  = q["english"].strip()

    ui_type, data, payload = user_input

    # 取得學生的答案 & 判斷正確性
    if mode in (MODE_1, MODE_2):
        chosen_disp = data  # radio 選到的文字
        if chosen_disp is None:
            st.warning("請先選擇一個選項。")
            return

        if mode == MODE_1:
            # 中文 -> 英文：正確應該是 correct_eng
            is_correct = (chosen_disp.strip().lower() == correct_eng.lower())
            chosen_label = chosen_disp.strip()
        else:
            # 英文 -> 中文：正確應該是 correct_name
            is_correct = (chosen_disp.strip() == correct_name)
            chosen_label = chosen_disp.strip()

    else:
        # MODE_3：自由輸入英文
        typed_ans = data or ""
        chosen_label = typed_ans.strip()
        is_correct = (chosen_label.lower() == correct_eng.lower())

    # 第一次按（送出答案）
    if not st.session_state.submitted:
        st.session_state.submitted = True

        st.session_state.records.append((
            st.session_state.round,
            (q["name"] if mode != MODE_2 else q["english"]),  # prompt: 如果是模式2，用英文當prompt，其餘用中文當prompt
            chosen_label,        # 學生填的/選的
            correct_eng,         # 正解英文
            correct_name,        # 正解中文
            is_correct,
            (payload["display"] if (payload and "display" in payload) else None)
        ))

        # 回饋文字
        if is_correct:
            st.session_state.last_feedback = (
                "<div class='feedback-small feedback-correct'>✅ 回答正確</div>"
            )
            st.session_state.score_this_round += 1
        else:
            # 錯的情況：依模式顯示正解
            if mode == MODE_1:
                # 顯示 英文(中文)
                st.session_state.last_feedback = (
                    f"<div class='feedback-small feedback-wrong'>❌ Incorrect. 正確答案："
                    f"{correct_eng} ({correct_name})</div>"
                )
            elif mode == MODE_2:
                # 顯示 中文(英文)
                st.session_state.last_feedback = (
                    f"<div class='feedback-small feedback-wrong'>❌ Incorrect. 正確答案："
                    f"{correct_name} ({correct_eng})</div>"
                )
            else:
                # 模式三：學生打英文，顯示 英文(中文)
                st.session_state.last_feedback = (
                    f"<div class='feedback-small feedback-wrong'>❌ Incorrect. 正確答案："
                    f"{correct_eng} ({correct_name})</div>"
                )

        # 把 text_input 的內容暫存（模式三用）
        if mode == MODE_3:
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

        # 檢查回合結束
        if st.session_state.cur_idx_in_round >= len(st.session_state.cur_round_qidx):
            # 全對且還有回合 → 進下一回合
            if (
                st.session_state.score_this_round
                == len(st.session_state.cur_round_qidx)
            ) and (st.session_state.round < MAX_ROUNDS):
                st.session_state.round += 1
                start_new_round()
            else:
                st.session_state.round = None  # 進入總結

        st.rerun()
        return

# ===================== 側邊欄 =====================
with st.sidebar:
    st.markdown("### 設定 / 身分")
    st.session_state.user_name = st.text_input(
        "姓名", st.session_state.get("user_name","")
    )
    st.session_state.user_class = st.text_input(
        "班級", st.session_state.get("user_class","")
    )
    st.session_state.user_seat = st.text_input(
        "座號", st.session_state.get("user_seat","")
    )

    # 只能在第一回合、第0題、還沒交過答案時換模式
    can_change_mode = (
        st.session_state.cur_idx_in_round == 0 and
        not st.session_state.submitted and
        st.session_state.round == 1 and
        len(st.session_state.records) == 0
    )

    st.session_state.mode = st.radio(
        "選擇練習模式",
        [MODE_1, MODE_2, MODE_3],
        index=[MODE_1, MODE_2, MODE_3].index(st.session_state.mode)
        if "mode" in st.session_state else 0,
        disabled=not can_change_mode,
    )

    if st.button("🔄 重新開始"):
        init_state()
        start_new_round()
        st.rerun()

# ===================== 主畫面 =====================
if st.session_state.round:
    # 題目進行中
    render_top_card()
    qidx, q, user_input = render_question()

    # 顯示答題後回饋框
    if st.session_state.submitted and st.session_state.last_feedback:
        st.markdown(st.session_state.last_feedback, unsafe_allow_html=True)

    # 主按鈕
    action_label = "下一題" if st.session_state.submitted else "送出答案"
    if st.button(action_label, key="action_btn"):
        handle_action(qidx, q, user_input)

    # 題目提交後：下方複習區（雙語格式）
    if st.session_state.submitted and st.session_state.records:
        last = st.session_state.records[-1]
        # last = (round, prompt, chosen_label, correct_eng, correct_name, is_correct, options_disp)
        _, _, _, correct_eng, correct_name, _, opts_disp = last
        mode_now = st.session_state.mode

        st.markdown("---")

        # 標題文字依模式調整
        if mode_now == MODE_1:
            # 中文→英文，所以主標示「正確英文術語：English(Name)」
            st.markdown(
                f"**正確英文術語：{correct_eng} ({correct_name})**"
            )
        elif mode_now == MODE_2:
            # 英文→中文，主標示「正確中文名稱：Name(English)」
            st.markdown(
                f"**正確中文名稱：{correct_name} ({correct_eng})**"
            )
        else:
            # 模式三：學生輸入英文
            st.markdown(
                f"**正確英文術語：{correct_eng} ({correct_name})**"
            )

        if opts_disp:
            # 對於每個選項，也做雙語顯示
            st.markdown("**本題兩個選項：**")
            bipairs = []
            for opt in opts_disp:
                # 我們需要把 opt 轉成 "英文(中文)" 或 "中文(英文)"
                # 找到這個 opt 在題庫中對應的 pair
                match = None
                for it in QUESTION_BANK:
                    n = it["name"].strip()
                    e = it["english"].strip()
                    if opt.strip().lower() == e.lower() or opt.strip() == n:
                        match = (n, e)
                        break
                if match:
                    n, e = match
                    if mode_now == MODE_1:
                        # 顯示英文(中文)
                        bipairs.append(f"{e}（{n}）")
                    elif mode_now == MODE_2:
                        # 顯示中文(英文)
                        bipairs.append(f"{n}（{e}）")
                    else:
                        # 模式三其實不會有 opts_disp，但保險
                        bipairs.append(f"{e}（{n}）")
                else:
                    # fallback: just show text
                    bipairs.append(opt.strip())

            st.markdown("、".join(bipairs))

else:
    # 總結畫面
    total_answered = len(st.session_state.records)
    total_correct = sum(1 for rec in st.session_state.records if rec[5])
    st.subheader("📊 總結")
    st.markdown(
        f"<h3>Total Answered: {total_answered}</h3>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<h3>Total Correct: {total_correct}</h3>",
        unsafe_allow_html=True
    )
    acc = (total_correct / total_answered * 100) if total_answered else 0.0
    st.markdown(
        f"<h3>Accuracy: {acc:.1f}%</h3>",
        unsafe_allow_html=True
    )

    if st.button("🔄 再玩一次"):
        init_state()
        start_new_round()
        st.rerun()
