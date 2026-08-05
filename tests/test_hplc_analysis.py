from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

import src.core.hplc_analysis as analysis


@pytest.fixture
def config() -> dict:
    return analysis.load_hplc_analysis_config(Path(__file__).resolve().parents[1])


def _repeat_record(
    injection_id: str,
    sample_name: str,
    *,
    acquired: str = "2026-07-18T10:00:00+08:00",
    sequence_name: str = "sequence-A",
    result_name: str = "result-A",
    result_set_id: str = "result-set-A",
    batch_marker: str = "batch-2",
    batch_folder: str = "20260718 Batch 2 condition-A",
    sequence_order: int = 1,
) -> dict:
    return {
        "injection_id": injection_id,
        "sample_name": sample_name,
        "normalized_sample_name": analysis.normalize_hplc_name(
            sample_name, strip_rerun_suffix=False
        ),
        "sample_identity_base": analysis.normalize_hplc_name(sample_name),
        "sample_has_explicit_rerun_word": False,
        "acquisition_local": acquired,
        "acquisition_date": date.fromisoformat(acquired[:10]),
        "sequence_name": sequence_name,
        "normalized_sequence_name": analysis.normalize_hplc_name(sequence_name),
        "result_name": result_name,
        "normalized_result_name": analysis.normalize_hplc_name(result_name),
        "result_set_id": result_set_id,
        "batch_marker": batch_marker,
        "repeat_condition_key": analysis._repeat_condition_key(sample_name),
        "folder_condition_key": analysis._folder_condition_key(batch_folder),
        "sequence_condition_key": analysis._sequence_condition_key(
            sequence_name, result_name
        ),
        "batch_condition_key": analysis._batch_condition_key(
            batch_folder, sequence_name, result_name
        ),
        "sequence_order": sequence_order,
        "is_wash": False,
        "is_before_screening": False,
    }


def _analysis_dataset(*injections: dict, include_vendor_peaks: bool = True) -> dict:
    columns = [
        {
            "injection_id": item["injection_id"],
            "time": [index / 100.0 for index in range(3000)],
            "signal": [0.0] * 3000,
        }
        for item in injections
    ]
    peaks = []
    if include_vendor_peaks:
        for injection in injections:
            for ordinal, (retention_time, area) in enumerate(
                ((5.50, 100.0), (7.34, 100.0), (16.52, 100.0)), start=1
            ):
                peaks.append(
                    {
                        "injection_id": injection["injection_id"],
                        "peak_ordinal": ordinal,
                        "retention_time_min": retention_time,
                        "area": area,
                        "begin_time_min": retention_time - 0.1,
                        "end_time_min": retention_time + 0.1,
                        "height": 10.0,
                        "baseline_start": 0.0,
                        "baseline_end": 0.0,
                        "baseline_model": "Linear",
                    }
                )
    return {
        "injections": list(injections),
        "raw_sheets": [{"columns": columns}],
        "peaks": peaks,
    }


def _injection(
    injection_id: str,
    sample_name: str,
    *,
    folder: str = "20260718 Batch 2 condition-A",
    acquired: str = "2026-07-18T10:00:00+08:00",
    sequence_order: int = 1,
    **overrides: object,
) -> dict:
    return {
        "injection_id": injection_id,
        "sample_name": sample_name,
        "batch_folder": folder,
        "acquisition_local": acquired,
        "sequence_name": "sequence-A",
        "result_name": "result-A",
        "result_set_id": "result-set-A",
        "sequence_order": sequence_order,
        "raw_file": f"{injection_id}.dx",
        "decode_status": "OK",
        "time_monotonic": True,
        "signal_finite": True,
        **overrides,
    }


def test_real_sample_suffix_two_is_not_auto_merged_as_a_rerun(config: dict):
    first = _repeat_record("one", "Catalyst", sequence_order=1)
    second = _repeat_record("two", "Catalyst-2", sequence_order=2)

    group_by_injection, _, edges, _ = analysis._assign_repeat_groups([first, second], config)

    assert group_by_injection == {}
    assert edges == []


