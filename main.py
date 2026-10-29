
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta, datetime

# =========================================================
# 1. 기본 설정
# =========================================================
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
    max-width: 1400px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e5e9f2;
    border-radius: 14px;
    padding: 16px;
}
.panel-title {
    font-size: 22px;
    font-weight: 750;
    margin-bottom: 8px;
}
.small-note {
    color: #788399;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

TASK_FILE = "study_tasks.json"
LOG_FILE = "study_logs.json"

DEFAULT_STEPS = [
    "개념 정리",
    "문제 풀이",
    "오답 정리",
    "최종 복습"
]

# =========================================================
# 2. 데이터 불러오기 및 저장
# =========================================================
def read_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def normalize_tasks(data):
    if not isinstance(data, list):
        return []

    result = []

    for task in data:
        if not isinstance(task, dict):
            continue

        try:
            task_id = int(task["id"])
            subject = str(task["subject"]).strip()
            name = str(task["name"]).strip()
            deadline = str(task["deadline"])
            date.fromisoformat(deadline)
            importance = int(task["importance"])

            if not subject or not name or importance not in (1, 2, 3):
                continue

            if not isinstance(task.get("completed", False), bool):
                continue

            raw_steps = task.get("checklist", DEFAULT_STEPS)
            if not isinstance(raw_steps, list):
                raw_steps = DEFAULT_STEPS

            checklist = []
            for step in raw_steps:
                if isinstance(step, dict) and isinstance(
                    step.get("done", False), bool
                ):
                    checklist.append({
                        "name": str(step.get("name", "준비 단계")),
                        "done": step.get("done", False)
                    })

            if not checklist:
                checklist = [
                    {"name": name, "done": False}
                    for name in DEFAULT_STEPS
                ]

            completed_at = task.get("completed_at")
            if not isinstance(completed_at, str):
                completed_at = None

            result.append({
                "id": task_id,
                "subject": subject,
                "name": name,
                "deadline": deadline,
                "importance": importance,
                "completed": task.get("completed", False),
                "completed_at": completed_at,
                "checklist": checklist
            })
        except (KeyError, TypeError, ValueError):
            continue

    return result


def normalize_logs(data):
    if not isinstance(data, list):
        return []

    result = []

    for log in data:
        if not isinstance(log, dict):
            continue

        try:
            log_id = int(log["id"])
            subject = str(log["subject"]).strip()
            minutes = int(log["minutes"])
            log_date = str(log["date"])
            date.fromisoformat(log_date)
            note = str(log.get("note", ""))

            if not subject or not (1 <= minutes <= 1440):
                continue

            result.append({
                "id": log_id,
                "subject": subject,
                "minutes": minutes,
                "date": log_date,
                "note": note
            })
        except (KeyError, TypeError, ValueError):
            continue

    return result


def save_data():
    try:
        with open(TASK_FILE, "w", encoding="utf-8") as file:
            json.dump(
                st.session_state.tasks,
                file,
                ensure_ascii=False,
                indent=2
            )

        with open(LOG_FILE, "w", encoding="utf-8") as file:
            json.dump(
                st.session_state.study_logs,
                file,
                ensure_ascii=False,
                indent=2
            )
        return True

    except OSError:
        st.warning(
            "파일 저장에 실패했습니다. 중요한 데이터는 백업 기능으로 "
            "다운로드해 주세요."
        )
        return False


if "tasks" not in st.session_state:
    st.session_state.tasks = normalize_tasks(
        read_json(TASK_FILE, [])
    )

if "study_logs" not in st.session_state:
    st.session_state.study_logs = normalize_logs(
        read_json(LOG_FILE, [])
    )

if "next_task_id" not in st.session_state:
    st.session_state.next_task_id = max(
        [t["id"] for t in st.session_state.tasks],
        default=0
    ) + 1

if "next_log_id" not in st.session_state:
    st.session_state.next_log_id = max(
        [log["id"] for log in st.session_state.study_logs],
        default=0
    ) + 1

tasks = st.session_state.tasks
study_logs = st.session_state.study_logs

# =========================================================
# 3. 공통 함수
# =========================================================
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


def format_minutes(minutes):
    hours = minutes // 60
    mins = minutes % 60

    if hours and mins:
        return f"{hours}시간 {mins}분"
    if hours:
        return f"{hours}시간"

    return f"{mins}분"


def weekly_logs():
    start = date.today() - timedelta(days=6)
    end = date.today()

    return [
        log for log in study_logs
        if start <= date.fromisoformat(log["date"]) <= end
    ]


def importance_text(value):
    return {3: "높음", 2: "보통", 1: "낮음"}.get(value, "보통")


def valid_checklist(task):
    checklist = task.get("checklist", [])

    if not checklist:
        return 0

    return sum(step["done"] for step in checklist)


# =========================================================
# 4. 제목 및 대시보드
# =========================================================
st.title("Study Planner")
st.caption("시험 준비부터 공부 시간 분석까지, 학습 과정을 관리하세요.")

st.write(
    f"오늘 날짜: {date.today().strftime('%Y년 %m월 %d일')}"
)

total = len(tasks)
completed = sum(task["completed"] for task in tasks)
unfinished = total - completed

urgent = sum(
    not task["completed"]
    and 0 <= days_left(task["deadline"]) <= 3
    for task in tasks
)

completion_rate = round(completed / total * 100) if total else 0

today_minutes = sum(
    log["minutes"]
    for log in study_logs
    if log["date"] == date.today().isoformat()
)

week_minutes = sum(
    log["minutes"] for log in weekly_logs()
)

c1, c2, c3, c4 = st.columns(4)

c1.metric("전체 일정", f"{total}개")
c2.metric("미완료 일정", f"{unfinished}개")
c3.metric("마감 임박", f"{urgent}개")
c4.metric("일정 완료율", f"{completion_rate}%")

c5, c6, c7 = st.columns(3)

c5.metric("오늘 공부 시간", format_minutes(today_minutes))
c6.metric("최근 7일 공부 시간", format_minutes(week_minutes))
c7.metric("최근 7일 공부 기록", f"{len(weekly_logs())}건")

st.progress(completion_rate / 100 if total else 0)
st.caption(f"완료한 일정 {completed}개 / 전체 일정 {total}개")

st.divider()

# =========================================================
# 5. 일정 등록
# =========================================================
st.header("1. 시험 및 수행평가 일정")

left, right = st.columns([1, 1.5], gap="large")

with left:
    st.subheader("새 일정 등록")

    with st.form("task_form", clear_on_submit=True):
        subject = st.text_input(
            "과목",
            placeholder="예: 수학"
        )

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
            format_func=importance_text
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
                "id": st.session_state.next_task_id,
                "subject": subject.strip(),
                "name": name.strip(),
                "deadline": deadline.isoformat(),
                "importance": importance,
                "completed": False,
                "completed_at": None,
                "checklist": [
                    {"name": step, "done": False}
                    for step in DEFAULT_STEPS
                ]
            }

            st.session_state.tasks.append(new_task)
            st.session_state.next_task_id += 1
            save_data()
            st.success("일정이 등록되었습니다.")
            st.rerun()

