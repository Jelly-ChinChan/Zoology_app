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

# ====== CSS：sidebar 保留、畫面貼頂、footer隱藏 ======
st.markdown("""
<style>

/* (A) 保留 sidebar，讓學生/老師可以看到輸入欄位與重新開始按鈕 */
/* 我們不動 sidebar 相關元素 */

/* (B) 隱藏主畫面標頭、雲端工具列（fork/share）和 footer */
header[data-testid="stHeader"] {
    display: none !important;
}
div[data-testid="stToolbar"] {
    display: none !important;
}
footer,
div[role="contentinfo"],
div[data-testid="stStatusWidget"],
div[class*="viewerBadge_container"],
div[class*="stActionButtonIcon"],
div[class*="stDeployButton"],
div[data-testid="stDecoration"],
div[data-testid="stMainMenu"],
div[class*="stFloatingActionButton"],
a[class^="css-"][href*="streamlit.io"],
button[kind="header"] {
    display: none !important;
}

/* (C) 最硬核貼頂：把主內容區塊的上方間距全部歸零，讓進度條/標題貼在視窗最上方 */
div[data-testid="stAppViewContainer"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
div[data-testid="stAppViewBlockContainer"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
main.block-container {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
.block-container {
    padding-top: 0 !important;
    margin-top: 0 !important;
    padding-bottom: 0.9rem !important;
    max-width: 1000px;
}
div[data-testid="stVerticalBlock"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
div[data-testid="stVerticalBlock"] > div:first-child {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

/* 進度條卡片本體 */
.progress-card {
    margin-top: 0 !important;
    margin-bottom: 0.22rem !important;
}

/* (D) 版面可讀性 */
html, body, [class*="css"]  {
    font-size: 22px !important;
}
h1, h2, h3 {
    line-height: 1.35em !important;
}
h2 {
    font-size: 26px !important;
    margin-top: 0.22em !important;
    margin-bottom: 0.22em !important;
}

/* 單選題區塊靠緊上面標題 */
.stRadio {
    margin-top: 0 !important;
}
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stRadio"]) {
    margin-top: 0 !important;
}

/* 主要按鈕（送出答案 / 下一題 / 重新開始 / 開始作答） */
.stButton>button{
    height: 44px;
    padding: 0 18px;
    font-size: 20px;
    border-radius: 12px;
    border: 1px solid rgba(0,0,0,0.2);
}

/* 回饋訊息（答對/答錯） */
.feedback-small {
    font-size: 17px !important;
    line-height: 1.4;
    margin: 6px 0 2px 0;
    display: inline-block;
    padding: 4px 6px;
    border-radius: 6px;
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

/* 模式三輸入框外觀 */
.text-input-big input {
    font-size: 24px !important;
    height: 3em !important;
    border-radius: 10px !important;
    border: 1px solid rgba(0,0,0,0.3) !important;
}

</style>
""", unsafe_allow_html=True)


