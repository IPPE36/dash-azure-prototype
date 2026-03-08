
# src/web/layout/page_jobs.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc, dash_table

from web.theme import TRANSPARENT


COLUMNS = [
    {"name": "ID", "id": "task_id", "editable": False},
    {"name": "STATUS", "id": "status", "editable": False},
    {"name": "LABEL", "id": "task_name", "editable": True},
]


def build_active_job_card(interval: int, width="50rem"):
    job_card = dbc.Card([
        dcc.ConfirmDialog(id="jobs-submit-msg", message=""),
        dcc.ConfirmDialog(id="jobs-delete-msg", message=""),
        dcc.ConfirmDialog(id="jobs-delete-confirm", message=""),
        dcc.Store(id="jobs-current-id", data=None),
        dcc.Store(id="jobs-finished-id", data=None),
        dcc.Store(id="jobs-todelete-id", data=None),
        dcc.Interval(id="jobs-poll", interval=interval, disabled=False, n_intervals=0, max_intervals=300),
        dbc.CardHeader([
            html.H5("Active Jobs", className="mb-2"),
            html.Div(
                dbc.InputGroup(
                    [
                        dbc.Input(id="jobs-submit-inp", type="text", maxLength=60, placeholder="Job Name"),
                        dbc.Button("Submit", id="jobs-submit-btn", size="sm", color="primary"),
                    ],
                    className="flex-grow-1 me-2"
                ),
            )
        ]),
        dbc.Collapse(
            dbc.CardHeader(
                [
                    html.Div(
                        [
                            html.Span("Progress:", className="me-3"),
                            dbc.Progress(
                                id="jobs-progress",
                                value=0,
                                max=100,
                                color="primary",
                                className="flex-grow-1 me-3",
                            ),
                            html.Div(
                                "0%",
                                id="jobs-progress-text",
                                style={"minWidth": "45px", "textAlign": "right"},
                            ),
                        ],
                        className="d-flex align-items-center",
                    ),
                ]
            ),
            id="jobs-active-container-collapse",
            is_open=False,
        ),
        html.Div(
            dash_table.DataTable(
                id="jobs-table",
                columns=COLUMNS,
                row_deletable=False,
                editable=False,
                cell_selectable=False,
                row_selectable="single",
                style_as_list_view=True,
                page_size=10,
                style_header={"display": "none"},
                style_cell={"backgroundColor": TRANSPARENT, "textAlign": "left"},
                hidden_columns=["task_id"],
                css=[
                    {"selector": ".show-hide", "rule": "display: none"},  # hides toggle columns button
                    {"selector": "tr:first-child", "rule": "display: none"},  # hides header row
                ],
            ), 
        ),
        dbc.CardFooter(
            html.Div(
                className="d-flex gap-2",
                children=[
                    dbc.Button("Load Results", id="jobs-result-btn", size="sm", color="secondary", disabled=True),
                    dbc.Button("Delete", id="jobs-delete-btn", size="sm", color="secondary", disabled=True),
                ],
            )
        ),
    ], style={"width": width})
    return job_card