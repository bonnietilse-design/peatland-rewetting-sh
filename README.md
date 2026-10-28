# Moorvernässung in Schleswig-Holstein

**Deutsch** | [English](README.en.md)

Wo liegen die Moorböden in Schleswig-Holstein, wie werden sie genutzt, wie viel emittieren sie – und wo wäre eine Wiedervernässung am sinnvollsten?

Ein QGIS-/Open-Source-Portfolioprojekt von **Bonnie Winter** (2026).

> Alle Emissionszahlen sind **Schätzungen** (Fläche × nationale Emissionsfaktoren) und als solche gekennzeichnet. Alle Schritte liefen in einem **Testgebiet** von 304 km² in der Sorgeniederung (Meggerdorf, Bergenhusen, Tetenhusen); mit `TEST_MODE = False` in `config.py` laufen dieselben Schritte für das ganze Land.

## Hintergrund

Laut Land Schleswig-Holstein (Moor-Klimaschutz, Jan. 2024) bedecken kohlenstoffreiche Böden rund 152.800 ha (≈ 10 % der Landesfläche). Über 81 % davon werden landwirtschaftlich genutzt, und sie verursachen etwa 17 % der Treibhausgasemissionen des Landes.

## Wichtigste Ergebnisse (Testgebiet)

| Frage | Ergebnis | Schritt |
|---|---|---|
| Wie viel landwirtschaftliche Fläche liegt auf organischem Boden? | **11.102 ha** – 10.824 ha Grünland, 278 ha Acker | 03 |
| Wie viel emittiert sie? | **≈ 354.000 t CO2-Äq./Jahr** (Schätzung); ≈ 293.000 t/Jahr ließen sich durch Vernässung der gesamten Fläche einsparen | 04 |
| Wie unsicher ist das? | 90-%-Bereich 351.000–358.000 t, wenn sich Fehler auf Feldebene ausgleichen; 144.000–487.000 t, wenn das ganze Gebiet vom deutschen Mittel abweicht – die Wahrheit liegt dazwischen | 08 |
| Wo sollte die Vernässung beginnen? | Für 75.000 t/Jahr Einsparung: Mit **78 ganzen Teileinzugsgebieten** werden nur **44 ha** Acker/Grünland auf Mineralboden mitvernässt – wählt man stattdessen die besten **Flurstücke**, sind 121–220 Einzugsgebiete betroffen und **4.500–7.200 ha** Mineralboden werden als Nebeneffekt nass | 05, 07 |
| Lässt sich die Karte von 1880 automatisch lesen? | Ein kleines **YOLO26**-Modell, auf meinem eigenen Rechner mit von Hand gelabelten Kacheln trainiert, plus regelbasierte Strichdetektion reproduziert meine Handdigitalisierung auf **91 %** der nicht zum Abstimmen genutzten Fläche (κ = 0,87) – und erreicht **93 % ± 4 %** Genauigkeit (flächengewichtet) in einer blinden 100-Punkte-Prüfung im übrigen Testgebiet | 06x–06v |
| Wie haben sich die nassen Flächen seit 1880 verändert? | Handdigitalisierter Block (36 km²): **92 %** der auf der Karte von 1878–80 nass dargestellten Fläche sind heute noch organischer Boden. Ganzes Testgebiet (304 km², automatisiert): **88 %** (10.441 von 11.872 ha). *Moor* von 1880 ≈ heutiges Hochmoor; ein Fünftel bis ein Drittel der nassen Wiesen von 1880 ist heute **Moorfolgeboden** (Torf weitgehend verloren); etwa 5.500 ha des heutigen Niedermoors waren schon 1880 entwässerte Weide oder trockene Wiese | 06 |
| Waren die ausgewählten Teileinzugsgebiete 1880 nass? | Ja: **68 %** der Fläche der 78 ausgewählten Teileinzugsgebiete waren auf der Karte von 1878–80 nass, gegenüber 40 % der übrigen Kandidaten – obwohl Schritt 07 nichts von 1880 wusste. Werden 1880 nasse Flächen bevorzugt, steigt dieser Anteil am vernässten Moor-Grünland/-Acker von 66 % auf 85 %, bei ~90 ha mehr mitvernässtem Mineralboden | 07b |

