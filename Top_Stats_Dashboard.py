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
    # Ensure df['date'] is in datetime format and convert to date only
    df['date'] = pd.to_datetime(df['date']).dt.date
    # Date input with corrected min_value and max_value
    date_range = st.sidebar.date_input(
        "Select Date Range",
        [df['date'].min(), df['date'].max()],
        min_value=df['date'].min(),
        max_value=df['date'].max()
    )

    # Filter data
    filtered_df = df
    if selected_players:
        filtered_df = filtered_df[filtered_df['name'].isin(selected_players)]
    if selected_professions:
        filtered_df = filtered_df[filtered_df['profession'].isin(selected_professions)]
    if len(date_range) == 2:
        start_date = date_range[0]
        end_date = date_range[1]
        filtered_df = filtered_df[(filtered_df['date'] >= start_date) & (filtered_df['date'] <= end_date)]
    elif len(date_range) == 1:
        start_date = date_range[0]
        end_date = start_date
        filtered_df = filtered_df[filtered_df['date'] == start_date]
        
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Performance Trends", "Comparison", "Custom Stats", "Bubble Chart"])

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
        # Ensure date is in date format for plotting
        trend_df['date'] = pd.to_datetime(trend_df['date']).dt.date
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

    with tab5:
        st.header("Bubble Charts")
        
        # Available metrics
        available_metrics = ["damage", "down_contribution", "downs", "kills", "damage_taken", 
                             "damage_barrier", "downed", "deaths", "cleanses", "boon_strips", 
                             "resurrects", "healing", "barrier", "downed_healing", "stab_gen", 
                             "migh_gen", "fury_gen", "quic_gen", "alac_gen", "prot_gen", "rege_gen", 
                             "vigo_gen", "aeg_gen", "swif_gen", "resi_gen", "reso_gen", 'duration', 'num_fights'] 
        
        # Select or input custom metrics
        st.write("Select predefined metrics or enter custom formulas (using pandas eval syntax). Available columns: " + 
                ", ".join(filtered_df.columns))
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            x_type = st.radio("X-axis Type", ["Predefined"], key="x_type")
            if x_type == "Predefined":
                x_metric = st.selectbox("Select X-axis Metric", available_metrics, index=0, key="x_predefined")
                x_column = x_metric
                x_label = x_metric.capitalize()
            else:
                x_formula = st.text_input("Enter X-axis Formula (e.g., 'damage / duration')", 
                                         value="damage", key="x_formula")
                x_column = "custom_x"
                x_label = "Custom X Metric"
                result = calculate_derived_stat(filtered_df, x_formula)
                if result is not None:
                    filtered_df['custom_x'] = result

        with col2:
            y_type = st.radio("Y-axis Type", ["Predefined"], key="y_type")
            if y_type == "Predefined":
                y_metric = st.selectbox("Select Y-axis Metric", available_metrics, index=1, key="y_predefined")
                y_column = y_metric
                y_label = y_metric.capitalize()
            else:
                y_formula = st.text_input("Enter Y-axis Formula (e.g., 'healing / duration')", 
                                         value="healing", key="y_formula")
                y_column = "custom_y"
                y_label = "Custom Y Metric"
                result = calculate_derived_stat(filtered_df, y_formula)
                if result is not None:
                    filtered_df['custom_y'] = result

        with col3:
            size_type = st.radio("Bubble Size Type", ["Predefined"], key="size_type")
            if size_type == "Predefined":
                size_metric = st.selectbox("Select Bubble Size Metric", available_metrics, index=2, key="size_predefined")
                size_column = size_metric
                size_label = size_metric.capitalize()
            else:
                size_formula = st.text_input("Enter Bubble Size Formula (e.g., 'num_fights * 10')", 
                                            value="num_fights", key="size_formula")
                size_column = "custom_size"
                size_label = "Custom Size Metric"
                result = calculate_derived_stat(filtered_df, size_formula)
                if result is not None:
                    filtered_df['custom_size'] = result

        # Create bubble chart
        if all(col in filtered_df.columns for col in [x_column, y_column, size_column]):
            fig_bubble = px.scatter(
                filtered_df,
                x=x_column,
                y=y_column,
                size=size_column,
                color='profession',
                hover_data=['name', 'date'],
                title=f"Bubble Chart: {x_label} vs {y_label} (Size: {size_label})",
                size_max=60
            )
            st.plotly_chart(fig_bubble, use_container_width=True)
        else:
            st.warning("Please ensure all custom formulas are valid to display the bubble chart.")

if __name__ == "__main__":
    main()