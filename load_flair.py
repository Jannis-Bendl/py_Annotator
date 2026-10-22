
from flair.datasets import ColumnCorpus
from flair.embeddings import TransformerWordEmbeddings
from flair.models import SequenceTagger
from flair.trainers import ModelTrainer

# 1. Deine eigenen Trainingsdaten laden
data_folder = "flair_data"

columns = {
    0: "text",
    1: "ner"
}

corpus = ColumnCorpus(
    data_folder,
    columns,
    train_file="train.txt",
    dev_file="dev.txt",
    test_file="test.txt"
)

print(corpus)

# 2. Deine eigenen NER-Labels aus den Daten laden
label_dictionary = corpus.make_label_dictionary(
    label_type="ner"
)

print("Labels:", label_dictionary.get_items())

# 3. Deutsches vortrainiertes Sprachmodell verwenden
embeddings = TransformerWordEmbeddings(
    "dbmdz/bert-base-german-cased"
)

# 4. NER-Modell erstellen
tagger = SequenceTagger(
    hidden_size=256,
    embeddings=embeddings,
    tag_dictionary=label_dictionary,
    tag_type="ner",
    use_crf=True
)

# 5. Mit deinen eigenen Daten trainieren
trainer = ModelTrainer(tagger, corpus)

trainer.train(
    "resources/taggers/geschaeftsvertretung-ner",
    learning_rate=5e-5,
    mini_batch_size=8,
    max_epochs=10
)