def test_sequence_and_result_rerun_suffixes_are_positive_rerun_evidence(config: dict):
    first = _repeat_record("one", "Catalyst 1H", sequence_name="sequence-A", result_name="result-A")
    second = _repeat_record(
        "two",
        "Catalyst 1H",
        sequence_name="sequence-A-2",
        result_name="result-A-2",
        sequence_order=2,
    )

    group_by_injection, evidence_by_group, edges, _ = analysis._assign_repeat_groups(
        [first, second], config
    )

    assert group_by_injection == {"one": "RG001", "two": "RG001"}
    assert len(edges) == 1
    assert evidence_by_group["RG001"]
    assert analysis.normalize_hplc_name(second["sequence_name"]) == "SEQUENCE-A"
    assert analysis.normalize_hplc_name(second["result_name"]) == "RESULT-A"


def test_second_and_third_batches_are_hard_boundaries_and_conflicts_are_flagged(config: dict):
    second, second_conflict, second_values = analysis.detect_batch_marker("Batch 2")
    third, third_conflict, third_values = analysis.detect_batch_marker("Batch 3")
    _, conflict, conflict_values = analysis.detect_batch_marker("Batch 2", "Batch 3")
    left = _repeat_record("two", "Catalyst 1H", batch_marker=second)
    right = _repeat_record("three", "Catalyst 1H", batch_marker=third)

    assert second_conflict is False and second_values
    assert third_conflict is False and third_values
    assert second != third
    assert conflict is True
    assert len(conflict_values) == 2
    assert analysis._repeat_hard_boundary_compatible(left, right, maximum_days=1) is False


def test_adjacent_days_with_different_conditions_cannot_merge(config: dict):
    first = _repeat_record("one", "Catalyst A 1H", acquired="2026-07-18T10:00:00+08:00")
    second = _repeat_record(
        "two",
        "Catalyst B 1H",
        acquired="2026-07-19T10:00:00+08:00",
        sequence_name="sequence-A-2",
        result_name="result-A-2",
        result_set_id="result-set-B",
        sequence_order=2,
    )

    group_by_injection, _, edges, _ = analysis._assign_repeat_groups([first, second], config)

    assert group_by_injection == {}
    assert edges == []


def test_july_17_is_light_screening_only_for_explicit_screening_folder(config: dict):
    screening_date = date(2026, 7, 17)
    screening_folder = "20260717 \u5149\u6e90\u7b5b\u9009"
    ordinary_folder = "20260717 \u5e38\u89c4\u53cd\u5e94"

    assert (
        analysis.classify_light_source(screening_date, config, folder_name=screening_folder)
        == config["date_rules"]["screening_label"]
    )
    assert (
        analysis.classify_light_source(screening_date, config, folder_name=ordinary_folder)
        != config["date_rules"]["screening_label"]
    )
    assert (
        analysis.classify_light_source(date(2026, 7, 18), config, folder_name="20260718 \u5e38\u89c4")
        == config["date_rules"]["ordinary_306_label"]
    )


def test_wash_injection_is_excluded_from_main_analysis(config: dict):
    wash = _injection("wash", "\u51b2\u67f1\u5b50")

    result = analysis.analyze_hplc_openlab_dataset({"injections": [wash]}, config)

    assert result["summary"]["wash_excluded_count"] == 1
    assert result["sample_results"] == []
    assert result["excluded_data"][0]["injection_id"] == "wash"


def test_english_pre_reaction_alias_and_plain_zero_hour_are_c0_candidates(config: dict):
    assert analysis.is_pre_reaction_sample("SM reaction before", config) is True
    assert analysis.extract_reaction_time_h("ordinary-condition 0H") == 0.0


