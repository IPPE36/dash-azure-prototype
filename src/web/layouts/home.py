import dash_bootstrap_components as dbc
from dash import html


def build_layout_home():
    cards = [
        {
            "title": "Jobs",
            "subtitle": "Run and monitor tasks",
            "info": "Launch background runs, track progress, and review logs in one place.",
            "href": "/jobs",
            "icon": "fa-solid fa-briefcase",
        },
        {
            "title": "Pred",
            "subtitle": "Model results and insights",
            "info": "Explore predictions, compare outputs, and inspect confidence.",
            "href": "/pred",
            "icon": "fa-solid fa-chart-line",
        },
        {
            "title": "Explore",
            "subtitle": "Discover patterns and datasets",
            "info": "Browse datasets, slice results, and discover useful signals.",
            "href": "/explore",
            "icon": "fa-solid fa-compass",
        },
    ]

    def build_card(card):
        return dbc.Card(
            dbc.CardBody(
                [
                    html.Div(
                        [
                            html.I(className=f"{card['icon']} fa-2x"),
                            html.Div(card["title"], className="fs-3 fw-semibold"),
                        ],
                        className="d-flex align-items-center gap-3 mb-2",
                    ),
                    html.Div(card["subtitle"], className="text-muted mb-3"),
                    html.P(card["info"], className="mb-3"),
                    dbc.Button(
                        f"Open {card['title']}",
                        href=card["href"],
                        color="primary",
                        outline=True,
                        className="w-100",
                    ),
                ]
            ),
            className="h-100 shadow-sm",
        )

    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.Div(
                                    "GENEC",
                                    className="display-4 fw-bold text-uppercase mb-2",
                                ),
                                html.Div(
                                    "Precision optimization for industrial operations.",
                                    className="fs-4 text-muted",
                                ),
                            ],
                            className="py-4",
                        ),
                        xs=12,
                    )
                ],
                className="mb-2",
            ),
            dbc.Row(
                [dbc.Col(build_card(card), xs=12, md=4, className="mb-3") for card in cards],
                className="g-3",
            )
        ],
        fluid=True,
        className="app-main bg-light px-3 py-3",
    )
