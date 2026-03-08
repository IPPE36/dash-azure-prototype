# src/web/pages/jobs.py

import os
import uuid

from dash_extensions.enrich import Input, State, Output, Trigger, no_update, callback, register_page, ALL, ctx
from dash.exceptions import PreventUpdate

from shared.db.users import get_user_id
from shared.db.tasks import add_task, get_queue_position, get_user_task_count, get_user_task_rows, get_next_user_task_id, delete_task, get_task
from shared.celery_tasks import long_task
from web.auth import get_user_name
from web.layouts.sidebar import build_sidebar_layout
from web.layouts.page_jobs import build_active_job_card, build_active_task_rows


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


@callback(
    Output("jobs-confirm", "displayed"),
    Output("jobs-confirm", "message"),
    Output("jobs-poll", "n_intervals"),
    Output("jobs-poll", "disabled"),
    Output("jobs-current-id", "data"),
    Output("jobs-submit-inp", "value"),
    Input("jobs-submit-btn", "n_clicks"),
    Input("jobs-submit-inp", "n_submit"),
    State("jobs-submit-inp", "value"),
)
def start_job(n_clicks, n_submit, task_name):

    user_name = get_user_name()
    user_id = get_user_id(user_name)

    if not n_clicks and not n_submit:
        task_id = get_next_user_task_id(user_id)
        return no_update, no_update, no_update, False, task_id, no_update
    
    if not task_name:
        return True, "No task name provided! Please enter...", no_update, no_update, no_update, no_update
    
    n_active = get_user_task_count(user_id)
    if n_active >= _MAX_USER_TASKS_ACTIVE:
        return True, f"Maximum number of user active tasks is {_MAX_USER_TASKS_ACTIVE}! Please wait until PENDING tasks complete...", no_update, no_update, no_update, no_update
    
    n_total = get_user_task_count(user_id, statuses=None)
    if n_total >= _MAX_USER_TASKS_TOTAL:
        return True, f"Maximum number of user total tasks is {_MAX_USER_TASKS_TOTAL}! Please delete old tasks in the database...", no_update, no_update, no_update, no_update
    
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
    return False, no_update, 0, False, task_id, ""



@callback(
    Output("jobs-active-container", "children"),
    Output("jobs-progress", "value"),
    Output("jobs-progress-text", "children"),
    Output("jobs-poll", "disabled"),
    Output("jobs-finished-id", "data"),
    Output("jobs-active-container-collapse", "is_open"),
    Trigger("jobs-poll", "n_intervals"),
    State("jobs-current-id", "data"),
)
def poll_job(task_id):
    
    if task_id is None:
        return [], 0, "0%", True, no_update, False
    
    user_name = get_user_name()
    user_id = get_user_id(user_name)

    task = get_task(task_id)
    status = task["status"]

    user_tasks = get_user_task_rows(
        newest_first=True,
        user_id=user_id,
        include_payloads=False,
        columns={"status", "task_name", "progress", "task_id"},
        status={"PENDING", "RUNNING"},
        limit=_MAX_USER_TASKS_ACTIVE
    )

    if status in {"COMPLETED", "ABORTED"}:
        user_tasks.append({
            "task_name": task["task_name"],
            "status": status,
            "task_id": task_id,
            "progress": task["progress"],
        })

    for i, t in enumerate(user_tasks):
        user_tasks[i]["pos"] = get_queue_position(t["task_id"])

    # n = get_queue_length()
    children = build_active_task_rows(user_tasks)

    if status in {"COMPLETED", "ABORTED"}:
        return children, 100, "100%", False, task_id, True
    
    if status == "PENDING":
        return children, no_update, no_update, False, no_update, True
    
    progress = int(task.get("progress") or 0)
    return children, progress, f"{progress}%", False, no_update, True


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
    Output("jobs-poll", "disabled"),
    Output("jobs-poll", "n_intervals"),
    Output("jobs-current-id", "data"),
    Output("jobs-progress", "value"),
    Output("jobs-progress-text", "children"),
    Trigger({"type": "jobs-cancel-btn", "index": ALL}, "n_clicks"),
    State("jobs-current-id", "data"),
)
def cancel_task(current_task_id):

    if not ctx.triggered:
        raise PreventUpdate

    if ctx.triggered[0]["value"] is None:
        raise PreventUpdate

    cancel_id = ctx.triggered_id["index"]

    user_name = get_user_name()
    user_id = get_user_id(user_name)
    if user_id is None:
        raise PreventUpdate

    task = get_task(cancel_id)
    if not task or task.get("user_id") != user_id:
        raise PreventUpdate

    delete_task(cancel_id)

    if cancel_id == current_task_id:
        next_task_id = get_next_user_task_id(user_id)
        if next_task_id is None:
            return True, 0, "0%", None, 0
        return False, 0, "0%", next_task_id, 0

    return False, 0, "0%", no_update, no_update