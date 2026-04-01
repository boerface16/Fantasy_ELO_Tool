"""PDF report generator for weekly fantasy projections.

Uses reportlab to produce a multi-page PDF with:
- Title page with week range and generation date
- Summary section (total/batter/pitcher points)
- Batter projections table with ELO-colored names and per-game matchups
- Pitcher projections table with ELO-colored names
- Team ELO rankings with weekly rank change
"""

import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

# Color constants
GREEN = "#16a34a"
RED = "#dc2626"
GRAY = "#6b7280"


def _elo_color(delta: float) -> str:
    """Return hex color based on ELO weekly change direction."""
    if delta > 0:
        return GREEN
    if delta < 0:
        return RED
    return GRAY


def _colored(text: str, color: str, style: ParagraphStyle) -> Paragraph:
    """Wrap text in a color-tagged Paragraph for use in table cells."""
    return Paragraph(f'<font color="{color}">{text}</font>', style)


def _elo_badge(elo: float, delta: float, style: ParagraphStyle) -> Paragraph:
    """Render an ELO value color-coded by its weekly delta."""
    color = _elo_color(delta)
    return Paragraph(f'<font color="{color}"><b>{elo:.0f}</b></font>', style)


def generate_pdf(
    projection: dict,
    team_elos: list | None = None,
    player_elos: dict | None = None,
    team_deltas: dict | None = None,
) -> bytes:
    """Generate a PDF report from weekly projection data.

    Args:
        projection: dict with keys matching WeeklyProjection serialization
        team_elos: optional list of dicts with teamCode and elo
        player_elos: optional dict {player_id: {"elo": float, "weekDelta": float}}
        team_deltas: optional dict {teamCode: {"elo": float, "weekDelta": float}}

    Returns:
        PDF file as bytes
    """
    player_elos = player_elos or {}
    team_deltas = team_deltas or {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=9, leading=11)
    cell_style_sm = ParagraphStyle("CellStyleSm", parent=styles["Normal"], fontSize=8, leading=10)
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=24, spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"],
        fontSize=12, textColor=colors.grey, spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"],
        fontSize=14, spaceBefore=16, spaceAfter=8,
        textColor=colors.HexColor("#1e3a5f"),
    )

    elements = []

    # --- Title ---
    week_start = projection.get("weekStart", projection.get("week_start", ""))
    week_end = projection.get("weekEnd", projection.get("week_end", ""))
    elements.append(Paragraph("Fantasy Matchup Report", title_style))
    elements.append(Paragraph(
        f"Week: {week_start} &mdash; {week_end} &nbsp;|&nbsp; Generated: {date.today().isoformat()}",
        subtitle_style,
    ))

    # --- Legend ---
    legend_style = ParagraphStyle(
        "Legend", parent=styles["Normal"], fontSize=8, leading=12, textColor=colors.HexColor("#374151"),
    )
    legend_text = (
        '<b>How to Read This Report</b><br/>'
        '<b>ELO Rating</b> — A number representing relative player or team strength. '
        '1500 = league average. Higher is better.<br/>'
        f'<font color="{GREEN}"><b>Green (1534)</b></font> = ELO gained over the last 7 days (trending up) &nbsp;&nbsp; '
        f'<font color="{RED}"><b>Red (1472)</b></font> = ELO lost over the last 7 days (trending down) &nbsp;&nbsp; '
        f'<font color="{GRAY}"><b>Gray (1500)</b></font> = No change'
    )
    legend_table = Table(
        [[Paragraph(legend_text, legend_style)]],
        colWidths=[6.5 * inch],
    )
    legend_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d1d5db")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(legend_table)
    elements.append(Spacer(1, 12))

    # --- Summary ---
    total = projection.get("totalPoints", projection.get("total_points", 0))
    batter_pts = projection.get("totalBatterPoints", projection.get("total_batter_points", 0))
    pitcher_pts = projection.get("totalPitcherPoints", projection.get("total_pitcher_points", 0))

    summary_data = [
        ["Total Points", "Batter Points", "Pitcher Points"],
        [f"{total:.1f}", f"{batter_pts:.1f}", f"{pitcher_pts:.1f}"],
    ]
    summary_table = Table(summary_data, colWidths=[2.2 * inch] * 3)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # --- Batter Projections ---
    batters = projection.get("batters", [])
    if batters:
        elements.append(Paragraph("Batter Projections", heading_style))

        batter_header = ["Name", "Team", "Slot", "Games", "Total Pts", "PPG"]
        batter_rows = [batter_header]
        for b in batters:
            name = b.get("name", b.get("player_name", ""))
            team = b.get("team", "")
            slot = b.get("slot", "")
            games = b.get("games", 0)
            game_count = len(games) if isinstance(games, list) else games
            total_pts = b.get("totalPoints", b.get("total_points", 0))
            ppg = b.get("pointsPerGame", b.get("points_per_game", 0))

            # Color-coded ELO next to name
            pid = b.get("playerId", b.get("player_id"))
            pdata = player_elos.get(pid, {}) if pid else {}
            elo_val = pdata.get("elo")
            elo_delta = pdata.get("weekDelta", 0)
            if elo_val is not None:
                color = _elo_color(elo_delta)
                name_cell = Paragraph(
                    f'{name} <font color="{color}"><b>({elo_val:.0f})</b></font>', cell_style
                )
            else:
                name_cell = name

            batter_rows.append([name_cell, team, slot, str(game_count), f"{total_pts:.1f}", f"{ppg:.1f}"])

        batter_table = Table(batter_rows, colWidths=[2.4 * inch, 0.6 * inch, 0.6 * inch, 0.7 * inch, 0.9 * inch, 0.8 * inch])
        batter_table.setStyle(_data_table_style(len(batter_rows)))
        elements.append(batter_table)
        elements.append(Spacer(1, 8))

        # Per-batter matchup details
        for b in batters:
            name = b.get("name", b.get("player_name", ""))
            matchups = b.get("matchups", b.get("games", []))
            if isinstance(matchups, list) and matchups:
                elements.append(Paragraph(f"<b>{name}</b> — Game-by-Game", styles["Normal"]))
                detail_header = ["Date", "Opponent", "Pitcher", "Home", "Exp wOBA", "Exp Pts"]
                detail_rows = [detail_header]
                for m in matchups:
                    opp_team = m.get("opponent", m.get("opponent_team", ""))
                    pitcher_name = m.get("pitcher", m.get("opponent_pitcher_name", ""))
                    pitcher_id = m.get("pitcherId", m.get("pitcher_id"))

                    # Color opponent team by team delta
                    td = team_deltas.get(opp_team, {})
                    team_delta = td.get("weekDelta", 0)
                    team_color = _elo_color(team_delta)
                    opp_cell = _colored(opp_team, team_color, cell_style_sm)

                    # Color pitcher ELO by pitcher's weekly delta
                    p_elo = player_elos.get(pitcher_id, {}) if pitcher_id else {}
                    p_elo_val = p_elo.get("elo")
                    p_elo_delta = p_elo.get("weekDelta", 0)
                    if p_elo_val is not None:
                        p_color = _elo_color(p_elo_delta)
                        pitcher_cell = Paragraph(
                            f'{pitcher_name} <font color="{p_color}"><b>({p_elo_val:.0f})</b></font>',
                            cell_style_sm,
                        )
                    else:
                        pitcher_cell = pitcher_name

                    detail_rows.append([
                        m.get("date", m.get("game_date", "")),
                        opp_cell,
                        pitcher_cell,
                        "Yes" if m.get("isHome", m.get("is_home", False)) else "No",
                        f"{m.get('expectedWoba', m.get('expected_woba', 0)):.3f}",
                        f"{m.get('expectedPoints', m.get('expected_points', 0)):.1f}",
                    ])
                detail_table = Table(detail_rows, colWidths=[0.9 * inch, 0.8 * inch, 1.7 * inch, 0.5 * inch, 0.9 * inch, 0.8 * inch])
                detail_table.setStyle(_data_table_style(len(detail_rows), small=True))
                elements.append(detail_table)
                elements.append(Spacer(1, 6))

    # --- Pitcher Projections ---
    pitchers = projection.get("pitchers", [])
    if pitchers:
        elements.append(PageBreak())
        elements.append(Paragraph("Pitcher Projections", heading_style))

        pitcher_header = ["Name", "Team", "Slot", "Starts", "Total Pts"]
        pitcher_rows = [pitcher_header]
        for p in pitchers:
            name = p.get("name", p.get("player_name", ""))
            team = p.get("team", "")
            slot = p.get("slot", "")
            starts = p.get("starts", 0)
            start_count = len(starts) if isinstance(starts, list) else starts
            total_pts = p.get("totalPoints", p.get("total_points", 0))

            # Color-coded ELO next to name
            pid = p.get("playerId", p.get("player_id"))
            pdata = player_elos.get(pid, {}) if pid else {}
            elo_val = pdata.get("elo")
            elo_delta = pdata.get("weekDelta", 0)
            if elo_val is not None:
                color = _elo_color(elo_delta)
                name_cell = Paragraph(
                    f'{name} <font color="{color}"><b>({elo_val:.0f})</b></font>', cell_style
                )
            else:
                name_cell = name

            pitcher_rows.append([name_cell, team, slot, str(start_count), f"{total_pts:.1f}"])

        pitcher_table = Table(pitcher_rows, colWidths=[2.6 * inch, 0.8 * inch, 0.6 * inch, 0.7 * inch, 1.0 * inch])
        pitcher_table.setStyle(_data_table_style(len(pitcher_rows)))
        elements.append(pitcher_table)
        elements.append(Spacer(1, 8))

        # Per-pitcher matchup details
        for p in pitchers:
            name = p.get("name", p.get("player_name", ""))
            matchups = p.get("matchups", p.get("starts", []))
            if isinstance(matchups, list) and matchups:
                elements.append(Paragraph(f"<b>{name}</b> — Starts", styles["Normal"]))
                detail_header = ["Date", "Opponent", "Home", "Exp wOBA", "Exp Pts"]
                detail_rows = [detail_header]
                for m in matchups:
                    opp_team = m.get("opponent", m.get("opponent_team", ""))

                    # Color opponent + team ELO by team delta
                    td = team_deltas.get(opp_team, {})
                    team_elo_val = td.get("elo")
                    team_delta = td.get("weekDelta", 0)
                    team_color = _elo_color(team_delta)
                    if team_elo_val is not None:
                        opp_cell = Paragraph(
                            f'<font color="{team_color}"><b>{opp_team} ({team_elo_val:.0f})</b></font>',
                            cell_style_sm,
                        )
                    else:
                        opp_cell = _colored(opp_team, team_color, cell_style_sm)

                    detail_rows.append([
                        m.get("date", m.get("game_date", "")),
                        opp_cell,
                        "Yes" if m.get("isHome", m.get("is_home", False)) else "No",
                        f"{m.get('expectedWoba', m.get('expected_woba', 0)):.3f}",
                        f"{m.get('expectedPoints', m.get('expected_points', 0)):.1f}",
                    ])
                detail_table = Table(detail_rows, colWidths=[1.0 * inch, 1.4 * inch, 0.6 * inch, 1.0 * inch, 1.0 * inch])
                detail_table.setStyle(_data_table_style(len(detail_rows), small=True))
                elements.append(detail_table)
                elements.append(Spacer(1, 6))

    # --- Team ELO Rankings ---
    if team_elos:
        elements.append(PageBreak())
        elements.append(Paragraph("Team ELO Rankings", heading_style))

        elo_sorted = sorted(team_elos, key=lambda t: t.get("elo", 0), reverse=True)

        # Compute last-week rankings by subtracting weekly delta
        last_week_elos = []
        for t in team_elos:
            tc = t.get("teamCode", t.get("team_code", ""))
            elo = t.get("elo", 0)
            delta = team_deltas.get(tc, {}).get("weekDelta", 0)
            last_week_elos.append({"teamCode": tc, "elo": elo - delta})
        last_week_sorted = sorted(last_week_elos, key=lambda t: t["elo"], reverse=True)
        last_week_rank = {t["teamCode"]: i + 1 for i, t in enumerate(last_week_sorted)}

        elo_header = ["Rank", "Last Wk", "Team", "ELO"]
        elo_rows = [elo_header]
        for i, t in enumerate(elo_sorted, 1):
            tc = t.get("teamCode", t.get("team_code", ""))
            elo = t.get("elo", 0)
            td = team_deltas.get(tc, {})
            delta = td.get("weekDelta", 0)
            color = _elo_color(delta)
            lw_rank = last_week_rank.get(tc, "—")

            team_cell = _colored(f"<b>{tc}</b>", color, cell_style)
            elo_cell = _colored(f"<b>{elo:.0f}</b>", color, cell_style)

            elo_rows.append([str(i), str(lw_rank), team_cell, elo_cell])

        elo_table = Table(elo_rows, colWidths=[0.5 * inch, 0.7 * inch, 0.8 * inch, 0.8 * inch])
        elo_table.setStyle(_data_table_style(len(elo_rows)))
        elements.append(elo_table)

    # --- Footer note ---
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "Generated by Fantasy Matchup Predictor — ELO-powered MLB projections",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=colors.grey),
    ))

    doc.build(elements)
    return buf.getvalue()


