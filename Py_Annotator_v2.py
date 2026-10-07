from flask import Flask, render_template_string, request
import pandas as pd
import json
import os

app = Flask("Annotator")

# =========================================================
# EINSTELLUNGEN
# =========================================================

SAMPLE_FILE = "annotation_sample.parquet"

# Neue Datei – die alte annotations.json bleibt erhalten
ANNOTATIONS_FILE = "annotations_v2.json"


# =========================================================
# DATEN LADEN
# =========================================================

print()
print("Lade Stichprobe ...")

df = pd.read_parquet(
    SAMPLE_FILE,
    columns=[
        "annotation_id",
        "source",
        "document_id",
        "document_text",
    ],
)

df["document_text"] = df["document_text"].fillna("")

documents = df.to_dict("records")

print(f"{len(documents)} Dokumente geladen.")


# =========================================================
# ANNOTATIONEN LADEN
# =========================================================
#
# WICHTIG:
# Der Schlüssel in annotations_v2.json ist die document_id.
# Die annotation_id wird nur intern für die Navigation im
# DataFrame verwendet.
#
# =========================================================

if os.path.exists(ANNOTATIONS_FILE):

    with open(
        ANNOTATIONS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        annotations = json.load(f)

    print(
        f"{len(annotations)} bereits bearbeitete "
        f"Dokumente geladen."
    )

else:

    annotations = {}

    print("Neue Annotation-Datei wird erstellt.")


# =========================================================
# SPEICHERN
# =========================================================

def save_annotations():

    temp_file = ANNOTATIONS_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            annotations,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # Erst nach erfolgreichem Schreiben ersetzen
    os.replace(
        temp_file,
        ANNOTATIONS_FILE
    )


# =========================================================
# NÄCHSTES NICHT BEARBEITETES DOKUMENT
# =========================================================

def get_next_unannotated():

    for doc in documents:

        document_id = str(
            doc["document_id"]
        )

        if document_id not in annotations:

            return document_id

    return None


# =========================================================
# HTML
# =========================================================

HTML = """
<!DOCTYPE html>

<html lang="de">

<head>

<meta charset="UTF-8">

<title>PII Annotator</title>

<style>

body {

    font-family: Arial, sans-serif;

    margin: 0;

    background: #f3f3f3;

}

.container {

    max-width: 1400px;

    margin: auto;

    padding: 20px;

}

.header {

    background: white;

    padding: 20px;

    border-radius: 8px;

    margin-bottom: 15px;

}

.header h1 {

    margin-top: 0;

}

.info {

    margin: 5px 0;

}


/* =====================================================
   BUTTONS
   ===================================================== */

.controls {

    background: white;

    padding: 15px;

    border-radius: 8px;

    margin-bottom: 15px;

}

button {

    padding: 10px 14px;

    margin: 4px;

    border: 1px solid #aaa;

    border-radius: 5px;

    cursor: pointer;

    font-size: 14px;

}

button:hover {

    opacity: 0.8;

}


/* =====================================================
   DOKUMENT
   ===================================================== */

.document {

    background: white;

    padding: 25px;

    border-radius: 8px;

    line-height: 1.6;

    white-space: pre-wrap;

    user-select: text;

    font-size: 16px;

    min-height: 300px;

}


/* =====================================================
   ANNOTATION FARBEN
   ===================================================== */

.ges-person {

    background: #ffd6d6;

    border-radius: 3px;

}

.ges-address {

    background: #ffb3b3;

    border-radius: 3px;

}

.ges-birthday {

    background: #ffd1a8;

    border-radius: 3px;

}

.creditor {

    background: #d9f2d9;

    border-radius: 3px;

}

.ins-person {

    background: #d6e4ff;

    border-radius: 3px;

}

.ins-address {

    background: #b3ccff;

    border-radius: 3px;

}

.ins-phone {

    background: #d6f5d6;

    border-radius: 3px;

}

.ins-fax {

    background: #fff0b3;

    border-radius: 3px;

}

.ins-email {

    background: #e5d6ff;

    border-radius: 3px;

}


/* =====================================================
   ANNOTATIONSLISTE
   ===================================================== */

.annotation-list {

    background: white;

    padding: 15px;

    border-radius: 8px;

    margin-top: 15px;

}

.annotation-item {

    padding: 8px;

    margin: 3px 0;

    border-bottom: 1px solid #ddd;

}

.keyboard {

    background: #fafafa;

    padding: 12px;

    border-radius: 6px;

    margin-top: 10px;

    font-size: 14px;

}

</style>

</head>


<body>

<div class="container">


<!-- ===================================================
     HEADER
     =================================================== -->

<div class="header">

<h1>PII Annotator</h1>

<div class="info">
Dokument <b>{{ position }}</b> von <b>{{ total }}</b>
</div>

<div class="info">
Annotation ID:
<b>{{ annotation_id }}</b>
</div>

<div class="info">
Quelle:
<b>{{ document_source }}</b>
</div>

<div class="info">
Document ID:
<b>{{ document_id }}</b>
</div>

</div>


<!-- ===================================================
     BUTTONS
     =================================================== -->

<div class="controls">

<b>Text markieren und anschließend Label auswählen:</b>

<br>
<br>


<button onclick="addAnnotation('GESCHAEFTSVERTRETUNG_PERSON')">
Geschäftsvertretung – Person (G)
</button>


<button onclick="addAnnotation('GESCHAEFTSVERTRETUNG_ADDRESS')">
Geschäftsvertretung – Adresse (Shift+G)
</button>


<button onclick="addAnnotation('GESCHAEFTSVERTRETUNG_GEBURTSTAG')">
Geschäftsvertretung – Geburtstag (B)
</button>


<button onclick="addAnnotation('GLAEUBIGER')">
Gläubiger (L)
</button>


<button onclick="addAnnotation('INSOLVENZVERWALTER_PERSON')">
Insolvenzverwalter – Person (I)
</button>


<button onclick="addAnnotation('INSOLVENZVERWALTER_ADDRESS')">
Insolvenzverwalter – Adresse (Shift+I)
</button>


<button onclick="addAnnotation('INSOLVENZVERWALTER_PHONE')">
Insolvenzverwalter – Telefon (T)
</button>


<button onclick="addAnnotation('INSOLVENZVERWALTER_FAX')">
Insolvenzverwalter – Fax (F)
</button>


<button onclick="addAnnotation('INSOLVENZVERWALTER_EMAIL')">
Insolvenzverwalter – E-Mail (E)
</button>


<br>
<br>


<button onclick="deleteLast()">
Letzte Annotation löschen (Z)
</button>


<button onclick="saveAndNext()">
Speichern & Weiter (N / Enter)
</button>


<button onclick="skipDocument()">
Keine Annotation (S)
</button>


<div class="keyboard">

<b>Tastenkürzel:</b><br>

G = Geschäftsvertretung Person<br>

Shift+G = Geschäftsvertretung Adresse<br>

B = Geschäftsvertretung Geburtstag<br>

L = Gläubiger<br>

I = Insolvenzverwalter Person<br>

Shift+I = Insolvenzverwalter Adresse<br>

T = Telefon<br>

F = Fax<br>

E = E-Mail<br>

Z = letzte Annotation löschen<br>

N / Enter = speichern & weiter<br>

S = keine Annotation

</div>

</div>


<!-- ===================================================
     DOKUMENT
     =================================================== -->

<div
    id="document"
    class="document"
>{{ rendered_text | safe }}</div>


<!-- ===================================================
     ANNOTATIONEN
     =================================================== -->

<div class="annotation-list">

<h3>Aktuelle Annotationen</h3>

<div id="annotationList"></div>

</div>


</div>


<script>

/* =====================================================
   VARIABLEN
   ===================================================== */

const documentText =
    {{ document_text | tojson }};

const documentId =
    {{ document_id | tojson }};

let currentAnnotations =
    {{ current_annotations | tojson }};


/* =====================================================
   HTML ESCAPEN
   ===================================================== */

function escapeHtml(text) {

    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


/* =====================================================
   FARBKLASSEN
   ===================================================== */

function getCssClass(label) {

    if (
        label ===
        "GESCHAEFTSVERTRETUNG_PERSON"
    ) {

        return "ges-person";

    }

    if (
        label ===
        "GESCHAEFTSVERTRETUNG_ADDRESS"
    ) {

        return "ges-address";

    }

    if (
        label ===
        "GESCHAEFTSVERTRETUNG_GEBURTSTAG"
    ) {

        return "ges-birthday";

    }

    if (
        label ===
        "GLAEUBIGER"
    ) {

        return "creditor";

    }

    if (
        label ===
        "INSOLVENZVERWALTER_PERSON"
    ) {

        return "ins-person";

    }

    if (
        label ===
        "INSOLVENZVERWALTER_ADDRESS"
    ) {

        return "ins-address";

    }

    if (
        label ===
        "INSOLVENZVERWALTER_PHONE"
    ) {

        return "ins-phone";

    }

    if (
        label ===
        "INSOLVENZVERWALTER_FAX"
    ) {

        return "ins-fax";

    }

    if (
        label ===
        "INSOLVENZVERWALTER_EMAIL"
    ) {

        return "ins-email";

    }

    return "";

}


/* =====================================================
   ANNOTATIONEN DARSTELLEN
   ===================================================== */

function renderAnnotations() {

    let html = "";

    let position = 0;

    const sorted =
        [...currentAnnotations].sort(
            (a, b) =>
                a.start - b.start
        );


    for (const ann of sorted) {

        html += escapeHtml(
            documentText.substring(
                position,
                ann.start
            )
        );


        const cssClass =
            getCssClass(ann.label);


        html +=
            '<span class="' +
            cssClass +
            '" title="' +
            ann.label +
            '">' +
            escapeHtml(
                documentText.substring(
                    ann.start,
                    ann.end
                )
            ) +
            '</span>';


        position = ann.end;

    }


    html += escapeHtml(
        documentText.substring(position)
    );


    document.getElementById(
        "document"
    ).innerHTML = html;


    renderAnnotationList();

}


/* =====================================================
   ANNOTATIONSLISTE
   ===================================================== */

function renderAnnotationList() {

    const list =
        document.getElementById(
            "annotationList"
        );


    if (
        currentAnnotations.length === 0
    ) {

        list.innerHTML =
            "<i>Keine Annotationen</i>";

        return;

    }


    list.innerHTML = "";


    currentAnnotations
        .sort(
            (a, b) =>
                a.start - b.start
        )
        .forEach(
            (ann, index) => {

                const text =
                    documentText.substring(
                        ann.start,
                        ann.end
                    );


                const div =
                    document.createElement(
                        "div"
                    );


                div.className =
                    "annotation-item";


                div.innerHTML =
                    "<b>" +
                    ann.label +
                    "</b>: " +
                    escapeHtml(text) +
                    " [" +
                    ann.start +
                    "–" +
                    ann.end +
                    "]";


                list.appendChild(div);

            }
        );

}


/* =====================================================
   MARKIERUNG ERMITTELN
   ===================================================== */

function getSelectionOffsets() {

    const selection =
        window.getSelection();


    if (!selection.rangeCount) {

        return null;

    }


    if (selection.isCollapsed) {

        return null;

    }


    const range =
        selection.getRangeAt(0);


    const container =
        document.getElementById(
            "document"
        );


    if (
        !container.contains(
            range.commonAncestorContainer
        )
    ) {

        return null;

    }


    const preRange =
        document.createRange();


    preRange.selectNodeContents(
        container
    );


    preRange.setEnd(
        range.startContainer,
        range.startOffset
    );


    const start =
        preRange.toString().length;


    const selectedText =
        range.toString();


    const end =
        start +
        selectedText.length;


    return {

        start: start,

        end: end

    };

}


/* =====================================================
   ÜBERSCHNEIDUNG PRÜFEN
   ===================================================== */

function overlaps(start, end) {

    for (
        const ann
        of currentAnnotations
    ) {

        if (
            start < ann.end &&
            end > ann.start
        ) {

            return true;

        }

    }

    return false;

}


/* =====================================================
   ANNOTATION HINZUFÜGEN
   ===================================================== */

function addAnnotation(label) {

    const selection =
        getSelectionOffsets();


    if (!selection) {

        alert(
            "Bitte zuerst Text markieren."
        );

        return;

    }


    const start =
        selection.start;

    const end =
        selection.end;


    if (overlaps(start, end)) {

        alert(
            "Diese Markierung überschneidet sich mit einer bestehenden Annotation."
        );

        return;

    }


    currentAnnotations.push({

        start: start,

        end: end,

        label: label

    });


    saveAnnotations();


    window
        .getSelection()
        .removeAllRanges();


    renderAnnotations();

}


/* =====================================================
   LETZTE ANNOTATION LÖSCHEN
   ===================================================== */

function deleteLast() {

    if (
        currentAnnotations.length === 0
    ) {

        return;

    }


    currentAnnotations.pop();


    saveAnnotations();


    renderAnnotations();

}


/* =====================================================
   SPEICHERN
   ===================================================== */

function saveAnnotations() {

    fetch(
        "/save",
        {

            method: "POST",

            headers: {

                "Content-Type":
                    "application/json"

            },

            body: JSON.stringify({

                document_id:
                    documentId,

                annotations:
                    currentAnnotations

            })

        }
    );

}


/* =====================================================
   SPEICHERN UND WEITER
   ===================================================== */

function saveAndNext() {

    saveAnnotations();


    setTimeout(

        () => {

            window.location.href =
                "/next/" +
                encodeURIComponent(documentId);

        },

        150

    );

}


/* =====================================================
   KEINE ANNOTATION
   ===================================================== */

function skipDocument() {

    currentAnnotations = [];

    saveAnnotations();

    setTimeout(
        () => {

            window.location.href =
                "/next/" +
                encodeURIComponent(documentId);

        },
        150
    );
}


/* =====================================================
   TASTATUR
   ===================================================== */

document.addEventListener(
    "keydown",
    function(event) {


        if (
            event.target.tagName ===
            "INPUT" ||
            event.target.tagName ===
            "TEXTAREA"
        ) {

            return;

        }


        /*
         * G
         * Geschäftsvertretung Person
         */

        if (
            event.key === "g"
        ) {

            addAnnotation(
                "GESCHAEFTSVERTRETUNG_PERSON"
            );

        }


        /*
         * SHIFT + G
         * Geschäftsvertretung Adresse
         */

        else if (
            event.key === "G"
        ) {

            addAnnotation(
                "GESCHAEFTSVERTRETUNG_ADDRESS"
            );

        }


        /*
         * B
         * Geschäftsvertretung Geburtstag
         */

        else if (
            event.key === "b" ||
            event.key === "B"
        ) {

            addAnnotation(
                "GESCHAEFTSVERTRETUNG_GEBURTSTAG"
            );

        }


        /*
         * L
         * Gläubiger
         */

        else if (
            event.key === "l" ||
            event.key === "L"
        ) {

            addAnnotation(
                "GLAEUBIGER"
            );

        }


        /*
         * I
         * Insolvenzverwalter Person
         */

        else if (
            event.key === "i"
        ) {

            addAnnotation(
                "INSOLVENZVERWALTER_PERSON"
            );

        }


        /*
         * SHIFT + I
         * Insolvenzverwalter Adresse
         */

        else if (
            event.key === "I"
        ) {

            addAnnotation(
                "INSOLVENZVERWALTER_ADDRESS"
            );

        }


        /*
         * T
         * Telefon
         */

        else if (
            event.key === "t" ||
            event.key === "T"
        ) {

            addAnnotation(
                "INSOLVENZVERWALTER_PHONE"
            );

        }


        /*
         * F
         * Fax
         */

        else if (
            event.key === "f" ||
            event.key === "F"
        ) {

            addAnnotation(
                "INSOLVENZVERWALTER_FAX"
            );

        }


        /*
         * E
         * E-Mail
         */

        else if (
            event.key === "e" ||
            event.key === "E"
        ) {

            addAnnotation(
                "INSOLVENZVERWALTER_EMAIL"
            );

        }


        /*
         * Z
         * letzte Annotation löschen
         */

        else if (
            event.key === "z" ||
            event.key === "Z"
        ) {

            deleteLast();

        }


        /*
         * N / ENTER
         * speichern und weiter
         */

        else if (
            event.key === "n" ||
            event.key === "N" ||
            event.key === "Enter"
        ) {

            saveAndNext();

        }


        /*
         * S
         * keine Annotation
         */

        else if (
            event.key === "s" ||
            event.key === "S"
        ) {

            skipDocument();

        }

    }
);


/* =====================================================
   START
   ===================================================== */

renderAnnotations();

</script>

</body>

</html>
"""


# =========================================================
# TEXT RENDERN
# =========================================================

def render_text(text, current_annotations):

    if not current_annotations:
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    result = []
    position = 0

    sorted_annotations = sorted(
        current_annotations,
        key=lambda x: x["start"]
    )

    css_classes = {
        "GESCHAEFTSVERTRETUNG_PERSON": "ges-person",
        "GESCHAEFTSVERTRETUNG_ADDRESS": "ges-address",
        "GESCHAEFTSVERTRETUNG_GEBURTSTAG": "ges-birthday",
        "GLAEUBIGER": "creditor",
        "INSOLVENZVERWALTER_PERSON": "ins-person",
        "INSOLVENZVERWALTER_ADDRESS": "ins-address",
        "INSOLVENZVERWALTER_PHONE": "ins-phone",
        "INSOLVENZVERWALTER_FAX": "ins-fax",
        "INSOLVENZVERWALTER_EMAIL": "ins-email",
    }

    for ann in sorted_annotations:

        start = ann["start"]
        end = ann["end"]
        label = ann["label"]

        before = text[position:start]

        result.append(
            before
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        selected = text[start:end]

        css_class = css_classes.get(label, "")

        result.append(
            f'<span class="{css_class}" title="{label}">'
            + selected
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            + "</span>"
        )

        position = end

    result.append(
        text[position:]
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return "".join(result)


# =========================================================
# DOKUMENT ANZEIGEN
# =========================================================

def show_document(document_id):

    row = df[
        df["document_id"].astype(str) == str(document_id)
    ].iloc[0]

    document_id = str(row["document_id"])

    current_annotations = annotations.get(
        document_id,
        []
    )

    # Position nur für die Anzeige
    position = (
        df.index[
            df["document_id"].astype(str) == document_id
        ][0] + 1
    )

    rendered_text = render_text(
        row["document_text"],
        current_annotations
    )

    return render_template_string(
        HTML,
        annotation_id=row["annotation_id"],
        position=position,
        total=len(df),
        document_source=row["source"],
        document_id=document_id,
        document_text=row["document_text"],
        rendered_text=rendered_text,
        current_annotations=current_annotations,
    )


# =========================================================
# STARTSEITE
# =========================================================

@app.route("/")
def index():

    document_id = get_next_unannotated()

    if document_id is None:

        return """
        <h1>Fertig!</h1>

        <p>
        Alle Dokumente wurden annotiert.
        </p>
        """

    return show_document(document_id)


# =========================================================
# SPEICHERN
# =========================================================

@app.route("/save", methods=["POST"])
def save():

    data = request.get_json()

    document_id = str(
        data["document_id"]
    )

    annotations[document_id] = data["annotations"]

    save_annotations()

    return {
        "status": "ok"
    }


# =========================================================
# NÄCHSTES DOKUMENT
# =========================================================

@app.route("/next/<document_id>")
def next_document_route(document_id):

    matches = df[
        df["document_id"].astype(str) == str(document_id)
    ]

    if matches.empty:

        return "Dokument nicht gefunden", 404

    current_index = matches.index[0]

    # Nächstes Dokument
    next_index = current_index + 1

    if next_index >= len(df):

        next_document_id = get_next_unannotated()

        if next_document_id is None:

            return """
            <h1>Fertig!</h1>

            <p>
            Alle Dokumente wurden annotiert.
            </p>
            """

        return show_document(next_document_id)

    next_document_id = str(
        df.iloc[next_index]["document_id"]
    )

    return show_document(next_document_id)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print()
    print("==============================")
    print("PII Annotator gestartet")
    print("==============================")
    print()

    print("Labels:")
    print()
    print("G       = Geschäftsvertretung Person")
    print("Shift+G = Geschäftsvertretung Adresse")
    print("B       = Geschäftsvertretung Geburtstag")
    print("L       = Gläubiger")
    print()
    print("I       = Insolvenzverwalter Person")
    print("Shift+I = Insolvenzverwalter Adresse")
    print()
    print("T       = Insolvenzverwalter Telefon")
    print("F       = Insolvenzverwalter Fax")
    print("E       = Insolvenzverwalter E-Mail")
    print()
    print("Z       = letzte Annotation löschen")
    print("N       = speichern und weiter")
    print("S       = keine Annotation")
    print()
    print(
        "Annotationsdatei (Schlüssel = document_id):",
        ANNOTATIONS_FILE
    )
    print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )