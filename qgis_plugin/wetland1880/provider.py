from pathlib import Path

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .algorithm import Wetland1880Algorithm


class Wetland1880Provider(QgsProcessingProvider):
    def loadAlgorithms(self):
        self.addAlgorithm(Wetland1880Algorithm())

    def id(self):
        return "wetland1880"

    def name(self):
        return "Wetland 1880 Reader"

    def icon(self):
        return QIcon(str(Path(__file__).parent / "icon.png"))