![Nasse Flächen 1878–80 vs. organische Böden heute, ganzes Testgebiet](outputs/06_historical_yolo_test_catchment.png)

## Methoden

| Schritt | Skript | Methode | Werkzeuge |
|---|---|---|---|
| 00 | `00_check_inputs.py` | Bestandsaufnahme der Eingangsdaten: KBS, Felder, Beispielwerte | GeoPandas, pyogrio |
| 01 | `01_prepare_dgm1.py` | 355 DGM1-Kacheln über den amtlichen Massendownload-Index, XYZ → GeoTIFF, Aufnahmejahre | GDAL, urllib + truststore |
| 02 | `02_prepare_inputs.py` | Umprojizieren, reparieren, auf das Untersuchungsgebiet zuschneiden → ein GeoPackage | GeoPandas |
| 03 | `03_overlay_soils_landuse.py` | Organische Böden × Acker/Grünland (Feldblöcke 2026), je Gemeinde | GeoPandas |
| 04 | `04_emission_estimate.py` | Fläche × implizite Emissionsfaktoren (Tiemeyer et al. 2020) | pandas |
| 05 | `05_hydrology.py` | DGM auf 5 m (Minimum), amtliches Gewässernetz 3 m tief eingebrannt (Stream Burning), Abflussakkumulation, Gewässerlinien, 350 Teileinzugsgebiete | GDAL, GRASS `r.watershed` über `qgis_process` |
| 06 | `06_historical_loss.py` | Nässesignaturen der Preußischen Landesaufnahme 1878–80 vs. heutige Bodenkarte – handdigitalisierter Block oder automatisierte Ebene für das ganze Testgebiet (`yolo`) | QGIS, GeoPandas, Shapely |
| 07 | `07_optimisation.py` | Mindestfläche für ein CO2-Ziel: Flurstücks-Ranking, Flurstücks-Optimum, Einzugsgebiets-Optimum | SciPy `milp` / HiGHS (binäre ganzzahlige Optimierung) |
| 07b | `07b_history_per_catchment.py` | Die Karte von 1880 je Teileinzugsgebiet: nasser Anteil, Moorfolgeboden, ausgewählte vs. übrige Gebiete, Sensitivitätslauf von 07 mit Vorrang für 1880 nasse Flächen | GeoPandas, SciPy `milp` |
| 08 | `08_monte_carlo.py` | 10.000 Läufe, schiefe (zweiteilige Normal-)Verteilung der Emissionsfaktoren, zwei Korrelationsszenarien | NumPy, SciPy |
| 09 | `09_export_maps_pyqgis.py` | Atlas: eine A4-Seite je Gemeinde mit ≥ 50 ha landwirtschaftlich genutztem Moor (24 Seiten) – [Webversion](docs/atlas_gemeinden_web.pdf) | PyQGIS |

**Stream Burning (Schritt 05).** In flachem Niedermoor sind viele Gräben schmaler als eine 5-m-Zelle oder verlaufen durch Durchlässe, sodass ein Abflussmodell auf dem reinen DGM Gewässer neben die echten Wasserläufe legt. Ich senke das DGM entlang des amtlichen Gewässernetzes (ATKIS Basis-DLM, 1.885 km Linien im Testgebiet, viele davon Feldgräben) um 3 m ab, bevor `r.watershed` läuft. Die modellierten Gewässer folgen jetzt den Flüssen und Gräben; die Zahl der Teileinzugsgebiete sinkt von 367 auf 350, und das CO2-Ziel in Schritt 07 wird mit 78 statt 82 davon erreicht. Breite Flüsse werden nur entlang ihrer Mittellinie eingebrannt, daher kann im Flussbett ein zweiter, paralleler Wasserlauf übrig bleiben.

