import streamlit as st
import pandas as pd
import re
from datetime import datetime
from supabase import create_client, Client

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# ========================
# 配置
# ========================
# CSV_PATH = "/Users/zhouzhou/Documents/WenyanProject/extracted_questions.csv"
CSV_PATH = "extracted_questions.csv"

# 题目数量配置
NUM_SINGLE = 30      # 单选题数量
NUM_MULTIPLE = 20    # 多选题数量
NUM_TRUE_FALSE = 10  # 判断题数量

SINGLE_SCORE = 1     # 单选题分值
MULTIPLE_SCORE = 2   # 多选题分值

# ========================
# 工具函数：判断是否为判断题
# ========================
def is_true_false_question(q: dict) -> bool:
    """判断是否为判断题：A 是“对/正确”，B 是“错/错误”"""
    opt_a = str(q.get("option_A", "")).strip()
    opt_b = str(q.get("option_B", "")).strip()

    # 提取选项文本（去掉 "A. " 前缀）
    content_a = re.sub(r'^[A-Za-z]\.\s*', '', opt_a, flags=re.IGNORECASE)
    content_b = re.sub(r'^[A-Za-z]\.\s*', '', opt_b, flags=re.IGNORECASE)

    a_is_true = any(word in content_a for word in ["对", "正确", "是"])
    b_is_false = any(word in content_b for word in ["错", "错误", "否"])

    return a_is_true and b_is_false

# ========================
# 加载并分类题目
# ========================
@st.cache_data
def load_and_sort_questions():
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        st.error(f"❌ 题库文件 '{CSV_PATH}' 未找到！请确保它在项目根目录。")
        st.stop()

    # 清理 answer 列
    df["answer"] = df["answer"].astype(str).str.strip().str.upper()
    df = df[df["answer"].str.len() > 0].copy()

    single_list = []
    multiple_list = []
    true_false_list = []

    for q in df.to_dict("records"):
        ans_len = len(q["answer"])
        if is_true_false_question(q):
            true_false_list.append(q)
        elif ans_len == 1:
            single_list.append(q)
        elif ans_len >= 2:
            multiple_list.append(q)

    # 抽样（内部打乱）
    import random
    random.seed(42)
    random.shuffle(single_list)
    random.shuffle(multiple_list)
    random.shuffle(true_false_list)

    final_questions = (
        single_list[:min(NUM_SINGLE, len(single_list))] +
        multiple_list[:min(NUM_MULTIPLE, len(multiple_list))] +
        true_false_list[:min(NUM_TRUE_FALSE, len(true_false_list))]
    )

    return {
        "questions": final_questions,
        "break_single": min(NUM_SINGLE, len(single_list)),
        "break_multiple": min(NUM_SINGLE, len(single_list)) + min(NUM_MULTIPLE, len(multiple_list))
    }

# ========================
# 显示单题（自动判断题型）
# ========================
def display_question(idx: int, q: dict):
    st.markdown(f"### 第 {idx + 1} 题")
    st.write(q["stem"])

    # 收集非空选项 A~F
    options_map = {}
    for label in ["A", "B", "C", "D", "E", "F"]:
        opt_text = q.get(f"option_{label}", "")
        if isinstance(opt_text, str) and opt_text.strip():
            options_map[label] = opt_text

    if not options_map:
        st.warning("该题无有效选项")
        return None

    option_labels = list(options_map.values())
    true_answer_str = str(q.get("answer", "")).strip().upper()
    is_multiple = len(true_answer_str) > 1

    if is_multiple:
        selected = st.multiselect(
            label=" ",
            options=option_labels,
            key=f"q_{idx}",
            label_visibility="collapsed"
        )
        user_choice = [s.split(".")[0] for s in selected] if selected else []
    else:
        selected = st.radio(
            label=" ",
            options=option_labels,
            index=None,
            key=f"q_{idx}",
            label_visibility="collapsed"
        )
        user_choice = selected.split(".")[0] if selected else None

    return user_choice

# ========================
# 主应用逻辑
# ========================
st.set_page_config(page_title="闻堰街道社区卫生服务中心", layout="wide")
st.title("📚 公卫月度在线考试系统")

