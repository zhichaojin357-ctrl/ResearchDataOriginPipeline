from __future__ import annotations

import hashlib
import json
import math
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


PMX_CHAIN_ENTRY = "TransformationChains/DefaultChain"
PMX_READER_NAME = "independent-agilent-pmx-reader"
PMX_READER_VERSION = "1.0.0"
_MAX_CHAIN_BYTES = 16 * 1024 * 1024


def read_agilent_pmx(path: str | Path) -> dict[str, Any]:
    """Read auditable processing settings from an Agilent OpenLab PMX package.

    PMX files are method/configuration packages.  This reader never executes or
    imports vendor assemblies; it only reads the package's XML representation.
    """
    pmx_path = Path(path).resolve()
    if not pmx_path.is_file():
        raise FileNotFoundError(f"Agilent PMX method not found: {pmx_path}")
    if pmx_path.suffix.casefold() != ".pmx":
        raise ValueError(f"expected an Agilent .pmx method: {pmx_path.name}")

    with zipfile.ZipFile(pmx_path) as archive:
        try:
            chain_info = archive.getinfo(PMX_CHAIN_ENTRY)
        except KeyError as exc:
            raise ValueError(
                f"{pmx_path.name} does not contain {PMX_CHAIN_ENTRY}"
            ) from exc
        if chain_info.file_size > _MAX_CHAIN_BYTES:
            raise ValueError(
                f"PMX transformation chain is unexpectedly large: "
                f"{chain_info.file_size} bytes"
            )
        chain_bytes = archive.read(chain_info)

    chain_text = _decode_chain(chain_bytes)
    try:
        root = ET.fromstring(chain_text)
    except ET.ParseError as exc:
        raise ValueError(f"invalid PMX transformation-chain XML: {pmx_path.name}") from exc

    transformations = []
    active_twelve_tone: list[dict[str, Any]] = []
    signal_alignment: dict[str, Any] = {}
    normalization: dict[str, Any] = {}
    for element in root.iter():
        if "TransformationId" not in element.attrib:
            continue
        transformation = _read_transformation(element)
        transformations.append(transformation["summary"])
        category = str(element.attrib.get("TransformationCategory") or "")
        enabled = _as_bool(element.attrib.get("IsEnabled"))
        tag_name = _local_name(element.tag)
        if (
            category == "Integration"
            and enabled
            and tag_name == "TwelveToneIntegratorTransformation64"
        ):
            active_twelve_tone.append(transformation)
        elif category == "SignalAlignment" and enabled:
            signal_alignment = _signal_alignment_settings(transformation)
        elif (
            enabled
            and category
            in {"CompoundIdentification", "Calibration", "Quantification"}
        ):
            expected = _parameter_value(
                transformation["parameter_sets"].get("ExpectedCompounds", {}),
                "ExpectedCompoundsIsNormalized",
            )
            if expected is not None:
                normalization[category] = _coerce_scalar(expected)

    if not active_twelve_tone:
        raise ValueError(
            f"{pmx_path.name} has no enabled 12-tone Integration transformation"
        )
    if len(active_twelve_tone) != 1:
        raise ValueError(
            f"{pmx_path.name} has multiple enabled 12-tone Integration transformations"
        )
    integration = _twelve_tone_settings(active_twelve_tone[0])
    source_sha256 = hashlib.sha256(pmx_path.read_bytes()).hexdigest().upper()
    return {
        "schema_version": "1.0",
        "reader": {
            "name": PMX_READER_NAME,
            "version": PMX_READER_VERSION,
            "vendor_code_executed": False,
        },
        "source": {
            "name": pmx_path.name,
            "size_bytes": pmx_path.stat().st_size,
            "sha256": source_sha256,
            "chain_entry": PMX_CHAIN_ENTRY,
        },
        "chain": {
            "name": root.attrib.get("Name", ""),
            "description": root.attrib.get("Description", ""),
            "version": root.attrib.get("Version", ""),
        },
        "transformations": transformations,
        "signal_alignment": signal_alignment,
        "integration": integration,
        "quantification_normalization": normalization,
    }