with right:
    st.subheader("일정 검색 및 관리")

    filter_option = st.selectbox(
        "일정 필터",
        ["전체", "미완료", "마감 임박", "기한 지남", "완료"],
        key="task_filter"
    )

    query = st.text_input(
        "과목 또는 일정 검색",
        placeholder="검색어를 입력하세요.",
        key="task_search"
    )

    filtered_tasks = []

    for task in tasks:
        status = get_status(task)

        if filter_option == "미완료" and task["completed"]:
            continue

        if filter_option == "마감 임박" and status not in (
            "오늘 마감", "마감 임박"
        ):
            continue

        if filter_option == "기한 지남" and status != "기한 지남":
            continue

        if filter_option == "완료" and not task["completed"]:
            continue

        search_text = (
            task["subject"] + " " + task["name"]
        ).lower()

        if query.strip().lower() not in search_text:
            continue

        filtered_tasks.append(task)

    filtered_tasks.sort(key=sort_key)

    if not filtered_tasks:
        st.info("표시할 일정이 없습니다.")

    for task in filtered_tasks:
        with st.container(border=True):
            st.markdown(f"**{task['name']}**")
            st.caption(
                f"{task['subject']} · 마감일 {task['deadline']}"
            )

            status = get_status(task)
            remaining_days = days_left(task["deadline"])

            if status == "완료":
                st.success("완료")
            elif status == "기한 지남":
                st.error(f"기한이 {abs(remaining_days)}일 지났습니다.")
            elif status == "오늘 마감":
                st.warning("오늘 마감")
            elif status == "마감 임박":
                st.warning(f"D-{remaining_days}")
            else:
                st.info(f"D-{remaining_days} · 진행 중")

            st.caption(f"중요도: {importance_text(task['importance'])}")

            checkbox_col, delete_col = st.columns([3, 1])

            with checkbox_col:
                is_done = st.checkbox(
                    "일정 완료",
                    value=task["completed"],
                    key=f"task_done_{task['id']}"
                )

                if is_done != task["completed"]:
                    task["completed"] = is_done
                    task["completed_at"] = (
                        date.today().isoformat() if is_done else None
                    )
                    save_data()
                    st.rerun()

            with delete_col:
                if st.button(
                    "삭제",
                    key=f"task_delete_{task['id']}"
                ):
                    st.session_state.tasks = [
                        t for t in tasks if t["id"] != task["id"]
                    ]
                    save_data()
                    st.rerun()

