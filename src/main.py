#!/usr/bin/env python
#!/usr/bin/env python
import os
import warnings
import sys
from datetime import datetime
from law_automation.crew import LawAutomationCrew


warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# Create output directory if it doesn't exist
os.makedirs('output', exist_ok=True)


module_name = "law_automation.py"
class_name = "LawAutomation"


requirements = """
A system that can help an attorney to automate the law firm's processes.
The title of the system says "Roman Kostenko's Law Office"

All frontend should be built with Streamlit.
There are 3 main components:
1. Home Page with a calendar that can add and remove event.
Events are saved in sql with those fields:
-Event Name
-Location
-Time
-Details
-Client
-Details
Under the calender list all events based on the date.
Can expand and fold events when toggle the date.

2. Legal Research and writing, it should be able to research the law, and provide the attorney with the relevant laws and cases based on Arizona Law
It should be able to write the legal documents based on the research and the attorney's instructions.
In this process, we need 1 agent with the ability to search the internet for the relevant laws and cases based on Arizona Law.
Use SerperDevTool to search the internet for the relevant laws and cases based on Arizona Law.
Need 1 evaluation agent to evaluate the quality of the research and the writing. Evaluate the research and the writing based on the Arizona Law. Only output the relevant laws and cases based on the Arizona Law.
Use OpenAI API to call both agents.
Both agents should be able to use sqlite3 database to store client records, the research and the writing.
Both agents should be able to use RAG technology to search the internet for the relevant laws and cases based on Arizona Law.
Both agents should be able to use memory and context to remember the research and the writing.
To create a simple chatbox UI for this component, we need to use Streamlit.


3. Billing and Payment
There is a + button to add a new client, and a - button to remove a client.
when a new client is added, we need to create a new client record in the database.
when a client is removed, we need to delete the client record from the database.
when a client is updated, we need to update the client record in the database.
when a client is viewed, we need to view the client record from the database.
The client record should have the following fields:
- Name
- Email
- Phone
- Address
- City
- State
- Zip
- Country
- Case Number
- Case Type
- Case Status (URL to the case status page)
- Case Description
- Billing services:
 - Service Name
 - Service Description
 - Service Price
 - Service Quantity
 - Service Total
 - Service Date

Inside the client record detail page:
There is a + button to add a new billing service, and a - button to remove a billing service.
Once a billing service is added, the system should calculate the total price of the billing services.
Once the total price is calculated, the system should display the total price in the client record detail page.
Once the total price is reached 3500, the system will generate a PDF form with all detailed billing service and the total price.
Attorney can download the PDF form and send it to the client to collect the payment.
Attorney can also edit the billing service and the total price and re-generate the PDF form.
Attorney can mark the invoice as paid if the client has paid the total price.
Attorney can also mark the invoice as unpaid if the client has not paid the total price.
Attorney can see the list of all invoices and the status of the invoices.
The system will automatically send a PDF form with all detailed billing service payment reminder email to the client to collect the payment using SendGrid API.
"""


def run():
   """
   Run the law automation crew.
   """
   inputs = {
       'requirements': requirements,
       'module_name': module_name,
       'class_name': class_name
   }
   result = LawAutomationCrew().crew().kickoff(inputs=inputs)
   return result

if __name__ == "__main__":
    run()
    