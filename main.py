
import json
import os
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st


# ==================================================
# 1. 기본 설정
# ==================================================

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


# ==================================================
# 2. 디자인
# ==================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1200px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    div[data-testid="stMetric"] {
        padding: 16px;
        border-radius: 12px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        background: rgba(128, 128, 128, 0.06);
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ==================================================
# 3. 데이터 처리 함수
# ==================================================

def read_json(path):
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (OSError, ValueError, TypeError):
        return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def valid_checklist(task):
    """잘못된 체크리스트 데이터가 있어도 앱이 중단되지 않도록 한다."""
    if not isinstance(task, dict):
        return []

    raw = task.get("checklist", [])

    if not isinstance(raw, list):
        return []

    result = []

    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            done = False

        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            done = bool(item.get("done", False))

        else:
            continue

        if name:
            result.append({
                "name": name,
                "done": done,
            })

    return result


def normalize_tasks(raw_tasks):
    if not isinstance(raw_tasks, list):
        return []

    result = []

    for item in raw_tasks:
        if not isinstance(item, dict):
            continue

        try:
            task_id = str(item.get("id") or uuid.uuid4().hex)
            subject = str(item.get("subject", "기타")).strip()
            name = str(item.get("name", "")).strip()
            deadline = str(item.get("deadline", ""))[:10]

            date.fromisoformat(deadline)

            if not name:
                continue

            try:
                importance = int(item.get("importance", 2))
            except (ValueError, TypeError):
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


def normalize_logs(raw_logs):
    if not isinstance(raw_logs, list):
        return []

    result = []

    for item in raw_logs:
        if not isinstance(item, dict):
            continue

        try:
            log_id = str(item.get("id") or uuid.uuid4().hex)
            subject = str(item.get("subject", "기타")).strip()
            study_date = str(item.get("study_date", ""))[:10]

            date.fromisoformat(study_date)

            if "minutes" in item:
                minutes = int(item["minutes"])
            else:
                minutes = int(float(item.get("hours", 0)) * 60)
                minutes += int(item.get("extra_minutes", 0))

            if minutes <= 0:
                continue

            result.append({
                "id": log_id,
                "subject": subject or "기타",
                "study_date": study_date,
                "minutes": minutes,
                "note": str(item.get("note", "")),
            })

        except (ValueError, TypeError, OverflowError):
            continue

    return result


def days_left(deadline):
    try:
        return (
            date.fromisoformat(str(deadline)[:10]) - date.today()
        ).days
    except (ValueError, TypeError):
        return 0


def format_minutes(minutes):
    minutes = max(0, int(minutes))
    hours, mins = divmod(minutes, 60)

    if hours and mins:
        return f"{hours}시간 {mins}분"
    if hours:
        return f"{hours}시간"
    return f"{mins}분"


def checklist_progress(task):
    checklist = valid_checklist(task)
    total = len(checklist)
    checked = sum(1 for item in checklist if item["done"])
    return checked, total


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


def priority_score(task):
    """
    우선순위 점수:
    마감일 + 중요도 + 준비 진행률을 함께 고려한다.
    점수가 높을수록 먼저 공부하도록 추천한다.
    """
    remaining = days_left(task["deadline"])
    importance = int(task.get("importance", 2))
    checked, total = checklist_progress(task)

    if remaining < 0:
        deadline_score = 100
    elif remaining == 0:
        deadline_score = 90
    elif remaining <= 2:
        deadline_score = 75
    elif remaining <= 5:
        deadline_score = 55
    elif remaining <= 7:
        deadline_score = 40
    else:
        deadline_score = 20

    importance_score = importance * 10

    if total > 0:
        unfinished_ratio = (total - checked) / total
    else:
        unfinished_ratio = 1

    preparation_score = unfinished_ratio * 20

    return deadline_score + importance_score + preparation_score


def priority_reason(task):
    remaining = days_left(task["deadline"])
    checked, total = checklist_progress(task)

    reasons = []

    if remaining < 0:
        reasons.append(f"마감일이 {abs(remaining)}일 지남")
    elif remaining == 0:
        reasons.append("오늘 마감")
    elif remaining <= 2:
        reasons.append(f"마감까지 {remaining}일")
    elif remaining <= 5:
        reasons.append(f"마감까지 {remaining}일")

    reasons.append(
        "중요도 " + IMPORTANCE_LABELS.get(
            task.get("importance", 2), "보통"
        )
    )

    if total > 0 and checked < total:
        reasons.append(f"준비 미완료 {total - checked}개")

    return " · ".join(reasons)


