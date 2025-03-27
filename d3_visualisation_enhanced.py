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

def get_node_color_by_type(request_data):
    """
    Get color based on node type using existing classifications.
    
    Args:
        request_data: The request data with classification flags
    
    Returns:
        str: Color code for the node
    """
    # Check classification in order of priority
    if request_data.get('is_first_party', False):
        return "#2E7D32"  # Green for first-party
    elif request_data.get('is_ccm_provider', False):
        return "#1565C0"  # Blue for CCM provider
    elif request_data.get('is_analytics_library', False):
        return "#FFB300"  # Yellow for analytics
    elif request_data.get('is_third_party', False):
        return "#C62828"  # Red for third-party
    else:
        return "#78909C"  # Gray default

def prepare_data_for_d3_network(result, phase="Pre-consent"):
    """
    Transform network chain data into a format suitable for D3.js visualization
    using existing request classifications.
    
    Args:
        result (dict): The complete result object containing network chain data
        phase (str): The consent phase to visualize
        
    Returns:
        dict, str: Hierarchical data structure compatible with D3.js tree layout and CCM provider name
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
    
    # Get CCM provider name if available
    provider_name = None
    if "ccm_detection" in result_dict and "provider_name" in result_dict["ccm_detection"]:
        provider_name = result_dict["ccm_detection"]["provider_name"]
    
    # Extract the request chains based on the structure in your data and the phase
    chains = []
    network_requests = []
    
    if phase == "Post-consent; Cookies Rejected":
        if "reject_flow" in result_dict and "network_state" in result_dict["reject_flow"]:
            chains = result_dict["reject_flow"]["network_state"]["request_chains"]
            network_requests = result_dict["reject_flow"]["network_state"]["requests"]
    elif phase == "Post-consent; Cookies Accepted":
        if "accept_flow" in result_dict and "network_state" in result_dict["accept_flow"]:
            chains = result_dict["accept_flow"]["network_state"]["request_chains"]
            network_requests = result_dict["accept_flow"]["network_state"]["requests"]
    else:  # Default to Pre-consent
        if "page_landing" in result_dict and "state" in result_dict["page_landing"]:
            chains = result_dict["page_landing"]["state"]["network_state"]["request_chains"]
            network_requests = result_dict["page_landing"]["state"]["network_state"]["requests"]
    
    # Map requests by URL for easy lookup of classifications
    requests_by_url = {}
    for req in network_requests:
        requests_by_url[req.get('url', '')] = req
    
    # Get requested URL as root node
    if "url_info" in result_dict and "requested_url" in result_dict["url_info"]:
        root_url = result_dict["url_info"]["requested_url"]
    else:
        root_url = "Root"
    
    # Create root node (always consider it first-party)
    root_node = {
        "id": "root",
        "name": shorten_url(root_url),
        "fullUrl": root_url,
        "children": [],
        "color": "#2E7D32",  # Green for first-party
        "is_first_party": True,
        "is_third_party": False,
        "is_ccm_provider": False,
        "is_analytics_library": False
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
        
        # Determine cookie type for edge coloring
        cookie_type = "none"
        edge_color = "#78909C"  # Default gray
        
        if chain.get("sets_cookies"):
            for cookie in chain["sets_cookies"]:
                if cookie.get("type") == "third_party":
                    cookie_type = "third_party"
                    edge_color = "#C62828"  # Red
                    break
                elif cookie.get("type") == "first_party" and cookie_type != "third_party":
                    cookie_type = "first_party"
                    edge_color = "#2E7D32"  # Green
                elif cookie.get("type") == "ccm_provider" and cookie_type not in ["third_party", "first_party"]:
                    cookie_type = "ccm_provider"
                    edge_color = "#1565C0"  # Blue
        
        # Create nodes if they don't exist
        if source not in nodes_by_url:
            # Try to get classifications from the requests map
            source_data = requests_by_url.get(source, {})
            
            source_node = {
                "id": f"node_{len(nodes_by_url)}",
                "name": shorten_url(source),
                "fullUrl": source,
                "children": [],
                "is_first_party": source_data.get("is_first_party", False),
                "is_third_party": source_data.get("is_third_party", False),
                "is_ccm_provider": source_data.get("is_ccm_provider", False),
                "is_analytics_library": source_data.get("is_analytics_library", False),
                "color": get_node_color_by_type(source_data)
            }
            nodes_by_url[source] = source_node
        
        if target not in nodes_by_url:
            # Try to get classifications from the requests map
            target_data = requests_by_url.get(target, {})
            
            target_node = {
                "id": f"node_{len(nodes_by_url)}",
                "name": shorten_url(target),
                "fullUrl": target,
                "children": [],
                "is_first_party": target_data.get("is_first_party", False),
                "is_third_party": target_data.get("is_third_party", False),
                "is_ccm_provider": target_data.get("is_ccm_provider", False),
                "is_analytics_library": target_data.get("is_analytics_library", False),
                "color": get_node_color_by_type(target_data)
            }
            nodes_by_url[target] = target_node
        
        # Add target as child of source
        source_node = nodes_by_url[source]
        target_node = nodes_by_url[target]
        
        # Add edge data to the relationship
        target_node_with_edge = target_node.copy()
        target_node_with_edge["edgeColor"] = edge_color
        target_node_with_edge["cookieType"] = cookie_type
        
        # Check if this child already exists
        child_exists = any(child["id"] == target_node["id"] for child in source_node["children"])
        if not child_exists:
            source_node["children"].append(target_node_with_edge)
    
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
                orphan_node = nodes_by_url[orphan]
                # Add default edge coloring for orphans
                orphan_node_with_edge = orphan_node.copy()
                orphan_node_with_edge["edgeColor"] = "#78909C"  # Default gray
                orphan_node_with_edge["cookieType"] = "none"
                root_node["children"].append(orphan_node_with_edge)
    
    # Add node stats (count of children)
    for url, node in nodes_by_url.items():
        node["childCount"] = len(node["children"])
        # Add phase information
        node["phase"] = phase
    
    return root_node, provider_name

def generate_d3_visualization_html(data, title="Network Request Visualization", provider_name=None):
    """
    Generate an enhanced D3.js visualization with color-coded nodes and edges plus a legend.
    Includes panning and zooming capabilities.
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
            max-width: 100%;
            margin: 0 auto;
            padding: 20px;
            position: relative;
        }}
        h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        #chart-container {{
            width: 100%;
            height: 700px;
            border: 1px solid #ddd;
            position: relative;
        }}
        .node circle {{
            stroke-width: 1.5px;
        }}
        .node text {{
            font: 12px sans-serif;
            text-shadow: 0 1px 0 #fff, 0 -1px 0 #fff, 1px 0 0 #fff, -1px 0 0 #fff;
            pointer-events: none;
            white-space: nowrap;
        }}
        .link {{
            fill: none;
            stroke-width: 1.5px;
        }}
        #legend {{
            position: absolute;
            top: 80px;
            right: 30px;
            background: white;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            z-index: 100;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 15px;
            height: 15px;
            margin-right: 8px;
            border-radius: 50%;
            border: 1px solid #ddd;
        }}
        .legend-line {{
            width: 20px;
            height: 3px;
            margin-right: 8px;
        }}
        .legend-title {{
            font-weight: bold;
            margin-top: 8px;
            margin-bottom: 4px;
        }}
        .zoom-controls {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            z-index: 100;
        }}
        .zoom-btn {{
            background: #f8f8f8;
            border: 1px solid #ddd;
            margin: 0 2px;
            padding: 5px 10px;
            cursor: pointer;
            border-radius: 3px;
        }}
        .zoom-btn:hover {{
            background: #e8e8e8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div id="chart-container">
            <!-- Zoom controls -->
            <div class="zoom-controls">
                <button class="zoom-btn" id="zoom-in">+</button>
                <button class="zoom-btn" id="zoom-out">−</button>
                <button class="zoom-btn" id="zoom-reset">Reset</button>
            </div>
        </div>
        
        <!-- Legend outside the chart -->
        <div id="legend">
            <div class="legend-title">Node Types</div>
            <div class="legend-item">
                <div class="legend-color" style="background:#2E7D32;"></div>
                <div>First Party</div>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background:#1565C0;"></div>
                <div>CCM Provider{f" ({provider_name})" if provider_name else ""}</div>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background:#FFB300;"></div>
                <div>Analytics Container</div>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background:#C62828;"></div>
                <div>Third Party</div>
            </div>
            
            <div class="legend-title">Connection Types</div>
            <div class="legend-item">
                <div class="legend-line" style="background:#2E7D32;"></div>
                <div>Sets First Party Cookie</div>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background:#1565C0;"></div>
                <div>Sets CCM Provider Cookie</div>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background:#C62828;"></div>
                <div>Sets Third Party Cookie</div>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background:#78909C;"></div>
                <div>No Cookies Set</div>
            </div>
        </div>
    </div>

    <script src="https://d3js.org/d3.v5.min.js"></script>
    <script>
        // Load the data
        const treeData = {json_data};
        console.log("Tree data:", treeData);
        
        // Set dimensions with ample space for all nodes
        const width = 1400;
        const height = 650;
        const margin = {{top: 40, right: 280, bottom: 40, left: 120}};
        
        // Create SVG with zoom support
        const svg = d3.select("#chart-container")
            .append("svg")
            .attr("width", "100%")
            .attr("height", height)
            .call(d3.zoom().on("zoom", function() {{
                g.attr("transform", d3.event.transform);
            }}))
            .append("g");
        
        // This is our main group that will be transformed during zoom
        const g = svg.append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
        
        // Create hierarchy
        const root = d3.hierarchy(treeData);
        
        // Create tree layout
        const tree = d3.tree()
            .size([height - margin.top - margin.bottom, width - margin.left - margin.right]);
        
        // Compute the tree layout
        tree(root);
        
        // Add links between nodes with color based on cookie type
        g.selectAll(".link")
            .data(root.links())
            .enter()
            .append("path")
            .attr("class", "link")
            .style("stroke", d => d.target.data.edgeColor || "#78909C")
            .attr("d", d3.linkHorizontal()
                .x(d => d.y)
                .y(d => d.x));
        
        // Add nodes
        const node = g.selectAll(".node")
            .data(root.descendants())
            .enter()
            .append("g")
            .attr("class", "node")
            .attr("transform", d => "translate(" + d.y + "," + d.x + ")");
        
        // Add circles to nodes with color based on node type
        node.append("circle")
            .attr("r", 5)
            .style("fill", d => d.data.color || "#78909C");
        
        // Add text labels with text shadow for better readability
        node.append("text")
            .attr("dy", ".35em")
            .attr("x", d => d.children ? -10 : 10)
            .attr("text-anchor", d => d.children ? "end" : "start")
            .text(d => d.data.name);
        
        // Zoom controls functionality
        document.getElementById('zoom-in').addEventListener('click', function() {{
            // Get the current zoom transform
            const transform = d3.zoomTransform(svg.node());
            // Apply new zoom transform with scale increased by 1.2
            svg.call(d3.zoom().transform, transform.scale(1.2));
        }});
        
        document.getElementById('zoom-out').addEventListener('click', function() {{
            // Get the current zoom transform
            const transform = d3.zoomTransform(svg.node());
            // Apply new zoom transform with scale decreased by 0.8
            svg.call(d3.zoom().transform, transform.scale(0.8));
        }});
        
        document.getElementById('zoom-reset').addEventListener('click', function() {{
            // Reset to initial transform
            svg.call(d3.zoom().transform, d3.zoomIdentity.translate(margin.left, margin.top));
        }});
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
    data, provider_name = prepare_data_for_d3_network(result, phase)
    
    # Generate HTML with D3 visualization
    title = f"Network Request Visualization - {phase}"
    html_content = generate_d3_visualization_html(data, title, provider_name)
    
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
    data, provider_name = prepare_data_for_d3_network(result, phase)
    
    # Generate HTML with D3 visualization
    title = f"Network Request Visualization - {phase}"
    html_content = generate_d3_visualization_html(data, title, provider_name)
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Visualization saved to {filename}")