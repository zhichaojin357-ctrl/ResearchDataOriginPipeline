from __future__ import annotations

import math
from typing import Any

from src.origin.operations import quote_labtalk, update_native_legend


def apply_xrd_standard_card_annotations(
    operations: object,
    graph_name: str,
    annotation_contract: object,
) -> dict[str, object]:
    """Restore the native top-series legend and current reference-card caption."""

    contract = annotation_contract if isinstance(annotation_contract, dict) else {}
    if not contract:
        return {"applied": False, "reason": "annotation_contract_missing"}
    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "origin_app_unavailable"}

    hidden_layers: list[int] = []
    for value in list(contract.get("hide_layer_legends") or []):
        layer_index = _positive_int(value)
        if layer_index is None:
            continue
        hidden = _hide_layer_legend(operations, graph_name, layer_index)
        if not hidden:
            return {
                "applied": False,
                "reason": "layer_legend_hide_failed",
                "layer_index": layer_index,
            }
        hidden_layers.append(layer_index)

    top_series = contract.get("top_series")
    if not isinstance(top_series, dict):
        return {"applied": False, "reason": "top_series_contract_missing"}
    top_layer_index = _positive_int(top_series.get("layer_index"))
    line_contract = top_series.get("line")
    top_text_contract = top_series.get("text")
    if top_layer_index is None or not isinstance(line_contract, dict) or not isinstance(top_text_contract, dict):
        return {"applied": False, "reason": "top_series_contract_invalid"}
    # The reviewed XRD binding places the top sample in Layer3, plot1.
    # Its former free line/text pair is replaced by Origin's linked legend.
    top_legend = update_native_legend(
        operations, graph_name, [str(top_text_contract.get("rich_text") or "")],
        plot_indices=[1], layer_index=3,
    )
    if not top_legend.ok:
        return {"applied": False, "reason": "top_series_native_legend_failed"}
    legend = _graph_object(_graph_layer(operations, graph_name, 3), "Legend")
    main_legend = _graph_object(_graph_layer(operations, graph_name, 1), "Legend")
    try:
        for prop, value in (("font", top_text_contract["font"]),
                            ("fsize", top_text_contract["font_size"]),
                            ("color", top_text_contract["color"]),
                            ("background", 0), ("border", 0), ("frame", 0)):
            legend.SetNumProp(prop, value)
        legend.Left = main_legend.Left
        legend.Top = _finite_number(top_text_contract["top"])
        legend.Show = 1
    except Exception:
        return {"applied": False, "reason": "top_series_native_legend_style_failed"}
    for old_name in (line_contract.get("name"), top_text_contract.get("name"), "Line", "Text"):
        name = _safe_object_name(old_name)
        if name:
            operations.run_labtalk(
                f'win -a "{quote_labtalk(graph_name)}"; layer -s {top_layer_index}; label -r {name};'
            )

    reference_card = contract.get("reference_card")
    if not isinstance(reference_card, dict):
        return {"applied": False, "reason": "reference_card_contract_missing"}
    card_layer_index = _positive_int(reference_card.get("layer_index"))
    card_text_contract = reference_card.get("text")
    if card_layer_index is None or not isinstance(card_text_contract, dict):
        return {"applied": False, "reason": "reference_card_contract_invalid"}
    card_text = _create_reviewed_text(
        operations,
        graph_name,
        card_layer_index,
        card_text_contract,
    )

    refreshed = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; layer -s 1; doc -uw;'
    )
    # Immediate repaint is useful on some Origin versions but is not a
    # correctness gate; the saved/reopened export below is authoritative.
    operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; draw -uwi;'
    )
    applied = bool(top_legend.ok and card_text and getattr(refreshed, "ok", False))
    return {
        "applied": applied,
        "method": "native_legend_and_reference_card_caption",
        "hidden_layer_legends": [index for index in hidden_layers if index != 3],
        "top_series_native_legend": top_legend.payload,
        "reference_card_text": card_text,
        "refresh_ok": bool(getattr(refreshed, "ok", False)),
    }