# =========================================================
# 6. 기능 1: 시험 준비 단계별 체크리스트
# =========================================================
st.divider()
st.header("2. 시험 준비 체크리스트")
st.caption(
    "시험별로 개념 정리, 문제 풀이, 오답 정리, 최종 복습의 진행 상황을 관리합니다."
)

if not tasks:
    st.info("먼저 시험 또는 수행평가 일정을 등록해 주세요.")
else:
    checklist_task = st.selectbox(
        "준비 과정을 확인할 일정",
        options=tasks,
        format_func=lambda t: f"{t['subject']} - {t['name']}",
        key="checklist_task_select"
    )

    checklist = checklist_task["checklist"]
    checked_count = valid_checklist(checklist)
    total_steps = len(checklist)
    checklist_rate = (
        round(checked_count / total_steps * 100)
        if total_steps else 0
    )

    st.progress(checklist_rate / 100 if total_steps else 0)
    st.write(
        f"준비 진행률: **{checklist_rate}%** "
        f"({checked_count}/{total_steps}단계 완료)"
    )

    for index, step in enumerate(checklist):
        check_value = st.checkbox(
            step["name"],
            value=step["done"],
            key=f"step_{checklist_task['id']}_{index}"
        )

        if check_value != step["done"]:
            step["done"] = check_value

            # 모든 준비 단계를 완료하면 해당 일정도 완료 처리
            if checklist and all(s["done"] for s in checklist):
                checklist_task["completed"] = True
                checklist_task["completed_at"] = date.today().isoformat()
            elif not all(s["done"] for s in checklist):
                checklist_task["completed"] = False
                checklist_task["completed_at"] = None

            save_data()
            st.rerun()

    with st.form("add_step_form", clear_on_submit=True):
        new_step_name = st.text_input(
            "추가 준비 단계",
            placeholder="예: 선생님께 질문하기"
        )
        add_step = st.form_submit_button("준비 단계 추가")

    if add_step:
        if not new_step_name.strip():
            st.error("추가할 단계 이름을 입력해 주세요.")
        else:
            checklist.append({
                "name": new_step_name.strip(),
                "done": False
            })
            save_data()
            st.rerun()

    removable_steps = [
        (index, step["name"])
        for index, step in enumerate(checklist)
    ]

    if removable_steps:
        with st.expander("준비 단계 삭제"):
            remove_index = st.selectbox(
                "삭제할 단계",
                options=[item[0] for item in removable_steps],
                format_func=lambda i: removable_steps[i][1],
                key="remove_step_select"
            )

            if st.button("선택한 단계 삭제"):
                checklist.pop(remove_index)

                if checklist and all(step["done"] for step in checklist):
                    checklist_task["completed"] = True
                    checklist_task["completed_at"] = date.today().isoformat()
                else:
                    checklist_task["completed"] = False
                    checklist_task["completed_at"] = None

                save_data()
                st.rerun()

# =========================================================
# 7. 기능 4: 공부 시간 기록
# =========================================================
st.divider()
st.header("3. 공부 시간 기록")
st.caption(
    "실제로 공부한 시간을 기록하고 과목별 학습량을 확인합니다."
)

