// Figma Plugin: Elementor Engine AI - Structural Data Extraction Layer
// code.ts

// 1. UI LIFECYCLE: Launch the user interface panel
figma.showUI(__html__, { width: 320, height: 400 });

// Helper function to convert Figma RGBA to Hex string
function rgbaToHex(color: RGBA): string {
  const r = Math.round(color.r * 255);
  const g = Math.round(color.g * 255);
  const b = Math.round(color.b * 255);
  const a = color.a < 1 ? Math.round(color.a * 255).toString(16).padStart(2, '0') : '';
  
  const toHex = (c: number) => c.toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}${a}`;
}

// Helper function to extract solid fills as hex array
function extractFills(fills: ReadonlyArray<Paint>): string[] {
  const hexColors: string[] = [];
  if (fills && fills !== figma.mixed) {
    for (const paint of fills) {
      if (paint.type === 'SOLID' && paint.color && paint.opacity !== undefined) {
        const colorWithOpacity: RGBA = {
          r: paint.color.r,
          g: paint.color.g,
          b: paint.color.b,
          a: paint.opacity
        };
        hexColors.push(rgbaToHex(colorWithOpacity));
      }
    }
  }
  return hexColors;
}

// 4. RECURSIVE NODE TRAVERSAL FUNCTION
async function serializeFigmaNode(node: SceneNode): Promise<any> {
  // Base properties for all nodes
  const baseData: any = {
    id: node.id,
    name: node.name,
    type: node.type
  };

  // Handle Text Nodes
  if (node.type === 'TEXT') {
    const textNode = node as TextNode;
    // Ensure font name is loaded before accessing fontFamily
    await figma.loadFontAsync(textNode.fontName);
    
    baseData.characters = textNode.characters;
    baseData.fontSize = textNode.fontSize;
    baseData.fontFamily = textNode.fontName.fontFamily;
    
    return baseData;
  }

  // Handle Frame-like Nodes (FRAME, COMPONENT, INSTANCE, GROUP)
  const frameLikeTypes = ['FRAME', 'COMPONENT', 'INSTANCE', 'GROUP'];
  
  if (frameLikeTypes.includes(node.type)) {
    const frameNode = node as FrameNode | ComponentNode | InstanceNode | GroupNode;
    
    // Layout properties (available on frames and auto-layout containers)
    if ('layoutMode' in frameNode) {
      baseData.layoutMode = frameNode.layoutMode; // VERTICAL, HORIZONTAL, NONE
      baseData.itemSpacing = frameNode.itemSpacing;
      baseData.paddingTop = frameNode.paddingTop;
      baseData.paddingRight = frameNode.paddingRight;
      baseData.paddingBottom = frameNode.paddingBottom;
      baseData.paddingLeft = frameNode.paddingLeft;
      baseData.primaryAxisAlignItems = frameNode.primaryAxisAlignItems;
      baseData.counterAxisAlignItems = frameNode.counterAxisAlignItems;
    }

    // Dimensions
    baseData.widths = frameNode.width;
    baseData.heights = frameNode.height;

    // Corner Radius
    if ('cornerRadius' in frameNode) {
      baseData.cornerRadius = frameNode.cornerRadius;
    } else if ('topLeftRadius' in frameNode) {
      // For nodes with individual corner radii
      baseData.cornerRadius = {
        topLeft: frameNode.topLeftRadius,
        topRight: frameNode.topRightRadius,
        bottomLeft: frameNode.bottomLeftRadius,
        bottomRight: frameNode.bottomRightRadius
      };
    }

    // Fills (extract solid colors as hex)
    if ('fills' in frameNode) {
      baseData.fills = extractFills(frameNode.fills);
    }

    // 5. RECURSIVE WALK: Process children if they exist
    if ('children' in frameNode && frameNode.children) {
      baseData.children = [];
      for (const child of frameNode.children) {
        const childData = await serializeFigmaNode(child);
        baseData.children.push(childData);
      }
    }
  } else {
    // Handle other node types (RECTANGLE, ELLIPSE, etc.) if needed
    // For now, we focus on Frames, Components, Instances, and Text as requested
    // but we can add basic properties for completeness
    if ('width' in node) {
      baseData.widths = (node as any).width;
      baseData.heights = (node as any).height;
    }
    if ('fills' in node) {
      baseData.fills = extractFills((node as any).fills);
    }
    if ('children' in node) {
      baseData.children = [];
      for (const child of (node as any).children) {
        const childData = await serializeFigmaNode(child);
        baseData.children.push(childData);
      }
    }
  }

  return baseData;
}

// 2. EVENT LISTENER: Listen for 'export-layout' message from UI
figma.ui.onmessage = async (msg: { type: string }) => {
  if (msg.type === 'export-layout') {
    // 3. SELECTION PARSER: Retrieve the active node
    const selection = figma.currentPage.selection;
    
    if (selection.length === 0 || !selection[0]) {
      figma.notify("Please select a parent frame first");
      return;
    }

    const rootNode = selection[0];

    try {
      // Serialize the selected node and its children
      const serializedTree = await serializeFigmaNode(rootNode);

      // 6. MESSAGE DISPATCHER: Send the compiled JSON tree back to UI
      figma.ui.postMessage({
        type: 'design-tree-ready',
        payload: serializedTree
      });
    } catch (error) {
      figma.notify("Error processing selection: " + (error as Error).message);
      console.error(error);
    }
  }
};
