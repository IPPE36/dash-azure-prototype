# src/web/pages/jobs.py

import os
import uuid


from dash_extensions.enrich import Input, State, Output, Trigger, no_update, callback, clientside_callback, register_page
from dash.exceptions import PreventUpdate

from shared.db.users import get_user_id
from shared.db.tasks import add_task, get_queue_position, get_user_task_count, get_user_task_rows, get_next_user_task_id, delete_task, get_task
from shared.celery_tasks import long_task
from web.auth import get_user_name
from web.layouts import build_jobs_main
from web.theme import TABLE_TAG_UNICODE


_PAGE_NAME = "Jobs"
_MAX_USER_TASKS_ACTIVE = os.getenv("MAX_USER_TASKS_ACTIVE", 3)
_MAX_USER_TASKS_TOTAL = os.getenv("MAX_USER_TASKS_TOTAL", 50)


register_page(__name__, path="/jobs", title=_PAGE_NAME)

layout = build_jobs_main()


clientside_callback(
    "function(n){return n ? true : window.dash_clientside.no_update;}",
    Output("jobs-settings-offcanvas", "is_open"),
    Input("jobs-add-btn", "n_clicks"),
)


clientside_callback(
    """
    function(widthBreakpoint) {
        if (widthBreakpoint === "mobile") {
            return ["task_id", "status", "created_at"];
        } else if (widthBreakpoint === "tablet") {
            return ["task_id", "status"];
        } else {
            return ["task_id"];
        }
    }
    """,
    Output("jobs-table", "hidden_columns"),
    Input("breakpoints", "widthBreakpoint"),
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
    Output("jobs-history-container", "is_open"),
    Output("jobs-results-container", "is_open"),
    Input("jobs-tabs", "active_tab"),
)
def cb_jobs_tabs(active_tab):
    is_history = active_tab == "jobs-tab-history"
    is_results = active_tab == "jobs-tab-results"
    return is_history, is_results


@callback(
    Output("jobs-results-graph", "figure"),
    Output("jobs-tabs", "active_tab"),
    Trigger("jobs-result-btn", "n_clicks"),
    State("jobs-table", "selected_rows"),
    State("jobs-table", "data"),
)
def cb_jobs_results(selected_rows, data):
    if not selected_rows:
        raise PreventUpdate
    if not data:
        raise PreventUpdate

    task_id = data[selected_rows[0]].get("task_id")
    if task_id is None:
        raise PreventUpdate

    task = get_task(task_id, include_payloads=True)
    if not task:
        raise PreventUpdate

    payload = task.get("output_payload") or []
    if not isinstance(payload, list):
        raise PreventUpdate

    x_vals = [row.get("x") for row in payload if isinstance(row, dict)]
    y_vals = [row.get("y") for row in payload if isinstance(row, dict)]
    z_vals = [row.get("z") for row in payload if isinstance(row, dict)]

    figure = {
        "data": [
            {
                "type": "scatter3d",
                "mode": "markers",
                "x": x_vals,
                "y": y_vals,
                "z": z_vals,
                "marker": {"size": 3, "color": "var(--bs-primary)"},
            }
        ],
        "layout": {
            "height": 320,
            "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
            "scene": {
                "xaxis": {"title": "x"},
                "yaxis": {"title": "y"},
                "zaxis": {"title": "z"},
            },
        },
    }

    return figure, "jobs-tab-results"


@callback(
    Output("jobs-submit-msg", "displayed"),
    Output("jobs-submit-msg", "message"),
    Output("jobs-poll", "disabled"),
    Output("jobs-current-id", "data"),
    Output("jobs-submit-inp", "value"),
    Output('jobs-table', 'selected_rows'),
    Input("jobs-submit-btn", "n_clicks"),
    Input("jobs-submit-inp", "n_submit"),
    State("jobs-submit-inp", "value"),
)
def cb_jobs_submit(n_clicks, n_submit, task_name):

    user_name = get_user_name()
    user_id = get_user_id(user_name)

    if not n_clicks and not n_submit:
        task_id = get_next_user_task_id(user_id)
        return no_update, no_update, False, task_id, no_update, no_update
    
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
    return False, no_update, False, task_id, "", []