def next_study_step(task):
    checklist = valid_checklist(task)

    for item in checklist:
        if not item["done"]:
            return item["name"]

    return "최종 복습 및 시험 범위 확인"


def persist_tasks():
    save_json(TASK_FILE, st.session_state.tasks)


def persist_logs():
    save_json(LOG_FILE, st.session_state.study_logs)


# ==================================================
# 4. 데이터 불러오기
# ==================================================

if "tasks" not in st.session_state:
    st.session_state.tasks = normalize_tasks(read_json(TASK_FILE))

if "study_logs" not in st.session_state:
    st.session_state.study_logs = normalize_logs(read_json(LOG_FILE))


# ==================================================
# 5. 상단 메뉴
# ==================================================

st.title("시험 및 수행평가 일정 관리")
st.caption("일정 관리부터 공부 우선순위 추천, 학습 기록까지 한곳에서")

(
    tab_dashboard,
    tab_tasks,
    tab_checklist,
    tab_study,
    tab_report,
    tab_backup,
) = st.tabs([
    "대시보드",
    "일정 관리",
    "시험 준비 체크리스트",
    "공부 시간 기록",
    "주간 학습 보고서",
    "백업 및 복원",
])


# ==================================================
# 6. 대시보드
# ==================================================

with tab_dashboard:
    st.header("나의 학습 현황")

    tasks = st.session_state.tasks
    logs = st.session_state.study_logs

    today = date.today()
    today_text = today.isoformat()
    week_start = today - timedelta(days=6)

    unfinished = [
        task for task in tasks
        if not task.get("completed", False)
    ]

    due_soon = [
        task for task in unfinished
        if 0 <= days_left(task["deadline"]) <= 3
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

    weekly_minutes = sum(
        log["minutes"]
        for log in logs
        if week_start.isoformat()
        <= log["study_date"]
        <= today_text
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 일정", f"{len(tasks)}개")
    c2.metric("미완료 일정", f"{len(unfinished)}개")
    c3.metric("3일 이내 마감", f"{len(due_soon)}개")
    c4.metric("완료율", f"{completion_rate:.0f}%")

    c5, c6 = st.columns(2)
    c5.metric("오늘 공부 시간", format_minutes(today_minutes))
    c6.metric("최근 7일 공부 시간", format_minutes(weekly_minutes))

    st.divider()
    st.header("오늘 먼저 공부할 과목")

    if not unfinished:
        st.success(
            "현재 미완료 일정이 없습니다. "
            "일정 관리 탭에서 시험이나 수행평가를 등록해 보세요."
        )
    else:
        ranked_tasks = sorted(
            unfinished,
            key=lambda task: (
                priority_score(task),
                -days_left(task["deadline"]),
                task.get("importance", 2),
            ),
            reverse=True,
        )

        st.write(
            "마감일, 중요도, 체크리스트 진행률을 기준으로 "
            "먼저 준비할 일정을 추천합니다."
        )

        for rank, task in enumerate(ranked_tasks[:3], start=1):
            checked, total = checklist_progress(task)
            progress = checked / total if total else 0
            remaining = days_left(task["deadline"])

            if remaining < 0:
                deadline_text = f"마감일 {abs(remaining)}일 지남"
            elif remaining == 0:
                deadline_text = "오늘 마감"
            else:
                deadline_text = f"D-{remaining}"

            with st.container(border=True):
                st.subheader(
                    f"{rank}위. {task['subject']} - {task['name']}"
                )

                left, right = st.columns([3, 1])

                with left:
                    st.write(f"**추천 이유:** {priority_reason(task)}")
                    st.write(f"**마감일:** {task['deadline']} ({deadline_text})")
                    st.write(f"**지금 할 일:** {next_study_step(task)}")
                    st.progress(progress)
                    st.caption(f"준비 진행률: {checked}/{total}")

                with right:
                    st.metric(
                        "중요도",
                        IMPORTANCE_LABELS.get(
                            task.get("importance", 2), "보통"
                        ),
                    )

                    if st.button(
                        "체크리스트 열기",
                        key=f"open_checklist_{task['id']}",
                        use_container_width=True,
                    ):
                        st.info(
                            "위쪽 메뉴에서 '시험 준비 체크리스트' 탭을 "
                            "선택해 해당 일정의 준비 항목을 확인하세요."
                        )

    st.divider()
    st.header("다가오는 일정")

    upcoming = sorted(
        unfinished,
        key=lambda task: (
            days_left(task["deadline"]),
            -task.get("importance", 2),
        ),
    )

    if not upcoming:
        st.info("다가오는 미완료 일정이 없습니다.")

    for task in upcoming[:5]:
        checked, total = checklist_progress(task)

        with st.container(border=True):
            st.markdown(f"**{task['subject']} | {task['name']}**")
            st.write(
                f"마감일: {task['deadline']} · "
                f"상태: {task_status(task)}"
            )
            st.write(
                f"중요도: {IMPORTANCE_LABELS.get(task['importance'], '보통')} "
                f"· 준비: {checked}/{total}"
            )


# ==================================================
# 7. 일정 관리
# ==================================================

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
                    importance = {
                        "높음": 3,
                        "보통": 2,
                        "낮음": 1,
                    }[importance_label]

                    st.session_state.tasks.append({
                        "id": uuid.uuid4().hex,
                        "subject": subject.strip(),
                        "name": task_name.strip(),
                        "deadline": deadline.isoformat(),
                        "importance": importance,
                        "completed": False,
                        "checklist": [
                            {"name": label, "done": False}
                            for label in DEFAULT_CHECKLIST
                        ],
                        "created_at": datetime.now().isoformat(),
                    })

                    persist_tasks()
                    st.success("일정을 등록했습니다.")
                    st.rerun()

    st.divider()

    search_text = st.text_input(
        "일정 검색",
        placeholder="과목 또는 일정 이름",
    )

    status_filter = st.selectbox(
        "상태 필터",
        ["전체", "미완료", "완료", "임박", "기한 지남"],
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
            days_left(task["deadline"]),
            -task["importance"],
        )
    )

    if not filtered_tasks:
        st.info("조건에 맞는 일정이 없습니다.")

    for task in filtered_tasks:
        checked, total = checklist_progress(task)

        with st.container(border=True):
            st.subheader(f"{task['subject']} · {task['name']}")
            st.write(
                f"마감일: {task['deadline']} · "
                f"중요도: {IMPORTANCE_LABELS[task['importance']]}"
            )

            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                new_subject = st.text_input(
                    "과목 수정",
                    value=task["subject"],
                    key=f"subject_{task['id']}",
                )

            with col2:
                new_name = st.text_input(
                    "일정 이름 수정",
                    value=task["name"],
                    key=f"name_{task['id']}",
                )

            with col3:
                if st.button(
                    "수정 저장",
                    key=f"edit_{task['id']}",
                    use_container_width=True,
                ):
                    if new_subject.strip() and new_name.strip():
                        task["subject"] = new_subject.strip()
                        task["name"] = new_name.strip()
                        persist_tasks()
                        st.success("일정을 수정했습니다.")
                        st.rerun()
                    else:
                        st.error("과목과 일정 이름을 입력해 주세요.")

            done_value = st.checkbox(
                "일정 완료",
                value=task["completed"],
                key=f"done_{task['id']}",
            )

            if done_value != task["completed"]:
                task["completed"] = done_value
                persist_tasks()
                st.rerun()

            st.caption(f"체크리스트 진행 상황: {checked}/{total}")

            if st.button(
                "일정 삭제",
                key=f"delete_task_{task['id']}",
            ):
                st.session_state.tasks = [
                    item for item in st.session_state.tasks
                    if item["id"] != task["id"]
                ]
                persist_tasks()
                st.rerun()


# ==================================================
# 8. 시험 준비 체크리스트
# ==================================================

with tab_checklist:
    st.header("시험 준비 체크리스트")
    st.write(
        "시험별로 개념 정리, 문제 풀이, 오답 정리, "
        "최종 복습의 진행 상황을 관리합니다."
    )

    if not st.session_state.tasks:
        st.info("일정 관리 탭에서 시험이나 수행평가를 먼저 등록해 주세요.")

    for task in st.session_state.tasks:
        checklist = valid_checklist(task)
        task["checklist"] = checklist

        checked, total = checklist_progress(task)

        with st.container(border=True):
            st.subheader(f"{task['subject']} · {task['name']}")
            st.caption(f"마감일: {task['deadline']}")

            progress = checked / total if total else 0
            st.progress(progress)
            st.write(f"진행률: {checked}/{total}")

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

            if changed:
                task["checklist"] = checklist

                if checklist and all(item["done"] for item in checklist):
                    task["completed"] = True
                else:
                    task["completed"] = False

                persist_tasks()
                st.rerun()

            with st.form(f"add_item_form_{task['id']}"):
                new_item = st.text_input(
                    "새 준비 항목",
                    placeholder="예: 선생님이 강조한 내용 확인",
                )

                add_item = st.form_submit_button("항목 추가")

                if add_item:
                    if new_item.strip():
                        checklist.append({
                            "name": new_item.strip(),
                            "done": False,
                        })
                        task["checklist"] = checklist
                        task["completed"] = False
                        persist_tasks()
                        st.rerun()
                    else:
                        st.warning("추가할 항목을 입력해 주세요.")

            if checklist:
                delete_choice = st.selectbox(
                    "삭제할 항목",
                    ["선택 안 함"] + [
                        f"{i + 1}. {item['name']}"
                        for i, item in enumerate(checklist)
                    ],
                    key=f"delete_choice_{task['id']}",
                )

                if st.button(
                    "선택 항목 삭제",
                    key=f"delete_item_{task['id']}",
                ):
                    if delete_choice != "선택 안 함":
                        index = int(delete_choice.split(".")[0]) - 1
                        checklist.pop(index)
                        task["checklist"] = checklist
                        persist_tasks()
                        st.rerun()


# ==================================================
# 9. 공부 시간 기록
# ==================================================

with tab_study:
    st.header("공부 시간 기록")

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

        col1, col2 = st.columns(2)

        with col1:
            hours = st.number_input(
                "시간",
                min_value=0,
                max_value=24,
                value=1,
                step=1,
            )

        with col2:
            extra_minutes = st.selectbox(
                "추가 분",
                [0, 10, 20, 30, 40, 50],
                index=3,
            )

        note = st.text_area(
            "학습 내용 및 메모",
            placeholder="예: 교과서 3단원 정리",
        )

        save_log = st.form_submit_button(
            "공부 기록 저장",
            use_container_width=True,
        )

        if save_log:
            total_minutes = int(hours) * 60 + int(extra_minutes)

            if not study_subject.strip():
                st.error("과목을 입력해 주세요.")
            elif total_minutes <= 0:
                st.error("공부 시간을 1분 이상 입력해 주세요.")
            else:
                st.session_state.study_logs.append({
                    "id": uuid.uuid4().hex,
                    "subject": study_subject.strip(),
                    "study_date": study_date.isoformat(),
                    "minutes": total_minutes,
                    "note": note.strip(),
                })

                persist_logs()
                st.success("공부 기록을 저장했습니다.")
                st.rerun()

    st.divider()
    st.subheader("최근 공부 기록")

    sorted_logs = sorted(
        st.session_state.study_logs,
        key=lambda log: (log["study_date"], log["id"]),
        reverse=True,
    )

    if not sorted_logs:
        st.info("아직 공부 기록이 없습니다.")

    for log in sorted_logs[:30]:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"**{log['study_date']} · {log['subject']}**")
                st.write(f"공부 시간: {format_minutes(log['minutes'])}")

                if log["note"]:
                    st.caption(log["note"])

            with col2:
                if st.button("삭제", key=f"delete_log_{log['id']}"):
                    st.session_state.study_logs = [
                        item for item in st.session_state.study_logs
                        if item["id"] != log["id"]
                    ]
                    persist_logs()
                    st.rerun()


