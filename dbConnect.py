from pymongo import MongoClient
from pprint import pprint
import logging
import datetime
# Logging setting Begin
# Setup a log formatter
formatter = logging.Formatter(
    "%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s : %(message)s")
# Setup a log file handler and set level/formater

# logFile = logging.FileHandler("./logs/runtime.log")
# logFile.setFormatter(formatter)

# Setup a log console handler and set level/formater
logConsole = logging.StreamHandler()
logConsole.setFormatter(formatter)
# Setup a logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# logger.addHandler(logFile)
logger.addHandler(logConsole)

# Usage:
# logger.debug('DEBUG')
# logger.info('INFO')
# logger.warning('WARN')
# logger.error('ERRO')
# logger.critical('CRIT')

# Logging setting End


class backEnd(object):
    def __init__(self):
        client = MongoClient("mongodb://root:example@10.70.80.241:27017")
        self.db = client.smartClickDb
# Internal Functions:

    def insertNewQueue(self, queueList):
        for i in queueList:
            if self.db.queueInfo.find_one({"queueName": i}) == None:
                """Confirm the queue non-exist in the database."""
                bigestQeueuId = self.db.queueInfo.find({}).sort(
                    "queueId", -1).limit(1)[0]["queueId"]
                logger.debug("The bigest queueId is: " + str(bigestQeueuId))
                __insertQueueItem = {
                    "queueName": i,
                    "defaultShiftPlan": 1,
                    "queueId": bigestQeueuId+1,
                    "lastShiftDate": "",
                    "announcement": "",
                }
                self.db.queueInfo.insert_one(__insertQueueItem)
                # Insert the item into database
                logger.debug("Add new queue: "+i + " into the database.")
            else:
                # Ingnore the existed queue in collection.
                logger.debug("Ignore the exist queue: "+i)

    def insertCecIntoQueueMember(self, queueMemberList, queueId):
        """Define a list which waiting for insert to cecInfo collection"""
        __cecInsertList = []

        for i in queueMemberList:
            __insertCecItem = {
                "queueId": queueId,
                "memberID": i,
                "cecShiftPlan": 1,   # Default shift plan is 1
                "shiftOrder": queueMemberList.index(i),
                "cecNote": "",
                "status": 0
            }
            __cecInsertList.append(__insertCecItem)
        self.db.cecInfo.insert_many(__cecInsertList)

    def getMemberList(self, queueId):
        """Get memeber list from a queue id"""
        findResult = self.db.cecInfo.find(
            {"queueId": queueId}).sort("shiftOrder")
        memberList = []
        for i in findResult:
            memberList.append(i["memberID"])
        return(memberList)

    def deleteCecAction(self, deletedCec, queueId):
        """delete cec from a queueid"""
        for i in deletedCec:
            self.db.cecInfo.delete_one({"memberID": i, "queueId": queueId})
            self.db.shiftInfo.delete_one(
                {"cecId": i, "queueId": queueId, "shiftDate": str(datetime.datetime.now())[:10]})
            logger.debug("Delete cec: " + i)

    def updateCecAction(self, updateCec, queueId, newMemberList):
        """update a cec order from a new cecid list"""
        for i in updateCec:
            self.db.cecInfo.update_one({"memberID": i, "queueId": queueId}, {
                "$set": {"shiftOrder": newMemberList.index(i)}})
            self.db.shiftInfo.update_one({"cecId": i,
                                          "queueId": queueId,
                                          "shiftDate": str(datetime.datetime.now())[:10]},
                                         {"$set": {"shiftOrder": newMemberList.index(i)}})
            logger.debug("Update order cec: "+i)

    def newCecAction(self, newCec, queueId, newMemberList):
        """add a new cec id into queue list."""
        __cecInsertList = []
        __insetTodayShiftList = []
        cecShiftPlanInQueueInfo = self.db.queueInfo.find_one({"queueId": queueId})[
            "defaultShiftPlan"]
        for i in newCec:
            __insertCecItem = {
                "queueId": queueId,
                "memberID": i,
                "cecShiftPlan": cecShiftPlanInQueueInfo,
                "shiftOrder": newMemberList.index(i),
                "cecNote": "",
                "status": 0
            }
            __cecInsertList.append(__insertCecItem)

            __insetTodayShiftInfoDic = {
                "cecId": i,
                "shiftOrder": newMemberList.index(i),
                "status": 0,
                "took": 0,
                "shiftDate": str(datetime.datetime.now())[:10],
                "queueId": queueId,
                "dailyNote": "",
                "shiftPointer": False
            }
            __insetTodayShiftList.append(__insetTodayShiftInfoDic)

            logger.debug("Add cec: " + i)
        self.db.cecInfo.insert_many(__cecInsertList)
        self.db.shiftInfo.insert_many(__insetTodayShiftList)

        todayPointer = self.db.shiftInfo.find_one({"queueId": queueId, "shiftPointer": True, "shiftDate": str(
            datetime.datetime.now())[:10]})
        if not todayPointer:
            self.db.shiftInfo.update_one({"queueId": queueId, "shiftOrder": 0, "shiftDate": str(
                datetime.datetime.now())[:10]}, {"$set": {"shiftPointer": True}})

    def getAvailableEngineerList(self, queueId):
        # Return the engineer info which status NOT PTO and NOT SHADOW
        availableEngineerResult = self.db.shiftInfo.find({"$and": [
            {"shiftDate": str(datetime.datetime.now())[:10]},
            {"queueId": queueId},
            {"status": {"$ne": 6}},
            {"status": {"$ne": 2}}
        ]}).sort("shiftOrder")
        AvailableEngineerList = []
        for i in availableEngineerResult:
            AvailableEngineerList.append(
                [i["shiftOrder"], self.checkEngineerInfo(i["cecId"], infoName="cecShiftPlan"), i["took"]])
            # [(2, 4, 0), (3, 6, 6), (4, 4, 4),(5, 4, 4),(6, 4, 4),(7, 4, 4)]
            # (order,shiftPlan,took)
        return AvailableEngineerList

    def initDailyShitTable(self, queueId):
        """Init daily shift every day."""
        cecInfoResult = self.db.cecInfo.find({"queueId": queueId})
        queueInfoResult = self.db.queueInfo.find({"queueId": queueId})

        def checkExistlastShiftDate():
            if queueInfoResult[0]["lastShiftDate"] == "":
                return False
            else:
                return True
        self.shiftResultDic = {}
        if checkExistlastShiftDate() == True:
            shiftResult = self.db.shiftInfo.find(
                {"queueId": queueId, "shiftDate": queueInfoResult[0]["lastShiftDate"]})

            for i in shiftResult:
                logger.debug(i)
                iDic = {i["cecId"]:
                        {
                    "took": i["took"],
                    "shiftPointer": i["shiftPointer"]
                }
                }
                self.shiftResultDic.update(iDic)
            logger.debug("shiftResultDic: " + str(self.shiftResultDic))

        __insertDailyList = []
        for i in cecInfoResult:
            cecId = i["memberID"]
            shiftOrder = i["shiftOrder"]
            status = i["status"]
            dailyNote = i["cecNote"]
            shiftDate = str(datetime.datetime.now())[:10]

            def ifAllNoPtoCecInQueueFullShift():
                if checkExistlastShiftDate() == True:
                    lastDayOnShiftEngineer = self.db.shiftInfo.find(
                        {"queueId": queueId, "shiftDate": queueInfoResult[0]["lastShiftDate"], "status": {"$ne": 2}})
                    prunePointer = False
                    for i in lastDayOnShiftEngineer:
                        if i["took"] >= self.checkEngineerInfo(cecId=i["cecId"], infoName="cecShiftPlan"):
                            prunePointer = True
                    return(prunePointer)
            prunePointer = ifAllNoPtoCecInQueueFullShift()

            if i["memberID"] in self.shiftResultDic:
                # get value from lastShiftday

                # if lastShiftday full, the took = took - cecPlan
                # if self.shiftResultDic[i["memberID"]]["took"] >= self.checkEngineerInfo(cecId=cecId, infoName="cecShiftPlan"):
                if prunePointer == True:
                    took = self.shiftResultDic[i["memberID"]]["took"] - \
                        self.checkEngineerInfo(
                            cecId=cecId, infoName="cecShiftPlan")
                else:
                    took = self.shiftResultDic[i["memberID"]]["took"]

                shiftPointer = self.shiftResultDic[i["memberID"]
                                                   ]["shiftPointer"]
            else:
                # default value
                took = 0
                shiftPointer = False

            __insertDailyItem = {
                "cecId": cecId,
                "shiftOrder": shiftOrder,
                "status": status,
                "took": took,
                "shiftDate": shiftDate,
                "queueId": queueId,
                "dailyNote": dailyNote,
                "shiftPointer": shiftPointer
            }
            __insertDailyList.append(__insertDailyItem)
        logger.debug(__insertDailyList)
        logger.debug("__insertDailyList len: " +
                     str(__insertDailyList.__len__()))
        if __insertDailyList.__len__() == 0:
            return False
        self.db.shiftInfo.insert_many(__insertDailyList)
        # Update the queueInfo lastShiftDate
        self.db.queueInfo.update_one({"queueId": queueId}, {
            "$set": {"lastShiftDate": str(datetime.datetime.now())[:10]}})

        onShiftInfoResult = self.db.shiftInfo.find_one(
            {"queueId": queueId, "shiftPointer": True, "shiftDate": str(datetime.datetime.now())[:10]})
        # if onShiftInfoResult["status"] in [2,7]:
        #     # TODO
        #     # need point to nextAvailableEngineer()
        #     pass
        if not onShiftInfoResult:
            firstAvailableEngineerId = self.getNextAvailableEngineer(
                queueId=queueId)
            self.db.shiftInfo.update_one({"queueId": queueId, "shiftOrder": firstAvailableEngineerId, "shiftDate": str(datetime.datetime.now())[:10]}, {
                "$set": {"shiftPointer": True,
                         }
            })
# Web Page Button Functions:

    def getNextAvailableEngineer(self, queueId):
        onShiftInfoResult = self.db.shiftInfo.find_one(
            {"queueId": queueId, "shiftPointer": True, "shiftDate": str(datetime.datetime.now())[:10]})
        # onShiftInfoResultOrder = onShiftInfoResult["shiftOrder"]
        availableEngineerList = self.getAvailableEngineerList(
            queueId=queueId)
        if not onShiftInfoResult:
            logger.debug("There is NOT a pointer in today: " +
                         str(datetime.datetime.now())[:10])
            for i in availableEngineerList:
                if i[2] >= i[1]:
                    pass
                else:
                    return(i[0])
        elif onShiftInfoResult:
            onShiftInfoResultOrder = onShiftInfoResult["shiftOrder"]

            def checkIfOnShiftInfoResultOrderInavailableEngineerList():
                logger.debug("availableEngineerList: " +
                             str(availableEngineerList) + ", onShiftInfoResultOrder: "+str(onShiftInfoResultOrder))
                for i in availableEngineerList:

                    if i[0] == onShiftInfoResultOrder:
                        logger.debug("onShiftOrder didn't PTO or shadow")
                        return True
                    else:
                        continue
                logger.debug("onShiftOrder PTO or shadow")
                return False
            if checkIfOnShiftInfoResultOrderInavailableEngineerList():
                logger.debug(
                    "The pointer in availableEngineerList(no PTO & no shadow),availablEngineerList: "+str(availableEngineerList))
                for i in availableEngineerList:
                    if i[0] == onShiftInfoResultOrder:
                        startIndex = (availableEngineerList.index(i)) + 1
                        correctAvailableEngineerList = availableEngineerList[startIndex:] + \
                            availableEngineerList[:startIndex]
                        break
            else:
                logger.debug(
                    "The ponter not in availableEngineerList,(the pointer PTO & shadow")
                onShiftIndex = (onShiftInfoResultOrder, self.checkEngineerInfo(
                    cecId=onShiftInfoResult["cecId"], infoName="cecShiftPlan"), onShiftInfoResult["took"])
                availableEngineerList.append(onShiftIndex)

                def takeFirst(elem):
                    return elem[0]
                availableEngineerList.sort(key=takeFirst)
                correctAvailableEngineerList = availableEngineerList[availableEngineerList.index(
                    onShiftIndex)+1:]+availableEngineerList[:availableEngineerList.index(onShiftIndex)]
                # print(correctAvailableEngineerList)
            #　Start normal search
            logger.debug("correctAvailableEngineerList:" +
                         str(correctAvailableEngineerList))
            for i in correctAvailableEngineerList:
                if i[2] >= i[1]:
                    # TODO if all cse full, will not return a value,this is a bug. need to fix.
                    i[2] = i[2]-i[1]
                else:
                    logger.debug("Found a pointer, there was a pointer in today: " +
                                 str(datetime.datetime.now())[:10] + " onShiftOrder is: [" + str(onShiftInfoResultOrder)+"] nextEngineer is: " + str(i[0]))
                    return(i[0])
                return(correctAvailableEngineerList[0][0])

    def getLastAvailableEngineer(self, queueId):
        onShiftInfoResult = self.db.shiftInfo.find_one(
            {"queueId": queueId, "shiftPointer": True, "shiftDate": str(datetime.datetime.now())[:10]})
        # onShiftInfoResultOrder = onShiftInfoResult["shiftOrder"]
        availableEngineerList = self.getAvailableEngineerList(
            queueId=queueId)
        if not onShiftInfoResult:
            logger.debug("There is NOT a pointer in today: " +
                         str(datetime.datetime.now())[:10])
            for i in availableEngineerList:
                if i[2] >= i[1]:
                    pass
                else:
                    return(i[0])
        elif onShiftInfoResult:
            onShiftInfoResultOrder = onShiftInfoResult["shiftOrder"]

            def checkIfOnShiftInfoResultOrderInavailableEngineerList():
                logger.debug("availableEngineerList: " +
                             str(availableEngineerList) + ", onShiftInfoResultOrder: "+str(onShiftInfoResultOrder))
                for i in availableEngineerList:

                    if i[0] == onShiftInfoResultOrder:
                        logger.debug("onShiftOrder didn't PTO or shadow")
                        return True
                    else:
                        continue
                logger.debug("onShiftOrder PTO or shadow")
                return False
            if checkIfOnShiftInfoResultOrderInavailableEngineerList():
                logger.debug(
                    "The pointer in availableEngineerList(no PTO & no shadow),availablEngineerList: "+str(availableEngineerList))
                for i in availableEngineerList:
                    if i[0] == onShiftInfoResultOrder:
                        startIndex = (availableEngineerList.index(i))
                        list1 = availableEngineerList[startIndex:]
                        list2 = availableEngineerList[:startIndex]
                        list1.reverse()
                        list2.reverse()
                        correctAvailableEngineerList = list2+list1
                        break
            else:
                logger.debug(
                    "The ponter not in availableEngineerList,(the pointer PTO & shadow")
                onShiftIndex = (onShiftInfoResultOrder, self.checkEngineerInfo(
                    cecId=onShiftInfoResult["cecId"], infoName="cecShiftPlan"), onShiftInfoResult["took"])
                availableEngineerList.append(onShiftIndex)

                def takeFirst(elem):
                    return elem[0]
                availableEngineerList.sort(key=takeFirst)
                startIndex = (availableEngineerList.index(onShiftIndex))
                list1 = availableEngineerList[startIndex:]
                list2 = availableEngineerList[:startIndex]
                list1.reverse()
                list2.reverse()
                correctAvailableEngineerList = list2+list1[:-1]
                # print(correctAvailableEngineerList)
            #　Start normal search
            logger.debug("correctAvailableEngineerList: " +
                         str(correctAvailableEngineerList))
            for i in correctAvailableEngineerList:
                if i[2] >= i[1]:
                    i[2] = i[2]-i[1]
                else:
                    logger.debug("Found a pointer, there was a pointer in today: " +
                                 str(datetime.datetime.now())[:10] + " onShiftOrder is: [" + str(onShiftInfoResultOrder)+"] nextEngineer is: " + str(i[0]))
                    return(i[0])
                return(correctAvailableEngineerList[0][0])

    def queueSetting(self, queueId, newCecList, defaultShiftPlan, announcement):
        """The function when click "apply" which in setting page "queue" section."""
        if len(set(newCecList)) == len(newCecList):
            logger.debug("Checked user if input a duplicate cec in list: PASS")
            self.db.queueInfo.update_one({"queueId": queueId}, {
                "$set": {
                    "announcement": announcement,
                    "defaultShiftPlan": defaultShiftPlan
                }
            })
            oldMemberList = self.getMemberList(queueId)
            deletedCec = (list(set(oldMemberList).difference(set(newCecList))))
            updateCec = (
                list(set(oldMemberList).intersection(set(newCecList))))
            newCec = (list(set(newCecList).difference(set(oldMemberList))))
            self.deleteCecAction(deletedCec=deletedCec, queueId=queueId)
            self.updateCecAction(newMemberList=newCecList,
                                 updateCec=updateCec, queueId=queueId)
            if not newCec:
                # bypass error, because update empty list will raise a error up.
                pass
            else:
                self.newCecAction(newMemberList=newCecList,
                                  newCec=newCec, queueId=queueId)
        else:
            logger.debug(
                "Checked user if input a duplicate cec in list: FAILS")
            return False

    def memberSetting(self, queueId, editCec, editStatus, editCecShiftPlan, editNote):
        """The function when click "apply" which in setting page "member" section."""

        self.db.cecInfo.update_one({"queueId": queueId, "memberID": editCec}, {
            "$set": {"status": editStatus,
                     "cecNote": editNote,
                     "cecShiftPlan": editCecShiftPlan
                     }})
        self.db.shiftInfo.update_one({"queueId": queueId, "cecId": editCec, "shiftDate": str(datetime.datetime.now())[:10]}, {
            "$set": {"status": editStatus,
                     "dailyNote": editNote
                     }})

    def checkEngineerInfo(self, cecId, infoName):
        """cecId,infoName
        Return the info of Queue"""
        checkEngineerInfoResult = self.db.cecInfo.find_one({"memberID": cecId})
        if checkEngineerInfoResult:
            logger.debug("Trigger checkEngineerInfo, return the result: " +
                         str(checkEngineerInfoResult[infoName]))
            return checkEngineerInfoResult[infoName]
        else:
            logger.debug("Trigger checkEngineerInfo, return the result: None")
            return None

    def getCseSum(self, queueId, shiftDate):
        # return self.db.shiftInfo.count_documents({"queueId": queueId,
        #                                           "shiftDate": shiftDate
        #                                           "status"
        #                                           })
        """Only return NOT PTO and NOT shadow count"""
        return self.db.shiftInfo.count_documents({"$and": [
            {"shiftDate": shiftDate},
            {"queueId": queueId},
            {"status": {"$ne": 6}},
            {"status": {"$ne": 2}}
        ]})

    def getQueueCaseSum(self, queueId, shiftDate):
        shiftInfoResult = self.db.shiftInfo.find({"queueId": queueId,
                                                  "shiftDate": shiftDate})
        resultSum = 0
        for i in shiftInfoResult:
            resultSum = resultSum+i["took"]
        return resultSum

    def checkQueueInfo(self, queueId, infoName):
        """queueId,infoName
        Return the info of Queue"""
        checkQueueInfoResult = self.db.queueInfo.find_one({"queueId": queueId})
        if checkQueueInfoResult:
            if checkQueueInfoResult[infoName]:
                logger.debug("Trigger checkQueueInfo: " + str(infoName) + " return the result: " +
                             checkQueueInfoResult[infoName])
                return checkQueueInfoResult[infoName]
            else:
                logger.debug("Trigger checkQueueInfo, return the result: None")
                return None
        return None

    def checkCecTook(self, cecId, shiftDate, queueId):
        return self.db.shiftInfo.find_one({"shiftDate": shiftDate,
                                           "queueId": queueId,
                                           "cecId": cecId
                                           })["took"]

    def plusTook(self, cecId, queueId):
        # Trigger plusTook button.
        oldTook = self.checkCecTook(cecId, shiftDate=str(
            datetime.datetime.now())[:10], queueId=queueId)
        tookNew = oldTook+1
        self.db.shiftInfo.update_one({"shiftDate": str(datetime.datetime.now())[:10],
                                      "queueId": queueId,
                                      "cecId": cecId
                                      }, {
            "$set": {"took": tookNew}})
        logger.debug("Trigger [plusTook] button, cec: " + cecId+" queueId: " +
                     str(queueId) + " change from: " + str(oldTook) + " to "+str(tookNew))

    def minusTook(self, cecId, queueId):
        # Trigger plusTook button.
        oldTook = self.checkCecTook(cecId, shiftDate=str(
            datetime.datetime.now())[:10], queueId=queueId)
        tookNew = oldTook-1
        self.db.shiftInfo.update_one({"shiftDate": str(datetime.datetime.now())[:10],
                                      "queueId": queueId,
                                      "cecId": cecId
                                      }, {
            "$set": {"took": tookNew}})
        logger.debug("Trigger [minusTook] button, cec: " + cecId+" queueId: " +
                     str(queueId) + " change from: " + str(oldTook) + " to "+str(tookNew))

    def nextShift(self, queueId):
        logger.debug("Trigger [nextShift] button: ")

        onShiftInfoResult = self.db.shiftInfo.find_one(
            {"queueId": queueId, "shiftPointer": True, "shiftDate": str(datetime.datetime.now())[:10]})

        nextEngineerOrder = self.getNextAvailableEngineer(queueId=queueId)
        if onShiftInfoResult:
            onShiftInfoResultOrder = onShiftInfoResult["shiftOrder"]
            self.db.shiftInfo.update_one({"shiftOrder": onShiftInfoResultOrder, "shiftDate": str(datetime.datetime.now())[:10]}, {
                "$set": {"shiftPointer": False,
                         }
            })
            self.db.shiftInfo.update_one({"shiftOrder": nextEngineerOrder, "shiftDate": str(datetime.datetime.now())[:10]}, {
                "$set": {"shiftPointer": True,
                         }
            })
            logger.debug("Found a exist pointer, changed pointer from: " +
                         str(onShiftInfoResultOrder)+" to: " + str(nextEngineerOrder))

        else:
            self.db.shiftInfo.update_one({"shiftOrder": nextEngineerOrder, "shiftDate": str(datetime.datetime.now())[:10]}, {
                "$set": {"shiftPointer": True,
                         }
            })
            logger.debug(
                "Cannot found a exist pointer ADD pointer to: " + str(nextEngineerOrder))

    def lastShift(self, queueId):
        logger.debug("Trigger [lastShift] button:")

        onShiftInfoResult = self.db.shiftInfo.find_one(
            {"queueId": queueId, "shiftPointer": True, "shiftDate": str(datetime.datetime.now())[:10]})

        lastEngineerOrder = self.getLastAvailableEngineer(queueId=queueId)
        if onShiftInfoResult:
            onShiftInfoResultOrder = onShiftInfoResult["shiftOrder"]
            self.db.shiftInfo.update_one({"shiftOrder": onShiftInfoResultOrder, "shiftDate": str(datetime.datetime.now())[:10]}, {
                "$set": {"shiftPointer": False,
                         }
            })
            self.db.shiftInfo.update_one({"shiftOrder": lastEngineerOrder, "shiftDate": str(datetime.datetime.now())[:10]}, {
                "$set": {"shiftPointer": True,
                         }
            })
            logger.debug("Found a exist pointer, changed pointer from: " +
                         str(onShiftInfoResultOrder)+" to: " + str(lastEngineerOrder))

        else:
            self.db.shiftInfo.update_one({"shiftOrder": lastEngineerOrder, "shiftDate": str(datetime.datetime.now())[:10]}, {
                "$set": {"shiftPointer": True,
                         }
            })
            logger.debug(
                "Cannot found a exist pointer ADD pointer to: " + str(lastEngineerOrder))
