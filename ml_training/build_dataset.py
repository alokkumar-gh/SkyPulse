"""
SkyPulse Weather Dataset Builder CLI & Master Orchestrator.
=============================================================
Builds reproducible, traceable, leakage-safe multi-year training datasets from real sources:
- SOURCE A: IMD (authoritative Indian meteorological records)
- SOURCE A2: IMD Pune CRS (gridded climate historical records)
- SOURCE B: data.gov.in (open government weather datasets)
- SOURCE C: Copernicus CDS ERA5 (historical & recent multi-year reanalysis context & weak labels)
- SOURCE D: SkyPulse verified reports (VERIFIED/SUPPORTED platform observations)

Supports:
- Multi-Year date ranges (2024 through latest available 2026+ data).
- Explicit calendar boundary splitting:
    TRAIN: 2024-01-01 -> 2025-12-31
    VAL:   2026-01-01 -> 2026-06-30
    TEST:  2026-07-01 -> latest available CDS date
- Google Colab + Google Drive integration via `--drive-root`.
- Resumable monthly chunk caching in Parquet format.
"""

import os
import sys
import json
import hashlib
import logging
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Ensure project paths are in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")

for p in [BASE_DIR, REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from ml.schemas import (
        TrainingRecord,
        DatasetManifest,
        DatasetReadiness,
        DatasetReadinessReport,
    )
except ImportError:
    from backend.ml.schemas import (
        TrainingRecord,
        DatasetManifest,
        DatasetReadiness,
        DatasetReadinessReport,
    )

from ml_training.quality import DatasetQualityEngine, dataset_quality_engine
from ml_training.labeling import LabelingEngine, labeling_engine
from ml_training.alignment import AlignmentEngine, alignment_engine
from ml_training.splitter import DatasetSplitter, dataset_splitter
from ml_training.readiness import ReadinessEngine, readiness_engine
from ml_training.imd_extractor import IMDDatasetExtractor
from ml_training.datagov_extractor import DataGovDatasetExtractor
from ml_training.skypulse_extractor import SkyPulseVerifiedExtractor
from ml_training.era5_adapter import ERA5Adapter, ERA5MultiYearConfig, INDIA_BOUNDING_BOX, SUPPORTED_VARIABLES
from ml_training.imd_historical_adapter import IMDHistoricalCRSAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("skypulse.ml.build_dataset")


class SkyPulseDatasetBuilder:
    """
    Master multi-year dataset assembly engine for SkyPulse ML training.
    """

    def __init__(
        self,
        output_dir: str = "ml_training/datasets",
        output_version: str = "v2",
        drive_root: Optional[str] = None,
        db_url: Optional[str] = None,
        imd_crs_data_dir: Optional[str] = None,
        era5_cache_dir: Optional[str] = None,
    ):
        # Configure Drive root if provided (Colab workflow)
        if drive_root:
            drive_root_abs = os.path.abspath(drive_root)
            if not os.path.exists(drive_root_abs):
                raise FileNotFoundError(
                    f"DRIVE_ROOT_NOT_FOUND: Google Drive path '{drive_root_abs}' does not exist or is not mounted. "
                    "In Google Colab, please execute `from google.colab import drive; drive.mount('/content/drive')` "
                    "before running dataset generation."
                )
            self.output_dir = os.path.join(drive_root_abs, "datasets")
            target_v2_dir = os.path.join(self.output_dir, output_version)
            self.era5_cache_dir = era5_cache_dir or os.path.join(target_v2_dir, "monthly_chunks")
        else:
            self.output_dir = os.path.abspath(output_dir)
            target_v2_dir = os.path.join(self.output_dir, output_version)
            self.era5_cache_dir = era5_cache_dir or os.path.join(target_v2_dir, "monthly_chunks")

        self.output_version = output_version
        self.db_url = db_url

        self.quality_engine = dataset_quality_engine
        self.labeling_engine = labeling_engine
        self.alignment_engine = alignment_engine
        self.splitter = dataset_splitter
        self.readiness_engine = readiness_engine

        self.imd_extractor = IMDDatasetExtractor(db_url=db_url)
        self.datagov_extractor = DataGovDatasetExtractor(db_url=db_url)
        self.skypulse_extractor = SkyPulseVerifiedExtractor(db_url=db_url)
        self.era5_adapter = ERA5Adapter(cache_dir=self.era5_cache_dir)
        self.imd_crs_adapter = IMDHistoricalCRSAdapter(data_dir=imd_crs_data_dir)

    def build(
        self,
        sources: List[str],
        start_date: str = "2024-01-01",
        end_date: str = "2026-12-31",
        train_end_date: Optional[str] = "2025-12-31",
        val_end_date: Optional[str] = "2026-06-30",
        test_start_date: Optional[str] = "2026-07-01",
        latest_available: bool = True,
        join_era5: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes full extraction, quality filtering, labeling, splitting, and manifest generation.
        """
        # Discover latest available CDS date
        actual_end_date, is_truncated = self.era5_adapter.discover_latest_available_date(end_date)
        effective_end_date = actual_end_date if latest_available else end_date

        logger.info(
            "Starting SkyPulse Dataset Build [version=%s, sources=%s, requested_dates=%s to %s, effective_end=%s (truncated=%s)]",
            self.output_version, sources, start_date, end_date, effective_end_date, is_truncated
        )

        source_status: Dict[str, str] = {}
        source_counts: Dict[str, int] = {}
        raw_records: List[Dict[str, Any]] = []

        # 1. Source Extractions
        # SOURCE A: IMD Live/Database
        if "imd" in sources:
            imd_res = self.imd_extractor.extract(start_date=start_date, end_date=effective_end_date)
            source_status["IMD"] = imd_res.get("status", "UNKNOWN")
            recs = imd_res.get("records", [])
            source_counts["IMD"] = len(recs)
            raw_records.extend(recs)
            logger.info("IMD Extraction status: %s (records: %d)", source_status["IMD"], len(recs))

        # SOURCE A2: IMD Pune CRS Gridded Climate Data
        if "imd_crs" in sources or "imd_historical" in sources:
            crs_res = self.imd_crs_adapter.extract(start_date=start_date, end_date=effective_end_date)
            source_status["IMD_CRS"] = crs_res.get("status", "UNKNOWN")
            recs = crs_res.get("records", [])
            source_counts["IMD_CRS"] = len(recs)
            raw_records.extend(recs)
            logger.info("IMD CRS Extraction status: %s (records: %d)", source_status["IMD_CRS"], len(recs))

        # SOURCE B: data.gov.in
        if "datagov" in sources:
            dg_res = self.datagov_extractor.extract(start_date=start_date, end_date=effective_end_date)
            source_status["data.gov.in"] = dg_res.get("status", "UNKNOWN")
            recs = dg_res.get("records", [])
            source_counts["data.gov.in"] = len(recs)
            raw_records.extend(recs)
            logger.info("data.gov.in Extraction status: %s (records: %d)", source_status["data.gov.in"], len(recs))

        # SOURCE D: SkyPulse Verified Reports
        if "skypulse" in sources:
            sp_res = self.skypulse_extractor.extract(start_date=start_date, end_date=effective_end_date)
            source_status["SkyPulse_Verified"] = sp_res.get("status", "UNKNOWN")
            recs = sp_res.get("records", [])
            source_counts["SkyPulse_Verified"] = len(recs)
            raw_records.extend(recs)
            logger.info("SkyPulse Verified Extraction status: %s (records: %d)", source_status["SkyPulse_Verified"], len(recs))

        # SOURCE C: Copernicus CDS ERA5 Reanalysis
        if "era5" in sources:
            if not os.getenv("CDS_API_KEY") and not os.getenv("CDSAPI_KEY") and not os.path.exists(os.path.expanduser("~/.cdsapirc")):
                source_status["ERA5"] = "NOT_CONFIGURED"
                source_counts["ERA5"] = 0
                logger.warning("ERA5 Copernicus CDS credentials not configured. Skipping ERA5 extraction.")
            else:
                try:
                    cfg = ERA5MultiYearConfig(
                        start_date=start_date,
                        end_date=effective_end_date,
                        cache_dir=self.era5_cache_dir,
                        latest_available=latest_available,
                    )
                    era5_records = self.era5_adapter.process_era5_training_records(cfg)
                    source_status["ERA5"] = "AVAILABLE" if era5_records else "NO_DATA"
                    source_counts["ERA5"] = len(era5_records)
                    raw_records.extend([r.model_dump() for r in era5_records])
                    logger.info("ERA5 Multi-Year extraction status: %s (records: %d)", source_status["ERA5"], len(era5_records))
                except Exception as e:
                    source_status["ERA5"] = f"ERROR: {str(e)}"
                    source_counts["ERA5"] = 0
                    logger.error("ERA5 processing failed: %s", e)

        logger.info("Total raw records gathered across all sources: %d", len(raw_records))

        # 2. Data Quality & Physical Bounds Validation
        quality_res = self.quality_engine.audit_and_clean_dataset(raw_records)
        valid_records: List[TrainingRecord] = quality_res["valid_records"]
        quality_report: Dict[str, Any] = quality_res["quality_report"]

        logger.info(
            "Quality audit complete: %d valid, %d suspicious, %d rejected",
            quality_report["valid_count"],
            quality_report["suspicious_count"],
            quality_report["rejected_count"],
        )

        # 3. Labeling & Cross-Source Conflict Resolution
        labeled_records: List[TrainingRecord] = []
        for rec in valid_records:
            labeled = self.labeling_engine.process_record(rec)
            labeled_records.append(labeled)

        # 4. Alignment & Environmental Features
        if join_era5 and valid_records:
            logger.info("Joining ERA5 environmental reanalysis features to dataset records...")
            labeled_records = self.alignment_engine.join_era5_features(labeled_records, era5_grid_data=[])

        # 5. Chronological Multi-Year Partitioning
        train_recs, val_recs, test_recs, split_meta = self.splitter.split_chronological(
            labeled_records,
            train_ratio=0.70,
            val_ratio=0.15,
            test_ratio=0.15,
            train_end_date=train_end_date,
            val_end_date=val_end_date,
            test_start_date=test_start_date,
        )

        logger.info(
            "Split complete: Train=%d, Val=%d, Test=%d (Mode: %s, Temporal leakage: %s, Spatial leakage: %s)",
            len(train_recs),
            len(val_recs),
            len(test_recs),
            split_meta.get("split_mode"),
            split_meta.get("temporal_leakage_detected"),
            split_meta.get("spatial_event_leakage_detected"),
        )

        # 6. Training Readiness Audit
        readiness_rep: DatasetReadinessReport = self.readiness_engine.evaluate_readiness(
            labeled_records, split_meta=split_meta
        )

        logger.info(
            "Readiness evaluation: %s (score: %.2f, blockers: %d, warnings: %d)",
            readiness_rep.status.value,
            readiness_rep.overall_score,
            len(readiness_rep.blockers),
            len(readiness_rep.warnings),
        )

        # 7. Write Dataset Files & Manifest
        target_dir = os.path.join(self.output_dir, self.output_version)
        os.makedirs(target_dir, exist_ok=True)

        train_path = os.path.join(target_dir, "train.jsonl")
        val_path = os.path.join(target_dir, "val.jsonl")
        test_path = os.path.join(target_dir, "test.jsonl")
        all_path = os.path.join(target_dir, "all_records.jsonl")
        manifest_path = os.path.join(target_dir, "dataset_manifest.json")
        quality_path = os.path.join(target_dir, "quality_report.json")
        readiness_path = os.path.join(target_dir, "readiness_report.json")

        self._export_jsonl(train_recs, train_path)
        self._export_jsonl(val_recs, val_path)
        self._export_jsonl(test_recs, test_path)
        self._export_jsonl(labeled_records, all_path)

        # Also export compact Parquet versions
        self._export_parquet(train_recs, os.path.join(target_dir, "train.parquet"))
        self._export_parquet(val_recs, os.path.join(target_dir, "val.parquet"))
        self._export_parquet(test_recs, os.path.join(target_dir, "test.parquet"))
        self._export_parquet(labeled_records, os.path.join(target_dir, "all_records.parquet"))

        # Calculate Checksum
        all_hash = self._calc_sha256(all_path) if os.path.exists(all_path) else "NONE"

        # Count label categories
        strong_count = sum(1 for r in labeled_records if r.metadata.get("label_type") == "STRONG")
        weak_count = sum(1 for r in labeled_records if r.metadata.get("label_type") == "WEAK")
        unlabeled_count = sum(1 for r in labeled_records if r.metadata.get("label_type") == "UNLABELED" or r.category.value == "UNKNOWN")

        # Compile comprehensive Multi-Year Manifest
        manifest_data = {
            "dataset_version": self.output_version,
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
            "source_statuses": source_status,
            "source_counts": source_counts,
            "era5_role": "meteorological_context_and_weak_labels",
            "requested_start_date": start_date,
            "requested_end_date": end_date,
            "actual_available_end_date": effective_end_date,
            "actual_start_date": split_meta.get("train_start") or start_date,
            "actual_end_date": split_meta.get("test_end") or effective_end_date,
            "availability_truncated": is_truncated,
            "train_start": split_meta.get("train_start") or start_date,
            "train_end": split_meta.get("train_end") or (train_end_date or "2025-12-31"),
            "validation_start": split_meta.get("val_start") or (val_end_date and "2026-01-01") or "2026-01-01",
            "validation_end": split_meta.get("val_end") or (val_end_date or "2026-06-30"),
            "test_start": split_meta.get("test_start") or (test_start_date or "2026-07-01"),
            "test_end": split_meta.get("test_end") or effective_end_date,
            "split_policy": "fixed_chronological_date_boundaries",
            "record_count": len(labeled_records),
            "train_count": len(train_recs),
            "validation_count": len(val_recs),
            "test_count": len(test_recs),
            "class_counts": readiness_rep.class_counts,
            "strong_label_count": strong_count,
            "weak_label_count": weak_count,
            "unknown_label_count": unlabeled_count,
            "geographic_bounds": {
                "north": INDIA_BOUNDING_BOX[0],
                "west": INDIA_BOUNDING_BOX[1],
                "south": INDIA_BOUNDING_BOX[2],
                "east": INDIA_BOUNDING_BOX[3],
            },
            "era5_variables": SUPPORTED_VARIABLES,
            "era5_resolution": "0.25x0.25",
            "labeling_policy": "Strict hierarchy: Authoritative/Verified > Weak Meteorological Thresholds > Unlabeled. ERA5 observations are never marked as ground truth.",
            "dataset_sha256": all_hash,
            "quality_summary": {
                "valid": quality_report.get("valid_count", 0),
                "suspicious": quality_report.get("suspicious_count", 0),
                "rejected": quality_report.get("rejected_count", 0),
            },
        }

        manifest = DatasetManifest(
            dataset_version=self.output_version,
            creation_timestamp=manifest_data["creation_timestamp"],
            sources=sources,
            source_statuses=source_status,
            total_records=len(labeled_records),
            train_records=len(train_recs),
            val_records=len(val_recs),
            test_records=len(test_recs),
            valid_records=quality_report.get("valid_count", 0),
            rejected_records=quality_report.get("rejected_count", 0),
            strong_labels=strong_count,
            weak_labels=weak_count,
            unlabeled_records=unlabeled_count,
            class_distribution=readiness_rep.class_counts,
            date_range={
                "start": manifest_data["actual_start_date"],
                "end": manifest_data["actual_end_date"],
            },
            geographic_bounds=manifest_data["geographic_bounds"],
            quality_summary=manifest_data["quality_summary"],
            sha256_checksum=all_hash,
            split_info=split_meta,
        )

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        with open(quality_path, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2)

        with open(readiness_path, "w", encoding="utf-8") as f:
            f.write(readiness_rep.model_dump_json(indent=2))

        logger.info("Dataset assembly finalized successfully in %s", target_dir)

        return {
            "status": "SUCCESS",
            "version": self.output_version,
            "target_dir": target_dir,
            "manifest": manifest_data,
            "readiness": readiness_rep.model_dump(),
            "quality": quality_report,
            "split": split_meta,
        }

    @staticmethod
    def _export_jsonl(records: List[TrainingRecord], file_path: str) -> int:
        with open(file_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(r.model_dump_json() + "\n")
        return len(records)

    @staticmethod
    def _export_parquet(records: List[TrainingRecord], file_path: str) -> int:
        if not records:
            return 0
        try:
            import pandas as pd
            df = pd.DataFrame([r.model_dump() for r in records])
            df.to_parquet(file_path, engine="pyarrow", compression="snappy", index=False)
            return len(records)
        except Exception as e:
            logger.warning("Parquet export skipped: %s", e)
            return 0

    @staticmethod
    def _calc_sha256(file_path: str) -> str:
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="SkyPulse Multi-Year Weather Dataset Builder")
    parser.add_argument("--sources", type=str, default="era5,imd,datagov,skypulse", help="Comma-separated data sources")
    parser.add_argument("--start-date", type=str, default="2024-01-01", help="Requested start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default="2026-12-31", help="Requested end date (YYYY-MM-DD)")
    parser.add_argument("--train-end-date", type=str, default="2025-12-31", help="Train partition end date")
    parser.add_argument("--val-end-date", type=str, default="2026-06-30", help="Validation partition end date")
    parser.add_argument("--test-start-date", type=str, default="2026-07-01", help="Test partition start date")
    parser.add_argument("--latest-available", action="store_true", default=True, help="Truncate to latest available CDS date")
    parser.add_argument("--output-version", type=str, default="v2", help="Dataset version identifier (e.g. v2)")
    parser.add_argument("--output-dir", type=str, default="ml_training/datasets", help="Output directory path")
    parser.add_argument("--drive-root", type=str, default=None, help="Google Drive root directory (e.g. /content/drive/MyDrive/SkyPulse)")
    parser.add_argument("--era5-cache-dir", type=str, default=None, help="Cache directory for monthly Parquet chunks")
    parser.add_argument("--join-era5", action="store_true", help="Join ERA5 features to records")
    parser.add_argument("--imd-crs-dir", type=str, default=None, help="Directory containing IMD CRS NetCDF files")
    parser.add_argument("--db-url", type=str, default=None, help="Database connection URL override")

    args = parser.parse_args()
    sources_list = [s.strip().lower() for s in args.sources.split(",") if s.strip()]

    builder = SkyPulseDatasetBuilder(
        output_dir=args.output_dir,
        output_version=args.output_version,
        drive_root=args.drive_root,
        db_url=args.db_url,
        imd_crs_data_dir=args.imd_crs_dir,
        era5_cache_dir=args.era5_cache_dir,
    )

    result = builder.build(
        sources=sources_list,
        start_date=args.start_date,
        end_date=args.end_date,
        train_end_date=args.train_end_date,
        val_end_date=args.val_end_date,
        test_start_date=args.test_start_date,
        latest_available=args.latest_available,
        join_era5=args.join_era5,
    )

    print("\n" + "=" * 65)
    print("SKYPULSE MULTI-YEAR DATASET BUILD SUMMARY")
    print("=" * 65)
    print(f"Dataset Version:        {result['version']}")
    print(f"Target Directory:       {result['target_dir']}")
    print(f"Requested Date Range:   {result['manifest']['requested_start_date']} -> {result['manifest']['requested_end_date']}")
    print(f"Actual Date Range:      {result['manifest']['actual_start_date']} -> {result['manifest']['actual_end_date']} (Truncated: {result['manifest']['availability_truncated']})")
    print(f"Total Records:          {result['manifest']['record_count']}")
    print(f"Train / Val / Test:     {result['manifest']['train_count']} / {result['manifest']['validation_count']} / {result['manifest']['test_count']}")
    print(f"Readiness Status:       {result['readiness']['status']} (Score: {result['readiness']['overall_score']})")
    print(f"Sources Status:         {result['manifest']['source_statuses']}")
    print(f"Source Counts:          {result['manifest']['source_counts']}")
    print(f"Label Counts:           Strong={result['manifest']['strong_label_count']}, Weak={result['manifest']['weak_label_count']}, Unlabeled={result['manifest']['unknown_label_count']}")
    print(f"SHA-256 Hash:           {result['manifest']['dataset_sha256']}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
