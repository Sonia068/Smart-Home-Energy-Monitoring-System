"""
Phase 12 — Report Generation
Reads energy_log.csv and generates:
  • Console summary
  • PDF report (outputs/energy_report.pdf)

Run:
    python report_generator.py
    python report_generator.py --csv ../data/energy_log.csv
"""

import argparse
import csv
import os
from datetime import datetime

# ── Optional PDF ─────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("[INFO] reportlab not installed. PDF skipped. "
          "Install: pip install reportlab")

CSV_DEFAULT  = os.path.join(os.path.dirname(__file__), "../data/energy_log.csv")
PDF_OUT      = os.path.join(os.path.dirname(__file__), "../outputs/energy_report.pdf")
os.makedirs(os.path.dirname(PDF_OUT), exist_ok=True)


# ─────────────────────────────────────────────
# READ CSV
# ─────────────────────────────────────────────
def read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"[ERROR] CSV not found: {path}")
        print("        Run simulator.py first to generate data.")
        return []
    rows = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Cast numeric columns
            for col in ["voltage_v", "current_a", "apparent_w", "true_w",
                        "wh_interval", "wh_cumulative", "kwh_cumulative",
                        "cost_rs"]:
                try:
                    row[col] = float(row[col])
                except (ValueError, KeyError):
                    row[col] = 0.0
            row["alert_active"] = row.get("alert_active", "False") == "True"
            rows.append(row)
    return rows


# ─────────────────────────────────────────────
# COMPUTE SUMMARY STATS
# ─────────────────────────────────────────────
def compute_stats(rows: list[dict]) -> dict:
    if not rows:
        return {}
    powers = [r["apparent_w"] for r in rows]
    costs  = [r["cost_rs"]    for r in rows]
    return {
        "total_readings":  len(rows),
        "start_time":      rows[0]["timestamp"],
        "end_time":        rows[-1]["timestamp"],
        "avg_voltage_v":   round(sum(r["voltage_v"] for r in rows) / len(rows), 2),
        "avg_current_a":   round(sum(r["current_a"] for r in rows) / len(rows), 4),
        "avg_power_w":     round(sum(powers) / len(powers), 2),
        "peak_power_w":    round(max(powers), 2),
        "min_power_w":     round(min(powers), 2),
        "total_wh":        round(rows[-1]["wh_cumulative"], 4),
        "total_kwh":       round(rows[-1]["kwh_cumulative"], 6),
        "total_cost_rs":   round(rows[-1]["cost_rs"], 4),
        "alert_count":     sum(1 for r in rows if r["alert_active"]),
        "modes":           list({r.get("mode","?") for r in rows}),
    }


# ─────────────────────────────────────────────
# CONSOLE REPORT
# ─────────────────────────────────────────────
def print_report(stats: dict, rows: list[dict]):
    print("\n" + "═"*70)
    print("  SMART HOME ENERGY MONITORING — CONSUMPTION REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═"*70)
    print(f"  Period         : {stats['start_time']}  →  {stats['end_time']}")
    print(f"  Total Readings : {stats['total_readings']}")
    print(f"  Mode(s)        : {', '.join(stats['modes'])}")
    print("─"*70)
    print(f"  Avg Voltage    : {stats['avg_voltage_v']} V")
    print(f"  Avg Current    : {stats['avg_current_a']} A")
    print(f"  Avg Power      : {stats['avg_power_w']} W")
    print(f"  Peak Power     : {stats['peak_power_w']} W")
    print(f"  Min Power      : {stats['min_power_w']} W")
    print("─"*70)
    print(f"  Total Energy   : {stats['total_wh']} Wh  ({stats['total_kwh']} kWh)")
    print(f"  Total Cost     : ₹ {stats['total_cost_rs']}")
    print(f"  Alerts Fired   : {stats['alert_count']}")
    print("═"*70)

    # Last 10 rows table
    print("\n  LAST 10 READINGS:")
    print(f"  {'Timestamp':<22} {'V':>7} {'A':>7} {'W':>8} {'kWh':>10} {'₹':>8} {'Alert'}")
    print("  " + "─"*70)
    for r in rows[-10:]:
        alert_str = "⚠" if r["alert_active"] else " "
        print(f"  {r['timestamp']:<22} {r['voltage_v']:>7.1f} {r['current_a']:>7.3f}"
              f" {r['apparent_w']:>8.1f} {r['kwh_cumulative']:>10.6f}"
              f" {r['cost_rs']:>8.4f}  {alert_str}")
    print()


