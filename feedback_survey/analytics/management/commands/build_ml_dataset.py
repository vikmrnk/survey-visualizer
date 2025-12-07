from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from analytics.services import compute_satisfaction_index, compute_survey_features
from responses.models import ResponseSession
from surveys.models import Survey


class Command(BaseCommand):
    help = "Build a CSV dataset with engineered survey features for ML experiments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-responses",
            type=int,
            default=5,
            help="Minimum number of completed responses to include a survey.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="analytics/data/surveys_ml_dataset.csv",
            help="Path where the CSV dataset will be saved.",
        )

    def handle(self, *args, **options):
        min_responses = options["min_responses"]
        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        surveys = Survey.objects.annotate(
            completed_count=Count(
                "response_sessions",
                filter=Q(response_sessions__status=ResponseSession.Status.COMPLETED),
            ),
        ).prefetch_related("questions")

        rows = []
        for survey in surveys:
            features = compute_survey_features(survey)
            if features.get("num_responses", 0) < min_responses:
                continue
            satisfaction_index = compute_satisfaction_index(features)
            row = {"survey_id": survey.id, "satisfaction_index": satisfaction_index}
            row.update(features)
            rows.append(row)

        if not rows:
            self.stdout.write(self.style.WARNING("No surveys met the criteria."))
            return

        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
        metadata = {
            "num_surveys": len(rows),
            "columns": list(df.columns),
        }
        metadata_path = output_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Dataset saved to {output_path} ({len(rows)} surveys, {len(df.columns)} columns)",
            ),
        )

