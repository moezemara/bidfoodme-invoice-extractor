from ftplib import FTP_TLS as FTP
import ftplib
import re
import config

class FTP_CLIENT:
    def __init__(self):
        self.base_location = config.ftp["base_location"]
        self.ftp = None
        self.connect()
        
    def connect(self):
        try:        
            self.ftp = FTP(config.ftp["host"])
            
            self.ftp.login(config.ftp["user"], config.ftp["password"])
            self.ftp.prot_p()
            self.ftp.set_pasv(True)            
            
        except:
            print("Failed to start ftp connection")
            self.ftp = None


    def disconnect(self):
        try:
            self.ftp.quit()
        except:
            print("failed to disconnect ftp")
        
    def download(self):
        if not self.ftp: return
        
        dir_list = []
        self.ftp.cwd(self.base_location)
        self.ftp.dir(dir_list.append)

        try:
            files = self.ftp.nlst()
        except ftplib.error_perm as resp:
            if str(resp) == "550 No files found":
                print("No files in this directory")
            else:
                raise
        
        files = [file for file in files if re.search("\.pdf$", file)]
        for file in files:
            try:
                with open(f"downloads/{file}", "wb") as fp:
                    self.ftp.retrbinary(f"RETR {file}", fp.write)
                #self.ftp.retrbinary("RETR " + file ,open(f"downloads/{file}", 'wb').write)
            except:
                print (f"Error saving file: {file}")

        print("Files saved successfully")
        return files
    
    def upload(self, filename, directory):
        if not self.ftp: return
        
        try:
            self.ftp.mkd(f"{self.base_location}/{directory}")
        except:
            pass
        
        self.ftp.cwd(f"{self.base_location}/{directory}")
        
        with open(f"pdfs/{filename}","rb") as file:
            self.ftp.storbinary(f"STOR {filename}", file) 
        
        print(f"File: {filename} uploaded successfully")
         

    def delete(self, filename):
        self.ftp.cwd(f"{self.base_location}")
        try:
            self.ftp.delete(filename)
        except:
            print(f"Error deleting file: {filename}")

def main():
    client = FTP_CLIENT()
    client.delete("test.txt")