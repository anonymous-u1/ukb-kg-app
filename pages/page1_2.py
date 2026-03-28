import streamlit as st
from streamlit.components.v1 import html
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from pyvis.network import Network
from pathlib import Path
import pandas as pd

st.title("Basic Search")

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
GRAPH_DIR = BASE_DIR / "graph"
GRAPH_DIR.mkdir(exist_ok=True)
GRAPH_HTML_PATH = GRAPH_DIR / "graph.html"

NODE_COLORS = {
    'GENE': '#E4A031',
    'MEAS': '#C76B60',
    'DISO': '#B55384',
    'PHYS': '#474769',
    'PROC': '#26445E',
    'CHEM': '#4C7780',
    'MISC': '#73A5A2',
    'ANAT': '#F3DBC1',
    'ACTI': '#B2B6C1',
    'BASE': '#D6E2E2'
}

SEARCH_NODE_LIMIT = 30
RELATED_NODE_LIMIT = 10
NEIGHBOR_RESULT_LIMIT = 100

@st.cache_resource(show_spinner=False)
def get_driver():
    uri = st.secrets["neo4j"]["uri"]
    user = st.secrets["neo4j"]["username"]
    password = st.secrets["neo4j"]["password"]
    return GraphDatabase.driver(uri, auth=(user, password))

@st.cache_data(show_spinner=False)
def load_medline_data() -> pd.DataFrame:
    df = pd.read_csv(st.secrets["DATA_URL"])
    if "PMC" in df.columns:
        df["PMC"] = df["PMC"].astype(str).str.strip().str.upper()
    return df

medline_data = load_medline_data()

def normalize_pmcid(pmcid: str) -> str:
    pmcid = str(pmcid).strip().upper()
    if pmcid and not pmcid.startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    return pmcid


@st.cache_data(show_spinner=False, ttl=300)
def search_node(name: str) -> list[dict]:
    name = name.strip().lower()
    if not name:
        return []

    driver = get_driver()
    query = f"""
    MATCH (n)
    WHERE toLower(n.name) CONTAINS $name
    RETURN n,
           CASE
               WHEN toLower(n.name) = $name THEN 0
               WHEN toLower(n.name) STARTS WITH $name THEN 1
               ELSE 2
           END AS priority,
           COUNT {{(n)--()}} AS degree
    ORDER BY priority ASC, degree DESC, n.name ASC
    LIMIT {SEARCH_NODE_LIMIT}
    """
    with driver.session() as session:
        result = session.run(query, name=name)
        return [record["n"] for record in result]


@st.cache_data(show_spinner=False, ttl=300)
def get_neighbors(node_id: int) -> tuple[list[dict], list[dict]]:
    driver = get_driver()
    query = f"""
    MATCH (n)-[r]-(m)
    WHERE id(n) = $node_id
    
    WITH n, r, m, COUNT{{(m)--()}} AS degree
    ORDER BY degree DESC   // 优先保留重要节点
    LIMIT {NEIGHBOR_RESULT_LIMIT}
    
    RETURN n, r, m
    """
    with driver.session() as session:
        result = session.run(query, node_id=node_id)
        node_map = {}
        edge_map = {}
        for record in result:
            start_node = record["n"]
            end_node = record["m"]
            edge = record["r"]

            node_map[start_node.id] = start_node
            node_map[end_node.id] = end_node
            edge_key = (
                edge.element_id,
                edge.start_node.id,
                edge.end_node.id,
                edge.type,
                tuple(sorted(edge.items())),
            )
            edge_map[edge_key] = edge

        return list(node_map.values()), list(edge_map.values())


@st.cache_data(show_spinner=False, ttl=300)
def find_related_nodes(name: str) -> list[dict]:
    name = name.strip().lower()
    if not name:
        return []

    driver = get_driver()
    query = f"""
    MATCH (n)
    WITH n,
         apoc.text.levenshteinSimilarity(toLower(n.name), toLower($name)) AS similarity,
         COUNT {{(n)--()}} AS degree
    RETURN n, similarity, degree
    ORDER BY similarity DESC, degree DESC
    LIMIT {RELATED_NODE_LIMIT}
    """
    with driver.session() as session:
        result = session.run(query, name=name)
        return [record["n"] for record in result]


