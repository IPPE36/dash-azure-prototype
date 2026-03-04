# src/web/pages/jobs.py
import time

from celery.result import AsyncResult
import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc, Input, Output, State, callback, register_page
from dash.exceptions import PreventUpdate

from shared.celery_app import celery_app
from shared.db import get_task_run
from shared.tasks import long_task
from web.auth import get_user_name
from web.layouts import build_sidebar_layout

register_page(__name__, path="/jobs")

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
            dcc.Interval(id="poll", interval=500, disabled=True),
            dbc.Progress(
                id="progress",
                value=0,
                max=100,
                label="0%",
                striped=True,
                animated=False,
                style={"height": "28px", "marginTop": "12px"},
            ),
            html.Div(id="status", children="Idle."),
        ]
    ),
)


@callback(
    Output("task-store", "data"),
    Output("task-meta", "data"),
    Output("poll", "disabled"),
    Output("status", "children"),
    Output("progress", "value"),
    Output("progress", "label"),
    Output("progress", "color"),
    Output("progress", "animated"),
    Input("btn", "n_clicks"),
)
def start_job(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    user_name = get_user_name() or "unknown-user"
    duration_s = 10
    res = long_task.delay(n_clicks, user_id=user_name, duration_s=duration_s)
    return (
        {"task_id": res.id},
        {"started_at": time.time(), "duration_s": duration_s},
        False,
        f"Queued task: {res.id} (user={user_name})",
        0,
        "0%",
        "info",
        True,
    )


@callback(
    Output("status", "children"),
    Output("poll", "disabled"),
    Output("progress", "value"),
    Output("progress", "label"),
    Output("progress", "color"),
    Output("progress", "animated"),
    Input("poll", "n_intervals"),
    State("task-store", "data"),
    State("task-meta", "data"),
)
def poll_job(_, data, meta):
    if not _:
        raise PreventUpdate
    if not data:
        return "No task.", True, 0, "0%", "secondary", False

    task_id = data["task_id"]
    r = AsyncResult(task_id, app=celery_app)
    db_row = get_task_run(task_id)

    if r.successful():
        if db_row is not None:
            input_payload = db_row.get("input_payload")
            output_payload = db_row.get("output_payload")
            user_id = db_row.get("user_id")
            return (
                f"Done (DB): user={user_id}, input={input_payload}, output={output_payload}",
                True,
                100,
                "100%",
                "success",
                False,
            )
        return f"Done: {r.result}", True, 100, "100%", "success", False

    if r.failed():
        if db_row is not None and db_row.get("error_payload"):
            return f"Failed (DB): {db_row['error_payload']}", True, 100, "Failed", "danger", False
        return f"Failed: {r.result}", True, 100, "Failed", "danger", False

    duration_s = max(1, int((meta or {}).get("duration_s", 10)))
    started_at = float((meta or {}).get("started_at", time.time()))
    elapsed = max(0.0, time.time() - started_at)
    pct = min(95, int((elapsed / duration_s) * 100))
    return f"State: {r.state}", False, pct, f"{pct}%", "info", True
