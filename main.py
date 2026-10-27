
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta

st.set_page_config(
    page_title="Study Planner",
    page_icon="📚",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #f4f6fb;
}
.block-container {
    padding-top: 2rem;
    max-width: 1250px;
}
[data-testid="stMetric"] {
    background: white;
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #e7ebf3;
}
.task-card {
    background: white;
    padding: 16px;
    border-radius: 12px;
    border: 1px solid #e7ebf3;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

DATA_FILE = "study_tasks.json"

def load_tasks():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []

def save_tasks():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.tasks, f, ensure_ascii=False, indent=2)

if "tasks" not in st.session_state:
    st.session_state.tasks = load_tasks()

if "next_id" not in st.session_state:
    st.session_state.next_id = max(
        [t.get("id", 0) for t in st.session_state.tasks],
        default=0
    ) + 1

def days_left(deadline):
    return (date.fromisoformat(deadline) - date.today()).days

def get_status(task):
    if task["completed"]:
        return "완료"
    remaining = days_left(task["deadline"])
    if remaining < 0:
        return "기한 지남"
    if remaining == 0:
        return "오늘 마감"
    if remaining <= 3:
        return "마감 임박"
    return "진행 중"

def sort_key(task):
    return (
        task["deadline"],
        -task["importance"],
        task["id"]
    )

st.title("Study Planner")
st.caption("시험과 수행평가 일정을 한곳에서 관리하세요.")
st.write(f"오늘 날짜: {date.today().strftime('%Y년 %m월 %d일')}")

tasks = st.session_state.tasks
total = len(tasks)
completed = sum(t["completed"] for t in tasks)
remaining = total - completed
urgent = sum(
    not t["completed"] and 0 <= days_left(t["deadline"]) <= 3
    for t in tasks
)
rate = round(completed / total * 100) if total else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("전체 일정", f"{total}개")
c2.metric("미완료 일정", f"{remaining}개")
c3.metric("3일 이내 마감", f"{urgent}개")
c4.metric("완료율", f"{rate}%")

st.progress(rate / 100 if total else 0)
st.caption(f"완료 {completed}개 / 전체 {total}개")

st.divider()

left, right = st.columns([1, 1.5], gap="large")

with left:
    st.subheader("일정 등록")

    with st.form("task_form", clear_on_submit=True):
        subject = st.text_input("과목", placeholder="예: 수학")
        name = st.text_input(
            "시험 또는 수행평가 이름",
            placeholder="예: 함수 단원 시험"
        )
        deadline = st.date_input(
            "마감일",
            value=date.today() + timedelta(days=1)
        )
        importance = st.selectbox(
            "중요도",
            options=[3, 2, 1],
            format_func=lambda x: {
                3: "높음",
                2: "보통",
                1: "낮음"
            }[x]
        )
        submitted = st.form_submit_button(
            "일정 등록하기",
            use_container_width=True
        )

    if submitted:
        if not subject.strip() or not name.strip():
            st.error("과목과 일정 이름을 모두 입력해 주세요.")
        elif deadline < date.today():
            st.error("오늘보다 이전 날짜는 선택할 수 없습니다.")
        else:
            new_task = {
                "id": st.session_state.next_id,
                "subject": subject.strip(),
                "name": name.strip(),
                "deadline": deadline.isoformat(),
                "importance": importance,
                "completed": False
            }
            st.session_state.tasks.append(new_task)
            st.session_state.next_id += 1
            save_tasks()
            st.success("일정이 등록되었습니다.")
            st.rerun()

    st.subheader("우선순위 추천")
    pending = sorted(
        [t for t in tasks if not t["completed"]],
        key=sort_key
    )

    if pending:
        first = pending[0]
        days = days_left(first["deadline"])
        if days < 0:
            message = f"마감일이 {abs(days)}일 지났습니다. 먼저 확인하세요."
        elif days == 0:
            message = "오늘 마감입니다. 우선적으로 확인하세요."
        elif days <= 3:
            message = f"마감까지 {days}일 남았습니다."
        else:
            message = f"마감까지 {days}일 남았습니다. 미리 준비하세요."

        st.info(
            f"**추천 일정: {first['subject']} - {first['name']}**\n\n"
            f"{message}\n\n"
            f"중요도: {{3: '높음', 2: '보통', 1: '낮음'}[first['importance']]}"
        )
    else:
        st.success("미완료 일정이 없습니다.")

