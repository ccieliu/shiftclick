import requests
import smtplib
import datetime
from pprint import pprint
from requests_toolbelt.multipart.encoder import MultipartEncoder
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from teamBotToken import teamBotToken
executor = ThreadPoolExecutor(2)


# markdown
# <@personEmail:yuxuliu@cisco.com>
# <@all>


class alerter(object):
    def __init__(self):
        self.accessToken = teamBotToken.token
        self.botId = "Y2lzY29zcGFyazovL3VzL0FQUExJQ0FUSU9OL2Q3NzQ5MmY1LTFlNGYtNGJhZC04OTAzLTI0MDVlNGFkNmFkYQ"
        self.FTDroomid = "Y2lzY29zcGFyazovL3VzL1JPT00vMDZiMDU1ODAtOGI0My0xMWU5LWFiYmUtOTcyMDY5ZDAzNDY0"
        self.ASAroomid = "Y2lzY29zcGFyazovL3VzL1JPT00vZDA4YTYzNzAtOGNmNC0xMWU5LWIyY2EtODdjODEwZjA3MTU2"

    def sendMessageToRoom(self, cecId, triggerCec, queueName):
        if queueName == "FTD_ISE":
            roomId = self.FTDroomid
        elif queueName == "ASA":
            roomId = self.ASAroomid
        messageContext = MultipartEncoder({
            'roomId': roomId,
            "markdown": "\r\n ************************  \r\n**SHIFT ALERT:** <@all>  \r\n PLS ON SHIFT: **" + cecId+"**  \r\n TRIGGER: "+triggerCec+"  \r\n ************************  \r\n"
        }
        )
        r = requests.post('https://api.ciscospark.com/v1/messages', data=messageContext,
                          headers={'Authorization': self.accessToken,
                                   'Content-Type': messageContext.content_type})
        mailFrom = "smartclick@cisco.com"
        mailRcptTo = cecId+"@cisco.com"
        SUBJECT = "[SHIFT ALERT] "+cecId.upper()+" ON SHIFT NOW //  "+str(datetime.datetime.now())[5:19]
        msg = "Hi "+cecId +",\r\rPlease on shift now.\r\r------\rShiftClick Alpha v1.0.3"
        msg = MIMEText(msg)
        msg['Subject'] = SUBJECT
        msg['To'] = mailRcptTo
        msg['From'] = mailFrom

        mySmtpClient = smtplib.SMTP(host="xch-rcd-014.cisco.com", port=25)
        mySmtpClient.sendmail(from_addr=mailFrom,
                              to_addrs=mailRcptTo, msg=msg.as_string())
        mySmtpClient.quit()
