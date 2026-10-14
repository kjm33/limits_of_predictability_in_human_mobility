"""Run any pipeline stage against any dataset's processed directory.

Equivalent to ``python -m mobility.<module>`` for GeoLife, but points the
stage at ``data/processed/<dataset>/`` for the new datasets:

    uv run python scripts/run_stage.py sequences --dataset fsq_nyc
    uv run python scripts/run_stage.py deep --dataset yjmob1 --epochs 1
    uv run python scripts/run_stage.py baselines --dataset yjmob1 --shards 8

Ingest stages for the new datasets are separate:
``python -m mobility.yjmob`` / ``python -m mobility.checkins``.
"""

import argparse
from importlib import import_module

STAGES = {
    "stays": "stay.run_stays",
    "coverage": "h3map.run_coverage",
    "sequences": "sequences.build_sequences",
    "entropy": "entropy.run_entropy",
    "baselines": "baselines.run_baselines",
    "routines": "routines.run_routines",
    "graphs": "graphs.run_graphs",
    "deep": "deep.run_deep",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=sorted(STAGES))
    parser.add_argument("--dataset", default="geolife", help="dataset key (default geolife)")
    parser.add_argument("--epochs", type=int, default=3, help="training epochs (deep only)")
    parser.add_argument(
        "--min-points",
        type=int,
        default=None,
        help="min observations per user before panel build (sequences only); "
        "bounds memory for long-span check-in datasets (e.g. brightkite: 100)",
    )
    parser.add_argument(
        "--shards",
        type=int,
        default=1,
        help="user shards for hourly baselines (baselines only); >1 enables the "
        "memory-bounded streaming path for 100k+ user panels (e.g. yjmob1: 8)",
    )
    args = parser.parse_args()

    module_name, func_name = STAGES[args.stage].split(".")
    func = getattr(import_module(f"mobility.{module_name}"), func_name)

    from mobility import config

    pdir = config.processed_dir(args.dataset)
    print(f"stage={args.stage} dataset={args.dataset} dir={pdir}")
    if args.stage == "deep":
        func(epochs=args.epochs, processed_dir=pdir)
    elif args.stage == "sequences" and args.min_points is not None:
        func(processed_dir=pdir, min_points_per_user=args.min_points)
    elif args.stage == "baselines" and args.shards > 1:
        func(processed_dir=pdir, shards=args.shards)
    else:
        func(processed_dir=pdir)


if __name__ == "__main__":
    main()
