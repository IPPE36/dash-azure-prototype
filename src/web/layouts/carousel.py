from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from dash import html


@dataclass
class CarouselItem:
    key: str
    content: Any | None = None
    src: str | None = None
    header: str | None = None
    caption: str | None = None
    subcaption: str | None = None
    href: str | None = None
    img_class: str | None = None
    img_style: dict[str, Any] | None = None


class MediaCarousel:
    """
    Lightweight Bootstrap carousel wrapper that accepts arbitrary Dash content
    per slide (including html.Video), while keeping an API similar to dbc.Carousel.
    """

    def __init__(
        self,
        *,
        items: Iterable[dict[str, Any] | CarouselItem],
        id: str = "media-carousel",
        controls: bool = True,
        indicators: bool = True,
        interval: int | None = 5000,
        ride: str | None = "carousel",
        className: str | None = None,
        style: dict[str, Any] | None = None,
        dark: bool = False,
    ) -> None:
        self.items = [self._coerce_item(i) for i in items]
        self.id = id
        self.controls = controls
        self.indicators = indicators
        self.interval = interval
        self.ride = ride
        self.className = className
        self.style = style
        self.dark = dark

    def _coerce_item(self, item: dict[str, Any] | CarouselItem) -> CarouselItem:
        if isinstance(item, CarouselItem):
            return item
        allowed = {field.name for field in CarouselItem.__dataclass_fields__.values()}
        payload = {k: v for k, v in item.items() if k in allowed}
        return CarouselItem(**payload)

    def _build_slide(self, item: CarouselItem, active: bool) -> html.Div:
        classes = "carousel-item"
        if active:
            classes += " active"

        if item.content is not None:
            body = item.content
        else:
            body = html.Img(
                src=item.src,
                className=item.img_class or "d-block w-100",
                style=item.img_style,
            )

        caption = None
        if item.header or item.caption or item.subcaption:
            caption = html.Div(
                [
                    html.H5(item.header) if item.header else None,
                    html.P(item.caption) if item.caption else None,
                    html.P(item.subcaption, className="mb-0") if item.subcaption else None,
                ],
                className="carousel-caption d-block text-light fs-6 fs-md-5",
            )

        return html.Div([body, caption], className=classes)

    def _build_indicators(self) -> list[html.Button]:
        indicators: list[html.Button] = []
        for idx, item in enumerate(self.items):
            indicators.append(
                html.Button(
                    type="button",
                    **{
                        "data-bs-target": f"#{self.id}",
                        "data-bs-slide-to": str(idx),
                        "className": "active" if idx == 0 else None,
                        "aria-current": "true" if idx == 0 else None,
                        "aria-label": f"Slide {idx + 1}",
                    },
                )
            )
        return indicators

    def _build_controls(self) -> list[html.Button]:
        return [
            html.Button(
                [
                    html.Span(className="carousel-control-prev-icon", **{"aria-hidden": "true"}),
                    html.Span("Previous", className="visually-hidden"),
                ],
                className="carousel-control-prev",
                type="button",
                **{
                    "data-bs-target": f"#{self.id}",
                    "data-bs-slide": "prev",
                },
            ),
            html.Button(
                [
                    html.Span(className="carousel-control-next-icon", **{"aria-hidden": "true"}),
                    html.Span("Next", className="visually-hidden"),
                ],
                className="carousel-control-next",
                type="button",
                **{
                    "data-bs-target": f"#{self.id}",
                    "data-bs-slide": "next",
                },
            ),
        ]

    def render(self) -> html.Div:
        outer_classes = "carousel slide"
        if self.dark:
            outer_classes += " carousel-dark"
        if self.className:
            outer_classes = f"{outer_classes} {self.className}"

        data_attrs = {}
        if self.ride:
            data_attrs["data-bs-ride"] = self.ride
        if self.interval is not None:
            data_attrs["data-bs-interval"] = str(int(self.interval))

        slides = [self._build_slide(item, idx == 0) for idx, item in enumerate(self.items)]

        children = []
        if self.indicators:
            children.append(html.Div(self._build_indicators(), className="carousel-indicators"))
        children.append(html.Div(slides, className="carousel-inner"))
        if self.controls:
            children.extend(self._build_controls())

        return html.Div(
            children,
            id=self.id,
            className=outer_classes,
            style=self.style,
            **data_attrs,
        )

    def __call__(self) -> html.Div:
        return self.render()
