from flask import Flask, render_template_string, request, session, jsonify
import pandas as pd
import json
import os
import sqlite3
import secrets
import time
from contextlib import contextmanager

app = Flask("Annotator")
app.secret_key = os.environ.get("ANNOTATOR_SECRET_KEY", secrets.token_hex(32))

# =========================================================
# EINSTELLUNGEN
# =========================================================
SAMPLE_FILE = "annotation_sample.parquet"
DATABASE_FILE = "annotations_shared.sqlite3"
RESERVATION_SECONDS = 2 * 60 * 60  # Reservierung läuft nach 2 Stunden ohne Aktivität ab.


# =========================================================
# DATEN LADEN
# =========================================================
print("\nLade Stichprobe ...")
df = pd.read_parquet(
    SAMPLE_FILE,
    columns=["annotation_id", "source", "document_id", "document_text"],
)
df["document_text"] = df["document_text"].fillna("")
df["document_id"] = df["document_id"].astype(str)
documents = df.to_dict("records")
documents_by_id = {str(doc["document_id"]): doc for doc in documents}
print(f"{len(documents)} Dokumente geladen.")


# =========================================================
# SQLITE-DATENBANK
# =========================================================
def connect_db():
    connection = sqlite3.connect(DATABASE_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                document_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                document_id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                lease_token TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reservations_client
            ON reservations(client_id)
        """)
        conn.commit()


init_db()


def get_client_id():
    if "client_id" not in session:
        session["client_id"] = secrets.token_urlsafe(24)
    return session["client_id"]


def get_saved_annotations(document_id):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT payload, version FROM annotations WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()
    if row:
        return json.loads(row["payload"]), int(row["version"])
    return [], 0


def get_client_reservation(client_id):
    now = time.time()
    with connect_db() as conn:
        conn.execute("DELETE FROM reservations WHERE expires_at < ?", (now,))
        row = conn.execute(
            """SELECT document_id, lease_token FROM reservations
               WHERE client_id = ? AND expires_at >= ? LIMIT 1""",
            (client_id, now),
        ).fetchone()
        conn.commit()
    if row:
        return str(row["document_id"]), row["lease_token"]
    return None


def reserve_next_document(client_id):
    """Reserviert atomar das nächste freie, noch nicht abgeschlossene Dokument."""
    now = time.time()
    with connect_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM reservations WHERE expires_at < ?", (now,))

        # Falls derselbe Browser erneut / aufruft, seine Reservierung beibehalten.
        existing = conn.execute(
            """SELECT document_id, lease_token FROM reservations
               WHERE client_id = ? AND expires_at >= ? LIMIT 1""",
            (client_id, now),
        ).fetchone()
        if existing:
            conn.commit()
            return str(existing["document_id"]), existing["lease_token"]

        for doc in documents:
            document_id = str(doc["document_id"])
            completed = conn.execute(
                "SELECT 1 FROM annotations WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            reserved = conn.execute(
                "SELECT 1 FROM reservations WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if completed or reserved:
                continue

            token = secrets.token_urlsafe(32)
            conn.execute(
                """INSERT INTO reservations
                   (document_id, client_id, lease_token, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (document_id, client_id, token, now + RESERVATION_SECONDS),
            )
            conn.commit()
            return document_id, token

        conn.commit()
    return None


def release_reservation(document_id, client_id):
    with connect_db() as conn:
        conn.execute(
            "DELETE FROM reservations WHERE document_id = ? AND client_id = ?",
            (str(document_id), client_id),
        )
        conn.commit()


# =========================================================
# HTML-OBERFLÄCHE
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

const leaseToken = {{ lease_token | tojson }};
let documentVersion = {{ document_version | tojson }};
let saveQueue = Promise.resolve();
// Reservierung regelmäßig verlängern, solange die Seite geöffnet ist.
setInterval(() => {
    fetch("/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId, lease_token: leaseToken })
    }).catch(() => {});
}, 5 * 60 * 1000);


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
    // Saves werden innerhalb dieses Browsers serialisiert, damit schnelle
    // aufeinanderfolgende Markierungen keine veraltete Versionsnummer senden.
    saveQueue = saveQueue.then(async () => {
        const response = await fetch("/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                document_id: documentId,
                annotations: currentAnnotations,
                version: documentVersion,
                lease_token: leaseToken
            })
        });

        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = result.error || "Speichern fehlgeschlagen.";
            alert(message + "\\nBitte Änderungen nicht einfach verwerfen. Lade die Seite neu und prüfe den Bearbeitungsstatus.");
            throw new Error(message);
        }
        documentVersion = result.version;
        return result;
    });
    return saveQueue;
}


