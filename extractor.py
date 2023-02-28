import cv2
from PIL import Image
from pdf2image import convert_from_path
import easyocr
import re
import ftp
import os
import json
import config
import gvision

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
        #page = page.transpose(Image.Transpose.ROTATE_90)
        page.save(image_name, "JPEG")
        
    return i

def convert_image_to_pdf(images_path, invoice_number):
    converted_list = []

    for path in images_path:
        image = Image.open(path)
        RGB_image = image.convert("RGB")
        #RGB_image = RGB_image.transpose(Image.Transpose.ROTATE_270)
        converted_list.append(RGB_image)
        
    if converted_list == []: return
    
    converted_list[0].save(f'pdfs/{invoice_number}.pdf', save_all=True, append_images=converted_list[1:])

def is_similar_word(correct_word, check_word):
    count = 0
    for i in range(len(correct_word)):
        try:
            if correct_word[i] == check_word[i]: count += 1
        except:
            break
    
    if (count/len(correct_word))*100 > 70: return True

def best_match_base(invoice):
    base_pattern = r"IN-[A-Z0-9-]{2,4}"
    invoice = invoice.upper()
    match = re.findall(base_pattern, invoice)
    
    if match == []: return False
    
    incorrect_base = match[0]
    
    base_scores = {}
    for base in config.bases["full_bases"]:
        count = 0
        for i in range(len(base)):
            try:
                if base[i] == incorrect_base[i]:
                    count += 1
            except:
                break
        
        base_scores[base] = (count/len(base))*100

    return max(base_scores, key=base_scores.get)
            
def add(x, y) -> str:
    return str(int(x) + int(y)).zfill(max(len(x), len(y)))
   
def extract_text(reader, image_path, orientation = -1):
    invoice_number = ""
    lpo = ""
    is_valid_page = False
    is_sub_page = False
        
    x0 = 2200
    y0 = 675
    x1 = 2100
    y1 = 962
    
    
    
    x0_title = 605
    y0_title = 511
    x1_title = x0_title + 2122
    y1_title = y0_title + 672
    
    # load the original image
    image = cv2.imread(image_path)
    
    if orientation != -1: image = cv2.rotate(image, orientation)
        
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
    
    # cv2.imshow("cropped", cropped_image)
    # cv2.waitKey(0)
    
    for i in range(len(result)):        
        if re.search("IN-[A-Z]{1,3}-[0-9]+", result[i][1]):
            invoice_number = result[i][1]
        
        if invoice_number == "" and is_similar_word("Invoice number:", result[i][1]):
            try:
                invoice_number = result[i+1][1]
            except: pass
                
        if "LPO" in result[i][1]:
            x0 = result[i][0][0][0]
            y0 = result[i][0][0][1]
            x1 = result[i][0][1][0]
            y1 = result[i][0][2][1]
            
            if(x0 > x1): x0, x1 = x1, x0
            if(y0 > y1): y0, y1 = y1, y0
            
            x0 += 216
            x1 = x0 + 369
            y1 = y0 + 111
            
            mini_cropped_area = thresh1[y0:y1, x0:x1]
            
            multiline_LPO_result = reader.readtext(image= mini_cropped_area, paragraph = True)
            
            for LPO_value in multiline_LPO_result:
                lpo += LPO_value[1].replace(" ", "")
            
            # cv2.imshow("mini cropped", mini_cropped_area)
            # cv2.waitKey(0)

    if invoice_number == "" and lpo == "": is_sub_page = True
    
    return invoice_number, lpo, is_valid_page, is_sub_page