def sync_table():
    user_name = get_user_name()
    user_id = get_user_id(user_name)
    user_tasks = get_user_task_rows(
        user_id=user_id,
        include_payloads=False,
        columns={"status", "task_name", "progress", "task_id", "created_at"},
        limit=_MAX_USER_TASKS_TOTAL,
        newest_first=True,
    )
    for i, t in enumerate(user_tasks):
        if t["status"] in {"PENDING"}:
            user_tasks[i]["status"] += f"-{get_queue_position(t['task_id'])-1}"
        user_tasks[i]["status_icon"] = TABLE_TAG_UNICODE
    return user_tasks


@callback(
    Output("jobs-table", "data"),
    Trigger("jobs-refresh-btn", "id"),
    Trigger("jobs-refresh-btn", "n_clicks"),
    prevent_initial_call=False,
)
def cb_jobs_refresh():
    return sync_table()


@callback(
    Output("jobs-table", "data"),
    Output("jobs-search-msg", "displayed"),
    Output("jobs-search-msg", "message"),
    Input("jobs-search-btn", "n_clicks"),
    Input("jobs-search-inp", "n_submit"),
    State("jobs-search-inp", "value"),
    prevent_initial_call=True,
)
def cb_jobs_search(n_clicks, n_submit, query):
    if not n_clicks and not n_submit:
        raise PreventUpdate

    rows = sync_table()
    if not query:
        return rows, False, no_update

    needle = query.strip().lower()
    if not needle:
        return rows, False, no_update

    def matches(row):
        for key in ("task_name", "status", "task_id", "created_at"):
            value = row.get(key)
            if value is None:
                continue
            if needle in str(value).lower():
                return True
        return False

    filtered = [row for row in rows if matches(row)]
    if not filtered:
        return rows, True, f'No tasks found for "{query}".'
    return filtered, False, no_update



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
def cb_jobs_poll(task_id):
    
    if task_id is None:
        return 0, "0%", True, no_update, False, no_update

    task = get_task(task_id)
    if task is None:
        return 0, "0%", True, no_update, False, no_update

    status = task["status"]
    task["status_icon"] = TABLE_TAG_UNICODE

    user_tasks = sync_table()
    if status in {"COMPLETED", "ABORTED"}:
        user_tasks.append({
            "task_name": task["task_name"],
            "status": status,
            "task_id": task_id,
            "progress": task["progress"],
            "created_at": task["created_at"],
        })

    if status in {"COMPLETED", "ABORTED"}:
        return 100, "100%", False, task_id, True, user_tasks
    
    if status == "PENDING":
        return no_update, no_update, False, no_update, True, user_tasks
    
    progress = int(task.get("progress") or 0)
    return progress, f"{progress}%", False, no_update, True, user_tasks


@callback(
    Output("jobs-current-id", "data"),
    Trigger("jobs-finished-id", "data"),
)
def cb_jobs_next():
    user_name = get_user_name()
    user_id = get_user_id(user_name)
    task_id = get_next_user_task_id(user_id)
    return task_id


@callback(
    Output('jobs-delete-confirm', 'displayed'),
    Output('jobs-delete-confirm', 'message'),
    Output('jobs-todelete-id', 'data'),
    Trigger('jobs-delete-btn', "n_clicks"),
    State('jobs-table', 'selected_rows'),
    State('jobs-table', 'data'),
)
def cb_jobs_delete(selected_rows, data):
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
    Output("jobs-current-id", "data"),
    Output("jobs-progress", "value"),
    Output("jobs-progress-text", "children"),
    Output("jobs-refresh-btn", "n_clicks"),  # refreshes table upon delete
    Trigger("jobs-delete-confirm", "submit_n_clicks"),
    State("jobs-todelete-id", "data"),
    State("jobs-current-id", "data"),
)
def cb_jobs_delete_confirm(task_data, current_task_id):
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
            return True, msg, True, None, 0, "0%", 0

        return True, msg, False, next_task_id, 0, "0%", 0

    return True, msg, no_update, no_update, no_update, no_update, 0


