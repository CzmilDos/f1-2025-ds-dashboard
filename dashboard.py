import dash
from dash import dcc, html, Input, Output, State, callback, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os
from sklearn.decomposition import PCA
import fastf1
import plotly.io as pio

# Chargement des datasets (modifie le chemin selon ton infra)
DATA_DIR = "data"
df_results = pd.read_parquet(f"{DATA_DIR}/results_2025.parquet")
df_pits = pd.read_parquet(f"{DATA_DIR}/pitstops_2025.parquet")
df_drv_stand = pd.read_parquet(f"{DATA_DIR}/driver_standings_2025.parquet")
df_team_stand = pd.read_parquet(f"{DATA_DIR}/team_standings_2025.parquet")
df_flights = pd.read_parquet(f"{DATA_DIR}/flightlegs_2025.parquet")
df_quali = pd.read_parquet(f"{DATA_DIR}/qualifying_2025.parquet")

# Utilitaires
PILOT_PLACEHOLDER_URL = "https://img.freepik.com/premium-photo/race-car-driver-with-helmet_155807-30671.jpg?w=740" 

def pilot_img_url(row):
    url = row.get("HeadshotUrl")
    if url is None or url == "None" or str(url).strip() == "":  # Gère None, "None" et les strings vides
        return PILOT_PLACEHOLDER_URL
    return url

team_colors = df_results.drop_duplicates("TeamName").set_index("TeamName")["TeamColor"].apply(lambda c: f"#{c}" if not c.startswith("#") else c).to_dict()
pilot_imgs = df_results.set_index("FullName")["HeadshotUrl"].to_dict()
pilot2team = df_results.set_index("FullName")["TeamName"].to_dict()

# 1️⃣ ACCUEIL – Data prep pour la bar race & podium pie
cumul = (
    df_drv_stand
    .sort_values(['FullName', 'round'])
    .groupby(['FullName', 'round'])['Points']
    .sum()
    .groupby(level=0).cumsum()
    .reset_index(name='PointsCum')
)
round_to_gp = df_results.set_index('round')['event'].to_dict()
cumul['event'] = cumul['round'].map(round_to_gp)
team_map = (
    df_results
    .drop_duplicates(subset=['FullName', 'round'])
    .set_index(['FullName', 'round'])[['TeamName', 'TeamColor', 'HeadshotUrl']]
    .to_dict(orient='index')
)
def fix_color(c):
    if isinstance(c, str) and not c.startswith('#'):
        return f'#{c}'
    return c
cumul['TeamName'] = cumul.apply(lambda row: team_map.get((row['FullName'], row['round']), {}).get('TeamName', 'N/A'), axis=1)
cumul['TeamColor'] = cumul.apply(lambda row: fix_color(team_map.get((row['FullName'], row['round']), {}).get('TeamColor', '#cccccc')), axis=1)
cumul['HeadshotUrl'] = cumul.apply(lambda row: team_map.get((row['FullName'], row['round']), {}).get('HeadshotUrl', 'https://media.formula1.com/d_driver_fallback_i'), axis=1)
team_color_map = {team: fix_color(color) for team, color in cumul.groupby('TeamName')['TeamColor'].first().items()}