Jeder Schritt schreibt einen kurzen Bericht nach [`docs/reports/`](docs/reports/). Eine ausführliche Erläuterung des ganzen Projekts (44 Seiten) steht in [`docs/peatland_project_report_2026-10-26_de.pdf`](docs/peatland_project_report_2026-10-26_de.pdf); die Abbildungen darin sind englisch beschriftet. Englische Fassung: [`docs/peatland_project_report_2026-10-26.pdf`](docs/peatland_project_report_2026-10-26.pdf).

### Historische Karte (Schritt 06)

Die Blätter von 1878–80 habe ich von Hand im Maßstab 1:2.500–1:5.000 digitalisiert. Erfasst wurde die Legendenklasse, die die Karte zeigt, nicht eine Interpretation:

| hist_type | Legende 1898 | Hinweis auf Torf |
|---|---|---|
| Moor | Sumpf, Bruch, Moor (Grasbüschel + Striche, Torfstich) | sicher |
| nasser Boden / nasse Wiese | nasser Boden / nasse Wiese | wahrscheinlich |
| Heide | Heide, nur in der Niederung | möglich |

Hutung, trockene Wiese, Sand, Acker und Ortschaften wurden nicht digitalisiert. Die Bedeutung der Signaturen stammt aus der amtlichen *Zeichen-Erklärung für die Messtischblätter* (1898) – siehe [`docs/digitising_legend.png`](docs/digitising_legend.png) und die Regeln in [`docs/historical_peat_digitising_rules.xlsx`](docs/historical_peat_digitising_rules.xlsx). Der Vergleich umfasst nur die tatsächlich geprüfte Fläche (`digitised_extent`). Ob Lücken an Wegen und Gräben bis 15 m oder bis 30 m geschlossen werden, ändert jede Kategorie um ≤ 1 %.

### Die Karte von 1880 automatisch lesen (Schritte 06x–06c)

Handdigitalisierung lässt sich nicht über wenige Blätter hinaus skalieren. Deshalb habe ich getestet, ob sich dieselben Klassen automatisch ableiten lassen. Alles läuft lokal auf einer CPU.

| Schritt | Skript | Was es tut |
|---|---|---|
| 06x | `06x_make_tiles.py` | 1-m-GeoTIFF des Blocks (WCS) → 361 Kacheln à 320 m, auf 640 px vergrößert, damit ein Grasbüschel ~25 px groß wird |
| – | QGIS | Ich habe jedes Grasbüschel (Punkt) und jeden *Torfstich* (Rechteck) in 32 Kacheln gelabelt, davon 11 Kacheln ohne Signaturen |
| 06y | `06y_labels_to_yolo.py` | Labels → YOLO-Format; räumliche Aufteilung 24 / 4 / 4 Kacheln (benachbarte Kacheln bleiben zusammen, nach Inhalt geschichtet) |
| – | Ultralytics | `yolo26n`, CPU, `scale=0.2` (damit die winzigen Signaturen nicht weiter verkleinert werden), Abbruch bei Epoche 124 |
| 06z | `06z_point_check.py` | punktbasierte Prüfung: Eine Signatur gilt als gefunden, wenn eine Detektion innerhalb von 8 m liegt |
| 06b | `06b_predict.py` | Detektion auf allen 361 Kacheln, Duplikate zusammengeführt → Kartenkoordinaten |
| 06c | `06c_detections_to_polygons.py` | Strichfilter + Grasbüschel + Torfstich → Klassen von 1880 auf einem 25-m-Raster; abgestimmt auf der Westhälfte, geprüft auf der Osthälfte |
| 06v | `06v_accuracy_check.py` | blinde Genauigkeitsprüfung: 100 geschichtete Zufallspunkte außerhalb des Blocks, von mir auf der Karte abgelesen, flächengewichtete Genauigkeit (Olofsson et al. 2014) |

**Signaturerkennung** (4 Testkacheln, die nie im Training waren, Konfidenz ≥ 0,20, vor dem Zusammenführen von Duplikaten): Grasbüschel Recall 0,75 / Precision 0,59; Torfstich 3 von 4 gefunden. Das Modell findet die meisten Grasbüschel, aber mit niedriger Konfidenz; der Schwellenwert ist deshalb wichtiger als der übliche Standardwert.