time_left, time_right = st.columns([1, 1.5], gap="large")

with time_left:
    st.subheader("새 공부 기록")

    existing_subjects = sorted(set(
        task["subject"] for task in tasks
    ))

    with st.form("study_log_form", clear_on_submit=True):
        subject_options = ["직접 입력"] + existing_subjects

        chosen_subject = st.selectbox(
            "과목 선택",
            subject_options
        )

        custom_subject = ""
        if chosen_subject == "직접 입력":
            custom_subject = st.text_input(
                "과목 이름",
                placeholder="예: 과학"
            )

        study_date = st.date_input(
            "공부한 날짜",
            value=date.today(),
            max_value=date.today()
        )

        study_hours = st.number_input(
            "공부 시간(시간)",
            min_value=0,
            max_value=24,
            value=1,
            step=1
        )

        study_minutes = st.selectbox(
            "추가 공부 시간(분)",
            [0, 15, 30, 45]
        )

        note = st.text_input(
            "공부 내용",
            placeholder="예: 2단원 개념 정리"
        )

        save_log = st.form_submit_button(
            "공부 기록 저장",
            use_container_width=True
        )

    if save_log:
        chosen_name = (
            custom_subject.strip()
            if chosen_subject == "직접 입력"
            else chosen_subject
        )

        total_minutes = int(study_hours * 60 + study_minutes)

        if not chosen_name:
            st.error("과목을 입력해 주세요.")
        elif total_minutes <= 0:
            st.error("공부 시간은 1분 이상이어야 합니다.")
        else:
            new_log = {
                "id": st.session_state.next_log_id,
                "subject": chosen_name,
                "minutes": total_minutes,
                "date": study_date.isoformat(),
                "note": note.strip()
            }

            st.session_state.study_logs.append(new_log)
            st.session_state.next_log_id += 1
            save_data()
            st.success("공부 시간이 기록되었습니다.")
            st.rerun()

with time_right:
    st.subheader("최근 공부 기록")

    if not study_logs:
        st.info("아직 공부 기록이 없습니다.")
    else:
        recent_logs = sorted(
            study_logs,
            key=lambda log: (log["date"], log["id"]),
            reverse=True
        )

        for log in recent_logs[:10]:
            with st.container(border=True):
                col_a, col_b = st.columns([4, 1])

                with col_a:
                    st.markdown(f"**{log['subject']}**")
                    st.caption(
                        f"{log['date']} · "
                        f"{format_minutes(log['minutes'])}"
                    )
                    if log["note"]:
                        st.write(log["note"])

                with col_b:
                    if st.button(
                        "삭제",
                        key=f"log_delete_{log['id']}"
                    ):
                        st.session_state.study_logs = [
                            item for item in study_logs
                            if item["id"] != log["id"]
                        ]
                        save_data()
                        st.rerun()

        if len(recent_logs) > 10:
            st.caption("최근 10건만 표시했습니다.")

# =========================================================
# 8. 기능 5: 주간 학습 보고서
# =========================================================
st.divider()
st.header("4. 주간 학습 보고서")
st.caption("오늘을 포함한 최근 7일간의 공부 시간과 일정 진행 상황입니다.")

start_date = date.today() - timedelta(days=6)
end_date = date.today()

week_logs = weekly_logs()

week_total_minutes = sum(
    log["minutes"] for log in week_logs
)

daily_data = []

for offset in range(7):
    current_date = start_date + timedelta(days=offset)

    minutes = sum(
        log["minutes"]
        for log in week_logs
        if log["date"] == current_date.isoformat()
    )

    daily_data.append({
        "날짜": current_date.strftime("%m-%d"),
        "공부 시간(분)": minutes
    })

daily_df = pd.DataFrame(daily_data)

w1, w2, w3, w4 = st.columns(4)

w1.metric(
    "7일간 총 공부 시간",
    format_minutes(week_total_minutes)
)

w2.metric(
    "하루 평균 공부 시간",
    format_minutes(round(week_total_minutes / 7))
)

w3.metric(
    "공부 기록 수",
    f"{len(week_logs)}건"
)

