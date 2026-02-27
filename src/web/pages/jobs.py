# src/web/pages/jobs.py
import dash
from celery.result import AsyncResult
from dash_extensions.enrich import html, dcc, Input, Output, State, callback, register_page
from dash.exceptions import PreventUpdate

from shared.celery_app import celery_app
from shared.tasks import long_task

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
    return {"task_id": res.id}, False, f"Queued task: {res.id}"


@callback(
    Output("status", "children"),
    Output("poll", "disabled"),
    Input("poll", "n_intervals"),
    State("task-store", "data"),
    # background=True,
)
def poll_job(_, data):
    if not _:
        raise PreventUpdate
    if not data:
        return "No task.", True
    r = AsyncResult(data["task_id"], app=celery_app)
    if r.successful():
        return f"✅ Done: {r.result}", True
    if r.failed():
        return f"❌ Failed: {r.result}", True
    return f"⏳ State: {r.state}", False