**Striche** werden ohne maschinelles Lernen erkannt: flache Tintenmarken (≤ 3 m hoch, 5–40 m lang) sind die Striche von *Bruch* und *nasser Wiese*; gepunktete Hutungsreihen, Schrift, Gebäude und Feldgrenzen fallen aus diesen Grenzen heraus. Die Strichdichte allein trennt nasse von nicht nassen Flächen fast so gut wie die Handdigitalisierung (AUC 0,97).

**Regeln** sind die der Handdigitalisierung: Grasbüschel + Striche → Moor; wiederkehrender Torfstich → Moor; nur Striche → nasse Wiese; Heide neben wiederkehrendem Torfstich oder an ein größeres Moor anschließend → Moor („Heide im Moor“). Die letzte Regel kam hinzu, nachdem ein erster Lauf das entwässerte Königsmoor als Heide eingestuft hatte (κ 0,76 → 0,85); sie stammt aus den Digitalisierregeln, nicht aus den Prüfdaten.

| Fläche | Übereinstimmung mit Handdigitalisierung | κ |
|---|---:|---:|
| Westhälfte (zum Abstimmen genutzt) | 84 % | 0,74 |
| **Osthälfte (nicht genutzt)** | **91 %** | **0,87** |

![Handdigitalisierung vs. YOLO + Regeln](outputs/06c_yolo_vs_hand_test_catchment.png)

Auf der Osthälfte wird Moor mit einer IoU von 0,91 und nasse Wiese mit 0,76 reproduziert (die Automatisierung zeichnet nasse Wiese etwas zu weit, bis in dichte Hutungsreihen); die kleine Klasse Heide (29 ha) wird kaum reproduziert, und Moornamen werden nicht erkannt. Plan und Labelanleitung: [`docs/yolo_plan.md`](docs/yolo_plan.md), [`docs/labelling_guide.png`](docs/labelling_guide.png). Ultralytics steht unter der AGPL-3.0.

### Anwendung auf das ganze Testgebiet

Dasselbe Modell und die auf dem Block abgestimmten Schwellenwerte (ohne neues Abstimmen) habe ich auf das ganze Testgebiet angewendet: 3.119 Kacheln, etwa 20 Minuten auf einer Laptop-CPU. Innerhalb des Blocks stimmt das Ergebnis weiterhin zu 87 % mit meiner Handdigitalisierung überein (κ 0,81). Die endgültige Ebene nutzt die Grasbüschel des ersten Modells und die Torfstiche des zweiten (11.943 Grasbüschel, 1.129 Torfstiche) und misst die Strichdichte je Feld – siehe *Zweite Trainingsrunde* und *Strichdichte je Feld* unten.

![Klassen von 1880 für das ganze Testgebiet](outputs/06c_yolo_aoi_test_catchment.png)

Zwölf Stichprobenkacheln außerhalb des Blocks zeigten keine Fehldetektionen auf Schrift, Feldgrenzen oder Ortschaften, verpassten aber steil gezeichnete Torfstiche und einige größere, anders gezeichnete Grasbüschel. Ein erster Lauf machte eine trockene Heide bei Friedrichsneuland zu Moor, weil die Grundlinien der Grasbüschel als Striche zählten und die Regel „Heide im Moor“ sich über die ganze Heide ausbreitete. Beides habe ich behoben (Grundlinien innerhalb von 10 m eines Grasbüschels werden ignoriert; Heide schließt sich nur einem mindestens gleich großen Moor an); auf dem Block bleibt das Prüfergebnis dabei unverändert (κ 0,85 → 0,86). Automatisch erkannte Heide zählt nicht zur nassen Fläche von 1880, da es überwiegend Geestheide ist.

**Blinde Genauigkeitsprüfung** (`06v`): 100 Zufallspunkte außerhalb des Blocks, 25 je kartierter Klasse, die ich auf der Karte von 1880 eingestuft habe, ohne die Vorhersage zu sehen.

