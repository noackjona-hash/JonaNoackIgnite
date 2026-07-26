def _patch_customtkinter_linux():
    try:
        from customtkinter.windows.widgets.ctk_scrollable_frame import CTkScrollableFrame
        from customtkinter.windows.widgets.ctk_scrollbar import CTkScrollbar
        from customtkinter.windows.widgets.ctk_slider import CTkSlider
        from customtkinter.windows.widgets.ctk_textbox import CTkTextbox

        def _safe_check_if_valid_scroll(self, widget):
            if widget == self._parent_canvas:
                return True
            elif isinstance(widget, (CTkScrollbar, CTkSlider, CTkTextbox)):
                return False
            elif isinstance(widget, CTkScrollableFrame):
                return widget._parent_canvas == self._parent_canvas
            elif isinstance(widget, str):
                try:
                    widget_obj = self._parent_canvas.nametowidget(widget)
                    return self._check_if_valid_scroll(widget_obj)
                except Exception:
                    return False
            elif hasattr(widget, "master") and widget.master is not None:
                return self._check_if_valid_scroll(widget.master)
            else:
                return False

        CTkScrollableFrame._check_if_valid_scroll = _safe_check_if_valid_scroll
    except Exception:
        pass

_patch_customtkinter_linux()

from gui.services.export_service import ExportService
from gui.services.processing_service import ThermalProcessingService
from gui.components.controls_panel import ParameterControlsPanel
from gui.components.thermal_canvas import ThermalCanvasWidget

__all__ = [
    "ExportService",
    "ThermalProcessingService",
    "ParameterControlsPanel",
    "ThermalCanvasWidget",
]
