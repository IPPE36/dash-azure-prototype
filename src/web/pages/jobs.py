# src/web/pages/jobs.py

import os
import uuid

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc, Input, State, Output, Trigger, no_update, callback, register_page, ALL, ctx
from dash.exceptions import PreventUpdate

from shared.db.users import get_user_id
from shared.db.tasks import add_task, get_queue_position, get_user_active_task_count, get_queue_length, get_user_task_rows, get_next_user_task_id, delete_task, get_task
from shared.celery_tasks import long_task
from web.auth import get_user_name
from web.layouts.sidebar import build_sidebar_layout


_MAX_USER_TASKS = os.getenv("MAX_USER_TASKS", 3)
_INTERVAL = os.getenv("JOB_INTERVAL", 1000)
STATUS_COLOR = {
    "RUNNING": "primary",
    "PENDING": "secondary",
    "ABORTED": "danger",
    "COMPLETED": "success",
}


register_page(__name__, path="/jobs")


job_card = dbc.Card([
    dcc.ConfirmDialog(id="cnf_job", message=""),
    dcc.Store(id="task_id_current", data=None),
    dcc.Store(id="task_id_finished", data=None),
    dcc.Interval(id="poll", interval=_INTERVAL, disabled=False, n_intervals=0, max_intervals=200),
    dbc.CardHeader([
        html.H5("Active Jobs", className="mb-2"),
        html.Div(
            dbc.InputGroup(
                [
                    dbc.Input(id="inp_submit_job", type="text", maxLength=60, placeholder="Job Name"),
                    dbc.Button("Submit", id="btn_submit_job", size="sm", color="primary"),
                ],
                className="flex-grow-1 me-2"
            ),
        )
    ]),
    html.Div(id="crd_body_job"),
    dbc.CardFooter([
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
                    animated=True,
                ),
            ],
            className="d-flex align-items-center",
        ),
    ]),
], style={"width": "50rem"})

# dbc.Collapse(
#     dbc.CardBody(
#         "HI"
#     ),
#     id="crd_body_clps_job",
#     is_open=False,
# ),
# dbc.Button("Cancel", disabled=True, id="btn_cancel_job", color="danger"),
#     Output("crd_body_clps_job", "is_open"),


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
    Trigger("inp_submit_job", "n_submit"),
    State("inp_submit_job", "value"),
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

    # schedule task with celery task id (string!)
    long_task.apply_async(
        args=[payload],
        kwargs={"task_id": task_id},
        task_id=celery_id,
    )

    task_id = get_next_user_task_id(user_id)
    return False, no_update, 0, False, task_id


def generate_task_rows(tasks: list[tuple]) -> list:
    children = []
    for t in tasks:
        color = STATUS_COLOR.get(t["status"], "secondary")
        row = dbc.CardBody(
            html.Div(
                [
                    dbc.Badge(t["status"], color=color, className="me-2"),
                    html.Span(t["task_name"], className="flex-grow-1 fw-bold"),
                    dbc.Button(
                        "Cancel",
                        id={"type": "btn_cancel_job", "index": t["task_id"]},
                        size="sm",
                        color="danger",
                        className="btn_cancel_job ms-3",
                    ),
                ],
                className="d-flex justify-content-between align-items-center",
            ),
            className="py-2 border-bottom",
        )
        children.append(row)
    return children


@callback(
    Output("crd_body_job", "children"),
    Output("progress", "value"),
    Output("progress", "label"),
    Output("poll", "disabled"),
    Output("task_id_finished", "data"),
    Input("poll", "n_intervals"),
    State("task_id_current", "data"),
)
def poll_job(n_intervals, task_id):

    if not n_intervals:
        raise PreventUpdate
    
    if task_id is None:
        return [], 0, "", True, no_update
    
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
        limit=_MAX_USER_TASKS
    )

    if status in {"COMPLETED", "ABORTED"}:
        user_tasks.append({"task_name": task["task_name"], "status": status, "task_id": task_id})

    children = generate_task_rows(user_tasks)

    if status in {"COMPLETED", "ABORTED"}:
        return children, 100, "100%", False, task_id
    
    if status == "PENDING":
        return children, no_update, no_update, False, no_update
    
    progress = int(task.get("progress") or 0)
    return children, progress, f"{progress}%", False, no_update


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
    Output("poll", "n_intervals"),
    Output("task_id_current", "data"),
    Output("progress", "value"),
    Output("progress", "label"),
    Input({"type": "btn_cancel_job", "index": ALL}, "n_clicks"),
    State("task_id_current", "data"),
)
def cancel_task(n_clicks, current_task_id):

    if not ctx.triggered:
        raise PreventUpdate

    if ctx.triggered[0]["value"] is None:
        raise PreventUpdate

    task_id_to_cancel = ctx.triggered_id["index"]

    user_name = get_user_name()
    user_id = get_user_id(user_name)
    if user_id is None:
        raise PreventUpdate

    task = get_task(task_id_to_cancel)
    if not task or task.get("user_id") != user_id:
        raise PreventUpdate

    delete_task(task_id_to_cancel)

    if task_id_to_cancel == current_task_id:
        next_task_id = get_next_user_task_id(user_id)
        if next_task_id is None:
            return True, 0, None, 0, ""
        return False, 0, next_task_id, 0, ""

    return False, 0, no_update, no_update, no_update