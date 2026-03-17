# src/web/callbacks/jobs.py

import os
import uuid

from dash import ctx
from dash_extensions.enrich import Input, State, Output, Trigger, no_update, callback, clientside_callback, MATCH
from dash.exceptions import PreventUpdate

from shared.db import get_user_id, add_task, get_queue_position, get_user_task_count, get_user_task_rows, get_next_user_task_id, delete_task, get_task, update_task
from shared.celery_tasks import long_task, short_task
from web.auth import get_user_name
from web.callbacks import toast_payload
from web.theme import CIRCLE_TAG


_MAX_USER_TASKS_ACTIVE = os.getenv("MAX_USER_TASKS_ACTIVE", 3)
_MAX_USER_TASKS_TOTAL = os.getenv("MAX_USER_TASKS_TOTAL", 50)


def register_callbacks_jobs():

    clientside_callback(
        "function(n){return n ? [true, 'jobs-settings-tab-bounds'] : [window.dash_clientside.no_update, window.dash_clientside.no_update];}",
        Output("jobs-settings-offcanvas", "is_open"),
        Output("jobs-settings-tabs", "active_tab"),
        Input("jobs-add-btn", "n_clicks"),
    )


    clientside_callback(
        """
        function(widthBreakpoint) {
            if (widthBreakpoint === "mobile") {
                return ["task_id", "status", "tag", "version"];
            } else if (widthBreakpoint === "tablet") {
                return ["task_id", "status", "version"];
            } else {
                return ["task_id", "status"];
            }
        }
        """,
        Output("jobs-table", "hidden_columns"),
        Input("breakpoints", "widthBreakpoint"),
        prevent_initial_call=False,
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
                return [false, false, false];
            }
            return [true, true, true];
        }
        """,
        Output("jobs-result-btn", "disabled"),
        Output("jobs-delete-btn", "disabled"),
        Output("jobs-tag-btn", "disabled"),
        Input("jobs-table", "selected_rows"),
    )

    clientside_callback(
        """
        function(rows) {
            const hasRows = Array.isArray(rows) && rows.length > 0;
            return [
                {display: hasRows ? "block" : "none"},
                {display: hasRows ? "flex" : "none"},
            ];
        }
        """,
        Output("jobs-search-group", "style"),
        Output("jobs-actions-group", "style"),
        Input("jobs-table", "data"),
    )

    clientside_callback(
        """
        function(selected_rows, data) {
            if (!selected_rows || selected_rows.length === 0 || !data) {
                return "";
            }

            const row = data[selected_rows[0]] || {};
            return row.tag || "";
        }
        """,
        Output("jobs-tag-inp", "value"),
        Input("jobs-table", "selected_rows"),
        State("jobs-table", "data"),
    )

    clientside_callback(
        """
        function(n_clicks, is_disabled) {
            if (!n_clicks) {
                throw window.dash_clientside.PreventUpdate;
            }

            const next_disabled = !Boolean(is_disabled);
            return [next_disabled, next_disabled];
        }
        """,
        Output({"type": "slider", "index": MATCH}, "disabled"),
        Output({"type": "slider_toggle", "index": MATCH}, "outline"),
        Input({"type": "slider_toggle", "index": MATCH}, "n_clicks"),
        State({"type": "slider", "index": MATCH}, "disabled"),
    )


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
        Output("toast-store", "data"),
        Output("jobs-poll", "disabled"),
        Output("jobs-current-id", "data"),
        Output("jobs-submit-inp", "value"),
        Output('jobs-table', 'selected_rows'),
        Output("jobs-settings-offcanvas", "is_open"),
        Input("jobs-submit-btn", "n_clicks"),
        Input("jobs-submit-inp", "n_submit"),
        State("jobs-submit-inp", "value"),
    )
    def cb_jobs_submit(n_clicks, n_submit, task_name):

        user_name = get_user_name()
        user_id = get_user_id(user_name)

        if not n_clicks and not n_submit:
            task_id = get_next_user_task_id(user_id)
            return no_update, False, task_id, no_update, no_update, no_update
        
        if not task_name:
            return (
                toast_payload("Job Submit", "No task name provided! Please enter...", kind="danger"),
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )
        
        n_active = get_user_task_count(user_id)
        if n_active >= _MAX_USER_TASKS_ACTIVE:
            message = f"Maximum number of user active tasks is {_MAX_USER_TASKS_ACTIVE}! Please wait until PENDING tasks complete..."
            return (
                toast_payload("Job Submit", message, kind="danger"),
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )
        
        n_total = get_user_task_count(user_id, statuses=None)
        if n_total >= _MAX_USER_TASKS_TOTAL:
            message = f"Maximum number of user total tasks is {_MAX_USER_TASKS_TOTAL}! Please delete old tasks in the database..."
            return (
                toast_payload("Job Submit", message, kind="danger"),
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )
        
        # schedule task with celery task id (string!)
        celery_id = str(uuid.uuid4())
        payload = 0
        task_id = add_task(
            user_id=user_id,
            task_name=task_name,
            input_payload={"x": payload},
        )
        if task_name.lower().startswith("short:"):
            short_task.apply_async(
                args=[payload],
                kwargs={"task_id": task_id},
                task_id=celery_id,
            )
        else:
            long_task.apply_async(
                args=[payload],
                kwargs={"task_id": task_id},
                task_id=celery_id,
            )

        task_id = get_next_user_task_id(user_id)
        message = f'Submit successful for task "{task_name}".'
        return toast_payload("Job Submit", message, kind="success"), False, task_id, "", [], False


    def sync_table():
        user_name = get_user_name()
        user_id = get_user_id(user_name)
        user_tasks = get_user_task_rows(
            user_id=user_id,
            include_payloads=False,
            columns={"status", "task_name", "tag", "version", "progress", "task_id", "created_at"},
            limit=_MAX_USER_TASKS_TOTAL,
            newest_first=True,
        )
        for i, t in enumerate(user_tasks):
            if t["status"] in {"PENDING"}:
                user_tasks[i]["status"] += f"-{get_queue_position(t['task_id'])-1}"
            if not t["version"].lower().startswith("v"):
                user_tasks[i]["version"] = f"v{user_tasks[i]['version']}"
            user_tasks[i]["status_icon"] = CIRCLE_TAG

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
        Output("toast-store", "data"),
        Input("jobs-search-btn", "n_clicks"),
        Input("jobs-search-inp", "n_submit"),
        State("jobs-search-inp", "value"),
    )
    def cb_jobs_search(n_clicks, n_submit, query):
        if not n_clicks and not n_submit:
            raise PreventUpdate

        rows = sync_table()
        if not query:
            return rows, no_update

        needle = query.strip().lower()
        if not needle:
            return rows, no_update

        def matches(row):
            for key in ("task_name", "tag", "status", "task_id", "created_at"):
                value = row.get(key)
                if value is None:
                    continue
                if needle in str(value).lower():
                    return True
            return False

        filtered = [row for row in rows if matches(row)]
        if not filtered:
            message = f'No tasks found for "{query}".'
            return rows, toast_payload("Search", message, kind="warning")
        return filtered, no_update



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
        task["status_icon"] = CIRCLE_TAG

        user_tasks = sync_table()

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
        Output("toast-store", "data"),
        Output("jobs-todelete-id", "data"),
        Trigger('jobs-delete-btn', "n_clicks"),
        State('jobs-table', 'selected_rows'),
        State('jobs-table', 'data'),
    )
    def cb_jobs_delete(selected_rows, data):
        if selected_rows is None:
            raise PreventUpdate
        if not len(selected_rows):
            return toast_payload("Delete", "No job selected.", kind="danger"), no_update
        task_id = data[selected_rows[0]]["task_id"]
        task = get_task(task_id)
        task_name = task["task_name"]
        message = f'Delete job "{task_name}"?'
        return (
            toast_payload(
                "Confirm Delete",
                message,
                kind="warning",
                duration=None,
                confirm_required=True,
                confirm_id="jobs-delete-confirm-btn",
                confirm_label="Delete",
                confirm_color="danger",
            ),
            {"task_id": task_id, "task_name": task_name},
        )


    @callback(
        Output("toast-store", "data"),
        Output("jobs-poll", "disabled"),
        Output("jobs-current-id", "data"),
        Output("jobs-progress", "value"),
        Output("jobs-progress-text", "children"),
        Output("jobs-refresh-btn", "n_clicks"),
        Input("app-toast-cancel-btn", "n_clicks"),
        Input("jobs-delete-confirm-btn", "n_clicks"),
        State("jobs-todelete-id", "data"),
        State("jobs-current-id", "data"),
        prevent_initial_call=True,
    )
    def cb_jobs_delete_confirm(n1, n2, task_data, current_task_id):
        if not n1 and not n2:
            raise PreventUpdate

        if ctx.triggered_id == "app-toast-cancel-btn":
            return no_update, no_update, no_update, no_update, no_update, no_update

        if ctx.triggered_id != "jobs-delete-confirm-btn":
            raise PreventUpdate

        if not task_data:
            raise PreventUpdate

        task_id = task_data["task_id"]
        label = task_data["task_name"]

        delete_task(task_id)
        msg = f'Deleted Task "{label}"!'

        if task_id == current_task_id:
            user_name = get_user_name()
            user_id = get_user_id(user_name)
            if user_id is None:
                raise PreventUpdate

            next_task_id = get_next_user_task_id(user_id)

            if next_task_id is None:
                return (
                    toast_payload("Delete", msg, kind="success"),
                    True,
                    None,
                    0,
                    "0%",
                    0,
                )

            return (
                toast_payload("Delete", msg, kind="success"),
                False,
                next_task_id,
                0,
                "0%",
                0,
            )

        return toast_payload("Delete", msg, kind="success"), no_update, no_update, no_update, no_update, 0


    @callback(
        Output("jobs-table", "data"),
        Output("jobs-tag-inp", "value"),
        Output("toast-store", "data"),
        Input("jobs-tag-btn", "n_clicks"),
        Input("jobs-tag-inp", "n_submit"),
        State("jobs-tag-inp", "value"),
        State("jobs-table", "selected_rows"),
        State("jobs-table", "data"),
    )
    def cb_jobs_apply_tag(n_clicks, n_submit, tag_value, selected_rows, data):
        if not n_clicks and not n_submit:
            raise PreventUpdate
        if not selected_rows or not data:
            raise PreventUpdate

        row = data[selected_rows[0]] or {}
        task_id = row.get("task_id")
        if task_id is None:
            raise PreventUpdate

        tag = (tag_value or "").strip()
        task_name = row.get("task_name")
        updated = update_task(task_id, tag=tag or None)
        if not updated:
            return (
                no_update,
                no_update,
                toast_payload("Tag", "Tag update failed. Please try again.", kind="danger"),
            )
        message = f'Applied tag "{tag}" to task "{task_name}".' if tag else f'Tag cleared for task "{task_name}".'
        return (
            sync_table(),
            tag,
            toast_payload("Tag", message, kind="success", duration=3000),
        )