# Podiums pour pie
podiums = df_results[df_results['Position'] <= 3]
podium_count = podiums.groupby("FullName")["Position"].count().sort_values(ascending=False)
pie_podium = px.pie(
    podium_count, values=podium_count.values, names=podium_count.index,
    title="Répartition des podiums (pilotes)",
    color=podium_count.index,
    color_discrete_map={p: team_colors.get(pilot2team.get(p), '#cccccc') for p in podium_count.index}
)
pie_podium.update_traces(textinfo="percent+label")
pie_podium.update_layout(template="plotly_dark", margin=dict(t=60, l=20, r=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', title_x=0.5)

# KPIs dynamiques
nb_gp = df_results['event'].nunique()
nb_pilotes = df_results['FullName'].nunique()
nb_teams = df_results['TeamName'].nunique()
nb_abandons = (df_results['Status'] != 'Finished').sum()
pct_abandons = nb_abandons / len(df_results) * 100
co2_total = int(df_flights['CO2_tonnes'].sum())
trajets = df_flights.sort_values("CO2_tonnes", ascending=False)
trajet_max = trajets.iloc[0]
trajet_min = trajets.iloc[-1]
best_winner = df_results[df_results['Position'] == 1]['FullName'].value_counts().idxmax()
nb_victoires = df_results[df_results['Position'] == 1]['FullName'].value_counts().max()
best_winner_row = df_results[df_results['FullName'] == best_winner].iloc[0]
best_winner_img = pilot_img_url(best_winner_row)
best_winner_team = best_winner_row['TeamName']  

def load_or_create_figure(path, create_func):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return pio.from_json(f.read())
    fig = create_func()
    with open(path, "w", encoding="utf-8") as f:
        f.write(fig.to_json())
    return fig

# Bar race animation (Accueil)
def bar_race_anim():
    fig = px.bar(
        cumul, 
        x='PointsCum', y='FullName', 
        color='TeamName',
        color_discrete_map=team_color_map,
        orientation='h',
        animation_frame='event',
        range_x=[0, cumul['PointsCum'].max()*1.1],
        title="Classement pilotes (points cumulés) – Animation course par course",
        labels={'PointsCum': 'Points cumulés', 'FullName': 'Pilote', 'event': 'Grand Prix', 'TeamName': 'Écurie'}
    )
    fig.update_layout(
        title_x=0.5,
        height=650, template='plotly_dark',
        xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        barcornerradius=15,
        updatemenus=[{
            "buttons": [
                {
                    "args": [None, {"frame": {"duration": 1200, "redraw": True}, "fromcurrent": True}],
                    "label": "Play",
                    "method": "animate"
                },
                {
                    "args": [[None], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                    "method": "animate"
                }
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 87},
            "showactive": False,
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top"
        }],
        sliders=[{
            "pad": {"b": 10, "t": 60},
            "currentvalue": {"prefix": "Grand Prix : ", "font": {"size": 20}},
            "transition": {"duration": 400},
            "len": 0.9
        }]
    )
    return fig

# Remplacer les appels directs aux fonctions de création de figures lourdes par la version cache
# ACCUEIL : bar_race_anim et pie_podium
bar_race_path = os.path.join("data", "fig_bar_race.json")
pie_podium_path = os.path.join("data", "fig_pie_podium.json")
fig_bar_race = load_or_create_figure(bar_race_path, bar_race_anim)
fig_pie_podium = load_or_create_figure(pie_podium_path, lambda: pie_podium)

def home_layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col(html.H2("🏁🚥 Dashboard F1 – Saison 2025", className="mb-3 text-center"), width=12, style={"marginBottom": "-10px", "marginTop": "-15px"})
        ]),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Grands prix"),
                dbc.CardBody(html.H4(nb_gp, className="card-title"))
            ], className="mb-2 bg-gradient-primary shadow kpi-glass kpi-fadein"), width=2),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Pilotes classés"),
                dbc.CardBody(html.H4(nb_pilotes, className="card-title"))
            ], className="mb-2 bg-gradient-info shadow kpi-glass kpi-fadein"), width=2),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Écuries"),
                dbc.CardBody(html.H4(nb_teams, className="card-title"))
            ], className="mb-2 bg-gradient-secondary shadow kpi-glass kpi-fadein"), width=2),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Abandons (%)"),
                dbc.CardBody(html.H4(f"{pct_abandons:.1f} %", className="card-title"))
            ], className="mb-2 bg-gradient-danger shadow kpi-glass kpi-fadein"), width=2),
            dbc.Col(dbc.Card([
                dbc.CardHeader("CO₂ logistique total (t)"),
                dbc.CardBody(html.H4(f"{co2_total}", className="card-title"))
            ], className="mb-2 bg-gradient-dark shadow kpi-glass kpi-fadein"), width=2),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Roi du GP"),
                dbc.CardBody(
                    html.Div([
                        html.Span([
                            html.Img(
                                src=best_winner_img,
                                height="38px",
                                style={
                                    "borderRadius": "19px",
                                    "verticalAlign": "middle",
                                    "marginRight": "8px",
                                    "border": f"2px solid {team_colors.get(best_winner_team, '#aaa')}"
                                }
                            ) if best_winner_img else "",
                            html.Span(
                                f"{best_winner}",
                                style={
                                    "verticalAlign": "middle",
                                    "fontWeight": "bold",
                                    "fontSize": "1.05rem",
                                    "color": team_colors.get(best_winner_team, "#ffa")
                                }
                            )
                        ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "gap": "6px", "lineHeight": "1.1", "marginBottom": "2px"}),
                        html.Div(
                            f"{best_winner_team}",
                            className="small mb-0 text-muted",
                            style={"lineHeight": "1", "marginBottom": "2px"}
                        ),
                        html.Div(
                            f"{nb_victoires} victoires",
                            className="small text-muted",
                            style={"lineHeight": "2", "marginBottom": "-15px"}
                        )
                    ], style={"padding": "0", "margin": "0"})
                ),
            ], className="mb-2 bg-gradient-warning shadow kpi-glass kpi-fadein"), width=2)
        ], className="text-center"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_bar_race, className="styled-card fadein-graph"), width=8),
            dbc.Col([
                dcc.Graph(figure=fig_pie_podium)
            ], width=4, style={"marginTop": "6.5%"}, className="styled-card fadein-graph")
        ])
    ], fluid=True)

