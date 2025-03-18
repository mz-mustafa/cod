"""
Network Visualization Module

This module provides functions to transform network request chain data
into formats suitable for visualization with D3.js.
"""
import json
from urllib.parse import urlparse

def normalize_url(url: str) -> str:
    """
    Normalizes URLs by removing 'http://', 'https://', and 'www.' prefixes.
    
    Args:
        url (str): The URL to normalize
        
    Returns:
        str: Normalized URL
    """
    # Remove http:// or https://
    if "://" in url:
        url = url.split("://", 1)[1]
    
    # Remove www.
    if url.startswith("www."):
        url = url[4:]
        
    return url

def shorten_url(url: str) -> str:
    """
    Shortens a URL for display purposes.
    For example, 'https://abc.com/page/something' becomes 'abc.com/page'.
    
    Args:
        url (str): The URL to shorten
        
    Returns:
        str: Shortened URL
    """
    try:
        # First normalize the URL
        url = normalize_url(url)
        parsed = urlparse(f"http://{url}")  # Add scheme to make urlparse work
        netloc = parsed.netloc
        
        # Process the path: strip leading/trailing slashes and split by '/'
        if parsed.path and parsed.path != "/":
            parts = parsed.path.strip("/").split("/")
            if parts:
                return f"{netloc}/{parts[0]}"
        return netloc
    except Exception:
        # In case of any parsing error, return the original URL
        return url

def get_domain_color(url: str) -> str:
    """
    Assigns colors to nodes based on their domain.

    Args:
        url (str): The URL to analyze

    Returns:
        str: Color code or name for the domain
    """
    lower_url = url.lower()
    
    # Mapping from keyword substring -> color
    domain_colors = {
        "facebook": "#4267B2",  # Facebook blue
        "amazon": "#FF9900",    # Amazon orange
        "tiktok": "#000000",    # TikTok black
        "abbott": "#006EB7",    # Abbott blue
        "hubspot": "#FA5C4F",   # HubSpot coral
        "hs-analytics": "#FA5C4F",  # HubSpot coral
        "google": "#4285F4",    # Google blue
        "googletagmanager": "#4285F4",  # Google blue
        "doubleclick": "#4285F4",  # Google blue
        "trustarc": "#4CAF50",  # Green
        "analytics": "#F57C00",  # Analytics - orange
        "tracking": "#E53935",  # Tracking - red
        "ad": "#E53935",        # Ad-related - red
        "cdn": "#7B1FA2",       # CDN - purple
    }
    
    # Return the first match or default to gray
    for keyword, color in domain_colors.items():
        if keyword in lower_url:
            return color
    return "#78909C"  # Default: blue-gray

def prepare_data_for_d3_network(result, phase="Pre-consent"):
    """
    Transform network chain data into a format suitable for D3.js tree visualization.
    
    Args:
        result (dict): The complete result object containing network chain data
        phase (str): The consent phase to visualize
        
    Returns:
        dict: Hierarchical data structure compatible with D3.js tree layout
    """
    # Convert to dictionary if it's not already
    if hasattr(result, '__dict__'):
        try:
            from dataclasses import asdict
            result_dict = asdict(result)
        except:
            result_dict = vars(result)
    else:
        result_dict = result
        
    # Extract the request chains based on the structure in your data and the phase
    if phase == "Post-consent; Cookies Rejected":
        if "reject_flow" in result_dict and "network_state" in result_dict["reject_flow"]:
            chains = result_dict["reject_flow"]["network_state"]["request_chains"]
        else:
            chains = []
    elif phase == "Post-consent; Cookies Accepted":
        if "accept_flow" in result_dict and "network_state" in result_dict["accept_flow"]:
            chains = result_dict["accept_flow"]["network_state"]["request_chains"]
        else:
            chains = []
    else:  # Default to Pre-consent
        if "page_landing" in result_dict and "state" in result_dict["page_landing"]:
            chains = result_dict["page_landing"]["state"]["network_state"]["request_chains"]
        elif "network_state" in result_dict and "request_chains" in result_dict["network_state"]:
            chains = result_dict["network_state"]["request_chains"]
        else:
            chains = []
    
    # Get requested URL as root node
    if "url_info" in result_dict and "requested_url" in result_dict["url_info"]:
        root_url = result_dict["url_info"]["requested_url"]
    else:
        root_url = "Root"
    
    # Create root node
    root_node = {
        "id": "root",
        "name": shorten_url(root_url),
        "fullUrl": root_url,
        "children": [],
        "color": get_domain_color(root_url)
    }
    
    # Keep track of nodes by URL
    nodes_by_url = {root_url: root_node}
    
    # Track processed edges to avoid duplicates
    processed_edges = set()
    
    # Process chains to build tree
    for chain in chains:
        source = chain.get("source", "unknown")
        target = chain.get("target", "unknown")
        
        # Skip self-referential links
        if source == target:
            continue
        
        # Create edge identifier
        edge_id = f"{source}|{target}"
        if edge_id in processed_edges:
            continue
        
        processed_edges.add(edge_id)
        
        # Create nodes if they don't exist
        if source not in nodes_by_url:
            source_node = {
                "id": f"node_{len(nodes_by_url)}",
                "name": shorten_url(source),
                "fullUrl": source,
                "children": [],
                "color": get_domain_color(source)
            }
            nodes_by_url[source] = source_node
        
        if target not in nodes_by_url:
            target_node = {
                "id": f"node_{len(nodes_by_url)}",
                "name": shorten_url(target),
                "fullUrl": target,
                "children": [],
                "color": get_domain_color(target)
            }
            nodes_by_url[target] = target_node
        
        # Add target as child of source
        source_node = nodes_by_url[source]
        target_node = nodes_by_url[target]
        
        # Check if this child already exists
        child_exists = any(child["id"] == target_node["id"] for child in source_node["children"])
        if not child_exists:
            source_node["children"].append(target_node)
    
    # Find orphan nodes (nodes with no incoming edges)
    all_nodes = set(nodes_by_url.keys())
    nodes_with_incoming = set()
    
    for url, node in nodes_by_url.items():
        for child in node["children"]:
            nodes_with_incoming.add(child["fullUrl"])
    
    orphans = all_nodes - nodes_with_incoming - {root_url}
    
    # Connect orphans to root
    for orphan in orphans:
        if orphan != root_url:
            # Check if this orphan already exists as a child
            orphan_exists = any(child["fullUrl"] == orphan for child in root_node["children"])
            if not orphan_exists:
                root_node["children"].append(nodes_by_url[orphan])
    
    # Add node stats (count of children)
    for url, node in nodes_by_url.items():
        node["childCount"] = len(node["children"])
        # Add phase information
        node["phase"] = phase
    
    return root_node