with right:
    st.subheader("일정 목록")

    filter_option = st.selectbox(
        "일정 필터",
        ["전체", "미완료", "마감 임박", "완료", "기한 지남"]
    )
    query = st.text_input("일정 검색", placeholder="과목 또는 일정 이름")

    filtered = []
    for task in tasks:
        status = get_status(task)

        if filter_option == "미완료" and task["completed"]:
            continue
        if filter_option == "마감 임박" and status not in ("오늘 마감", "마감 임박"):
            continue
        if filter_option == "완료" and not task["completed"]:
            continue
        if filter_option == "기한 지남" and status != "기한 지남":
            continue

        if query.strip():
            search_text = (task["subject"] + " " + task["name"]).lower()
            if query.strip().lower() not in search_text:
                continue

        filtered.append(task)

    filtered.sort(key=sort_key)

    if not filtered:
        st.info("표시할 일정이 없습니다.")
    else:
        for task in filtered:
            with st.container(border=True):
                col_a, col_b = st.columns([4, 1])

                with col_a:
                    st.markdown(f"**{task['name']}**")
                    st.caption(
                        f"{task['subject']} · "
                        f"마감일 {task['deadline']}"
                    )

                    status = get_status(task)
                    days = days_left(task["deadline"])

                    if status == "완료":
                        st.success("완료")
                    elif status == "기한 지남":
                        st.error(f"기한 지남 · {abs(days)}일")
                    elif status == "오늘 마감":
                        st.warning("오늘 마감")
                    elif status == "마감 임박":
                        st.warning(f"D-{days}")
                    else:
                        st.info(f"D-{days} · 진행 중")

                    st.caption(
                        "중요도: " +
                        {3: "높음", 2: "보통", 1: "낮음"}[task["importance"]]
                    )

                with col_b:
                    is_done = st.checkbox(
                        "완료",
                        value=task["completed"],
                        key=f"done_{task['id']}"
                    )
                    if is_done != task["completed"]:
                        task["completed"] = is_done
                        save_tasks()
                        st.rerun()

                    if st.button(
                        "삭제",
                        key=f"delete_{task['id']}"
                    ):
                        st.session_state.tasks = [
                            t for t in st.session_state.tasks
                            if t["id"] != task["id"]
                        ]
                        save_tasks()
                        st.rerun()

st.divider()

st.subheader("과목별 일정 현황")

if tasks:
    df = pd.DataFrame(tasks)
    chart_data = df.groupby("subject").size().sort_values(ascending=False)
    st.bar_chart(chart_data)
else:
    st.caption("일정을 등록하면 과목별 현황이 표시됩니다.")

with st.expander("데이터 백업 및 복원"):
    st.write("일정 데이터를 JSON 파일로 다운로드하거나 이전 백업을 불러올 수 있습니다.")

    backup = json.dumps(
        tasks,
        ensure_ascii=False,
        indent=2
    )

    st.download_button(
        "일정 백업 다운로드",
        data=backup,
        file_name="study_tasks_backup.json",
        mime="application/json",
        use_container_width=True
    )

    uploaded = st.file_uploader(
        "백업 파일 선택",
        type=["json"]
    )

    if uploaded is not None:
        if st.button("백업 불러오기"):
            try:
                imported = json.load(uploaded)

                valid = isinstance(imported, list) and all(
                    isinstance(t, dict)
                    and isinstance(t.get("subject"), str)
                    and isinstance(t.get("name"), str)
                    and isinstance(t.get("deadline"), str)
                    and isinstance(t.get("completed"), bool)
                    and t.get("importance") in (1, 2, 3)
                    and isinstance(t.get("id"), int)
                    for t in imported
                )

                if not valid:
                    st.error("백업 파일의 형식이 올바르지 않습니다.")
                else:
                    for t in imported:
                        date.fromisoformat(t["deadline"])

                    st.session_state.tasks = imported
                    st.session_state.next_id = max(
                        [t["id"] for t in imported],
                        default=0
                    ) + 1
                    save_tasks()
                    st.success("백업을 불러왔습니다.")
                    st.rerun()
            except (ValueError, json.JSONDecodeError, TypeError):
                st.error("파일을 읽을 수 없습니다. 올바른 백업인지 확인하세요.")

    if st.button("모든 일정 삭제", type="secondary"):
        st.session_state.confirm_clear = True

    if st.session_state.get("confirm_clear", False):
        st.warning("정말 모든 일정을 삭제할까요?")
        yes, no = st.columns(2)

        if yes.button("삭제 확인", type="primary"):
            st.session_state.tasks = []
            st.session_state.next_id = 1
            st.session_state.confirm_clear = False
            save_tasks()
            st.rerun()

        if no.button("취소"):
            st.session_state.confirm_clear = False
            st.rerun()

st.caption(
    "Study Planner · 시험 및 수행평가 일정 관리 프로그램"
)
