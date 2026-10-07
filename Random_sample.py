import pandas as pd

# Einstellungen

INPUT_FILE = "documents.parquet"
OUTPUT_FILE = "annotations_sample.parquet"

SAMPLE_SIZE = 1000  
RANDOM_SEED = 53

# Anzahl pro Quelle

SAMPLES_PER_SOURCE = {
    "insolvex" : 549,
    "inregnew" : 345,
    "inregold" : 106
}

# Parquet Datei laden

print("Lese Parquet Datei...")

df = pd.read_parquet(
    INPUT_FILE,
    columns=[
        "source",
        "document_id", 
        "document_text",
    ],
)

# Fehlende Texte entfernen

df = df.dropna(subset=["document_text"])

print(f"Anzahl Dokumente nach Entfernen fehlender Texte: {len(df)}")

# Stichprobe ziehen 

samples = []

for source, n in SAMPLES_PER_SOURCE.items():
    source_df = df[df["source"] == source]

    print(
        f"{source}: "
        f"{len(source_df):,} vorhanden, "
        f"{n} werden ausgewählt"
    )

    sample = source_df.sample(
        n=n,
        random_state=RANDOM_SEED,
    )

    samples.append(sample)

#  Stichproben zusammenführen 

sample_df = pd.concat(samples, ignore_index=True)

# Noch einmal mischen, damit die Quellen
# nicht in Blöcken hintereinander stehen.
sample_df = sample_df.sample(
    frac=1,
    random_state=RANDOM_SEED,
).reset_index(drop=True)

sample_df.insert(
    0,
    "annotation_id",
    range(len(sample_df)),
)


# -----------------------------
# Speichern
# -----------------------------

sample_df.to_parquet(
    OUTPUT_FILE,
    index=False,
)


# -----------------------------
# Kontrolle
# -----------------------------

print()
print("Stichprobe erstellt!")
print(f"Datei: {OUTPUT_FILE}")
print(f"Anzahl Fälle: {len(sample_df)}")

print()
print("Verteilung:")
print(sample_df["source"].value_counts())

print()
print("Fertig.")