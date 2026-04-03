import dash_bootstrap_components as dbc
from dash import dcc, html

from web.layouts.carousel import MediaCarousel


def build_layout_home():
    slide_height = "calc(100vh - var(--navbar-height))"
    video_style = {"height": slide_height, "objectFit": "cover"}
    overlay_style = {
        "position": "absolute",
        "inset": "0",
        "backgroundColor": "var(--bs-dark)",
        "opacity": "0.75",
        "pointerEvents": "none",
        "zIndex": "0",
    }

    def video_block(src: str, icon_class: str, headline: str, blurb: str, href: str):
        return html.Div(
            [
                html.Video(
                    src=src,
                    autoPlay=True,
                    muted=True,
                    loop=True,
                    className="d-block w-100",
                    style=video_style,
                ),
                html.Div(style=overlay_style),
                html.Div(
                    [
                        html.I(
                            className=f"{icon_class} fa-3x d-block mx-auto mb-3",
                        ),
                        html.Div(headline, className="fs-2 fw-semibold mb-2"),
                        html.P(blurb, className="mb-3 fs-6"),
                        dbc.Button(
                            f"Open {headline}",
                            href=href,
                            color="light",
                            outline=True,
                            className="px-4",
                            size="lg",
                        ),
                    ],
                    className="position-absolute top-50 start-50 translate-middle text-center text-light",
                    style={"maxWidth": "720px", "padding": "0 16px", "zIndex": "2"},
                ),
            ],
            className="position-relative",
            style={"height": slide_height},
        )

    def main_slide():
        quick_actions = [
            {
                "label": "Open Jobs",
                "id": {"type": "home-carousel-jump", "index": 1},
                "className": "home-jobs-btn",
            },
            {
                "label": "Open Predictions",
                "id": {"type": "home-carousel-jump", "index": 2},
                "className": "home-pred-btn",
            },
        ]

        return html.Div(
            [
                html.Div(
                    [
                        html.I(className="fa-solid fa-compass fa-3x d-block mx-auto mb-3"),
                        html.Div("Quick Access", className="fs-2 fw-semibold mb-2"),
                        html.Div(
                            [
                                html.Div(
                                    html.Button(
                                        action["label"],
                                        id=action["id"],
                                        type="button",
                                        className=f"btn btn-outline-primary {action['className']} w-100",
                                        **{
                                            "data-bs-target": "#home-carousel",
                                            "data-bs-slide-to": str(action["id"]["index"]),
                                        },
                                    ),
                                    className="home-action-btn",
                                )
                                for action in quick_actions
                            ],
                            className="home-action-group",
                        ),
                    ],
                    className="position-absolute top-50 start-50 translate-middle text-center text-dark",
                    style={"maxWidth": "720px", "padding": "0 16px", "zIndex": "2"},
                ),
            ],
            className="position-relative",
            style={"height": slide_height},
        )

    slides = [
        {
            "key": "main",
            "header": None,
            "caption": None,
            "href": None,
            "content": main_slide(),
            "subcaption": None,
        },
        {
            "key": "jobs",
            "header": None,
            "caption": None,
            "href": "/jobs",
            "content": video_block(
                "https://samplelib.com/lib/preview/mp4/sample-5s.mp4",
                "fa-solid fa-briefcase",
                "Jobs Hub",
                "Launch and monitor background runs in one place. Track progress, review logs, "
                "and organize results without leaving the dashboard.",
                "/jobs",
            ),
            "subcaption": None,
        },
        {
            "key": "predictions",
            "header": None,
            "caption": None,
            "href": "/predictions",
            "content": video_block(
                "https://samplelib.com/lib/preview/mp4/sample-10s.mp4",
                "fa-solid fa-chart-line",
                "Model Insights",
                "Explore predictions with confidence. Compare targets, inspect uncertainty, "
                "and spot trends across the models you serve.",
                "/predictions",
            ),
            "subcaption": None,
        },
    ]

    return dbc.Container(
        [
            dcc.Store(id="home-carousel-jump"),
            MediaCarousel(
                id="home-carousel",
                items=slides,
                controls=True,
                indicators=True,
                interval=None,
                ride="carousel",
                className="w-100",
                style={"height": slide_height},
            )(),
        ],
        fluid=True,
        className="app-main px-0 py-0",
        style=dict(overflow="hidden"),
    )
