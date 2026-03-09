import sqlite3
from typing import List, Dict
from datetime import datetime
import streamlit as st
from fpdf import FPDF
import requests

class LawAutomation:
    def __init__(self):
        self.conn = self._connect_to_db()
        self._create_tables()
        self.streamlit_interface = False

    def _connect_to_db(self):
        conn = sqlite3.connect(':memory:')
        return conn

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT,
            location TEXT,
            time TEXT,
            details TEXT,
            client TEXT
        )''')
        cursor.execute('''
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, phone TEXT, address TEXT,
            city TEXT, state TEXT, zip TEXT, country TEXT,
            case_number TEXT, case_type TEXT, case_status TEXT, 
            case_description TEXT
        )''')
        cursor.execute('''
        CREATE TABLE billing_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            service_name TEXT,
            service_description TEXT,
            service_price REAL,
            service_quantity INTEGER,
            service_total REAL,
            service_date TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )''')
        cursor.execute('''
        CREATE TABLE research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            research TEXT,
            writing TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )''')
        self.conn.commit()

    # Event Management
    def add_event(self, event_name: str, location: str, time: str, details: str, client: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO events (event_name, location, time, details, client) 
            VALUES (?, ?, ?, ?, ?)''', (event_name, location, time, details, client))
        self.conn.commit()

    def remove_event(self, event_id: int) -> None:
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        self.conn.commit()

    def list_events(self, date: str) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM events WHERE time LIKE ?', (f"{date}%",))
        events = cursor.fetchall()
        return [{
            "id": row[0], "event_name": row[1], "location": row[2],
            "time": row[3], "details": row[4], "client": row[5]
        } for row in events]

    def toggle_event_visibility(self, date: str) -> None:
        # Simplification: No actual UI toggle implemented
        events = self.list_events(date)
        print(f"Events on {date}: {events}")

    # Legal Research and Writing
    def perform_legal_research(self, query: str) -> List[Dict]:
        # Placeholder for SerperDevTool or similar library call
        response = requests.get(f"https://api.legalresearch.com/search?query={query}")
        return response.json()

    def evaluate_research_and_writing(self, research_id: int) -> Dict:
        # Placeholder for using OpenAI API or similar
        response = requests.get(f"https://api.legalresearch.com/evaluate?research_id={research_id}")
        return response.json()

    def store_research_and_writing(self, client_id: int, research: str, writing: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO research (client_id, research, writing) VALUES (?, ?, ?)''', 
            (client_id, research, writing))
        self.conn.commit()
        return cursor.lastrowid

    # Billing and Payment
    def add_client(self, name: str, email: str, phone: str, address: str, city: str, state: str, zip_code: str, country: str, case_number: str, case_type: str, case_status: str, case_description: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO clients (name, email, phone, address, city, state, zip, country, case_number, case_type, case_status, case_description) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
            (name, email, phone, address, city, state, zip_code, country, case_number, case_type, case_status, case_description))
        self.conn.commit()
        return cursor.lastrowid

    def remove_client(self, client_id: int) -> None:
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM clients WHERE id = ?', (client_id,))
        self.conn.commit()

    def update_client(self, client_id: int, **kwargs) -> None:
        cursor = self.conn.cursor()
        columns = ', '.join(f'{k} = ?' for k in kwargs)
        values = list(kwargs.values())
        values.append(client_id)
        cursor.execute(f'UPDATE clients SET {columns} WHERE id = ?', values)
        self.conn.commit()

    def view_client(self, client_id: int) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
        client = cursor.fetchone()
        if client:
            return {
                "id": client[0], "name": client[1], "email": client[2],
                "phone": client[3], "address": client[4], "city": client[5],
                "state": client[6], "zip": client[7], "country": client[8],
                "case_number": client[9], "case_type": client[10], 
                "case_status": client[11], "case_description": client[12]
            }
        return {}

    def add_billing_service(self, client_id: int, service_name: str, service_description: str, service_price: float, service_quantity: int, service_date: str) -> None:
        service_total = service_price * service_quantity
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO billing_services (client_id, service_name, service_description, service_price, service_quantity, service_total, service_date) 
            VALUES (?, ?, ?, ?, ?, ?, ?)''', 
            (client_id, service_name, service_description, service_price, service_quantity, service_total, service_date))
        self.conn.commit()
        self.calculate_total_price(client_id)

    def remove_billing_service(self, client_id: int, service_id: int) -> None:
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM billing_services WHERE id = ? AND client_id = ?', (service_id, client_id))
        self.conn.commit()

    def calculate_total_price(self, client_id: int) -> float:
        cursor = self.conn.cursor()
        cursor.execute('SELECT SUM(service_total) FROM billing_services WHERE client_id = ?', (client_id,))
        total = cursor.fetchone()[0]
        if total is None:
            total = 0.0
        return total

    def generate_invoice_pdf(self, client_id: int) -> str:
        total_price = self.calculate_total_price(client_id)
        if total_price >= 3500:
            client = self.view_client(client_id)
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Invoice for {client['name']}", ln=True, align='C')
            cursor = self.conn.cursor()
            cursor.execute('SELECT service_name, service_description, service_price, service_quantity, service_total FROM billing_services WHERE client_id = ?', (client_id,))
            services = cursor.fetchall()
            for service in services:
                pdf.cell(200, 10, txt=str(service), ln=True)
            pdf.cell(200, 10, txt=f"Total Price: ${total_price}", ln=True)
            file_path = f"invoice_client_{client_id}.pdf"
            pdf.output(file_path)
            return file_path
        return ""

    def send_payment_reminder(self, client_id: int) -> None:
        client = self.view_client(client_id)
        total_price = self.calculate_total_price(client_id)
        if total_price > 0:
            pdf_path = self.generate_invoice_pdf(client_id)
            if pdf_path:
                email_data = {
                    "personalizations": [{
                        "to": [{"email": client['email']}],
                        "subject": f"Payment Reminder for Case {client['case_number']}"
                    }],
                    "from": {"email": "lawoffice@example.com"},
                    "content": [{"type": "text/plain", "value": f"Please find the attached invoice for ${total_price} due."}],
                    "attachments": [{
                        "content": open(pdf_path, "rb").read().encode("base64"),
                        "type": "application/pdf",
                        "filename": "invoice.pdf"
                    }]
                }
                headers = {
                    'Authorization': 'Bearer YOUR_SENDGRID_API_KEY',
                    'Content-Type': 'application/json'
                }
                response = requests.post('https://api.sendgrid.com/v3/mail/send', 
                                         json=email_data, headers=headers)
                print(f'Status Code: {response.status_code}, Message: {response.content.decode()}')

    def mark_invoice_status(self, client_id: int, is_paid: bool) -> None:
        # This could update a real payment status database
        print(f"Invoice status for client_id {client_id} marked as {'paid' if is_paid else 'unpaid'}.")

    # Helper Methods
    def _setup_streamlit_interface(self):
        # Simplified Streamlit setup, more complex logic required for full functionality
        self.streamlit_interface = True
        st.title("Roman Kostenko's Law Office - Legal Research")
        st.text_input("Enter your query for legal research based on Arizona Law:")

# Usage
law_automation = LawAutomation()
# law_automation._setup_streamlit_interface() # Uncomment this to run with Streamlit interface if desired
# Followed by any other interactive code needed for actual operation