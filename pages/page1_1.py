import streamlit as st
import pandas as pd
import altair as alt
from vega_datasets import data

st.title("Graph Overview")

# sub1
st.subheader("Entity Type Summary:\n")

entity_type = pd.read_csv('data/entity_type.csv', nrows=12)
percent_col = "Percent"

column_config = {}
for col in entity_type.columns:
    if col == percent_col:
        column_config[col] = st.column_config.ProgressColumn(
            col,
            min_value=0.0,
            max_value=0.3,
            format="%.2f",
            width="medium",
            color="red",
        )
    else:
        column_config[col] = st.column_config.Column(col)

st.dataframe(
    entity_type,
    hide_index=True,
    use_container_width=True,
    column_config=column_config,
)

# sub2
st.subheader("Relationship Views:\n")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Relationship flow**")
    st.image("figures/chord.png", use_container_width=True)
    st.caption("How connections are distributed across different types of nodes.")

with col2:
    st.markdown("**Node-Degree distribution**")
    st.image("figures/bubble.png", use_container_width=True)
    st.caption("Bubble size represents node counts and degree of each entity type, while position reflects the average degree.")

# sub3
st.subheader("Entity Cloud Examples:\n")
st.markdown("Entity Cloud highlights representative entities, with size reflecting their frequency")

col1, col2 = st.columns(2)
with col1:
    st.image("figures/DISO.png", use_container_width=True)
    st.caption("Entity cloud for DISO entities")
with col2:
    st.image("figures/ACTI.png", use_container_width=True)
    st.caption("Entity cloud for ACTI entities")

col3, col4 = st.columns(2)
with col3:
    st.image("figures/CHEM.png", use_container_width=True)
    st.caption("Entity cloud for CHEM entities")
with col4:
    st.image("figures/ANAT.png", use_container_width=True)
    st.caption("Entity cloud for ANAT entities")