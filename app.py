from flask import Flask, render_template, request, render_template, session, url_for, redirect, flash
from authCec import author
from dbConnect import backEnd
import datetime
from concurrent.futures import ThreadPoolExecutor
from notice import alerter

app = Flask(__name__)
app.secret_key = u"dLhwX<<sK/C7:=XTSPy^*P&pcSka5@^;h:bx;>qZN{f3Ta/cswNQ^U&RUS!p.KHr~n/+;.g.zBF]Q7/u*8~x/hTDFvxe9y;x5~ex/XSX!4Hk_g7tyfXFGBHYGVCH"
mybackEnd = backEnd()
executor = ThreadPoolExecutor()

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = datetime.timedelta(hours=9)


def checkUserLogined():
    if session.get("cecId") is None:
        return False
    if session.get("cecId"):
        return True


def converStatusIdToStatusStr(stautsId):
    if stautsId == 0:
        status = "ON"
    elif stautsId == 2:
        status = "OFF"
    elif stautsId == 3:
        status = "WFH"
    elif stautsId == 4:
        status = "MOBILE"
    elif stautsId == 5:
        status = "OTHER"
    elif stautsId == 6:
        status = "SHADOW"
    else:
        status = "UNKNOW"
    return(status)


def getLoginCec():
    return session.get("cecId")


@app.errorhandler(404)
def page_not_found(e):
    return "404 Page not found, if you need any help, please contact yuxuliu@cisoc.com", 404


@app.route("/")
def index():
    if request.method == 'GET':
        if checkUserLogined():
            cecId = getLoginCec()
            queueId = mybackEnd.checkEngineerInfo(
                cecId=cecId, infoName="queueId")
            if queueId:
                queueName = mybackEnd.checkQueueInfo(
                    queueId=queueId, infoName="queueName")
                
            else:
                queueName=None
                queueId=None
            queueList = mybackEnd.db.queueInfo.find().sort("queueId")
            shiftDate = request.args.get('shiftDate', None)
            if shiftDate != None:
                flash(message="History: "+shiftDate)
            else:
                shiftDate = str(datetime.datetime.now())[:10]

            shiftDataSet = []
            for i in queueList:
                queue = i["queueName"]
                cseSum = mybackEnd.getCseSum(i["queueId"], shiftDate=shiftDate)
                caseSum = mybackEnd.getQueueCaseSum(
                    i["queueId"], shiftDate=shiftDate)
                if (cseSum == 0) or (caseSum) == 0:
                    caseAvg = 0
                    caseProgress = "0%"
                else:
                    caseAvg = round(caseSum/cseSum, 2)
                    caseProgress = str(round(caseSum/30, 2)*100)+"%"

                # print("Append into shiftDataSet: " +
                    #   str([queue, cseSum, caseSum, caseAvg, caseProgress]))
                shiftDataSet.append(
                    [queue, cseSum, caseSum, caseAvg, caseProgress])

            returnData = {"cecId": cecId,
                          "queueName": queueName,
                          "shiftDataSet": shiftDataSet}
            sumCecSum = 0
            sumSrsum = 0
            for i in shiftDataSet:
                sumCecSum = i[1]+sumCecSum
                sumSrsum = i[2]+sumSrsum
            if (sumCecSum == 0) or (sumSrsum) == 0:
                sumAvg = 0
            else:
                sumAvg = round(sumSrsum/sumCecSum, 2)
            sumList = [sumCecSum, sumSrsum, sumAvg]
            returnData.update({"sumList": sumList})
            print(returnData)
            return render_template("dashboard.html", returnData=returnData)
        else:
            return redirect(url_for("login"))
    else:
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if checkUserLogined():
            return(redirect(url_for("index")))
        else:
            return render_template("login.html")
    elif request.method == 'POST':
        myauthor = author()
        if myauthor.authenticate(request.form['cec'],
                                 request.form['password']):
            session.clear()
            session["cecId"] = request.form['cec']
            return redirect(url_for('index'))
        else:
            flash("Login failed, please login again.")
            return redirect(url_for('login'))


@app.route('/queue/<queueName>/', methods=['GET', 'POST'])
def shiftTable(queueName):
    if checkUserLogined():
        if request.method == 'GET':
            if mybackEnd.db.queueInfo.find_one({"queueName": queueName}) == None:
                flash(
                    "Error: No that queue, if you need add a queue, please contact yuxuliu@cisco.com")
                return redirect(url_for("index"))
            else:
                returnData = {}
                loginCecId = getLoginCec()
                shiftDate = request.args.get('shiftDate', None)
                if shiftDate != None:
                    returnData.update({"history": "0"})
                    flash(message="History: "+shiftDate)
                else:
                    shiftDate = str(datetime.datetime.now())[:10]
                loginQueueId = mybackEnd.checkEngineerInfo(
                    cecId=loginCecId, infoName="queueId")
                loginQueueName = mybackEnd.checkQueueInfo(
                    queueId=loginQueueId, infoName="queueName")
                queueList = mybackEnd.db.queueInfo.find().sort("queueId")

                queueNameList = []
                for i in queueList:
                    queueNameList.append(i["queueName"])

                queueId = mybackEnd.db.queueInfo.find_one(
                    {"queueName": queueName})["queueId"]

                announcement = mybackEnd.checkQueueInfo(
                    queueId, "announcement")

                onShiftInfoResult = mybackEnd.db.shiftInfo.find_one(
                    {"queueId": queueId, "shiftPointer": True, "shiftDate": shiftDate})
                if onShiftInfoResult:
                    # check if the queueId have a pointer.
                    shiftPointer = onShiftInfoResult["cecId"].upper()
                else:
                    # if there isn't shiftpointer in the shiftDate
                    if shiftDate == str(datetime.datetime.now())[:10]:
                        if mybackEnd.initDailyShitTable(queueId=queueId) == False:
                            # if there isn't CSE in this queue
                            returnData.update({"queueNameList": queueNameList,
                                               "announcement": "No engineer in this queue, please add cse in.",
                                               "cecId": loginCecId,
                                               "queueName": loginQueueName,
                                               "shiftPointer": "",
                                               "shiftList": [],
                                               "caseSum": "",
                                               "pageCec": ""
                                               })
                            return(render_template("shiftTable.html", returnData=returnData))
                        else:
                            onShiftInfoResult = mybackEnd.db.shiftInfo.find_one(
                                {"queueId": queueId, "shiftPointer": True, "shiftDate": shiftDate})
                            shiftPointer = onShiftInfoResult["cecId"].upper()
                    else:
                        "the some day do not have a pointer, bypass the pointer"
                        shiftPointer = None

                shiftList = []
                caseSum = 0

                shiftInfoResult = mybackEnd.db.shiftInfo.find(
                    {"queueId": queueId, "shiftDate": shiftDate}).sort("shiftOrder")
                for i in shiftInfoResult:
                    status = converStatusIdToStatusStr(i["status"])
                    if shiftPointer == i["cecId"].upper():
                        shiftCecId = i["cecId"].upper()
                    else:
                        shiftCecId = i["cecId"]
                    took = i["took"]
                    caseSum = caseSum+took
                    note = i['dailyNote']
                    cecCaseProgress = str(round(took/8, 2)*100)+"%"
                    shiftList.append(
                        (status, shiftCecId, took, note, cecCaseProgress))
                pageCec = request.args.get('pageCec', None)
                if pageCec != None:
                    flash(
                        "Attention please, you are editing: [" + pageCec + "]")

                returnData.update({"queueNameList": queueNameList,
                                   "announcement": announcement,
                                   "cecId": loginCecId,
                                   "queueName": loginQueueName,
                                   "shiftPointer": shiftPointer,
                                   "shiftList": shiftList,
                                   "caseSum": caseSum,
                                   "pageCec": pageCec
                                   })
                return(render_template("shiftTable.html", returnData=returnData))
        elif request.method == 'POST':
            # cecId = getLoginCec()
            queueId = mybackEnd.db.queueInfo.find_one(
                {"queueName": queueName})["queueId"]
            changeCec = request.form['pageCec']
            changeAction = request.form['changeAction']
            shiftDate = str(datetime.datetime.now())[:10]
            onShiftInfoResult = mybackEnd.db.shiftInfo.find_one(
                                {"queueId": queueId, "shiftPointer": True, "shiftDate": shiftDate})
            shiftPointer = onShiftInfoResult["cecId"].lower()
            if changeAction == "plus":
                if changeCec == "None":
                    mybackEnd.plusTook(shiftPointer, queueId)
                else:
                    mybackEnd.plusTook(changeCec.lower(), queueId)
            elif changeAction == "minus":
                if changeCec == "None":
                    mybackEnd.minusTook(shiftPointer, queueId)
                else:
                    mybackEnd.minusTook(changeCec.lower(), queueId)
            elif changeAction == "nextShift":
                mybackEnd.nextShift(queueId)
            elif changeAction == "lastShift":
                mybackEnd.lastShift(queueId)
            elif changeAction == "alert":
                if changeCec == "None":
                    changeCec=shiftPointer
                myAlert=alerter()
                triggerCec=getLoginCec()

                executor.submit(myAlert.sendMessageToRoom,changeCec.lower(),triggerCec,queueName)
            flash("Alerted: "+changeCec.lower() + "   Have fun!  ")
            return(redirect(url_for("shiftTable", queueName=queueName)))
    else:
        return redirect(url_for("login"))