| Klasse | Kartiert (ha) | Nutzergenauigkeit | Herstellergenauigkeit | Geschätzt (ha, ± 95 %) |
|---|---:|---:|---:|---:|
| Moor | 3.690 | 0,89 | 0,93 | 3.714 ± 726 |
| nasse Wiese | 5.881 | 0,86 | 0,86 | 4.754 ± 1.668 |
| Heide | 831 | 0,89 | 0,78 | 910 ± 393 |
| keine | 16.356 | 0,96 | 0,96 | 17.381 ± 1.605 |
| **Gesamtgenauigkeit** | | **93 % ± 4 %** | | |

Moor ist zuverlässig; nasse Wiese ist weiterhin die unsicherste Klasse, daher ist die „verlorene“ Fläche im Vergleich über das ganze Gebiet (1.431 ha) eine Obergrenze.

### Zweite Trainingsrunde

Die Stichproben zeigten drei Schwachstellen: diagonal oder waagerecht gezeichnete Torfstiche, große fächerförmige Grasbüschel und nasse Wiese, die in Hutungsreihen hineinreicht. Ich habe 10 weitere Kacheln außerhalb des Blocks gelabelt, die die ersten beiden abdecken (181 Grasbüschel, 36 Torfstiche), ausgewählt abseits der 100 Prüfpunkte, damit die blinde Prüfung unabhängig bleibt. Sie kamen nur ins Training; Validierungs- und Testkacheln blieben gleich. Das Modell wurde mit moderater Rotation (±30°, ohne vertikales Spiegeln – Grasbüschel stehen immer aufrecht) neu trainiert. Die Hutungsreihen sind ein Problem der Strichregel, nicht des Modells; mehr Labels können sie nicht beheben.

| Blinde Prüfung, 100 Punkte | Runde 1 | Runde 2 | Grasbüschel Runde 1 + Torfstiche Runde 2 |
|---|---:|---:|---:|
| Gesamtgenauigkeit | 90 % ± 6 % | 90 % ± 6 % | **91 % ± 6 %** |
| Moor, Nutzer- / Herstellergen. | 0,92 / 0,86 | 0,84 / 0,89 | 0,90 / 0,93 |
| Heide, Nutzer- / Herstellergen. | 0,84 / 0,69 | 0,92 / 0,78 | 0,89 / 0,81 |
| Block, Osthälfte (κ) | 0,86 | 0,86 | 0,86 |

Was passiert ist: Das zweite Modell findet Torfstiche deutlich besser (alle 6 auf den Validierungs- und Testkacheln, 46 % mehr im ganzen Gebiet), aber seine Konfidenzen für Grasbüschel liegen gehäuft bei 0,15–0,25, sodass das Ergebnis mit dem Schwellenwert schwankt – bei 0,15 „findet“ es auch Grasbüschel in gestrichelten Wiesen, und aus Grasbüscheln + Strichen wird falsches Moor. Längeres Training änderte daran nichts. Eine strengere Torfstichregel (jetzt auf dem Block abgestimmt: ≥ 3 Torfstiche je 275 m statt 2) änderte kaum etwas; daran zeigte sich, dass das falsche Moor von den Grasbüscheln kam, nicht von den Torfstichen. Jede Signatur aus dem Modell zu nehmen, das für sie zuverlässig ist, ergibt die beste Karte. Der Gewinn liegt innerhalb des Konfidenzintervalls, und die Kombination ist die dritte Variante, die gegen dieselben 100 Punkte geprüft wurde – ich lese das als „etwas besser, nicht signifikant besser“. Der Vergleich einer neuen Karte mit einer Stichprobe, die aus einer älteren gezogen wurde, nutzt den Schätzer für Schichten, die nicht den Kartenklassen entsprechen (Stehman 2014; `06v_accuracy_check.py compare`).

### Strichdichte je Feld

