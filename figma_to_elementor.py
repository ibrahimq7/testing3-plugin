#!/usr/bin/env python3
"""
Elementor Engine AI - Enterprise Figma to Elementor Compiler
Converts Figma JSON trees into pixel-perfect Elementor Pro templates.
"""

import sys
import json
import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# MODULE 1: DesignSystemKit
# Hardcoded "Industrial Sophistication" Design Tokens
# =============================================================================
class DesignSystemKit:
    """Central repository for design tokens and style constants."""
    
    COLORS = {
        "text_dark": "#0b1c30",
        "muted": "#44474d",
        "accent": "#0066FF",
        "surface": "#ffffff",
        "border": "#e2e8f0",
        "shadow": "0 20px 40px rgba(10, 25, 47, 0.05)"
    }
    
    RADIUS = {
        "card": 16,
        "button": 8
    }
    
    FONTS = {
        "heading": {"family": "Geist", "weight": "600"},
        "body": {"family": "Inter", "weight": "400"}
    }
    
    @staticmethod
    def get_shadow_css() -> str:
        return DesignSystemKit.COLORS["shadow"]

    @staticmethod
    def get_border_radius(style_type: str) -> int:
        return DesignSystemKit.RADIUS.get(style_type, 0)


# =============================================================================
# MODULE 2: IdRegistry
# Deterministic 7-character Hex ID Generator
# =============================================================================
class IdRegistry:
    """Generates unique, deterministic IDs for Elementor elements."""
    
    def __init__(self):
        self.counter = 0
    
    def generate(self, node_name: str, node_type: str, index: int) -> str:
        """
        Creates a 7-char hex hash based on node properties and an internal counter.
        Ensures uniqueness even for identical nodes.
        """
        seed = f"{node_name}{node_type}{index}{self.counter}"
        hash_obj = hashlib.md5(seed.encode('utf-8'))
        hex_digest = hash_obj.hexdigest().upper()
        self.counter += 1
        return hex_digest[:7]


