from pathlib import Path
import streamlit as st
import pandas as pd
from neo4j import GraphDatabase
from pyvis.network import Network

st.set_page_config(page_title="Subgraph Explorer", layout="wide")
st.title("Subgraph Explorer")

# =========================
# Config
# =========================
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
VALID_TYPES = set(NODE_COLORS.keys())
DEFAULT_NODE_COLOR = "#9E9E9E"
GRAPH_DIR = Path(__file__).resolve().parent.parent / "graph"
GRAPH_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# Neo4j
# =========================
@st.cache_resource
def get_driver():
    uri = st.secrets["neo4j"]["uri"]
    user = st.secrets["neo4j"]["username"]
    password = st.secrets["neo4j"]["password"]
    return GraphDatabase.driver(uri, auth=(user, password))


def normalize_type(value: str) -> str:
    value = (value or "").strip().upper()
    return value if value in VALID_TYPES else ""


# =========================
# Query
# =========================
@st.cache_data(show_spinner=False, ttl=300)
def get_subgraph(node1, node2, type1, type2, hop, limit):
    driver = get_driver()

    node1 = (node1 or "").strip()
    node2 = (node2 or "").strip()
    type1 = normalize_type(type1)
    type2 = normalize_type(type2)
    hop = max(1, min(int(hop), 10))
    limit = max(1, min(int(limit), 200))

    node1_type = f":{type1}" if type1 else ""
    node2_type = f":{type2}" if type2 else ""

    params = {
        "node1": node1,
        "node2": node2,
        "limit": limit,
    }

    if node1 and node2:
        query = f"""
        MATCH p=(n1{node1_type} {{name: $node1}})-[*1..{hop}]-(n2{node2_type} {{name: $node2}})
        RETURN p
        ORDER BY length(p) ASC
        LIMIT $limit
        """
    elif node1:
        query = f"""
        MATCH p=(n1{node1_type} {{name: $node1}})-[*1..{hop}]-(n{node2_type})
        RETURN p
        ORDER BY length(p) ASC
        LIMIT $limit
        """
    elif node2:
        query = f"""
        MATCH p=(n2{node2_type} {{name: $node2}})-[*1..{hop}]-(n{node1_type})
        RETURN p
        ORDER BY length(p) ASC
        LIMIT $limit
        """
    else:
        query = f"""
        MATCH p=(n1{node1_type})-[*1..1]-(n2{node2_type})
        RETURN p
        LIMIT $limit
        """

    with driver.session() as session:
        result = session.run(query, params)

        node_map = {}
        edge_map = {}

        for record in result:
            path = record["p"]

            for node in path.nodes:
                label = next(iter(node.labels), "")
                node_map[node.element_id] = {
                    "element_id": node.element_id,
                    "name": node.get("name", ""),
                    "label": label,
                    "properties": dict(node.items()),
                }

            for rel in path.relationships:
                edge_key = (
                    rel.element_id,
                    rel.start_node.element_id,
                    rel.end_node.element_id,
                    rel.type,
                    tuple(sorted(rel.items())),
                )
                edge_map[edge_key] = {
                    "element_id": rel.element_id,
                    "start": rel.start_node.element_id,
                    "end": rel.end_node.element_id,
                    "type": rel.type,
                    "properties": dict(rel.items()),
                }

        return list(node_map.values()), list(edge_map.values())


# =========================
# Visualization
# =========================
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