# 2️⃣ STRATEGIE & CHAOS (avec heatmap custom + bar pneus par GP)
# Variables globales nécessaires au callback
pits_valid = df_pits.dropna(subset=['CompoundIn', 'CompoundOut', 'event'])
gp_list = df_results.sort_values("round")["event"].unique().tolist()
compound_colors = {
    'SOFT': '#FF2B2B',         # Rouge
    'MEDIUM': '#FFD12E',       # Jaune
    'HARD': '#FFFFFF',         # Blanc
    'INTERMEDIATE': '#43B047', # Vert
    'WET': '#0067AD',          # Bleu
    'SUPER_SOFT': '#FF6F61',   # Rose
    'ULTRA_SOFT': '#A020F0',   # Violet,
}

fastf1.Cache.enable_cache('.cache_f1')

def strategie_layout():
    # --- 1. Graphique temps au tour top 5 dernier GP ---
    fig_lap_path = os.path.join("data", "fig_lap_lastgp.json")
    fig_lap = None

    if os.path.exists(fig_lap_path):
        # Chargement rapide du graphique pré-calculé
        with open(fig_lap_path, "r", encoding="utf-8") as f:
            fig_lap = pio.from_json(f.read())
    else:
        # Génération et sauvegarde si besoin
        last_gp_round = df_results['round'].max()
        last_gp_name = df_results[df_results['round'] == last_gp_round]['event'].iloc[0]
        df_last_gp = df_results[df_results['round'] == last_gp_round].sort_values('Position')
        drivers = df_last_gp['Abbreviation'].head(5).tolist()
        abbr_to_full = df_last_gp.set_index('Abbreviation')['FullName'].to_dict()
        driver_to_team = df_last_gp.set_index('Abbreviation')['TeamName'].to_dict()
        team_colors = df_results.drop_duplicates("TeamName").set_index("TeamName")["TeamColor"].apply(
            lambda c: f"#{c}" if not str(c).startswith("#") else str(c)).to_dict()
        import sys, contextlib
        from io import StringIO
        with contextlib.redirect_stdout(StringIO()), contextlib.redirect_stderr(StringIO()):
            session = fastf1.get_session(2025, last_gp_name, 'R')
            session.load()
        fig_lap = go.Figure()
        for driver in drivers:
            team = driver_to_team[driver]
            full_name = abbr_to_full.get(driver, driver)
            laps = session.laps.pick_drivers(driver).pick_quicklaps()
            if laps.empty:
                continue
            fig_lap.add_trace(go.Scatter(
                x=laps['LapNumber'],
                y=laps['LapTime'].dt.total_seconds(),
                mode='lines+markers',
                name=full_name,
                line=dict(color=team_colors.get(team, "#888"), width=3),
                marker=dict(size=6, symbol="circle"),
                hovertemplate=(
                    f"<b>Pilote : {full_name}</b><br>"
                    f"Écurie : {team}<br>"
                    "Tour : %{x}<br>"
                    "Temps : %{y:.3f} s"
                ),
            ))
        fig_lap.update_layout(
            title=f"⏱️ Temps au tour — Top 5 pilotes — Dernier GP ({last_gp_name})",
            title_x=0.5,
            xaxis_title="Numéro de tour",
            yaxis_title="Temps au tour (s)",
            legend_title="Pilote",
            template="plotly_dark",
            height=450,
            font=dict(family="Montserrat, Arial", size=15),
            margin=dict(l=60, r=40, t=60, b=40),
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=False, zeroline=False)
        )
        # Sauvegarde pour les prochains lancements
        with open(fig_lap_path, "w", encoding="utf-8") as f:
            f.write(fig_lap.to_json())

    # --- Heatmap interactif (graphique) ---
    df_results['delta'] = df_results['GridPosition'] - df_results['Position']
    gp_order = df_results.sort_values("round")["event"].unique().tolist()
    pilot_order = df_results.groupby("FullName")["Position"].sum().sort_values().index.tolist()
    pivot = df_results.pivot_table(index='FullName', columns='event', values='delta').reindex(index=pilot_order, columns=gp_order)
    gridpos = df_results.pivot_table(index='FullName', columns='event', values='GridPosition').reindex(index=pilot_order, columns=gp_order)
    arrpos  = df_results.pivot_table(index='FullName', columns='event', values='Position').reindex(index=pilot_order, columns=gp_order)
    hovertext = np.empty(pivot.shape, dtype=object)
    textvals = np.empty(pivot.shape, dtype=object)
    for i, name in enumerate(pivot.index):
        for j, ev in enumerate(pivot.columns):
            val = pivot.iloc[i, j]
            grid = gridpos.iloc[i, j]
            arr  = arrpos.iloc[i, j]
            sign = "+" if pd.notna(val) and val > 0 else ""
            textvals[i, j] = f"{sign}{int(val) if pd.notna(val) else ''}"
            hovertext[i, j] = (
                f"Grand Prix : <b>{ev}</b><br>"
                f"Pilote : <b>{name}</b><br>"
                f"Positions gagnées/perdues : <b>{sign}{val if pd.notna(val) else 'N/A'}</b><br>"
                f"Position départ : <b>{int(grid) if pd.notna(grid) else 'N/A'}</b><br>"
                f"Position arrivée : <b>{int(arr) if pd.notna(arr) else 'N/A'}</b>"
            )
    fig_heatmap = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            customdata=hovertext,
            text=textvals,
            texttemplate="%{text}",
            hovertemplate='%{customdata}<extra></extra>',
            colorscale='Viridis',
            colorbar=dict(title="Δ Positions", thickness=15),
            reversescale=False, zmin=-12, zmax=12
        )
    )
    fig_heatmap.update_layout(
        title="<b>🏁 Progression sur la grille : du départ à l'arrivée par Grand Prix</b>",
        title_x=0.5,
        template="plotly_dark",
        font=dict(family="Montserrat, Arial", color="#F2F2F2"),
        height=550,
        margin=dict(l=80, r=20, t=50, b=20),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=False)
    )

    # --- Bar chart abandons (graphique) ---
    abandons = df_results[df_results['Status'] != 'Finished'].groupby('event')['FullName'].count().reindex(gp_order, fill_value=0)
    max_abd = abandons.max()
    colors_abd = ['#43B047' if v <= 2 else '#FFD12E' if v <= 5 else '#FF2B2B' for v in abandons.values]
    fig_abandon = go.Figure()
    fig_abandon.add_trace(go.Bar(
        x=abandons.index, y=abandons.values, marker_color=colors_abd, text=abandons.values,
        textposition='outside', textfont=dict(size=14, color='#fff'),
        hovertemplate='Grand Prix : %{x}<br>Abandons : %{y}<extra></extra>', name="Abandons"
    ))
    fig_abandon.update_layout(
        template='plotly_dark', height=320,
        title=dict(text="<b>💥 Moments de Chaos : Abandons par Course</b>", x=0.5, font=dict(size=20)),
        margin=dict(l=30, r=30, t=80, b=30),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Montserrat, Arial", color="#F2F2F2"),
        yaxis=dict(showgrid=False, zeroline=False, title="Nb abandons", range=[0, max_abd + 3]),
        showlegend=False,
        barcornerradius=8,
        annotations=[
            dict(
                x=0.5, y=1.05, xref='paper', yref='paper',
                text=f"Course la plus chaotique : <span style='color:#FF2B2B;font-weight:bold'>{abandons.idxmax()} ({max_abd} abandons)</span>",
                showarrow=False, font=dict(size=15, color="#f2f2f2"), align="center"
            )
        ]
    )
    # --- Layout final de la page ---
    layout = dbc.Container([
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_lap, className="styled-card fadein-graph"), width=12)
        ], className="mb-3", style={"marginTop": "-30px"}),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_heatmap, id="fig-heatmap", config={"displayModeBar": False}, className="fadein-graph"), className="styled-card"), width=7),
            dbc.Col(dbc.Card([
                html.H5("🔧🛞 Stratégie de Pneus par GP", className="text-center mb-3"),
                dcc.Dropdown(
                    id="dropdown-gp",
                    options=[{"label": gp, "value": gp} for gp in gp_list],
                    value=gp_list[0], clearable=False, className="custom-dropdown"
                ),
                dcc.Graph(id="fig-pit-gp", config={"displayModeBar": False}, style={"height": "460px"}, className="fadein-graph")
            ], className="styled-card"), width=5)
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_abandon, id="fig-abandon", config={"displayModeBar": False}, className="fadein-graph"), className="styled-card"), width=12)
        ], className="mb-3"),
    ], fluid=True)
    return layout

