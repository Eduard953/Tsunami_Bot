import telebot
from replit import db
import os
import requests
from datetime import datetime
import pywaves as pw

class Tsunami:

    def __init__(self, contractAddress, myAddress = None, node = 'https://nodes.wavesexplorer.com', usdnAssetId = 'DG2xFkPdDwKUoBkzGAhQtLpSGzfXLiCYPEzeKH2Ad24p'):
        self.contractAddress = contractAddress
        self.usdnAssetId = usdnAssetId
        self.myAddress = myAddress
        self.node = node
        self.LONG = 1
        self.SHORT = 2

    def calcRemainMarginWithFundingPayment(self, positionSize, positionMargin, positionLstUpdCPF, unrealizedPnl):
        position = requests.post(self.node + '/utils/script/evaluate/' + self.contractAddress, json = { "expr": "calcRemainMarginWithFundingPayment(" + str(positionSize) + ", "  + str(positionMargin) + ", " + str(positionLstUpdCPF) + ", " + str(unrealizedPnl) + ")" }).json()
        positionValues = position['result']['value']

        return { 'remainMargin': positionValues['_1']['value'], 'badDebt': positionValues['_2']['value'] }

    def getPositionNotionalAndUnrealizedPnl(self, address):
        position = requests.post(self.node + '/utils/script/evaluate/' + self.contractAddress, json = { "expr": "getPositionNotionalAndUnrealizedPnl(\"" + address + "\")" }).json()
        positionValues = position['result']['value']

        return { 'positionNotional': positionValues['_1']['value'], 'unrealizedPnl': positionValues['_2']['value'] }

    def getPosition(self, address):
        position = requests.post(self.node + '/utils/script/evaluate/3N4mv2c2ehFvfSR5pXDCUqFZDaatagfBaMA', json = { "expr": "getPosition(\"" + address + "\")" }).json()
        positionValues = position['result']['value']

        return { 'positionSize': positionValues['_1']['value'], 'margin': positionValues['_2']['value'], 'pon': positionValues['_3']['value'], 'positionLstUpdCPF': positionValues['_4']['value'] }

    def getPayout(self, address):
        position = self.getPosition(address)
        notionalAndUnrealizedPnl = self.getPositionNotionalAndUnrealizedPnl(address)
        remainMarginWithFundingPayment = self.calcRemainMarginWithFundingPayment(position['positionSize'], position['margin'], position['positionLstUpdCPF'], notionalAndUnrealizedPnl['unrealizedPnl'])

        return remainMarginWithFundingPayment['remainMargin'] / 1000000

    def getTwapSpotPrice(self):
        qtAstR = self.getDataFromContract('k_qtAstR')
        bsAstR = self.getDataFromContract('k_bsAstR')

        return qtAstR / bsAstR

    def getOracleTwapPrice(self):
        oracle = self.getDataFromContract('k_ora')
        priceKey = self.getDataFromContract('k_ora_key')

        return self.getDataFromAddress(oracle, priceKey) / 1000000

    def getFundingRate(self):
        underlyingPrice = self.getOracleTwapPrice()
        spotTwapPrice = self.getTwapSpotPrice()
        premium = spotTwapPrice - underlyingPrice
        decimalUnit = (1 * (((((10 * 10) * 10) * 10) * 10) * 10))
        oneDay = 86400 * decimalUnit
        fundingPeriodRaw = self.getDataFromContract('k_fundingPeriod')
        fundingPeriodDecimal = fundingPeriodRaw * decimalUnit
        premiumFraction = (premium * fundingPeriodDecimal) / oneDay

        return premiumFraction / underlyingPrice

    def getTimeToNextFunding(self):
        nextFundingRound = self.getNextFundingTimestamp()
        now = datetime.now()

        return nextFundingRound - now

    def getNextFundingTimestamp(self):
        return self.getDataFromContract('k_nextFundingBlockMinTimestamp')

    def getDataFromContract(self, key):
        return self.getDataFromAddress(self.contractAddress, key)

    def getDataFromAddress(self, address, key):
        return requests.get(self.node + '/addresses/data/' + address + '/' + key).json()['value']

    def liquidate(self, address):
        return self.myAddress.invokeScript(self.contractAddress, 'liquidate', [{'type': 'string', 'value': address}], [])

    def long(self, investment, margin):
        return self.myAddress.invokeScript(self.contractAddress, 'increasePosition', [{'type': 'integer', 'value': self.LONG}, {'type': 'integer', 'value': margin * 1000000}, {'type': 'integer', 'value': int(investment / 4 * 1000000)}], [ { "amount": investment * 1000000, "assetId": self.usdnAssetId }])

    def decreaseLong(self, investment, margin):
        return self.myAddress.invokeScript(self.contractAddress, 'decreasePosition', [{'type': 'integer', 'value': self.LONG}, {'type': 'integer', 'value': investment * 1000000 }, {'type': 'integer', 'value': margin * 1000000}, {'type': 'integer', 'value': int(investment / 2 * 1000000)}], [ ])

    def short(self, investment, margin):
        return self.myAddress.invokeScript(self.contractAddress, 'increasePosition', [{'type': 'integer', 'value': self.SHORT}, {'type': 'integer', 'value': margin * 1000000}, {'type': 'integer', 'value': int(investment / 4 * 1000000)}], [ { "amount": investment * 1000000, "assetId": self.usdnAssetId }])

    def decreaseShort(self, investment, margin):
        return self.myAddress.invokeScript(self.contractAddress, 'decreasePosition', [{'type': 'integer', 'value': self.SHORT}, {'type': 'integer', 'value': investment * 1000000}, {'type': 'integer', 'value': margin * 1000000}, {'type': 'integer', 'value': int(investment / 2 * 1000000)}], [ ])

    def closePosition(self):
        return self.myAddress.invokeScript(self.contractAddress, 'closePosition', [], [])

bot = telebot.TeleBot(os.environ['API_KEY'])


def extract_adress(arg):
    return arg.split()[1:]
  
@bot.message_handler(commands=['start'])
def send_welcome(message):
  bot.reply_to(message, "Dear user! This bot will notify you once your Margin Ratio will near maintenance margin ratio. Please use /address 3PF.., to add your address. More features coming soon")


@bot.message_handler(commands=['address'])
def add_adress(message):
  user_id = message.chat.id
  address = extract_adress(message.text)
  db[user_id] = address
  bot.send_message(user_id, address)
  bot.send_message(user_id, "please check if this is your adress otherwise repeat the command")

bot.infinity_polling()


# @bot.message_handler(commands=['start', 'help'])
# def send_welcome(message):
# 	bot.reply_to(message, "Howdy, how are you doing?")

# @bot.message_handler(func=lambda message: True)
# def echo_all(message):
# 	bot.reply_to(message, message.text)