def _hide_layer_legend(operations: object, graph_name: str, layer_index: int) -> bool:
    graph = quote_labtalk(graph_name)
    result = operations.run_labtalk(
        f'win -a "{graph}"; layer -s {int(layer_index)}; legend.show=0;'
    )
    layer = _graph_layer(operations, graph_name, layer_index)
    if layer is None:
        return False
    legend = _graph_object(layer, "Legend")
    # A correctly harvested overlay layer may not contain a legend object at
    # all.  In that state there is nothing to hide, and LabTalk legitimately
    # reports failure for ``legend.show`` because the object is absent.
    if legend is None:
        return True
    try:
        legend.Show = 0
    except Exception:
        pass
    try:
        legend.SetNumProp("show", 0)
    except Exception:
        pass
    read = getattr(operations, "get_labtalk_variable", None)
    if read is None:
        return bool(getattr(result, "ok", False))
    try:
        value = float(read("legend.show").payload.get("value"))
    except (AttributeError, TypeError, ValueError):
        return bool(getattr(result, "ok", False))
    return bool(getattr(result, "ok", False)) and value == 0.0


def _create_reviewed_text(
    operations: object,
    graph_name: str,
    layer_index: int,
    contract: dict[str, object],
) -> bool:
    name = _safe_object_name(contract.get("name"))
    rich_text = str(contract.get("rich_text") or "").strip()
    if not name or not rich_text:
        return False
    graph = quote_labtalk(graph_name)
    created = operations.run_labtalk(
        f'win -a "{graph}"; layer -s {int(layer_index)}; '
        f'label -r {name}; label -n {name} "x";'
    )
    if not getattr(created, "ok", False):
        return False
    layer = _graph_layer(operations, graph_name, layer_index)
    graph_object = _graph_object(layer, name)
    if graph_object is None:
        return False
    try:
        graph_object.Text = rich_text
        graph_object.Left = _finite_number(contract.get("left"))
        graph_object.Top = _finite_number(contract.get("top"))
        graph_object.Width = _finite_number(contract.get("width"))
        graph_object.Height = _finite_number(contract.get("height"))
        graph_object.Show = 1
    except Exception:
        return False
    for prop, value in (
        ("font", _finite_number(contract.get("font"))),
        ("fsize", _finite_number(contract.get("font_size"))),
        ("bold", 0),
        ("italic", 0),
        ("color", _finite_number(contract.get("color"))),
        ("background", 0),
        ("border", 0),
        ("frame", 0),
        ("fill", 0),
        ("show", 1),
    ):
        try:
            graph_object.SetNumProp(prop, value)
        except Exception:
            pass
    font = _finite_number(contract.get("font"))
    font_size = _finite_number(contract.get("font_size"))
    color = _finite_number(contract.get("color"))
    operations.run_labtalk(
        f'win -a "{graph}"; layer -s {int(layer_index)}; '
        f"{name}.attach=0; {name}.font={font:g}; {name}.fsize={font_size:g}; "
        f"{name}.bold=0; {name}.color={color:g}; {name}.show=1;"
    )
    # Styling can let Origin recompute the text bounds.  Restore the reviewed
    # physical placement last so the native export is deterministic.
    try:
        graph_object.Left = _finite_number(contract.get("left"))
        graph_object.Top = _finite_number(contract.get("top"))
        # Origin derives text width/height from its font metrics.  Reapplying
        # the reviewed font and point size above should reproduce those
        # dimensions; forcing stale bounds can cause Origin to rescale text.
    except Exception:
        return False
    return str(getattr(graph_object, "Text", "") or "") == rich_text


def _graph_layer(operations: object, graph_name: str, layer_index: int) -> Any:
    getter = getattr(operations, "_graph_layer", None)
    if getter is not None:
        try:
            return getter(graph_name, layer_index)
        except Exception:
            pass
    app = getattr(operations, "app", None)
    if app is None:
        return None
    for reference in (f"[{graph_name}]{layer_index}", f"[{graph_name}]Layer{layer_index}"):
        try:
            layer = app.FindGraphLayer(reference)
        except Exception:
            layer = None
        if layer:
            return layer
    return None


def _graph_object(layer: object, name: str) -> Any:
    collection = getattr(layer, "GraphObjects", None)
    if collection is None:
        return None
    try:
        return collection[name]
    except Exception:
        pass
    try:
        return collection.Item(name)
    except Exception:
        return None


def _safe_object_name(value: object) -> str:
    text = str(value or "").strip()
    if not text or not (text[0].isalpha() or text[0] == "_"):
        return ""
    return text if all(character.isalnum() or character == "_" for character in text) else ""


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 24 else None


def _finite_number(value: object) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Origin object contract requires finite numbers")
    return number
