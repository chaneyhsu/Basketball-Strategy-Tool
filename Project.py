import streamlit as st
import pandas as pd
import re
from difflib import get_close_matches

@st.cache_data
def load_kenpom_data():
    df = pd.read_csv("/Users/chaney/Desktop/kenpom_all_teams.csv")
    df.columns = (
        df.columns
        .str.encode('ascii', errors='ignore').str.decode('ascii')
        .str.replace(r'\s+', '', regex=True)
        .str.strip()
        .str.lower()
    )
    return df

kenpom_df = load_kenpom_data()

def find_team_row(team_name, df):
    team_col = [col for col in df.columns if "team" in col][0]
    df[team_col] = df[team_col].astype(str).str.strip().str.lower()
    team_input = team_name.strip().lower()

    matches = df[df[team_col].str.contains(team_input, na=False)]
    if matches.empty:
        suggestions = get_close_matches(team_input, df[team_col].tolist(), n=1, cutoff=0.6)
        if suggestions:
            return None, f"Team '{team_name}' not found. Did you mean: {suggestions[0]}?"
        return None, f"Team '{team_name}' not found. Please check spelling."

    if len(matches) > 1:
        st.warning(f"Multiple KenPom matches found for '{team_name}': {list(matches[team_col])}. Using the first match found.")
    return matches.iloc[0], None

def extract_metrics(row):
    try:
        return {
            "Adj Tempo": float(row.get("adjt", "nan")),
            "Adj Offensive Efficiency": float(row.get("ortg", "nan")),
            "Adj Defensive Efficiency": float(row.get("drtg", "nan")),
            "Net Rating": float(row.get("netrtg", "nan")),
            "Luck": float(row.get("luck", "nan")),
            "Strength of Schedule": float(row.get("strengthofschedule", "nan"))
        }
    except:
        return {k: "N/A" for k in [
            "Adj Tempo", "Adj Offensive Efficiency", "Adj Defensive Efficiency", "Net Rating", "Luck", "Strength of Schedule"
        ]}

def compare_teams_metrics(team1_name, team2_name):
    row1, err1 = find_team_row(team1_name, kenpom_df)
    row2, err2 = find_team_row(team2_name, kenpom_df)

    if err1:
        return None, err1
    if err2:
        return None, err2

    team1_stats = extract_metrics(row1)
    team2_stats = extract_metrics(row2)

    data = []
    for metric in team1_stats:
        val1 = team1_stats[metric]
        val2 = team2_stats[metric]
        try:
            diff = round(val1 - val2, 3)
        except:
            diff = "N/A"
        data.append({
            "Metric": metric,
            team1_name.title(): round(val1, 3) if isinstance(val1, float) else "N/A",
            team2_name.title(): round(val2, 3) if isinstance(val2, float) else "N/A",
            "Difference": diff
        })

    return pd.DataFrame(data), None

def classify_tempo_bucket(tempo):
    if tempo < 61:
        return "Very Slow"
    elif 61 <= tempo < 64:
        return "Slow"
    elif 64 <= tempo < 67:
        return "Balanced"
    elif 67 <= tempo < 70:
        return "Fast"
    else:
        return "Very Fast"

def get_coaching_notes(bucket, tempo):
    tempo_profile = f"Tempo Profile: ~{tempo:.1f} possessions/game ({bucket} classification)."
    templates = {
        "Very Slow": """Recommended Coaching Notes:

{tempo_profile}

Offensive Ideas:
- Emphasize extremely patient, deliberate half-court sets.
- Maximize clock to find best shot.
- Prioritize inside-out play and post touches.

Defensive Ideas:
- Prevent all easy transition points.
- Force long, late-clock half-court possessions.
- Mix zone and man to disrupt timing.

Rotation/Personnel Notes:
- Favor size and physicality.
- Use rim protectors and strong rebounders.
- Include disciplined defenders to avoid fouls.
""",
        "Slow": """Recommended Coaching Notes:

{tempo_profile}

Offensive Ideas:
- Prioritize half-court sets with multiple options.
- Use off-ball screening to create high percentage shots.
- Control the pace by avoiding rushed shots.

Defensive Ideas:
- Get back early to stop transition.
- Force them into late-clock decisions.
- Communicate through switches to avoid mismatches.

Rotation/Personnel Notes:
- Favor physical, disciplined players.
- Keep bigs on the floor for rebounding and rim protection.
- Use bench players strategically to maintain defensive intensity.
""",
        "Balanced": """Recommended Coaching Notes:

{tempo_profile}

Offensive Ideas:
- Be flexible between pace options.
- Mix early offense with patient sets.
- Use matchup reads to adjust on the fly.

Defensive Ideas:
- Prepare for pace shifts mid-game.
- Emphasize communication to handle adjustments.
- Force them to settle into uncomfortable rhythm.

Rotation/Personnel Notes:
- Favor versatile players who can handle different tempos.
- Adjust lineups to exploit matchups dynamically.
- Plan substitutions to match opponent's pace.
""",
        "Fast": """Recommended Coaching Notes:

{tempo_profile}

Offensive Ideas:
- Push pace and attack early.
- Use drag screens, transition threes, and rim runs.
- Space the floor to exploit scramble rotations.

Defensive Ideas:
- Selective full-court or 3/4 press to generate turnovers.
- Force quick shots, increase possession count.
- Emphasize gang-rebounding to ignite breaks.

Rotation/Personnel Notes:
- Favor athletic, fast lineups.
- Prioritize ball-handlers and shooters.
- Ready your deep bench for high-tempo rotations.
""",
        "Very Fast": """Recommended Coaching Notes:

{tempo_profile}

Offensive Ideas:
- Prioritize pace and spacing.
- Push the ball in transition at every opportunity.
- Use constant motion to tire them out.

Defensive Ideas:
- Sprint back immediately to stop easy baskets.
- Force them into contested shots in transition.
- Change defensive looks to slow their rhythm.

Rotation/Personnel Notes:
- Emphasize speed and athleticism.
- Plan quick substitutions to maintain pace.
- Use pressing units strategically.
"""
    }
    return templates[bucket].format(tempo_profile=tempo_profile)