# Callback pour le graphique des pneus (inchangé, mais le graphique s'adaptera au nouveau style de la carte)
@callback(
    Output("fig-pit-gp", "figure"),
    Input("dropdown-gp", "value")
)
def update_pit_plot(gp):
    data = pits_valid[pits_valid["event"] == gp]
    if data.empty:
        # Affiche un graphique vide si pas de données
        fig_pit = go.Figure()
        fig_pit.update_layout(
            title=f"Aucune donnée d'arrêts pour {gp}",
            template='plotly_dark',
            height=550
        )
        return fig_pit
    bar_data = data.groupby(['TeamName', 'CompoundIn']).size().reset_index(name='NbArrets')
    bar_data["TeamTotal"] = bar_data.groupby("TeamName")["NbArrets"].transform("sum")
    bar_data = bar_data.sort_values(["TeamTotal", "TeamName"], ascending=[False, True])
    fig_pit = px.bar(
        bar_data, x='TeamName', y='NbArrets', color='CompoundIn',
        title=f"Arrêts par Écurie – {gp}",
        labels={'NbArrets': "Nombre d'arrêts", 'TeamName': 'Écurie', 'CompoundIn': 'Pneu monté'},
        color_discrete_map=compound_colors
    )
    fig_pit.update_layout(
        barmode='stack', template='plotly_dark', height=450,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Montserrat, Arial", color="#F2F2F2"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
        barcornerradius=8
    )

    return fig_pit