def pmx_integration_policy(method: dict[str, Any]) -> dict[str, Any]:
    """Convert a parsed PMX method to the candidate integrator policy."""
    integration = method["integration"]
    events: dict[str, Any] = {}
    event_rows: dict[str, dict[str, Any]] = {}
    for event in integration["initial_events"]:
        if not event["used"]:
            continue
        event_name = str(event["event"])
        if event_name in events:
            raise ValueError(
                f"PMX method contains duplicate enabled initial event: {event_name}"
            )
        events[event_name] = event["value"]
        event_rows[event_name] = event
    required = {
        "SlopeSensitivity": "slope_sensitivity",
        "PeakWidth": "initial_peak_width_min",
        "AreaReject": "area_reject_mau_s",
        "HeightReject": "height_reject_mau",
    }
    missing = [event for event in required if event not in events]
    if missing:
        raise ValueError(
            "PMX method is missing enabled initial integration events: "
            + ", ".join(missing)
        )
    _validate_integration_event_units(event_rows)
    settings = integration["settings"]
    policy = {
        target: float(events[source]) for source, target in required.items()
    }
    policy.update(
        {
            "area_percent_reject": float(events.get("AreaPercentReject", 0.0)),
            "shoulders_mode": str(events.get("ShouldersMode", "OFF")),
            "baseline_correction": str(settings.get("BaselineCorrection", "Standard")),
            "tangent_skim_mode": str(settings.get("TangentSkimMode", "Standard")),
            "front_skim_height_ratio": float(settings.get("FrontSkimHeightRatio", 0.0)),
            "tail_skim_height_ratio": float(settings.get("TailSkimHeightRatio", 0.0)),
            "skim_valley_ratio": float(settings.get("SkimValleyRatio", 0.0)),
            "peak_to_valley_ratio": float(settings.get("PeakToValleyRatio", 0.0)),
            "timed_events": integration["timed_events"],
            "signal_specific_events": integration["signal_specific_events"],
            "smoothing": method["signal_alignment"].get("smoothing", {}),
            "blank_subtraction": method["signal_alignment"].get(
                "blank_subtraction", {}
            ),
            "quantification_normalization": method[
                "quantification_normalization"
            ],
            "unit_assumptions": {
                "SlopeSensitivity": (
                    "PMX reports Unspecified; interpreted by the versioned "
                    "candidate recognition-filter normalization"
                ),
                "PeakWidth": "minutes, per ChemStation integration-event definition",
                "AreaReject": "mAU*s for a decoded mAU chromatogram",
                "HeightReject": "mAU for a decoded mAU chromatogram",
            },
            "method_source": {
                "kind": "pmx",
                **method["source"],
                "reader_name": method["reader"]["name"],
                "reader_version": method["reader"]["version"],
            },
        }
    )
    return policy


def _validate_integration_event_units(
    events: dict[str, dict[str, Any]],
) -> None:
    allowed = {
        "SlopeSensitivity": {"", "unspecified"},
        "PeakWidth": {"", "unspecified", "minutes", "min"},
        "AreaReject": {"", "unspecified"},
        "HeightReject": {"", "unspecified"},
    }
    for event_name, accepted in allowed.items():
        unit = str(events[event_name].get("value_units") or "").strip().casefold()
        if unit not in accepted:
            raise ValueError(
                f"unsupported PMX unit for {event_name}: "
                f"{events[event_name].get('value_units')}"
            )