def create_network(nodes, edges):
    net = Network(height="760px", width="100%", notebook=False, directed=True)
    net.barnes_hut()

    degree_map = {}
    for edge in edges:
        degree_map[edge["start"]] = degree_map.get(edge["start"], 0) + 1
        degree_map[edge["end"]] = degree_map.get(edge["end"], 0) + 1

    for node in nodes:
        color = NODE_COLORS.get(node["label"], DEFAULT_NODE_COLOR)
        degree = degree_map.get(node["element_id"], 0)
        size = 18 + min(degree * 2, 18)

        title = "<br>".join(
            [f"<b>{node['name']}</b>", f"Type: {node['label']}"] +
            [f"{k}: {v}" for k, v in list(node["properties"].items())[:8]]
        )

        net.add_node(
            node["element_id"],
            label=node["name"],
            title=title,
            color=color,
            size=size,
            font={"size": 18},
        )

    for edge in edges:
        pmcid = edge["properties"].get("PMCID", "")
        title = "<br>".join(
            [f"Type: {edge['type']}"] +
            [f"{k}: {v}" for k, v in edge["properties"].items()]
        )

        label = edge["type"]
        if pmcid:
            label = f"{edge['type']}"

        net.add_edge(
            edge["start"],
            edge["end"],
            label=label,
            title=title,
            color="#9E9E9E",
            arrows="to",
            smooth=False,
            font={"size": 12, "align": "middle"},
        )

    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -2500,
          "centralGravity": 0.2,
          "springLength": 140,
          "springConstant": 0.04,
          "damping": 0.9
        },
        "minVelocity": 0.75
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true
      },
      "nodes": {
        "shape": "dot"
      },
      "edges": {
        "selectionWidth": 2
      }
    }
    """)

    return net


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


# =========================
# UI
# =========================
if "node1" not in st.session_state:
    st.session_state.node1 = ""
if "node2" not in st.session_state:
    st.session_state.node2 = ""
if "type1" not in st.session_state:
    st.session_state.type1 = ""
if "type2" not in st.session_state:
    st.session_state.type2 = ""

with st.container(border=True):
    st.markdown("**Search filters**")
    c1, c2= st.columns(2)

    with c1:
        use_node1 = st.toggle("Set Node 1", value=bool(st.session_state.node1))

    c3, c4 = st.columns(2)
    with c3:
        st.session_state.node1 = st.text_input(
            "Node 1",
            value=st.session_state.node1 if use_node1 else "",
            disabled=not use_node1,
            placeholder="e.g. smoking",
        )

    with c4:
        type1_options = [""] + sorted(VALID_TYPES)

        if not use_node1:
            st.session_state.type1 = ""

        current_type1 = normalize_type(st.session_state.type1)
        type1_index = type1_options.index(current_type1) if current_type1 in type1_options else 0

        st.session_state.type1 = st.selectbox(
            "Type 1",
            options=type1_options,
            index=type1_index,
            disabled=not use_node1,
            help="Optional type filter for Node 1" if use_node1 else "Enable 'Set Node 1' first to choose Type 1",
        )

    c5, c6 = st.columns(2)
    with c5:
        use_node2= st.toggle("Set Node 2", value=bool(st.session_state.node2))

    c7, c8 = st.columns(2)
    with c7:
        st.session_state.node2 = st.text_input(
            "Node 2",
            value=st.session_state.node2 if use_node2 else "",
            disabled=not use_node2,
            placeholder="e.g. lung cancer",
        )

    with c8:
        type2_options = [""] + sorted(VALID_TYPES)

        if not use_node2:
            st.session_state.type2 = ""

        current_type2 = normalize_type(st.session_state.type2)
        type2_index = type2_options.index(current_type2) if current_type2 in type2_options else 0

        st.session_state.type2 = st.selectbox(
            "Type 2",
            options=type2_options,
            index=type2_index,
            disabled=not use_node2,
            help="Optional type filter for Node 2" if use_node2 else "Enable 'Set Node 2' first to choose Type 2",
        )

    c9, c10 = st.columns(2)
    with c9:
        hop = st.slider("Hop", min_value=1, max_value=5, value=2)
    with c10:
        limit = st.slider("Path limit", min_value=1, max_value=1000, value=100)

generate = st.button("Generate", type="primary", use_container_width=True)

if generate:
    try:
        nodes, edges = get_subgraph(
            st.session_state.node1,
            st.session_state.node2,
            st.session_state.type1,
            st.session_state.type2,
            hop,
            limit,
        )
    except Exception as e:
        st.error(f"Query failed: {e}")
        st.stop()

    if not nodes or not edges:
        st.warning("No matching subgraph was found under the current filters.")
        st.stop()

    m1, m2, m3 = st.columns(3)
    with m1:
        small_metric("Nodes", len(nodes))
    with m2:
        small_metric("Relationships", len(edges))
    with m3:
        small_metric("Hop / Limit", f"{hop} / {limit}")

    net = create_network(nodes, edges)
    html_content = net.generate_html()

    tab1, tab2 = st.tabs(["Graph", "Table"])

    with tab1:
        st.components.v1.html(html_content, height=780, scrolling=True)
        render_node_legend()

    with tab2:
        node_lookup = {node["element_id"]: node for node in nodes}

        data = {
            "Node": [],
            "Relationship": [],
            "Neighbor": [],
            "PMCID": [],
            "Info": [],
        }

        for edge in edges:
            start_node = node_lookup.get(edge["start"], {})
            end_node = node_lookup.get(edge["end"], {})

            data["Node"].append(
                f"{start_node.get('name', '')} ({start_node.get('label', '')})"
            )
            data["Relationship"].append(edge["type"])
            data["Neighbor"].append(
                f"{end_node.get('name', '')} ({end_node.get('label', '')})"
            )
            data["PMCID"].append(edge["properties"].get("PMCID", ""))
            info = {k: v for k, v in edge["properties"].items() if k != "PMCID"}
            data["Info"].append(info)

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)