# -----------  DUELS INTRA-ECURIE ------------------
def duels_layout():
    teams = sorted(df_results["TeamName"].unique())
    return dbc.Container([
        dbc.Row(dbc.Col(html.H1("⚔️ Duels des Coéquipiers", className="text-center text-light my-4"), width=12, style={"marginTop": "-50px"})),
        dbc.Row(dbc.Col(dcc.Dropdown(
            id="select-team",
            options=[{"label": t, "value": t} for t in teams],
            value=teams[0],
            clearable=False,
            className="custom-dropdown"
        ), width=6, className="mx-auto mb-4")),
        dbc.Row([
            dbc.Col(id="duel-col-1", width=4),
            dbc.Col(id="duel-col-2", width=4),
            dbc.Col(id="duel-col-3", width=4),
        ], className="g-4 mb-4"),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(id="fig-bar-duel", className="fadein-graph"), className="styled-card"), width=6),
            dbc.Col(dbc.Card(dcc.Graph(id="fig-bump-duel", className="fadein-graph"), className="styled-card"), width=6),
        ], className="g-4")
    ], fluid=True)

@callback(
    [Output("fig-bar-duel", "figure"),
     Output("fig-bump-duel", "figure"),
     Output("duel-col-1", "children"),
     Output("duel-col-2", "children"),
     Output("duel-col-3", "children")],
    [Input("select-team", "value")]
)
def update_duel(team):
    sub = df_results[df_results["TeamName"] == team]
    score = sub.groupby('FullName')['Points'].sum().sort_values(ascending=False)
    pilotes = score.index.tolist()

    # --- Graphiques (logique commune) ---
    bar = px.bar(
        score, x=score.values, y=score.index, orientation='h',
        color_discrete_sequence=[team_colors.get(team, "#fff")]*len(pilotes),
        text=score.values, labels={'y': 'Pilote', 'x': 'Points'},
        title=f"<b>Points par Pilote – {team}</b>"
    )
    bar.update_layout(
        template="plotly_dark", showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False, autorange="reversed"),
        height=350, uniformtext_minsize=8, uniformtext_mode='hide', title_x=0.5
    )
    bar.update_traces(marker_line_width=0, marker_cornerradius=8, textposition='outside')

    cumul = (df_drv_stand[df_drv_stand["TeamName"] == team].sort_values(['FullName', 'round'])
             .groupby(['FullName', 'round'])['Points'].sum().groupby(level=0).cumsum().reset_index(name='PointsCum'))
    cumul['event'] = cumul['round'].map(df_results.set_index('round')['event'].to_dict())
    pilot_color_map = {p: c for p, c in zip(pilotes, px.colors.qualitative.Plotly)}
    bump = px.line(
        cumul, x='event', y='PointsCum', color='FullName', markers=True,
        title=f"<b>Progression Saison – {team}</b>", 
        labels={'event': 'Grand Prix', 'PointsCum': 'Points Cumulés', 'FullName': 'Pilote'},
        color_discrete_map=pilot_color_map
    )
    bump.update_layout(
        template="plotly_dark", height=350, paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False), 
        yaxis=dict(showgrid=False, zeroline=False), title_x=0.5
    )

    # --- Cartes (logique conditionnelle) ---
    def create_driver_card_content(p_name, p_score):
        row = sub[sub["FullName"] == p_name].iloc[0]
        url = pilot_img_url(row)
        return [
            html.Img(src=url, className="mb-3 mx-auto d-block", style={
                "width": "120px", "height": "120px", "borderRadius": "50%",
                "objectFit": "cover", "border": f"5px solid {team_colors.get(team, '#fff')}"
            }),
            html.H4(p_name, className="mb-2"),
            html.Div([
                html.Span("Points", className="text-muted d-block"),
                html.H3(p_score, className="font-weight-bold")
            ])
        ]

    if len(pilotes) == 2:
        p1, p2 = pilotes[0], pilotes[1]
        h2h_races = sub.pivot(index='event', columns='FullName', values='Position').dropna()
        p1_wins = (h2h_races[p1] < h2h_races[p2]).sum()
        p2_wins = (h2h_races[p2] < h2h_races[p1]).sum()

        col1 = dbc.Card(create_driver_card_content(p1, score[p1]), className="styled-card text-center p-3 h-100")
        col3 = dbc.Card(create_driver_card_content(p2, score[p2]), className="styled-card text-center p-3 h-100")
        col2 = dbc.Card([
            html.H5("Face-à-Face en Course", className="mb-3"),
            html.H1(f"{p1_wins} - {p2_wins}", className="my-auto display-4")
        ], className="styled-card text-center p-3 h-100 d-flex flex-column justify-content-center")
        
        return bar, bump, col1, col2, col3
    
    elif len(pilotes) >= 3:
        cols = [dbc.Card(create_driver_card_content(p, score[p]), className="styled-card text-center p-3 h-100") for p in pilotes[:3]]
        while len(cols) < 3:
            cols.append(None)
        return bar, bump, cols[0], cols[1], cols[2]

    else: # 0 ou 1 pilote
        empty_fig = go.Figure().update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', annotations=[dict(text="Pas assez de données", showarrow=False)])
        return empty_fig, empty_fig, None, None, None

