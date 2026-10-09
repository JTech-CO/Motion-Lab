"""Closed, shared analysis vocabulary for assets, public filters and MCP."""

ANALYSIS_VERSION = 1
ASSET_TYPES = ("animation", "transition", "typography", "interaction", "background",
               "loader", "palette", "gradient", "shader", "reference", "pattern", "shape", "material")
EFFECTS = ("fade", "slide", "scale", "rotate", "flip", "spring", "shake", "pulse",
           "mask", "glitch", "pixel", "wave", "text", "stagger", "blur", "other")
COMPONENTS = ("text", "shape", "image", "particles", "grid", "stroke", "mask", "layer", "color")
TECHNIQUES = ("keyframes", "transition", "transform", "pseudo-element", "clip-path",
              "filter", "gradient", "glsl", "texture-sampling", "procedural-noise",
              "color-values", "reference-link", "svg-animation", "svg-geometry", "image-texture", "static-design")
USE_CASES = ("intro", "outro", "scene-change", "status", "attention", "feedback",
             "ambient", "color-system", "reference", "design-kit")
RENDERERS = ("css", "glsl", "svg", "palette", "gradient", "image", "none")
BASES = ("code", "color-values", "reviewed-source", "metadata", "image")
DOMAINS = ("motion", "design")
ANALYSIS_FILTERS = {"asset_type": ASSET_TYPES, "effect": EFFECTS,
                    "component": COMPONENTS, "use_case": USE_CASES, "basis": BASES, "domain": DOMAINS}