# ===================== 題庫載入（容錯版） =====================
@st.cache_data
def load_question_bank(xlsx_path="Zoology_Terms_Bilingual.xlsx"):
    """
    嘗試讀取 Excel 並自動對應「中文名欄」與「英文名欄」.
    支援常見欄位名稱（不分大小寫）：
      中文欄候選: Name, 中文, 名稱, Chinese, CN
      英文欄候選: English, 英文, Term, 英文名, EN, English term
    回傳 dict:
    {
      "ok": bool,
      "error": str,
      "bank": [ { "name":..., "english":...}, ... ],
      "debug_cols": [...]
    }
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

    def norm(s):
        return str(s).strip().lower()

    cols_norm = {norm(c): c for c in df.columns}

    cn_candidates = ["name", "中文", "名稱", "chinese", "cn"]
    en_candidates = ["english", "英文", "term", "英文名", "en", "english term"]

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
        return {
            "ok": False,
            "error": (
                "找不到必要欄位。\n"
                f"目前檔案欄位是：{list(df.columns)}\n"
                f"中文欄候選：{cn_candidates}\n"
                f"英文欄候選：{en_candidates}\n"
                "請把 Excel 兩欄名稱改成上述其中一個（例如：Name / English）。"
            ),
            "bank": [],
            "debug_cols": list(df.columns)
        }

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
                "name": cn_val,
                "english": en_val,
            })

    return {
        "ok": True,
        "error": "",
        "bank": bank_list,
        "debug_cols": list(df.columns)
    }

loaded = load_question_bank()
QUESTION_BANK = loaded["bank"]

if not loaded["ok"] or not QUESTION_BANK:
    st.error("⚠ 題庫讀取失敗或為空，請檢查 Excel 欄位。")
    st.stop()


# ===================== 常數 / 模式名稱 =====================
MAX_ROUNDS = 3
QUESTIONS_PER_ROUND = 10

MODE_1 = "模式一：中文 ➜ 英文（二選一）"
MODE_2 = "模式二：英文 ➜ 中文（二選一）"
MODE_3 = "模式三：中文 ➜ 英文（手寫輸入＋提示）"

ALL_MODES = [MODE_1, MODE_2, MODE_3]


# ===================== Session State 初始化 & 工具 =====================
def init_game_state():
    """初始化遊戲用的狀態 (不包含 user_name 等資料)"""
    st.session_state.round = 1                             # 第幾回合
    st.session_state.used_pairs = set()                    # 用過的英文單字，避免重複
    st.session_state.cur_round_qidx = []                   # 本回合抽到的題目 index
    st.session_state.cur_idx_in_round = 0                  # 本回合目前第幾題
    st.session_state.records = []                          # 紀錄：(round,prompt,chosen,correct_eng,correct_name,is_correct,opts)
    st.session_state.score_this_round = 0
    st.session_state.submitted = False                     # 目前這題是否已經交答案
    st.session_state.last_feedback = ""                    # HTML feedback
    st.session_state.answer_cache = ""                     # 模式三 text_input 暫存
    st.session_state.options_cache = {}                    # (qidx, mode) → 選項(cache)
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

def start_new_round():
    """抽一個新回合的題目清單"""
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
    """確保遊戲狀態存在且完整"""
    needed_keys = [
        "mode_locked",        # bool, 是否已經選定模式並進入遊戲
        "chosen_mode_label",  # str, 選到哪個模式
        "round",
        "used_pairs",
        "cur_round_qidx",
        "cur_idx_in_round",
        "records",
        "score_this_round",
        "submitted",
        "last_feedback",
        "answer_cache",
        "options_cache",
        "session_id",
        "user_name",
        "user_class",
        "user_seat",
    ]
    missing = any(k not in st.session_state for k in needed_keys)

    if missing:
        # 若還沒選模式，先建初始結構
        if "mode_locked" not in st.session_state:
            st.session_state.mode_locked = False
        if "chosen_mode_label" not in st.session_state:
            st.session_state.chosen_mode_label = None

        if "user_name" not in st.session_state:
            st.session_state.user_name = ""
        if "user_class" not in st.session_state:
            st.session_state.user_class = ""
        if "user_seat" not in st.session_state:
            st.session_state.user_seat = ""

        # 初始化遊戲本體
        init_game_state()
        # 如果之後有 round 但沒題目，等會進頁面時會再 start_new_round()

    # 如果 round 還有值、但題目列表是空的，補抽
    if st.session_state.mode_locked and st.session_state.round and not st.session_state.cur_round_qidx:
        start_new_round()


ensure_state_ready()


def get_options_for_q(qidx, mode_label):
    """
    產生/回傳兩個選項（模式一 & 模式二用）
    回傳格式：
    {
      "display": [...兩個選項字串...],
      "value":   [...一樣的...]
    }
    """
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


# ===================== 畫面元件：進度條卡 =====================
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


# ===================== 題目顯示（回傳 qidx, q, ("mc"/"text", user_answer, payload)） =====================
def render_question():
    cur_pos = st.session_state.cur_idx_in_round
    qidx = st.session_state.cur_round_qidx[cur_pos]
    q = QUESTION_BANK[qidx]
    mode_label = st.session_state.chosen_mode_label

    if mode_label == MODE_1:
        # 中文 -> 英文 (選擇題)
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
        # 英文 -> 中文 (選擇題)
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
        # MODE_3: 中文 -> 英文(手寫)
        prompt_name = q["name"].strip()
        target_eng = q["english"].strip()
        # 提示：首字 + … + 尾字
        hint = ""
        w = target_eng.strip()
        if len(w) <= 2:
            hint = w
        else:
            hint = f"{w[0]}…{w[-1]}"

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


# ===================== 答案提交 / 下一題邏輯 =====================
def handle_action(qidx, q, user_input):
    mode_label = st.session_state.chosen_mode_label
    correct_name = q["name"].strip()
    correct_eng  = q["english"].strip()

    ui_type, data, payload = user_input

    # 判斷正確與否
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
        # MODE_3：手寫英文
        typed_ans = data or ""
        chosen_label = typed_ans.strip()
        is_correct = (chosen_label.lower() == correct_eng.lower())

    # 第一次按：送出答案
    if not st.session_state.submitted:
        st.session_state.submitted = True

        # 紀錄一筆
        st.session_state.records.append((
            st.session_state.round,
            (q["name"] if mode_label != MODE_2 else q["english"]),
            chosen_label,
            correct_eng,
            correct_name,
            is_correct,
            (payload["display"] if (payload and "display" in payload) else None)
        ))

        # 產生回饋
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

        # 對於模式三，保留剛剛輸入的字，讓學生看得到
        if mode_label == MODE_3:
            st.session_state.answer_cache = chosen_label

        st.rerun()
        return

    # 第二次按：下一題
    else:
        # 避免該英文單字太快重複
        st.session_state.used_pairs.add(correct_eng)

        st.session_state.cur_idx_in_round += 1
        st.session_state.submitted = False
        st.session_state.last_feedback = ""
        st.session_state.answer_cache = ""

        # 檢查回合結束
        if st.session_state.cur_idx_in_round >= len(st.session_state.cur_round_qidx):
            # 判斷是否滿分 + 還有下一回合
            full_score = (
                st.session_state.score_this_round
                == len(st.session_state.cur_round_qidx)
            )
            has_more_rounds = (st.session_state.round < MAX_ROUNDS)

            if full_score and has_more_rounds:
                st.session_state.round += 1
                start_new_round()
            else:
                # 遊戲結束
                st.session_state.round = None

        st.rerun()
        return


# ===================== 畫面一：模式選擇頁（還沒鎖定模式時顯示） =====================
def render_mode_select_page():
    st.markdown("## 選擇練習模式")
    st.write("請選一種模式後開始作答：")

    chosen = st.radio(
        "練習模式",
        ALL_MODES,
        index=0,
        key="mode_pick_for_start"
    )

    st.session_state.user_name = st.text_input(
        "姓名", st.session_state.get("user_name", "")
    )
    st.session_state.user_class = st.text_input(
        "班級", st.session_state.get("user_class", "")
    )
    st.session_state.user_seat = st.text_input(
        "座號", st.session_state.get("user_seat", "")
    )

    if st.button("開始作答 ▶"):
        # 設定模式鎖定
        st.session_state.chosen_mode_label = chosen
        st.session_state.mode_locked = True

        # 重新初始化遊戲狀態（確保是乾淨第一回合）
        init_game_state()
        start_new_round()

        st.rerun()


# ===================== 畫面二：作答頁（模式已鎖定時顯示） =====================
def render_quiz_page():
    # 側邊欄 (sidebar)
    with st.sidebar:
        st.markdown("### 你的資訊")
        st.text_input(
            "姓名",
            st.session_state.get("user_name", ""),
            key="user_name"
        )
        st.text_input(
            "班級",
            st.session_state.get("user_class", ""),
            key="user_class"
        )
        st.text_input(
            "座號",
            st.session_state.get("user_seat", ""),
            key="user_seat"
        )

        st.markdown("---")
        st.write("模式已鎖定：")
        st.write(st.session_state.chosen_mode_label)

        # 重新開始整個遊戲（回到模式選擇頁）
        if st.button("🔄 重新開始（重新選模式）"):
            # 清掉 mode_locked，讓使用者回到模式選擇頁
            st.session_state.mode_locked = False
            st.session_state.chosen_mode_label = None
            init_game_state()
            st.rerun()

    # ===== 主內容 =====
    if st.session_state.round:
        # 進行中
        render_top_card()
        qidx, q, user_input = render_question()

        # 如果已經送出答案，顯示回饋
        if st.session_state.submitted and st.session_state.last_feedback:
            st.markdown(st.session_state.last_feedback, unsafe_allow_html=True)

        # 主按鈕：沒交→送出答案；交完→下一題
        action_label = "下一題" if st.session_state.submitted else "送出答案"
        if st.button(action_label, key="action_btn"):
            handle_action(qidx, q, user_input)

        # 題目提交後的複習區（選項雙語對照）
        if st.session_state.submitted and st.session_state.records:
            last = st.session_state.records[-1]
            # last = (round, prompt, chosen_label, correct_eng, correct_name, is_correct, opts_disp)
            _, _, _, correct_eng, correct_name, _, opts_disp = last
            mode_now = st.session_state.chosen_mode_label

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
        # 回合都打完了，顯示總結畫面
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

        if st.button("🔄 再玩一次（同模式）"):
            # 同一個模式下再來一輪
            init_game_state()
            start_new_round()
            st.rerun()

        if st.button("🧪 選別的模式"):
            # 回到模式選擇頁
            st.session_state.mode_locked = False
            st.session_state.chosen_mode_label = None
            init_game_state()
            st.rerun()


# ===================== 頁面路由 =====================
if not st.session_state.mode_locked:
    # 還沒選模式 → 顯示模式選擇頁
    render_mode_select_page()
else:
    # 已經選過模式 → 顯示正式答題頁
    render_quiz_page()