# ==================================================
# 10. 주간 학습 보고서
# ==================================================

with tab_report:
    st.header("주간 학습 보고서")

    today = date.today()
    start_day = today - timedelta(days=6)

    weekly_logs = [
        log for log in st.session_state.study_logs
        if start_day.isoformat()
        <= log["study_date"]
        <= today.isoformat()
    ]

    total_minutes = sum(log["minutes"] for log in weekly_logs)
    average_minutes = round(total_minutes / 7)

    m1, m2, m3 = st.columns(3)

    m1.metric("최근 7일 총 공부 시간", format_minutes(total_minutes))
    m2.metric("하루 평균 공부 시간", format_minutes(average_minutes))
    m3.metric("최근 7일 기록 수", f"{len(weekly_logs)}회")

    st.divider()
    st.subheader("날짜별 공부 시간")

    daily_rows = []

    for offset in range(7):
        day = start_day + timedelta(days=offset)

        minutes = sum(
            log["minutes"]
            for log in weekly_logs
            if log["study_date"] == day.isoformat()
        )

        daily_rows.append({
            "날짜": day.strftime("%m-%d"),
            "공부 시간": round(minutes / 60, 2),
            "공부 시간(분)": minutes,
        })

    daily_df = pd.DataFrame(daily_rows)

    st.bar_chart(
        daily_df.set_index("날짜")[["공부 시간"]]
    )

    st.dataframe(
        daily_df,
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

        st.bar_chart(subject_df.set_index("과목"))
    else:
        st.info("최근 7일의 공부 기록이 없어 그래프를 표시할 수 없습니다.")

    st.divider()
    st.subheader("남은 일정 및 우선순위")

    pending = [
        task for task in st.session_state.tasks
        if not task.get("completed", False)
    ]

    pending.sort(
        key=lambda task: (
            priority_score(task),
            -days_left(task["deadline"]),
        ),
        reverse=True,
    )

    if pending:
        rows = []

        for task in pending:
            checked, total = checklist_progress(task)

            rows.append({
                "과목": task["subject"],
                "일정": task["name"],
                "마감일": task["deadline"],
                "남은 일수": days_left(task["deadline"]),
                "중요도": IMPORTANCE_LABELS[task["importance"]],
                "준비 진행률": f"{checked}/{total}",
                "우선순위 점수": round(priority_score(task), 1),
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

        first = pending[0]
        st.info(
            f"**우선 추천: {first['subject']} - {first['name']}**\n\n"
            f"추천 이유: {priority_reason(first)}\n\n"
            f"지금 할 일: {next_study_step(first)}"
        )
    else:
        st.success("미완료 일정이 없습니다.")


# ==================================================
# 11. 백업 및 복원
# ==================================================

with tab_backup:
    st.header("데이터 백업 및 복원")

    backup_data = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "tasks": st.session_state.tasks,
        "study_logs": st.session_state.study_logs,
    }

    st.download_button(
        "전체 데이터 백업 다운로드",
        data=json.dumps(
            backup_data,
            ensure_ascii=False,
            indent=2,
        ),
        file_name=f"study_planner_backup_{date.today().isoformat()}.json",
        mime="application/json",
        use_container_width=True,
    )

    st.divider()
    st.subheader("백업 파일 복원")

    st.warning(
        "복원하면 현재 데이터가 백업 파일의 데이터로 교체됩니다. "
        "필요하다면 먼저 현재 데이터를 백업하세요."
    )

    uploaded_file = st.file_uploader(
        "JSON 백업 파일 선택",
        type=["json"],
    )

    if uploaded_file is not None:
        if st.button("백업 데이터 복원", type="primary"):
            try:
                restored = json.loads(
                    uploaded_file.getvalue().decode("utf-8")
                )

                if not isinstance(restored, dict):
                    raise ValueError("올바른 백업 파일이 아닙니다.")

                if not isinstance(restored.get("tasks"), list):
                    raise ValueError("일정 데이터 형식이 올바르지 않습니다.")

                if not isinstance(restored.get("study_logs"), list):
                    raise ValueError("공부 기록 형식이 올바르지 않습니다.")

                st.session_state.tasks = normalize_tasks(restored["tasks"])
                st.session_state.study_logs = normalize_logs(
                    restored["study_logs"]
                )

                persist_tasks()
                persist_logs()

                st.success("백업 데이터를 복원했습니다.")
                st.rerun()

            except (
                json.JSONDecodeError,
                UnicodeDecodeError,
                ValueError,
                TypeError,
            ) as error:
                st.error(f"복원에 실패했습니다: {error}")

    st.divider()
    st.subheader("전체 데이터 초기화")

    confirmed = st.checkbox(
        "모든 일정과 공부 기록을 삭제하는 것에 동의합니다."
    )

    if st.button("전체 데이터 삭제", disabled=not confirmed):
        st.session_state.tasks = []
        st.session_state.study_logs = []

        persist_tasks()
        persist_logs()

        st.success("데이터를 초기화했습니다.")
        st.rerun()


# ==================================================
# 12. 하단 안내
# ==================================================

st.divider()

st.caption(
    "중요: Streamlit Cloud의 로컬 파일은 영구 저장을 보장하지 않습니다. "
    "중요한 일정과 공부 기록은 주기적으로 백업하세요."
)
