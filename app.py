import json
import random
import uuid
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st

APP_TITLE = "SwingForm Range Tracker"
DATA_DIR = Path(__file__).parent
SETTINGS_FILE = DATA_DIR / "swingform_settings.json"
SESSIONS_FILE = DATA_DIR / "swingform_sessions.csv"
SHOTS_FILE = DATA_DIR / "swingform_shots.csv"

DEFAULT_CLUBS = []

CLUB_TYPE_OPTIONS = [
    "Driver", "3W", "5W", "7W",
    "3H", "4H", "5H",
    "3i", "4i", "5i", "6i", "7i", "8i", "9i",
    "PW", "GW", "SW", "LW"
]


def ensure_csv_files():
    if not SESSIONS_FILE.exists():
        pd.DataFrame(columns=[
            "session_id", "session_date", "range_name", "player_name",
            "start_time", "finish_time", "duration_minutes",
            "selected_clubs_json", "total_hits", "total_misses",
            "total_score", "overall_accuracy"
        ]).to_csv(SESSIONS_FILE, index=False)

    if not SHOTS_FILE.exists():
        pd.DataFrame(columns=[
            "session_id", "session_date", "range_name", "player_name",
            "round_no", "shot_in_round", "total_shot_no",
            "club_name", "club_type", "target_type", "result", "score"
        ]).to_csv(SHOTS_FILE, index=False)



def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "clubs" not in data or not isinstance(data["clubs"], list):
                data["clubs"] = DEFAULT_CLUBS.copy()
            return data
        except Exception:
            pass

    return {
        "player_name": "",
        "home_range": "",
        "clubs": DEFAULT_CLUBS.copy(),
    }



def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)



def load_sessions_df():
    ensure_csv_files()
    try:
        return pd.read_csv(SESSIONS_FILE)
    except Exception:
        return pd.DataFrame()



def load_shots_df():
    ensure_csv_files()
    try:
        return pd.read_csv(SHOTS_FILE)
    except Exception:
        return pd.DataFrame()



def append_session_row(row):
    ensure_csv_files()
    df = pd.read_csv(SESSIONS_FILE)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(SESSIONS_FILE, index=False)



def append_shot_rows(rows):
    ensure_csv_files()
    df = pd.read_csv(SHOTS_FILE)
    df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    df.to_csv(SHOTS_FILE, index=False)



def club_target(club_type: str) -> str:
    ctype = str(club_type).strip().lower()
    if ctype == "driver" or ctype.endswith("w"):
        return "Fairway"
    return "Green"



def build_session_plan(selected_clubs):
    rounds = []
    for round_no in range(1, 7):
        clubs_this_round = selected_clubs.copy()
        random.shuffle(clubs_this_round)
        for shot_idx, club in enumerate(clubs_this_round, start=1):
            rounds.append({
                "round_no": round_no,
                "shot_in_round": shot_idx,
                "club_name": club["club_name"],
                "club_type": club["club_type"],
                "target_type": club_target(club["club_type"]),
            })
    return rounds



def start_new_session(player_name, session_date, range_name, bag_clubs):
    selected_clubs = random.sample(bag_clubs, 8)
    session_plan = build_session_plan(selected_clubs)
    st.session_state.active_session = {
        "session_id": str(uuid.uuid4()),
        "player_name": player_name,
        "session_date": str(session_date),
        "range_name": range_name,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "finish_time": None,
        "selected_clubs": selected_clubs,
        "session_plan": session_plan,
        "current_index": 0,
        "results": [],
        "saved": False,
    }



def get_active_session():
    return st.session_state.get("active_session")



def clear_active_session():
    if "active_session" in st.session_state:
        del st.session_state["active_session"]
    if "shot_choice" in st.session_state:
        del st.session_state["shot_choice"]



