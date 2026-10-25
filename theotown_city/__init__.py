"""TheoTown .city parser (read-only).

Split into small modules:
- format: file layout, header, pixels, tagged values
- ground: ground-type list and parsing
- analysis: scalars, heights, terrain stats
- images: minimap / preview PNG export, plus an overlay map
- objects: string-table parser for trees, roads, buildings, rails
- cli: command-line interface
"""

__version__ = "1.3.0"
__all__ = ["load_city", "analyse", "export_images", "export_overlay"]

from .format import load_city
from .analysis import analyse
from .images import export_images, export_overlay
