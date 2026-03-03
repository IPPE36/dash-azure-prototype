# src/web/pages/jobs.py
from celery.result import AsyncResult
from dash_extensions.enrich import html, dcc, Input, Output, State, callback, register_page
from dash.exceptions import PreventUpdate

from shared.celery_app import celery_app
from shared.db import get_task_run
from shared.tasks import long_task
from web.auth import get_user_name

register_page(__name__, path="/jobs")

layout = html.Div(
    [
        html.H3("Jobs"),
        html.Button("Start background job", id="btn"),
        dcc.Store(id="task-store"),
        dcc.Interval(id="poll", interval=1000, disabled=True),
        html.Div(id="status", children="Idle."),
    ]
)


@callback(
    Output("task-store", "data"),
    Output("poll", "disabled"),
    Output("status", "children"),
    Input("btn", "n_clicks"),
)
def start_job(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    res = long_task.delay(n_clicks)
    user_name = get_user_name() or "unknown-user"
    return {"task_id": res.id}, False, f"Queued task: {res.id} (user={user_name})"


@callback(
    Output("status", "children"),
    Output("poll", "disabled"),
    Input("poll", "n_intervals"),
    State("task-store", "data"),
)
def poll_job(_, data):
    if not _:
        raise PreventUpdate
    if not data:
        return "No task.", True

    task_id = data["task_id"]
    r = AsyncResult(task_id, app=celery_app)
    db_row = get_task_run(task_id)

    if r.successful():
        if db_row is not None:
            input_payload = db_row.get("input_payload")
            output_payload = db_row.get("output_payload")
            return (
                f"Done (DB): input={input_payload}, output={output_payload}",
                True,
            )
        return f"Done: {r.result}", True

    if r.failed():
        if db_row is not None and db_row.get("error_payload"):
            return f"Failed (DB): {db_row['error_payload']}", True
        return f"Failed: {r.result}", True

    return f"State: {r.state}", False
