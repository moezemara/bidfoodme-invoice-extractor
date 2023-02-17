import config
import schedule
import time
import extractor

def job():
    print("Cron Started!")
    extractor.start()

#schedule.every(10).minutes.do(job)
#schedule.every().hour.do(job)

schedule.every().day.at("12:00").do(job)

while 1:
    schedule.run_pending()
    time.sleep(1)