def create_network(nodes: list[dict], edges: list[dict]) -> str:
    theme = getattr(st.context.theme, "type", "dark")

    if theme == "light":
        bgcolor = "#FFFFFF"
        font_color = "#111827"
        edge_color = "#9CA3AF"
    else:
        bgcolor = "#0E1117"
        font_color = "#FAFAFA"
        edge_color = "#7F8C8D"

    net = Network(
        height="750px",
        width="100%",
        notebook=False,
        directed=True,
        bgcolor=bgcolor,
        font_color=font_color,
    )

    for node in nodes:
        label = next(iter(node.labels), "Node")
        color = NODE_COLORS.get(label, "#9AA0A6")

        degree = sum(
            1
            for edge in edges
            if edge.start_node.id == node.id or edge.end_node.id == node.id
        )

        net.add_node(
            node.id,
            label=node.get("name", ""),
            title=f"{node.get('name', '')} ({label})<br>Degree: {degree}",
            color=color,
            font={"color": font_color},
            size=max(18, min(42, 16 + degree * 2)),
        )

    for edge in edges:
        pmcid = edge.get("PMCID") or edge.get("pmcid") or ""
        title = edge.type if not pmcid else f"{edge.type}<br>{pmcid}"

        net.add_edge(
            edge.start_node.id,
            edge.end_node.id,
            label=edge.type,
            title=title,
            color=edge_color,
            font={"color": font_color, "size": 12},
            arrows="to",
        )

    net.force_atlas_2based(
        gravity=-35,
        central_gravity=0.015,
        spring_length=90,
        spring_strength=0.05,
        damping=0.6,
    )

    net.save_graph(str(GRAPH_HTML_PATH))
    return GRAPH_HTML_PATH.read_text(encoding="utf-8")


