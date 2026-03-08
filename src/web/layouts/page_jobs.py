
# src/web/layout/page_jobs.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc

from web.theme import JOBS_STATUS_COLOR


def build_active_job_card(interval: int, width="30rem"):
    job_card = dbc.Card([
        html.Tr(
            [
                html.Td("1"),
                html.Td("Train Model"),
                html.Td("RUNNING"),
            ],
            id={"type": "task-row", "index": 1},
            n_clicks=0,
            style={"cursor": "pointer"}
        ),
        dcc.ConfirmDialog(id="jobs-confirm", message=""),
        dcc.Store(id="jobs-current-id", data=None),
        dcc.Store(id="jobs-finished-id", data=None),
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
        html.Div(id="jobs-active-container"),
        dbc.Collapse(
            dbc.CardFooter(
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
        )
    ], style={"width": width})
    return job_card


def build_active_task_rows(tasks: list[dict]) -> list:
    children = []

    for t in tasks:
        color = JOBS_STATUS_COLOR.get(t["status"], "secondary")
        info_pos = f" {t['pos']-1}" if t["status"] == "PENDING" else ""
        info = f"{t['status']}{info_pos}"

        row = dbc.CardBody(
            html.Div(
                [
                    dbc.Badge(
                        info,
                        color=color,
                        className="me-3 text-start",
                        style={"display": "inline-block"},
                        pill=True,
                    ),
                    html.Span(
                        t["task_name"],
                        className=f"flex-grow-1 fw-semibold me-3 text-{color}",
                        style={
                            "whiteSpace": "nowrap",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "minWidth": "0",
                        },
                    ),
                    dbc.Button(
                        id={"type": "jobs-cancel-btn", "index": t["task_id"]},
                        size="sm",
                        color="danger",
                        className="jobs-cancel-btn flex-shrink-0",
                    ),
                ],
                className="d-flex align-items-center w-100",
                style={"minWidth": "0"},
            ),
            className="py-2 border-bottom",
        )

        children.append(row)

    return children