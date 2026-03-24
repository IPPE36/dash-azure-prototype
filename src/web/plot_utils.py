# src/web/plot_utils.py

from typing import Sequence

import plotly.graph_objects as go


DEFAULT_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "responsive": True,
}


def _base_layout(
    *,
    title: str | None = None,
    height: int = 320,
    show_legend: bool = False,
    margin: int = 10,
) -> dict:
    layout = {
        "autosize": True,
        "height": height,
        "margin": {"l": margin, "r": margin, "t": margin, "b": margin},
        "showlegend": show_legend,
        "template": "simple_white",
    }
    if title:
        layout["title"] = {"text": title}
    return layout


def bar_figure(
    x: Sequence,
    y: Sequence,
    *,
    name: str | None = None,
    title: str | None = None,
    color: str = "var(--bs-primary)",
    height: int = 320,
) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Bar(
                x=list(x),
                y=list(y),
                name=name,
                marker={"color": color},
            )
        ]
    )
    fig.update_layout(_base_layout(title=title, height=height))
    return fig


def polar_figure(
    r: Sequence,
    theta: Sequence,
    *,
    name: str | None = None,
    title: str | None = None,
    mode: str = "markers",
    color: str = "var(--bs-primary)",
    height: int = 320,
) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=list(r),
                theta=list(theta),
                mode=mode,
                name=name,
                marker={"color": color, "size": 6},
                line={"color": color},
            )
        ]
    )
    fig.update_layout(_base_layout(title=title, height=height))
    return fig


def scatter_figure(
    x: Sequence,
    y: Sequence,
    *,
    name: str | None = None,
    title: str | None = None,
    color: str = "var(--bs-primary)",
    height: int = 320,
) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Scatter(
                x=list(x),
                y=list(y),
                mode="markers",
                name=name,
                marker={"color": color, "size": 6},
            )
        ]
    )
    fig.update_layout(_base_layout(title=title, height=height))
    return fig


def scatter3d_figure(
    x: Sequence,
    y: Sequence,
    z: Sequence,
    *,
    name: str | None = None,
    title: str | None = None,
    color: str = "var(--bs-primary)",
    height: int = 320,
) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=list(x),
                y=list(y),
                z=list(z),
                mode="markers",
                name=name,
                marker={"color": color, "size": 3},
            )
        ]
    )
    fig.update_layout(
        _base_layout(title=title, height=height)
        | {
            "scene": {
                "xaxis": {"title": "x"},
                "yaxis": {"title": "y"},
                "zaxis": {"title": "z"},
            }
        }
    )
    return fig
