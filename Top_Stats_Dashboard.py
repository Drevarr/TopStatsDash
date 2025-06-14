import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import shutil
import uuid

# Database connection
@st.cache_resource
def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    return conn

# Fetch data from database
@st.cache_data
def load_data(db_path):
    conn = get_db_connection(db_path)
    query = "SELECT * FROM player_stats"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Calculate derived stat based on user input
def calculate_derived_stat(df, formula):
    try:
        result = df.eval(formula)
        return result
    except Exception as e:
        st.error(f"Error in formula: {str(e)}")
        return None

# Main dashboard
def main():
    st.set_page_config(page_title="GW2 Player Stats Dashboard", layout="wide")
    st.title("Guild Wars 2 Player Performance Dashboard")

    # Database upload and selection
    st.sidebar.header("Database Management")
    uploaded_files = st.sidebar.file_uploader("Upload SQLite Database(s)", 
                                            type=["db", "sqlite", "sqlite3"], 
                                            accept_multiple_files=True)

    # Store uploaded databases
    if 'db_files' not in st.session_state:
        st.session_state.db_files = {}

    # Save uploaded files to temporary directory
    temp_dir = "temp_dbs"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            # Generate unique filename to avoid conflicts
            unique_filename = f"{uuid.uuid4()}_{uploaded_file.name}"
            file_path = os.path.join(temp_dir, unique_filename)
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Store in session state
            st.session_state.db_files[uploaded_file.name] = file_path

    # Database selection
    if st.session_state.db_files:
        selected_db = st.sidebar.selectbox("Select Database", 
                                         list(st.session_state.db_files.keys()))
        db_path = st.session_state.db_files.get(selected_db, None)
    else:
        st.warning("Please upload at least one SQLite database to continue.")
        return

    # Load data from selected database
    if db_path:
        df = load_data(db_path)
    else:
        st.error("No valid database selected.")
        return

    # Sidebar filters
    st.sidebar.header("Filters")
    selected_players = st.sidebar.multiselect("Select Players", options=sorted(df['name'].unique()))
    selected_professions = st.sidebar.multiselect("Select Professions", options=sorted(df['profession'].unique()))
    # Ensure df['date'] is in datetime format
    df['date'] = pd.to_datetime(df['date'])
    # Date input with corrected min_value and max_value
    date_range = st.sidebar.date_input(
        "Select Date Range",
        [df['date'].min().date(), df['date'].max().date()],
        min_value=df['date'].min().date(),
        max_value=df['date'].max().date()
    )

    # Filter data
    filtered_df = df
    if selected_players:
        filtered_df = filtered_df[filtered_df['name'].isin(selected_players)]
    if selected_professions:
        filtered_df = filtered_df[filtered_df['profession'].isin(selected_professions)]
    if len(date_range) == 2:
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1]) + timedelta(days=1) - timedelta(seconds=1)  # Include full end date
        filtered_df = filtered_df[(filtered_df['date'] >= start_date) & (filtered_df['date'] <= end_date)]
    elif len(date_range) == 1:
        start_date = pd.to_datetime(date_range[0])
        end_date = start_date + timedelta(days=1) - timedelta(seconds=1)  # Single day, include full day
        filtered_df = filtered_df[(filtered_df['date'] >= start_date) & (filtered_df['date'] <= end_date)]
        
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Performance Trends", "Comparison", "Custom Stats"])

    with tab1:
        st.header("Overview")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Fights", int(filtered_df['num_fights'].sum()))
        with col2:
            st.metric("Total Duration (s)", int(filtered_df['duration'].sum()))
        with col3:
            st.metric("Unique Players", len(filtered_df['name'].unique()))

        # Damage Distribution
        fig_dmg = px.histogram(filtered_df, x='damage', color='profession', 
                              title="Damage Distribution by Profession")
        st.plotly_chart(fig_dmg, use_container_width=True)

    with tab2:
        st.header("Performance Trends")
        
        metric = st.selectbox("Select Metric", 
                             ['damage', 'damage_taken', 'healing', 'barrier', 
                              'cleanses', 'boon_strips', 'resurrects'])
        
        # Group by name_profession and date
        trend_df = filtered_df.groupby(['date', 'name', 'profession'])[metric].mean().reset_index()
        fig_trend = px.line(trend_df, x='date', y=metric, color='name', 
                           line_group='profession', title=f"{metric.capitalize()} Trend Over Time")
        st.plotly_chart(fig_trend, use_container_width=True)

    with tab3:
        st.header("Player Comparison")
        
        metric_comp = st.selectbox("Select Comparison Metric", 
                                  ['damage', 'damage_taken', 'healing', 'barrier', 
                                   'cleanses', 'boon_strips', 'resurrects'])
        
        # Box plot for comparison
        fig_comp = px.box(filtered_df, x='profession', y=metric_comp, color='name',
                         title=f"{metric_comp.capitalize()} Comparison by Profession")
        st.plotly_chart(fig_comp, use_container_width=True)

    with tab4:
        st.header("Custom Stats Calculator")
        
        st.write("Create custom metrics using pandas eval syntax. Available columns: " + 
                ", ".join(filtered_df.columns))
        
        formula = st.text_input("Enter formula (e.g., 'damage / duration')", 
                               value="damage / duration")
        
        if st.button("Calculate"):
            result = calculate_derived_stat(filtered_df, formula)
            if result is not None:
                filtered_df['custom_metric'] = result
                st.write("Custom Metric Results:")
                st.dataframe(filtered_df[['name', 'profession', 'date', 'custom_metric']])
                
                # Visualize custom metric
                fig_custom = px.bar(filtered_df, x='name', y='custom_metric', 
                                   color='profession', title="Custom Metric Results")
                st.plotly_chart(fig_custom, use_container_width=True)

if __name__ == "__main__":
    main()