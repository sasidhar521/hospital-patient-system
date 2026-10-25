from datetime import datetime
import sqlite3
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

DB_FILE = "hospital.db"


def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  # Automatically check if old table schema exists and upgrade safely
  cursor.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND"
      " name='patient_records'"
  )
  table_exists = cursor.fetchone()
  if table_exists:
    cursor.execute("PRAGMA table_info(patient_records)")
    columns = [col[1] for col in cursor.fetchall()]
    if "unique_id" not in columns or "surgery" in columns:
      cursor.execute("DROP TABLE IF EXISTS patient_records")
      cursor.execute("DROP TABLE IF EXISTS patients")
      cursor.execute("DROP TABLE IF EXISTS patient_records_temp")

  # Patients Master Table (Unique ID -> Patient Name)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            unique_id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

  # Patient Medical Records Table (Order: reason_for_visit then treatment)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_id TEXT NOT NULL,
            reason_for_visit TEXT NOT NULL,
            treatment TEXT NOT NULL,
            doctor TEXT NOT NULL,
            prescription TEXT NOT NULL,
            hospital_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unique_id) REFERENCES patients(unique_id)
        )
    """)

  # Pre-load your 17 friends into the master patient directory for instant lookup
  initial_friends = [
      ("1", "Sharan"),
      ("2", "Akhil"),
      ("3", "Shahul"),
      ("4", "Aariz"),
      ("5", "Vaibhav"),
      ("6", "Moksha"),
      ("7", "Arvind"),
      ("8", "Lokesh"),
      ("9", "Abhishek"),
      ("10", "Solomon"),
      ("11", "Bhuvan"),
      ("12", "Rohan"),
      ("13", "Vignesh"),
      ("14", "Nikhil"),
      ("15", "Yuva"),
      ("16", "Syon"),
      ("17", "Gokul"),
  ]
  cursor.executemany(
      "INSERT OR IGNORE INTO patients (unique_id, name) VALUES (?, ?)",
      initial_friends,
  )

  conn.commit()
  conn.close()


init_db()


def reindex_ids(cursor):
  """Completely recreates the table to guarantee IDs start cleanly from 1 with no gaps."""
  cursor.execute("""
        CREATE TABLE patient_records_temp AS 
        SELECT unique_id, reason_for_visit, treatment, doctor, prescription, hospital_name, created_at 
        FROM patient_records ORDER BY id ASC
    """)
  cursor.execute("DROP TABLE patient_records")
  cursor.execute("""
        CREATE TABLE patient_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_id TEXT NOT NULL,
            reason_for_visit TEXT NOT NULL,
            treatment TEXT NOT NULL,
            doctor TEXT NOT NULL,
            prescription TEXT NOT NULL,
            hospital_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unique_id) REFERENCES patients(unique_id)
        )
    """)
  cursor.execute("""
        INSERT INTO patient_records (unique_id, reason_for_visit, treatment, doctor, prescription, hospital_name, created_at)
        SELECT unique_id, reason_for_visit, treatment, doctor, prescription, hospital_name, created_at 
        FROM patient_records_temp
    """)
  cursor.execute("DROP TABLE patient_records_temp")


@app.get("/", response_class=HTMLResponse)
def read_root(search: str = "", edit_id: str = "", page: int = 1):
  conn = sqlite3.connect(DB_FILE)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  # Fetch all registered patients for JavaScript instant name lookup & datalist
  cursor.execute("SELECT * FROM patients")
  all_patients = cursor.fetchall()
  patient_map_js = {p["unique_id"]: p["name"] for p in all_patients}

  # Search query handling
  if search:
    cursor.execute(
        """
        SELECT r.*, p.name FROM patient_records r
        JOIN patients p ON r.unique_id = p.unique_id
        WHERE r.unique_id LIKE ? OR p.name LIKE ? OR r.hospital_name LIKE ? OR r.doctor LIKE ? OR r.reason_for_visit LIKE ? OR r.treatment LIKE ?
        ORDER BY r.id ASC
    """,
        (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%",
            f"%{search}%",
            f"%{search}%",
            f"%{search}%",
        ),
    )
    records = cursor.fetchall()
    total_records = len(records)
    paginated_records = records
    total_pages = 1
  else:
    # Pagination logic (10 records per page)
    per_page = 10
    cursor.execute("SELECT COUNT(*) FROM patient_records")
    total_records = cursor.fetchone()[0]
    total_pages = max(1, (total_records + per_page - 1) // per_page)

    if page < 1:
      page = 1
    elif page > total_pages:
      page = total_pages

    offset = (page - 1) * per_page
    cursor.execute(
        """
        SELECT r.*, p.name FROM patient_records r
        JOIN patients p ON r.unique_id = p.unique_id
        ORDER BY r.id ASC LIMIT ? OFFSET ?
    """,
        (per_page, offset),
    )
    paginated_records = cursor.fetchall()

  # If editing via control panel, fetch that record
  edit_record = None
  if edit_id.isdigit():
    cursor.execute(
        """
        SELECT r.*, p.name FROM patient_records r
        JOIN patients p ON r.unique_id = p.unique_id
        WHERE r.id = ?
    """,
        (int(edit_id),),
    )
    edit_record = cursor.fetchone()

  conn.close()

  # Clean table rows with swapped positions (Reason for Visit then Treatment)
  rows_html = ""
  for r in paginated_records:
    rows_html += f"""
        <tr class="hover:bg-sky-50/50 transition-colors">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-semibold text-slate-700">{r["id"]}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                <a href="/patient/{r["unique_id"]}" class="px-2.5 py-1 bg-sky-100 text-sky-800 rounded-md font-mono text-xs font-bold hover:bg-sky-200 transition underline">{r["unique_id"]}</a>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <a href="/patient/{r["unique_id"]}" class="px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-md font-semibold text-xs hover:bg-emerald-200 transition">{r["name"]}</a>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-600">{r["reason_for_visit"]}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-700 font-medium">{r["treatment"]}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-700 font-medium">Dr. {r["doctor"]}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-600">{r["prescription"]}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <span class="px-2.5 py-1 bg-blue-100 text-blue-800 rounded-md font-semibold text-xs">{r["hospital_name"]}</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-xs text-slate-400">{r["created_at"]}</td>
        </tr>
        """
  if not rows_html:
    rows_html = """
        <tr>
            <td colspan="9" class="text-center py-10 text-slate-400 text-sm italic">No patient records found in the system.</td>
        </tr>
        """

  # Pagination buttons HTML
  pagination_html = ""
  if not search and total_pages > 1:
    prev_disabled = (
        "opacity-40 pointer-events-none cursor-not-allowed"
        if page <= 1
        else ""
    )
    next_disabled = (
        "opacity-40 pointer-events-none cursor-not-allowed"
        if page >= total_pages
        else ""
    )
    pagination_html = f"""
        <div class="flex items-center justify-between px-6 py-4 bg-slate-50/50 border-t border-slate-100">
            <a href="/?page={page - 1}" class="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-sky-50 transition shadow-sm {prev_disabled}">« Previous</a>
            <span class="text-sm text-slate-600 font-medium">Page <span class="text-sky-700 font-bold">{page}</span> of <span class="text-sky-700 font-bold">{total_pages}</span> <span class="text-slate-400 mx-2">|</span> Total Records: <span class="text-slate-800 font-semibold">{total_records}</span></span>
            <a href="/?page={page + 1}" class="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-sky-50 transition shadow-sm {next_disabled}">Next »</a>
        </div>
        """

  # Generate datalist options for autocomplete
  datalist_options = ""
  for p in all_patients:
    datalist_options += (
        f'<option value="{p["unique_id"]}" data-name="{p["name"]}"></option>'
    )

  # Form configuration for adding or editing
  form_action = "/update" if edit_record else "/add"
  form_title = (
      f"Edit Patient Record (ID: {edit_record['id']})"
      if edit_record
      else "Add Patient Treatment Record"
  )
  btn_text = "Update Record" if edit_record else "Save Record"
  border_accent = (
      "border-amber-500" if edit_record else "border-sky-600"
  )

  unique_id_val = edit_record["unique_id"] if edit_record else ""
  name_val = edit_record["name"] if edit_record else ""
  reason_for_visit = edit_record["reason_for_visit"] if edit_record else ""
  treatment = edit_record["treatment"] if edit_record else ""
  doctor = edit_record["doctor"] if edit_record else ""
  prescription = edit_record["prescription"] if edit_record else ""
  hospital_name = edit_record["hospital_name"] if edit_record else ""
  record_id_input = (
      f'<input type="hidden" name="id" value="{edit_record["id"]}">'
      if edit_record
      else ""
  )
  cancel_btn = (
      '<a href="/" class="px-4 py-2.5 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition">Cancel</a>'
      if edit_record
      else ""
  )

  html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hospital Patient Record System</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            const patientMap = {patient_map_js};
            function updatePatientName(input) {{
                const uid = input.value.trim();
                const nameField = document.getElementById('patient_name');
                if (patientMap[uid]) {{
                    nameField.value = patientMap[uid];
                    nameField.readOnly = true;
                    nameField.classList.add('bg-slate-100', 'text-slate-500');
                }} else {{
                    nameField.value = "";
                    nameField.placeholder = "New Patient: Enter Name";
                    nameField.readOnly = false;
                    nameField.classList.remove('bg-slate-100', 'text-slate-500');
                }}
            }}
        </script>
    </head>
    <body class="bg-gradient-to-br from-sky-50 via-slate-50 to-blue-50 text-slate-800 antialiased min-h-screen py-10 px-4 sm:px-6 lg:px-8">
        <div class="max-w-7xl mx-auto space-y-8">
            
            <!-- Header -->
            <header class="text-center space-y-3 bg-white/80 backdrop-blur-md py-6 px-4 rounded-2xl shadow-sm border border-slate-200/60 max-w-2xl mx-auto">
                <div class="inline-flex items-center justify-center p-3.5 bg-sky-100 text-sky-700 rounded-2xl shadow-sm mb-1">
                    <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                </div>
                <h1 class="text-3xl font-extrabold tracking-tight text-slate-900">Hospital Patient Record System</h1>
                <p class="text-sm font-medium text-slate-500">Universal ID Tracking & Clinical History Timeline</p>
            </header>

            <!-- Add / Edit Form Card -->
            <div class="bg-white shadow-xl shadow-slate-100 rounded-2xl border border-slate-200/80 p-6 sm:p-8 border-t-4 {border_accent}">
                <h3 class="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
                    <span>{form_title}</span>
                </h3>
                <form action="{form_action}" method="post" class="space-y-6">
                    {record_id_input}
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Unique ID / Aadhaar</label>
                            <input type="text" name="unique_id" id="unique_id_input" value="{unique_id_val}" required list="patient-list" placeholder="e.g. 1 or 9482..." oninput="updatePatientName(this)" class="w-full px-3.5 py-2.5 text-sm bg-slate-50/50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white focus:outline-none transition">
                            <datalist id="patient-list">
                                {datalist_options}
                            </datalist>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Patient Name</label>
                            <input type="text" name="patient_name" id="patient_name" value="{name_val}" required placeholder="Auto-resolved" class="w-full px-3.5 py-2.5 text-sm bg-slate-50/50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white focus:outline-none transition">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Reason to Visit Hospital</label>
                            <input type="text" name="reason_for_visit" value="{reason_for_visit}" required placeholder="e.g., Severe Chest Pain / Fever" class="w-full px-3.5 py-2.5 text-sm bg-slate-50/50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white focus:outline-none transition">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Treatment</label>
                            <input type="text" name="treatment" value="{treatment}" required placeholder="e.g., General Consultation" class="w-full px-3.5 py-2.5 text-sm bg-slate-50/50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white focus:outline-none transition">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Doctor Name</label>
                            <input type="text" name="doctor" value="{doctor}" required placeholder="Dr. Smith" class="w-full px-3.5 py-2.5 text-sm bg-slate-50/50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white focus:outline-none transition">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Prescription</label>
                            <input type="text" name="prescription" value="{prescription}" required placeholder="Paracetamol 500mg" class="w-full px-3.5 py-2.5 text-sm bg-slate-50/50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white focus:outline-none transition">
                        </div>
                        <div class="sm:col-span-2">
                            <label class="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Hospital Name</label>
                            <input type="text" name="hospital_name" value="{hospital_name}" required placeholder="City General Hospital" class="w-full px-3.5 py-2.5 text-sm bg-slate-50/50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white focus:outline-none transition">
                        </div>
                    </div>
                    <div class="flex items-center justify-end gap-3 pt-2">
                        {cancel_btn}
                        <button type="submit" class="px-5 py-2.5 text-sm font-bold text-white bg-sky-600 rounded-lg hover:bg-sky-700 shadow-md shadow-sky-600/20 transition">{btn_text}</button>
                    </div>
                </form>
            </div>

            <!-- Search & Table Card -->
            <div class="bg-white shadow-xl shadow-slate-100 rounded-2xl border border-slate-200/80 overflow-hidden">
                <div class="p-6 sm:p-8 border-b border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-50/30">
                    <div>
                        <h3 class="text-lg font-bold text-slate-800">Patient History Timeline</h3>
                        <p class="text-xs text-slate-500 mt-0.5">Click any Unique ID or Name to view full patient profile</p>
                    </div>
                    <form method="get" action="/" class="flex items-center gap-2 w-full sm:w-auto">
                        <input type="text" name="search" value="{search}" placeholder="Search ID, Name, Hospital..." class="w-full sm:w-72 px-3.5 py-2 text-sm bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:outline-none transition shadow-sm">
                        <button type="submit" class="px-4 py-2 text-sm font-semibold text-white bg-slate-700 rounded-lg hover:bg-slate-800 transition shadow-sm">Search</button>
                        <a href="/" class="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-100 transition shadow-sm">Reset</a>
                    </form>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-slate-100/70 border-b border-slate-200 text-slate-600 uppercase text-[11px] tracking-wider font-bold">
                                <th class="px-6 py-3.5">ID</th>
                                <th class="px-6 py-3.5">Unique ID</th>
                                <th class="px-6 py-3.5">Patient Name</th>
                                <th class="px-6 py-3.5">Reason for Visit</th>
                                <th class="px-6 py-3.5">Treatment</th>
                                <th class="px-6 py-3.5">Doctor</th>
                                <th class="px-6 py-3.5">Prescription</th>
                                <th class="px-6 py-3.5">Hospital Name</th>
                                <th class="px-6 py-3.5">Date & Time</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            {rows_html}
                        </tbody>
                    </table>
                </div>
                {pagination_html}
            </div>

            <!-- Bottom Management Control Panel -->
            <div class="bg-white shadow-xl shadow-slate-100 rounded-2xl border border-slate-200/80 p-6 sm:p-8 border-t-4 border-cyan-500">
                <h3 class="text-lg font-bold text-slate-800 mb-1">Record Management Control Panel</h3>
                <p class="text-xs text-slate-500 mb-4">Manage individual row entries by ID with automatic sequence reordering</p>
                <form method="get" action="/" class="flex flex-col sm:flex-row items-end gap-4">
                    <div class="w-full sm:w-1/3">
                        <label class="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Enter Record ID to Edit/Delete:</label>
                        <input type="number" name="edit_id" value="{edit_id}" placeholder="e.g. 1, 2, 3..." min="1" class="w-full px-3.5 py-2.5 text-sm bg-slate-50/50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:bg-white focus:outline-none transition">
                    </div>
                    <div class="flex items-center gap-2 w-full sm:w-auto">
                        <button type="submit" class="px-4 py-2.5 text-sm font-bold text-slate-900 bg-amber-400 rounded-lg hover:bg-amber-500 transition shadow-sm">Load for Edit</button>
                        <button type="submit" formaction="/delete-by-id" onclick="return confirm('Delete this record ID? The table will auto-reorder sequentially starting from 1.');" class="px-4 py-2.5 text-sm font-bold text-white bg-rose-600 rounded-lg hover:bg-rose-700 transition shadow-sm">Delete ID</button>
                        <a href="/" class="px-4 py-2.5 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition">Clear</a>
                    </div>
                </form>
            </div>

        </div>
    </body>
    </html>
    """
  return HTMLResponse(content=html_content)