# -----------  RECORDS / STORYTELLING ------------------
# Cache pour chaque figure
records_figs = {
    'comeback': os.path.join("data", "fig_records_comeback.json"),
    'streak': os.path.join("data", "fig_records_streak.json"),
    'dnf': os.path.join("data", "fig_records_dnf.json"),
    'podiums': os.path.join("data", "fig_records_podiums.json"),
}
def records_layout():
    def create_comeback():
        df_results['comeback'] = df_results['GridPosition'] - df_results['Position']
        best_comebacks = df_results.sort_values('comeback', ascending=False).head(10)
        fig = px.bar(
            best_comebacks[::-1], x='comeback', y='FullName', color='TeamName', color_discrete_map=team_colors,
            orientation='h', text='event', hover_data=['event', 'GridPosition', 'Position'],
            labels={'comeback': 'Positions Gagnées', 'FullName': 'Pilote'},
            title="🏆 Top 10 des Plus Grandes Remontées"
        )
        fig.update_layout(
            template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True,
            xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False),
            barcornerradius=8, title_x=0.5
        )
        return fig
    def create_streak():
        df_results_sorted = df_results.sort_values(['FullName', 'round'])
        df_results_sorted['has_points'] = df_results_sorted['Points'] > 0
        streaks = {}
        for pilot in df_results_sorted['FullName'].unique():
            s = df_results_sorted[df_results_sorted['FullName'] == pilot]['has_points'].values
            max_streak = 0
            current = 0
            for v in s:
                if v:
                    current += 1
                    max_streak = max(max_streak, current)
                else:
                    current = 0
            streaks[pilot] = max_streak
        streaks = pd.Series(streaks).sort_values(ascending=False).head(10)
        fig = px.bar(
            streaks[::-1], x=streaks.values, y=streaks.index,
            color=streaks.index, color_discrete_sequence=px.colors.sequential.Viridis,
            orientation='h', title="📈 Plus Longues Séries de Points (Top 10)",
            labels={'y': 'Pilote', 'x': 'Nombre de GP consécutifs'}
        )
        fig.update_layout(
            template="plotly_dark", height=400, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False),
            barcornerradius=8, title_x=0.5
        )
        return fig
    def create_dnf():
        dnf = df_results[df_results["Status"].isin(["Retired", "Disqualified"])]
        dnf_pilots = dnf["FullName"].value_counts().head(8)
        fig = px.bar(
            dnf_pilots[::-1], x=dnf_pilots.values, y=dnf_pilots.index,
            color=dnf_pilots.index, color_discrete_sequence=px.colors.sequential.OrRd,
            orientation='h', title="💥 Pilotes avec le Plus d'Abandons",
            labels={'y': 'Pilote', 'x': "Nombre d'abandons"}
        )
        fig.update_layout(
            template="plotly_dark", height=400, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False),
            barcornerradius=8, title_x=0.5
        )
        return fig
    def create_podiums():
        podiums = df_results[df_results['Position'] <= 3]
        podium_count = podiums.groupby("FullName")["Position"].count().sort_values(ascending=False).head(10)
        fig = px.bar(
            podium_count[::-1], x=podium_count.values, y=podium_count.index,
            color=podium_count.index,
            color_discrete_map={p: team_colors.get(pilot2team.get(p), "#aaa") for p in podium_count.index},
            orientation='h', title="🏅 Top 10 des Pilotes par Nombre de Podiums",
            labels={'y': 'Pilote', 'x': 'Nombre de Podiums'}
        )
        fig.update_layout(
            template="plotly_dark", height=400, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False),
            barcornerradius=8, title_x=0.5
        )
        return fig
    fig_comeback = load_or_create_figure(records_figs['comeback'], create_comeback)
    fig_streak = load_or_create_figure(records_figs['streak'], create_streak)
    fig_dnf = load_or_create_figure(records_figs['dnf'], create_dnf)
    fig_podiums = load_or_create_figure(records_figs['podiums'], create_podiums)
    return dbc.Container([
        dbc.Row(dbc.Col(html.H1("🏆 Les Super-records de la saison", className="text-center text-light my-4"), width=12, style={"marginTop": "-50px"})),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_comeback, className="fadein-graph"), className="styled-card"), width=6),
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_streak, className="fadein-graph"), className="styled-card"), width=6),
        ], className="g-4 mb-4"),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_dnf, className="fadein-graph"), className="styled-card"), width=6),
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_podiums, className="fadein-graph"), className="styled-card"), width=6),
        ], className="g-4")
    ], fluid=True)