# =============================================================================
# MODULE 3: FigmaTreeCompiler
# Core Recursive Compiler with Geometric Rules
# =============================================================================
class FigmaTreeCompiler:
    def __init__(self):
        self.id_registry = IdRegistry()
        self.max_depth_before_flatten = 4
    
    def compile(self, figma_tree: Dict[str, Any]) -> Dict[str, Any]:
        """Entry point to compile the entire tree into an Elementor template."""
        root_element = self._process_node(figma_tree, parent=None, depth=0, index=0)
        
        # Wrap in standard Elementor Page Template Schema
        template = {
            "version": "0.4",
            "type": "page",
            "content": [root_element],
            "page_settings": []
        }
        return template

    def _process_node(self, node: Dict[str, Any], parent: Optional[Dict], depth: int, index: int) -> Dict[str, Any]:
        """
        Recursive function to map Figma nodes to Elementor structures.
        Handles layout conversion, geometry calculation, and optimization.
        """
        node_type = node.get("type", "")
        node_name = node.get("name", "Unnamed")
        layout_mode = node.get("layoutMode", "NONE")
        
        # Generate deterministic ID
        element_id = self.id_registry.generate(node_name, node_type, index)
        
        # Initialize Elementor Element Structure
        element = {
            "id": element_id,
            "elType": "container",
            "settings": {},
            "elements": []
        }
        
        # ---------------------------------------------------------------------
        # STEP 1: Apply Layout & Geometry Settings
        # ---------------------------------------------------------------------
        settings = element["settings"]
        
        # Map Flex Direction
        if layout_mode == "HORIZONTAL":
            settings["flex_direction"] = "row"
            settings["flex_wrap"] = "wrap"
        elif layout_mode == "VERTICAL":
            settings["flex_direction"] = "column"
            settings["flex_wrap"] = "nowrap"
        else:
            # Default to column for frames without explicit auto-layout if they have children
            if node.get("children"):
                settings["flex_direction"] = "column"
                settings["flex_wrap"] = "nowrap"
            else:
                settings["flex_direction"] = "column"
                settings["flex_wrap"] = "nowrap"

        # Map Gaps (itemSpacing)
        if "itemSpacing" in node and node["itemSpacing"] is not None:
            gap_val = str(node["itemSpacing"])
            settings["gap"] = gap_val
            settings["element_gap"] = gap_val

        # Map Padding (Multi-linked)
        padding_map = {
            "padding_top": "paddingTop",
            "padding_right": "paddingRight",
            "padding_bottom": "paddingBottom",
            "padding_left": "paddingLeft"
        }
        
        has_padding = False
        for setting_key, figma_key in padding_map.items():
            if figma_key in node and node[figma_key] is not None:
                val = str(node[figma_key])
                settings[setting_key] = val
                settings[f"padding_${setting_key.split('_')[1]}$"] = {"unit": "px", "size": float(val)}
                has_padding = True
        
        if has_padding:
             settings["padding"] = {
                 "unit": "px", 
                 "top": str(node.get('paddingTop', 0)), 
                 "right": str(node.get('paddingRight', 0)), 
                 "bottom": str(node.get('paddingBottom', 0)), 
                 "left": str(node.get('paddingLeft', 0))
             }

        # Map Widths (Proportional Compiler)
        if parent and layout_mode != "NONE":
            width_config = self._compute_element_width(node, parent)
            if width_config:
                settings["width"] = width_config
                settings["width_tablet"] = width_config
                settings["width_mobile"] = {"unit": "%", "size": 100}

        # Map Border Radius
        if "cornerRadius" in node and node["cornerRadius"]:
            radius = str(node["cornerRadius"])
            settings["border_radius"] = {
                "unit": "px", 
                "top": radius, 
                "right": radius, 
                "bottom": radius, 
                "left": radius
            }
            
        # Map Background Colors (Fills)
        if "fills" in node and node["fills"]:
            if len(node["fills"]) > 0:
                color = node["fills"][0]
                settings["background_color"] = color
                settings["background_background"] = "classic"

        # ---------------------------------------------------------------------
        # STEP 2: Hierarchy Optimization (Anti-Bloat Guardrails)
        # ---------------------------------------------------------------------
        children_data = node.get("children", [])
        processed_children = []
        
        # Check for flattening condition: Depth > 4 AND only 1 child
        should_flatten = (depth > self.max_depth_before_flatten) and (len(children_data) == 1)
        
        # Process Children Recursively
        for idx, child in enumerate(children_data):
            child_element = self._process_node(child, node, depth + 1, idx)
            
            if should_flatten and child_element.get("elType") == "container":
                # If flattening, push child elements up one layer
                if "elements" in child_element:
                    processed_children.extend(child_element["elements"])
                else:
                    processed_children.append(child_element)
            else:
                processed_children.append(child_element)
        
        # ---------------------------------------------------------------------
        # STEP 3: Widget Conversion (Text Nodes)
        # ---------------------------------------------------------------------
        if node_type == "TEXT":
            text_content = node.get("characters", "")
            font_size = node.get("fontSize", 16)
            
            # Determine Widget Type based on character length and depth
            is_heading = len(text_content) < 50 or depth < 2
            widget_type = "heading" if is_heading else "text-editor"
            
            # Typography Calculations
            if is_heading:
                line_height = font_size * 1.3
                font_config = DesignSystemKit.FONTS["heading"]
                tag = "h2" if depth < 3 else "h4"
            else:
                line_height = font_size * 1.5
                font_config = DesignSystemKit.FONTS["body"]
                tag = "p"
            
            widget_id = self.id_registry.generate(node_name, "widget", index)
            
            widget_element = {
                "id": widget_id,
                "elType": "widget",
                "widgetType": widget_type,
                "settings": {
                    ("title" if is_heading else "editor"): text_content,
                    "align": "left",
                    "typography_typography": "custom",
                    "typography_font_family": font_config["family"],
                    "typography_font_weight": font_config["weight"],
                    "typography_font_size": {"unit": "px", "size": font_size},
                    "typography_line_height": {"unit": "em", "size": line_height / font_size},
                    "typography_text_color": DesignSystemKit.COLORS["text_dark"]
                },
                "elements": []
            }
            
            if is_heading:
                widget_element["settings"]["header_size"] = tag
            
            element["elements"] = [widget_element]
            element["elType"] = "container"
            
            if "justify_content" not in settings:
                settings["justify_content"] = "flex-start"
                
            return element

        # Attach processed children
        element["elements"] = processed_children
        
        return element

    def _compute_element_width(self, node: Dict[str, Any], parent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Mathematical method to calculate exact percentage allocation based on Figma dimensions.
        Implements the intelligent snap matrix.
        """
        node_width = node.get("width")
        parent_width = parent.get("width")
        
        if not node_width or not parent_width or parent_width == 0:
            return None
            
        # Only apply proportional width if parent is horizontal (Flex Row)
        parent_layout = parent.get("layoutMode", "NONE")
        if parent_layout != "HORIZONTAL":
            return None

        percentage = (node_width / parent_width) * 100
        
        # Count siblings to determine grid intent
        siblings = parent.get("children", [])
        sibling_count = len(siblings)
        
        snapped_size = None
        
        # Intelligent Snap Matrix
        # Rule 1: 21% - 26% OR 4 siblings -> 23.5%
        if (21 <= percentage <= 26) or sibling_count == 4:
            snapped_size = 23.5
            
        # Rule 2: 30% - 35% OR 3 siblings -> 31.3%
        elif (30 <= percentage <= 35) or sibling_count == 3:
            snapped_size = 31.3
            
        # Rule 3: 46% - 51% OR 2 siblings -> 48.0%
        elif (46 <= percentage <= 51) or sibling_count == 2:
            snapped_size = 48.0
            
        # Default: Exact rounded float
        if snapped_size is None:
            snapped_size = round(percentage, 2)
            
        return {"unit": "%", "size": snapped_size}


# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: python figma_to_elementor.py <input_figma_json> [output_elementor_json]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "final_elementor_import.json"
    
    try:
        # 1. Input Parser
        with open(input_file, 'r', encoding='utf-8') as f:
            figma_data = json.load(f)
        
        # Handle case where input is a list or a single node
        root_node = figma_data
        if isinstance(figma_data, list):
            root_node = figma_data[0]
            
        # 2. Compile Tree
        compiler = FigmaTreeCompiler()
        elementor_template = compiler.compile(root_node)
        
        # 3. Output Generation
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(elementor_template, f, indent=2)
            
        print(f"Successfully compiled '{input_file}' to '{output_file}'")
        print(f"Design System: Industrial Sophistication Applied")
        print(f"Optimization: Depth flattening enabled > {compiler.max_depth_before_flatten} layers")
        
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{input_file}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Critical Error during compilation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