Die verbleibenden Fehler bei nasser Wiese lagen in **trockener Wiese** (Reihen von Punktpaaren). Die Punktpaare selbst wurden korrekt ignoriert – aber die Strichdichte wurde über ein gleitendes Fenster von 125 m gemittelt, das über die Feldgrenze in eine benachbarte nasse Wiese hineinreichte. Die Landmesser zeichneten eine Signatur je Feld; deshalb lasse ich jetzt die Feldgrenzen der Karte selbst (Tinte länger als 80 m) die Fläche in Felder teilen und berechne die Strichdichte innerhalb jedes Feldes; sehr kleine Splitter und große offene Flächen behalten den Fensterwert. 06c probiert beide Methoden auf der Westhälfte des Blocks aus.

| Strichdichte | κ West (Abstimmung) | κ Ost (Prüfung) |
|---|---:|---:|
| gleitendes Fenster | 0,740 | 0,856 |
| je Feld | 0,736 | **0,866** |

Auf der Westhälfte lagen beide gleichauf. Deshalb habe ich **vor** dem Blick auf die Prüfpunkte eine Regel festgelegt: Liegen beide innerhalb von 0,01 κ, gewinnt die Feldmethode, weil sie der Digitalisierregel „Grenzen folgen der Feldgrenze“ entspricht. In der blinden Prüfung behebt sie zwei der drei Fehler in trockener Wiese, verpasst aber drei lückenhafte nasse Wiesen; 87 statt 88 der 100 Punkte sind richtig, während die flächengewichtete Genauigkeit von 91 % auf 93 % steigt, weil ein korrigierter Punkt ein großes Gewicht hat. Insgesamt: etwa gleich genau, mit Grenzen, die den Feldern folgen, wie sie gezeichnet wurden.

## Aufbau des Repositorys

```
config.py            alle Pfade, Felder, Parameter, Emissionsfaktoren
peatsh/common.py     gemeinsame Hilfsfunktionen (Gebiet, Zuschnitt, GeoPackage-E/A, Berichte)
scripts/             nummerierte Schritte 00–09 (06x–06c: automatisches Lesen der Karte von 1880)
qgis/                QGIS-Projekt, Stile (.qml)
data/raw/            Downloads und handdigitalisierte Ebenen – nicht in git
data/interim/        Zwischenraster, Kartenkacheln, YOLO-Datensatz und -Modell – nicht in git
data/processed/      peatland_sh.gpkg – nicht in git
outputs/             Karten, Abbildungen, CSV-Tabellen
docs/                Berichte je Schritt, Projektbericht, Digitalisierlegende und -regeln
```

## Ausführen

Entwickelt mit dem Python, das mit **QGIS LTR** unter Windows mitgeliefert wird (GeoPandas, GDAL, SciPy, matplotlib enthalten), ausgeführt in der OSGeo4W Shell:

```bat
python -m pip install --user pulp tabulate truststore
python scripts\00_check_inputs.py
python scripts\01_prepare_dgm1.py
python scripts\02_prepare_inputs.py
python scripts\03_overlay_soils_landuse.py
python scripts\04_emission_estimate.py
python scripts\05_hydrology.py        :: benötigt: qgis_process-qgis-ltr plugins enable grassprovider
python scripts\06_historical_loss.py  :: benötigt die handdigitalisierte Ebene in data\raw\historical\
python scripts\07_optimisation.py
python scripts\07b_history_per_catchment.py  :: nach 06 yolo
python scripts\08_monte_carlo.py
```

Schritt 09 läuft in QGIS (Python-Konsole). Die YOLO-Schritte nutzen eine eigene Umgebung (`python -m venv yolo-env`, dann `pip install ultralytics` mit der CPU-Version von PyTorch); 06x, 06y, 06c, 06v und 06 laufen in der OSGeo4W Shell, Training, 06z und 06b in `yolo-env`:

```bat
:: Block: Kacheln, Labels → Datensatz, Training, Prüfung, Abstimmung
python scripts\06x_make_tiles.py
python scripts\06y_labels_to_yolo.py
yolo detect train data=dataset/data.yaml model=yolo26n.pt imgsz=640 epochs=300 patience=80 batch=8 device=cpu workers=0 scale=0.2
python scripts\06b_predict.py
python scripts\06c_detections_to_polygons.py
:: ganzes Testgebiet: dasselbe Modell, dieselben Schwellenwerte
python scripts\06x_make_tiles.py aoi
python scripts\06b_predict.py aoi
python scripts\06c_detections_to_polygons.py aoi
python scripts\06_historical_loss.py yolo
python scripts\06v_accuracy_check.py make   :: dann "ref" in QGIS ausfüllen
python scripts\06v_accuracy_check.py eval
:: zweite Runde: weitere Kacheln in tiles_aoi.gpkg labeln (use = 'label'), dann
python scripts\06y_labels_to_yolo.py
yolo detect train data=dataset/data.yaml model=yolo26n.pt imgsz=640 epochs=150 patience=40 batch=8 device=cpu workers=2 scale=0.2 degrees=30 flipud=0 project=runs name=train3
python scripts\06b_predict.py aoi data\interim\yolo\runs\detect\runs\train3\weights\best.pt 0.15/0.20
python scripts\06v_accuracy_check.py compare data\interim\yolo\round1\yolo_classes_aoi.tif
:: endgültige Karte: Grasbüschel Runde 1 + Torfstiche Runde 2 in detections*.csv, dann 06c, 06c aoi, 06 yolo, 07b
```

Alternativ beschreibt `environment.yml` eine gleichwertige conda-Umgebung. Die Datenquellen stehen in [DATA_SOURCES.md](DATA_SOURCES.md).

## Grenzen

- Die Emissionsfaktoren sind nationale Klassenmittel; Wasserstand, Torfmächtigkeit und Bewirtschaftung innerhalb einer Klasse werden nicht berücksichtigt.
- Das DGM zeigt keine Drainagen, Durchlässe oder Schöpfwerke, die den Wasserhaushalt im Niedermoor steuern; das Testgebiet ist ein von Hand gezeichnetes Polygon, kein echtes Einzugsgebiet, daher werden nur vollständige Teileinzugsgebiete verwendet.
- Der historische Vergleich stellt Karten*signaturen* einer *Boden*karte gegenüber – unterschiedliche Konzepte. Handdigitalisierung, die Lagegenauigkeit der Aufnahme von 1880 und eine etwa 20 Jahre jüngere Legende erhöhen die Unsicherheit; etwa ein Drittel der „verlorenen“ Fläche liegt innerhalb von 25 m einer Grenze.
- Die DGM1-Kacheln stammen aus den Aufnahmejahren 2005–2025; entwässerter Torf sackt, daher können an Kachelrändern kleine Stufen auftreten.
- Die YOLO-Modelle wurden auf 42 Kacheln trainiert, 32 davon aus einem einzigen 36-km²-Block. Im ganzen Testgebiet erreicht die Karte 93 % ± 4 % Genauigkeit (100 blinde Punkte; die endgültige Karte ist das Ergebnis einer Auswahl zwischen mehreren gegen diese Punkte geprüften Varianten, daher ist der Wert leicht optimistisch). Nasse Wiese ist die unsicherste Klasse (Nutzergenauigkeit 0,86), die Grasbüschel-Konfidenzen des zweiten Modells sind instabil, und Moornamen werden nicht gelesen. Flächen um Torfstiche werden als Quadrate statt als ganze Felder kartiert. Die Regeln wurden auf einem Block abgestimmt; andere Landesteile (Marsch, Hochmoore, östliches Hügelland) bräuchten eigene Prüfungen.
- Das Stream Burning nutzt die Mittellinien des Gewässernetzes; breite Flüsse und Drainagen werden nicht abgebildet.

## Daten und Lizenzen

Siehe [DATA_SOURCES.md](DATA_SOURCES.md). Der Code wurde mit KI-Unterstützung geschrieben; jeden Schritt habe ich selbst ausgeführt und geprüft.