def generate_d3_visualization_html(data, title="Network Request Visualization"):
    """
    Generate a simplified, more robust D3.js visualization.
    """
    json_data = json.dumps(data)
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #333;
        }}
        #chart-container {{
            width: 100%;
            height: 700px;
            border: 1px solid #ddd;
            overflow: auto;
        }}
        .node circle {{
            fill: #fff;
            stroke: steelblue;
            stroke-width: 1.5px;
        }}
        .node text {{
            font: 12px sans-serif;
        }}
        .link {{
            fill: none;
            stroke: #ccc;
            stroke-width: 1.5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div id="chart-container"></div>
    </div>

    <script src="https://d3js.org/d3.v5.min.js"></script>
    <script>
        // Load the data
        const treeData = {json_data};
        console.log("Tree data:", treeData);
        
        // Set dimensions
        const width = 1000;
        const height = 600;
        const margin = {{top: 40, right: 120, bottom: 40, left: 120}};
        
        // Create SVG
        const svg = d3.select("#chart-container")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
        
        // Create hierarchy
        const root = d3.hierarchy(treeData);
        
        // Create tree layout
        const tree = d3.tree()
            .size([height - margin.top - margin.bottom, width - margin.left - margin.right]);
        
        // Compute the tree layout
        tree(root);
        
        // Add links between nodes
        svg.selectAll(".link")
            .data(root.links())
            .enter()
            .append("path")
            .attr("class", "link")
            .attr("d", d3.linkHorizontal()
                .x(d => d.y)
                .y(d => d.x));
        
        // Add nodes
        const node = svg.selectAll(".node")
            .data(root.descendants())
            .enter()
            .append("g")
            .attr("class", "node")
            .attr("transform", d => "translate(" + d.y + "," + d.x + ")");
        
        // Add circles to nodes
        node.append("circle")
            .attr("r", 5)
            .style("fill", d => d.data.color || "steelblue");
        
        // Add text labels
        node.append("text")
            .attr("dy", ".35em")
            .attr("x", d => d.children ? -10 : 10)
            .attr("text-anchor", d => d.children ? "end" : "start")
            .text(d => d.data.name);
    </script>
</body>
</html>
    """

def display_network_visualization(result, phase="Pre-consent"):
    """
    Function to use in Jupyter notebook to visualize network data.
    
    Args:
        result: The network analysis result
        phase: The consent phase to visualize
        
    Returns:
        IPython.display.HTML: HTML display object
    """
    from IPython.display import HTML, display
    
    # Prepare data for D3 tree
    data = prepare_data_for_d3_network(result, phase)
    
    # Generate HTML with D3 visualization
    title = f"Network Request Visualization - {phase}"
    html_content = generate_d3_visualization_html(data, title)
    
    # Add an iframe to avoid interference with notebook styling
    iframe_content = f"""
    <iframe srcdoc='{html_content.replace("'", "&apos;")}' width='100%' height='800px' style='border:1px solid #ddd;'></iframe>
    """
    
    return HTML(iframe_content)

def save_visualization_html(result, filename="network_visualization.html", phase="Pre-consent"):
    """
    Save visualization as a standalone HTML file.
    
    Args:
        result: The network analysis result
        filename: Output HTML filename
        phase: The consent phase to visualize
    """
    # Prepare data for D3 tree
    data = prepare_data_for_d3_network(result, phase)
    
    # Generate HTML with D3 visualization
    title = f"Network Request Visualization - {phase}"
    html_content = generate_d3_visualization_html(data, title)
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Visualization saved to {filename}")