def test_c0_never_crosses_different_condition_keys(config: dict):
    pre_reaction = _injection("c0", "SM", sequence_order=1)
    condition_a = _injection("a", "Catalyst A 1H", sequence_order=2)
    condition_b = _injection(
        "b",
        "Catalyst B 1H",
        folder="20260718 Batch 2 condition-B",
        acquired="2026-07-18T10:02:00+08:00",
        sequence_order=3,
    )

    result = analysis.analyze_hplc_openlab_dataset(
        _analysis_dataset(pre_reaction, condition_a, condition_b), config
    )
    rows = {row["sample_name"]: row for row in result["sample_results"]}

    assert rows["SM"]["c0_mM"] is not None
    assert rows["Catalyst A 1H"]["c0_mM"] == rows["SM"]["c0_mM"]
    assert rows["Catalyst B 1H"]["c0_mM"] is None


def test_target_peak_matching_selects_nearest_peak_and_preserves_ordinals(config: dict):
    matched = analysis.match_target_peaks(
        [
            {"peak_ordinal": 8, "retention_time_min": 5.48, "area": 20.0},
            {"peak_ordinal": 3, "retention_time_min": 5.52, "area": 10.0},
            {"peak_ordinal": 12, "retention_time_min": 16.52, "area": 30.0},
        ],
        config,
        missing_can_be_zero=True,
    )

    sulfoxide = matched["sulfoxide"]
    assert sulfoxide["area"] == 10.0
    assert sulfoxide["candidate_count"] == 2
    assert sulfoxide["candidate_peak_ordinals"] == [3, 8]
    assert sulfoxide["candidate_retention_times_min"] == [5.52, 5.48]
    assert sulfoxide["selected_peak_ordinal"] == 3
    assert matched["thioanisole"]["candidate_peak_ordinals"] == [12]
    assert matched["sulfone"]["area"] == 0.0


def test_manual_repeat_override_cannot_cross_batch_or_condition_boundary(config: dict):
    configured = deepcopy(config)
    configured["manual_overrides"]["repeat_group_by_injection"] = {
        "batch-two": "forced",
        "batch-three": "forced",
    }
    second = _repeat_record("batch-two", "Catalyst 1H", batch_marker="batch-2")
    third = _repeat_record("batch-three", "Catalyst 1H", batch_marker="batch-3")

    with pytest.raises(ValueError, match="crosses a hard batch/condition/date boundary"):
        analysis._assign_repeat_groups([second, third], configured)


def test_missing_vendor_result_never_falls_back_to_project_integration(config: dict):
    injection = _injection(
        "unprocessed",
        "Catalyst 1H",
        openlab_processing_state="NoMethodProvided",
        acquisition_method="",
        processing_method="",
    )

    result = analysis.analyze_hplc_openlab_dataset(
        _analysis_dataset(injection, include_vendor_peaks=False), config
    )

    assert result["summary"]["openlab_no_method_injection_count"] == 1
    assert result["summary"]["vendor_result_unavailable_injection_count"] == 1
    assert result["injection_analysis"][0]["primary_peak_source"] == "vendor_unavailable"
    assert result["sample_results"][0]["targets"]["sulfoxide"]["area"] is None
    assert result["sample_results"][0]["used_injection_ids"] == []
    assert "native_peaks" not in result
    assert "native_rejected_candidates" not in result
    assert any(
        item["issue_type"] == "原厂积分结果缺失" for item in result["manual_review"]
    )


def test_successful_vendor_result_is_the_only_peak_source(config: dict):
    injection = _injection("vendor", "Catalyst 1H")
    with_vendor = _analysis_dataset(injection)
    with_vendor["peaks"] = [
        {
            "injection_id": "vendor",
            "peak_ordinal": ordinal,
            "retention_time_min": retention_time,
            "area": 1.0,
        }
        for ordinal, retention_time in enumerate((5.50, 7.34, 16.52), start=1)
    ]

    compared = analysis.analyze_hplc_openlab_dataset(with_vendor, config)

    assert compared["injection_analysis"][0]["quality"] == "正常"
    assert compared["sample_results"][0]["used_injection_ids"] == ["vendor"]
    selected = compared["injection_analysis"][0]["targets"]["sulfoxide"]
    assert selected["peak_source"] == "vendor_rx"
    assert selected["area"] == 1.0
    assert compared["sample_results"][0]["targets"]["sulfoxide"]["area"] == 1.0
    assert compared["summary"]["vendor_primary_injection_count"] == 1
    assert len(compared["peak_details"]) == len(compared["sample_results"]) == 1
    assert compared["peak_detail_columns"][3:6] == [
        "茴香亚砜峰序号",
        "茴香亚砜出峰时间(min)",
        "茴香亚砜峰面积",
    ]
    assert compared["peak_details"][0]["sulfoxide_peak_ordinal"] == 1
    assert compared["peak_details"][0]["sulfoxide_retention_time_min"] == 5.5
    assert compared["peak_details"][0]["sulfoxide_area"] == 1.0