def record_shot(choice):
    sess = get_active_session()
    idx = sess["current_index"]
    shot = sess["session_plan"][idx]
    score = 1 if choice == "HIT" else 0

    sess["results"].append({
        "session_id": sess["session_id"],
        "session_date": sess["session_date"],
        "range_name": sess["range_name"],
        "player_name": sess["player_name"],
        "owner_email": current_user_email(),
        "round_no": shot["round_no"],
        "shot_in_round": shot["shot_in_round"],
        "total_shot_no": idx + 1,
        "club_name": shot["club_name"],
        "club_type": shot["club_type"],
        "target_type": shot["target_type"],
        "result": choice,
        "score": score,
    })

    sess["current_index"] += 1

    if sess["current_index"] >= len(sess["session_plan"]):
        sess["finish_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def session_finished():
    sess = get_active_session()
    return bool(sess and sess["current_index"] >= len(sess["session_plan"]))



def session_results_df():
    sess = get_active_session()
    if not sess or not sess["results"]:
        return pd.DataFrame()
    return pd.DataFrame(sess["results"])



def save_active_session_to_files():
    sess = get_active_session()
    if not sess or sess["saved"]:
        return

    results_df = session_results_df()
    if results_df.empty:
        return

    start_dt = datetime.strptime(sess["start_time"], "%Y-%m-%d %H:%M:%S")
    finish_dt = datetime.strptime(sess["finish_time"], "%Y-%m-%d %H:%M:%S")
    duration_minutes = round((finish_dt - start_dt).total_seconds() / 60, 2)

    total_hits = int(results_df["score"].sum())
    total_shots = len(results_df)
    total_misses = total_shots - total_hits
    overall_accuracy = round((total_hits / total_shots) * 100, 2) if total_shots else 0.0

    session_row = {
        "session_id": sess["session_id"],
        "session_date": sess["session_date"],
        "range_name": sess["range_name"],
        "player_name": sess["player_name"],
        "owner_email": current_user_email(),
        "start_time": sess["start_time"],
        "finish_time": sess["finish_time"],
        "duration_minutes": duration_minutes,
        "selected_clubs_json": json.dumps(sess["selected_clubs"]),
        "total_hits": total_hits,
        "total_misses": total_misses,
        "total_score": total_hits,
        "overall_accuracy": overall_accuracy,
    }

    append_session_row(session_row)
    append_shot_rows(sess["results"])
    sess["saved"] = True



def make_club_summary(results_df):
    if results_df.empty:
        return pd.DataFrame()

    grp = results_df.groupby(["club_name", "club_type", "target_type"], as_index=False).agg(
        attempts=("score", "count"),
        hits=("score", "sum")
    )
    grp["club"] = grp["club_name"].astype(str) + " " + grp["club_type"].astype(str)
    grp["misses"] = grp["attempts"] - grp["hits"]
    grp["club_score"] = grp["hits"]
    grp["accuracy_num"] = ((grp["hits"] / grp["attempts"]) * 100).round(1)
    grp["accuracy_%"] = grp["accuracy_num"].map(lambda x: f"{x:.1f}%")
    return grp[["club", "target_type", "attempts", "hits", "misses", "club_score", "accuracy_%"]]



def make_round_summary(results_df):
    if results_df.empty:
        return pd.DataFrame()

    grp = results_df.groupby("round_no", as_index=False).agg(
        hits=("score", "sum"),
        shots=("score", "count")
    )
    grp["misses"] = grp["shots"] - grp["hits"]
    grp["round_score"] = grp["hits"]
    grp["accuracy_num"] = ((grp["hits"] / grp["shots"]) * 100).round(1)
    grp["accuracy_%"] = grp["accuracy_num"].map(lambda x: f"{x:.1f}%")
    return grp[["round_no", "hits", "misses", "round_score", "accuracy_%"]]



def require_login():
    if not st.user.is_logged_in:
        st.title(APP_TITLE)
        st.subheader("Please log in.")
        st.button("Log in with Google", on_click=st.login)
        st.stop()


def current_user_email():
    try:
        return str(st.user.get("email", "")).strip().lower()
    except Exception:
        return ""


def render_header():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("Range practice tracker with random 8-club sessions, 6 rounds, and live hit/miss capture.")
    st.markdown(
        """
        <style>
        div[data-testid="stDataFrame"] table td, div[data-testid="stDataFrame"] table th {
            text-align: center !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def render_setup_page(settings):
    st.subheader("Setup")

    player_name = st.text_input("Player Name", value=settings.get("player_name", ""))
    home_range = st.text_input("Home Range (optional)", value=settings.get("home_range", ""))

    st.markdown("### Clubs In Bag")
    st.caption("Add one club at a time. Club Name = brand/model. Club Type = the club itself, for example Driver or 7i.")

    current_clubs = settings.get("clubs", [])

    add_col1, add_col2, add_col3 = st.columns([2, 2, 1])
    with add_col1:
        new_club_name = st.text_input("Club Name", value="", placeholder="Example: Mizuno", key="new_club_name")
    with add_col2:
        new_club_type = st.selectbox("Club Type", CLUB_TYPE_OPTIONS, index=0, key="new_club_type")
    with add_col3:
        st.write("")
        st.write("")
        if st.button("Add Club", use_container_width=True):
            if not str(new_club_name).strip():
                st.error("Enter Club Name.")
            else:
                current_clubs.append({"club_name": new_club_name.strip(), "club_type": new_club_type})
                settings["clubs"] = current_clubs
                save_settings(settings)
                st.rerun()

    st.markdown("### Bag")
    if current_clubs:
        for i, club in enumerate(current_clubs):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.text(club.get("club_name", ""))
            c2.text(club.get("club_type", ""))
            if c3.button("Delete", key=f"del_club_{i}", use_container_width=True):
                del current_clubs[i]
                settings["clubs"] = current_clubs
                save_settings(settings)
                st.rerun()
    else:
        st.info("No clubs added yet.")

    if st.button("Save Settings", use_container_width=True):
        if not str(player_name).strip():
            st.error("Enter Player Name.")
        elif len(current_clubs) < 8:
            st.error("Add at least 8 clubs.")
        else:
            settings["player_name"] = player_name.strip()
            settings["home_range"] = home_range.strip()
            settings["clubs"] = current_clubs
            save_settings(settings)
            st.success("Settings saved.")


def render_start_session_page(settings):
    st.subheader("Start Session")

    player_name = settings.get("player_name", "")
    bag_clubs = settings.get("clubs", [])
    default_range = settings.get("home_range", "")

    session_date = st.date_input("Date", value=date.today())
    range_name = st.text_input("Driving Range Name", value=default_range)

    if st.button("Start Session", use_container_width=True):
        if not str(player_name).strip():
            st.error("Go to Setup and save Player Name first.")
        elif len(bag_clubs) < 8:
            st.error("Go to Setup and save at least 8 clubs first.")
        elif not str(range_name).strip():
            st.error("Enter Driving Range Name.")
        else:
            start_new_session(player_name, session_date, range_name.strip(), bag_clubs)
            st.session_state["go_page"] = "Live Session"
            st.rerun()

    sess = get_active_session()
    if sess and not session_finished():
        st.markdown("### Active Session")
        st.write(f"**Date:** {sess['session_date']}")
        st.write(f"**Range:** {sess['range_name']}")
        st.write(f"**Start Time:** {sess['start_time']}")

        selected_df = pd.DataFrame(sess["selected_clubs"])
        selected_df["club"] = selected_df["club_name"].astype(str) + " " + selected_df["club_type"].astype(str)
        selected_df = selected_df[["club"]]
        st.markdown("**Selected 8 Clubs**")
        st.dataframe(selected_df, use_container_width=True, hide_index=True)


def render_live_session_page():
    st.subheader("Live Session")
    sess = get_active_session()

    if not sess:
        st.info("Start a session first.")
        return

    if session_finished():
        st.success("Session completed. Go to Summary.")
        return

    idx = sess["current_index"]
    shot = sess["session_plan"][idx]

    round_no = shot["round_no"]
    shot_in_round = shot["shot_in_round"]
    total_shot_no = idx + 1

    st.markdown(f"### Round {round_no} of 6")
    st.caption(f"Shot {shot_in_round} of 8 • Total {total_shot_no} of 48")

    st.markdown("---")
    st.markdown(f"## {shot['club_name']} {shot['club_type']}")
    st.markdown(f"### Target: {shot['target_type']}")

    if "shot_choice" not in st.session_state:
        st.session_state.shot_choice = None

    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            min-height: 72px;
            font-size: 1.25rem;
            font-weight: 700;
            border-radius: 14px;
        }
        div[data-testid="column"]:nth-of-type(1) div[data-testid="stButton"] > button {
            background: #16a34a !important;
            color: white !important;
            border: 1px solid #16a34a !important;
        }
        div[data-testid="column"]:nth-of-type(2) div[data-testid="stButton"] > button {
            background: #dc2626 !important;
            color: white !important;
            border: 1px solid #dc2626 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("HIT", use_container_width=True, key="hit_btn"):
            st.session_state.shot_choice = "HIT"
    with col2:
        if st.button("MISS", use_container_width=True, key="miss_btn"):
            st.session_state.shot_choice = "MISS"

    current_choice = st.session_state.get("shot_choice")
    if current_choice:
        st.write(f"**Selected:** {current_choice}")

    if st.button("NEXT SHOT", use_container_width=True, type="primary"):
        if current_choice not in ["HIT", "MISS"]:
            st.error("Select HIT or MISS first.")
        else:
            finished_round = shot["shot_in_round"] == 8
            record_shot(current_choice)
            st.session_state.shot_choice = None

            if session_finished():
                st.session_state["go_page"] = "Summary"
            elif finished_round:
                latest_results = session_results_df()
                rnd = latest_results[latest_results["round_no"] == round_no]
                round_hits = int(rnd["score"].sum())
                st.success(f"Round {round_no} complete. Round Score: {round_hits} / 8")
            st.rerun()



def render_summary_page():
    st.subheader("Summary")
    sess = get_active_session()

    if not sess:
        st.info("No active session.")
        return

    if not session_finished():
        st.info("Finish the session first.")
        return

    results_df = session_results_df()
    club_df = make_club_summary(results_df)
    round_df = make_round_summary(results_df)

    start_dt = datetime.strptime(sess["start_time"], "%Y-%m-%d %H:%M:%S")
    finish_dt = datetime.strptime(sess["finish_time"], "%Y-%m-%d %H:%M:%S")
    duration_minutes = round((finish_dt - start_dt).total_seconds() / 60, 2)

    total_hits = int(results_df["score"].sum())
    total_shots = len(results_df)
    total_misses = total_shots - total_hits
    overall_accuracy = round((total_hits / total_shots) * 100, 2) if total_shots else 0.0

    st.write(f"**Date:** {sess['session_date']}")
    st.write(f"**Range:** {sess['range_name']}")
    st.write(f"**Start Time:** {sess['start_time']}")
    st.write(f"**Finish Time:** {sess['finish_time']}")
    st.write(f"**Duration (minutes):** {duration_minutes}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Hits", f"{total_hits} / 48")
    c2.metric("Total Misses", total_misses)
    c3.metric("Overall Accuracy %", f"{overall_accuracy:.1f}%")

    st.markdown("### Club Summary")
    st.dataframe(club_df.style.set_properties(**{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}]), use_container_width=True, hide_index=True)

    st.markdown("### Round Summary")
    st.dataframe(round_df.style.set_properties(**{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}]), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Session", use_container_width=True, type="primary"):
            save_active_session_to_files()
            st.success("Session saved.")
    with col2:
        if st.button("Discard Session", use_container_width=True):
            clear_active_session()
            st.warning("Session discarded.")
            st.rerun()



def render_tracking_page():
    st.subheader("Tracking")
    current_player = str(load_settings().get("player_name", "")).strip()
    if current_player:
        st.caption(f"Showing data for: {current_player}")

    sessions_df = load_sessions_df()
    shots_df = load_shots_df()

    if sessions_df.empty:
        st.info("No saved sessions yet.")
        return

    sessions_df["session_date"] = pd.to_datetime(sessions_df["session_date"], errors="coerce")

    min_date = sessions_df["session_date"].min().date() if not sessions_df["session_date"].isna().all() else date.today()
    max_date = sessions_df["session_date"].max().date() if not sessions_df["session_date"].isna().all() else date.today()

    f1, f2, f3 = st.columns(3)
    with f1:
        date_from = st.date_input("Date From", value=min_date, key="track_from")
    with f2:
        date_to = st.date_input("Date To", value=max_date, key="track_to")
    with f3:
        range_options = ["All"] + sorted([x for x in sessions_df["range_name"].dropna().astype(str).unique().tolist() if x.strip()])
        range_filter = st.selectbox("Range Name", range_options, index=0)

    owner_email = current_user_email()
    filt = sessions_df.copy()
    if "owner_email" in filt.columns:
        filt = filt[filt["owner_email"].astype(str).str.strip().str.lower() == owner_email]

    if filt.empty:
        st.info("No sessions in selected filters.")
        return

    total_sessions = len(filt)
    avg_score = round(pd.to_numeric(filt["total_score"], errors="coerce").fillna(0).mean(), 2)
    avg_accuracy = round(pd.to_numeric(filt["overall_accuracy"], errors="coerce").fillna(0).mean(), 2)
    best_session = pd.to_numeric(filt["overall_accuracy"], errors="coerce").fillna(0).max()
    worst_session = pd.to_numeric(filt["overall_accuracy"], errors="coerce").fillna(0).min()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sessions Completed", total_sessions)
    c2.metric("Average Total Score", avg_score)
    c3.metric("Average Accuracy %", f"{avg_accuracy:.1f}%")
    c4.metric("Best Session", f"{best_session:.1f}%")

    st.markdown("### Session History")
    display_sessions = filt.copy()
    display_sessions["session_date"] = display_sessions["session_date"].dt.strftime("%Y-%m-%d")
    display_sessions["overall_accuracy"] = pd.to_numeric(display_sessions["overall_accuracy"], errors="coerce").fillna(0).map(lambda x: f"{x:.1f}%")
    st.dataframe(display_sessions[[
        "session_date", "range_name", "player_name", "start_time", "finish_time",
        "total_hits", "total_misses", "total_score", "overall_accuracy"
    ]].style.set_properties(**{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}]), use_container_width=True, hide_index=True)

    st.markdown("### Performance Over Time")
    chart_df = filt.sort_values("session_date").copy()
    chart_df["label"] = chart_df["session_date"].dt.strftime("%Y-%m-%d")

    graph_choice = st.selectbox(
        "Select Graph",
        ["Accuracy Over Time", "Total Score Over Time", "Club Accuracy Over Time"],
        index=0
    )

    if graph_choice == "Accuracy Over Time":
        st.line_chart(chart_df.set_index("label")["overall_accuracy"])

    elif graph_choice == "Total Score Over Time":
        st.line_chart(chart_df.set_index("label")["total_score"])

    elif graph_choice == "Club Accuracy Over Time":
        if not shots_df.empty:
            valid_ids = set(filt["session_id"].astype(str).tolist())
            shots_f2 = shots_df[shots_df["session_id"].astype(str).isin(valid_ids)].copy()
            if "owner_email" in shots_f2.columns:
                shots_f2 = shots_f2[shots_f2["owner_email"].astype(str).str.strip().str.lower() == owner_email]

            shots_f2["club"] = shots_f2["club_name"].astype(str) + " " + shots_f2["club_type"].astype(str)

            club_options = sorted(shots_f2["club"].dropna().unique().tolist())

            if club_options:
                selected_club = st.selectbox("Select Club", club_options, index=0)

                club_chart = shots_f2[shots_f2["club"] == selected_club].copy()
                club_chart = club_chart.groupby("session_date", as_index=False).agg(
                    hits=("score", "sum"),
                    attempts=("score", "count")
                )

                club_chart["accuracy"] = ((club_chart["hits"] / club_chart["attempts"]) * 100).round(1)
                club_chart["label"] = pd.to_datetime(club_chart["session_date"], errors="coerce").dt.strftime("%Y-%m-%d")

                st.line_chart(club_chart.set_index("label")["accuracy"])
            else:
                st.info("No club data available.")

    if not shots_df.empty:
        shots_df["session_date"] = pd.to_datetime(shots_df["session_date"], errors="coerce")
        valid_ids = set(filt["session_id"].astype(str).tolist())
        shots_f = shots_df[shots_df["session_id"].astype(str).isin(valid_ids)].copy()
        if "owner_email" in shots_f.columns:
            shots_f = shots_f[shots_f["owner_email"].astype(str).str.strip().str.lower() == owner_email]

        if not shots_f.empty:
            st.markdown("### Club Performance")
            club_perf = shots_f.groupby(["club_name", "club_type"], as_index=False).agg(
                attempts=("score", "count"),
                hits=("score", "sum")
            )
            club_perf["club"] = club_perf["club_name"].astype(str) + " " + club_perf["club_type"].astype(str)
            club_perf["accuracy_num"] = ((club_perf["hits"] / club_perf["attempts"]) * 100).round(1)
            club_perf["accuracy_%"] = club_perf["accuracy_num"].map(lambda x: f"{x:.1f}%")
            club_perf = club_perf[["club", "attempts", "hits", "accuracy_num", "accuracy_%"]].sort_values(["accuracy_num", "hits"], ascending=[False, False])
            st.dataframe(
                club_perf[["club", "attempts", "hits", "accuracy_%"]].style.set_properties(**{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}]),
                use_container_width=True,
                hide_index=True
)

            round_scores = shots_f.groupby(["session_id", "session_date", "round_no"], as_index=False).agg(
                round_score=("score", "sum")
            )
            round_pivot = round_scores.pivot_table(
                index=["session_date"],
                columns="round_no",
                values="round_score",
                aggfunc="sum"
            ).reset_index()
            round_pivot.columns = [
                "session_date" if x == "session_date" else f"Round {x}" for x in round_pivot.columns
            ]
            round_pivot["session_date"] = pd.to_datetime(round_pivot["session_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            st.markdown("### Round Scores")
            st.dataframe(
                round_pivot.style.set_properties(**{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}]),
                use_container_width=True,
                hide_index=True
)

            best_row = club_perf.iloc[0]
            worst_row = club_perf.iloc[-1]
            b1, b2 = st.columns(2)
            b1.metric("Best Club", f"{best_row['club']} ({best_row['accuracy_%']})")
            b2.metric("Weakest Club", f"{worst_row['club']} ({worst_row['accuracy_%']})")



def main():
    ensure_csv_files()
    settings = load_settings()
    render_header()
    require_login()

    pages = ["Setup", "Start Session", "Live Session", "Summary", "Tracking"]
    default_index = pages.index(st.session_state.get("go_page", "Setup")) if st.session_state.get("go_page", "Setup") in pages else 0
    page = st.sidebar.radio(
        "Go to page",
        pages,
        index=default_index
    )
    st.session_state["go_page"] = page

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Signed in as: {current_user_email()}")
    st.sidebar.button("Log out", on_click=st.logout, use_container_width=True)
    st.sidebar.markdown("---")
    sess = get_active_session()
    if sess and not session_finished():
        st.sidebar.success("Active session in progress")
        st.sidebar.write(f"Range: {sess['range_name']}")
        st.sidebar.write(f"Date: {sess['session_date']}")
        st.sidebar.write(f"Progress: {sess['current_index']} / 48")
    elif sess and session_finished():
        st.sidebar.info("Session completed - ready to save")

    if page == "Setup":
        render_setup_page(settings)
    elif page == "Start Session":
        render_start_session_page(settings)
    elif page == "Live Session":
        render_live_session_page()
    elif page == "Summary":
        render_summary_page()
    elif page == "Tracking":
        render_tracking_page()


if __name__ == "__main__":
    main()
