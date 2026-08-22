"""Tests for teacher report generation."""

from __future__ import annotations

import pytest

from gapbridge import config, gaps, grouping
from gapbridge.assessment import load_assessment_csv
from gapbridge.models import ApprovalDecision, GroupName, TeacherReportMetadata
from gapbridge.plans import propose_all
from gapbridge.report import build_report, priority_gaps, save_report


@pytest.fixture(scope="module")
def analysis(tmp_path_factory):
    csv_path = tmp_path_factory.mktemp("data") / "synthetic_assessment.csv"
    source = config.PROJECT_ROOT / "data" / "synthetic_assessment.csv"
    csv_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    dataset = load_assessment_csv(csv_path)
    class_analysis = gaps.analyze_class(dataset.learners)
    grouping.assign_groups(class_analysis)
    return class_analysis


@pytest.fixture()
def report(analysis):
    plans = propose_all(analysis)
    approvals = [
        ApprovalDecision(
            decision="approved",
            actor="teacher (simulated)",
            timestamp="2026-08-21T12:00:00+00:00",
            plan_version=1,
            comment="Approved for demo.",
        )
    ]
    metadata = TeacherReportMetadata(
        report_id="gapbridge-report-test",
        generated_at="2026-08-21T12:00:00+00:00",
        assessment_title=analysis.title,
        learner_count=len(analysis.learners),
        plan_version=1,
        source_file="synthetic_assessment.csv",
    )
    from gapbridge.exercises import generate_exercises

    sets = generate_exercises(analysis, plans)
    return build_report(analysis, plans, sets, approvals, metadata)


class TestPriorityGaps:
    def test_gaps_sorted_worst_first_below_threshold(self, analysis):
        gaps = priority_gaps(analysis)
        assert [skill for skill, _avg in gaps] == [
            "adding_fractions",
            "equivalent_fractions",
            "comparing_fractions",
        ]
        assert all(avg < config.SKILL_MASTERY_THRESHOLD for _s, avg in gaps)


class TestReportContent:
    def test_contains_all_required_sections(self, report):
        for heading in (
            "# GapBridge Teacher Report",
            "## 1. Class Overview",
            "## 2. Assessment Summary",
            "## 3. Remediation Groups",
            "## 4. Priority Learning Gaps",
            "## 5. Learner Group Explanations",
            "## 6. Approved Remediation Plans",
            "## 7. Exercise Sets Summary",
            "## 8. Approval Record",
            "## 9. Provenance and Privacy Notes",
        ):
            assert heading in report

    def test_includes_group_counts_and_learner_explanations(self, report):
        counts = {"Mastered": 8, "Developing": 9, "Intensive Support": 7}
        for group_name, count in counts.items():
            assert f"| {group_name} | {count} |" in report
        assert "**S022**" in report
        assert "**S007**" in report

    def test_includes_plan_and_approval_details(self, report):
        assert "plan-intensive-support-v1" in report
        assert "adding_fractions, equivalent_fractions" in report
        assert "**APPROVED** by teacher (simulated)" in report
        assert "plan version 1" in report

    def test_includes_synthetic_data_note(self, report):
        assert "synthetic and anonymized" in report

    def test_save_report_writes_markdown(self, report, tmp_path):
        path = save_report(tmp_path / "teacher_report.md", report)
        saved = path.read_text(encoding="utf-8")
        assert saved == report
        assert path.suffix == ".md"
