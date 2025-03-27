from urllib.parse import urlparse
from dataclasses import asdict
import networkx as nx
from urllib.parse import urlparse
import matplotlib.pyplot as plt
from networkx.drawing.nx_agraph import graphviz_layout

def normalize_url(url: str) -> str:
    """
    Normalizes URLs by removing 'http://', 'https://', and 'www.' prefixes.
    For example: 'https://www.example.com' becomes 'example.com'
    """
    # Remove http:// or https://
    if "://" in url:
        url = url.split("://", 1)[1]
    
    # Remove www.
    if url.startswith("www."):
        url = url[4:]
        
    return url

def shorten_url(url):
    """
    For example, 'https://abc.com/page/something' becomes 'abc.com/page'.
    """
    try:
        # First normalize the URL
        url = normalize_url(url)
        parsed = urlparse(f"http://{url}")  # Add scheme to make urlparse work correctly
        netloc = parsed.netloc
        # Process the path: strip leading/trailing slashes and split by '/'
        if parsed.path and parsed.path != "/":
            parts = parsed.path.strip("/").split("/")
            if parts:
                return f"{netloc}/{parts[0]}"
        return netloc
    except Exception:
        # In case of any parsing error, return the original URL.
        return url
    
def collapse_url(url: str, requested_url: str, max_path_sections: int = 2) -> str:
    """
    Collapses URLs, with special handling for the requested_url:
    - If URL starts with requested_url, return requested_url
    - Otherwise collapse normally
    """
    try:
        # Normalize both URLs before comparison
        normalized_url = normalize_url(url)
        normalized_requested = normalize_url(requested_url)
        
        # Check if this URL is or starts with the requested_url
        if normalized_url.startswith(normalized_requested):
            return requested_url
            
        parsed = urlparse(f"http://{normalized_url}")  # Add scheme to make urlparse work correctly
        netloc = parsed.netloc or "unknown"
        # Split path into segments, ignoring empty parts
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        # Keep only up to 'max_path_sections' segments
        collapsed = "/".join(path_parts[:max_path_sections])
        return f"{netloc}/{collapsed}" if collapsed else netloc
    except Exception:
        return url

def get_node_color(short_label: str) -> str:
    """Assigns colors to nodes based on their domain."""
    lower_label = short_label.lower()
    
    # Mapping from keyword substring -> color
    keyword_to_color = {
        "facebook": "blue",
        "amazon": "orange",
        "tiktok": "black",
        "abbott": "royalblue",
        "hubspot": "orange",
        "hs-analytics": "orange",
        "google": "yellow",
        "googletagmanager": "yellow",
        "doubleclick": "yellow",
        "trustarc": "green",
    }
    
    # Return the first match or default to gray
    for keyword, color in keyword_to_color.items():
        if keyword in lower_label:
            return color
    return "gray"

def draw_network_graph(result, hierarchical=False, collapse=False, make_url_short=False, phase="Pre-consent"):
    # Convert the dataclass to a dictionary for dictionary-style access
    result_dict = asdict(result)
    requested_url = result_dict["url_info"]["requested_url"]

    # Extract the request chains
    if phase == "Post-consent; Cookies Rejected":
        chains = result_dict["reject_flow"]["network_state"]["request_chains"]
    elif phase == "Post-consent; Cookies Accepted":
        chains = result_dict["accept_flow"]["network_state"]["request_chains"]
    else:
        chains = result_dict["page_landing"]["state"]["network_state"]["request_chains"]

    # We will build a new directed graph that uses "collapsed" node labels
    G = nx.DiGraph()
    
    # A mapping from the collapsed node label -> set of raw URLs (to track how many)
    node_map = {}
    
    # Process chains and build the graph
    if collapse:
        # Collapse and build the graph
        for chain in chains:
            raw_src = chain.get("source", "unknown")
            raw_tgt = chain.get("target", "unknown")
            
            src = collapse_url(raw_src, requested_url, max_path_sections=2)
            tgt = collapse_url(raw_tgt, requested_url, max_path_sections=2)
            
            node_map.setdefault(src, set()).add(raw_src)
            node_map.setdefault(tgt, set()).add(raw_tgt)
            
            G.add_edge(src, tgt, type=chain.get("type", "unknown"))
    else:
        for chain in chains:
            src = chain.get("source", "unknown")
            tgt = chain.get("target", "unknown")
            
            # Even when not collapsing URLs, we still want to consolidate the requested_url
            if normalize_url(src).startswith(normalize_url(requested_url)):
                src = requested_url
            if normalize_url(tgt).startswith(normalize_url(requested_url)):
                tgt = requested_url
                
            # When not collapsing, each node represents exactly one URL
            node_map.setdefault(src, set()).add(src)
            node_map.setdefault(tgt, set()).add(tgt)
            G.add_edge(src, tgt, type=chain.get("type", "unknown"))
    
    # Find orphan nodes (nodes with no incoming edges except requested_url)
    all_nodes = set(G.nodes())
    nodes_with_incoming = {v for u, v in G.edges()}
    orphan_nodes = all_nodes - nodes_with_incoming - {requested_url}
    
    # Add edges from requested_url to orphan nodes
    for orphan in orphan_nodes:
        G.add_edge(requested_url, orphan, type="unknown")
    
    # Build labels and node colors
    labels = {}
    node_colors = []
    for node in G.nodes():
        raw_count = len(node_map[node])  # Distinct raw URLs
        if make_url_short:
            short_label = f"{shorten_url(node)} ({raw_count})"  # e.g. "abc.com/page (3)"
            labels[node] = short_label
        else:
            labels[node] = f"{node} ({raw_count})"
        color = get_node_color(node)
        node_colors.append(color)
    
    # Choose a layout
    if hierarchical:
        # Requires graphviz installed
        # rankdir=TB means top-to-bottom flow
        pos = graphviz_layout(G, prog='dot', args='-Grankdir=TB')
    else:
        # Default: force-directed layout
        pos = nx.spring_layout(G, seed=42)
    
    # Draw
    plt.figure(figsize=(24, 16))
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=500)
    nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=20, edge_color='gray')
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    
    layout_name = "Hierarchical (Top-Down)" if hierarchical else "Spring"
    plt.title(f"Network Request Chains for {requested_url} - {phase} phase")
    plt.axis("off")
    plt.show()