# -----------  EMPREINTE CARBONE ------------------
co2_fig_path = os.path.join("data", "fig_co2.json")
def create_co2_fig():
    df_flights['segment'] = df_flights['event_from'] + " → " + df_flights['event_to']
    fig = px.bar(
        df_flights.sort_values('CO2_tonnes'),
        x='CO2_tonnes', y='segment',
        color='CO2_tonnes', color_continuous_scale='OrRd',
        orientation='h',
        labels={'CO2_tonnes': "Tonnes CO₂", 'segment': "Trajet"},
        title="Emissions CO₂ logistique par segment F1 (t·CO₂)"
    )
    fig.update_traces(
        marker_line_width=0,
        marker_cornerradius=8,
        hovertemplate='<b>%{y}</b><br>CO₂: %{x:.0f} t<extra></extra>'
    )
    fig.update_layout(
        height=600, margin=dict(l=150, t=50, b=40),
        coloraxis_showscale=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, title_font=dict(size=18), tickfont=dict(size=15)),
        yaxis=dict(showgrid=False, title_font=dict(size=18), tickfont=dict(size=15)),
        font=dict(size=17, color="#fff"),
        transition={'duration': 900, 'easing': 'cubic-in-out'},
        title_x=0.5
    )
    return fig
fig_co2 = load_or_create_figure(co2_fig_path, create_co2_fig)

def co2_layout():
    # S'assure que la colonne segment existe même si le graphique est chargé depuis le cache
    if "segment" not in df_flights.columns:
        df_flights['segment'] = df_flights['event_from'] + " → " + df_flights['event_to']
    total_co2 = int(df_flights["CO2_tonnes"].sum())
    max_leg = df_flights.sort_values("CO2_tonnes", ascending=False).iloc[0]
    min_leg = df_flights.sort_values("CO2_tonnes", ascending=True).iloc[0]
    return dbc.Container([
        dbc.Row(dbc.Col(html.H1("🌍 Empreinte Carbone de la Saison", className="text-center text-light my-4"), width=12, style={"marginTop": "-50px"})),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_co2, config={'displayModeBar': False}), className="styled-card fadein-graph"), width=8),
            dbc.Col([
                html.H5("KPI Empreinte CO₂", className="mb-3"),
                dbc.Card([
                    dbc.CardHeader("CO₂ total (t)"),
                    dbc.CardBody(html.H4(f"{total_co2:.0f}", className="card-title"))
                ], className="mb-2 kpi-glass kpi-fadein"),
                dbc.Card([
                    dbc.CardHeader("Trajet le + polluant"),
                    dbc.CardBody(html.H6(f"{max_leg['segment']}", className="card-title"), style={"fontSize": "1.2rem"}),
                    dbc.CardBody(html.H6(f"{max_leg['CO2_tonnes']:.0f} t", style={"color": "#FF5733"})),
                ], className="mb-2 kpi-glass kpi-fadein"),
                dbc.Card([
                    dbc.CardHeader("Trajet le - polluant"),
                    dbc.CardBody(html.H6(f"{min_leg['segment']}", className="card-title"), style={"fontSize": "1.2rem"}),
                    dbc.CardBody(html.H6(f"{min_leg['CO2_tonnes']:.0f} t", style={"color": "#43B047"})),
                ], className="kpi-glass kpi-fadein"),
            ], width=3, className="text-center")
        ])
    ], fluid=True)