def read_uniform_pmx_integration_policy(
    input_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read every PMX below a corpus and require one integration policy.

    This intentionally validates all method copies, rather than silently using
    whichever file happens to sort first.  Package hashes may differ while the
    effective integration policy remains identical.
    """
    root = Path(input_root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    paths = sorted(
        (path for path in root.rglob("*.pmx") if path.is_file()),
        key=lambda path: str(path.relative_to(root)).casefold(),
    )
    if not paths:
        raise FileNotFoundError(f"no Agilent PMX methods found below: {root}")

    packages: dict[str, dict[str, Any]] = {}
    policies: dict[str, dict[str, Any]] = {}
    pmx_result_sets: set[str] = set()
    for path in paths:
        method = read_agilent_pmx(path)
        policy = pmx_integration_policy(method)
        signature_policy = {
            key: value for key, value in policy.items() if key != "method_source"
        }
        signature = hashlib.sha256(
            json.dumps(
                signature_policy,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest().upper()
        policies.setdefault(signature, signature_policy)
        package_sha = str(method["source"]["sha256"])
        package = packages.setdefault(
            package_sha,
            {
                "sha256": package_sha,
                "file_count": 0,
                "names": set(),
                "policy_signatures": set(),
            },
        )
        package["file_count"] += 1
        package["names"].add(path.name)
        package["policy_signatures"].add(signature)
        result_set = _containing_result_set(path, root)
        if result_set is not None:
            pmx_result_sets.add(result_set)

    if len(policies) != 1:
        raise ValueError(
            "PMX corpus contains multiple effective integration policies: "
            + ", ".join(sorted(policies))
        )
    selected_signature, selected_policy = next(iter(policies.items()))
    package_groups = []
    for package in sorted(packages.values(), key=lambda item: item["sha256"]):
        package_groups.append(
            {
                "sha256": package["sha256"],
                "file_count": package["file_count"],
                "names": sorted(package["names"]),
                "policy_signatures": sorted(package["policy_signatures"]),
            }
        )
    audit = {
        "pmx_file_count": len(paths),
        "unique_package_count": len(packages),
        "unique_integration_policy_count": len(policies),
        "selected_policy_signature_sha256": selected_signature,
        "package_groups": package_groups,
        "pmx_result_set_count": len(pmx_result_sets),
        "pmx_result_set_relatives": sorted(pmx_result_sets),
        "all_pmx_files_parsed": True,
    }
    selected = dict(selected_policy)
    selected["method_source"] = {
        "kind": "pmx_corpus",
        "pmx_file_count": len(paths),
        "unique_package_sha256": sorted(packages),
        "integration_policy_signature_sha256": selected_signature,
        "reader_name": PMX_READER_NAME,
        "reader_version": PMX_READER_VERSION,
    }
    return selected, audit


def _containing_result_set(path: Path, root: Path) -> str | None:
    for parent in path.parents:
        if parent.suffix.casefold() == ".rslt":
            return parent.relative_to(root).as_posix()
        if parent == root:
            break
    return None


def _decode_chain(raw: bytes) -> str:
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("PMX transformation chain is not valid UTF-16 or UTF-8")


def _read_transformation(element: ET.Element) -> dict[str, Any]:
    parameter_sets: dict[str, dict[str, Any]] = {}
    for descendant in element.iter():
        serialized = descendant.attrib.get("SerializedPsetRepresentation")
        if not serialized:
            continue
        try:
            nested = ET.fromstring(serialized)
        except ET.ParseError as exc:
            raise ValueError(
                "invalid SerializedPsetRepresentation in PMX transformation "
                f"{element.attrib.get('DisplayName', _local_name(element.tag))}"
            ) from exc
        for parameter_set in _direct_children(nested, "ParameterSet"):
            key = str(parameter_set.attrib.get("usagekey") or "")
            parameter_sets[key] = _read_parameter_set(parameter_set)
    return {
        "summary": {
            "type": _local_name(element.tag),
            "display_name": element.attrib.get("DisplayName", ""),
            "category": element.attrib.get("TransformationCategory", ""),
            "enabled": _as_bool(element.attrib.get("IsEnabled")),
            "processing_level": element.attrib.get("ProcessingLevel", ""),
            "transformation_id": element.attrib.get("TransformationId", ""),
            "parameter_set_keys": sorted(parameter_sets),
        },
        "parameter_sets": parameter_sets,
    }


def _read_parameter_set(parameter_set: ET.Element) -> dict[str, Any]:
    parameters_node = _first_direct(parameter_set, "Parameters")
    parameters: dict[str, Any] = {}
    if parameters_node is not None:
        for parameter in _direct_children(parameters_node, "Parameter"):
            parameter_id = str(parameter.attrib.get("id") or "")
            value_node = _first_direct(parameter, "Value")
            parameters[parameter_id] = {
                "value": _value_text(value_node),
                "xml": value_node,
            }
    return {
        "usage_key": parameter_set.attrib.get("usagekey", ""),
        "display_name": parameter_set.attrib.get("displayName", ""),
        "class": parameter_set.attrib.get("class", ""),
        "parameters": parameters,
    }


def _twelve_tone_settings(transformation: dict[str, Any]) -> dict[str, Any]:
    parameter_set = transformation["parameter_sets"].get("12ToneIntegratorSettings")
    if parameter_set is None:
        raise ValueError("enabled 12-tone transformation has no settings parameter set")
    parameters = parameter_set["parameters"]
    simple_keys = (
        "TangentSkimMode",
        "BaselineCorrection",
        "FrontSkimHeightRatio",
        "TailSkimHeightRatio",
        "SkimValleyRatio",
        "PeakToValleyRatio",
    )
    settings = {
        key: _coerce_scalar(parameters[key]["value"])
        for key in simple_keys
        if key in parameters
    }
    initial_events = _read_events(parameters.get("InitialEventsTable", {}).get("xml"))
    timed_events = _read_events(parameters.get("TimedEventsTable", {}).get("xml"))
    group_xml = parameters.get("GroupParameter", {}).get("xml")
    signal_specific_events = _read_signal_specific_events(group_xml)
    return {
        "engine": transformation["summary"]["display_name"],
        "engine_type": transformation["summary"]["type"],
        "transformation_id": transformation["summary"]["transformation_id"],
        "settings": settings,
        "initial_events": initial_events,
        "timed_events": timed_events,
        "signal_specific_events": signal_specific_events,
    }


def _read_events(value_node: ET.Element | None) -> list[dict[str, Any]]:
    if value_node is None:
        return []
    events: list[dict[str, Any]] = []
    for parameter_set in _direct_children(value_node, "ParameterSet"):
        parameters = _first_direct(parameter_set, "Parameters")
        if parameters is None:
            continue
        event_parameter = next(
            (
                item
                for item in _direct_children(parameters, "Parameter")
                if item.attrib.get("id") == "IntegrationEvent"
            ),
            None,
        )
        if event_parameter is None:
            continue
        event_value = _first_direct(event_parameter, "Value")
        if event_value is None:
            continue
        value_container = _first_direct(event_value, "IntegrationEventValue")
        inner_parameter = (
            _first_direct(value_container, "Parameter")
            if value_container is not None
            else None
        )
        scalar_node = (
            _first_direct(inner_parameter, "Value")
            if inner_parameter is not None
            else None
        )
        time_parameter = next(
            (
                item
                for item in _direct_children(parameters, "Parameter")
                if item.attrib.get("id") == "Time"
            ),
            None,
        )
        time_value = _value_text(_first_direct(time_parameter, "Value"))
        units = _value_text(_first_direct(inner_parameter, "XUnits"))
        event_name = _value_text(_first_direct(event_value, "IntegrationEvent"))
        events.append(
            {
                "event": event_name,
                "value": _coerce_scalar(_value_text(scalar_node)),
                "used": bool(
                    _as_bool(_value_text(_first_direct(event_value, "IsUsed")))
                ),
                "timed": bool(
                    _as_bool(
                        _value_text(_first_direct(event_value, "IsTimedEvent"))
                    )
                ),
                "time_min": (
                    float(time_value)
                    if _is_finite_number(time_value)
                    else None
                ),
                "value_units": units,
            }
        )
    return events


def _read_signal_specific_events(value_node: ET.Element | None) -> list[dict[str, Any]]:
    if value_node is None:
        return []
    groups: list[dict[str, Any]] = []
    for parameter_set in value_node.iter():
        if _local_name(parameter_set.tag) != "ParameterSet":
            continue
        events = []
        for parameter in parameter_set.iter():
            if parameter.attrib.get("id") not in {"InitialEventsTable", "TimedEventsTable"}:
                continue
            events.extend(_read_events(_first_direct(parameter, "Value")))
        if events:
            groups.append(
                {
                    "usage_key": parameter_set.attrib.get("usagekey", ""),
                    "display_name": parameter_set.attrib.get("displayName", ""),
                    "events": events,
                }
            )
    return groups


def _signal_alignment_settings(transformation: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    smoothing = transformation["parameter_sets"].get("SignalSmoothingPSet")
    if smoothing:
        result["smoothing"] = {
            key: _coerce_scalar(_parameter_value(smoothing, key))
            for key in ("SmoothingAlgorithm", "NumberOfPoints", "NumberOfPasses")
        }
    blank = transformation["parameter_sets"].get("BlankSubtractionPSet")
    if blank:
        result["blank_subtraction"] = {
            key: _coerce_scalar(_parameter_value(blank, key))
            for key in (
                "BlankSubtractionTarget",
                "UsedBlank",
                "BlankExternalReferencePath",
                "BlankExternalReference",
                "UseBlankIfDifferentRate",
                "SignalMatchingMode",
                "ExtractedChromatogramSupported",
            )
        }
    return result


def _parameter_value(parameter_set: dict[str, Any], key: str) -> str | None:
    parameter = parameter_set.get("parameters", {}).get(key)
    return None if parameter is None else parameter.get("value")


def _direct_children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _first_direct(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    return next(iter(_direct_children(element, name)), None)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _value_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return str(element.text or "").strip()


def _as_bool(value: Any) -> bool | None:
    normalized = str(value or "").strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _coerce_scalar(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    boolean = _as_bool(text)
    if boolean is not None:
        return boolean
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if math.isfinite(number) and number.is_integer() and not any(
        marker in text.casefold() for marker in (".", "e")
    ):
        return int(number)
    return number
