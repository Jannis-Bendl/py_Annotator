"Random_sample.py" zieht aus der "documents.parquet" eine Stichprobe (die Datei muss also noch lokal hinzugefügt werden), anschließend kann "Py_Annotator_v2.py" ausgeführt werden.
"load_flair.py" initialisiert das NLP-Modelltraining und legt den einen Ordner "flair_data" und "resources" im Working Directory an. Hierin befinden sich der test, train und dev Teil des Datensatzes sowie das fertige Modell inklusive der Evaluation am Testdatensatz.

"pii_annotator_network" ist ein kleines Experiment. Hier wurde der bereits fertige annotator um eine SQLite Datenbank erweitert um das parallele bearbeiten der Dokumente zu ermöglichen.