def test_vendor_reprocessed_result_is_not_mislabeled_as_stored_rx():
    selected = analysis._select_vendor_target(
        {"retention_time_min": 5.5, "area": 99.0},
        vendor_available=True,
        vendor_result_origin="agilent_processing_server_reprocessed_rx",
    )

    assert selected["peak_source"] == "vendor_rx"
    assert selected["vendor_result_origin"] == "agilent_processing_server_reprocessed_rx"
    assert "Processing Server" in selected["integrator_name"]
    assert "stored" not in selected["integrator_name"].casefold()


def test_successful_zero_peak_vendor_result_is_primary_zero_not_missing(
    config: dict,
):
    injection = _injection(
        "vendor-zero",
        "Catalyst 1H",
        openlab_processing_state="PassedWithWarning",
        vendor_peak_count=0,
    )

    result = analysis.analyze_hplc_openlab_dataset(
        _analysis_dataset(injection, include_vendor_peaks=False), config
    )
    selected = result["injection_analysis"][0]["targets"]["sulfoxide"]

    assert result["summary"]["vendor_primary_injection_count"] == 1
    assert selected["peak_source"] == "vendor_rx"
    assert selected["retention_time_min"] is None
    assert selected["area"] == 0.0


def test_failed_vendor_state_cannot_become_primary_even_if_peak_rows_exist(
    config: dict,
):
    assert analysis._vendor_result_available(
        {"openlab_processing_state": "NoMethodProvided"},
        [{"retention_time_min": 5.5, "area": 1.0}],
        config,
    ) is False
    injection = _injection(
        "failed-vendor",
        "Catalyst 1H",
        openlab_processing_state="NoMethodProvided",
    )
    result = analysis.analyze_hplc_openlab_dataset(_analysis_dataset(injection), config)
    selected = result["injection_analysis"][0]["targets"]["sulfoxide"]
    assert selected["peak_source"] == "vendor_result_unavailable"
    assert selected["area"] is None
    assert selected["retention_time_min"] is None
    assert result["sample_results"][0]["used_injection_ids"] == []


def test_discarded_rerun_quality_label_follows_processing_method(
    config: dict,
):
    result = analysis.analyze_hplc_openlab_dataset(
        _analysis_dataset(_injection("used", "Catalyst 1H")),
        config,
    )
    used = result["injection_analysis"][0]
    used["experiment_date"] = date.fromisoformat(used["experiment_date"])
    discarded = deepcopy(used)
    discarded.update(
        {
            "injection_id": "discarded",
            "raw_file": "discarded.dx",
            "source_relative": "discarded.dx",
            "acquisition_local": "2026-07-18T10:05:00+08:00",
            "quality": "待人工复核",
        }
    )

    abnormal_rerun = analysis._combine_final_result(
        [used, discarded],
        [used],
        [discarded],
        group_id="RG001",
        process_method="舍弃异常重打",
        process_note="test",
        config=config,
    )
    trend_choice = analysis._combine_final_result(
        [used, discarded],
        [used],
        [discarded],
        group_id="RG001",
        process_method="趋势择优",
        process_note="test",
        config=config,
    )

    assert abnormal_rerun["data_quality"] == "正常（已排除异常重打）"
    assert trend_choice["data_quality"] == "正常（趋势择优）"