# ─────────────────────────────────────────────
# PDF REPORT  (Phase 12)
# ─────────────────────────────────────────────
def generate_pdf(stats: dict, rows: list[dict], out_path: str):
    if not PDF_AVAILABLE:
        print("[SKIP] PDF generation requires reportlab.")
        return

    doc    = SimpleDocTemplate(out_path, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    # Title
    title_style = ParagraphStyle("title", parent=styles["Title"],
                                 textColor=colors.HexColor("#1a73e8"),
                                 fontSize=18, spaceAfter=6)
    story.append(Paragraph("⚡ Smart Home Energy Monitoring Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                           styles["Normal"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a73e8")))
    story.append(Spacer(1, 0.4*cm))

    # Summary table
    story.append(Paragraph("📊 Summary Statistics", styles["Heading2"]))
    summary_data = [
        ["Parameter", "Value"],
        ["Period",          f"{stats['start_time']}  →  {stats['end_time']}"],
        ["Total Readings",  str(stats['total_readings'])],
        ["Mode(s)",         ", ".join(stats['modes'])],
        ["Avg Voltage",     f"{stats['avg_voltage_v']} V"],
        ["Avg Current",     f"{stats['avg_current_a']} A"],
        ["Avg Power",       f"{stats['avg_power_w']} W"],
        ["Peak Power",      f"{stats['peak_power_w']} W"],
        ["Total Energy",    f"{stats['total_wh']} Wh  ({stats['total_kwh']} kWh)"],
        ["Total Cost",      f"₹ {stats['total_cost_rs']}"],
        ["Alerts Fired",    str(stats['alert_count'])],
    ]

    tbl = Table(summary_data, colWidths=[6*cm, 11*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8f9fa"), colors.white]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.6*cm))

    # Readings table (all rows, max 100)
    story.append(Paragraph("📋 Detailed Readings (first 100)", styles["Heading2"]))
    headers = ["Timestamp", "V", "A", "W", "kWh", "₹", "Alert"]
    table_data = [headers]
    for r in rows[:100]:
        table_data.append([
            r["timestamp"],
            f"{r['voltage_v']:.1f}",
            f"{r['current_a']:.3f}",
            f"{r['apparent_w']:.1f}",
            f"{r['kwh_cumulative']:.6f}",
            f"{r['cost_rs']:.4f}",
            "YES" if r["alert_active"] else "—",
        ])

    col_widths = [4.5*cm, 1.8*cm, 1.8*cm, 2*cm, 2.5*cm, 2*cm, 1.8*cm]
    dtbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    dtbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#343a40")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8f9fa"), colors.white]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#dee2e6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        # Highlight alert rows
        *[("BACKGROUND", (0, i+1), (-1, i+1), colors.HexColor("#fff3cd"))
          for i, r in enumerate(rows[:100]) if r["alert_active"]],
    ]))
    story.append(dtbl)

    doc.build(story)
    print(f"[PDF] Report saved: {out_path}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Energy Report Generator")
    parser.add_argument("--csv", default=CSV_DEFAULT, help="Path to CSV log")
    parser.add_argument("--out", default=PDF_OUT,     help="PDF output path")
    args = parser.parse_args()

    rows  = read_csv(args.csv)
    if not rows:
        exit(1)

    stats = compute_stats(rows)
    print_report(stats, rows)
    generate_pdf(stats, rows, args.out)
