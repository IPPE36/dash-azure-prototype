# src/web/pages/jobs.py

import os
import uuid

from dash_extensions.enrich import Input, State, Output, Trigger, no_update, callback, clientside_callback, register_page, ALL, ctx
from dash.exceptions import PreventUpdate

from shared.db.users import get_user_id
from shared.db.tasks import add_task, get_queue_position, get_user_task_count, get_user_task_rows, get_next_user_task_id, delete_task, get_task
from shared.celery_tasks import long_task
from web.auth import get_user_name
from web.layouts.sidebar import build_sidebar_layout
from web.layouts.page_jobs import build_active_job_card


_MAX_USER_TASKS_ACTIVE = os.getenv("MAX_USER_TASKS_ACTIVE", 3)
_MAX_USER_TASKS_TOTAL = os.getenv("MAX_USER_TASKS_TOTAL", 50)
_INTERVAL = os.getenv("JOB_INTERVAL", 1000)  # update every second -> expensive?

register_page(__name__, path="/jobs")

active_job_card = build_active_job_card(_INTERVAL)

layout = build_sidebar_layout(
    nav_items=[
        ("Home", "/"),
        ("Jobs", "/jobs"),
    ],
    content=active_job_card
)


clientside_callback(
    """
    function(disabled) {
        return {
            position: "absolute",
            top: "8px",
            right: "12px",
            display: disabled ? "none" : "block"
        };
    }
    """,
    Output("jobs-spinner-wrap", "style"),
    Input("jobs-poll", "disabled"),
)


# @callback(
#     Output("jobs-result-btn", "disabled"),
#     Output("jobs-delete-btn", "disabled"),
#     Input("jobs-table", "selected_rows"),
# )
# def enable_button(selected_rows):
#     if selected_rows:
#         return False, False
#     return True, True
clientside_callback(
    """
    function(selected_rows) {
        if (selected_rows && selected_rows.length > 0) {
            return [false, false];
        }
        return [true, true];
    }
    """,
    Output("jobs-result-btn", "disabled"),
    Output("jobs-delete-btn", "disabled"),
    Input("jobs-table", "selected_rows"),
)


@callback(
    Output("jobs-submit-msg", "displayed"),
    Output("jobs-submit-msg", "message"),
    Output("jobs-poll", "n_intervals"),
    Output("jobs-poll", "disabled"),
    Output("jobs-current-id", "data"),
    Output("jobs-submit-inp", "value"),
    Output('jobs-table', 'selected_rows'),
    Input("jobs-submit-btn", "n_clicks"),
    Input("jobs-submit-inp", "n_submit"),
    State("jobs-submit-inp", "value"),
)
def start_job(n_clicks, n_submit, task_name):

    user_name = get_user_name()
    user_id = get_user_id(user_name)

    if not n_clicks and not n_submit:
        task_id = get_next_user_task_id(user_id)
        return no_update, no_update, no_update, False, task_id, no_update, no_update
    
    if not task_name:
        return True, "No task name provided! Please enter...", no_update, no_update, no_update, no_update, no_update
    
    n_active = get_user_task_count(user_id)
    if n_active >= _MAX_USER_TASKS_ACTIVE:
        return True, f"Maximum number of user active tasks is {_MAX_USER_TASKS_ACTIVE}! Please wait until PENDING tasks complete...", no_update, no_update, no_update, no_update, no_update
    
    n_total = get_user_task_count(user_id, statuses=None)
    if n_total >= _MAX_USER_TASKS_TOTAL:
        return True, f"Maximum number of user total tasks is {_MAX_USER_TASKS_TOTAL}! Please delete old tasks in the database...", no_update, no_update, no_update, no_update, no_update
    
    # schedule task with celery task id (string!)
    celery_id = str(uuid.uuid4())
    payload = 0
    task_id = add_task(
        user_id=user_id,
        task_name=task_name,
        input_payload={"x": payload},
    )
    long_task.apply_async(
        args=[payload],
        kwargs={"task_id": task_id},
        task_id=celery_id,
    )

    task_id = get_next_user_task_id(user_id)
    return False, no_update, 0, False, task_id, "", []


@callback(
    Output("jobs-table", "data"),
    Trigger("app-location", "pathname"),
    Trigger("jobs-refresh-btn", "n_clicks"),
)
def page_load():
    user_name = get_user_name()
    user_id = get_user_id(user_name)

    user_tasks = get_user_task_rows(
        newest_first=True,
        user_id=user_id,
        include_payloads=False,
        columns={"status", "task_name", "progress", "task_id"},
        limit=_MAX_USER_TASKS_TOTAL
    )

    for i, t in enumerate(user_tasks):
        if t["status"] in {"PENDING"}:
            user_tasks[i]["status"] += f"-{get_queue_position(t['task_id'])-1}"

    return user_tasks


