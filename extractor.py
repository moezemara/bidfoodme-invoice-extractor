import cv2
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import easyocr
import re
import ftp
import os

def convert_pdf_to_image(filepath):
    try:
        
        pages = convert_from_path(filepath, 350)
    except:
        print(f"Could not convert file: {filepath} to image")
        return 
    i = 0
    for page in pages:
        i = i+1
        image_name = "images/Page_" + str(i) + ".jpg"
        page = page.transpose(Image.Transpose.ROTATE_90)
        page.save(image_name, "JPEG")
        
    return i

def convert_image_to_pdf(images_path, invoice_number):
    converted_list = []

    for path in images_path:
        image = Image.open(path)
        RGB_image = image.convert("RGB")
        RGB_image = RGB_image.transpose(Image.Transpose.ROTATE_270)
        converted_list.append(RGB_image)
        
    if converted_list == []: return
    
    converted_list[0].save(f'pdfs/{invoice_number}.pdf', save_all=True, append_images=converted_list[1:])

def extract_text(reader, image_path):
    invoice_number = ""
    lpo = ""
    is_valid_page = False
    is_sub_page = False
    
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'

    x0 = 2371
    y0 = 772
    x1 = 1683
    y1 = 731
    
    
    x0_title = 819
    y0_title = 518
    x1_title = x0_title + 1377
    y1_title = y0_title + 311
    
    # load the original image
    image = cv2.imread(image_path)
    
    # cropping image img = image[y0:y1, x0:x1]
    cropped_image = image[y0:y0+y1, x0:x0+x1]
    title_cropped_image = image[y0_title:y1_title, x0_title:x1_title]
    
    ret,thresh_title = cv2.threshold(title_cropped_image,120,255,cv2.THRESH_BINARY)
    
    result_title = reader.readtext(image= thresh_title, paragraph = True)
    title = "TAX INVOICE / DELIVERY NOTE"
    
    # cv2.imshow("cropped", title_cropped_image)
    # cv2.waitKey(0)

    for value in result_title:
        if ("TAX" in value[1] or "DELIVERY NOTE" in value[1]):
            is_valid_page = True
            break
            
    if not is_valid_page: return invoice_number, lpo, is_valid_page, is_sub_page
    

    
    # convert the image to black and white for better OCR
    ret,thresh1 = cv2.threshold(cropped_image,120,255,cv2.THRESH_BINARY)
    
    result = reader.readtext(thresh1)
    
    for value in result:        
        if re.search("IN-[A-Z]{1,3}-[0-9]+", value[1]):
            invoice_number = value[1]
                
        if "LPO" in value[1]:
            x0 = value[0][0][0]
            y0 = value[0][0][1]
            x1 = value[0][1][0]
            y1 = value[0][2][1]
            
            if(x0 > x1): x0, x1 = x1, x0
            if(y0 > y1): y0, y1 = y1, y0
            
            x0 += 216
            x1 = x0 + 369
            y1 = y0 + 111
            
            mini_cropped_area = thresh1[y0:y1, x0:x1]
            
            multiline_LPO_result = reader.readtext(image= mini_cropped_area, paragraph = True)
            
            for LPO_value in multiline_LPO_result:
                lpo += LPO_value[1].replace(" ", "")
            
            # cv2.imshow("cropped", mini_cropped_area)
            # cv2.waitKey(0)

    if invoice_number == "" and lpo == "": is_sub_page = True
    
    return invoice_number, lpo, is_valid_page, is_sub_page

