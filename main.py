
import json
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st


# ==========================================
# 1. 기본 설정
# ==========================================

st.set_page_config(
    page_title="시험 및 수행평가 관리",
    page_icon="📚",
    layout="wide",
)

TASK_FILE = "study_tasks.json"
LOG_FILE = "study_logs.json"

DEFAULT_CHECKLIST = [
    "개념 정리",
    "문제 풀이",
    "오답 정리",
    "최종 복습",
]

IMPORTANCE_LABELS = {
    3: "높음",
    2: "보통",
    1: "낮음",
}


# ==========================================
# 2. 화면 디자인
# ==========================================

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    h1, h2, h3 {
        letter-spacing: -0.5px;
    }

    div[data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.18);
        padding: 16px;
        border-radius: 12px;
    }

    div[data-testid="stForm"] {
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================
# 3. 데이터 읽기 및 검증
# ==========================================

def read_json(path, default):
    """JSON 파일을 안전하게 읽는다."""
    if not os.path.exists(path):
        return default.copy() if isinstance(default, (dict, list)) else default

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(default, list) and isinstance(data, list):
            return data

        if isinstance(default, dict) and isinstance(data, dict):
            return data

        return default.copy() if isinstance(default, (dict, list)) else default

    except (json.JSONDecodeError, OSError, TypeError):
        return default.copy() if isinstance(default, (dict, list)) else default


def save_json(path, data):
    """데이터를 JSON 파일로 저장한다."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def valid_checklist(task):
    """
    체크리스트 데이터를 검증한다.
    task가 None이거나 딕셔너리가 아니어도 오류가 발생하지 않는다.
    """
    if not isinstance(task, dict):
        return []

    checklist = task.get("checklist", [])

    if not isinstance(checklist, list):
        return []

    result = []

    for item in checklist:
        if isinstance(item, str):
            result.append({
                "name": item,
                "done": False,
            })

        elif isinstance(item, dict):
            name = str(item.get("name", "체크리스트 항목")).strip()

            if not name:
                name = "체크리스트 항목"

            result.append({
                "name": name,
                "done": bool(item.get("done", False)),
            })

    return result


def normalize_tasks(data):
    """기존 일정 데이터의 형식을 통일한다."""
    if not isinstance(data, list):
        return []

    result = []

    for item in data:
        if not isinstance(item, dict):
            continue

        try:
            task_id = str(item.get("id", "")).strip()
            subject = str(item.get("subject", "기타")).strip()
            name = str(item.get("name", "")).strip()
            deadline = str(item.get("deadline", ""))[:10]

            date.fromisoformat(deadline)

            if not task_id or not name:
                continue

            try:
                importance = int(item.get("importance", 2))
            except (TypeError, ValueError):
                importance = 2

            importance = max(1, min(3, importance))

            checklist = valid_checklist(item)

            if not checklist:
                checklist = [
                    {"name": label, "done": False}
                    for label in DEFAULT_CHECKLIST
                ]

            result.append({
                "id": task_id,
                "subject": subject or "기타",
                "name": name,
                "deadline": deadline,
                "importance": importance,
                "completed": bool(item.get("completed", False)),
                "checklist": checklist,
                "created_at": str(
                    item.get("created_at", datetime.now().isoformat())
                ),
            })

        except (ValueError, TypeError, OverflowError):
            continue

    return result


def normalize_logs(data):
    """공부 시간 기록의 형식을 통일한다."""
    if not isinstance(data, list):
        return []

    result = []

    for item in data:
        if not isinstance(item, dict):
            continue

        try:
            log_id = str(item.get("id", "")).strip()
            subject = str(item.get("subject", "기타")).strip()
            study_date = str(item.get("study_date", ""))[:10]

            date.fromisoformat(study_date)

            hours = float(item.get("hours", 0))
            minutes = int(item.get("minutes", 0))

            if not log_id or hours < 0 or minutes < 0:
                continue

            total_minutes = int(hours * 60) + minutes

            if total_minutes <= 0:
                continue

            result.append({
                "id": log_id,
                "subject": subject or "기타",
                "study_date": study_date,
                "minutes": total_minutes,
                "note": str(item.get("note", "")),
            })

        except (ValueError, TypeError, OverflowError):
            continue

    return result


# ==========================================
# 4. 데이터 불러오기
# ==========================================

if "tasks" not in st.session_state:
    st.session_state.tasks = normalize_tasks(
        read_json(TASK_FILE, [])
    )

if "study_logs" not in st.session_state:
    st.session_state.study_logs = normalize_logs(
        read_json(LOG_FILE, [])
    )


def persist_tasks():
    save_json(TASK_FILE, st.session_state.tasks)


def persist_logs():
    save_json(LOG_FILE, st.session_state.study_logs)


def days_left(deadline):
    try:
        return (date.fromisoformat(str(deadline)[:10]) - date.today()).days
    except (ValueError, TypeError):
        return 0


def format_minutes(minutes):
    minutes = max(0, int(minutes))
    hours, remaining = divmod(minutes, 60)

    if hours and remaining:
        return f"{hours}시간 {remaining}분"
    if hours:
        return f"{hours}시간"
    return f"{remaining}분"


def checklist_progress(task):
    checklist = valid_checklist(task)

    if not checklist:
        return 0, 0

    checked = sum(1 for item in checklist if item["done"])
    return checked, len(checklist)


def task_status(task):
    if task.get("completed", False):
        return "완료"

    remaining = days_left(task.get("deadline", ""))

    if remaining < 0:
        return "기한 지남"
    if remaining == 0:
        return "오늘 마감"
    if remaining <= 3:
        return "임박"

    return "예정"


def update_task(task_id, updates):
    for task in st.session_state.tasks:
        if task.get("id") == task_id:
            task.update(updates)
            break

    persist_tasks()


def delete_task(task_id):
    st.session_state.tasks = [
        task for task in st.session_state.tasks
        if task.get("id") != task_id
    ]
    persist_tasks()


# ==========================================
# 5. 제목 및 메뉴
# ==========================================

st.title("시험 및 수행평가 일정 관리")
st.caption("시험 일정부터 준비 과정, 공부 시간과 주간 보고서까지 한곳에서 관리하세요.")

tab_dashboard, tab_tasks, tab_checklist, tab_study, tab_report, tab_backup = st.tabs([
    "대시보드",
    "일정 관리",
    "시험 준비 체크리스트",
    "공부 시간 기록",
    "주간 학습 보고서",
    "백업 및 복원",
])


# ==========================================
# 6. 대시보드
# ==========================================

with tab_dashboard:
    st.header("학습 현황")

    tasks = st.session_state.tasks
    logs = st.session_state.study_logs

    today_text = date.today().isoformat()

    unfinished = [
        task for task in tasks
        if not task.get("completed", False)
    ]

    due_soon = [
        task for task in unfinished
        if 0 <= days_left(task.get("deadline", "")) <= 3
    ]

    completed_count = sum(
        1 for task in tasks if task.get("completed", False)
    )

    completion_rate = (
        completed_count / len(tasks) * 100 if tasks else 0
    )

    today_minutes = sum(
        log["minutes"]
        for log in logs
        if log["study_date"] == today_text
    )

    week_start = date.today() - timedelta(days=6)

    week_minutes = sum(
        log["minutes"]
        for log in logs
        if week_start.isoformat() <= log["study_date"] <= today_text
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("전체 일정", f"{len(tasks)}개")
    c2.metric("미완료 일정", f"{len(unfinished)}개")
    c3.metric("3일 이내 마감", f"{len(due_soon)}개")
    c4.metric("일정 완료율", f"{completion_rate:.0f}%")

    c5, c6 = st.columns(2)
    c5.metric("오늘 공부 시간", format_minutes(today_minutes))
    c6.metric("최근 7일 공부 시간", format_minutes(week_minutes))

    st.divider()
    st.subheader("다가오는 일정")

    upcoming = sorted(
        unfinished,
        key=lambda task: task.get("deadline", "9999-12-31")
    )

    if not upcoming:
        st.success("등록된 미완료 일정이 없습니다.")

    for task in upcoming[:5]:
        remaining = days_left(task["deadline"])
        checked, total = checklist_progress(task)

        if remaining < 0:
            deadline_label = f"마감일 {abs(remaining)}일 지남"
        elif remaining == 0:
            deadline_label = "오늘 마감"
        else:
            deadline_label = f"D-{remaining}"

        with st.container(border=True):
            st.markdown(f"**{task['subject']} | {task['name']}**")
            st.write(
                f"마감일: {task['deadline']} · {deadline_label}"
            )
            st.write(
                f"중요도: {IMPORTANCE_LABELS.get(task['importance'], '보통')}"
                f" · 준비 진행률: {checked}/{total}"
            )

    st.divider()
    st.subheader("오늘의 학습 안내")

    if due_soon:
        st.warning(
            f"마감이 3일 이내인 일정이 {len(due_soon)}개 있습니다. "
            "시험 준비 체크리스트를 확인해 보세요."
        )
    elif unfinished:
        st.info("마감일이 가까운 일정부터 차근차근 준비해 보세요.")
    else:
        st.success("등록된 미완료 일정이 없습니다. 새로운 일정을 등록할 수 있습니다.")


# ==========================================
# 7. 일정 관리
# ==========================================

with tab_tasks:
    st.header("시험 및 수행평가 일정")

    with st.expander("새 일정 등록", expanded=True):
        with st.form("add_task_form", clear_on_submit=True):
            subject = st.text_input("과목", placeholder="예: 수학")
            task_name = st.text_input(
                "시험 또는 수행평가 이름",
                placeholder="예: 함수 단원 시험",
            )

            deadline = st.date_input(
                "마감일",
                value=date.today() + timedelta(days=7),
                min_value=date.today(),
            )

            importance_label = st.selectbox(
                "중요도",
                ["높음", "보통", "낮음"],
            )

            submitted = st.form_submit_button(
                "일정 등록",
                use_container_width=True,
            )

            if submitted:
                if not subject.strip() or not task_name.strip():
                    st.error("과목과 일정 이름을 모두 입력해 주세요.")
                else:
                    importance_value = {
                        "높음": 3,
                        "보통": 2,
                        "낮음": 1,
                    }[importance_label]

                    new_task = {
                        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                        "subject": subject.strip(),
                        "name": task_name.strip(),
                        "deadline": deadline.isoformat(),
                        "importance": importance_value,
                        "completed": False,
                        "checklist": [
                            {"name": label, "done": False}
                            for label in DEFAULT_CHECKLIST
                        ],
                        "created_at": datetime.now().isoformat(),
                    }

                    st.session_state.tasks.append(new_task)
                    persist_tasks()
                    st.success("일정을 등록했습니다.")
                    st.rerun()

    st.divider()

    search_text = st.text_input(
        "일정 검색",
        placeholder="과목이나 일정 이름 검색",
        key="task_search",
    )

    status_filter = st.selectbox(
        "상태 필터",
        ["전체", "미완료", "완료", "임박", "기한 지남"],
        key="task_status_filter",
    )

    filtered_tasks = []

    for task in st.session_state.tasks:
        search_target = (
            task["subject"] + " " + task["name"]
        ).lower()

        if search_text.lower() not in search_target:
            continue

        status = task_status(task)

        if status_filter == "미완료" and task["completed"]:
            continue
        if status_filter == "완료" and not task["completed"]:
            continue
        if status_filter == "임박" and status not in ["오늘 마감", "임박"]:
            continue
        if status_filter == "기한 지남" and status != "기한 지남":
            continue

        filtered_tasks.append(task)

    filtered_tasks.sort(
        key=lambda task: (
            task["completed"],
            task["deadline"],
            -task["importance"],
        )
    )

    if not filtered_tasks:
        st.info("조건에 맞는 일정이 없습니다.")

    for task in filtered_tasks:
        checked, total = checklist_progress(task)
        status = task_status(task)

        with st.container(border=True):
            left, right = st.columns([4, 1])

            with left:
                st.markdown(f"### {task['subject']} · {task['name']}")
                st.write(f"마감일: {task['deadline']} · 상태: {status}")
                st.write(
                    f"중요도: {IMPORTANCE_LABELS.get(task['importance'], '보통')}"
                    f" · 체크리스트: {checked}/{total}"
                )

            with right:
                current_done = st.checkbox(
                    "일정 완료",
                    value=task["completed"],
                    key=f"task_done_{task['id']}",
                )

                if current_done != task["completed"]:
                    update_task(task["id"], {"completed": current_done})
                    st.rerun()

                if st.button(
                    "일정 삭제",
                    key=f"task_delete_{task['id']}",
                    use_container_width=True,
                ):
                    delete_task(task["id"])
                    st.rerun()


# ==========================================
# 8. 시험 준비 체크리스트
# ==========================================

with tab_checklist:
    st.header("시험 준비 체크리스트")
    st.write("시험별로 개념 정리, 문제 풀이, 오답 정리, 최종 복습의 진행 상황을 관리합니다.")

    if not st.session_state.tasks:
        st.info("먼저 '일정 관리' 탭에서 시험 또는 수행평가를 등록해 주세요.")

    for task in st.session_state.tasks:
        # 세션 데이터도 항상 검증한 후 사용한다.
        checklist = valid_checklist(task)
        task["checklist"] = checklist

        checked_count = sum(
            1 for item in checklist if item["done"]
        )
        total_count = len(checklist)

        with st.container(border=True):
            st.subheader(f"{task['subject']} · {task['name']}")
            st.caption(f"마감일: {task['deadline']}")

            progress = (
                checked_count / total_count if total_count > 0 else 0
            )
            st.progress(progress)
            st.write(f"준비 진행률: {checked_count}/{total_count}")

            changed = False

            for index, item in enumerate(checklist):
                new_value = st.checkbox(
                    item["name"],
                    value=item["done"],
                    key=f"check_{task['id']}_{index}_{item['name']}",
                )

                if new_value != item["done"]:
                    item["done"] = new_value
                    changed = True

            with st.form(f"add_checklist_{task['id']}"):
                new_item = st.text_input(
                    "체크리스트 항목 추가",
                    key=f"new_check_item_{task['id']}",
                    placeholder="예: 교과서 핵심 문제 다시 풀기",
                )

                add_item = st.form_submit_button("항목 추가")

                if add_item:
                    if new_item.strip():
                        checklist.append({
                            "name": new_item.strip(),
                            "done": False,
                        })
                        task["checklist"] = checklist
                        persist_tasks()
                        st.success("체크리스트 항목을 추가했습니다.")
                        st.rerun()
                    else:
                        st.warning("추가할 항목을 입력해 주세요.")

            if changed:
                task["checklist"] = checklist

                # 모든 준비 항목을 체크하면 일정도 완료 처리한다.
                # 체크를 해제하면 일정은 다시 미완료 상태가 된다.
                if checklist and all(item["done"] for item in checklist):
                    task["completed"] = True
                elif not all(item["done"] for item in checklist):
                    task["completed"] = False

                persist_tasks()
                st.rerun()

            if checklist:
                delete_options = [
                    f"{i + 1}. {item['name']}"
                    for i, item in enumerate(checklist)
                ]

                selected_delete = st.selectbox(
                    "삭제할 체크리스트 항목",
                    ["선택 안 함"] + delete_options,
                    key=f"delete_check_select_{task['id']}",
                )

                if st.button(
                    "선택 항목 삭제",
                    key=f"delete_check_button_{task['id']}",
                ):
                    if selected_delete != "선택 안 함":
                        selected_index = delete_options.index(selected_delete)
                        checklist.pop(selected_index)
                        task["checklist"] = checklist
                        persist_tasks()
                        st.rerun()


# ==========================================
# 9. 공부 시간 기록
# ==========================================

with tab_study:
    st.header("공부 시간 기록")
    st.write("과목별 공부 시간을 기록하고 학습량을 확인합니다.")

    with st.form("study_log_form", clear_on_submit=True):
        study_subject = st.text_input(
            "공부한 과목",
            placeholder="예: 영어",
        )

        study_date = st.date_input(
            "공부 날짜",
            value=date.today(),
            max_value=date.today(),
        )

        col_hours, col_minutes = st.columns(2)

        with col_hours:
            study_hours = st.number_input(
                "시간",
                min_value=0,
                max_value=24,
                value=1,
                step=1,
            )

        with col_minutes:
            study_minutes = st.selectbox(
                "추가 분",
                [0, 10, 20, 30, 40, 50],
                index=3,
            )

        study_note = st.text_area(
            "학습 내용 및 메모",
            placeholder="예: 교과서 3단원 정리, 문제집 20문제 풀이",
        )

        save_log = st.form_submit_button(
            "공부 기록 저장",
            use_container_width=True,
        )

        if save_log:
            total_minutes = int(study_hours) * 60 + int(study_minutes)

            if not study_subject.strip():
                st.error("과목을 입력해 주세요.")
            elif total_minutes <= 0:
                st.error("공부 시간을 1분 이상 입력해 주세요.")
            else:
                st.session_state.study_logs.append({
                    "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                    "subject": study_subject.strip(),
                    "study_date": study_date.isoformat(),
                    "minutes": total_minutes,
                    "note": study_note.strip(),
                })

                persist_logs()
                st.success("공부 시간을 저장했습니다.")
                st.rerun()

    st.divider()
    st.subheader("최근 공부 기록")

    logs_sorted = sorted(
        st.session_state.study_logs,
        key=lambda log: (log["study_date"], log["id"]),
        reverse=True,
    )

    if not logs_sorted:
        st.info("아직 등록된 공부 기록이 없습니다.")

    for log in logs_sorted[:30]:
        with st.container(border=True):
            col_info, col_action = st.columns([5, 1])

            with col_info:
                st.markdown(
                    f"**{log['study_date']} · {log['subject']}**"
                )
                st.write(f"공부 시간: {format_minutes(log['minutes'])}")

                if log["note"]:
                    st.caption(log["note"])

            with col_action:
                if st.button(
                    "삭제",
                    key=f"delete_log_{log['id']}",
                ):
                    st.session_state.study_logs = [
                        item
                        for item in st.session_state.study_logs
                        if item["id"] != log["id"]
                    ]
                    persist_logs()
                    st.rerun()


# ==========================================
# 10. 주간 학습 보고서
# ==========================================

with tab_report:
    st.header("주간 학습 보고서")
    st.write("오늘을 포함한 최근 7일의 공부 시간과 일정 진행 상황을 확인합니다.")

    today = date.today()
    start_day = today - timedelta(days=6)

    weekly_logs = [
        log for log in st.session_state.study_logs
        if start_day.isoformat() <= log["study_date"] <= today.isoformat()
    ]

    total_week_minutes = sum(
        log["minutes"] for log in weekly_logs
    )

    average_minutes = total_week_minutes / 7

    completed_this_week = sum(
        1 for task in st.session_state.tasks
        if task.get("completed", False)
        and task.get("created_at", "")[:10] >= start_day.isoformat()
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("최근 7일 총 공부 시간", format_minutes(total_week_minutes))
    m2.metric("하루 평균 공부 시간", format_minutes(round(average_minutes)))
    m3.metric("이번 주 새 일정 중 완료", f"{completed_this_week}개")

    st.divider()
    st.subheader("날짜별 공부 시간")

    days = [
        start_day + timedelta(days=i)
        for i in range(7)
    ]

    daily_data = []

    for day in days:
        minutes = sum(
            log["minutes"]
            for log in weekly_logs
            if log["study_date"] == day.isoformat()
        )

        daily_data.append({
            "날짜": day.strftime("%m-%d"),
            "공부 시간(분)": minutes,
            "공부 시간": round(minutes / 60, 2),
        })

    daily_df = pd.DataFrame(daily_data)

    st.bar_chart(
        daily_df.set_index("날짜")[["공부 시간"]],
        y_label="시간",
    )

    st.dataframe(
        daily_df[["날짜", "공부 시간(분)"]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("과목별 공부 시간")

    if weekly_logs:
        subject_totals = {}

        for log in weekly_logs:
            subject_totals[log["subject"]] = (
                subject_totals.get(log["subject"], 0)
                + log["minutes"]
            )

        subject_df = pd.DataFrame([
            {
                "과목": subject,
                "공부 시간": round(minutes / 60, 2),
            }
            for subject, minutes in sorted(
                subject_totals.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ])

        st.bar_chart(
            subject_df.set_index("과목"),
            y_label="시간",
        )
    else:
        st.info("최근 7일의 공부 기록이 없어 과목별 보고서를 표시할 수 없습니다.")

    st.divider()
    st.subheader("남은 일정과 우선순위")

    pending = [
        task for task in st.session_state.tasks
        if not task.get("completed", False)
    ]

    pending.sort(
        key=lambda task: (
            days_left(task["deadline"]),
            -task["importance"],
        )
    )

    if pending:
        pending_df = pd.DataFrame([
            {
                "과목": task["subject"],
                "일정": task["name"],
                "마감일": task["deadline"],
                "남은 일수": days_left(task["deadline"]),
                "중요도": IMPORTANCE_LABELS.get(task["importance"], "보통"),
            }
            for task in pending
        ])

        st.dataframe(
            pending_df,
            use_container_width=True,
            hide_index=True,
        )

        first = pending[0]
        remaining = days_left(first["deadline"])

        if remaining < 0:
            message = (
                f"우선 추천: **{first['subject']} - {first['name']}**\n\n"
                f"마감일이 {abs(remaining)}일 지났습니다."
            )
        elif remaining == 0:
            message = (
                f"우선 추천: **{first['subject']} - {first['name']}**\n\n"
                "오늘 마감인 일정입니다."
            )
        else:
            message = (
                f"우선 추천: **{first['subject']} - {first['name']}**\n\n"
                f"마감일까지 {remaining}일 남았습니다."
            )

        st.info(message)

    else:
        st.success("미완료 일정이 없습니다.")


# ==========================================
# 11. 데이터 백업 및 복원
# ==========================================

with tab_backup:
    st.header("데이터 백업 및 복원")

    st.write(
        "일정, 시험 준비 체크리스트, 공부 기록을 JSON 파일로 백업할 수 있습니다."
    )

    backup_data = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "tasks": st.session_state.tasks,
        "study_logs": st.session_state.study_logs,
    }

    backup_text = json.dumps(
        backup_data,
        ensure_ascii=False,
        indent=2,
    )

    st.download_button(
        "전체 데이터 백업 다운로드",
        data=backup_text,
        file_name=f"study_planner_backup_{date.today().isoformat()}.json",
        mime="application/json",
        use_container_width=True,
    )

    st.divider()
    st.subheader("백업 파일 복원")
    st.warning(
        "복원하면 현재 일정과 공부 기록이 백업 파일의 내용으로 교체됩니다. "
        "필요하다면 먼저 현재 데이터를 백업하세요."
    )

    uploaded_file = st.file_uploader(
        "JSON 백업 파일 선택",
        type=["json"],
    )

    if uploaded_file is not None:
        if st.button(
            "백업 데이터 복원",
            type="primary",
            use_container_width=True,
        ):
            try:
                restored = json.loads(
                    uploaded_file.getvalue().decode("utf-8")
                )

                if not isinstance(restored, dict):
                    raise ValueError("백업 파일의 최상위 형식이 올바르지 않습니다.")

                if "tasks" not in restored or "study_logs" not in restored:
                    raise ValueError("일정 또는 공부 기록 데이터가 없습니다.")

                new_tasks = normalize_tasks(restored["tasks"])
                new_logs = normalize_logs(restored["study_logs"])

                st.session_state.tasks = new_tasks
                st.session_state.study_logs = new_logs

                persist_tasks()
                persist_logs()

                st.success("백업 데이터를 복원했습니다.")
                st.rerun()

            except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as error:
                st.error(f"복원에 실패했습니다. JSON 파일을 확인해 주세요. ({error})")

    st.divider()
    st.subheader("전체 데이터 초기화")

    st.warning("이 기능은 현재 저장된 모든 일정을 체크리스트와 함께 삭제하고 공부 기록도 삭제합니다.")

    confirm_reset = st.checkbox(
        "모든 데이터를 삭제하는 것에 동의합니다.",
        key="confirm_reset",
    )

    if st.button("전체 데이터 삭제", disabled=not confirm_reset):
        st.session_state.tasks = []
        st.session_state.study_logs = []

        persist_tasks()
        persist_logs()

        st.success("현재 데이터 파일을 초기화했습니다.")
        st.rerun()


# ==========================================
# 12. 하단 안내
# ==========================================

st.divider()

st.caption(
    "사용 안내: Streamlit Cloud의 로컬 파일은 앱 재배포나 환경 변경에 따라 "
    "유지되지 않을 수 있습니다. 중요한 데이터는 주기적으로 백업하세요."
)