@callback(
    Output("jobs-progress", "value"),
    Output("jobs-progress-text", "children"),
    Output("jobs-poll", "disabled"),
    Output("jobs-finished-id", "data"),
    Output("jobs-active-container-collapse", "is_open"),
    Output("jobs-table", "data"),
    Trigger("jobs-poll", "n_intervals"),
    State("jobs-current-id", "data"),
)
def poll_job(task_id):
    
    if task_id is None:
        return 0, "0%", True, no_update, False, no_update
    
    user_name = get_user_name()
    user_id = get_user_id(user_name)

    task = get_task(task_id)
    if task is None:
        return 0, "0%", True, no_update, False, no_update

    status = task["status"]

    user_tasks = get_user_task_rows(
        newest_first=True,
        user_id=user_id,
        include_payloads=False,
        columns={"status", "task_name", "progress", "task_id"},
        limit=_MAX_USER_TASKS_TOTAL
    )

    if status in {"COMPLETED", "ABORTED"}:
        user_tasks.append({
            "task_name": task["task_name"],
            "status": status,
            "task_id": task_id,
            "progress": task["progress"],
        })

    for i, t in enumerate(user_tasks):
        if t["status"] in {"PENDING"}:
            user_tasks[i]["status"] += f"-{get_queue_position(t['task_id'])-1}"

    if status in {"COMPLETED", "ABORTED"}:
        return 100, "100%", False, task_id, True, user_tasks
    
    if status == "PENDING":
        return no_update, no_update, False, no_update, True, user_tasks
    
    progress = int(task.get("progress") or 0)
    return progress, f"{progress}%", False, no_update, True, user_tasks



@callback(
    Output("mobile-sidebar", "is_open"),
    Input("open-sidebar-btn", "n_clicks"),
    State("mobile-sidebar", "is_open"),
    prevent_initial_call=True,
)
def toggle_mobile_sidebar(n_clicks, is_open):
    return not is_open


@callback(
    Output("jobs-poll", "n_intervals"),
    Output("jobs-current-id", "data"),
    Trigger("jobs-finished-id", "data"),
)
def next_job():
    user_name = get_user_name()
    user_id = get_user_id(user_name)
    task_id = get_next_user_task_id(user_id)
    return 0, task_id


@callback(
    Output('jobs-delete-confirm', 'displayed'),
    Output('jobs-delete-confirm', 'message'),
    Output('jobs-todelete-id', 'data'),
    Trigger('jobs-delete-btn', "n_clicks"),
    State('jobs-table', 'selected_rows'),
    State('jobs-table', 'data'),
    prevent_initial_call=True,
)
def cb_delete_rows(selected_rows, data):
    if selected_rows is None:
        raise PreventUpdate
    if not len(selected_rows):
        return True, "No Optimization selected!"
    task_id = data[selected_rows[0]]["task_id"]
    task = get_task(task_id)
    task_name = task["task_name"]
    return (True, f"Are you sure you want to deleted optimization \"{task_name}\" with ID {task_id}?",
            {"task_id": task_id, "task_name": task_name})


@callback(
    Output("jobs-delete-msg", "displayed"),
    Output("jobs-delete-msg", "message"),
    Output("jobs-poll", "disabled"),
    Output("jobs-poll", "n_intervals"),
    Output("jobs-current-id", "data"),
    Output("jobs-progress", "value"),
    Output("jobs-progress-text", "children"),
    Output("jobs-refresh-btn", "n_clicks"),  # refreshes table upon delete
    Trigger("jobs-delete-confirm", "submit_n_clicks"),
    State("jobs-todelete-id", "data"),
    State("jobs-current-id", "data"),
    prevent_initial_call=True,
)
def cb_delete_after_confirm(task_data, current_task_id):
    if not task_data:
        raise PreventUpdate

    task_id = task_data["task_id"]
    label = task_data["task_name"]

    delete_task(task_id)

    msg = f'Deleted Task "{label}" with ID {task_id}!'

    if task_id == current_task_id:
        user_name = get_user_name()
        user_id = get_user_id(user_name)
        if user_id is None:
            raise PreventUpdate

        next_task_id = get_next_user_task_id(user_id)

        if next_task_id is None:
            return True, msg, True, 0, None, 0, "0%", 0

        return True, msg, False, 0, next_task_id, 0, "0%", 0

    return True, msg, no_update, no_update, no_update, no_update, no_update, 0