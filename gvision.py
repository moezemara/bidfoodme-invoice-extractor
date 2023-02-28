
from google.oauth2 import service_account
from google.cloud import vision
import io
import config

class GVision:
    def __init__(self):
        self.credentials = service_account.Credentials.from_service_account_file("bme-automation-4eca6e4c4791.json")
        self.client = vision.ImageAnnotatorClient(credentials=self.credentials)

    def detect_text(self, path):
        with io.open(path, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)

        response = self.client.text_detection(image=image)
        texts = response.text_annotations
        
        detected_base = ""
        invoice_number = ""
        for i in range(len(texts)):
            if texts[i].description == "IN":
                try:
                    detected_base = texts[i+2].description.upper() ## base location
                    for base in config.bases["core_bases"]:
                        if base in detected_base:
                            for j in range(i, i+5):
                                invoice_number += texts[j].description
                                if invoice_number[-1].isnumeric(): return invoice_number
                            return invoice_number  
                except: continue