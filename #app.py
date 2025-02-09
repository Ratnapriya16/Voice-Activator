#app.py
from flask import Flask, render_template, redirect, session, request, flash, jsonify, url_for
import psycopg2
import os
from database import DB_CONFIG
from flask import Flask, request, jsonify
from io import StringIO
import csv
from psycopg2.extras import DictCursor
import io
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)
app.secret_key = "test123"
# Hardcoded admin credentials for testing
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
# Update your DB_CONFIG with correct credentials
DB_CONFIG = {
'dbname': 'campus_connect',
'user': 'postgres', # Changed from 'postgre' to 'postgres'
'password': 'indhu0504', # Make sure this matches your PostgreSQL password
'host': 'localhost',
'port': '5432'
}
@app.route("/")
def home():
return render_template("index.html")
@app.route("/admin-login", methods=['GET', 'POST'])
def admin_login():
if request.method == 'POST':
username = request.form.get('username')
password = request.form.get('password')
if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
session['admin'] = True
return redirect('/admin-panel')

Computer Science and Engineering (AI&ML) 20
Campus Connect: Smart tracking faculty and Scheduling System

else:
flash('Invalid credentials')
return redirect('/admin-login')
return render_template("admin_login.html")
@app.route("/admin-panel")
def admin_panel():
if not session.get('admin'):
return redirect('/admin-login')
return render_template("admin_panel.html")
# Add this route for adding faculty
@app.route("/add-faculty", methods=['POST'])
def add_faculty():
if not session.get('admin'):
return jsonify({'error': 'Unauthorized'}), 401
faculty_name = request.form.get('faculty_name')
if not faculty_name:
return jsonify({'error': 'Faculty name is required'}), 400
try:
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
# Insert the faculty
cur.execute(
"INSERT INTO faculty (name) VALUES (%s) RETURNING id",
(faculty_name,)
)
faculty_id = cur.fetchone()[0]
conn.commit()
# Return success response
return jsonify({
'success': True,
'id': faculty_id,
'name': faculty_name
})
except psycopg2.Error as e:
# If there's an error, rollback the transaction
if conn:
conn.rollback()
return jsonify({'error': str(e)}), 400
finally:
# Always close cursor and connection
if cur:
cur.close()
if conn:
conn.close()

Computer Science and Engineering (AI&ML) 21
Campus Connect: Smart tracking faculty and Scheduling System

@app.route("/search-faculty", methods=['POST'])
def search_faculty():
faculty_name = request.form.get('faculty_name')
search_day = request.form.get('day')
search_start = request.form.get('start_time')
search_end = request.form.get('end_time')
print(f"Search parameters: faculty={faculty_name}, day={search_day}, start={search_start},
end={search_end}")
if not all([faculty_name, search_day, search_start, search_end]):
return jsonify({
'available': False,
'message': 'All fields are required'
})
try:
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
# First verify faculty exists
cur.execute("SELECT id FROM faculty WHERE name = %s", (faculty_name,))
faculty_result = cur.fetchone()
if not faculty_result:
return jsonify({
'available': False,
'message': f'Faculty "{faculty_name}" not found'
})
faculty_id = faculty_result[0]
# Check if the time slot exactly matches one of the available slots
cur.execute("""
SELECT EXISTS (
SELECT 1 FROM schedules
WHERE faculty_id = %s
AND day = %s
AND start_time = %s::time
AND end_time = %s::time
)
""", (faculty_id, search_day, search_start, search_end))
is_exact_match = cur.fetchone()[0]
if is_exact_match:
return jsonify({
'available': True,
'message': f'{faculty_name} is available on {search_day} from {search_start} to
{search_end}'
})

Computer Science and Engineering (AI&ML) 22
Campus Connect: Smart tracking faculty and Scheduling System

else:
# Get all available slots for that day
cur.execute("""
SELECT start_time::text, end_time::text, room
FROM schedules
WHERE faculty_id = %s AND day = %s
ORDER BY start_time
""", (faculty_id, search_day))
available_slots = cur.fetchall()
return jsonify({
'available': False,
'message': f'{faculty_name} is not available during the requested time',
'free_slots': [{
'start_time': s[0],
'end_time': s[1],
'room': s[2]
} for s in available_slots]
})
except Exception as e:
print(f"Search error: {str(e)}")
return jsonify({
'available': False,
'message': f'Error: {str(e)}'
}), 500
finally:
if 'cur' in locals():
cur.close()
if 'conn' in locals():
conn.close()
@app.route("/bulk-upload", methods=['POST'])
def bulk_upload():
if not session.get('admin'):
return jsonify({'error': 'Unauthorized'}), 401
if 'file' not in request.files:
return jsonify({'error': 'No file uploaded'}), 400
file = request.files['file']
if file.filename == '':
return jsonify({'error': 'No file selected'}), 400
if not file.filename.endswith('.csv'):
return jsonify({'error': 'Please upload a CSV file'}), 400
try:
# Read the CSV file
stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
csv_data = csv.DictReader(stream)

Computer Science and Engineering (AI&ML) 23
Campus Connect: Smart tracking faculty and Scheduling System

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
success_count = 0
error_count = 0
errors = []
for row in csv_data:
try:
# Get faculty ID or create new faculty
cur.execute("SELECT id FROM faculty WHERE name = %s", (row['name'],))
faculty_result = cur.fetchone()
if faculty_result:
faculty_id = faculty_result[0]
else:
cur.execute("INSERT INTO faculty (name) VALUES (%s) RETURNING id",
(row['name'],))
faculty_id = cur.fetchone()[0]
# Insert schedule
cur.execute("""
INSERT INTO schedules (faculty_id, day, start_time, end_time, room)
VALUES (%s, %s, %s, %s, %s)
""", (
faculty_id,
row['day'],
row['start_time'],
row['end_time'],
row['room']
))
success_count += 1
except Exception as row_error:
error_count += 1
errors.append(f"Error in row {success_count + error_count}: {str(row_error)}")
print(f"Error in row: {row}, Error: {str(row_error)}")
conn.commit()
return jsonify({
'success': True,
'message': f'Upload complete. {success_count} schedules added, {error_count} errors.',
'errors': errors if errors else None
})
except Exception as e:
if 'conn' in locals():
conn.rollback()
print(f"Upload error: {str(e)}")
return jsonify({
'error': f'Error uploading file: {str(e)}'
}), 500

Computer Science and Engineering (AI&ML) 24
Campus Connect: Smart tracking faculty and Scheduling System

finally:
if 'cur' in locals():
cur.close()
if 'conn' in locals():
conn.close()
@app.route("/logout")
def logout():
session.pop('admin', None)
return redirect('/')
@app.route("/admin/dashboard")
def admin_dashboard():
if not session.get('admin'):
return redirect(url_for('login'))
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=DictCursor)
try:
cur.execute("""
SELECT s.*, f.name as faculty_name
FROM schedules s
JOIN faculty f ON s.faculty_id = f.id
ORDER BY f.name, s.day, s.start_time
""")
schedules = cur.fetchall()
return render_template('admin/dashboard.html', schedules=schedules)
except Exception as e:
flash(f'Error: {str(e)}', 'error')
return redirect(url_for('index'))
finally:
cur.close()
conn.close()
@app.route("/get-schedule/<int:schedule_id>")
def get_schedule(schedule_id):
if not session.get('admin'):
return jsonify({'error': 'Unauthorized'}), 401
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=DictCursor)
try:
cur.execute("""
SELECT s.*, f.name as faculty_name
FROM schedules s
JOIN faculty f ON s.faculty_id = f.id
WHERE s.id = %s
""", (schedule_id,))
schedule = cur.fetchone()