def save_pdf(
    projection: dict,
    team_elos: list | None = None,
    player_elos: dict | None = None,
    team_deltas: dict | None = None,
    output_dir: str = "reports",
) -> str:
    """Generate PDF and save to disk.

    Args:
        projection: dict matching WeeklyProjection serialization
        team_elos: optional list of dicts with teamCode and elo
        player_elos: optional dict {player_id: {"elo": float, "weekDelta": float}}
        team_deltas: optional dict {teamCode: {"elo": float, "weekDelta": float}}
        output_dir: directory to write PDF to (created if needed)

    Returns:
        Path to the saved PDF file
    """
    os.makedirs(output_dir, exist_ok=True)
    week_start = projection.get("weekStart", projection.get("week_start", "unknown"))
    filename = f"fantasy-report-{week_start}.pdf"
    path = os.path.join(output_dir, filename)
    pdf_bytes = generate_pdf(projection, team_elos, player_elos=player_elos, team_deltas=team_deltas)
    with open(path, "wb") as f:
        f.write(pdf_bytes)
    return path


def _data_table_style(num_rows: int, small: bool = False) -> TableStyle:
    """Standard table style for data tables."""
    font_size = 8 if small else 10
    header_size = 9 if small else 11
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), header_size),
        ("FONTSIZE", (0, 1), (-1, -1), font_size),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ])