# -----------  EXPLORER AVANCÉ ------------------
explorer_figs = {
    'corr': os.path.join("data", "fig_explorer_corr.json"),
    'scatter': os.path.join("data", "fig_explorer_scatter.json"),
    'outlier': os.path.join("data", "fig_explorer_outlier.json"),
    'pca': os.path.join("data", "fig_explorer_pca.json"),
}
def explorer_layout():
    def create_corr():
        numerics = df_results[["GridPosition", "Position", "Points"]].copy()
        fig = px.imshow(
            numerics.corr(), text_auto=True, color_continuous_scale="Picnic",
            title="Matrice de Corrélation"
        )
        fig.update_traces(xgap=3, ygap=3)
        fig.update_layout(height=400, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=40, r=40, t=80, b=40), title_x=0.5)
        fig.update_layout(xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False))
        return fig
    def create_scatter():
        fig = px.scatter(
            df_results, x="GridPosition", y="Position", color="TeamName",
            size="Points", hover_name="FullName", hover_data=['event'],
            labels={'GridPosition': "Position de Départ", 'Position': "Position d'Arrivée"},
            title="Départ vs. Arrivée (Taille = Points)"
        )
        fig.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', title_x=0.5)
        fig.update_layout(xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False))
        return fig
    def create_outlier():
        df_results['abs_delta'] = np.abs(df_results['GridPosition'] - df_results['Position'])
        outliers = df_results.sort_values('abs_delta', ascending=False).head(10)
        fig = px.bar(
            outliers[::-1], x="abs_delta", y="FullName",
            color="TeamName", orientation='h', text="event",
            hover_data=["event", "GridPosition", "Position"],
            color_discrete_map=team_colors,
            labels={'abs_delta': 'Écart de Positions (Absolu)', 'FullName': 'Pilote', 'TeamName': 'Écurie'},
            title="Top 10 des Plus Grands Écarts Grille/Arrivée"
        )
        fig.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True, barcornerradius=8, title_x=0.5)
        fig.update_layout(xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False))
        return fig
    def create_pca():
        feats = df_results[["GridPosition", "Position", "Points"]].fillna(0)
        pca = PCA(n_components=2)
        pca_vals = pca.fit_transform(feats)
        df_pca = pd.DataFrame(pca_vals, columns=["PC1", "PC2"])
        df_pca["TeamName"] = df_results["TeamName"]
        df_pca["FullName"] = df_results["FullName"]
        df_pca["event"] = df_results["event"]
        fig = px.scatter(
            df_pca, x="PC1", y="PC2", color="TeamName", hover_data=["FullName", "event"],
            title="Projection PCA des Performances de Course",
            color_discrete_map=team_colors
        )
        fig.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', title_x=0.5)
        fig.update_layout(xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False))
        return fig
    fig_corr = load_or_create_figure(explorer_figs['corr'], create_corr)
    fig_scatter = load_or_create_figure(explorer_figs['scatter'], create_scatter)
    fig_outlier = load_or_create_figure(explorer_figs['outlier'], create_outlier)
    fig_pca = load_or_create_figure(explorer_figs['pca'], create_pca)
    return dbc.Container([
        dbc.Row(dbc.Col(html.H1("🔬 F1 Insights Playground", className="text-center text-light my-4"), width=12, style={"marginTop": "-50px"})),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_corr), className="styled-card fadein-graph"), width=6),
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_scatter, className="fadein-graph"), className="styled-card"), width=6),
        ], className="g-4 mb-4"),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_outlier, className="fadein-graph"), className="styled-card"), width=6),
            dbc.Col(dbc.Card(dcc.Graph(figure=fig_pca, className="fadein-graph"), className="styled-card"), width=6),
        ], className="g-4"),
    ], fluid=True)

# -----------  ROUTING ---------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], suppress_callback_exceptions=True)
server = app.server

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Accueil", href="/", active="exact")),
        dbc.NavItem(dbc.NavLink("Stratégie & Chaos", href="/strategie", active="exact")),
        dbc.NavItem(dbc.NavLink("Duels intra-écurie", href="/duels", active="exact")),
        dbc.NavItem(dbc.NavLink("Records", href="/records", active="exact")),
        dbc.NavItem(dbc.NavLink("Empreinte carbone", href="/co2", active="exact")),
        dbc.NavItem(dbc.NavLink("Explorer", href="/explorer", active="exact")),
    ],
    brand="🏎️💨 F1 Data Science – Ultimate Dashboard",
    color=None, # La couleur est gérée par la classe CSS
    dark=True,
    className="navbar-glass shadow-lg" # Nouvelle classe
)

app.layout = html.Div(id='main-container', children=[
    dcc.Location(id="url"),
    navbar,
    html.Div(id="page-content", className="mt-4 p-4") # Marge pour le contenu sous la navbar
])

@app.callback(
    [Output("page-content", "children"), Output("main-container", "className")],
    [Input("url", "pathname")]
)
def display_page(pathname):
    if pathname == "/strategie":
        return strategie_layout(), "bg-strategie"
    elif pathname == "/duels":
        return duels_layout(), "bg-duels"
    elif pathname == "/records":
        return records_layout(), "bg-records"
    elif pathname == "/co2":
        return co2_layout(), "bg-co2"
    elif pathname == "/explorer":
        return explorer_layout(), "bg-explorer"
    # ... etc
    else: # Home
        return home_layout(), "bg-accueil"

if __name__ == "__main__":
    app.run(debug=True)