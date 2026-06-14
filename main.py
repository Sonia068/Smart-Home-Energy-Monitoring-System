"""
Smart Home Energy Monitoring System
Main Entry Point

Usage:
    python main.py                        # normal sim, 30 readings
    python main.py --mode high            # high usage scenario
    python main.py --mode overload        # overload scenario
    python main.py --mode multi           # multi-appliance
    python main.py --readings 60          # custom count
    python main.py --report               # generate report from existing CSV
    python main.py --mode high --report   # sim + report in one go
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python_simulation"))

from simulator        import run_simulation, APPLIANCE_PROFILES
from report_generator import read_csv, compute_stats, print_report, generate_pdf

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "energy_log.csv")
PDF_PATH = os.path.join(os.path.dirname(__file__), "outputs", "energy_report.pdf")


def main():
    parser = argparse.ArgumentParser(
        description="Smart Home Energy Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Simulation Modes:
  normal   — everyday household (lights, fan, laptop, charger)
  high     — heavy usage (AC, water heater, washing machine)
  overload — all heavy appliances simultaneously (triggers alerts)
  multi    — 6 mixed appliances

Examples:
  python main.py --mode overload --readings 20 --report
  python main.py --report   (just generate report from saved CSV)
        """,
    )
    parser.add_argument("--mode", choices=list(APPLIANCE_PROFILES.keys()),
                        default="normal")
    parser.add_argument("--readings", type=int, default=30)
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--no-mqtt", action="store_true",
                        help="Disable MQTT (offline mode)")
    parser.add_argument("--report", action="store_true",
                        help="Generate PDF report after simulation")
    parser.add_argument("--report-only", action="store_true",
                        help="Skip simulation; only generate report from CSV")
    args = parser.parse_args()

    if not args.report_only:
        run_simulation(
            mode=args.mode,
            n_readings=args.readings,
            mqtt_host=args.mqtt_host,
            use_mqtt=not args.no_mqtt,
        )

    if args.report or args.report_only:
        print("\n[REPORT] Generating report from CSV…")
        rows  = read_csv(CSV_PATH)
        if rows:
            stats = compute_stats(rows)
            print_report(stats, rows)
            generate_pdf(stats, rows, PDF_PATH)


if __name__ == "__main__":
    main()
