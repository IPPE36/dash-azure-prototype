# src/web/pages/jobs.py

import time
from uuid import uuid4

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc, Input, Output, callback, register_page
from dash.exceptions import PreventUpdate

from shared.celery_app import celery_app
from shared.db.tasks import add_task, delete_task_run, get_task_queue_position, get_user_task_monitor
from shared.tasks import long_task
from web.auth import get_user_name
from web.layouts.layout_sidebar import build_sidebar_layout

register_page(__name__, path="/jobs")
PROGRESS_VISIBLE_STYLE = {"height": "28px", "marginTop": "12px"}
PROGRESS_HIDDEN_STYLE = {"height": "28px", "marginTop": "12px", "display": "none"}
BUTTON_VISIBLE_STYLE = {"marginTop": "12px", "display": "inline-block"}
BUTTON_HIDDEN_STYLE = {"marginTop": "12px", "display": "none"}
FAST_POLL_MS = 1000
IDLE_POLL_MS = 30000


def _render_monitor(monitor):
    mode = monitor.get("mode", "idle")
    if mode == "running":
        progress = int(monitor.get("progress", 0))
        return (
            f"Queue position: {monitor['position']}/{monitor['total_active']}",
            False,
            FAST_POLL_MS,
            progress,
            f"{progress}%",
            "info",
            True,
            PROGRESS_VISIBLE_STYLE,
            BUTTON_VISIBLE_STYLE,
        )
    if mode == "pending":
        return (
            f"Pending. Next of your tasks is position {monitor['position']} in queue.",
            False,
            FAST_POLL_MS,
            0,
            "Pending",
            "secondary",
            False,
            PROGRESS_VISIBLE_STYLE,
            BUTTON_VISIBLE_STYLE,
        )
    return (
        "No active or pending tasks.",
        False,
        IDLE_POLL_MS,
        0,
        "0%",
        "secondary",
        False,
        PROGRESS_HIDDEN_STYLE,
        BUTTON_HIDDEN_STYLE,
    )

layout = build_sidebar_layout(
    page_title="Jobs",
    nav_items=[
        ("Home", "/"),
        ("Jobs", "/jobs"),
    ],
    content=html.Div(
        [
            html.Button("Start background job", id="btn"),
            dcc.Store(id="task-store"),
            dcc.Store(id="task-meta"),
            dcc.Interval(id="poll", interval=IDLE_POLL_MS, disabled=False),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Progress(
                            id="progress",
                            value=0,
                            max=100,
                            label="0%",
                            striped=True,
                            animated=False,
                            style=PROGRESS_HIDDEN_STYLE,
                        ),
                        xs=10,
                        md=11,
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Delete",
                            id="btn-cancel-task",
                            color="danger",
                            size="sm",
                            className="rounded-0",
                            style=BUTTON_HIDDEN_STYLE,
                        ),
                        xs=2,
                        md=1,
                        className="d-flex align-items-start justify-content-end",
                    ),
                ],
                className="g-2 align-items-start",
            ),
            html.Div(id="status", children="Idle."),
        ]
    ),
)


@callback(
    Output("task-store", "data"),
    Output("task-meta", "data"),
    Output("poll", "disabled"),
    Output("poll", "interval"),
    Output("status", "children"),
    Output("progress", "value"),
    Output("progress", "label"),
    Output("progress", "color"),
    Output("progress", "animated"),
    Output("progress", "style"),
    Output("btn-cancel-task", "style"),
    Input("btn", "n_clicks"),
)
def start_job(n_clicks):
    if not n_clicks:
        raise PreventUpdate

    user_name = get_user_name() or "unknown-user"
    duration_s = 10
    task_id = str(uuid4())
    add_task(
        celery_task_id=task_id,
        task_name="long_task",
        input_payload={"x": n_clicks, "duration_s": duration_s},
        user_id=user_name,
        status="PENDING",
    )
    res = long_task.apply_async(args=[n_clicks], kwargs={"user_id": user_name, "duration_s": duration_s}, task_id=task_id)
    queue_info = get_task_queue_position(task_id)
    queue_status = ""
    if queue_info is not None and queue_info.get("position") is not None:
        queue_status = f" | queue position: {queue_info['position']}/{queue_info['total_active']}"
    return (
        {"task_id": res.id},
        {"started_at": time.time(), "duration_s": duration_s},
        False,
        FAST_POLL_MS,
        f"Queued task: {res.id} (user={user_name}){queue_status}",
        0,
        "Pending",
        "secondary",
        False,
        PROGRESS_VISIBLE_STYLE,
        BUTTON_VISIBLE_STYLE,
    )


@callback(
    Output("status", "children"),
    Output("poll", "disabled"),
    Output("poll", "interval"),
    Output("progress", "value"),
    Output("progress", "label"),
    Output("progress", "color"),
    Output("progress", "animated"),
    Output("progress", "style"),
    Output("btn-cancel-task", "style"),
    Input("poll", "n_intervals"),
)
def poll_job(_):
    if not _:
        raise PreventUpdate
    user_name = get_user_name() or "unknown-user"
    monitor = get_user_task_monitor(user_name)
    return _render_monitor(monitor)


@callback(
    Output("status", "children"),
    Output("poll", "disabled"),
    Output("poll", "interval"),
    Output("progress", "value"),
    Output("progress", "label"),
    Output("progress", "color"),
    Output("progress", "animated"),
    Output("progress", "style"),
    Output("btn-cancel-task", "style"),
    Input("btn-cancel-task", "n_clicks"),
)
def cancel_oldest_task(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    user_name = get_user_name() or "unknown-user"
    monitor = get_user_task_monitor(user_name)
    if monitor.get("mode") == "idle":
        return _render_monitor(monitor)

    task_id = monitor.get("task_id")
    if task_id:
        try:
            celery_app.control.revoke(task_id, terminate=(monitor.get("mode") == "running"))
        except Exception:
            pass
        delete_task_run(task_id)

    updated_monitor = get_user_task_monitor(user_name)
    rendered = _render_monitor(updated_monitor)
    return (
        f"Deleted task: {task_id}",
        rendered[1],
        rendered[2],
        rendered[3],
        rendered[4],
        rendered[5],
        rendered[6],
        rendered[7],
        rendered[8],
    )