/* =====================================================
   SPEICHERN UND WEITER
   ===================================================== */

async function saveAndNext() {
    try {
        await saveAnnotations();
        window.location.href = "/next/" + encodeURIComponent(documentId);
    } catch (error) {
        console.error(error);
    }
}


/* =====================================================
   KEINE ANNOTATION
   ===================================================== */

async function skipDocument() {
    if (!confirm("Dieses Dokument ohne Annotation abschließen?")) return;
    currentAnnotations = [];
    renderAnnotations();
    try {
        await saveAnnotations();
        window.location.href = "/next/" + encodeURIComponent(documentId);
    } catch (error) {
        console.error(error);
    }
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
        return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    result = []
    position = 0
    sorted_annotations = sorted(current_annotations, key=lambda x: x["start"])
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
        start, end, label = ann["start"], ann["end"], ann["label"]
        result.append(text[position:start].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        selected = text[start:end]
        css_class = css_classes.get(label, "")
        result.append(
            f'<span class="{css_class}" title="{label}">'
            + selected.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            + "</span>"
        )
        position = end
    result.append(text[position:].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return "".join(result)


def show_document(document_id, lease_token):
    document_id = str(document_id)
    row = documents_by_id.get(document_id)
    if row is None:
        return "Dokument nicht gefunden", 404

    current_annotations, version = get_saved_annotations(document_id)
    position = next(i for i, doc in enumerate(documents, start=1)
                    if str(doc["document_id"]) == document_id)
    rendered_text = render_text(str(row["document_text"]), current_annotations)

    return render_template_string(
        HTML,
        annotation_id=row["annotation_id"],
        position=position,
        total=len(documents),
        document_source=row["source"],
        document_id=document_id,
        document_text=str(row["document_text"]),
        rendered_text=rendered_text,
        current_annotations=current_annotations,
        lease_token=lease_token,
        document_version=version,
    )


@app.route("/")
def index():
    client_id = get_client_id()
    reservation = get_client_reservation(client_id)
    if reservation:
        return show_document(reservation[0], reservation[1])

    reservation = reserve_next_document(client_id)
    if reservation is None:
        return """
        <h1>Keine freien Dokumente</h1>
        <p>Alle Dokumente sind bereits annotiert oder aktuell von anderen Bearbeitern reserviert.</p>
        <p>Bitte später erneut laden.</p>
        <p><a href="/">Erneut prüfen</a></p>
        """
    return show_document(reservation[0], reservation[1])


@app.route("/save", methods=["POST"])
def save():
    data = request.get_json(silent=True) or {}
    document_id = str(data.get("document_id", ""))
    annotations = data.get("annotations")
    lease_token = data.get("lease_token", "")
    expected_version = data.get("version")
    client_id = get_client_id()

    if document_id not in documents_by_id:
        return jsonify(error="Unbekanntes Dokument."), 404
    if not isinstance(annotations, list) or not isinstance(expected_version, int):
        return jsonify(error="Ungültige Speicherdaten. Bitte Seite neu laden."), 400

    # Validiert Struktur und verhindert ungültige Offsets/überlappende Einträge.
    text_length = len(str(documents_by_id[document_id]["document_text"]))
    previous_end = 0
    for ann in sorted(annotations, key=lambda a: a.get("start", -1)):
        if not isinstance(ann, dict):
            return jsonify(error="Ungültige Annotation."), 400
        start, end, label = ann.get("start"), ann.get("end"), ann.get("label")
        if (not isinstance(start, int) or not isinstance(end, int)
                or start < previous_end or end <= start or end > text_length
                or not isinstance(label, str)):
            return jsonify(error="Ungültige oder überlappende Annotationen."), 400
        previous_end = end

    now = time.time()
    with connect_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        reservation = conn.execute(
            """SELECT client_id, lease_token, expires_at FROM reservations
               WHERE document_id = ?""",
            (document_id,),
        ).fetchone()
        if (not reservation or reservation["client_id"] != client_id
                or reservation["lease_token"] != lease_token
                or reservation["expires_at"] < now):
            conn.rollback()
            return jsonify(error="Die Dokumentreservierung ist abgelaufen oder gehört zu einem anderen Bearbeiter. Bitte lade die Seite neu."), 409

        existing = conn.execute(
            "SELECT version FROM annotations WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        current_version = int(existing["version"]) if existing else 0
        if current_version != expected_version:
            conn.rollback()
            return jsonify(error="Versionskonflikt: Das Dokument wurde zwischenzeitlich geändert. Bitte lade die Seite neu und prüfe die Annotationen."), 409

        new_version = current_version + 1
        conn.execute(
            """INSERT INTO annotations (document_id, payload, version, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(document_id) DO UPDATE SET
                 payload = excluded.payload,
                 version = excluded.version,
                 updated_at = excluded.updated_at""",
            (document_id, json.dumps(annotations, ensure_ascii=False),
             new_version, now),
        )
        # Jede erfolgreiche Speicherung verlängert die Reservierung.
        conn.execute(
            "UPDATE reservations SET expires_at = ? WHERE document_id = ? AND client_id = ?",
            (now + RESERVATION_SECONDS, document_id, client_id),
        )
        conn.commit()
    return jsonify(status="ok", version=new_version)


@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(silent=True) or {}
    document_id = str(data.get("document_id", ""))
    lease_token = data.get("lease_token", "")
    client_id = get_client_id()
    now = time.time()
    with connect_db() as conn:
        cursor = conn.execute(
            """UPDATE reservations SET expires_at = ?
               WHERE document_id = ? AND client_id = ? AND lease_token = ? AND expires_at >= ?""",
            (now + RESERVATION_SECONDS, document_id, client_id, lease_token, now),
        )
        conn.commit()
    if cursor.rowcount != 1:
        return jsonify(error="Reservierung abgelaufen. Bitte Seite neu laden."), 409
    return jsonify(status="ok")


@app.route("/next/<document_id>")
def next_document_route(document_id):
    client_id = get_client_id()
    release_reservation(document_id, client_id)
    reservation = reserve_next_document(client_id)
    if reservation is None:
        return """
        <h1>Keine freien Dokumente</h1>
        <p>Alle Dokumente sind annotiert oder aktuell reserviert.</p>
        <p><a href="/">Erneut prüfen</a></p>
        """
    return show_document(reservation[0], reservation[1])


@app.route("/status")
def status():
    with connect_db() as conn:
        completed = conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
        now = time.time()
        reserved = conn.execute(
            "SELECT COUNT(*) FROM reservations WHERE expires_at >= ?", (now,)
        ).fetchone()[0]
    return jsonify(total=len(documents), completed=completed,
                   reserved=reserved, remaining=max(0, len(documents) - completed))


if __name__ == "__main__":
    print("\n================================")
    print("PII Annotator – Netzwerkbetrieb")
    print("================================")
    print(f"Dokumente: {len(documents)}")
    print(f"Datenbank: {os.path.abspath(DATABASE_FILE)}")
    print("Im Browser aufrufen: http://<SERVER-IP>:5000")
    print("Für den Betrieb im Firmennetzwerk Firewall und Zugriffsschutz beachten.")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
