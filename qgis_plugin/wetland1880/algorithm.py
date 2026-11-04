"""Processing algorithm: read wet land from the Prussian survey map 1878-80."""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr
from qgis.core import (QgsProcessingParameterDefinition, QgsProcessingParameterNumber,
                       QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
                       QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
                       QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
                       QgsProcessingLayerPostProcessorInterface,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFile, QgsProcessingParameterRasterLayer,
                       QgsProcessingUtils, QgsProject, QgsRectangle, QgsSettings, QgsWkbTypes)
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon

from . import rules

HERE = Path(__file__).parent
MODELS = HERE / "models"
TUFT_MODEL = MODELS / "tufts_round1.pt"
TORF_MODEL = MODELS / "torfstich_round2.pt"
CONF = {"tuft": 0.20, "torfstich": 0.20}
TILE_M, TILE_PX = 320, 640
TARGET = "EPSG:25832"
SETTING = "wetland1880/python"


class StylePostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None

    def postProcessLayer(self, layer, context, feedback):
        layer.loadNamedStyle(str(HERE / "style_1880.qml"))
        layer.triggerRepaint()

    @staticmethod
    def create():
        StylePostProcessor.instance = StylePostProcessor()
        return StylePostProcessor.instance


class Wetland1880Algorithm(QgsProcessingAlgorithm):
    INPUT, AOI, PYTHON, OUTPUT, POINTS = "INPUT", "AOI", "PYTHON", "OUTPUT", "POINTS"
    HEATH = "HEATH_TUFTS"

    def tr(self, s):
        return QCoreApplication.translate("Wetland1880", s)

    def createInstance(self):
        return Wetland1880Algorithm()

    def name(self):
        return "classify1880"

    def displayName(self):
        return self.tr("Classify 1878–80 map (YOLO + rules)")

    def group(self):
        return ""

    def groupId(self):
        return ""

    def icon(self):
        return QIcon(str(HERE / "icon.png"))

    def shortHelpString(self):
        return self.tr(
            "Reads moor (Moor), wet meadow (nasse Wiese) and heath (Heide) from the Prussian survey "
            "map 1878–80 (Preußische Landesaufnahme, e.g. the WCS 'Chronologen' of LVermGeo SH, "
            "exported at 1 m).\n\n"
            "A small YOLO model finds tufts and peat cuttings (Torfstich); dashes are found by "
            "image analysis per field; the rules of the 1898 map key turn them into classes on a "
            "25 m grid.\n\n"
            "Needs a Python environment with Ultralytics (pip install ultralytics) – give its "
            "python.exe. Everything runs on your own computer.\n\n"
            "Tested on the Treene–Sorge lowland: 93 % ± 4 % overall accuracy in a blind check. "
            "Other landscapes (marsh, raised bogs) have not been checked – look at the result "
            "before using it.\n\n"
            "Bonnie Winter · https://github.com/bonnietilse-design/peatland-rewetting-sh · "
            "Map © GeoBasis-DE/LVermGeo SH/CC BY 4.0")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, self.tr("1878–80 map, 1 m (black = ink)")))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.AOI, self.tr("Area of interest (optional)"),
            [QgsProcessing.TypeVectorPolygon], optional=True))
        p = QgsProcessingParameterFile(
            self.PYTHON, self.tr("python.exe of the environment with Ultralytics"),
            behavior=QgsProcessingParameterFile.File,
            defaultValue=QgsSettings().value(SETTING, ""))
        self.addParameter(p)
        h = QgsProcessingParameterNumber(
            self.HEATH, self.tr("Tufts per 75 m needed for Heide (1 = as tuned; 2 removes single "
                                "false tufts in dense dry meadow)"),
            QgsProcessingParameterNumber.Integer, defaultValue=1, minValue=1, maxValue=6)
        h.setFlags(h.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(h)
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr("1880 classes"), QgsProcessing.TypeVectorPolygon))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.POINTS, self.tr("Detected symbols"), QgsProcessing.TypeVectorPoint,
            optional=True, createByDefault=False))

    # ------------------------------------------------------------------ helpers
    def _prepare_map(self, raster, aoi_geom, tmp, feedback):
        """Warp to EPSG:25832 at 1 m and convert to an ink mask (1 = ink, 0 = paper)."""
        src = raster.source()
        bounds = None
        if aoi_geom is not None:
            b = aoi_geom.boundingBox()
            bounds = (int(b.xMinimum()) - 1, int(b.yMinimum()) - 1,
                      int(b.xMaximum()) + 2, int(b.yMaximum()) + 2)
        warped = str(tmp / "map_1m.tif")
        # srcNodata "None": in the raw WCS data 0 means ink, never "no data";
        # areas outside the map become 255 (= paper)
        gdal.Warp(warped, src, dstSRS=TARGET, xRes=1, yRes=1, targetAlignedPixels=True,
                  outputBounds=bounds, resampleAlg="near", srcNodata="None", dstNodata=255,
                  creationOptions=["COMPRESS=DEFLATE", "TILED=YES", "BIGTIFF=IF_SAFER"])
        ds = gdal.Open(warped)
        if ds is None:
            raise QgsProcessingException("Could not reproject the map.")
        W, H = ds.RasterXSize, ds.RasterYSize
        band = ds.GetRasterBand(1)
        mx = band.ComputeRasterMinMax(True)[1]
        thr = 0.5 if mx <= 1 else mx / 2          # 0/1 raw WCS data or grey/colour image
        ink_path = str(tmp / "ink_1m.tif")
        out = gdal.GetDriverByName("GTiff").Create(ink_path, W, H, 1, gdal.GDT_Byte,
                                                   options=["COMPRESS=DEFLATE", "TILED=YES",
                                                            "BIGTIFF=IF_SAFER"])
        out.SetGeoTransform(ds.GetGeoTransform())
        out.SetProjection(ds.GetProjection())
        ob = out.GetRasterBand(1)
        for y in range(0, H, 2000):
            h = min(2000, H - y)
            a = band.ReadAsArray(0, y, W, h)
            ob.WriteArray(((a < thr) & (a != 255)).astype(np.uint8), 0, y)
            if feedback.isCanceled():
                return None
        gt = ds.GetGeoTransform()
        ds = out = None
        feedback.pushInfo(f"map: {W} × {H} m")
        return ink_path, gt, W, H

    def _make_tiles(self, ink_path, gt, W, H, aoi_geom, tile_dir, feedback):
        ds = gdal.Open(ink_path)
        band = ds.GetRasterBand(1)
        n, written = 0, 0
        rows, cols = -(-H // TILE_M), -(-W // TILE_M)
        for r in range(rows):
            for c in range(cols):
                n += 1
                if feedback.isCanceled():
                    return 0
                x0, y1 = gt[0] + c * TILE_M, gt[3] - r * TILE_M
                if aoi_geom is not None and not aoi_geom.intersects(
                        QgsGeometry.fromRect(QgsRectangle(x0, y1 - TILE_M, x0 + TILE_M, y1))):
                    continue
                xs, ys = min(TILE_M, W - c * TILE_M), min(TILE_M, H - r * TILE_M)
                a = band.ReadAsArray(c * TILE_M, r * TILE_M, xs, ys)
                if not a.any():
                    continue
                img = np.full((TILE_PX, TILE_PX), 255, np.uint8)
                img[: ys * 2, : xs * 2] = np.where(np.repeat(np.repeat(a, 2, 0), 2, 1) > 0, 0, 255)
                mem = gdal.GetDriverByName("MEM").Create("", TILE_PX, TILE_PX, 1, gdal.GDT_Byte)
                mem.SetGeoTransform((x0, 0.5, 0, y1, 0, -0.5))
                mem.GetRasterBand(1).WriteArray(img)
                gdal.GetDriverByName("PNG").CreateCopy(str(tile_dir / f"r{r:04d}_c{c:04d}.png"), mem,
                                                       options=["WORLDFILE=YES"])
                written += 1
            feedback.setProgress(5 + 10 * (r + 1) / rows)
        feedback.pushInfo(f"tiles with ink: {written}")
        return written

    def _run_yolo(self, python, tile_dir, out_csv, feedback):
        for m in (TUFT_MODEL, TORF_MODEL):
            if not m.exists():
                raise QgsProcessingException(f"Model file missing: {m}")
        env = {k: v for k, v in os.environ.items()
               if k.upper() not in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "QGIS_PREFIX_PATH")}
        pdir = Path(python).parent
        keep = [p for p in env.get("PATH", "").split(os.pathsep)
                if p and not any(s in p.lower() for s in ("qgis", "osgeo4w"))]
        env["PATH"] = os.pathsep.join([str(pdir), str(pdir / "Scripts"),
                                       str(pdir / "Library" / "bin")] + keep)
        cmd = [python, str(HERE / "yolo_worker.py"), str(tile_dir), str(out_csv),
               f"{TUFT_MODEL}:tuft:{CONF['tuft']}", f"{TORF_MODEL}:torfstich:{CONF['torfstich']}"]
        flags = 0x08000000 if sys.platform == "win32" else 0      # CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env=env, creationflags=flags)
        log = []
        for line in proc.stdout:
            line = line.strip()
            if feedback.isCanceled():
                proc.kill()
                return False
            if line.startswith("PROGRESS"):
                feedback.setProgress(15 + 0.45 * float(line.split()[1]))
            elif line:
                log.append(line)
                if line.startswith("DONE"):
                    feedback.pushInfo(f"detections: {line.split()[1]}")
        if proc.wait() != 0:
            raise QgsProcessingException("The YOLO step failed:\n" + "\n".join(log[-25:]) +
                                         "\n\nIs Ultralytics installed in this Python? "
                                         f"({python} -m pip install ultralytics)")
        return True

    # ------------------------------------------------------------------ main
    def processAlgorithm(self, parameters, context, feedback):
        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        python = self.parameterAsFile(parameters, self.PYTHON, context)
        if not python or not Path(python).exists():
            raise QgsProcessingException("Give the python.exe of an environment with Ultralytics.")
        QgsSettings().setValue(SETTING, python)
        crs = QgsCoordinateReferenceSystem(TARGET)

        aoi_geom = None
        src = self.parameterAsSource(parameters, self.AOI, context)
        if src is not None:
            tr = QgsCoordinateTransform(src.sourceCrs(), crs, QgsProject.instance())
            geoms = []
            for f in src.getFeatures():
                g = QgsGeometry(f.geometry())
                g.transform(tr)
                geoms.append(g)
            aoi_geom = QgsGeometry.unaryUnion(geoms)

        tmp = Path(QgsProcessingUtils.tempFolder()) / "wetland1880"
        tile_dir = tmp / "tiles"
        tile_dir.mkdir(parents=True, exist_ok=True)
        for old in tile_dir.glob("*"):
            old.unlink()

        feedback.pushInfo("1/4 preparing the map ...")
        prep = self._prepare_map(raster, aoi_geom, tmp, feedback)
        if prep is None:
            return {}
        ink_path, gt, W, H = prep
        feedback.pushInfo("2/4 cutting tiles ...")
        if not self._make_tiles(ink_path, gt, W, H, aoi_geom, tile_dir, feedback):
            raise QgsProcessingException("No map symbols found in the area.")
        feedback.pushInfo("3/4 finding tufts and peat cuttings (YOLO) ...")
        det_csv = tmp / "detections.csv"
        if not self._run_yolo(python, tile_dir, det_csv, feedback):
            return {}
        det = list(csv.DictReader(det_csv.open(encoding="utf-8")))

        feedback.pushInfo("4/4 dashes, fields and rules ...")
        P = json.loads((HERE / "rule_parameters.json").read_text(encoding="utf-8"))

        def px(cls):
            a = np.array([[float(d["x"]) - gt[0], gt[3] - float(d["y"])] for d in det
                          if d["cls"] == cls])
            return a.reshape(-1, 2)
        ds = gdal.Open(ink_path)
        t_heath = self.parameterAsInt(parameters, self.HEATH, context)
        grid = rules.classes(ds.GetRasterBand(1), W, H, px("tuft"), px("torfstich"), P, feedback,
                             t_heath=max(t_heath, P["t_min"]))
        if grid is None:
            return {}
        n_r, n_c = grid.shape
        cell = rules.CELL
        proj = ds.GetProjection()
        ds = None

        mem = gdal.GetDriverByName("MEM").Create("", n_c, n_r, 1, gdal.GDT_Byte)
        mem.SetGeoTransform((gt[0], cell, 0, gt[3], 0, -cell))
        mem.SetProjection(proj)
        if aoi_geom is not None:
            mask = gdal.GetDriverByName("MEM").Create("", n_c, n_r, 1, gdal.GDT_Byte)
            mask.SetGeoTransform((gt[0], cell, 0, gt[3], 0, -cell))
            mask.SetProjection(proj)
            ods = ogr.GetDriverByName("Memory").CreateDataSource("aoi")
            srs = osr.SpatialReference()
            srs.ImportFromWkt(proj)
            lyr = ods.CreateLayer("aoi", srs, ogr.wkbMultiPolygon)
            f = ogr.Feature(lyr.GetLayerDefn())
            f.SetGeometry(ogr.CreateGeometryFromWkt(aoi_geom.asWkt()))
            lyr.CreateFeature(f)
            gdal.RasterizeLayer(mask, [1], lyr, burn_values=[1])
            grid = np.where(mask.GetRasterBand(1).ReadAsArray() > 0, grid, 0)
            mask = ods = None
        mem.GetRasterBand(1).WriteArray(grid.astype(np.uint8))

        pds = ogr.GetDriverByName("Memory").CreateDataSource("p")
        srs = osr.SpatialReference()
        srs.ImportFromWkt(proj)
        pl = pds.CreateLayer("p", srs, ogr.wkbPolygon)
        pl.CreateField(ogr.FieldDefn("code", ogr.OFTInteger))
        band = mem.GetRasterBand(1)
        gdal.Polygonize(band, band, pl, 0)

        fields = QgsFields()
        fields.append(QgsField("hist_type", QVariant.String))
        fields.append(QgsField("code", QVariant.Int))
        fields.append(QgsField("area_ha", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields,
                                          QgsWkbTypes.Polygon, crs)
        for f in pl:
            code = f.GetField("code")
            if not code:
                continue
            g = QgsGeometry.fromWkt(f.GetGeometryRef().ExportToWkt())
            qf = QgsFeature(fields)
            qf.setGeometry(g)
            qf.setAttributes([rules.NAMES[code], int(code), g.area() / 1e4])
            sink.addFeature(qf, QgsFeatureSink.FastInsert)
        results = {self.OUTPUT: dest}

        pfields = QgsFields()
        pfields.append(QgsField("symbol", QVariant.String))
        pfields.append(QgsField("conf", QVariant.Double))
        psink, pdest = self.parameterAsSink(parameters, self.POINTS, context, pfields,
                                            QgsWkbTypes.Point, crs)
        if psink is not None:
            for d in det:
                qf = QgsFeature(pfields)
                qf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(d["x"]), float(d["y"]))))
                qf.setAttributes([d["cls"], float(d["conf"])])
                psink.addFeature(qf, QgsFeatureSink.FastInsert)
            results[self.POINTS] = pdest

        if context.willLoadLayerOnCompletion(dest):
            context.layerToLoadOnCompletionDetails(dest).setPostProcessor(StylePostProcessor.create())
        ha = rules.CELL * rules.CELL / 1e4
        for code in (1, 2, 3):
            feedback.pushInfo(f"{rules.NAMES[code]}: {(grid == code).sum() * ha:,.0f} ha")
        return results