def processfiles(count, filename):
    reader = easyocr.Reader(['en'], gpu=True) # this needs to run only once to load the model into memory

    extracts = []
    invoices_images = {}
    
    for i in range(1, count+1):
        image_path = f"images/Page_{i}.jpg"
        invoice_number, lpo, is_valid_page, is_sub_page = extract_text(reader, image_path)
        extract = {"Page": i, "invoice_number": invoice_number, "lpo": lpo, "is_valid_page": is_valid_page, "is_sub_page": is_sub_page}
        extracts.append(extract)        

    if extracts == []: return {}
    current_invoice = ""
    
    company_code_pattern = r"IN-[A-Z0-9-]{2,4}"
    invoice_number_pattern = r"[0-9]{5,}"

    company_codes = {}
    squence_digits = {}
    invoice_length = {}
    sequence_list = []
    
    for index in range(len(extracts)):
        if not extracts[index]["is_valid_page"] or extracts[index]["is_sub_page"]:
            sequence_list.append(-2)
            continue
        
        match = re.findall(company_code_pattern, extracts[index]["invoice_number"])
        numbers_match = re.findall(invoice_number_pattern, extracts[index]["invoice_number"])
                
        if numbers_match == []: 
            sequence_list.append(-1)
            continue
        else:
            if int(numbers_match[0]) in sequence_list:
                extracts[index]["invoice_number"] = ""
                extracts[sequence_list.index(int(numbers_match[0]))]["invoice_number"] = ""
                sequence_list.append(-1)
                sequence_list[sequence_list.index(int(numbers_match[0]))] = -1
            else:
                sequence_list.append(int(numbers_match[0]))
        
        if match == []: continue
        
        if len(extracts[index]["invoice_number"]) not in invoice_length:
            invoice_length[len(extracts[index]["invoice_number"])] = 1
        else:
            invoice_length[len(extracts[index]["invoice_number"])] += 1
        
        if len(numbers_match[0]) not in squence_digits:
            squence_digits[len(numbers_match[0])] = 1
        else:
            squence_digits[len(numbers_match[0])] += 1
        
        if match[0] not in company_codes:
            company_codes[match[0]] = 1
        else:
            company_codes[match[0]] += 1
    
    correct_invoice_length = max(invoice_length, key=invoice_length.get)
    correct_sequence_digits = max(squence_digits, key=squence_digits.get)
    correct_company_code = max(company_codes, key=company_codes.get)    
    
    last_correct = -1
    last_correct_index = -1
    last_non_correct_indexes = []
    
    
    difference = 0
    for i in range(len(sequence_list)):
        if sequence_list[i] == -2 : continue
        
        if len(str(sequence_list[i])) == correct_sequence_digits:
            last_correct = sequence_list[i]
            last_correct_index = i
            continue
        
        if len(str(sequence_list[i])) != correct_sequence_digits or sequence_list[i] == -1:
            last_non_correct_indexes.append(i)
            difference += 1
        
        if last_correct != -1 and last_non_correct_indexes != []:
            for index in last_non_correct_indexes:
                if index < last_correct_index:
                    sequence_list[index] = last_correct + difference
                else:
                    sequence_list[index] = last_correct - difference
                last_correct = sequence_list[i]
                last_correct_index = i
                difference -= 1
            last_non_correct_indexes = []
            difference = 0
        else: continue


    for i in range(len(extracts)):
        if not extracts[i]["is_valid_page"] or extracts[i]["is_sub_page"]:
            continue
        
        invoice_number = extracts[i]["invoice_number"]
        numbers_match = re.findall(invoice_number_pattern, invoice_number)
        
        if len(invoice_number) == correct_invoice_length and correct_company_code in invoice_number and len(numbers_match[0]) == correct_sequence_digits:
            continue
        else:
            invoice_number = correct_company_code + str(sequence_list[i])
            extracts[i]["invoice_number"] = invoice_number
            continue
    
    
    for extract in extracts:
        if not extract["is_valid_page"]:
            continue

        if not extract["is_sub_page"]:
            page_id = extract["Page"]
            current_invoice = extract["invoice_number"]
            invoices_images[extract["invoice_number"]] = []
            invoices_images[extract["invoice_number"]].append(f"images/Page_{page_id}.jpg")
        else:
            page_id = extract["Page"]
            invoices_images[current_invoice].append(f"images/Page_{page_id}.jpg")
    print(invoices_images)

    return invoices_images
    
def emptyfiles():
    dirs = ["images", "pdfs"]
    for directory in dirs:
        for f in os.listdir(directory):
            os.remove(os.path.join(directory, f))

def start():    
    ftpclient = ftp.FTP_CLIENT()
    full_files = ftpclient.download()
    ftpclient.disconnect()

    if len(full_files) == 0: return
    for full_filename in full_files:
        count = convert_pdf_to_image(f"downloads/{full_filename}")
        invoices_images = processfiles(count, full_filename)
        ftpclient.connect()

        for key, value in invoices_images.items():
            if value == "" or key == "":
                continue
            convert_image_to_pdf(value, key) # key is invoice number

        for key, value in invoices_images.items():
            if value == "" or key == "":
                continue
            filename = f"{key}.pdf"
            foldername = full_filename.split(".")[0]
            #ftpclient.upload(filename, foldername)
        #ftpclient.delete(filename)
        ftpclient.disconnect()
        #emptyfiles()