def processfiles(count):
    reader = easyocr.Reader(['en'], gpu=True) # this needs to run only once to load the model into memory

    extracts = []
    invoices_images = {}


    orientation = get_correct_orientation(reader, count)
    
    if orientation == -2: return {}
    
    for i in range(1, count+1):
        image_path = f"images/Page_{i}.jpg"
        invoice_number, lpo, is_valid_page, is_sub_page = extract_text(reader, image_path, orientation)
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
            sequence_list.append("-2")
            continue
        
        match = re.findall(company_code_pattern, extracts[index]["invoice_number"])
        numbers_match = re.findall(invoice_number_pattern, extracts[index]["invoice_number"])
                
        if numbers_match == []: 
            sequence_list.append("-1")
            continue
        else:
            if numbers_match[0] in sequence_list:
                extracts[index]["invoice_number"] = ""
                extracts[sequence_list.index(numbers_match[0])]["invoice_number"] = ""
                sequence_list.append("-1")
                sequence_list[sequence_list.index(numbers_match[0])] = "-1"
            else:
                sequence_list.append(numbers_match[0])
        
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
        if sequence_list[i] == "-2" : continue
        
        if len(sequence_list[i]) == correct_sequence_digits:
            last_correct = sequence_list[i]
            last_correct_index = i
            continue
        
        if len(sequence_list[i]) != correct_sequence_digits or sequence_list[i] == "-1":
            last_non_correct_indexes.append(i)
            difference += 1
        
        if last_correct != -1 and last_non_correct_indexes != []:
            for index in last_non_correct_indexes:
                if index < last_correct_index:
                    sequence_list[index] = add(last_correct, str(difference)) #last_correct + difference
                else:
                    sequence_list[index] = add(last_correct, str(-difference)) #last_correct - difference
                last_correct = sequence_list[i]
                last_correct_index = i
                difference -= 1
            last_non_correct_indexes = []
            difference = 0
        else: continue

    logs = {}
    error_list = []
    gvision_client = gvision.GVision()
    gvision_uses = 0
    
    for i in range(len(extracts)):
        if not extracts[i]["is_valid_page"] or extracts[i]["is_sub_page"]:
            continue
        
        invoice_number = extracts[i]["invoice_number"]
        numbers_match = re.findall(invoice_number_pattern, invoice_number)
        page_num = extracts[i]["Page"]
        
        if numbers_match != [] and len(invoice_number) == correct_invoice_length and correct_company_code in invoice_number and len(numbers_match[0]) == correct_sequence_digits:
            continue
        else:
            correct_base = best_match_base(invoice_number)
            orig_invoice = invoice_number
            
            if correct_base and numbers_match != [] and len(numbers_match[0]) == correct_sequence_digits:
                invoice_number = correct_base + numbers_match[0]
            else:
                ## try gvision
                gvision_invoice = gvision_client.detect_text(f"images/Page_{page_num}.jpg")
                if gvision_invoice: 
                    invoice_number = gvision_invoice
                    gvision_uses += 1
                    extracts[i]["invoice_number"] = invoice_number
                    continue
                else:
                    invoice_number = correct_company_code + sequence_list[i]
                
            extracts[i]["invoice_number"] = invoice_number
            
            if orig_invoice == invoice_number: continue
            
            error_list.append({"invoice_number": invoice_number, "original_invoice": orig_invoice, "page_number": page_num})
            continue
    
    if gvision_uses != 0:   logs["gvision_uses"] = gvision_uses
    if error_list != []: logs["errors"] = error_list
    
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

    return invoices_images, logs
    
def emptyfiles():
    dirs = ["images", "pdfs"]
    for directory in dirs:
        for f in os.listdir(directory):
            os.remove(os.path.join(directory, f))

def is_correct_orientation(reader, image_path, orientation = -1):
    x0_title = 605
    y0_title = 511
    x1_title = x0_title + 2122
    y1_title = y0_title + 672
        
    # load the original image
    image = cv2.imread(image_path)
    
    if orientation != -1: 
        image = cv2.rotate(image, orientation)
    
    # cv2.imshow("image", image)
    # cv2.waitKey(0)
    
    
    title_cropped_image = image[y0_title:y1_title, x0_title:x1_title]
    
    
    
    ret,thresh_title = cv2.threshold(title_cropped_image,120,255,cv2.THRESH_BINARY)
    
    result_title = reader.readtext(image= thresh_title, paragraph = True)
    title = "TAX INVOICE / DELIVERY NOTE"
    
    for value in result_title:
        if ("TAX" in value[1] or "DELIVERY NOTE" in value[1]):
            return True
            
    return False

def get_correct_orientation(reader, count):
    orientations = [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]
    
    for i in range(1, count+1):
        image_path = f"images/Page_{i}.jpg"
        if not is_correct_orientation(reader, image_path):
            for orientation in orientations:
                if is_correct_orientation(reader, image_path, orientation=orientation): return orientation
        else: return -1
    return -2

def save_logs(name, logs):
    with open(f"logs/{name}.json", "w") as outfile:
        json.dump(logs, outfile, indent=4, sort_keys=True)
      
def start():
    ftpclient = ftp.FTP_CLIENT()
        
    full_files = ftpclient.download()
    ftpclient.disconnect()
    
    if len(full_files) == 0: return
    
    for full_filename in full_files:
        emptyfiles()
        foldername = full_filename.split(".pdf")[0]
        count = convert_pdf_to_image(f"downloads/{full_filename}")
        invoices_images, logs = processfiles(count)
        ftpclient.connect()

        for key, value in invoices_images.items():
            if value == "" or key == "":
                continue
            convert_image_to_pdf(value, key) # key is invoice number

        if logs != []:
            save_logs(foldername, logs)
            ftpclient.upload(f"{foldername}.json", "logs", "Logs")

        for key, value in invoices_images.items():
            if value == "" or key == "":
                continue
            filename = f"{key}.pdf"
            ftpclient.upload(filename, "pdfs", "Processed")
        ftpclient.move(filename = full_filename, source = "", destination = "Archived")
        ftpclient.disconnect()