completed_this_week = sum(
    1 for task in tasks
    if task["completed_at"]
    and start_date.isoformat() <= task["completed_at"] <= end_date.isoformat()
)

w4.metric(
    "이번 주 완료 일정",
    f"{completed_this_week}개"
)

st.subheader("날짜별 공부 시간")
st.bar_chart(
    daily_df.set_index("날짜"),
    y="공부 시간(분)"
)

st.subheader("과목별 공부 시간")

if week_logs:
    subject_minutes = {}

    for log in week_logs:
        subject_minutes[log["subject"]] = (
            subject_minutes.get(log["subject"], 0) + log["minutes"]
        )

    subject_df = pd.DataFrame([
        {
            "과목": subject,
            "공부 시간(분)": minutes
        }
        for subject, minutes in sorted(
            subject_minutes.items(),
            key=lambda item: item[1],
            reverse=True
        )
    ])

    st.bar_chart(
        subject_df.set_index("과목"),
        y="공부 시간(분)"
    )

    st.dataframe(
        subject_df.assign(
            공부시간_읽기쉬운형식=subject_df["공부 시간(분)"].apply(
                format_minutes
            )
        ).rename(columns={
            "공부시간_읽기쉬운형식": "공부 시간"
        })[["과목", "공부 시간"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("최근 7일간의 공부 기록을 입력하면 과목별 분석이 표시됩니다.")

st.subheader("미완료 일정 분석")

pending_tasks = sorted(
    [task for task in tasks if not task["completed"]],
    key=sort_key
)

if pending_tasks:
    pending_rows = []

    for task in pending_tasks:
        pending_rows.append({
            "과목": task["subject"],
            "일정": task["name"],
            "마감일": task["deadline"],
            "남은 날짜": days_left(task["deadline"]),
            "중요도": importance_text(task["importance"]),
            "상태": get_status(task)
        })

    st.dataframe(
        pd.DataFrame(pending_rows),
        use_container_width=True,
        hide_index=True
    )

    first = pending_tasks[0]
    days = days_left(first["deadline"])

    st.info(
        f"우선 추천: **{first['subject']} - {first['name']}**\n\n"
        f"마감일까지 {days}일 남았습니다."
        if days >= 0
        else f"우선 추천: **{first['subject']} - {first['name']}**\n\n"
        f"마감일이 {abs(days)}일 지났습니다."
    )
else:
    st.success("미완료 일정이 없습니다.")

# =========================================================
# 9. 데이터 백업 및 복원
# =========================================================
st.divider()
st.header("5. 데이터 백업 및 복원")

backup_data = {
    "version": 2,
    "tasks": tasks,
    "study_logs": study_logs
}

backup_json = json.dumps(
    backup_data,
    ensure_ascii=False,
    indent=2
)

st.download_button(
    "전체 데이터 백업 다운로드",
    data=backup_json,
    file_name=f"study_planner_backup_{date.today().isoformat()}.json",
    mime="application/json",
    use_container_width=True
)

uploaded_file = st.file_uploader(
    "이전에 저장한 백업 파일 불러오기",
    type=["json"]
)

if uploaded_file is not None:
    if st.button("백업 데이터 복원"):
        try:
            imported = json.load(uploaded_file)

            if isinstance(imported, list):
                imported_tasks = normalize_tasks(imported)
                imported_logs = []
            elif isinstance(imported, dict):
                imported_tasks = normalize_tasks(
                    imported.get("tasks", [])
                )
                imported_logs = normalize_logs(
                    imported.get("study_logs", [])
                )
            else:
                raise ValueError("지원하지 않는 백업 형식입니다.")

            st.session_state.tasks = imported_tasks
            st.session_state.study_logs = imported_logs

            st.session_state.next_task_id = max(
                [task["id"] for task in imported_tasks],
                default=0
            ) + 1

            st.session_state.next_log_id = max(
                [log["id"] for log in imported_logs],
                default=0
            ) + 1

            save_data()
            st.success("백업 데이터를 복원했습니다.")
            st.rerun()

        except (ValueError, json.JSONDecodeError, TypeError):
            st.error("백업 파일을 읽을 수 없습니다.")

st.caption(
    "Study Planner | 시험 일정 · 준비 체크리스트 · 공부 시간 · 주간 보고서"
)