def small_metric(label, value):
    theme_type = getattr(st.context.theme, "type", "dark")

    if theme_type == "light":
        bg = "#FFFFFF"
        border = "#E5E7EB"
        label_color = "#6B7280"
        value_color = "#111827"
    else:
        bg = "#111827"
        border = "rgba(255,255,255,0.10)"
        label_color = "#9CA3AF"
        value_color = "#F9FAFB"

    st.markdown(
        f"""
        <div style="
            padding:8px 10px;
            border:1px solid {border};
            border-radius:10px;
            background:{bg};
        ">
            <div style="font-size:12px; color:{label_color};">{label}</div>
            <div style="font-size:18px; font-weight:600; color:{value_color}; margin-top:2px;">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_node_legend():
    with st.expander("Node type legend", expanded=True):

        legend_items = list(NODE_COLORS.items())
        num_columns = 5
        rows = [legend_items[i:i + num_columns] for i in range(0, len(legend_items), num_columns)]

        for row in rows:
            columns = st.columns(num_columns)
            for idx, column in enumerate(columns):
                if idx < len(row):
                    label, color = row[idx]
                    column.markdown(
                        f"<div style='display:flex; align-items:center; gap:0.45rem; margin:0.15rem 0;'>"
                        f"<span style='display:inline-block; width:0.9rem; height:0.9rem; "
                        f"border-radius:50%; background:{color}; border:1px solid rgba(255,255,255,0.25);'></span>"
                        f"<span style='font-size:0.95rem;'>{label}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )


def search_contextual_features(pmcid: str) -> pd.DataFrame:
    if medline_data.empty:
        return pd.DataFrame()
    normalized = normalize_pmcid(pmcid)
    if not normalized:
        return pd.DataFrame()
    return medline_data[medline_data["PMC"] == normalized].copy()



def build_relationship_table(nodes: list[dict], edges: list[dict]) -> pd.DataFrame:
    node_map = {node.id: node for node in nodes}
    rows = []

    for edge in edges:
        start_node = node_map.get(edge.start_node.id)
        end_node = node_map.get(edge.end_node.id)
        if start_node is None or end_node is None:
            continue

        start_label = next(iter(start_node.labels), "Node")
        end_label = next(iter(end_node.labels), "Node")
        pmcid = edge.get("PMCID") or edge.get("pmcid") or ""
        rows.append(
            {
                "Node": f"{start_node.get('name', '')} ({start_label})",
                "Relationship": edge.type,
                "Neighbor": f"{end_node.get('name', '')} ({end_label})",
                "PMCID": pmcid,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["Node", "Relationship", "Neighbor", "PMCID"])

    return pd.DataFrame(rows).sort_values(["Relationship", "Node", "Neighbor"]).reset_index(drop=True)



def render_graph_result(selected_node):
    nodes, edges = get_neighbors(selected_node.id)

    if not nodes:
        st.info("No neighbors were found for this node.")
        return

    html_content = create_network(nodes, edges)
    relation_df = build_relationship_table(nodes, edges)

    col1, col2, col3 = st.columns(3)
    with col1:
        small_metric("Matched node", selected_node.get("name", ""))
    with col2:
        small_metric("Neighbor nodes", max(len(nodes) - 1, 0))
    with col3:
        small_metric("Relationships", len(edges))

    tab1, tab2 = st.tabs(["Graph", "Table"])
    with tab1:
        html(html_content, height=540)
        render_node_legend()
    with tab2:
        st.dataframe(
            relation_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Node": st.column_config.TextColumn(width="medium"),
                "Relationship": st.column_config.TextColumn(width="small"),
                "Neighbor": st.column_config.TextColumn(width="medium"),
                "PMCID": st.column_config.TextColumn(width="small"),
            },
        )


for key, default in {
    "search_results": [],
    "search_button": False,
    "selected_search_index": 0,
    "search_results_2": pd.DataFrame(),
    "search_button_2": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


with st.container(border=True):
    st.subheader("Search a node")
    st.caption(
        f"Search by node name and inspect its 1-hop neighborhood in the knowledge graph (Only {NEIGHBOR_RESULT_LIMIT} neighbors are shown)."
    )

    node_name = st.text_input("Enter node name", placeholder="e.g. lung cancer, breast cancer, APOE")

    button_col1, button_col2 = st.columns([1, 1])
    with button_col1:
        search_clicked = st.button("Search", use_container_width=True)
    with button_col2:
        clear_clicked = st.button("Clear All", key="clear1", use_container_width=True)

    if clear_clicked:
        st.session_state.search_results = []
        st.session_state.search_button = False
        st.session_state.selected_search_index = 0
        st.rerun()

    if search_clicked:
        cleaned_name = node_name.strip().lower()
        if not cleaned_name:
            st.warning("Please enter a node name first.")
        else:
            try:
                st.session_state.search_results = search_node(cleaned_name)
                st.session_state.search_button = True
                st.session_state.selected_search_index = 0
            except Neo4jError as exc:
                st.error(f"Neo4j query failed: {exc}")
            except Exception as exc:
                st.error(f"Unable to search the graph right now: {exc}")

    if st.session_state.search_button:
        search_results = st.session_state.search_results

        if search_results:
            option_labels = [
                f"{node.get('name', '')} ({next(iter(node.labels), 'Node')})"
                for node in search_results
            ]
            selected_label = st.selectbox(
                "Matched nodes",
                options=option_labels,
                index=min(st.session_state.selected_search_index, len(option_labels) - 1),
                help="Choose the node you want to visualize when multiple matches are found.",
            )
            selected_index = option_labels.index(selected_label)
            st.session_state.selected_search_index = selected_index
            selected_node = search_results[selected_index]
            render_graph_result(selected_node)
        else:
            st.info("No exact/substring match found. Try one of these related nodes:")
            try:
                related_nodes = find_related_nodes(node_name)
            except Neo4jError as exc:
                st.error(f"Neo4j query failed: {exc}")
                related_nodes = []
            except Exception as exc:
                st.error(f"Unable to search related nodes right now: {exc}")
                related_nodes = []

            if related_nodes:
                selected_node_name = st.selectbox(
                    "Related nodes",
                    [f"{node.get('name', '')} ({next(iter(node.labels), 'Node')})" for node in related_nodes],
                    index=None,
                    placeholder="Select a related node...",
                )
                if selected_node_name:
                    selected_node = related_nodes[
                        [
                            f"{node.get('name', '')} ({next(iter(node.labels), 'Node')})"
                            for node in related_nodes
                        ].index(selected_node_name)
                    ]
                    render_graph_result(selected_node)
            else:
                st.warning("No related nodes were found.")

with st.container(border=True):
    st.subheader("Search contextual features")
    st.caption("Look up metadata for a paper by PMCID.")

    pmcid = st.text_input("Enter PMCID", placeholder="e.g. PMC8416852")

    button_col1, button_col2 = st.columns([1, 1])
    with button_col1:
        contextual_search_clicked = st.button("Search", key="search2", use_container_width=True)
    with button_col2:
        contextual_clear_clicked = st.button("Clear All", key="clear2", use_container_width=True)

    if contextual_clear_clicked:
        st.session_state.search_results_2 = pd.DataFrame()
        st.session_state.search_button_2 = False
        st.rerun()

    if contextual_search_clicked:
        if medline_data.empty:
            st.error("The contextual feature file is missing")
        else:
            normalized_pmcid = normalize_pmcid(pmcid)
            if not normalized_pmcid:
                st.warning("Please enter a PMCID first.")
            else:
                st.session_state.search_results_2 = search_contextual_features(normalized_pmcid)
                st.session_state.search_button_2 = True

    if st.session_state.search_button_2:
        if not st.session_state.search_results_2.empty:
            contextual_features = st.session_state.search_results_2
            st.success(f"Found {len(contextual_features)} matched record(s).")
            st.dataframe(contextual_features, use_container_width=True, hide_index=True)
        else:
            st.info("No matched PMCID. Please try another one.")
