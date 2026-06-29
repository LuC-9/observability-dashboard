"""Plotly chart builders for the OTel Observability Dashboard."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Theme colors ──────────────────────────────────────────────────────────────
# All colors are hex codes used to keep the dashboard visually consistent
_BG       = "#ffffff"   # light background for the whole chart canvas
_PLOT_BG  = "#f8fafc"   # slightly lighter background for the plot area (slate-50)
_GRID     = "#e2e8f0"   # color of grid lines inside the plot (slate-200)
_FONT     = "#0f172a"   # default text color (slate-900)
_BLUE     = "#3b82f6"   # blue-500
_GREEN    = "#22c55e"   # green-500
_AMBER    = "#eab308"   # amber-500
_RED      = "#ef4444"   # red-500
_VIOLET   = "#8b5cf6"   # violet-500
_SLATE    = "#64748b"   # slate-500

# Maps log severity levels to colors so each level is visually distinct in charts
_SEVERITY_COLORS = {
    "ERROR":   _RED,
    "FATAL":   "#c084fc",
    "WARN":    _AMBER,
    "WARNING": _AMBER,
    "INFO":    _BLUE,
    "DEBUG":   _SLATE,
    "TRACE":   "#475569",
}

# Shared layout settings applied to every chart for a consistent dark-mode look
_LAYOUT = dict(
    paper_bgcolor=_BG,       # outer background (outside the axes)
    plot_bgcolor=_PLOT_BG,   # inner background (inside the axes)
    font=dict(color=_FONT, family="Inter, sans-serif"),
    margin=dict(l=48, r=24, t=48, b=40),   # padding around the chart
)


def _empty(msg: str = "No data available") -> go.Figure:
    # Returns a blank chart with a centered message — used when there's no data to display
    fig = go.Figure()
    fig.add_annotation(
        text=msg, xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=15, color=_SLATE),
    )
    fig.update_layout(**_LAYOUT, height=320)
    return fig


def _axis_style(**kwargs) -> dict:
    # Returns a dict of axis styling options — used to apply consistent grid and line colors
    return dict(gridcolor=_GRID, zeroline=False, linecolor=_GRID, **kwargs)


# ── Logs ──────────────────────────────────────────────────────────────────────

def make_severity_pie(df: pd.DataFrame) -> go.Figure:
    # Draws a donut chart showing what percentage of logs are ERROR, INFO, WARN, etc.
    if df.empty or "severity" not in df.columns:
        return _empty("No log data")

    # Assign each severity its color; unknown severities fall back to slate grey
    colors = [_SEVERITY_COLORS.get(s, _SLATE) for s in df["severity"]]
    fig = go.Figure(go.Pie(
        labels=df["severity"], values=df["count"],
        marker=dict(colors=colors, line=dict(color=_BG, width=2)),
        textinfo="percent+label",   # show both percentage and label on each slice
        hole=0.38,                  # makes it a donut instead of a full pie
    ))
    fig.update_layout(**_LAYOUT, title="Log Severity Distribution", height=340,
                      legend=dict(bgcolor=_BG, bordercolor=_GRID, borderwidth=1))
    return fig


# ── Traces ────────────────────────────────────────────────────────────────────

def make_latency_histogram(df: pd.DataFrame) -> go.Figure:
    # Shows how span durations are distributed — e.g. most calls take 100–200ms
    if df.empty or "duration_ms" not in df.columns:
        return _empty("No trace data")
    data = df["duration_ms"].dropna()   # drop rows where duration is missing
    if data.empty:
        return _empty("No duration data")

    fig = go.Figure(go.Histogram(
        x=data, nbinsx=40,   # split the range into 40 buckets
        marker=dict(color=_BLUE, line=dict(color=_BG, width=0.5)),
        opacity=0.85,
    ))
    fig.update_layout(
        **_LAYOUT, title="Trace Duration Distribution (ms)", height=340,
        xaxis=_axis_style(title="Duration (ms)"),
        yaxis=_axis_style(title="Count"),
    )
    return fig


def make_latency_by_agent(df: pd.DataFrame) -> go.Figure:
    # Horizontal bar chart comparing mean, median, and max latency per agent
    if df.empty or "agent_name" not in df.columns or "duration_ms" not in df.columns:
        return _empty("No agent latency data")

    # Group by agent and compute three summary statistics
    agg = (
        df.dropna(subset=["agent_name", "duration_ms"])
          .groupby("agent_name")["duration_ms"]
          .agg(["mean", "median", "max"])
          .reset_index()
          .sort_values("mean", ascending=True)   # sort so slowest agent appears at top
    )
    if agg.empty:
        return _empty("No agent latency data")

    fig = go.Figure()
    # Each statistic is a separate bar group; horizontal layout makes agent names readable
    fig.add_trace(go.Bar(name="Mean",   x=agg["mean"],   y=agg["agent_name"], orientation="h", marker_color=_BLUE))
    fig.add_trace(go.Bar(name="Median", x=agg["median"], y=agg["agent_name"], orientation="h", marker_color=_GREEN))
    fig.add_trace(go.Bar(name="Max",    x=agg["max"],    y=agg["agent_name"], orientation="h", marker_color=_RED))
    fig.update_layout(
        **_LAYOUT, title="Latency by Agent (ms)", height=max(340, 60 * len(agg) + 80),
        barmode="group",   # bars for each stat are placed side by side
        xaxis=_axis_style(title="Duration (ms)"),
        yaxis=_axis_style(title=""),
        legend=dict(bgcolor=_BG),
    )
    return fig


# ── Time-series helpers ───────────────────────────────────────────────────────

def make_cost_timeseries(df: pd.DataFrame) -> go.Figure:
    # Line chart showing total LLM cost (USD) grouped by hour over the selected time range
    if df.empty or "hour" not in df.columns:
        return _empty("No cost data")
    df = df.dropna(subset=["hour"])
    if df.empty:
        return _empty("No cost data")

    fig = go.Figure(go.Scatter(
        x=df["hour"], y=df["total_cost_usd"].fillna(0),
        mode="lines+markers", name="Cost (USD)",
        line=dict(color=_AMBER, width=2),
        fill="tozeroy", fillcolor="rgba(234,179,8,0.12)",   # shaded area under the line
    ))
    fig.update_layout(
        **_LAYOUT, title="LLM Cost Over Time (USD)", height=320,
        xaxis=_axis_style(title="Time"),
        yaxis=_axis_style(title="USD"),
    )
    return fig


def make_avg_latency_timeseries(df: pd.DataFrame) -> go.Figure:
    # Line chart showing average span duration (ms) per hour
    if df.empty or "hour" not in df.columns:
        return _empty("No latency data")
    df = df.dropna(subset=["hour"])

    fig = go.Figure(go.Scatter(
        x=df["hour"], y=df["avg_duration_ms"].fillna(0),
        mode="lines+markers", name="Avg Latency (ms)",
        line=dict(color=_VIOLET, width=2),
        fill="tozeroy", fillcolor="rgba(139,92,246,0.12)",
    ))
    fig.update_layout(
        **_LAYOUT, title="Avg Latency Over Time (ms)", height=320,
        xaxis=_axis_style(title="Time"),
        yaxis=_axis_style(title="ms"),
    )
    return fig


def make_token_timeseries(df: pd.DataFrame) -> go.Figure:
    # Stacked bar chart showing input and output token counts per hour
    if df.empty or "hour" not in df.columns:
        return _empty("No token data")
    df = df.dropna(subset=["hour"])

    fig = go.Figure()
    # Input tokens stacked below output tokens so the total bar height = total tokens used
    fig.add_trace(go.Bar(
        x=df["hour"], y=df["input_tokens"].fillna(0),
        name="Input Tokens", marker_color=_BLUE,
    ))
    fig.add_trace(go.Bar(
        x=df["hour"], y=df["output_tokens"].fillna(0),
        name="Output Tokens", marker_color=_GREEN,
    ))
    fig.update_layout(
        **_LAYOUT, title="Token Usage Over Time", height=320,
        barmode="stack",   # stack input + output on top of each other
        xaxis=_axis_style(title="Time"),
        yaxis=_axis_style(title="Tokens"),
        legend=dict(bgcolor=_BG),
    )
    return fig


def make_error_rate_timeseries(df: pd.DataFrame) -> go.Figure:
    # Line chart showing what percentage of spans were errors each hour
    if df.empty or "hour" not in df.columns:
        return _empty("No error data")
    df = df.dropna(subset=["hour"]).copy()
    if "error_count" not in df.columns or "span_count" not in df.columns:
        return _empty("No error rate data")

    # Calculate error rate as a percentage; replace 0 span_count with 1 to avoid divide-by-zero
    df["error_rate"] = (df["error_count"] / df["span_count"].replace(0, 1) * 100).round(2)
    fig = go.Figure(go.Scatter(
        x=df["hour"], y=df["error_rate"],
        mode="lines+markers", name="Error Rate (%)",
        line=dict(color=_RED, width=2),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.12)",
    ))
    fig.update_layout(
        **_LAYOUT, title="Error Rate Over Time (%)", height=320,
        xaxis=_axis_style(title="Time"),
        yaxis=_axis_style(title="%", rangemode="tozero"),   # always start y-axis at 0
    )
    return fig


# ── Metrics ───────────────────────────────────────────────────────────────────

# Cycle through these colors when plotting multiple metrics so each gets a distinct color
_PALETTE = [_BLUE, _GREEN, _AMBER, _VIOLET, _RED, _SLATE]


def _is_cost(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("usd", "cost"))


def make_single_metric_chart(df: pd.DataFrame, mname: str, color: str) -> go.Figure:
    """Standalone line chart for one metric name — used for the per-metric grid."""
    mdf = df[df["metric_name"] == mname].copy() if not df.empty else df
    if mdf.empty:
        return _empty(f"No data for {mname}")

    mtype = mdf["metric_type"].iloc[0] if "metric_type" in mdf.columns else "Counter"
    if mtype == "Histogram":
        y_vals = mdf["histogram_sum"].fillna(0)
        y_label = "Sum"
    else:
        mdf["_val"] = mdf["value_int"].fillna(mdf["value_double"])
        y_vals  = mdf["_val"].fillna(0)
        y_label = "Value"

    cost = _is_cost(mname)
    if cost:
        y_label = "USD ($)"

    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    fig = go.Figure(go.Scatter(
        x=mdf["timestamp"], y=y_vals,
        mode="lines+markers", name=mname,
        line=dict(color=color, width=2),
        fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.1)",
        showlegend=False,
    ))
    yaxis = _axis_style(title=y_label)
    if cost:
        yaxis["tickprefix"] = "$"
        yaxis["tickformat"] = ".6f"
    fig.update_layout(
        **_LAYOUT, title=mname, height=260,
        xaxis=_axis_style(title=""),
        yaxis=yaxis,
    )
    return fig


def make_metric_timeseries(df: pd.DataFrame) -> go.Figure:
    """Returns a list of per-metric figures via make_single_metric_chart.
    Kept for backward compatibility — callers should prefer per-metric charts."""
    return _empty("No metrics data") if df.empty else _empty("Use metric_charts instead")


def make_metric_bar_summary(df: pd.DataFrame) -> go.Figure:
    """Latest value per metric as a bar chart — good for counters."""
    if df.empty or "metric_name" not in df.columns:
        return _empty("No metrics data")

    rows = []
    for mname, gdf in df.groupby("metric_name"):
        mtype = gdf["metric_type"].iloc[0] if "metric_type" in gdf.columns else "Counter"
        # Sort by time and take the most recent data point for each metric
        latest = gdf.sort_values("timestamp").iloc[-1]

        def _scalar(v):
            # Safely converts a value to float; returns 0.0 if it's None or NaN
            return 0.0 if (v is None or (isinstance(v, float) and pd.isna(v))) else float(v)

        if mtype == "Histogram":
            val = _scalar(latest.get("histogram_sum"))
        else:
            # Use int value first, then fall back to double
            val = _scalar(latest.get("value_int")) or _scalar(latest.get("value_double"))
        rows.append({"metric": mname, "value": val})

    if not rows:
        return _empty("No summary data")

    def _fmt(mname: str, val: float) -> str:
        if _is_cost(mname):
            if val >= 0.01:
                return f"${val:.4f}"
            return f"${val:.6f}"
        if val == int(val):
            return f"{int(val):,}"
        return f"{val:,.4g}"

    agg = pd.DataFrame(rows).sort_values("value", ascending=True)
    agg["label"] = [_fmt(r["metric"], r["value"]) for _, r in agg.iterrows()]

    fig = go.Figure(go.Bar(
        x=agg["value"], y=agg["metric"], orientation="h",
        text=agg["label"], textposition="outside",
        textfont=dict(color=_FONT, size=11),
        marker=dict(color=_BLUE, line=dict(color=_BG, width=0.5)),
    ))
    fig.update_layout(
        **_LAYOUT, title="Latest Metric Values", height=max(300, 55 * len(agg) + 80),
        xaxis=_axis_style(title="Value", tickformat=".4g", exponentformat="none"),
        yaxis=_axis_style(title=""),
    )
    return fig


# ── Trace Waterfall ───────────────────────────────────────────────────────────

# Color each span bar by its status so errors stand out immediately
_STATUS_COLORS = {"ERROR": _RED, "OK": _GREEN, "UNSET": _BLUE}


def _build_span_tree(df: pd.DataFrame):
    """Return (ordered_rows, depths) via DFS on parent_span_id tree."""
    span_ids = set(df["span_id"].dropna())
    # Build a dict so we can look up any span by its ID in O(1)
    by_id = {row["span_id"]: row for _, row in df.iterrows()}

    # Build a children map: for each span, which spans have it as their parent
    children: dict[str, list] = {sid: [] for sid in span_ids}

    roots = []
    for _, row in df.iterrows():
        pid = row.get("parent_span_id")
        if pid and pid in span_ids:
            # This span has a known parent — attach it as a child
            children[pid].append(row["span_id"])
        else:
            # No known parent means this is a root span (top of the tree)
            roots.append(row["span_id"])

    ordered, depths = [], []

    def dfs(sid: str, depth: int):
        # Depth-first traversal: visit a span, then recursively visit its children
        row = by_id.get(sid)
        if row is None:
            return
        ordered.append(row)
        depths.append(depth)   # depth tells us how much to indent this span's label
        # Visit children in order of their start time so the waterfall reads left to right
        for child in sorted(children.get(sid, []), key=lambda c: by_id[c].get("rel_start_ms", 0)):
            dfs(child, depth + 1)

    # Start DFS from each root, sorted by start time
    for root in sorted(roots, key=lambda s: by_id[s].get("rel_start_ms", 0)):
        dfs(root, 0)

    return ordered, depths


def make_trace_waterfall(df: pd.DataFrame, trace_id: str = "") -> go.Figure:
    # Draws a Gantt-style waterfall chart showing all spans in a single trace
    # Each span is a horizontal bar; position on x-axis = time since trace started
    if df.empty:
        return _empty("Select a trace from the list — click any row then Load Waterfall")

    df = df.copy()
    # Parse timestamps to timezone-aware datetime objects for accurate subtraction
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["end_time"]   = pd.to_datetime(df["end_time"],   utc=True, errors="coerce")

    # Convert absolute timestamps to milliseconds relative to the earliest span start
    trace_start = df["start_time"].min()
    df["rel_start_ms"] = (df["start_time"] - trace_start).dt.total_seconds() * 1000
    df["rel_end_ms"]   = (df["end_time"]   - trace_start).dt.total_seconds() * 1000
    # Ensure every bar is at least 0.5ms wide so it's visible even for very fast spans
    df["dur_ms"]       = (df["rel_end_ms"] - df["rel_start_ms"]).clip(lower=0.5)

    ordered, depths = _build_span_tree(df)
    if not ordered:
        return _empty("Could not build span tree")

    total_ms = df["rel_end_ms"].max()   # total trace duration, used for label width threshold

    y_ticks, x_starts, x_durs, colors, hovers, texts = [], [], [], [], [], []

    for row, depth in zip(ordered, depths):
        # Indent child spans with spaces and a tree connector symbol
        prefix = "  " * depth + ("└ " if depth > 0 else "")
        label  = f"{prefix}{row.get('span_name') or 'unnamed'}"
        y_ticks.append(label)

        rs  = float(row.get("rel_start_ms") or 0)
        dur = float(row.get("dur_ms") or 0.5)
        x_starts.append(rs)
        x_durs.append(dur)

        status = str(row.get("status_code") or "UNSET")
        colors.append(_STATUS_COLORS.get(status, _BLUE))

        # Only show the duration text inside the bar if the bar is wide enough to fit it
        texts.append(f"{dur:.1f}ms" if dur > total_ms * 0.06 else "")

        # Build a rich hover tooltip shown when the user mouses over a span bar
        agent  = row.get("agent_name") or "—"
        kind   = row.get("span_kind")  or "—"
        ti     = row.get("gen_ai_input_tokens")
        to_    = row.get("gen_ai_output_tokens")
        cost   = row.get("llm_cost_total_usd")
        msg    = row.get("status_message") or ""

        tip = (
            f"<b>{row.get('span_name') or 'unnamed'}</b><br>"
            f"Duration : {dur:.2f} ms<br>"
            f"Status   : {status}" + (f" — {msg}" if msg else "") + "<br>"
            f"Kind     : {kind}<br>"
            f"Agent    : {agent}<br>"
        )
        # Convert token values safely — treat None/NaN as zero
        _i = 0 if (ti is None or pd.isna(ti)) else int(ti)
        _o = 0 if (to_ is None or pd.isna(to_)) else int(to_)
        if _i or _o:
            tip += f"Tokens   : {_i} in / {_o} out<br>"
        if cost is not None and not pd.isna(cost):
            tip += f"Cost     : ${float(cost):.6f}<br>"
        hovers.append(tip)

    n = len(y_ticks)
    row_h = 34   # pixel height per span row
    height = max(420, row_h * n + 120)

    # Truncate very long trace IDs in the chart title to avoid overflow
    short_id = (trace_id[:20] + "…") if len(trace_id) > 20 else trace_id
    title = f"Trace Waterfall  •  {short_id}" if short_id else "Trace Waterfall"

    fig = go.Figure()

    # Invisible base bar — Plotly Bar needs a "base" value for stacking,
    # so we add a transparent bar of width = rel_start_ms to push each visible bar to the right
    fig.add_trace(go.Bar(
        x=x_starts, y=list(range(n)), orientation="h",
        marker=dict(color="rgba(0,0,0,0)"), hoverinfo="skip",
        showlegend=False,
    ))

    # Visible span bars — width = duration, base = start offset so they begin at the right time
    fig.add_trace(go.Bar(
        x=x_durs, y=list(range(n)), orientation="h",
        base=x_starts,
        marker=dict(color=colors, opacity=0.88, line=dict(color=_BG, width=0.8)),
        text=texts, textposition="inside",
        textfont=dict(color="white", size=11),
        hovertext=hovers, hoverinfo="text",
        showlegend=False,
    ))

    # Add dummy traces just to create legend entries for each status color
    for label, color in _STATUS_COLORS.items():
        fig.add_trace(go.Bar(
            x=[None], y=[None], orientation="h",
            name=label, marker_color=color, showlegend=True,
        ))

    fig.update_layout(
        **_LAYOUT,
        title=title,
        height=height,
        barmode="overlay",   # overlay means the invisible base and visible bar share the same position
        xaxis=_axis_style(title="Time from trace start (ms)"),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(n)),
            ticktext=y_ticks,
            autorange="reversed",   # first span at the top, like a typical waterfall diagram
            gridcolor=_GRID, zeroline=False, linecolor=_GRID,
            tickfont=dict(family="monospace", size=12),
        ),
        bargap=0.25,
        legend=dict(
            orientation="h", x=0, y=1.04,
            bgcolor=_BG, bordercolor=_GRID, borderwidth=1,
            font=dict(size=12),
        ),
    )
    return fig


# ── Sessions ──────────────────────────────────────────────────────────────────

def make_sessions_status_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty or "status" not in df.columns:
        return _empty("No session data")
    grp = df.groupby("status").size().reset_index(name="count")
    status_colors = {"completed": _GREEN, "active": _BLUE, "failed": _RED, "expired": _AMBER}
    colors = [status_colors.get(s, _SLATE) for s in grp["status"]]
    
    # Calculate percentage for labels in legend
    total = grp["count"].sum()
    labels = [
        f"{status} — {int(round(count / total * 100))}%"
        for status, count in zip(grp["status"], grp["count"])
    ]
    
    fig = go.Figure(go.Pie(
        labels=labels, values=grp["count"],
        marker=dict(colors=colors, line=dict(color=_BG, width=2)),
        textinfo="none", hole=0.38,
        hoverinfo="label+value"
    ))
    fig.update_layout(
        **_LAYOUT,
        title=dict(
            text="STATUS DISTRIBUTION",
            font=dict(size=11, color="#6b7280", family="Inter, sans-serif"),
        ),
        height=340,
        legend=dict(bgcolor=_BG, bordercolor=_GRID, borderwidth=1)
    )
    return fig


def make_sessions_over_time(df: pd.DataFrame) -> go.Figure:
    if df.empty or "hour" not in df.columns:
        return _empty("No session timeline data")
    df = df.dropna(subset=["hour"])
    fig = go.Figure(go.Bar(
        x=df["hour"], y=df["count"],
        name="Sessions",
        marker=dict(
            color="#10b981", # Fallback color, will be styled by CSS gradient
            line=dict(color="rgba(0,0,0,0)"),
            cornerradius=8
        ),
    ))
    fig.update_layout(
        **_LAYOUT,
        title=dict(
            text="SESSIONS OVER TIME",
            font=dict(size=11, color="#6b7280", family="Inter, sans-serif"),
        ),
        height=320,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, showline=True, linecolor="#e2e8f0"),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False, showline=True, linecolor="#e2e8f0"),
        barcornerradius=8,
    )
    return fig


def make_cost_by_agent(df: pd.DataFrame) -> go.Figure:
    cost_col = "total_cost" if "total_cost" in df.columns else "cost" if "cost" in df.columns else None
    if df.empty or "agent_id" not in df.columns or cost_col is None:
        return _empty("No cost data")
    agg = df.groupby("agent_id")[cost_col].sum().reset_index().sort_values(cost_col, ascending=True)
    if agg.empty:
        return _empty("No cost data")
    fig = go.Figure(go.Bar(
        x=agg[cost_col], y=agg["agent_id"], orientation="h",
        text=[f"${v:.4f}" for v in agg[cost_col]], textposition="outside",
        textfont=dict(color=_FONT, size=11),
        marker=dict(color=_AMBER, line=dict(color=_BG, width=0.5)),
    ))
    fig.update_layout(
        **_LAYOUT, title="Total Cost by Agent (USD)", height=max(300, 55 * len(agg) + 80),
        xaxis=_axis_style(title="Cost (USD)", tickprefix="$"),
        yaxis=_axis_style(title=""),
    )
    return fig


def make_turns_histogram(df: pd.DataFrame) -> go.Figure:
    if df.empty or "total_turns" not in df.columns:
        return _empty("No turns data")
    data = df["total_turns"].dropna()
    fig = go.Figure(go.Histogram(
        x=data, nbinsx=20,
        marker=dict(color=_VIOLET, line=dict(color=_BG, width=0.5)),
        opacity=0.85,
    ))
    fig.update_layout(
        **_LAYOUT, title="Session Turns Distribution", height=320,
        xaxis=_axis_style(title="Total Turns"),
        yaxis=_axis_style(title="Count"),
    )
    return fig


# ── LLM Interactions ──────────────────────────────────────────────────────────

def make_cost_by_model(df: pd.DataFrame) -> go.Figure:
    if df.empty or "model_name" not in df.columns:
        return _empty("No LLM cost data")
    agg = df.groupby("model_name")["cost"].sum().reset_index().sort_values("cost", ascending=True)
    fig = go.Figure(go.Bar(
        x=agg["cost"], y=agg["model_name"], orientation="h",
        text=[f"${v:.6f}" for v in agg["cost"]], textposition="outside",
        textfont=dict(color=_FONT, size=11),
        marker=dict(color=_AMBER, line=dict(color=_BG, width=0.5)),
    ))
    fig.update_layout(
        **_LAYOUT, title="Total Cost by Model (USD)", height=max(300, 55 * len(agg) + 80),
        xaxis=_axis_style(title="Cost (USD)", tickprefix="$"),
        yaxis=_axis_style(title=""),
    )
    return fig


def make_llm_latency_hist(df: pd.DataFrame) -> go.Figure:
    if df.empty or "latency_ms" not in df.columns:
        return _empty("No latency data")
    data = df["latency_ms"].dropna()
    fig = go.Figure(go.Histogram(
        x=data, nbinsx=40,
        marker=dict(color=_VIOLET, line=dict(color=_BG, width=0.5)),
        opacity=0.85,
    ))
    fig.update_layout(
        **_LAYOUT, title="LLM Latency Distribution (ms)", height=320,
        xaxis=_axis_style(title="Latency (ms)"),
        yaxis=_axis_style(title="Count"),
    )
    return fig


def make_llm_tokens_over_time(df: pd.DataFrame) -> go.Figure:
    if df.empty or "hour" not in df.columns:
        return _empty("No token data")
    df = df.dropna(subset=["hour"])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["hour"], y=df["tokens_input"].fillna(0),
                         name="Input Tokens", marker_color=_BLUE))
    fig.add_trace(go.Bar(x=df["hour"], y=df["tokens_output"].fillna(0),
                         name="Output Tokens", marker_color=_GREEN))
    fig.update_layout(
        **_LAYOUT, title="Token Usage Over Time", height=320,
        barmode="stack",
        xaxis=_axis_style(title="Time"),
        yaxis=_axis_style(title="Tokens"),
        legend=dict(bgcolor=_BG),
    )
    return fig


def make_provider_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty or "provider" not in df.columns:
        return _empty("No provider data")
    grp = df.groupby("provider").size().reset_index(name="count")
    fig = go.Figure(go.Pie(
        labels=grp["provider"], values=grp["count"],
        marker=dict(line=dict(color=_BG, width=2)),
        textinfo="percent+label", hole=0.38,
    ))
    fig.update_layout(**_LAYOUT, title="Calls by Provider", height=340,
                      legend=dict(bgcolor=_BG, bordercolor=_GRID, borderwidth=1))
    return fig


# ── Tool Executions ───────────────────────────────────────────────────────────

def make_tool_calls_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty or "tool_name" not in df.columns:
        return _empty("No tool execution data")
    agg = df.groupby("tool_name").size().reset_index(name="count").sort_values("count", ascending=True)
    fig = go.Figure(go.Bar(
        x=agg["count"], y=agg["tool_name"], orientation="h",
        text=agg["count"].astype(str), textposition="outside",
        textfont=dict(color=_FONT, size=11),
        marker=dict(color=_BLUE, line=dict(color=_BG, width=0.5)),
    ))
    fig.update_layout(
        **_LAYOUT, title="Executions by Tool", height=max(300, 55 * len(agg) + 80),
        xaxis=_axis_style(title="Count"),
        yaxis=_axis_style(title=""),
    )
    return fig


def make_tool_latency_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty or "tool_name" not in df.columns or "latency_ms" not in df.columns:
        return _empty("No tool latency data")
    agg = (df.dropna(subset=["tool_name", "latency_ms"])
             .groupby("tool_name")["latency_ms"]
             .mean().reset_index()
             .sort_values("latency_ms", ascending=True))
    fig = go.Figure(go.Bar(
        x=agg["latency_ms"], y=agg["tool_name"], orientation="h",
        text=[f"{v:.0f}ms" for v in agg["latency_ms"]], textposition="outside",
        textfont=dict(color=_FONT, size=11),
        marker=dict(color=_VIOLET, line=dict(color=_BG, width=0.5)),
    ))
    fig.update_layout(
        **_LAYOUT, title="Avg Latency by Tool (ms)", height=max(300, 55 * len(agg) + 80),
        xaxis=_axis_style(title="Avg Latency (ms)"),
        yaxis=_axis_style(title=""),
    )
    return fig


def make_tool_status_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty or "status" not in df.columns:
        return _empty("No tool status data")
    grp = df.groupby("status").size().reset_index(name="count")
    status_colors = {"success": _GREEN, "failure": _RED, "timeout": _AMBER}
    colors = [status_colors.get(s, _SLATE) for s in grp["status"]]
    fig = go.Figure(go.Pie(
        labels=grp["status"], values=grp["count"],
        marker=dict(colors=colors, line=dict(color=_BG, width=2)),
        textinfo="percent+label", hole=0.38,
    ))
    fig.update_layout(**_LAYOUT, title="Tool Execution Status", height=340,
                      legend=dict(bgcolor=_BG, bordercolor=_GRID, borderwidth=1))
    return fig


def make_tool_executions_over_time(df: pd.DataFrame) -> go.Figure:
    if df.empty or "hour" not in df.columns:
        return _empty("No execution timeline data")
    df = df.dropna(subset=["hour"])
    fig = go.Figure(go.Scatter(
        x=df["hour"], y=df["count"],
        mode="lines+markers", name="Executions",
        line=dict(color=_GREEN, width=2),
        fill="tozeroy", fillcolor="rgba(34,197,94,0.12)",
    ))
    fig.update_layout(
        **_LAYOUT, title="Tool Executions Over Time", height=320,
        xaxis=_axis_style(title="Time"),
        yaxis=_axis_style(title="Executions", rangemode="tozero"),
    )
    return fig


# ── Errors ────────────────────────────────────────────────────────────────────

def make_errors_over_time(df: pd.DataFrame) -> go.Figure:
    if df.empty or "hour" not in df.columns:
        return _empty("No error timeline data")
    df = df.dropna(subset=["hour"])
    fig = go.Figure(go.Scatter(
        x=df["hour"], y=df["count"],
        mode="lines+markers", name="Errors",
        line=dict(color=_RED, width=2),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.12)",
    ))
    fig.update_layout(
        **_LAYOUT, title="Errors Over Time", height=320,
        xaxis=_axis_style(title="Time"),
        yaxis=_axis_style(title="Errors", rangemode="tozero"),
    )
    return fig


def make_errors_by_component(df: pd.DataFrame) -> go.Figure:
    if df.empty or "component" not in df.columns:
        return _empty("No component data")
    agg = df.groupby("component").size().reset_index(name="count").sort_values("count", ascending=True)
    fig = go.Figure(go.Bar(
        x=agg["count"], y=agg["component"], orientation="h",
        text=agg["count"].astype(str), textposition="outside",
        textfont=dict(color=_FONT, size=11),
        marker=dict(color=_RED, line=dict(color=_BG, width=0.5)),
    ))
    fig.update_layout(
        **_LAYOUT, title="Errors by Component", height=max(300, 55 * len(agg) + 80),
        xaxis=_axis_style(title="Count"),
        yaxis=_axis_style(title=""),
    )
    return fig


def make_errors_by_type(df: pd.DataFrame) -> go.Figure:
    if df.empty or "error_type" not in df.columns:
        return _empty("No error type data")
    agg = df.groupby("error_type").size().reset_index(name="count").sort_values("count", ascending=True)
    fig = go.Figure(go.Bar(
        x=agg["count"], y=agg["error_type"], orientation="h",
        text=agg["count"].astype(str), textposition="outside",
        textfont=dict(color=_FONT, size=11),
        marker=dict(color=_AMBER, line=dict(color=_BG, width=0.5)),
    ))
    fig.update_layout(
        **_LAYOUT, title="Errors by Type", height=max(300, 55 * len(agg) + 80),
        xaxis=_axis_style(title="Count"),
        yaxis=_axis_style(title=""),
    )
    return fig


def make_error_severity_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty or "severity" not in df.columns:
        return _empty("No severity data")
    grp = df.groupby("severity").size().reset_index(name="count")
    sev_colors = {"CRITICAL": "#c084fc", "ERROR": _RED, "WARNING": _AMBER}
    colors = [sev_colors.get(s, _SLATE) for s in grp["severity"]]
    fig = go.Figure(go.Pie(
        labels=grp["severity"], values=grp["count"],
        marker=dict(colors=colors, line=dict(color=_BG, width=2)),
        textinfo="percent+label", hole=0.38,
    ))
    fig.update_layout(**_LAYOUT, title="Error Severity Distribution", height=340,
                      legend=dict(bgcolor=_BG, bordercolor=_GRID, borderwidth=1))
    return fig