@app.route('/queue/<queueName>/setting/', methods=['GET', 'POST'])
def queueSetting(queueName):
    if checkUserLogined():
        if request.method == 'GET':
            queueNameList = []
            queueId = mybackEnd.db.queueInfo.find_one(
                {"queueName": queueName})["queueId"]
            queueList = mybackEnd.db.queueInfo.find().sort("queueId")
            for i in queueList:
                queueNameList.append(i["queueName"])
            announcement = mybackEnd.checkQueueInfo(
                queueId, "announcement")
            loginCecId = getLoginCec()
            loginQueueId = mybackEnd.checkEngineerInfo(
                cecId=loginCecId, infoName="queueId")
            loginQueueName = mybackEnd.checkQueueInfo(
                queueId=loginQueueId, infoName="queueName")

            memberList = mybackEnd.getMemberList(queueId=queueId)

            memberListStr = str(mybackEnd.getMemberList(queueId=queueId))[
                1:-1].replace('\'', '')
            shiftPlan = mybackEnd.db.queueInfo.find_one({"queueName": queueName})[
                "defaultShiftPlan"]
            editCec = request.args.get('editCec', None)
            if editCec:
                currentStatusId = mybackEnd.db.cecInfo.find_one(
                    {"memberID": editCec})["status"]
                currentShiftPlan = mybackEnd.db.cecInfo.find_one(
                    {"memberID": editCec})["cecShiftPlan"]
                cecNote = mybackEnd.db.cecInfo.find_one(
                    {"memberID": editCec})["cecNote"]
            else:
                currentStatusId = None
                currentShiftPlan = None
                cecNote = None

            returnData = {"queueNameList": queueNameList,
                          "announcement": announcement,
                          "cecId": loginCecId,
                          "queueName": loginQueueName,
                          "memberList": memberList,
                          "memberListStr": memberListStr,
                          "shiftPlan": shiftPlan,
                          "editCec": editCec,
                          "currentStatus": currentStatusId,
                          "currentShiftPlan": currentShiftPlan,
                          "cecNote": cecNote,
                          "editQueueName": queueName
                          }
            print(returnData)
            return(render_template("setting.html", returnData=returnData))

        if request.method == 'POST':
            editType = request.form["type"]
            queueId = mybackEnd.db.queueInfo.find_one(
                {"queueName": queueName})["queueId"]
            if editType == "member":
                editCec = request.form["editCec"]
                if editCec != "None":
                    newStatus = request.form["newStatus"]
                    newShiftPlan = request.form["newShiftPlan"]
                    newNote = request.form["newNote"]
                    mybackEnd.memberSetting(queueId, editCec, int(
                        newStatus), int(newShiftPlan), newNote)
                    flash("Saved")
                    return(redirect(url_for("queueSetting", queueName=queueName, editCec=editCec)))
                flash("Oops! What are you doing? You submitted null form! Luckily I bypass this issue yet, otherwise database will throw an exception!")
                return(redirect(url_for("queueSetting", queueName=queueName)))
            elif editType == "queue":
                cecListStr = request.form["cecList"]
                cecList = cecListStr.replace(" ", "").strip(",").split(',')
                if cecList[0] == "":
                    flash("A queue should have a CEC LIST")
                    return(redirect(url_for("queueSetting", queueName=queueName)))
                else:
                    newdefaultShiftPlan = request.form["queueShiftPlan"]
                    announcement = request.form["announcement"]
                    mybackEnd.queueSetting(queueId=queueId, newCecList=cecList, defaultShiftPlan=int(newdefaultShiftPlan), announcement=announcement)
                    return(redirect(url_for("queueSetting", queueName=queueName)))

    else:
        return redirect(url_for("login"))
        
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)