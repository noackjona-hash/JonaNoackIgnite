# -*- coding: utf-8 -*-
"""gui/views package."""

from gui.views.dashboard_view import DashboardView
from gui.views.single_view import SingleInspectView
from gui.views.analytics_view import AnalyticsView
from gui.views.podology_view import PodologyView
from gui.views.batch_view import BatchView
from gui.views.settings_view import SettingsView

__all__ = [
    "DashboardView",
    "SingleInspectView",
    "AnalyticsView",
    "PodologyView",
    "BatchView",
    "SettingsView",
]