@app.get("/patient/{unique_id}", response_class=HTMLResponse)
def patient_profile(unique_id: str):
  conn = sqlite3.connect(DB_FILE)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  # Fetch patient details
  cursor.execute("SELECT * FROM patients WHERE unique_id = ?", (unique_id,))
  patient = cursor.fetchone()

  if not patient:
    conn.close()
    raise HTTPException(status_code=404, detail="Patient not found")

  # Fetch all medical history for this unique ID
  cursor.execute(
      """
        SELECT * FROM patient_records 
        WHERE unique_id = ? 
        ORDER BY id DESC
    """,
      (unique_id,),
  )
  records = cursor.fetchall()
  conn.close()

  # Build timeline items (swapped order)
  timeline_html = ""
  for r in records:
    timeline_html += f"""
        <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-3">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100">
                <span class="px-3 py-1 bg-blue-100 text-blue-800 font-bold rounded-lg text-xs">{r["hospital_name"]}</span>
                <span class="text-xs text-slate-400 font-medium">Record ID: #{r["id"]} | {r["created_at"]}</span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                <div>
                    <span class="block text-xs font-bold text-slate-400 uppercase tracking-wider">Reason for Visit</span>
                    <span class="font-semibold text-slate-800">{r["reason_for_visit"]}</span>
                </div>
                <div>
                    <span class="block text-xs font-bold text-slate-400 uppercase tracking-wider">Treatment</span>
                    <span class="font-semibold text-slate-800">{r["treatment"]}</span>
                </div>
                <div>
                    <span class="block text-xs font-bold text-slate-400 uppercase tracking-wider">Attending Doctor</span>
                    <span class="font-semibold text-slate-800">Dr. {r["doctor"]}</span>
                </div>
            </div>
            <div class="pt-2 bg-slate-50 p-3 rounded-lg border border-slate-100">
                <span class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Prescription Details</span>
                <p class="text-sm font-mono text-slate-700">{r["prescription"]}</p>
            </div>
        </div>
        """

  if not timeline_html:
    timeline_html = """
        <div class="text-center py-12 bg-white rounded-xl border border-slate-200 text-slate-400 italic">
            No medical history records found for this patient.
        </div>
        """

  html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Patient Profile - {patient["name"]}</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gradient-to-br from-sky-50 via-slate-50 to-blue-50 text-slate-800 antialiased min-h-screen py-10 px-4 sm:px-6 lg:px-8">
        <div class="max-w-4xl mx-auto space-y-6">
            
            <!-- Navigation Back -->
            <div>
                <a href="/" class="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-slate-600 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition shadow-sm">
                    ← Back to Dashboard
                </a>
            </div>

            <!-- Patient Info Banner -->
            <div class="bg-white shadow-xl shadow-slate-100 rounded-2xl border border-slate-200/80 p-6 sm:p-8 border-t-4 border-sky-600 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <span class="px-2.5 py-1 bg-sky-100 text-sky-800 rounded-md font-mono text-xs font-bold">ID: {patient["unique_id"]}</span>
                    <h1 class="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-2">{patient["name"]}</h1>
                    <p class="text-xs text-slate-500 mt-1">Complete Medical History & Treatment Timeline</p>
                </div>
                <div class="bg-sky-50 px-4 py-3 rounded-xl border border-sky-100 text-right sm:text-left">
                    <span class="block text-xs font-bold text-sky-600 uppercase">Total Visits Recorded</span>
                    <span class="text-2xl font-black text-sky-900">{len(records)}</span>
                </div>
            </div>

            <!-- Timeline Section -->
            <div class="space-y-4">
                <h3 class="text-lg font-bold text-slate-800 px-1">Chronological Medical Records</h3>
                {timeline_html}
            </div>

        </div>
    </body>
    </html>
    """
  return HTMLResponse(content=html_content)


@app.post("/add")
def add_record(
    unique_id: str = Form(...),
    patient_name: str = Form(...),
    reason_for_visit: str = Form(...),
    treatment: str = Form(...),
    doctor: str = Form(...),
    prescription: str = Form(...),
    hospital_name: str = Form(...),
):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR REPLACE INTO patients (unique_id, name) VALUES (?, ?)",
      (unique_id.strip(), patient_name.strip()),
  )
  cursor.execute(
      """
        INSERT INTO patient_records (unique_id, reason_for_visit, treatment, doctor, prescription, hospital_name)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
      (
          unique_id.strip(),
          reason_for_visit,
          treatment,
          doctor,
          prescription,
          hospital_name,
      ),
  )
  conn.commit()
  conn.close()
  return RedirectResponse(url="/", status_code=303)


@app.post("/update")
def update_record(
    id: int = Form(...),
    unique_id: str = Form(...),
    patient_name: str = Form(...),
    reason_for_visit: str = Form(...),
    treatment: str = Form(...),
    doctor: str = Form(...),
    prescription: str = Form(...),
    hospital_name: str = Form(...),
):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR REPLACE INTO patients (unique_id, name) VALUES (?, ?)",
      (unique_id.strip(), patient_name.strip()),
  )
  cursor.execute(
      """
        UPDATE patient_records 
        SET unique_id = ?, reason_for_visit = ?, treatment = ?, doctor = ?, prescription = ?, hospital_name = ?
        WHERE id = ?
    """,
      (
          unique_id.strip(),
          reason_for_visit,
          treatment,
          doctor,
          prescription,
          hospital_name,
          id,
      ),
  )
  conn.commit()
  conn.close()
  return RedirectResponse(url="/", status_code=303)


@app.get("/delete-by-id")
def delete_by_id(edit_id: int):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("DELETE FROM patient_records WHERE id = ?", (edit_id,))
  reindex_ids(cursor)
  conn.commit()
  conn.close()
  return RedirectResponse(url="/", status_code=303)