"""Carbon-inspired shared primitives (angular surfaces, 16px grid)."""

from __future__ import annotations

import reflex as rx


def panel(*children, **props) -> rx.Component:
    class_name = props.pop(
        "class_name",
        "",
    )
    return rx.el.section(
        *children,
        class_name=f"border border-[#e0e0e0] bg-white rounded-[2px] {class_name}",
        **props,
    )


def panel_header(
    title: str, caption: str = "", icon: str = "circle"
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon(icon, class_name="h-4 w-4 text-[#0f62fe]"),
            rx.el.h2(
                title,
                class_name="font-['IBM_Plex_Sans_Condensed'] text-[16px] font-semibold uppercase tracking-wide text-[#161616]",
            ),
            class_name="flex items-center gap-2",
        ),
        rx.cond(
            caption != "",
            rx.el.p(
                caption, class_name="text-[12px] font-medium text-[#6f6f6f]"
            ),
        ),
        class_name="flex flex-wrap items-center justify-between gap-2 border-b border-[#e0e0e0] px-4 py-3",
    )


def dot(color: rx.Var | str, size: str = "h-2.5 w-2.5") -> rx.Component:
    return rx.el.span(
        style={"backgroundColor": color},
        class_name=f"{size} shrink-0 rounded-[1px]",
    )


def status_pill(label: rx.Var | str, color: rx.Var | str) -> rx.Component:
    return rx.el.span(
        dot(color, "h-2 w-2"),
        rx.el.span(
            label,
            class_name="text-[11px] font-semibold uppercase tracking-wide",
        ),
        class_name="flex w-fit items-center gap-2 rounded-[2px] border border-[#e0e0e0] bg-[#f4f4f4] px-2 py-1 text-[#161616]",
    )


def source_tag(source: rx.Var | str) -> rx.Component:
    return rx.el.span(
        source,
        class_name="w-fit rounded-[2px] border border-[#c6c6c6] bg-white px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-[#6f6f6f]",
    )


def meter(share: rx.Var, color: rx.Var | str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            style={"width": f"{share}%", "backgroundColor": color},
            class_name="h-2 rounded-[1px]",
        ),
        class_name="h-2 w-full min-w-[80px] bg-[#e0e0e0] rounded-[1px]",
    )


def field_label(text: str) -> rx.Component:
    return rx.el.label(
        text,
        class_name="mb-1 block text-[12px] font-semibold uppercase tracking-wide text-[#525252]",
    )


def select_box(
    options: rx.Var | list[str],
    value: rx.Var | str,
    on_change,
    label: str = "",
) -> rx.Component:
    return rx.el.div(
        rx.cond(label != "", field_label(label)),
        rx.el.div(
            rx.el.select(
                rx.foreach(options, lambda opt: rx.el.option(opt, value=opt)),
                value=value,
                on_change=on_change,
                class_name="h-10 w-full appearance-none border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] px-3 pr-9 text-[14px] font-medium text-[#161616] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe] focus:ring-offset-0",
            ),
            rx.icon(
                "chevron-down",
                class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-[#525252]",
            ),
            class_name="relative w-full",
        ),
        class_name="w-full",
    )


def primary_button(
    label: str, on_click, icon: str = "check", disabled=False
) -> rx.Component:
    return rx.el.button(
        rx.icon(icon, class_name="h-4 w-4"),
        rx.el.span(label),
        on_click=on_click,
        disabled=disabled,
        class_name="flex h-10 w-fit items-center gap-2 rounded-[2px] bg-[#0f62fe] px-4 text-[14px] font-semibold text-white transition-colors hover:bg-[#0353e9] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#c6c6c6]",
    )


def ghost_button(label: str, on_click, icon: str = "x") -> rx.Component:
    return rx.el.button(
        rx.icon(icon, class_name="h-4 w-4"),
        rx.el.span(label),
        on_click=on_click,
        class_name="flex h-10 w-fit items-center gap-2 rounded-[2px] border border-[#8d8d8d] bg-white px-4 text-[14px] font-semibold text-[#161616] transition-colors hover:bg-[#e8e8e8] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe] focus:ring-offset-2",
    )


def notification(kind: str, message: rx.Var | str) -> rx.Component:
    colors = {
        "success": ("#24a148", "#defbe6", "circle-check"),
        "error": ("#da1e28", "#fff1f1", "circle-alert"),
        "info": ("#0f62fe", "#edf5ff", "info"),
    }
    accent, bg, icon = colors.get(kind, colors["info"])
    return rx.el.div(
        rx.icon(icon, class_name="h-4 w-4 shrink-0", style={"color": accent}),
        rx.el.p(message, class_name="text-[13px] font-medium text-[#161616]"),
        style={"backgroundColor": bg, "borderLeftColor": accent},
        class_name="flex items-start gap-3 rounded-[2px] border border-[#e0e0e0] border-l-[3px] px-4 py-3",
    )


def empty_state(message: str, icon: str = "inbox") -> rx.Component:
    return rx.el.div(
        rx.icon(icon, class_name="h-6 w-6 text-[#8d8d8d]"),
        rx.el.p(message, class_name="text-[13px] font-medium text-[#6f6f6f]"),
        class_name="flex flex-col items-center justify-center gap-2 px-4 py-12 text-center",
    )


def skeleton_rows(count: int = 4) -> rx.Component:
    return rx.el.div(
        *[
            rx.el.div(
                class_name="h-8 w-full animate-pulse rounded-[2px] bg-[#e8e8e8]"
            )
            for _ in range(count)
        ],
        class_name="flex flex-col gap-2 p-4",
    )


def th(label: str, icon: str = "") -> rx.Component:
    return rx.el.th(
        rx.el.div(
            rx.cond(
                icon != "",
                rx.icon(icon, class_name="h-3.5 w-3.5 text-[#6f6f6f]"),
            ),
            rx.el.span(label),
            class_name="flex items-center gap-1.5",
        ),
        class_name="whitespace-nowrap border-b border-[#e0e0e0] bg-[#f4f4f4] px-4 py-2 text-left text-[12px] font-semibold uppercase tracking-wide text-[#525252]",
    )


def td(*children, **props) -> rx.Component:
    class_name = props.pop("class_name", "")
    return rx.el.td(
        *children,
        class_name=f"whitespace-nowrap border-b border-[#f4f4f4] px-4 py-2 text-[13px] font-medium text-[#161616] {class_name}",
        **props,
    )
