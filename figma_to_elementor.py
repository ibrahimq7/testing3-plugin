#!/usr/bin/env python3
"""
Figma to Elementor Pro Layout Compiler
Converts figma_design_map.json into a valid Elementor Pro template JSON.
"""

import json
import sys
import hashlib
import time

def generate_deterministic_id(seed_string: str) -> str:
    """Generates a deterministic 7-character hexadecimal ID based on input string."""
    hash_object = hashlib.md5(seed_string.encode('utf-8'))
    return hash_object.hexdigest()[:7]

def flatten_hierarchy(node: dict, depth: int = 0, parent_path: str = "root") -> list:
    """
    Recursive layout converter and hierarchy optimizer.
    Flattens empty wrappers if depth > 4 and the wrapper adds no visual value.
    Returns a list of Elementor elements.
    """
    elements = []
    current_path = f"{parent_path}_{node['id']}"
    
    # Determine element type and settings
    node_type = node.get('type')
    layout_mode = node.get('layoutMode', 'NONE')
    
    # Base settings for all containers
    settings = {}
    is_container = False
    
    if node_type in ['FRAME', 'COMPONENT', 'INSTANCE']:
        is_container = True
        
        # Map Auto Layout to Flexbox
        if layout_mode == 'VERTICAL':
            settings['flex_direction'] = 'column'
        elif layout_mode == 'HORIZONTAL':
            settings['flex_direction'] = 'row'
            settings['flex_wrap'] = 'wrap'
        else:
            settings['flex_direction'] = 'column' # Default to column for frames
            
        # Map Spacing (Item Gap)
        if 'itemSpacing' in node and node['itemSpacing'] > 0:
            settings['gap'] = f"{node['itemSpacing']}px"
            
        # Map Padding
        padding_map = {}
        if node.get('paddingTop', 0) > 0: padding_map['top'] = f"{node['paddingTop']}px"
        if node.get('paddingRight', 0) > 0: padding_map['right'] = f"{node['paddingRight']}px"
        if node.get('paddingBottom', 0) > 0: padding_map['bottom'] = f"{node['paddingBottom']}px"
        if node.get('paddingLeft', 0) > 0: padding_map['left'] = f"{node['paddingLeft']}px"
        
        if padding_map:
            settings['padding'] = padding_map
            
        # Map Border Radius
        if 'cornerRadius' in node and node['cornerRadius'] > 0:
            radius_val = f"{node['cornerRadius']}px"
            settings['border_radius'] = {
                'top_left': radius_val,
                'top_right': radius_val,
                'bottom_right': radius_val,
                'bottom_left': radius_val
            }
            
        # Map Background Colors (Fills)
        if 'fills' in node and len(node['fills']) > 0:
            settings['background_color'] = node['fills'][0] # Take first solid color

    elif node_type == 'TEXT':
        # Text Node Handling
        font_size = node.get('fontSize', 16)
        settings['text'] = node.get('characters', '')
        settings['font_family'] = node.get('fontName', 'Default')
        settings['font_size'] = {'size': font_size, 'unit': 'px'}
        settings['line_height'] = {'size': round(font_size * 1.3, 2), 'unit': 'px'}
        
        # Decide between heading and text-editor based on simple heuristic (could be expanded)
        # For now, we treat all as text-editor for safety, or heading if large
        widget_type = 'heading' if font_size >= 24 else 'text-editor'
        if widget_type == 'heading':
            settings['header_size'] = 'h2' if font_size < 32 else 'h1'

    # Hierarchy Optimization (Flattening) Logic
    # If depth > 4 and this is a container with no specific styles (no bg, no radius, no padding),
    # we might consider flattening, BUT the prompt asks to discard wrapper if it pushes deeper than 4.
    # We implement a check: If we are about to create a wrapper at depth 4+, and it's "empty" style-wise,
    # we skip creating the wrapper element and just process children.
    
    should_flatten = False
    if depth >= 4 and is_container:
        # Check if "unstyled": no bg, no radius, no padding, default flex
        is_unstyled = (
            'background_color' not in settings and
            'border_radius' not in settings and
            'padding' not in settings and
            settings.get('flex_direction') == 'column' and # Default
            'gap' not in settings
        )
        if is_unstyled:
            should_flatten = True

    if should_flatten:
        # Skip this node's element creation, but process children at current depth
        if 'children' in node:
            for child in node['children']:
                elements.extend(flatten_hierarchy(child, depth, current_path))
        return elements

    # Create the Elementor Element Object
    element_id = generate_deterministic_id(current_path)
    
    element_data = {
        "id": element_id,
        "elType": "container" if is_container else "widget",
        "settings": settings,
        "elements": [] # Will hold children if container
    }
    
    if not is_container:
        element_data["widgetType"] = node_type.lower() if node_type == 'TEXT' else 'unknown'
        # Correction: Widget type needs to be specific Elementor widget name
        if node_type == 'TEXT':
            element_data["widgetType"] = 'heading' if settings.get('header_size') else 'text-editor'

    # Process Children
    if 'children' in node and len(node['children']) > 0:
        child_elements = []
        for child in node['children']:
            # If container, children go into 'elements' array of this element
            # If widget (text), it shouldn't have children in Figma usually, but handle safely
            if is_container:
                child_elements.extend(flatten_hierarchy(child, depth + 1, current_path))
            else:
                # Should not happen for Text nodes, but if it does, ignore or warn
                pass
        
        if is_container:
            element_data["elements"] = child_elements

    elements.append(element_data)
    return elements

def build_elementor_template(flat_elements: list) -> dict:
    """
    Wraps the structured nodes inside a valid Elementor Pro template schema.
    Since flatten_hierarchy returns a list of root-level elements (potentially multiple if top level was flattened),
    we need to ensure we have a single root or handle the structure correctly.
    Usually, Figma selection is one root. If flattened, we might have siblings.
    Elementor templates expect a list of elements at the root 'content' level.
    """
    
    # Construct the content array
    # The recursive function returns a list. If the original root was kept, list has 1 item.
    # If original root was flattened (unlikely for root unless deep recursion logic triggers immediately), 
    # it might have multiple. Elementor supports multiple top-level sections/containers.
    
    template = {
        "version": "0.4",
        "type": "page",
        "title": "Imported from Figma",
        "page_settings": [],
        "content": flat_elements
    }
    
    return template

def main():
    if len(sys.argv) < 2:
        print("Usage: python figma_to_elementor.py <input_figma_json>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = "final_elementor_import.json"

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            figma_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in '{input_file}'.")
        sys.exit(1)

    print(f"Processing {input_file}...")

    # Start recursion from the root of the parsed JSON
    # The input JSON is a single node tree usually
    converted_elements = flatten_hierarchy(figma_data, depth=0)

    if not converted_elements:
        print("Warning: No elements generated. Check input structure.")
        # Create empty valid template anyway
        final_template = build_elementor_template([])
    else:
        final_template = build_elementor_template(converted_elements)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_template, f, indent=2)

    print(f"Successfully compiled to {output_file}")

if __name__ == "__main__":
    main()