Computer Science and Engineering (AI&ML) 25
Campus Connect: Smart tracking faculty and Scheduling System

if not schedule:
return jsonify({'error': 'Schedule not found'}), 404
return jsonify({
'id': schedule['id'],
'faculty_id': schedule['faculty_id'],
'faculty_name': schedule['faculty_name'],
'day': schedule['day'],
'start_time': schedule['start_time'].strftime('%H:%M'),
'end_time': schedule['end_time'].strftime('%H:%M'),
'room': schedule['room'],
'is_temporary': schedule['is_temporary'],
'valid_until': schedule['valid_until'].strftime('%Y-%m-%d') if schedule['valid_until'] else
None
})
except Exception as e:
print(f"Error getting schedule: {str(e)}")
return jsonify({'error': str(e)}), 500
finally:
cur.close()
conn.close()
if __name__ == "__main__":
app.run(debug=True)
#database.py
import psycopg2
from psycopg2 import Error
DB_CONFIG = {
'dbname': 'campus_connect',
'user': 'postgres',
'password': 'indhu0504',
'host': 'localhost',
'port': '5432'
}
def create_tables():
conn = None # Initialize conn to None
try:
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
# Create faculty table
cur.execute("""
CREATE TABLE IF NOT EXISTS faculty (
id SERIAL PRIMARY KEY,
name VARCHAR(100) NOT NULL UNIQUE
)
""")

Computer Science and Engineering (AI&ML) 26
Campus Connect: Smart tracking faculty and Scheduling System

# Updated schedules table with busy flag
cur.execute("""
CREATE TABLE IF NOT EXISTS schedules (
id SERIAL PRIMARY KEY,
faculty_id INTEGER REFERENCES faculty(id),
day VARCHAR(10),
start_time TIME,
end_time TIME,
room VARCHAR(50),
is_temporary BOOLEAN DEFAULT FALSE,
is_busy BOOLEAN DEFAULT FALSE, -- Added busy flag
original_schedule_id INTEGER, -- Added reference to original schedule
original_start_time TIME,
original_end_time TIME,
valid_until DATE,
CONSTRAINT valid_times CHECK (start_time < end_time)
)
""")
# Updated deleted_schedules table with deleted_by field
cur.execute("""
DROP TABLE IF EXISTS deleted_schedules;
CREATE TABLE deleted_schedules (
id SERIAL PRIMARY KEY,
faculty_id INTEGER,
day VARCHAR(10),
start_time TIME,
end_time TIME,
room VARCHAR(50),
deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
reason VARCHAR(200),
deleted_by VARCHAR(100),
original_schedule_id INTEGER
)
""")
conn.commit()
print("Tables created successfully!")
except (Exception, Error) as error:
print("Error while connecting to PostgreSQL:", error)
finally:
if conn:
cur.close()
conn.close()
if __name__ == "__main__":
create_tables()
