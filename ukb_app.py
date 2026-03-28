import streamlit as st

st.set_page_config(page_title="UKB-KG App", page_icon=":material/home:", layout="wide")


def render_home():
    st.title("UKB-KG Platform")
    st.markdown(
        """
        Welcome to the UKB-KG platform. Use the navigation menu to explore the graph,
        search for entities, relationships and contextual features, or interact with the chatbot.
        """
    )

    st.subheader("Available pages")
    col1, col2 = st.columns(2)
    with col1:
        st.info("**KG Explore**\n\n- Graph Overview\n- Basic Search\n- Subgraph Explorer")
    with col2:
        st.info("**Assistant**\n\n- Chatbot")

pages = {
    "": [
        st.Page(render_home, title="Home", icon=":material/home:", default=True),
    ],
    "KG Explore": [
        st.Page("pages/page1_1.py", title="Graph Overview", icon=":material/bar_chart:"),
        st.Page("pages/page1_2.py", title="Basic Search", icon=":material/search:"),
        st.Page("pages/page1_3.py", title="Subgraph Explorer", icon=":material/hub:"),
    ],
    "KG Assistant": [
        st.Page("pages/page2.py", title="Chatbot", icon=":material/smart_toy:"),
    ],
}

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()