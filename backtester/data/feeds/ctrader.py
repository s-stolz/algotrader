from ctrader_open_api import Client, Protobuf, TcpProtocol, Auth, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import *
from twisted.internet import reactor
import json
import datetime
import calendar
from decouple import config



host = EndPoints.PROTOBUF_LIVE_HOST if config['CTRADER_HOST'].lower() == "live" else EndPoints.PROTOBUF_DEMO_HOST
client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)

def transformTrendbar(trendbar):
    openTime = datetime.datetime.fromtimestamp(trendbar.utcTimestampInMinutes * 60, datetime.timezone.utc)
    openPrice = (trendbar.low + trendbar.deltaOpen) / 100000.0
    highPrice = (trendbar.low + trendbar.deltaHigh) / 100000.0
    lowPrice = trendbar.low / 100000.0
    closePrice = (trendbar.low + trendbar.deltaClose) / 100000.0
    return [openTime, openPrice, highPrice, lowPrice, closePrice, trendbar.volume]


def sendProtoOAGetTrendbarsReq(ctidTraderAccountId, weeks, period, symbolId, clientMsgId = None):
    request = ProtoOAGetTrendbarsReq()
    request.ctidTraderAccountId = ctidTraderAccountId
    request.period = ProtoOATrendbarPeriod.Value(period)
    request.fromTimestamp = int(calendar.timegm((datetime.datetime.utcnow() - datetime.timedelta(weeks=int(weeks))).utctimetuple())) * 1000
    request.toTimestamp = int(calendar.timegm(datetime.datetime.utcnow().utctimetuple())) * 1000
    request.symbolId = int(symbolId)
    deferred = client.send(request, clientMsgId = clientMsgId)

def getPriceFromRelative(symbol, relative): round(relative / 100000.0, symbol.digits)

def onHistoricalTrendbarsReceived(message):

    trendbars = message.trendbars

    data = []

    for trendbar in trendbars:
        data.append(Trendbar(low=getPriceFromRelative(symbol, trendbar.low), high=getPriceFromRelative(symbol, trendbar.low + int(trendbar.deltaHigh)), open=getPriceFromRelative(symbol, trendbar.low + int(trendbar.deltaHigh)), close=getPriceFromRelative(symbol, trendbar.low +int(trendbar.deltaClose))))

    return data

def trendbarsResponseCallback(result):
    print("\nTrendbars received")
    trendbars = Protobuf.extract(result)
    barsData = list(map(transformTrendbar, trendbars.trendbar))
    global dailyBars
    dailyBars.clear()
    dailyBars.extend(barsData)
    print("\ndailyBars length:", len(dailyBars))
    print("\Stopping reactor...")
    reactor.stop()
    
def symbolsResponseCallback(result):
    print("\nSymbols received")
    symbols = Protobuf.extract(result)
    global symbolName
    symbolsFilterResult = list(filter(lambda symbol: symbol.symbolName == symbolName, symbols.symbol))
    if len(symbolsFilterResult) == 0:
        raise Exception(f"There is symbol that matches to your defined symbol name: {symbolName}")
    elif len(symbolsFilterResult) > 1:
        raise Exception(f"More than one symbol matched with your defined symbol name: {symbolName}, match result: {symbolsFilterResult}")
    symbol = symbolsFilterResult[0]
    request = ProtoOAGetTrendbarsReq()
    request.symbolId = symbol.symbolId
    request.ctidTraderAccountId = credentials["AccountId"]
    request.period = ProtoOATrendbarPeriod.D1
    # We set the from/to time stamps to 50 weeks, you can load more data by sending multiple requests
    # Please check the ProtoOAGetTrendbarsReq documentation for more detail
    request.fromTimestamp = int(calendar.timegm((datetime.datetime.utcnow() - datetime.timedelta(weeks=50)).utctimetuple())) * 1000
    request.toTimestamp = int(calendar.timegm(datetime.datetime.utcnow().utctimetuple())) * 1000
    deferred = client.send(request)
    deferred.addCallbacks(trendbarsResponseCallback, onError)
    
def accountAuthResponseCallback(result):
    print("\nAccount authenticated")
    request = ProtoOASymbolsListReq()
    request.ctidTraderAccountId = credentials["AccountId"]
    request.includeArchivedSymbols = False
    deferred = client.send(request)
    deferred.addCallbacks(symbolsResponseCallback, onError)
    
def applicationAuthResponseCallback(result):
    print("\nApplication authenticated")
    request = ProtoOAAccountAuthReq()
    request.ctidTraderAccountId = credentials["AccountId"]
    request.accessToken = credentials["AccessToken"]
    deferred = client.send(request)
    deferred.addCallbacks(accountAuthResponseCallback, onError)

def onError(client, failure): # Call back for errors
    print("\nMessage Error: ", failure)

def disconnected(client, reason): # Callback for client disconnection
    print("\nDisconnected: ", reason)

def onMessageReceived(client, message): # Callback for receiving all messages
    if message.payloadType in [ProtoHeartbeatEvent().payloadType, ProtoOAAccountAuthRes().payloadType, ProtoOAApplicationAuthRes().payloadType, ProtoOASymbolsListRes().payloadType, ProtoOAGetTrendbarsRes().payloadType]:
        return
    print("\nMessage received: \n", Protobuf.extract(message))
    
def connected(client): # Callback for client connection
    print("\nConnected")
    request = ProtoOAApplicationAuthReq()
    request.clientId = credentials["ClientId"]
    request.clientSecret = credentials["Secret"]
    deferred = client.send(request)
    deferred.addCallbacks(applicationAuthResponseCallback, onError)
    
# Setting optional client callbacks
client.setConnectedCallback(connected)
client.setDisconnectedCallback(disconnected)
client.setMessageReceivedCallback(onMessageReceived)