def generate_risk_prediction(net_diff, luck_diff, sos_diff, team1, team2):
    messages = []
    score = 0

    if abs(net_diff) < 5:
        messages.append(f"Net Rating gap: {net_diff:.1f} → This game could possibly be close and upset-prone.")
        score += 1
    else:
        messages.append(f"Net Rating gap: {net_diff:.1f} → There is a clear difference in team strength.")

    if abs(luck_diff) > 0.05:
        messages.append(f"Luck differential: {luck_diff:.3f} → One team may be overperforming.")
        score += 1
    else:
        messages.append(f"Luck differential: {luck_diff:.3f} → Fairly stable performance from both teams.")

    if abs(sos_diff) > 1.5:
        messages.append(f"Strength of Schedule difference: {sos_diff:.1f} → One team may have faced tougher competition.")
        score += 1
    else:
        messages.append(f"Strength of Schedule difference: {sos_diff:.1f} → Comparable schedule difficulty.")

    risk_level = "High" if score >= 2 else "Moderate" if score == 1 else "Low"

    adjusted_net1 = (net_diff * 0.85) + (sos_diff * 0.1) - (luck_diff * 0.05)
    predicted_winner = team1 if adjusted_net1 > 0 else team2

    confidence_score = min(99.0, max(50.0, round(abs(adjusted_net1) * 4.5 + 50, 1)))

    upset_risk = risk_level

    messages.append(f"""
Final Prediction:
- Predicted Winner: {predicted_winner.title()}
- Confidence Score: {confidence_score:.1f}%
- Upset Risk Level: {upset_risk}
""")

    return "\n\n".join(messages)

# Streamlit UI
st.title("Basketball Strategy Tools")
st.subheader("Retrieves information from 2025 KenPom to make custom analyses and give suggestions.")

mode = st.selectbox("Choose from the following:", [
    "Team Comparison",
    "Opponent Analysis & Strategy Recommendations",
    "Game Risk & Volatility Estimator"
])

if mode == "Team Comparison":
    col1, col2 = st.columns(2)
    with col1:
        team1 = st.text_input("Enter Your Team Name (exactly as in KenPom)").strip()
    with col2:
        team2 = st.text_input("Enter Opponent Team Name (exactly as in KenPom)").strip()

    if st.button("Compare Teams"):
        if not team1 or not team2:
            st.warning("Please enter both team names.")
        else:
            table, error = compare_teams_metrics(team1, team2)
            if error:
                st.error(error)
            else:
                st.subheader("Team Comparison:")
                st.dataframe(table)

elif mode == "Opponent Analysis & Strategy Recommendations":
    team_input = st.text_input("Enter opponent team name (exactly as in KenPom)").strip()

    if st.button("Generate Game Plan"):
        if not team_input:
            st.warning("Please enter a team name.")
        else:
            row, error = find_team_row(team_input, kenpom_df)
            if error:
                st.error(error)
            else:
                tempo = float(row["adjt"])
                bucket = classify_tempo_bucket(tempo)
                st.success(f"KenPom Adj Tempo: {tempo:.1f} possessions/game")
                st.markdown(get_coaching_notes(bucket, tempo))

elif mode == "Game Risk & Volatility Estimator":
    col1, col2 = st.columns(2)
    with col1:
        team1 = st.text_input("Enter Your Team Name (exactly as in KenPom)").strip()
    with col2:
        team2 = st.text_input("Enter Opponent Team Name (exactly as in KenPom)").strip()

    if st.button("Evaluate Game Risk"):
        if not team1 or not team2:
            st.warning("Please enter both team names.")
        else:
            row1, err1 = find_team_row(team1, kenpom_df)
            row2, err2 = find_team_row(team2, kenpom_df)
            if err1:
                st.error(err1)
            elif err2:
                st.error(err2)
            else:
                net_diff = float(row1["netrtg"]) - float(row2["netrtg"])
                luck_diff = float(row1["luck"]) - float(row2["luck"])
                sos_diff = float(row1["strengthofschedule"]) - float(row2["strengthofschedule"])

                st.subheader("Game Risk Assessment")
                st.markdown(generate_risk_prediction(net_diff, luck_diff, sos_diff, team1, team2))