# --- 步骤 1：输入姓名和学号 ---
if "name" not in st.session_state or "id" not in st.session_state:
    st.subheader("👤 请先填写个人信息")
    name_input = st.text_input("姓名", value=st.session_state.get("name", ""))
    id_input = st.text_input("身份证号", value=st.session_state.get("id", ""))
    
    if st.button("✅ 开始考试"):
        if name_input.strip() and id_input.strip():
            st.session_state.name = name_input.strip()
            st.session_state.id = id_input.strip()
            st.rerun()
        else:
            st.warning("请输入姓名和身份证号！")
    st.stop()

# --- 步骤 2：加载题目 ---
if "initialized" not in st.session_state:
    result = load_and_sort_questions()
    
    questions = result["questions"]
    # 安全获取分界点，避免 KeyError
    break_single = result.get("break_single", 0)
    break_multiple = result.get("break_multiple", len(questions))

    st.session_state.questions = questions
    st.session_state.user_answers = [None] * len(questions)
    st.session_state.submitted = False
    
    # 👇 关键：确保这两个属性一定存在！
    st.session_state.break_single = break_single
    st.session_state.break_multiple = break_multiple
    
    st.session_state.initialized = True

total_q = len(st.session_state.questions)
st.write(f"共 {total_q} 题 | 单选题每题 {SINGLE_SCORE} 分，多选题/判断题每题 {MULTIPLE_SCORE} 分")

# --- 步骤 3：答题界面 ---
if not st.session_state.submitted:
    for i, q in enumerate(st.session_state.questions):
        # 分组标题
        if i == 0:
            st.markdown("## 📝 第一部分：单项选择题")
        elif i == st.session_state.break_single:
            st.markdown("---\n## 📝 第二部分：多项选择题")
        elif i == st.session_state.break_multiple:
            st.markdown("---\n## 📝 第三部分：判断题")

        ans = display_question(i, q)
        st.session_state.user_answers[i] = ans
        st.divider()

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("✅ 提交答卷", type="primary"):
            st.session_state.submitted = True
            st.rerun()

# --- 步骤 4：评分与结果 ---
if st.session_state.submitted:
    total_score = 0
    correct_count = 0
    details = []

    for i, (q, user_ans) in enumerate(zip(st.session_state.questions, st.session_state.user_answers)):
        true_ans_str = str(q.get("answer", "")).strip().upper()
        true_set = set(true_ans_str)

        if isinstance(user_ans, list):
            user_set = set(user_ans)
        elif isinstance(user_ans, str):
            user_set = {user_ans}
        else:
            user_set = set()

        is_correct = (user_set == true_set)
        score = MULTIPLE_SCORE if len(true_set) > 1 else SINGLE_SCORE
        if not is_correct:
            score = 0

        total_score += score
        if is_correct:
            correct_count += 1

        details.append({
            "题号": i + 1,
            "正确": "✅" if is_correct else "❌",
            "标准答案": "".join(sorted(true_set)),
            "你的答案": "".join(sorted(user_set)) if user_set else "未答"
        })

    # 显示总分
    st.header("🎉 考试结果")
    

    # 生成 CSV 并提供下载（适合 Streamlit Cloud）
    scores_df = pd.DataFrame([{
        "姓名": st.session_state.name,
        "身份证号": st.session_state.id,
        "总分": total_score,
        "答题时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    st.markdown(st.session_state.name)
    st.markdown(st.session_state.id)
    st.markdown(f'答题时间:{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    st.metric("总得分", f"{total_score} 分")
    
    # 答题详情
    with st.expander("📊 查看答题详情"):
        st.dataframe(pd.DataFrame(details), use_container_width=True)

        try:
    # 插入成绩
            response = supabase.table("exam_scores").insert({
                "name": st.session_state.name,
                "id": st.session_state.id,
                "score": total_score,
                "datetime": datetime.now().isoformat()
            }).execute()

            if response.status_code == 201:
                st.success("✅ 成绩已成功提交到数据库！")
            else:
                st.error(f"❌ 提交失败：{response.text}")
        except Exception as e:
            st.error(f"❌ 数据库连接异常：{e}")


    # # ================================
    # # 👨‍🏫 教师统计面板（需密码）
    # # ================================
    with st.expander("🔒 教师入口：查看/编辑成绩"):
        pwd = st.text_input("输入管理密码", type="password", key="admin_pwd")
        if pwd == "admin123":
            try:
                response = supabase.table("exam_scores").select("*").execute()
                df = pd.DataFrame(response.data)
                if not df.empty:
                    st.dataframe(df)
                    # 显示统计...
                else:
                    st.info("暂无成绩")
            except Exception as e:
                st.error(f"加载失败：{e}")