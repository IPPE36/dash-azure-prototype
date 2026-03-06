# src/web/pages/jobs.py

import os
import uuid

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc, Input, State, Output, Trigger, no_update, callback, register_page
from dash.exceptions import PreventUpdate

from shared.db.users import get_user_id
from shared.db.tasks import add_task, get_queue_position, get_user_active_task_count, get_queue_length, get_next_user_task_id, delete_task, get_task, set_celery_id
from shared.tasks import long_task
from web.auth import get_user_name
from web.layouts.sidebar import build_sidebar_layout


_MAX_USER_TASKS = 3
_INTERVAL_FAST = os.getenv("JOB_UPDATE_INTERVAL_FAST", 1000)
_INTERVAL_SLOW = os.getenv("JOB_UPDATE_INTERVAL_SLOW", 5000)


register_page(__name__, path="/jobs")


job_card = dbc.Card([
    dcc.ConfirmDialog(id="cnf_job", message=""),
    dcc.Store(id="task_id_current", data=None),
    dcc.Store(id="task_id_finished", data=None),
    dcc.Interval(id="poll", interval=1000, disabled=False, n_intervals=0, max_intervals=200),
    dbc.CardHeader([
        html.H5("Active Jobs", className="mb-2"),
        html.Div(
            [
                dbc.InputGroup(
                    [
                        dbc.Input(id="inp_submit_job", type="text", placeholder="Job Name"),
                        dbc.Button("Submit", id="btn_submit_job", color="primary"),
                    ],
                    className="flex-grow-1 me-2"
                ),
                dbc.Button("Cancel", disabled=True, id="btn_cancel_job", color="danger"),
            ],
            className="d-flex align-items-center"
        )
    ]),
    dbc.Collapse(
        dbc.CardBody(
            "HI"
        ),
        id="crd_body_clps_job",
        is_open=False,
    ),
    dbc.CardFooter([
        html.Span(id="status", className="mb-2"),
        html.Div(
            [
                html.Span("Progress:", className="me-3"),
                dbc.Progress(
                    id="progress",
                    value=0,
                    max=100,
                    label="0%",
                    color="secondary",
                    className="flex-grow-1",
                ),
            ],
            className="d-flex align-items-center",
        ),
    ]),
], style={"width": "50rem"})


layout = build_sidebar_layout(
    page_title="Jobs",
    nav_items=[
        ("Home", "/"),
        ("Jobs", "/jobs"),
    ],
    content=job_card
)

@callback(
    Output("cnf_job", "displayed"),
    Output("cnf_job", "message"),
    Output("poll", "n_intervals"),
    Output("poll", "disabled"),
    Output("task_id_current", "data"),
    Input("btn_submit_job", "n_clicks"),
    State("inp_submit_job", "value")
)
def start_job(n_clicks, task_name):

    if not task_name and n_clicks:
        return True, "Please provide a task name!", no_update, no_update, no_update

    user_name = get_user_name()
    user_id = get_user_id(user_name)
    
    n_active = get_user_active_task_count(user_id)
    if n_active >= _MAX_USER_TASKS:
        return True, f"Maximum number of tasks = {_MAX_USER_TASKS}!", no_update, no_update, no_update
    
    celery_id = str(uuid.uuid4())

    payload = 0

    task_id = add_task(
        user_id=user_id,
        task_name=task_name,
        input_payload={"x": payload},
    )

    set_celery_id(task_id, celery_id)

    # schedule task with celery task id (string!)
    long_task.apply_async(
        args=[payload],
        kwargs={"task_id": task_id},
        task_id=celery_id,
    )

    task_id = get_next_user_task_id(user_id)
    return False, no_update, 0, False, task_id


@callback(
    Output("status", "children"),
    Output("progress", "value"),
    Output("progress", "label"),
    Output("poll", "interval"),
    Output("poll", "disabled"),
    Output("task_id_finished", "data"),
    Output("btn_cancel_job", "disabled"),
    Output("crd_body_clps_job", "is_open"),
    Input("poll", "n_intervals"),
    State("task_id_current", "data"),
)
def poll_job(n_intervals, task_id):

    if not n_intervals:
        raise PreventUpdate
    
    if task_id is None:
        return "", 0, "", _INTERVAL_FAST, True, no_update, True, False

    task = get_task(task_id)
    if task is None:
        return "", 0, "", _INTERVAL_FAST, True, no_update, True, False
    
    status = task["status"]
    
    # n = get_queue_length()
    info = f"{status} {task['task_name']}"

    if status == "PENDING":
        pos = get_queue_position(task["task_id"])
        interval = _INTERVAL_SLOW if pos > 1 else _INTERVAL_FAST
        return info, no_update, no_update, interval, False, no_update, True, True
    
    if status in {"COMPLETED", "ABORTED"}:
        return "", 100, "100%", _INTERVAL_FAST, False, task_id, True, True
    
    progress = int(task.get("progress") or 0)
    return info, progress, f"{progress}%", _INTERVAL_FAST, False, no_update, False, True


@callback(
    Output("poll", "n_intervals"),
    Output("task_id_current", "data"),
    Trigger("task_id_finished", "data"),
)
def next_job():
    user_name = get_user_name()
    user_id = get_user_id(user_name)
    task_id = get_next_user_task_id(user_id)
    return 0, task_id


@callback(
    Output("poll", "disabled"),
    Output("status", "children"),
    Output("poll", "n_intervals"),
    Output("task_id_current", "data"),
    Output("progress", "value"),
    Output("progress", "label"),
    Output("crd_body_clps_job", "is_open"),
    Trigger("btn_cancel_job", "n_clicks"),
    State("task_id_current", "data"),
)
def delete_current_task(task_id):
    if not task_id:
        return  True, no_update, no_update, no_update, no_update, no_update, no_update
    delete_task(task_id)    
    user_name = get_user_name()
    user_id = get_user_id(user_name)
    task_id = get_next_user_task_id(user_id)
    if not task_id:
        return True, "", 0, no_update, 0, "", False
    return False, "", 0, task_id, 0, "", True